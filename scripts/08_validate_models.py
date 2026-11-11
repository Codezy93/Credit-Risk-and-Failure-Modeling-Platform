"""Recompute exact diagnostics, paired uncertainty, and separate-year calibration."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

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
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.risk_scope import log_risk_scope
from util.calibration import fit_sigmoid
from util.feature_policy import validate_features
from util.metrics import calibration_table, evaluate_model, paired_auc_bootstrap
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table
from util.modeling import build_models
from util.validation import validate_periods


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_inputs(data):
    frames, metadata, hashes = {}, {}, {}
    for item in data["artifacts"]:
        if item["split"] not in ("train", "validation"):
            continue
        path = ROOT / item["path"]
        digest = file_hash(path)
        if digest != item["sha256"]:
            raise ValueError(f"Prepared data changed: {path}")
        frame = pd.read_parquet(path)
        if len(frame) != item["rows"]:
            raise ValueError(f"Unexpected row count: {path}")
        hashes[item["path"]] = digest
        if item["kind"] == "metadata":
            metadata[item["split"]] = frame
        else:
            if list(frame.columns) != data["features"] + [data["target"]]:
                raise ValueError(f"Unexpected feature or target columns: {path}")
            frame[data["numeric_features"]] = frame[data["numeric_features"]].astype("float64")
            frames[item["split"]] = frame
    validate_periods(metadata)
    for split in frames:
        if len(frames[split]) != len(metadata[split]):
            raise ValueError(f"Metadata alignment failed: {split}")
    return frames, metadata, hashes


def confidence_intervals(samples, point_a, point_b):
    rows = []
    for name, column, point in [("logistic_regression", "auc_a", point_a),
                                ("hist_gradient_boosting", "auc_b", point_b),
                                ("boosting_minus_logistic", "delta_b_minus_a", point_b - point_a)]:
        lower, upper = samples[column].quantile([0.025, 0.975])
        rows.append({"comparison": name, "metric": "roc_auc" if column != "delta_b_minus_a" else "auc_difference",
                     "estimate": point, "lower_95": lower, "upper_95": upper})
        if column != "delta_b_minus_a":
            rows.append({"comparison": name, "metric": "gini", "estimate": 2 * point - 1,
                         "lower_95": 2 * lower - 1, "upper_95": 2 * upper - 1})
    return pd.DataFrame(rows)


def main():
    execution_source = Path(__file__).read_text()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", type=int, default=500)
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("At least two bootstrap resamples are required.")
    results = ROOT / "assets/results"
    data = json.loads((results / "model_data_manifest.json").read_text())
    previous = json.loads((results / "model_experiments_latest.json").read_text())
    features, target = data["features"], data["target"]
    policy = validate_features(features)
    if features != previous["features"]:
        raise ValueError("The historical comparison used different features.")
    frames, metadata, input_hashes = load_inputs(data)
    # The stored experiment snapshot binds historical models to their exact inputs.
    historical = {a["path"]: a["sha256"] for a in previous["data_decision_snapshot"]["artifacts"]}
    if any(historical.get(path) != digest for path, digest in input_hashes.items()):
        raise ValueError("The historical models used different prepared inputs.")
    incumbent_path = ROOT / "models/selected_model.joblib"
    incumbent_hash = file_hash(incumbent_path)
    x_validation, y_validation = frames["validation"][features], frames["validation"][target]

    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    experiment_name = "lendingclub_validation_hardening"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    versions = {name: importlib.metadata.version(name) for name in
                ["scikit-learn", "mlflow", "numpy", "pandas", "scipy", "joblib", "cloudpickle", "threadpoolctl"]}
    with mlflow.start_run(experiment_id=experiment_id, run_name="validation_hardening") as batch:
        log_risk_scope()
        batch_id = batch.info.run_id
        result_dir = results / "validation_hardening" / batch_id
        figure_dir = ROOT / "assets/figures/validation_hardening" / batch_id
        model_dir = ROOT / "models/validation_hardening" / batch_id
        for directory in (result_dir, figure_dir, model_dir):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {"status": "running", "batch_run_id": batch_id, "experiment_id": experiment_id,
                    "experiment_name": experiment_name, "features": features, "selected_model": "",
                    "model_uris": {}, "run_ids": {}, "seed": 42, "bootstrap_resamples": args.bootstrap,
                    "feature_policy": policy, "input_sha256": input_hashes, "versions": versions,
                    "historical_batch_id": previous["batch_run_id"], "exploratory_2015_read": False,
                    "deployment_backtest": False, "data_previously_explored": True,
                    "result_directory": str(result_dir.relative_to(ROOT)),
                    "figure_directory": str(figure_dir.relative_to(ROOT)),
                    "model_directory": str(model_dir.relative_to(ROOT))}
        mlflow.log_params({"seed": 42, "bootstrap_resamples": args.bootstrap, "calibration": "sigmoid",
                           "base_fit_years": "2011-2012", "calibration_year": 2013, "evaluation_year": 2014})
        diagnostics, predictions, model_hashes = [], {}, {}
        for name in previous["run_ids"]:
            path = ROOT / previous["model_directory"] / f"{name}.joblib"
            model_hashes[str(path.relative_to(ROOT))] = file_hash(path)
            model = joblib.load(path)
            for split in ("train", "validation"):
                frame = frames[split]
                probabilities = model.predict_proba(frame[features])[:, 1]
                diagnostics.append({"model": name, "split": split,
                                    **evaluate_model(frame[target], probabilities)})
                if split == "validation":
                    predictions[name] = probabilities
        diagnostics = pd.DataFrame(diagnostics)
        print(f"Computing {args.bootstrap} paired bootstrap resamples on 2014 loans", flush=True)
        samples = paired_auc_bootstrap(y_validation, predictions["logistic_regression"],
                                      predictions["hist_gradient_boosting"], args.bootstrap, seed=42)
        point = diagnostics[diagnostics.split == "validation"].set_index("model").roc_auc
        intervals = confidence_intervals(samples, point["logistic_regression"], point["hist_gradient_boosting"])

        fit_mask = metadata["train"].issue_year.isin([2011, 2012])
        calibration_mask = metadata["train"].issue_year == 2013
        if not (fit_mask | calibration_mask).all():
            raise ValueError("Unexpected year in the training population.")
        role_frames = {"model_fit": frames["train"].loc[fit_mask],
                       "calibration": frames["train"].loc[calibration_mask],
                       "evaluation": frames["validation"]}
        role_metadata = {"model_fit": metadata["train"].loc[fit_mask],
                         "calibration": metadata["train"].loc[calibration_mask],
                         "evaluation": metadata["validation"]}
        validate_periods(role_metadata)
        datasets, role_rows = {}, []
        for role, frame in role_frames.items():
            path = model_dir / f"{role}.parquet"
            frame.to_parquet(path, index=False)
            datasets[role] = mlflow.data.from_pandas(frame, source=str(path), targets=target, name=f"{role}_loans")
            mlflow.log_input(datasets[role], context=role)
            mlflow.log_artifact(str(path), artifact_path="datasets")
            dates = pd.to_datetime(role_metadata[role].issue_date)
            role_rows.append({"role": role, "rows": len(frame), "positives": int(frame[target].sum()),
                              "positive_rate": frame[target].mean(), "first_issue_date": str(dates.min().date()),
                              "last_issue_date": str(dates.max().date()), "dataset_digest": datasets[role].digest})
        candidates = build_models(data["numeric_features"], data["categorical_features"], seed=42)
        calibration_rows, bins, evaluations = [], [], []
        for name in ("logistic_regression", "hist_gradient_boosting"):
            print(f"Fitting {name} on 2011-2012; calibrating on 2013", flush=True)
            base = candidates[name]
            base.fit(role_frames["model_fit"][features], role_frames["model_fit"][target])
            before = base.predict_proba(x_validation.head(100))
            calibrated = fit_sigmoid(base, role_frames["calibration"][features], role_frames["calibration"][target],
                                     role_metadata["model_fit"], role_metadata["calibration"])
            if not np.array_equal(before, base.predict_proba(x_validation.head(100))):
                raise ValueError("Calibration modified the base estimator.")
            for version, model in (("raw", base), ("sigmoid", calibrated)):
                label = f"{name}_{version}"
                probabilities = model.predict_proba(x_validation)[:, 1]
                metrics = evaluate_model(y_validation, probabilities)
                calibration_rows.append({"model": name, "version": version, **metrics})
                table = calibration_table(y_validation, probabilities)
                table["model"], table["version"] = name, version
                bins.append(table)
                with mlflow.start_run(experiment_id=experiment_id, run_name=label, nested=True) as run:
                    log_risk_scope()
                    manifest["run_ids"][label] = run.info.run_id
                    mlflow.log_input(datasets["model_fit"], context="training")
                    if version == "sigmoid":
                        mlflow.log_input(datasets["calibration"], context="calibration")
                    mlflow.log_input(datasets["evaluation"], context="validation")
                    mlflow.log_dict(json.loads(json.dumps(base.get_params(), default=str)), "base_parameters.json")
                    mlflow.log_metrics({f"validation_{key}": value for key, value in metrics.items()},
                                       dataset=datasets["evaluation"])
                    path = model_dir / f"{label}.joblib"
                    joblib.dump(model, path)
                    if not np.allclose(joblib.load(path).predict_proba(x_validation.head(100)),
                                       model.predict_proba(x_validation.head(100)), atol=1e-12):
                        raise ValueError("Saved model changed predictions.")
                    info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle",
                        pyfunc_predict_fn="predict_proba",
                        input_example=x_validation.head(5), signature=infer_signature(x_validation.head(5),
                        model.predict_proba(x_validation.head(5))),
                        pip_requirements=[f"{key}=={value}" for key, value in versions.items()])
                    manifest["model_uris"][label] = info.model_uri
                evaluations.append(log_saved_model_evaluation(manifest, label, "validation", datasets["evaluation"]))

        tables = {"historical_exact_metrics": diagnostics, "paired_auc_bootstrap": samples,
                  "auc_confidence_intervals": intervals, "calibration_metrics": pd.DataFrame(calibration_rows),
                  "calibration_bins": pd.concat(bins, ignore_index=True), "cohort_roles": pd.DataFrame(role_rows),
                  "mlflow_native_evaluations": pd.DataFrame(evaluations)}
        historical_lr = joblib.load(ROOT / previous["model_directory"] / "logistic_regression.joblib")
        tables["logistic_coefficients"] = pd.DataFrame({
            "transformed_feature": [*historical_lr.named_steps["prepare"].get_feature_names_out(), "intercept"],
            "coefficient": [*historical_lr.named_steps["model"].coef_[0], historical_lr.named_steps["model"].intercept_[0]]})
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
        for axis, name in zip(axes, ("logistic_regression", "hist_gradient_boosting")):
            axis.plot([0, 1], [0, 1], "--", color="gray")
            for version in ("raw", "sigmoid"):
                table = tables["calibration_bins"]
                table = table[(table.model == name) & (table.version == version)]
                axis.plot(table.mean_probability, table.observed_positive_rate, "o-", label=version)
            axis.set(title=name.replace("_", " "), xlabel="Mean predicted probability", ylabel="Observed charged-off rate")
            axis.legend()
        for suffix in ("png", "svg"):
            figure.savefig(figure_dir / f"calibration.{suffix}", dpi=160)
        plt.close(figure)
        figure, axis = plt.subplots(figsize=(7, 4), constrained_layout=True)
        axis.hist(samples.delta_b_minus_a, bins=30)
        axis.axvline(0, color="red", linestyle="--")
        axis.set(xlabel="Validation AUC: boosting minus logistic regression", ylabel="Bootstrap resamples")
        for suffix in ("png", "svg"):
            figure.savefig(figure_dir / f"paired_auc_difference.{suffix}", dpi=160)
        plt.close(figure)
        if file_hash(incumbent_path) != incumbent_hash:
            raise ValueError("The incumbent artifact changed during validation.")
        source_files = [Path(__file__), ROOT / "requirements.txt", ROOT / "requirements.lock", *sorted((ROOT / "util").glob("*.py"))]
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
                        incumbent_sha256=incumbent_hash, incumbent_unchanged=True, historical_model_sha256=model_hashes,
                        source_sha256={str(path.relative_to(ROOT)): file_hash(path) for path in source_files},
                        results_sha256={path.name: file_hash(path) for path in result_dir.glob("*.csv")},
                        model_sha256={path.name: file_hash(path) for path in model_dir.glob("*.joblib")})
        manifest["execution_script_sha256"] = hashlib.sha256(execution_source.encode()).hexdigest()
        mlflow.log_text(execution_source, "source/executed_08_validate_models.py")
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (results / "validation_hardening_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_dict(policy, "feature_policy_check.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifacts(str(figure_dir), artifact_path="figures")
        mlflow.log_artifact(str(ROOT / "docs/validation_hardening.md"), artifact_path="reports")
        for path in source_files:
            mlflow.log_artifact(str(path), artifact_path="source")
        print(report, flush=True)


def write_report(manifest, tables):
    report = "# Validation hardening\n\n"
    report += ("This is a retrospective analysis of charged-off versus fully-paid, resolved 36-month loans. "
               "The data has already been explored. There is no fresh holdout, fixed-horizon regulatory PD, "
               "or point-in-time deployment backtest. No 2015 rows are read by this stage.\n\n"
               "## Exact historical diagnostics\n\n"
               "Original saved models, unchanged inputs. KS uses every distinct score threshold and is "
               "the maximum absolute TPR–FPR difference; Gini = 2 × AUC − 1. Threshold metrics use 0.5.\n\n")
    report += markdown_table(tables["historical_exact_metrics"]) + "\n\n## Paired AUC uncertainty\n\n"
    report += (f"{manifest['bootstrap_resamples']} stratified loan-level bootstrap resamples, seed 42; identical "
               "sampled loans for both original models. Intervals are 2.5th/97.5th percentiles, conditional on "
               "the fitted models and observed class counts. They exclude model fitting and selection uncertainty, "
               "year-to-year variation, and possible borrower clustering. They are not a significance claim after model selection.\n\n")
    report += markdown_table(tables["auc_confidence_intervals"]) + "\n\n## Separate-year calibration\n\n"
    report += ("Both base models use the original fixed settings, refitted on 2011–2012 only. A frozen estimator "
               "receives sigmoid calibration using 2013 only; both versions are evaluated on 2014. "
               "This differs from the historical 2011–2013 training protocol, so compare raw and sigmoid "
               "within the table below. A calibration method can worsen later-cohort predictions. No model is promoted.\n\n")
    report += markdown_table(tables["cohort_roles"]) + "\n\n" + markdown_table(tables["calibration_metrics"]) + "\n\n"
    for name, group in tables["calibration_metrics"].groupby("model"):
        versions = group.set_index("version")
        raw, sigmoid = versions.loc["raw"], versions.loc["sigmoid"]
        report += (f"{name}: sigmoid minus raw Brier change {sigmoid.brier_score - raw.brier_score:+.6f}; "
                   f"log-loss change {sigmoid.log_loss - raw.log_loss:+.6f}; "
                   f"ECE change {sigmoid.ece_10_uniform_bins - raw.ece_10_uniform_bins:+.6f}. "
                   f"Calibrated mean probability {sigmoid.mean_predicted_probability:.4%}, "
                   f"observed rate {sigmoid.observed_positive_rate:.4%}.\n\n")
    report += "Negative Brier, log-loss, and ECE changes indicate improvement. Assess these together before choosing a calibration policy.\n\n"
    report += (f"![Calibration](../{manifest['figure_directory']}/calibration.png)\n\n"
               f"![Paired differences](../{manifest['figure_directory']}/paired_auc_difference.png)\n\n"
               "Calibration curves show all occupied uniform-width bins, including sparse bins; counts are saved "
               "in calibration_bins.csv. Interpret the tails using those counts.\n\n"
               "## Controls and artifacts\n\n"
               "Shared feature policy rejects post-origination fields before preparation/training, including when "
               "a denied field is accidentally added to an allowlist. This enforces the selected vocabulary; "
               "it cannot certify source timestamps. Expanded bureau fields remain research candidates.\n\n"
               "The coefficient CSV describes the historical logistic pipeline's transformed coordinates "
               "(including scaling, log transforms, missing flags, and one-hot categories). These are not "
               "scorecard points or causal effects.\n\n"
               f"All CSVs and the hashed manifest: [{manifest['result_directory']}](../{manifest['result_directory']}/manifest.json). "
               "MLflow stores the three full role datasets, four model versions, dataset-linked metrics, "
               "and four native classifier evaluations. The incumbent model remains unchanged.\n\n"
               "Reproduce with `make validate` after the core workflow. Use `make all RAW_DATA=/path/to/accepted.csv` "
               "for a headless core run, or a `.csv.gz` file for local decompression.\n\n"
               "Calibration follows the [scikit-learn guidance on disjoint fitting and calibration data]"
               "(https://scikit-learn.org/stable/modules/calibration.html). "
               "Dependency locking uses [uv hash-locked requirements]"
               "(https://docs.astral.sh/uv/pip/compile/).\n")
    (ROOT / "docs/validation_hardening.md").write_text(report)
    marker = "<!-- validation-hardening-statistics -->"
    path = ROOT / "assets/statistics.md"
    section = f"\n\n{marker}\n\n## 21. Validation hardening\n\n" + report.split("\n", 1)[1]
    for name, frame in tables.items():
        section += f"\n\n### {name}\n\n" + markdown_table(frame)
    # Earlier sections are historical snapshots; this stage owns only its appended section.
    section += "\n\n### Full validation manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n"
    contents = path.read_text()
    verification_marker = "<!-- validation-hardening-verification -->"
    if verification_marker in contents:
        # Keep the separately dated end-to-end verification snapshot on report reruns.
        section += "\n\n" + verification_marker + contents.split(verification_marker, 1)[1]
    original = contents.split(marker)[0].rstrip()
    toc = "21. [Validation hardening](#21-validation-hardening)"
    if toc not in original:
        original = original.replace("20. [AUC improvement experiments](#20-auc-improvement-experiments)",
                                    "20. [AUC improvement experiments](#20-auc-improvement-experiments)\n" + toc)
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Saved result CSVs |"):
            lines[index] = f"| Saved result CSVs | {len(list((ROOT / 'assets/results').rglob('*.csv')))} |"
        elif line.startswith("| Saved figure sets |"):
            lines[index] = f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |"
        elif line.startswith("| Saved image files |"):
            lines[index] = f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |"
        elif line.startswith("| Completed stage |"):
            lines[index] = "| Completed stage | Validation hardening complete (section 21); incumbent unchanged |"
    path.write_text(("\n".join(lines) + section).rstrip() + "\n")
    return f"Validation report: {ROOT / 'docs/validation_hardening.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
