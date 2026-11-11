"""Attach real datasets and native classifier evaluations to saved MLflow models."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import mlflow
from util.risk_scope import log_risk_scope
import mlflow.sklearn
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def markdown_table(frame):
    lines = ["| " + " | ".join(frame.columns) + " |",
             "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("—")
            elif isinstance(value, float):
                cells.append(f"{value:,.6f}".rstrip("0").rstrip("."))
            else:
                cells.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_visibility_report(manifest):
    result_dir = ROOT / manifest["result_directory"]
    summary_path = result_dir / "mlflow_native_evaluations.csv"
    summary = pd.read_csv(summary_path)
    info = manifest["native_evaluation_logging"]
    datasets = pd.DataFrame([{"dataset": name, **values} for name, values in info["datasets"].items()])
    report_marker = "<!-- native-mlflow-evaluation-visibility -->"
    report = f"""{report_marker}
## MLflow datasets and native evaluations

Dataset/evaluation logging repaired at {info['completed_at_utc']} without retraining,
model reselection, or threshold changes. The original integration attached dataset
inputs only to training runs and logged custom metrics/CSV artifacts. It omitted
comparison-run inputs, dataset-bound model metrics, and native classifier evaluations.

In experiment **{manifest['experiment_name']}**, expand `first_model_comparison`:

- On the comparison run, inspect dataset inputs for train, validation, and
  exploratory_test. Its `datasets/` artifacts contain the full prepared Parquet
  files, their manifest, and 200-row previews.
- Open any `evaluate_*` child run for native classification metrics, ROC, PR,
  lift, calibration, confusion-matrix plots, and a sampled row-evaluation table.
- On a logged model, select a dataset to inspect its linked metrics. All four
  models have train/validation metrics; only the selected model has exploratory
  evaluation metrics. Dataset names and digests are recorded explicitly.
- The comparison run also contains `evaluation/model_comparison_table.json`
  and `evaluation/native_evaluation_summary.json` for tabular comparison.

### Datasets

{markdown_table(datasets)}

### Native evaluations

{markdown_table(summary)}

Native evaluations use each sklearn classifier's default decision rule (0.5 for
these pipelines). They do not replace the frozen F1-policy results: the selected
threshold remains {manifest['selected_threshold']:.8f}, with its original full-data
metrics bound to the relevant datasets on the selected training run. In this
MLflow version, binary `precision_recall_auc` matches the saved average-precision
values; ROC-AUC and all example counts were checked against the original results.

Every native metric uses the full split. The row-evaluation tables contain a
deterministic uniform sample of at most 1,000 positions, seed 42; they are previews,
not the metric population. Parent previews show the first 200 rows. No SHAP or
InterpretML explanation evaluation was enabled.

The [native evaluation CSV](../{manifest['result_directory']}/mlflow_native_evaluations.csv)
and statistics section 19 contain all evaluation IDs and metrics. Run
`python scripts/06_log_mlflow_evaluations.py` to verify or repair an existing
completed comparison. Running it again reuses the completed repair and creates
no duplicate evaluation runs. Future training calls this logging step automatically.

These are classic ML classifier evaluations. MLflow's separate GenAI evaluation
datasets/scorers are not used for this loan-classification benchmark.
"""
    doc = ROOT / "docs/model_experiments.md"
    doc.write_text(doc.read_text().split(report_marker)[0].rstrip() + "\n\n" + report + "\n")
    archive = result_dir / "report.md"
    archive.write_text(archive.read_text().split(report_marker)[0].rstrip() + "\n\n" + report.replace("../assets/", "../../../") + "\n")
    stats = ROOT / "assets/statistics.md"
    marker = "<!-- mlflow-evaluation-visibility-statistics -->"
    existing_statistics = stats.read_text()
    auc_marker = "<!-- auc-improvement-statistics -->"
    auc_section = ""
    if auc_marker in existing_statistics:
        auc_section = auc_marker + existing_statistics.split(auc_marker, 1)[1]
    original = existing_statistics.split(marker)[0].rstrip()
    original = original.replace("19. [MLflow datasets and evaluations](#19-mlflow-datasets-and-evaluations)\n", "")
    original = original.replace("18. [Model experiments](#18-model-experiments)", "18. [Model experiments](#18-model-experiments)\n19. [MLflow datasets and evaluations](#19-mlflow-datasets-and-evaluations)")
    old_count = "| Saved result CSVs | "
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(old_count):
            lines[index] = f"| Saved result CSVs | {len(list((ROOT / 'assets/results').rglob('*.csv')))} |"
    original = "\n".join(lines)
    digest = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    parts = [marker, "## 19. MLflow datasets and evaluations",
             f"Completed: {info['completed_at_utc']}. Parent run: `{manifest['batch_run_id']}`. Models, selection, and frozen threshold are unchanged.",
             "### Dataset inputs on the comparison run", markdown_table(datasets),
             "The full three Parquet datasets and their manifest are stored under the parent run's datasets/ artifacts. Parent previews are 200 rows each. Model metrics have explicit dataset name/digest associations, verified through MlflowClient.get_logged_model.",
             "### All native evaluation metrics and identifiers", markdown_table(summary),
             f"Source: [mlflow_native_evaluations.csv](results/experiments/{manifest['batch_run_id']}/mlflow_native_evaluations.csv). SHA-256: `{digest}`.",
             "Native metrics evaluate the full 162,570 validation rows for each model and 283,026 exploratory rows for the selected model. The classifier's default rule is 0.5; custom frozen-threshold metrics remain separate on the selected training run. Native binary precision_recall_auc matches this MLflow version's average precision; no selection was changed.",
             "Each evaluation run has ROC, PR, lift, calibration, and confusion-matrix artifacts, a dataset input, model linkage, and a 1,000-row uniformly sampled evaluation table (seed 42). Sample rows are not the population used to compute metrics. No explanation/SHAP evaluation was enabled.",
             "### Verification", "All five evaluation runs finished successfully. Each has its full dataset input and a logged table artifact. All four logged models have dataset-linked train/validation metrics, and the selected model also has exploratory metrics. All three comparison dataset inputs are persisted. Original validation ROC-AUC values and cohort counts match; no retraining or policy change occurred. These checks concern classic ML evaluations, not the separate GenAI dataset/scorer system."]
    stats.write_text(original + "\n\n" + "\n\n".join(parts) + "\n\n" + auc_section)


def log_saved_model_evaluation(manifest, name, split, dataset):
    model_uri = manifest["model_uris"][name]
    model_id = model_uri.split("/")[-1]
    with mlflow.start_run(experiment_id=manifest["experiment_id"],
                          run_name=f"evaluate_{name}_{split}", nested=True) as run:
        log_risk_scope()
        mlflow.set_tags({"run_kind": "evaluation", "model": name, "dataset_split": split,
                         "source_training_run_id": manifest["run_ids"][name]})
        mlflow.log_params({"decision_threshold": 0.5, "positive_label": 1,
                           "model_id": model_id, "evaluation_rows": len(dataset.df)})
        # The sklearn flavor exposes both class predictions and probabilities.
        # Keep native threshold-0.5 evaluation distinct from the frozen F1 policy.
        result = mlflow.models.evaluate(
            model=model_uri, model_id=model_id, data=dataset,
            model_type="classifier", evaluators="default",
            evaluator_config={"metric_prefix": f"native_{split}_", "pos_label": 1,
                              "log_model_explainability": False,
                              "log_metrics_with_dataset_info": False},
        )
        prefix = f"native_{split}_"
        values = {key.removeprefix(prefix): value for key, value in result.metrics.items()}
        assert int(values["example_count"]) == len(dataset.df)

        # Classifier aggregate metrics do not automatically create a row table.
        # A clearly labeled preview makes inputs, scores, and errors inspectable.
        indices = np.sort(np.random.default_rng(42).choice(len(dataset.df), min(1000, len(dataset.df)), replace=False))
        preview = dataset.df.iloc[indices].copy()
        model = mlflow.sklearn.load_model(model_uri)
        x = preview[manifest["features"]]
        probabilities = model.predict_proba(x)[:, 1]
        preview["source_row_number"] = indices
        preview["prediction_probability"] = probabilities
        preview["prediction"] = model.predict(x)
        preview["correct"] = preview.prediction == preview.charged_off
        preview["squared_probability_error"] = (probabilities - preview.charged_off) ** 2
        if name == manifest["selected_model"]:
            preview["prediction_validation_f1"] = (probabilities >= manifest["selected_threshold"]).astype(int)
            mlflow.log_param("frozen_validation_f1_threshold", manifest["selected_threshold"])
        mlflow.log_param("evaluation_preview_rows", len(preview))
        mlflow.log_table(preview.reset_index(drop=True), artifact_file=f"{prefix}eval_results_table.json")
        mlflow.log_dict({"dataset_name": dataset.name, "dataset_digest": dataset.digest,
                         "full_evaluation_rows": len(dataset.df), "preview_rows": len(preview),
                         "preview_sampling": "1000 uniform random positions without replacement; seed 42",
                         "metrics_use_full_dataset": True,
                         "artifacts": {key: artifact.uri for key, artifact in result.artifacts.items()}},
                        "evaluation_manifest.json")
        return {"model": name, "split": split, "evaluation_run_id": run.info.run_id,
                "source_training_run_id": manifest["run_ids"][name], "model_id": model_id,
                "dataset_name": dataset.name, "dataset_digest": dataset.digest,
                "decision_threshold": 0.5, **values}


def add_native_evaluations(manifest):
    """Repair a completed comparison, without retraining or changing selection."""
    mlflow.set_tracking_uri(manifest["tracking_uri"])
    client = mlflow.MlflowClient()
    if manifest.get("native_evaluation_logging", {}).get("status") == "complete":
        assert len(client.get_run(manifest["batch_run_id"]).inputs.dataset_inputs) >= 3
        for run_id in manifest["native_evaluation_logging"]["evaluation_run_ids"]:
            assert client.get_run(run_id).info.status == "FINISHED"
        write_visibility_report(manifest)
        return manifest

    datasets = {}
    paths = {}
    data = manifest["data_decision_snapshot"]
    for artifact in data["artifacts"]:
        if artifact["kind"] != "features_and_target":
            continue
        path = ROOT / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        frame = pd.read_parquet(path)
        frame[manifest["numeric_features"]] = frame[manifest["numeric_features"]].astype("float64")
        split = artifact["split"]
        datasets[split] = mlflow.data.from_pandas(frame, name=split, targets="charged_off", source=str(path))
        paths[split] = path

    result_dir = ROOT / manifest["result_directory"]
    ordinary_metrics = pd.read_csv(result_dir / "train_validation_metrics.csv")
    selected_metrics = pd.read_csv(result_dir / "selected_model_metrics.csv")
    comparison = pd.read_csv(result_dir / "model_comparison.csv")
    records = []
    with mlflow.start_run(run_id=manifest["batch_run_id"]):
        log_risk_scope()
        for split, dataset in datasets.items():
            context = {"train": "training", "validation": "validation", "exploratory_test": "exploratory_evaluation"}[split]
            mlflow.log_input(dataset, context=context)
            mlflow.log_artifact(str(paths[split]), artifact_path="datasets")
            mlflow.log_table(dataset.df.head(200), artifact_file=f"datasets/{split}_preview.json")
        mlflow.log_artifact(str(ROOT / "assets/results/model_data_manifest.json"), artifact_path="datasets")
        mlflow.log_table(comparison, artifact_file="evaluation/model_comparison_table.json")

        for name, training_run_id in manifest["run_ids"].items():
            model_id = manifest["model_uris"][name].split("/")[-1]
            for row in ordinary_metrics[ordinary_metrics.model == name].to_dict(orient="records"):
                split = row.pop("split")
                row.pop("model")
                mlflow.log_metrics({f"{split}_{key}": value for key, value in row.items()},
                    run_id=training_run_id, model_id=model_id, dataset=datasets[split])
            record = log_saved_model_evaluation(manifest, name, "validation", datasets["validation"])
            expected = comparison[comparison.model == name].iloc[0]
            assert np.isclose(record["roc_auc"], expected.validation_roc_auc, atol=1e-12)
            assert np.isclose(record["precision_recall_auc"], expected.validation_average_precision, atol=1e-12)
            records.append(record)
            mlflow.log_metrics({f"{name}_validation_roc_auc": record["roc_auc"],
                                f"{name}_validation_average_precision": expected.validation_average_precision},
                               model_id=model_id, dataset=datasets["validation"])

        winner = manifest["selected_model"]
        test_record = log_saved_model_evaluation(manifest, winner, "exploratory_test", datasets["exploratory_test"])
        test_expected = selected_metrics[(selected_metrics.split == "exploratory_test") & (selected_metrics.policy == "default_0.5")].iloc[0]
        assert np.isclose(test_record["roc_auc"], test_expected.roc_auc, atol=1e-12)
        assert np.isclose(test_record["precision_recall_auc"], test_expected.average_precision, atol=1e-12)
        records.append(test_record)
        for row in selected_metrics.to_dict(orient="records"):
            split, policy = row.pop("split"), row.pop("policy")
            row.pop("model")
            mlflow.log_metrics({f"{split}_{policy}_{key}": value for key, value in row.items()},
                run_id=manifest["selected_run_id"], model_id=manifest["selected_model_uri"].split("/")[-1],
                dataset=datasets[split])
        summary = pd.DataFrame(records)
        summary_path = result_dir / "mlflow_native_evaluations.csv"
        summary.to_csv(summary_path, index=False)
        mlflow.log_table(summary, artifact_file="evaluation/native_evaluation_summary.json")
        mlflow.log_artifact(str(summary_path), artifact_path="evaluation")
        mlflow.log_artifact(str(Path(__file__)), artifact_path="source/native_evaluation")

    # Verify persisted run inputs AND model/dataset links, rather than just local files.
    parent = client.get_run(manifest["batch_run_id"])
    assert {item.dataset.name for item in parent.inputs.dataset_inputs} >= set(datasets)
    for name, uri in manifest["model_uris"].items():
        model = client.get_logged_model(uri.split("/")[-1])
        linked = {metric.dataset_name for metric in model.metrics if metric.dataset_digest}
        assert {"train", "validation"} <= linked
        if name == manifest["selected_model"]:
            assert "exploratory_test" in linked
    for record in records:
        run = client.get_run(record["evaluation_run_id"])
        assert run.info.status == "FINISHED"
        assert any(item.dataset.name == record["split"] for item in run.inputs.dataset_inputs)
        assert "mlflow.loggedArtifacts" in run.data.tags

    manifest["native_evaluation_logging"] = {
        "status": "complete", "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datasets": {name: {"digest": dataset.digest, "rows": len(dataset.df)} for name, dataset in datasets.items()},
        "evaluation_run_ids": [record["evaluation_run_id"] for record in records],
        "native_default_threshold": 0.5, "frozen_policy_threshold": manifest["selected_threshold"],
        "models_retrained": False, "model_selection_changed": False,
        "dataset_artifact_directory": "datasets", "row_previews_are_samples": True,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "backend_links_verified": True,
    }
    manifest["results_sha256"][summary_path.name] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    (result_dir / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "assets/results/model_experiments_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with mlflow.start_run(run_id=manifest["batch_run_id"]):
        log_risk_scope()
        mlflow.log_dict(manifest, "experiment_manifest.json")
    write_visibility_report(manifest)
    return manifest
