"""Bounded validation-only AUC experiments; keep the original selected model intact."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import sys
from time import perf_counter

os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")
import duckdb
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
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table
from util.feature_policy import validate_features
from util.metrics import evaluate_model
from util.temporal_xgboost import fit_temporal_xgboost

RESULTS = ROOT / "assets/results"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        chunk = stream.read(1024 * 1024)
        while chunk:
            digest.update(chunk)
            chunk = stream.read(1024 * 1024)
    return digest.hexdigest()


def main():
    execution_source = Path(__file__).read_text()
    previous_path = RESULTS / "auc_improvement_latest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    original = json.loads((RESULTS / "model_experiments_latest.json").read_text())
    contract = original["data_decision_snapshot"]
    original_model_hash = file_hash(ROOT / "models/selected_model.joblib")
    original_manifest_hash = file_hash(RESULTS / "model_experiments_latest.json")
    if file_hash(ROOT / contract["source_path"]) != contract["source_sha256"]:
        raise ValueError("Clean source differs from the baseline contract.")
    for artifact in contract["artifacts"]:
        if artifact["split"] in ["train", "validation"]:
            if file_hash(ROOT / artifact["path"]) != artifact["sha256"]:
                raise ValueError(f"Changed prepared input: {artifact['path']}")

    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=4")
    con.execute("SET VARIABLE clean_path=?", [str(ROOT / contract["source_path"])])
    raw_path = ROOT / "data/raw/accepted_2007_to_2018Q4.csv"
    con.execute("SET VARIABLE raw_path=?", [str(raw_path)])
    logging.info("Preparing candidate bureau features for 2011–2014 only")
    con.execute((ROOT / "sql/32_auc_feature_expansion.sql").read_text())
    profile = con.execute((ROOT / "sql/33_auc_feature_profile.sql").read_text()).df()
    population = con.execute("SELECT * FROM auc_population ORDER BY issue_date, loan_id").df()
    if (int(population.source_parse_failures.sum()) != 0 or population.loan_id.nunique() != len(population)
            or population.issue_year.max() != 2014 or set(population.charged_off.unique()) != {0, 1}):
        raise ValueError("Candidate population violates the source/label/year contract.")
    metadata_by_split = {}
    for split, expected_rows in [("train", 157993), ("validation", 162570)]:
        current = population[population.split == split]
        metadata = pd.read_parquet(ROOT / f"data/clean/modeling/{split}_metadata.parquet")
        if len(current) != expected_rows:
            raise ValueError(f"Unexpected {split} row count.")
        np.testing.assert_array_equal(current.loan_id.to_numpy(), metadata.loan_id.to_numpy())
        metadata_by_split[split] = metadata
    con.close()

    base = original["features"]
    derived = ["loan_to_income", "revolving_balance_to_income", "high_dti_flag", "over_limit_flag"]
    pricing = ["grade", "sub_grade", "int_rate"]
    bureau = sorted(set(profile.feature) - set(base + derived + pricing))
    feature_sets = {"base13": base, "expanded_bureau": base + bureau + derived,
                    "post_underwriting": base + bureau + derived + pricing}
    training_profile = profile[profile.split == "train"].set_index("feature")
    dropped = training_profile[(training_profile.nonmissing == 0) |
        ((training_profile.distinct_nonmissing == 1) & (training_profile.missing == 0))].index.tolist()
    feature_sets = {name: [feature for feature in values if feature not in dropped] for name, values in feature_sets.items()}
    forbidden = {"loan_id", "issue_date", "issue_year", "loan_status", "charged_off", "last_fico_range_low",
                 "last_fico_range_high", "total_pymnt", "recoveries", "last_pymnt_amnt"}
    for columns in feature_sets.values():
        assert not (set(columns) & forbidden)
        assert not any(name.startswith(("last_", "hardship_", "settlement_", "debt_settlement_")) for name in columns)
    feature_policy = {name: validate_features(features, {"base13": "independent_baseline",
                      "expanded_bureau": "expanded_bureau_candidate", "post_underwriting": "post_underwriting"}[name])
                      for name, features in feature_sets.items()}

    configs = [
        {"name": "shallow", "max_depth": 3, "min_child_weight": 30, "reg_lambda": 10},
        {"name": "regularized", "max_depth": 5, "min_child_weight": 100, "reg_lambda": 20},
        {"name": "deep", "max_depth": 7, "min_child_weight": 100, "reg_lambda": 30},
    ]
    versions = {name: importlib.metadata.version(name) for name in
                ["xgboost-cpu", "scikit-learn", "numpy", "pandas", "mlflow", "scipy", "joblib", "cloudpickle", "threadpoolctl"]}
    mlflow.set_tracking_uri(original["tracking_uri"])
    experiment_name = "lendingclub_auc_ablation"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts/auc_ablation").as_uri())

    with mlflow.start_run(experiment_id=experiment_id, run_name="temporal_stopping_auc_ablation") as parent:
        batch_id = parent.info.run_id
        result_dir = RESULTS / "auc_experiments" / batch_id
        figure_dir = ROOT / "assets/figures/auc_experiments" / batch_id
        model_dir = ROOT / "models/auc_experiments" / batch_id
        data_dir = ROOT / "data/clean/auc_experiments" / batch_id
        for directory in [result_dir, figure_dir, model_dir, data_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        profile.to_csv(result_dir / "feature_profile.csv", index=False)
        mlflow.log_artifact(str(Path(__file__)), artifact_path="source")
        for filename in ["32_auc_feature_expansion.sql", "33_auc_feature_profile.sql"]:
            mlflow.log_artifact(str(ROOT / "sql" / filename), artifact_path="source")
        mlflow.log_dict(original, "previous_comparison_snapshot.json")
        mlflow.log_dict(feature_policy, "feature_policy_checks.json")
        mlflow.set_tags({"protocol_version": "2", "stopping_year": "2013", "selection_year": "2014"})
        mlflow.log_params({"target_auc": 0.8, "selection_metric": "validation_roc_auc",
                           "bounded_trials": 7, "evaluation_2015_used": False,
                           "target_or_cohorts_changed": False, "seed": 42,
                           "stopping_year": 2013, "comparison_year": 2014, "refit_uses_eval_set": False})
        rows, native_rows, feature_audit = [], [], []
        stopping_curves, temporal_details, role_rows = [], {}, []
        candidate_artifacts = []
        dataset_fingerprints = {}
        for set_name, features in feature_sets.items():
            categorical = [name for name in ["home_ownership", "purpose", "grade", "sub_grade"] if name in features]
            numeric = [name for name in features if name not in categorical]
            train = population[population.split == "train"][features + ["charged_off"]].copy()
            validation = population[population.split == "validation"][features + ["charged_off"]].copy()
            train[numeric] = train[numeric].astype("float64")
            validation[numeric] = validation[numeric].astype("float64")
            if not all(np.isfinite(frame[numeric].to_numpy()[~frame[numeric].isna().to_numpy()]).all()
                       for frame in (train, validation)):
                raise ValueError("Nonfinite candidate predictors.")
            datasets = {}
            years = metadata_by_split["train"].issue_year.to_numpy()
            role_frames = {"inner_fit": train.loc[years <= 2012], "stopping": train.loc[years == 2013],
                           "train": train, "validation": validation}
            for split, frame in role_frames.items():
                path = data_dir / f"{set_name}_{split}.parquet"
                con = duckdb.connect()
                con.register("split_frame", frame)
                con.execute("COPY split_frame TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)])
                con.close()
                datasets[split] = mlflow.data.from_pandas(frame, name=f"{split}_{set_name}", targets="charged_off", source=str(path))
                mlflow.log_input(datasets[split], context=split)
                mlflow.log_artifact(str(path), artifact_path="datasets")
                dataset_fingerprints[f"{set_name}_{split}"] = {"path": str(path.relative_to(ROOT)),
                    "sha256": file_hash(path), "mlflow_digest": datasets[split].digest, "rows": len(frame)}
                role_rows.append({"feature_set": set_name, "role": split, "rows": len(frame),
                    "charged_off": int(frame.charged_off.sum()), "positive_rate": frame.charged_off.mean()})
            for feature in features:
                feature_audit.append({"feature_set": set_name, "feature": feature,
                    "role": "existing_candidate" if feature in base else "underwriting_output" if feature in pricing else "derived_ratio_or_flag" if feature in derived else "additional_bureau_candidate",
                    "availability": "after_underwriting" if feature in pricing else "application_or_credit_snapshot_candidate; exact as-of timing not source-certified",
                    "deployment_timing_review_required": True})

            set_configs = configs[:1] if set_name == "base13" else configs
            for config in set_configs:
                name = f"{set_name}_{config['name']}"
                logging.info("Training %s: %s features", name, len(features))
                with mlflow.start_run(experiment_id=experiment_id, run_name=name, nested=True) as run:
                    mlflow.set_tags({"feature_set": set_name, "scoring_point": "post_underwriting" if set_name == "post_underwriting" else "independent_risk_candidate",
                                     "test_used": "false", "run_kind": "training"})
                    mlflow.log_input(datasets["train"], context="training")
                    mlflow.log_input(datasets["validation"], context="validation")
                    mlflow.log_input(datasets["inner_fit"], context="inner_fit")
                    mlflow.log_input(datasets["stopping"], context="stopping")
                    started = perf_counter()
                    params = {key: value for key, value in config.items() if key != "name"}
                    params.update(learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, objective="binary:logistic", eval_metric="auc",
                        tree_method="hist", n_jobs=4, random_state=42)
                    scope = {"base13": "independent_baseline", "expanded_bureau": "expanded_bureau_candidate",
                             "post_underwriting": "post_underwriting"}[set_name]
                    pipeline, learning, details = fit_temporal_xgboost(train, metadata_by_split["train"],
                        features, numeric, categorical, params, scope=scope)
                    temporal_details[name] = details
                    learning["trial"] = name
                    stopping_curves.append(learning)
                    classifier = pipeline.named_steps["model"]
                    mlflow.log_dict(details, "temporal_stopping.json")
                    fit_seconds = perf_counter() - started
                    p_train = pipeline.predict_proba(train[features])[:, 1]
                    p_validation = pipeline.predict_proba(validation[features])[:, 1]
                    train_metrics = evaluate_model(train.charged_off, p_train)
                    validation_metrics = evaluate_model(validation.charged_off, p_validation)
                    values = {"train_roc_auc": train_metrics["roc_auc"], "validation_roc_auc": validation_metrics["roc_auc"],
                        "train_average_precision": train_metrics["average_precision"],
                        "validation_average_precision": validation_metrics["average_precision"],
                        "validation_brier_score": validation_metrics["brier_score"],
                        "validation_log_loss": validation_metrics["log_loss"],
                        "validation_gini": validation_metrics["gini"], "validation_ks": validation_metrics["ks"],
                        "best_iteration": details["stopping_best_iteration"],
                        "selected_estimators": details["selected_estimators"],
                        "stopping_2013_auc": details["stopping_best_auc"], "fit_seconds": fit_seconds}
                    mlflow.log_params({**classifier.get_params(), "feature_count": len(features),
                                       "encoded_features": len(pipeline.named_steps["prepare"].get_feature_names_out())})
                    mlflow.log_dict({"features": features, "numeric_features": numeric, "categorical_features": categorical}, "feature_contract.json")
                    path = model_dir / f"{name}.joblib"
                    joblib.dump(pipeline, path)
                    np.testing.assert_allclose(joblib.load(path).predict_proba(validation[features].head(256))[:, 1], p_validation[:256])
                    info = mlflow.sklearn.log_model(pipeline, name="model", serialization_format="cloudpickle",
                        signature=infer_signature(train[features].head(5), pipeline.predict_proba(train[features].head(5))),
                        input_example=train[features].head(5), pyfunc_predict_fn="predict_proba",
                        pip_requirements=[f"{package}=={version}" for package, version in versions.items()])
                    for split in ["train", "validation"]:
                        metrics = {key: float(value) for key, value in values.items() if key.startswith(split + "_")}
                        mlflow.log_metrics(metrics, model_id=info.model_id, dataset=datasets[split])
                    mlflow.log_metrics({"best_iteration": values["best_iteration"], "fit_seconds": fit_seconds})
                    native = log_saved_model_evaluation({"model_uris": {name: info.model_uri},
                        "run_ids": {name: run.info.run_id}, "experiment_id": str(experiment_id),
                        "features": features, "selected_model": ""}, name, "validation", datasets["validation"])
                    assert np.isclose(native["roc_auc"], values["validation_roc_auc"], atol=1e-12)
                    assert np.isclose(native["precision_recall_auc"], values["validation_average_precision"], atol=1e-12)
                    native_rows.append(native)
                    rows.append({"trial": name, "feature_set": set_name,
                        "scoring_point": "post_underwriting" if set_name == "post_underwriting" else "independent_risk_candidate",
                        "run_id": run.info.run_id, "model_uri": info.model_uri, "feature_count": len(features),
                        "max_depth": config["max_depth"], "min_child_weight": config["min_child_weight"],
                        "reg_lambda": config["reg_lambda"], **values})
                    candidate_artifacts.append({"trial": name, "path": str(path.relative_to(ROOT)), "sha256": file_hash(path), "features": features})
                    logging.info("%s: validation ROC-AUC %.5f, AP %.5f; best iteration %s", name,
                                 values["validation_roc_auc"], values["validation_average_precision"], details["stopping_best_iteration"])

        comparison = pd.DataFrame(rows).sort_values("validation_roc_auc", ascending=False)
        comparison.to_csv(result_dir / "auc_comparison.csv", index=False)
        pd.concat(stopping_curves, ignore_index=True).to_csv(result_dir / "stopping_learning_curves.csv", index=False)
        pd.DataFrame(role_rows).to_csv(result_dir / "temporal_roles.csv", index=False)
        if previous:
            previous_comparison = pd.read_csv(ROOT / previous["result_directory"] / "auc_comparison.csv")
            protocol_comparison = comparison[["trial", "validation_roc_auc", "selected_estimators"]].merge(
                previous_comparison[["trial", "validation_roc_auc"]], on="trial", suffixes=("_current", "_previous"))
            protocol_comparison["auc_change"] = protocol_comparison.validation_roc_auc_current - protocol_comparison.validation_roc_auc_previous
            protocol_comparison.to_csv(result_dir / "protocol_comparison.csv", index=False)
        native_summary = pd.DataFrame(native_rows)
        native_summary.to_csv(result_dir / "native_evaluations.csv", index=False)
        audit = pd.DataFrame(feature_audit)
        audit.to_csv(result_dir / "feature_availability.csv", index=False)
        best_independent = comparison[comparison.scoring_point == "independent_risk_candidate"].iloc[0]
        best_post = comparison[comparison.scoring_point == "post_underwriting"].iloc[0]
        client = mlflow.MlflowClient()
        for row in [best_independent, best_post]:
            client.set_tag(row.run_id, "best_within_scoring_point", "true")
            mlflow.log_metric(f"best_{row.scoring_point}_validation_roc_auc", row.validation_roc_auc)
        mlflow.log_table(comparison, artifact_file="evaluation/auc_comparison.json")
        for path in result_dir.glob("*.csv"):
            mlflow.log_artifact(str(path), artifact_path="evaluation")
        baseline_comparison = pd.read_csv(ROOT / original["result_directory"] / "model_comparison.csv")
        baseline_auc = float(baseline_comparison[baseline_comparison.model == original["selected_model"]].validation_roc_auc.iloc[0])
        fig, axes = plt.subplots(1, 2, figsize=(15, 7))
        colors = comparison.feature_set.map({"base13": "#0072B2", "expanded_bureau": "#009E73", "post_underwriting": "#D55E00"})
        trial_labels = [f"T{index + 1}" for index in range(len(comparison))]
        axes[0].barh([f"{label}: {name}" for label, name in zip(trial_labels, comparison.trial)], comparison.validation_roc_auc, color=colors)
        axes[0].axvline(baseline_auc, color="black", linestyle="--", label=f"Original HGB: {baseline_auc:.4f}")
        axes[0].axvline(0.8, color="gray", linestyle=":", label="Requested 0.80")
        axes[0].set(xlabel="Validation ROC-AUC", xlim=(0.5, 0.85), title="Same target, rows, and temporal validation")
        axes[0].legend(fontsize=8)
        axes[1].scatter(comparison.train_roc_auc, comparison.validation_roc_auc, c=colors, s=70)
        for label, row in zip(trial_labels, comparison.itertuples()):
            axes[1].annotate(label, (row.train_roc_auc, row.validation_roc_auc), xytext=(3, 3), textcoords="offset points", fontsize=9)
        axes[1].set(xlabel="Training ROC-AUC", ylabel="Validation ROC-AUC", title="Training gains do not guarantee validation gains")
        fig.tight_layout()
        fig.savefig(figure_dir / "auc_comparison.png", dpi=160, bbox_inches="tight")
        svg = figure_dir / "auc_comparison.svg"
        fig.savefig(svg, bbox_inches="tight")
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
        plt.close(fig)
        mlflow.log_artifact(str(figure_dir / "auc_comparison.png"), artifact_path="figures")
        if (file_hash(ROOT / "models/selected_model.joblib") != original_model_hash or
                file_hash(RESULTS / "model_experiments_latest.json") != original_manifest_hash):
            raise ValueError("The incumbent artifact or comparison manifest changed.")
        manifest = {"status": "complete", "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "batch_run_id": batch_id, "experiment_id": str(experiment_id), "experiment_name": experiment_name,
            "tracking_uri": original["tracking_uri"], "target_validation_roc_auc": 0.8,
            "best_independent_validation_roc_auc": float(best_independent.validation_roc_auc),
            "best_post_underwriting_validation_roc_auc": float(best_post.validation_roc_auc),
            "target_reached_in_independent_scope": bool(best_independent.validation_roc_auc >= 0.8),
            "target_reached_in_post_underwriting_scope": bool(best_post.validation_roc_auc >= 0.8),
            "original_validation_roc_auc": baseline_auc, "original_selected_model_replaced": False,
            "test_2015_loaded_or_scored": False, "training_rows": 157993, "validation_rows": 162570,
            "feature_sets": feature_sets, "training_only_dropped_features": dropped, "trial_count": len(comparison),
            "feature_policy": feature_policy,
            "protocol_version": 2, "epoch_selection_year": 2013, "candidate_selection_year": 2014,
            "temporal_protocol": "fit 2011-2012, stop on 2013, refit 2011-2013 at fixed tree count, compare 2014",
            "validation_used_for_early_stopping": False, "final_refit_used_eval_set": False,
            "previous_auc_batch_id": previous["batch_run_id"] if previous else None,
            "temporal_details": temporal_details,
            "fixed_params": {"n_estimators": 1200, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8,
                             "early_stopping_rounds": 60, "eval_metric": "auc", "random_state": 42, "n_jobs": 4},
            "grid": configs, "versions": versions, "dataset_fingerprints": dataset_fingerprints,
            "raw_source_sha256": file_hash(raw_path), "clean_source_sha256": contract["source_sha256"],
            "script_sha256": hashlib.sha256(execution_source.encode()).hexdigest(), "model_artifacts": candidate_artifacts,
            "source_sha256": {str(path.relative_to(ROOT)): file_hash(path) for path in
                [Path(__file__), ROOT / "util/temporal_xgboost.py", ROOT / "util/feature_policy.json", ROOT / "requirements.lock"]},
            "result_directory": str(result_dir.relative_to(ROOT)), "figure_directory": str(figure_dir.relative_to(ROOT)),
            "additional_bureau_asof_timing_source_certified": False,
            "results_sha256": {path.name: file_hash(path) for path in result_dir.glob("*.csv")}}
        (result_dir / "auc_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (RESULTS / "auc_improvement_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "auc_manifest.json")
        write_report(manifest, comparison, profile, audit, native_summary)
        mlflow.log_artifact(str(ROOT / "util/temporal_xgboost.py"), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "docs/auc_improvement.md"), artifact_path="reports")
    logging.info("Done: best independent AUC %.5f; post-underwriting %.5f", best_independent.validation_roc_auc, best_post.validation_roc_auc)


def write_report(manifest, comparison, profile, audit, native_summary):
    report = f"""# AUC improvement experiments

Completed: {manifest['completed_at_utc']}. MLflow experiment:
**{manifest['experiment_name']}**, parent run `{manifest['batch_run_id']}`.

## Result

The best independent-scope candidate reached **{manifest['best_independent_validation_roc_auc']:.6f} validation ROC-AUC**,
compared with **{manifest['original_validation_roc_auc']:.6f}** for the original histogram-boosting pipeline.
The separately scoped post-underwriting comparison reached
**{manifest['best_post_underwriting_validation_roc_auc']:.6f}**.
Independent-scope target 0.80 reached: **{manifest['target_reached_in_independent_scope']}**.
Post-underwriting target 0.80 reached: **{manifest['target_reached_in_post_underwriting_scope']}**.

No 2015 dataset was loaded or scored. The original selected model, its threshold,
and original experiment manifest are unchanged. These are validation candidates;
they are not newly measured test results or deployment-approved replacements.

## What changed

- XGBoost on the original 13 predictors separates the model-family effect from
  adding information. The expanded set adds 42 candidate credit-report fields
  and four deterministic ratios/flags. Training-only constants/all-missing fields
  are removed, as listed in the manifest.
- A separate post-underwriting set adds assigned grade, subgrade, and interest
  rate. Those incorporate existing underwriting; their score does not represent
  an independent pre-pricing application model.
- A bounded seven-trial search uses shallow, regularized, and deeper trees.
  Protocol v2 fits stopping candidates on 2011–2012 and chooses their tree counts
  using **2013 only**, with patience 60 and at most 1,200 trees. Each encoder and
  classifier then refits from scratch on 2011–2013 using the frozen tree budget,
  with **no eval_set and no early stopping**. **2014 only compares candidates**.
  The earlier protocol reused 2014 for stopping; its archived results remain
  historical snapshots. This correction does not make the already-explored 2014
  cohort a fresh holdout or remove candidate-selection optimism.
- Numeric missingness is retained for XGBoost. One-hot encoders learn categories
  on 2011–2012 for stopping, then 2011–2013 for the fixed-budget refit, and ignore
  unknown labels. Candidate/constant-column decisions use final training rows
  only; no 2014 outcome enters those decisions. The fitted encoder and model
  are saved as one sklearn pipeline. There is no resampling, target relabeling,
  hard-loan deletion, or inclusion of payment/recovery/settlement/updated-FICO data.
- Cohorts remain 157,993 training loans (2011–2013) and 162,570 validation loans
  (2014), all 36-month, ordinary resolved outcomes. IDs and row order were checked
  against the original split metadata. Each trial has dataset-linked metrics,
  a native classifier evaluation, plots, and a 1,000-row evaluation preview in MLflow.

Inner fit: **57,571** loans (2011–2012). Stopping: **100,422** loans (2013).
The stopping set is included in the later refit and is not an independent final
evaluation. Full roles, every stopping iteration and the old/new protocol
comparison are saved in `temporal_roles.csv`, `stopping_learning_curves.csv` and
`protocol_comparison.csv`. The previous batch is `{manifest['previous_auc_batch_id']}`.

## Comparison

{markdown_table(comparison)}

Training AUC can be much higher than validation AUC. Changing a probability
threshold affects confusion counts, not ROC-AUC; calibration also does not create
new ranking information. An arbitrary 0.80 is a goal, not a defensible promise.
No performance gains from a later-outcome feature would count as an improvement.

## Feature availability limits

The additional fields are bureau/snapshot candidates, not a source-certified
point-in-time contract. Earlier EDA conservatively left these fields out. Their
availability has now been recorded explicitly in a separate experiment audit;
the original dictionary and production-candidate contract were not silently changed.
Historical loan-listing SDK implementations contain many corresponding bureau
attributes, but that does not prove the exact collection/update time in this CSV.
Any apparent gain requires as-of verification before an application-time claim.
The pricing ablation additionally requires scoring after underwriting.

Source implementation evidence: [historical loan API model](https://pkg.go.dev/github.com/TONKPILS/LENDINGCLUB).
This is not an official LendingClub dictionary. Exact additional-field timing
remains unverified and is marked false in the manifest. The original benchmark
also remains resolved-loan, accepted-only and retrospective, not fixed-horizon
default probability or a historical deployment simulation.

## Reproduction and artifacts

Run `python scripts/07_improve_auc.py`. It executes SQL files 32–33 and never
reads the 2015 model split. Model selection is by validation ROC-AUC for this
experiment, distinct from the original AP-selected baseline. Each run archives
its parameters, versions, raw/clean hashes, feature sets, dataset hashes, pipeline
artifacts, metrics, and native evaluation records. No confidence interval or
protected-group fairness evaluation was computed.

[Latest manifest](../assets/results/auc_improvement_latest.json),
[feature/profile and comparison CSVs](../{manifest['result_directory']}/auc_comparison.csv),
[availability audit](../{manifest['result_directory']}/feature_availability.csv), and
[figure](../{manifest['figure_directory']}/auc_comparison.png).

XGBoost API references: [CPU installation](https://xgboost.readthedocs.io/en/stable/install.html)
and [Python API/early stopping](https://xgboost.readthedocs.io/en/stable/python/python_api.html).
"""
    (ROOT / "docs/auc_improvement.md").write_text(report)
    result_dir = ROOT / manifest["result_directory"]
    (result_dir / "report.md").write_text(report.replace("../assets/", "../../../"))
    marker = "<!-- auc-improvement-statistics -->"
    path = ROOT / "assets/statistics.md"
    contents = path.read_text()
    later_marker = "<!-- validation-hardening-statistics -->"
    later = "\n\n" + later_marker + contents.split(later_marker, 1)[1] if later_marker in contents else ""
    original = contents.split(marker)[0].rstrip()
    original = original.replace(
        "> Latest measured model results are in section 18 and docs/model_experiments.md. Earlier sections retain their stage-specific snapshots. Kafka stress tests, InterpretML, and bias evaluations have not run.",
        "> Selected-model results are in section 18; later validation-only AUC research is in section 20. The selected model remains unchanged. Earlier sections retain their stage-specific snapshots. Kafka stress tests, InterpretML, and bias evaluations have not run.")
    original = original.replace("20. [AUC improvement experiments](#20-auc-improvement-experiments)\n", "")
    original = original.replace("19. [MLflow datasets and evaluations](#19-mlflow-datasets-and-evaluations)", "19. [MLflow datasets and evaluations](#19-mlflow-datasets-and-evaluations)\n20. [AUC improvement experiments](#20-auc-improvement-experiments)")
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Saved result CSVs |"):
            lines[index] = f"| Saved result CSVs | {len(list(RESULTS.rglob('*.csv')))} |"
        elif line.startswith("| Saved figure sets |"):
            lines[index] = f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |"
        elif line.startswith("| Saved image files |"):
            lines[index] = f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |"
        elif line.startswith("| Completed stage |"):
            lines[index] = "| Completed stage | Validation-only AUC ablations complete; incumbent unchanged |"
        elif line.startswith("| Models trained / MLflow evaluation metrics |"):
            lines[index] = "| Models trained / MLflow evaluation metrics | Four baseline pipelines (section 18); seven AUC trials (section 20) |"
    parts = [marker, "## 20. AUC improvement experiments", f"Completed: {manifest['completed_at_utc']}.",
        f"MLflow experiment `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`. Validation only: 157,993 train / 162,570 validation rows. No 2015 scoring, no incumbent replacement, no target/cohort changes.",
        f"Best independent-scope ROC-AUC: {manifest['best_independent_validation_roc_auc']:.6f}; separately scoped post-underwriting: {manifest['best_post_underwriting_validation_roc_auc']:.6f}; original validation baseline: {manifest['original_validation_roc_auc']:.6f}. The 0.80 target was reached in independent scope: {manifest['target_reached_in_independent_scope']}; in post-underwriting scope: {manifest['target_reached_in_post_underwriting_scope']}.",
        "Protocol v2 fits 2011–2012, stops on 2013, then refits 2011–2013 using a frozen tree count before comparing on 2014. No final refit eval_set is supplied. 2014 remains previously explored candidate-selection data. Added bureau fields have unverified exact as-of timing, and grade/subgrade/rate results require scoring after underwriting.",
        "### Full comparison", markdown_table(comparison), "### Complete feature profiles (both splits)", markdown_table(profile),
        "### Feature-set availability audit", markdown_table(audit), "### Native evaluation metrics and IDs", markdown_table(native_summary),
        "### Dataset fingerprints", markdown_table(pd.DataFrame([{"dataset": name, **values} for name, values in manifest["dataset_fingerprints"].items()])),
        "### Configuration", "```json\n" + json.dumps({name: manifest[name] for name in ["fixed_params", "grid", "versions", "training_only_dropped_features", "raw_source_sha256", "clean_source_sha256", "script_sha256"]}, indent=2) + "\n```",
        "### Source fingerprints"]
    for name, digest in manifest["results_sha256"].items():
        parts.append(f"- [{name}](results/auc_experiments/{manifest['batch_run_id']}/{name}): `{digest}`")
    for filename in ["temporal_roles.csv", "protocol_comparison.csv", "stopping_learning_curves.csv"]:
        csv_path = result_dir / filename
        if csv_path.exists():
            parts.extend([f"### {csv_path.stem}", markdown_table(pd.read_csv(csv_path))])
    parts.extend(["### Temporal protocol details", "```json\n" + json.dumps(manifest["temporal_details"], indent=2) + "\n```"])
    parts.append("[Full report](../docs/auc_improvement.md). Earlier model/threshold results remain unchanged. No new exploratory-test, bias, stress-test, or production metrics are implied.")
    path.write_text("\n".join(lines) + "\n\n" + "\n\n".join(parts) + later + "\n")


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
