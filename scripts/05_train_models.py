"""Run the first train/validation model comparison and log it in local MLflow."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import re
import sys
from time import perf_counter
import warnings

os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import precision_recall_curve, roc_curve
from threadpoolctl import threadpool_limits


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.mlflow_evaluation import add_native_evaluations
from util.modeling import build_models
from util.metrics import calibration_table, choose_threshold, evaluate_model as evaluate
from util.feature_policy import validate_features
RESULTS = ROOT / "assets/results"
SEED = 42
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        chunk = stream.read(1024 * 1024)
        while chunk:
            digest.update(chunk)
            chunk = stream.read(1024 * 1024)
    return digest.hexdigest()


def markdown_table(frame):
    lines = ["| " + " | ".join(frame.columns) + " |",
             "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append("—")
            elif isinstance(value, float):
                values.append(f"{value:,.6f}".rstrip("0").rstrip("."))
            elif isinstance(value, int):
                values.append(f"{value:,}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def curve_table(y, probabilities, name, split):
    fpr, tpr, roc_thresholds = roc_curve(y, probabilities)
    precision, recall, pr_thresholds = precision_recall_curve(y, probabilities)
    rows = []
    for curve, x, values, thresholds in [
        ("roc", fpr, tpr, roc_thresholds),
        ("precision_recall", recall, precision, np.append(pr_thresholds, np.nan)),
    ]:
        indices = np.unique(np.linspace(0, len(x) - 1, min(256, len(x))).astype(int))
        for i in indices:
            rows.append({"model": name, "split": split, "curve": curve,
                         "x": x[i], "y": values[i], "threshold": thresholds[i]})
    return pd.DataFrame(rows)


def save_figure(figure, directory, name):
    figure.tight_layout()
    figure.savefig(directory / f"{name}.png", dpi=160, bbox_inches="tight")
    svg = directory / f"{name}.svg"
    figure.savefig(svg, bbox_inches="tight")
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(figure)


def plot_results(comparison, curves, calibration, evaluations, figure_dir):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    validation_curves = curves[curves.split == "validation"]
    for name in comparison.model:
        for kind, ax in [("roc", axes[0]), ("precision_recall", axes[1])]:
            points = validation_curves[(validation_curves.model == name) & (validation_curves.curve == kind)]
            if kind == "precision_recall":
                ax.step(points.x, points.y, where="post", label=name.replace("_", " "))
            else:
                ax.plot(points.x, points.y, label=name.replace("_", " "))
        points = calibration[(calibration.model == name) & (calibration.split == "validation")]
        points = points[points.rows >= 200]
        axes[2].plot(points.mean_probability, points.observed_positive_rate, marker="o", label=name.replace("_", " "))
    axes[0].plot([0, 1], [0, 1], "k--", linewidth=1)
    axes[2].plot([0, 1], [0, 1], "k--", linewidth=1)
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="Validation ROC")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Validation precision–recall")
    axes[2].set(xlabel="Mean predicted probability", ylabel="Observed charged-off share", title="Validation calibration (bins with ≥200 rows)")
    axes[0].legend(fontsize=8)
    save_figure(fig, figure_dir, "validation_curves")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, column, label in zip(axes, ["validation_average_precision", "validation_brier_score", "fit_seconds"],
                                ["Validation average precision (higher is better)", "Validation Brier score (lower is better)", "Fit time including preprocessing (seconds)"]):
        ax.barh(comparison.model, comparison[column])
        ax.set(xlabel=label)
    save_figure(fig, figure_dir, "model_comparison")

    test = evaluations[evaluations.split == "exploratory_test"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, row in zip(axes, test.itertuples()):
        matrix = np.array([[row.tn, row.fp], [row.fn, row.tp]])
        ax.imshow(matrix, cmap="Blues")
        for (i, j), count in np.ndenumerate(matrix):
            ax.text(j, i, f"{count:,}", ha="center", va="center", color="white" if count > matrix.max() / 2 else "black")
        ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Fully paid", "Charged off"],
               yticklabels=["Fully paid", "Charged off"], xlabel="Predicted class", ylabel="Observed class",
               title=f"2015 exploratory: {row.policy}\nthreshold={row.threshold:.4f}")
    save_figure(fig, figure_dir, "selected_model_confusion")


def main():
    data_path = RESULTS / "model_data_manifest.json"
    data = json.loads(data_path.read_text())
    assert data["status"] == "complete" and not data["fixed_horizon"]
    features = data["features"]
    feature_policy = validate_features(features)
    numeric, categorical = data["numeric_features"], data["categorical_features"]
    dataset_frames = {}
    for artifact in data["artifacts"]:
        if artifact["kind"] == "features_and_target":
            path = ROOT / artifact["path"]
            assert file_hash(path) == artifact["sha256"], f"Changed prepared dataset: {path}"
            frame = pd.read_parquet(path)
            assert list(frame.columns) == features + [data["target"]]
            assert len(frame) == artifact["rows"] and set(frame[data["target"]].unique()) == {0, 1}
            frame[numeric] = frame[numeric].astype("float64")
            dataset_frames[artifact["split"]] = frame
    x_train = dataset_frames["train"][features]
    y_train = dataset_frames["train"][data["target"]]
    x_validation = dataset_frames["validation"][features]
    y_validation = dataset_frames["validation"][data["target"]]
    models = build_models(numeric, categorical, seed=SEED)

    tracking_uri = "sqlite:///" + str(ROOT / "models/mlflow.db")
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name = "lendingclub_resolved_36m"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    else:
        experiment_id = experiment.experiment_id
    versions = {name: importlib.metadata.version(name) for name in ["scikit-learn", "mlflow", "numpy", "pandas", "scipy", "joblib", "cloudpickle", "threadpoolctl"]}
    pip_requirements = [f"{name}=={version}" for name, version in versions.items()]
    train_dataset = mlflow.data.from_pandas(dataset_frames["train"], source=str(ROOT / "data/clean/modeling/train.parquet"), targets=data["target"], name="train")
    validation_dataset = mlflow.data.from_pandas(dataset_frames["validation"], source=str(ROOT / "data/clean/modeling/validation.parquet"), targets=data["target"], name="validation")

    with mlflow.start_run(experiment_id=experiment_id, run_name="first_model_comparison") as batch:
        batch_id = batch.info.run_id
        result_dir = RESULTS / "experiments" / batch_id
        figure_dir = ROOT / "assets/figures/experiments" / batch_id
        model_dir = ROOT / "models/experiments" / batch_id
        for directory in [result_dir, figure_dir, model_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        mlflow.log_dict(feature_policy, "feature_policy_check.json")
        mlflow.log_artifact(str(ROOT / "util/feature_policy.json"), artifact_path="source")
        mlflow.log_dict(data, "prepared_dataset_snapshot.json")
        mlflow.log_dict(versions, "versions.json")
        mlflow.log_artifact(str(Path(__file__)), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "requirements.txt"), artifact_path="source")
        mlflow.log_params({"seed": SEED, "selection_metric": "validation_average_precision",
                           "tie_breaker": "lower_validation_brier_score", "feature_count": len(features),
                           "thread_limit": 4, "fixed_horizon": False, "evaluation_is_exploratory": True})
        metric_rows, comparison_rows, all_curves, all_calibration = [], [], [], []
        validation_predictions, runs, model_uris, configurations = {}, {}, {}, {}
        for name, model in models.items():
            logging.info("Training %s on %s rows", name, len(y_train))
            with mlflow.start_run(experiment_id=experiment_id, run_name=name, nested=True) as run:
                runs[name] = run.info.run_id
                mlflow.set_tags({"model": name, "selected": "false", "benchmark": "retrospective_resolved_loans"})
                mlflow.log_params({"feature_count": len(features), "seed": SEED})
                mlflow.log_params(model.named_steps["model"].get_params())
                configurations[name] = json.loads(json.dumps(model.get_params(), default=str))
                mlflow.log_dict(configurations[name], "pipeline_parameters.json")
                mlflow.log_input(train_dataset, context="training")
                mlflow.log_input(validation_dataset, context="validation")
                started = perf_counter()
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    model.fit(x_train, y_train)
                fit_seconds = perf_counter() - started
                assert model.classes_.tolist() == [0, 1]
                train_probabilities = model.predict_proba(x_train)[:, 1]
                started = perf_counter()
                probabilities = model.predict_proba(x_validation)[:, 1]
                validation_seconds = perf_counter() - started
                validation_predictions[name] = probabilities
                train_metrics = evaluate(y_train, train_probabilities)
                validation_metrics = evaluate(y_validation, probabilities)
                for split, metrics in [("train", train_metrics), ("validation", validation_metrics)]:
                    metric_rows.append({"model": name, "split": split, **metrics})
                    mlflow.log_metrics({f"{split}_{key}": value for key, value in metrics.items()})
                mlflow.log_metrics({"fit_seconds": fit_seconds, "validation_batch_predict_seconds": validation_seconds})
                all_curves.append(curve_table(y_validation, probabilities, name, "validation"))
                calibration = calibration_table(y_validation, probabilities)
                calibration["model"], calibration["split"] = name, "validation"
                all_calibration.append(calibration)
                model_path = model_dir / f"{name}.joblib"
                joblib.dump(model, model_path)
                reloaded = joblib.load(model_path)
                assert np.allclose(reloaded.predict_proba(x_validation.head(256))[:, 1], probabilities[:256], atol=1e-12)
                info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle",
                    signature=infer_signature(x_train.head(5), model.predict_proba(x_train.head(5))),
                    input_example=x_train.head(5), pyfunc_predict_fn="predict_proba", pip_requirements=pip_requirements)
                model_uris[name] = info.model_uri
                comparison_rows.append({"model": name, "run_id": run.info.run_id, "model_uri": info.model_uri,
                    "train_average_precision": train_metrics["average_precision"],
                    "validation_average_precision": validation_metrics["average_precision"],
                    "validation_roc_auc": validation_metrics["roc_auc"],
                    "validation_brier_score": validation_metrics["brier_score"],
                    "validation_log_loss": validation_metrics["log_loss"],
                    "fit_seconds": fit_seconds, "validation_batch_predict_seconds": validation_seconds,
                    "model_bytes": model_path.stat().st_size})
                logging.info("%s: validation AP %.4f, ROC-AUC %.4f", name, validation_metrics["average_precision"], validation_metrics["roc_auc"])

        comparison = pd.DataFrame(comparison_rows).sort_values(["validation_average_precision", "validation_brier_score"], ascending=[False, True])
        winner = comparison.iloc[0].model
        selected = models[winner]
        threshold = choose_threshold(y_validation, validation_predictions[winner])
        # All model and threshold choices above are now frozen. Only the winner scores 2015.
        x_test = dataset_frames["exploratory_test"][features]
        y_test = dataset_frames["exploratory_test"][data["target"]]
        test_started = perf_counter()
        test_probabilities = selected.predict_proba(x_test)[:, 1]
        test_seconds = perf_counter() - test_started
        evaluation_rows = [{"model": winner, "split": "validation", "policy": "validation_f1", **evaluate(y_validation, validation_predictions[winner], threshold)}]
        for policy, cutoff in [("default_0.5", 0.5), ("validation_f1", threshold)]:
            evaluation_rows.append({"model": winner, "split": "exploratory_test", "policy": policy, **evaluate(y_test, test_probabilities, cutoff)})
        evaluations = pd.DataFrame(evaluation_rows)
        with mlflow.start_run(run_id=runs[winner], nested=True):
            mlflow.set_tag("selected", "true")
            mlflow.log_param("validation_f1_threshold", threshold)
            mlflow.log_metric("exploratory_test_batch_predict_seconds", test_seconds)
            for row in evaluation_rows:
                prefix = f"{row['split']}_{row['policy']}"
                mlflow.log_metrics({f"{prefix}_{key}": value for key, value in row.items() if isinstance(value, (int, float))})
        all_curves.append(curve_table(y_test, test_probabilities, winner, "exploratory_test"))
        calibration = calibration_table(y_test, test_probabilities)
        calibration["model"], calibration["split"] = winner, "exploratory_test"
        all_calibration.append(calibration)
        curves = pd.concat(all_curves, ignore_index=True)
        calibration = pd.concat(all_calibration, ignore_index=True)
        tables = {"model_comparison": comparison, "train_validation_metrics": pd.DataFrame(metric_rows),
                  "selected_model_metrics": evaluations, "calibration_bins": calibration, "curve_points": curves}
        for name, frame in tables.items():
            frame.to_csv(result_dir / f"{name}.csv", index=False)
        plot_results(comparison, curves, calibration, evaluations, figure_dir)
        joblib.dump(selected, ROOT / "models/selected_model.joblib")
        native = joblib.load(ROOT / "models/selected_model.joblib")
        np.testing.assert_allclose(native.predict_proba(x_test.head(256))[:, 1], test_probabilities[:256], atol=1e-12)
        logged = mlflow.sklearn.load_model(model_uris[winner])
        np.testing.assert_allclose(logged.predict_proba(x_test.head(256))[:, 1], test_probabilities[:256], atol=1e-12)
        pyfunc = mlflow.pyfunc.load_model(model_uris[winner])
        np.testing.assert_allclose(np.asarray(pyfunc.predict(x_test.head(256)))[:, 1], test_probabilities[:256], atol=1e-12)
        for name in tables:
            mlflow.log_artifact(str(result_dir / f"{name}.csv"), artifact_path="evaluation")
        for path in figure_dir.glob("*.png"):
            mlflow.log_artifact(str(path), artifact_path="figures")
        mlflow.log_param("selected_model", winner)
        mlflow.log_param("selected_model_run_id", runs[winner])
        manifest = {"stage": "first_model_experiments", "status": "complete",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "batch_run_id": batch_id, "experiment_id": str(experiment_id), "experiment_name": experiment_name,
            "tracking_uri": tracking_uri, "run_ids": runs, "model_uris": model_uris,
            "selected_model": winner, "selected_run_id": runs[winner], "selected_model_uri": model_uris[winner],
            "selection_metric": "validation_average_precision", "tie_breaker": "lower_validation_brier_score",
            "selected_threshold": threshold, "threshold_rule": "maximum validation F1; ties choose lowest threshold",
            "default_threshold": 0.5, "features": features, "numeric_features": numeric, "categorical_features": categorical,
            "positive_class": 1, "class_order": [0, 1], "seed": SEED, "thread_limit": 4,
            "numeric_input_dtype": "float64", "feature_policy": feature_policy,
            "train_rows": len(y_train), "validation_rows": len(y_validation), "exploratory_test_rows": len(y_test),
            "test_scored_models": [winner], "refit_on_validation": False,
            "fixed_horizon": False, "deployment_backtest": False, "test_previously_explored": True,
            "data_manifest_sha256": file_hash(data_path), "data_decision_snapshot": data,
            "training_script_sha256": file_hash(Path(__file__)), "versions": versions,
            "configurations": configurations, "result_directory": str(result_dir.relative_to(ROOT)),
            "figure_directory": str(figure_dir.relative_to(ROOT)), "model_directory": str(model_dir.relative_to(ROOT)),
            "selected_joblib_sha256": file_hash(ROOT / "models/selected_model.joblib"),
            "artifact_reload_checks_passed": True, "stress_testing_started": False,
            "results_sha256": {path.name: file_hash(path) for path in result_dir.glob("*.csv")}}
        failed = mlflow.search_runs(experiment_ids=[experiment_id], filter_string="attributes.status = 'FAILED'")
        manifest["prior_failed_runs"] = failed[["run_id", "status", "tags.mlflow.runName"]].fillna("").to_dict(orient="records") if len(failed) else []
        (result_dir / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (RESULTS / "model_experiments_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "experiment_manifest.json")
        write_report(manifest, comparison, tables, result_dir, figure_dir)
        mlflow.log_artifact(str(ROOT / "docs/model_experiments.md"), artifact_path="reports")
    logging.info("Completed batch %s. Selected %s, threshold %.6f", batch_id, winner, threshold)
    add_native_evaluations(manifest)


def write_report(manifest, comparison, tables, result_dir, figure_dir):
    selected_metrics = tables["selected_model_metrics"]
    test = selected_metrics[(selected_metrics.split == "exploratory_test") & (selected_metrics.policy == "validation_f1")].iloc[0]
    relative_results = str(result_dir.relative_to(ROOT))
    relative_figures = str(figure_dir.relative_to(ROOT))
    default = selected_metrics[(selected_metrics.split == "exploratory_test") & (selected_metrics.policy == "default_0.5")].iloc[0]
    threshold_note = ""
    if default.predicted_positive_rate == 0:
        threshold_note = f"At threshold 0.5 this model predicts no charged-off loans: accuracy is {default.accuracy:.6f}, but recall is zero. The validation-selected threshold makes the sensitivity/false-positive trade-off explicit."
    report = f"""# First MLflow experiment comparison

Completed: {manifest['completed_at_utc']}. Batch run: `{manifest['batch_run_id']}`.

Four pipelines were fitted on {manifest['train_rows']:,} training loans and
compared on {manifest['validation_rows']:,} validation loans. Selection used
validation **average precision**, with lower validation Brier score as the
tie-breaker. Average precision is the scikit-learn metric, not trapezoidal PR-AUC.
No cross-validation, hyperparameter search, or independent calibration fit was run.

## Comparison

{markdown_table(comparison)}

The selected pipeline is **{manifest['selected_model']}**. It was not refitted on
validation. Only this model scored the {manifest['exploratory_test_rows']:,} 2015
loans. A decision threshold of **{manifest['selected_threshold']:.8f}** maximizes
validation F1; ties choose the lowest threshold. This is a benchmark choice,
not a cost-optimized approval policy. Default-0.5 results are also preserved.

## Selected-model evaluations

{markdown_table(selected_metrics)}

At the frozen threshold, exploratory ROC-AUC is {test.roc_auc:.6f}, average
precision is {test.average_precision:.6f}, and Brier score is {test.brier_score:.6f}.
These metrics describe the selected resolved-loan population. Precision, recall,
F1, specificity, and confusion counts depend on the documented threshold.
All rates here are fractions from 0 to 1, not percentages. Calibration ECE uses
10 fixed uniform probability bins weighted by their counts; empty bins are omitted.
Small occupied bins remain in the CSV and should not be overinterpreted.
The calibration figure displays bins with at least 200 rows; all occupied bins
contribute to the saved table and ECE. Precision–recall plots use steps so a
constant-score dummy is not drawn as a misleading sloping line.

## Preprocessing and reproducibility

The feature contract uses 13 predictors. Each pipeline fits its own preprocessing
on training rows only. Logistic regression uses median imputation, log1p for
annual income/revolving balance, numeric scaling, indicators for all numeric
missingness, and one-hot categories with unknowns ignored. Random forest and the
dummy baseline use median imputation, numeric missingness flags, and one-hot
categories. Histogram gradient boosting retains numeric missing values and uses
native categorical splits after training-fitted ordinal encoding; unseen category
codes are negative and treated as missing. No class balancing or oversampling was
used. A missing numeric indicator is not a new source observation.

The dummy model predicts the training positive-class prior. The other configurations
are fixed first-pass choices: logistic C=1, max_iter=1000; random forest 150 trees,
depth 12, minimum leaf 50; histogram boosting 200 iterations, learning rate 0.05,
15 leaves, minimum leaf 50, L2=1, early stopping disabled. Random seeds are 42;
thread pools are limited to four. Full pipeline parameters, package versions,
dataset fingerprints, model URIs, run IDs, and the code fingerprint are in the
manifest and MLflow. A convergence warning fails the run instead of being hidden.

Recorded fit times include preprocessing. Batch prediction times are single
wall-clock observations, not a latency/throughput benchmark. No p95 inference
latency, confidence intervals, financial savings, or stress-test measurements
are claimed. MLflow uses a local SQLite database and local model artifacts.

## Files and loading

- [Latest manifest](../assets/results/model_experiments_latest.json).
- [Full metrics](../{relative_results}/train_validation_metrics.csv),
  [selected evaluations](../{relative_results}/selected_model_metrics.csv),
  [calibration bins](../{relative_results}/calibration_bins.csv), and
  [curve points](../{relative_results}/curve_points.csv).
- [Validation curves](../{relative_figures}/validation_curves.png),
  [comparison](../{relative_figures}/model_comparison.png), and
  [selected confusion matrices](../{relative_figures}/selected_model_confusion.png).

Models and tracking data are local and Git-ignored. `models/selected_model.joblib`
contains the full fitted pipeline; call `predict_proba(frame[features])[:, 1]` for
the charged-off score, then apply the recorded threshold for the F1 decision rule.
Numeric input columns are standardized to float64 before fitting/logging, allowing
missing numeric inputs without an integer-only MLflow schema. The prepared Parquet
files themselves are unchanged.
The native pipeline's `predict()` still uses its classifier's default rule; it
does not automatically apply the validation-selected threshold. MLflow pyfunc
returns the two probability columns in class order [0, 1]. Native joblib,
MLflow sklearn, and MLflow pyfunc reloads were checked against saved-model scores.
The selected artifact is a benchmark candidate, not a production-approved model.

Each rerun creates a new batch with archived result/figure/model directories.
The latest manifest, selected joblib, report, and statistics section point to the
most recent completed batch. Previous batches remain available in MLflow and the
archive directories. No loan-level predictions are published in the result CSVs.
Curves contain at most 256 points per curve for plotting; all scalar metrics and
threshold selection use the complete prediction arrays, not the plotted points.

{threshold_note}

## Limits

2015 was inspected during EDA and remains exploratory. The target is charged off
among selected resolved 36-month loans, not fixed-horizon default probability.
Snapshot label timing prevents a historical deployment-backtest claim. The data
contains accepted loans only. Model explanations, protected-group bias evaluation,
economic stress scenarios, Kafka load testing, and ELK monitoring have not run.
No fairness or causality conclusion follows from these scores.

Run `python scripts/05_train_models.py` from the project root. Open the local UI
with `mlflow ui --backend-store-uri sqlite:///models/mlflow.db --host 127.0.0.1 --port 5000`.
See [MLflow tracking](https://mlflow.org/docs/latest/tracking/) and
[scikit-learn histogram boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
for the underlying APIs.
"""
    (ROOT / "docs/model_experiments.md").write_text(report)
    (result_dir / "report.md").write_text(report.replace("../assets/", "../../../"))
    path = ROOT / "assets/statistics.md"
    marker = "<!-- model-experiment-statistics -->"
    existing_statistics = path.read_text()
    evaluation_marker = "<!-- mlflow-evaluation-visibility-statistics -->"
    later_sections = ""
    if evaluation_marker in existing_statistics:
        later_sections = evaluation_marker + existing_statistics.split(evaluation_marker, 1)[1]
    original = existing_statistics.split(marker)[0].rstrip()
    original = re.sub(r"\| Completed stage \| [^\n]+ \|", "| Completed stage | First MLflow model comparison complete |", original)
    original = re.sub(r"\| Saved result CSVs \| [\d,]+ \|", f"| Saved result CSVs | {len(list(RESULTS.rglob('*.csv')))} |", original)
    original = re.sub(r"\| Saved figure sets \| [\d,]+ \|", f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |", original)
    original = re.sub(r"\| Saved image files \| [\d,]+ \|", f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |", original)
    original = re.sub(r"\| Models trained / MLflow evaluation metrics \| [^\n]+ \|", "| Models trained / MLflow evaluation metrics | Four fitted pipelines; current measured results in section 18 |", original)
    old_notice = "> EDA is complete. The final cohort, feature, and preprocessing decisions are in section 16 and docs/eda_summary.md. Earlier split proposals remain historical snapshot records. No models or stress tests have been run."
    original = original.replace(old_notice, "> Latest measured model results are in section 18 and docs/model_experiments.md. Earlier sections retain their stage-specific snapshots. Kafka stress tests, InterpretML, and bias evaluations have not run.")
    original = original.replace("**Current state: not implemented or measured.** No trained model, MLflow experiment result, fitted preprocessing pipeline, or selected champion exists in this stage.", "**Historical EDA-stage snapshot.** The original metric register below predates training. Current measured model results, fitted pipelines, and selection decisions are recorded in section 18.")
    original = original.replace("18. [Model experiments](#18-model-experiments)\n", "")
    original = original.replace("17. [Model-data preparation](#17-model-data-preparation)", "17. [Model-data preparation](#17-model-data-preparation)\n18. [Model experiments](#18-model-experiments)")
    parts = [marker, "## 18. Model experiments", f"Completed: {manifest['completed_at_utc']}.",
        f"Batch `{manifest['batch_run_id']}`; selected `{manifest['selected_model']}`. Selection uses validation average precision; threshold maximizes validation F1 before exploratory scoring. No refitting on validation and no fixed-horizon/deployment claim.",
        f"[Report](../docs/model_experiments.md), [latest manifest](results/model_experiments_latest.json). All rates below are fractions, not percentages. Fit/prediction times are single wall-clock observations, not stress-test metrics.",
        "### Run and artifact identifiers", markdown_table(comparison),
        "### All training and validation metrics at threshold 0.5", markdown_table(tables["train_validation_metrics"]),
        "### Frozen-threshold and default-threshold evaluations", markdown_table(selected_metrics),
        "### Complete calibration bins", markdown_table(tables["calibration_bins"]),
        "### Configuration and reproducibility", "```json\n" + json.dumps({key: manifest[key] for key in ["seed", "thread_limit", "features", "selected_threshold", "threshold_rule", "versions", "selected_model_uri", "selected_run_id", "selected_joblib_sha256", "data_manifest_sha256", "training_script_sha256"]}, indent=2) + "\n```",
        "Full estimator and preprocessing parameters for every model are preserved under `configurations` in the linked experiment manifest and in each MLflow run. Numeric indicators cover all numeric features; all learned preprocessing was fitted only on training data. No oversampling or class weighting was used.",
        "### Earlier failed attempts", markdown_table(pd.DataFrame(manifest["prior_failed_runs"])) if manifest["prior_failed_runs"] else "None.",
        "Earlier failed run records are retained for transparency; the completed-batch comparisons above do not combine their results. The first logging attempt stopped on a duplicated class-weight parameter with inconsistent string values before logistic regression fitting.",
        "### Saved result fingerprints"]
    for name, digest in manifest["results_sha256"].items():
        target = f"experiments/{manifest['batch_run_id']}/{name}"
        parts.append(f"- [{name}](results/{target}): `{digest}`")
    parts.extend(["Curve-point files retain at most 256 points per model/curve. They are plotting data; scalar metrics and threshold choice use all predictions. Full bin counts, confusion matrices, batch timings, model sizes, versions, identifiers, and aggregate metrics are recorded above or in the manifest. Uncertainty, bias, interpretability, and stress-test metrics remain Not measured.",
                  "### Verification", "Prepared dataset hashes matched; all four local pipelines reloaded with equivalent scores. Selected native and MLflow sklearn/pyfunc probability outputs matched. Model selection and threshold fitting used validation only; only the selected model scored the exploratory dataset."])
    path.write_text(original + "\n\n" + "\n\n".join(parts) + "\n\n" + later_sections)


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
