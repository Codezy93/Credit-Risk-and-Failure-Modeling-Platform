"""Explain the frozen incumbent and audit observed borrower-segment disparities."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")
import duckdb
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.risk_scope import log_risk_scope
from util.feature_policy import validate_features
from util.interpretation import explain_incumbent
from util.metrics import evaluate_model
from util.mlflow_evaluation import markdown_table
from util.segment_audit import disparity_summary, segment_metrics, wilson_interval
from util.validation import validate_periods

DIMENSIONS = ["home", "purpose", "income", "fico", "employment", "delinquency", "bankruptcy",
              "missingness", "state", "application", "income_home", "fico_delinquency"]


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_inputs():
    data = json.loads((ROOT / "assets/results/model_data_manifest.json").read_text())
    reference = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
    features = data["features"]
    policy = validate_features(features)
    if features != reference["features"]:
        raise ValueError("The explanation and reference feature orders differ.")
    frames, metadata, hashes = {}, {}, {}
    historical = {a["path"]: a["sha256"] for a in reference["data_decision_snapshot"]["artifacts"]}
    for item in data["artifacts"]:
        path = ROOT / item["path"]
        if file_hash(path) != item["sha256"] or historical.get(item["path"]) != item["sha256"]:
            raise ValueError(f"Prepared input differs from the original model: {path}")
        hashes[item["path"]] = item["sha256"]
        frame = pd.read_parquet(path)
        if len(frame) != item["rows"]:
            raise ValueError("Unexpected prepared row count.")
        if item["kind"] == "metadata":
            metadata[item["split"]] = frame
        else:
            if list(frame.columns) != features + ["charged_off"]:
                raise ValueError("Unexpected predictor/target schema.")
            frame[data["numeric_features"]] = frame[data["numeric_features"]].astype(float)
            frames[item["split"]] = frame
    validate_periods({name: metadata[name] for name in ["train", "validation", "exploratory_test"]})
    clean = ROOT / data["source_path"]
    if file_hash(clean) != data["source_sha256"]:
        raise ValueError("Clean source changed; state audit join cannot be trusted.")
    return data, reference, policy, frames, metadata, hashes


def group_calibration(frame, dimension):
    rows = []
    for (split, label), group in frame.groupby(["split", f"{dimension}_group"], sort=True):
        bins = np.minimum((group.probability.to_numpy() * 10).astype(int), 9)
        values = group.assign(calibration_bin=bins)
        for number, cell in values.groupby("calibration_bin"):
            lower, upper = wilson_interval(int(cell.charged_off.sum()), len(cell))
            rows.append({"split": split, "dimension": dimension, "group": label,
                "bin": int(number), "rows": len(cell), "mean_probability": cell.probability.mean(),
                "observed_rate": cell.charged_off.mean(), "observed_lower_95": lower, "observed_upper_95": upper})
    return rows


def main():
    execution_source = Path(__file__).read_text()
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-cases", type=int, default=128)
    parser.add_argument("--coalitions", type=int, default=512)
    args = parser.parse_args()
    if args.local_cases < 1 or args.coalitions < 32:
        parser.error("Use at least one random explanation case and 32 coalition samples.")
    data, reference, policy, frames, metadata, input_hashes = read_inputs()
    features, categorical = data["features"], data["categorical_features"]
    model_path = ROOT / "models/selected_model.joblib"
    model_hash = file_hash(model_path)
    if model_hash != reference["selected_joblib_sha256"]:
        raise ValueError("The incumbent artifact changed.")
    model = joblib.load(model_path)
    if model.classes_.tolist() != [0, 1]:
        raise ValueError("Expected positive class 1 = Charged Off.")
    threshold = reference["selected_threshold"]
    income_cuts = frames["train"].annual_inc.quantile([0.25, 0.5, 0.75]).tolist()
    if len(set(income_cuts)) != 3 or not np.isfinite(income_cuts).all():
        raise ValueError("Training income quartiles are not distinct finite cut points.")
    schema_path = ROOT / "assets/results/eda_source_column_audit.csv"
    source_columns = pd.read_csv(schema_path).source_column.str.lower().tolist()
    with (ROOT / "data/raw/accepted_2007_to_2018Q4.csv").open(encoding="utf-8-sig", newline="") as source:
        actual_header = [name.lower() for name in next(csv.reader(source))]
    if set(source_columns) != set(actual_header) or len(source_columns) != len(actual_header):
        raise ValueError("Saved source schema differs from the canonical CSV header.")
    sensitive = {"race": ["race"], "ethnicity": ["ethnicity"], "sex_or_gender": ["sex", "gender"],
        "age_or_birth_date": ["age", "birth_date", "date_of_birth", "dob"],
        "disability": ["disability", "disability_status"], "marital_status": ["marital_status"],
        "religion": ["religion"], "national_origin": ["national_origin"]}
    coverage = pd.DataFrame([{"attribute": attribute, "matching_structured_source_fields": ",".join(sorted(set(aliases) & set(source_columns))),
        "available_as_structured_source_field": bool(set(aliases) & set(source_columns)),
        "protected_group_audit_performed": False,
        "scope_note": "Not inferred from names, text, state, income, or credit history; unavailable in current model inputs."}
        for attribute, aliases in sensitive.items()])
    audit_frames, overall_rows = [], []
    for split in ["validation", "exploratory_test"]:
        frame = frames[split].copy()
        frame["probability"] = model.predict_proba(frame[features])[:, 1]
        frame["loan_id"] = metadata[split].loan_id.to_numpy()
        frame["application_type"] = metadata[split].application_type.to_numpy()
        frame["split"] = split
        frame["has_missing_predictor"] = frame[features].isna().any(axis=1)
        audit_frames.append(frame)
        for name, cutoff in [("frozen_validation_f1", threshold), ("default_0_5", 0.5)]:
            overall_rows.append({"split": split, "policy": name, **evaluate_model(frame.charged_off, frame.probability, cutoff)})
    audit = pd.concat(audit_frames, ignore_index=True)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='1GB'")
    con.register("audit_ids", audit[["loan_id"]])
    con.execute("SET VARIABLE clean_path=?", [str(ROOT / data["source_path"])])
    states = con.execute("SELECT ids.loan_id, c.addr_state, c.loan_id IS NOT NULL AS source_found "
        "FROM audit_ids ids LEFT JOIN read_parquet(getvariable('clean_path')) c USING(loan_id)").df()
    if states.loan_id.duplicated().any() or not states.source_found.all():
        raise ValueError("State audit join must be complete and one-to-one.")
    audit = audit.merge(states[["loan_id", "addr_state"]], on="loan_id", validate="one_to_one", sort=False)
    con.register("audit_population", audit)
    for name, value in zip(["income_q1", "income_q2", "income_q3"], income_cuts):
        con.execute(f"SET VARIABLE {name}=?", [value])
    con.execute((ROOT / "sql/38_audit_segments.sql").read_text())
    labels = con.execute("SELECT * FROM audit_segments").df()
    con.close()
    expected = {split: len(frames[split]) for split in ["validation", "exploratory_test"]}
    for dimension in DIMENSIONS:
        if labels[f"{dimension}_group"].isna().any():
            raise ValueError("A missing segment label would silently drop a loan.")
    if labels.loan_id.duplicated().any() or labels.groupby("split").size().to_dict() != expected:
        raise ValueError("Segment labels do not preserve the evaluation populations.")
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    name = "lendingclub_interpretability_bias"
    experiment = mlflow.get_experiment_by_name(name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(name,
        artifact_location=(ROOT / "models/mlartifacts").as_uri())
    versions = {package: importlib.metadata.version(package) for package in
        ["interpret-core", "shap", "plotly", "scikit-learn", "numpy", "pandas", "scipy", "mlflow", "duckdb"]}
    with mlflow.start_run(experiment_id=experiment_id, run_name="incumbent_explanations_and_segment_audit") as run:
        log_risk_scope()
        batch_id = run.info.run_id
        result_dir = ROOT / "assets/results/interpret_bias" / batch_id
        figure_dir = ROOT / "assets/figures/interpret_bias" / batch_id
        model_dir = ROOT / "models/interpret_bias" / batch_id
        for directory in [result_dir, figure_dir, model_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {"status": "running", "batch_run_id": batch_id, "experiment_name": name, "experiment_id": experiment_id,
            "source_model_name": reference["selected_model"], "source_model_uri": reference["selected_model_uri"],
            "source_model_run_id": reference["selected_run_id"], "source_model_sha256": model_hash,
            "features": features, "feature_policy": policy, "positive_class": "Charged Off",
            "input_sha256": input_hashes, "clean_source_sha256": data["source_sha256"], "seed": 42,
            "source_schema_audit_sha256": file_hash(schema_path),
            "canonical_source_header_sha256": hashlib.sha256(json.dumps(actual_header).encode()).hexdigest(),
            "protected_field_schema_checked_against_actual_header": True,
            "frozen_threshold": threshold, "threshold_source": "original 2014 F1 selection; not retuned here",
            "comparison_threshold": 0.5, "income_quartile_cutpoints_from_training": income_cuts,
            "cohorts": {"validation": "2014, already used for model/threshold selection",
                        "exploratory_test": "2015, previously explored; no fresh holdout claim"},
            "min_supported_rows": 500, "min_supported_positive_and_negative_rows": 50,
            "dimensions": DIMENSIONS, "protected_group_fairness_established": False,
            "protected_attributes_inferred": False, "decision_policy": "flagged risk, not an observed approval or denial",
            "incumbent_retrained": False, "group_thresholds_fitted": False, "versions": versions,
            "result_directory": str(result_dir.relative_to(ROOT)), "figure_directory": str(figure_dir.relative_to(ROOT)),
            "model_directory": str(model_dir.relative_to(ROOT))}
        mlflow.set_tags({"source_model_uri": reference["selected_model_uri"], "scope": "descriptive_segment_disparities",
                         "protected_group_fairness_claim": "false"})
        mlflow.log_dict(manifest, "audit_scope.json")
        mlflow.log_params({"frozen_threshold": threshold, "seed": 42, "local_random_cases": args.local_cases,
            "kernel_coalitions": args.coalitions, "minimum_segment_rows": 500, "minimum_class_rows": 50,
            "protected_attributes_inferred": False})
        for split in ["train", "validation", "exploratory_test"]:
            dataset = mlflow.data.from_pandas(frames[split], source=str(ROOT / f"data/clean/modeling/{split}.parquet"),
                targets="charged_off", name=f"interpret_bias_{split}")
            mlflow.log_input(dataset, context="background_source" if split == "train" else split)
        print("Auditing two frozen thresholds across 12 borrower-segment dimensions", flush=True)
        segment_rows, calibration_rows = [], []
        with mlflow.start_run(experiment_id=experiment_id, run_name="borrower_segment_disparities", nested=True):
            log_risk_scope()
            for dimension in DIMENSIONS:
                for (split, group_name), group in labels.groupby(["split", f"{dimension}_group"], sort=True):
                    for policy_name, cutoff in [("frozen_validation_f1", threshold), ("default_0_5", 0.5)]:
                        segment_rows.append({"split": split, "policy": policy_name, "dimension": dimension, "group": group_name,
                            **segment_metrics(group.charged_off, group.probability, cutoff)})
                calibration_rows.extend(group_calibration(labels, dimension))
            segments = pd.DataFrame(segment_rows)
            disparities = pd.DataFrame(disparity_summary(segments))
            for split, group in segments.groupby("split"):
                for dimension, values in group[group.policy == "frozen_validation_f1"].groupby("dimension"):
                    if values.rows.sum() != expected[split]:
                        raise ValueError("Segment metrics do not reconcile to full cohort counts.")
            mlflow.log_table(segments, artifact_file="segment_metrics.json")
            mlflow.log_table(disparities, artifact_file="segment_spreads.json")
        with mlflow.start_run(experiment_id=experiment_id, run_name="interpretml_and_permutation", nested=True):
            log_risk_scope()
            explanation_tables, settings, local, global_explanation = explain_incumbent(model, frames["train"],
                frames["validation"], features, categorical, threshold, model_dir,
                random_cases=args.local_cases, coalitions=args.coalitions)
            mlflow.log_dict(settings, "explanation_settings.json")
            mlflow.log_metric("maximum_shap_additivity_residual", settings["maximum_additivity_residual"])
            mlflow.log_artifact(str(model_dir / "interpretml_native_explanations.json"), artifact_path="native_explanations")
            mlflow.log_artifact(str(model_dir / "explanation_metadata.json"), artifact_path="native_explanations")
            for path in model_dir.glob("*.parquet"):
                mlflow.log_artifact(str(path), artifact_path="explanation_datasets")
            # Native interactive plots use a CDN for Plotly; PNG/SVG exports work offline.
            for feature in ["delinq_2yrs", "pub_rec_bankruptcies"]:
                global_explanation.visualize(features.index(feature)).write_html(
                    figure_dir / f"interpretml_pdp_{feature}.html", include_plotlyjs="cdn")
            for selection in ["curated_TP", "curated_TN", "curated_FP", "curated_FN"]:
                case = explanation_tables["local_cases"]
                index = int(case[case.selection == selection].index[0])
                local.visualize(index).write_html(figure_dir / f"interpretml_{selection}.html", include_plotlyjs="cdn")
        primary = segments[segments.policy == "frozen_validation_f1"]
        left = primary[primary.split == "validation"]
        right = primary[primary.split == "exploratory_test"]
        drift_columns = ["dimension", "group", "rows", "supported", "observed_rate", "mean_probability", "calibration_bias", "tpr", "fpr", "roc_auc"]
        drift = left[drift_columns].merge(right[drift_columns], on=["dimension", "group"], how="outer", suffixes=("_2014", "_2015"))
        for column in ["observed_rate", "mean_probability", "calibration_bias", "tpr", "fpr", "roc_auc"]:
            drift[f"{column}_change_2015_minus_2014"] = drift[f"{column}_2015"] - drift[f"{column}_2014"]
        drift["supported_both_years"] = drift.supported_2014.eq(True) & drift.supported_2015.eq(True)
        support = []
        for feature in ["delinq_2yrs", "pub_rec_bankruptcies"]:
            counts = frames["train"][feature].astype(object).fillna("Missing").value_counts(dropna=False)
            support.extend({"feature": feature, "training_value": str(value), "rows": int(count)} for value, count in counts.items())
        tables = {"overall_metrics": pd.DataFrame(overall_rows), "protected_attribute_coverage": coverage,
            "segment_metrics": segments, "segment_spreads": disparities,
            "segment_calibration_bins": pd.DataFrame(calibration_rows), "segment_temporal_drift": drift,
            "training_count_feature_support": pd.DataFrame(support), **explanation_tables}
        original_metrics = pd.read_csv(ROOT / reference["result_directory"] / "selected_model_metrics.csv")
        for split in expected:
            old = original_metrics[(original_metrics.split == split) & (original_metrics.policy == "validation_f1")].iloc[0]
            current = tables["overall_metrics"][(tables["overall_metrics"].split == split) &
                (tables["overall_metrics"].policy == "frozen_validation_f1")].iloc[0]
            for metric in ["roc_auc", "average_precision", "brier_score", "precision", "recall", "f1"]:
                if abs(float(old[metric]) - float(current[metric])) > 1e-12:
                    raise ValueError(f"Frozen incumbent metrics changed: {split} {metric}")
            mlflow.log_metrics({f"{split}_{metric}": float(current[metric]) for metric in
                ["roc_auc", "average_precision", "brier_score", "precision", "recall", "f1", "mean_predicted_probability"]})
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        plot_results(tables, figure_dir)
        if file_hash(model_path) != model_hash:
            raise ValueError("The incumbent changed during the explanation audit.")
        source_paths = [Path(__file__), ROOT / "util/interpretation.py", ROOT / "util/explanation_input.py",
            ROOT / "util/segment_audit.py", ROOT / "util/metrics.py", ROOT / "sql/38_audit_segments.sql",
            ROOT / "util/feature_policy.json", ROOT / "requirements.txt", ROOT / "requirements.lock"]
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
            explanation_settings=settings, incumbent_unchanged=True, overall_metrics_match_reference=True,
            explanation_additivity_verified=True, group_population_reconciliation_verified=True,
            execution_script_sha256=hashlib.sha256(execution_source.encode()).hexdigest(),
            source_sha256={str(path.relative_to(ROOT)): file_hash(path) for path in source_paths},
            results_sha256={path.name: file_hash(path) for path in result_dir.glob("*.csv")},
            explanation_dataset_sha256={path.name: file_hash(path) for path in model_dir.glob("*.parquet")})
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (ROOT / "assets/results/interpret_bias_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifacts(str(figure_dir), artifact_path="figures")
        for path in source_paths:
            mlflow.log_artifact(str(path), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "docs/interpret_bias.md"), artifact_path="reports")
        print(report, flush=True)


def save_figure(figure, directory, name):
    figure.savefig(directory / f"{name}.png", dpi=160, bbox_inches="tight")
    path = directory / f"{name}.svg"
    figure.savefig(path, bbox_inches="tight")
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(figure)


def plot_results(tables, directory):
    importance = tables["shap_global_importance"].sort_values("mean_absolute_contribution")
    permutation = tables["permutation_importance"].sort_values("roc_auc_drop_mean")
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    axes[0].barh(importance.feature, importance.mean_absolute_contribution)
    random_count = int(tables["local_cases"].selection.eq("random_sample").sum())
    axes[0].set(xlabel="Mean |SHAP|, probability units", title=f"{random_count} random complete 2014 cases")
    axes[1].barh(permutation.feature, permutation.roc_auc_drop_mean, xerr=permutation.repeat_standard_deviation)
    axes[1].set(xlabel="ROC-AUC decrease after permutation", title="10,000 validation rows; repeat SD bars")
    save_figure(figure, directory, "feature_importance")
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for axis, feature in zip(axes.flat, ["fico_mid", "dti", "delinq_2yrs", "pub_rec_bankruptcies"]):
        rows = tables["partial_dependence"]
        rows = rows[rows.feature == feature].sort_values("grid_value")
        axis.plot(rows.grid_value, rows.mean_probability, "o-")
        axis.fill_between(rows.grid_value, rows.lower_row_spread, rows.upper_row_spread, alpha=0.15)
        axis.set(xlabel=feature, ylabel="Mean charged-off probability", title="PDP; bands show background-row spread")
    save_figure(figure, directory, "partial_dependence")
    figure, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    cases, contributions = tables["local_cases"], tables["local_contributions"]
    for axis, selection in zip(axes.flat, ["curated_TP", "curated_TN", "curated_FP", "curated_FN"]):
        row = cases[cases.selection == selection].iloc[0]
        values = contributions[contributions.case_id == row.case_id].sort_values("contribution_probability_units")
        axis.barh(values.feature, values.contribution_probability_units,
            color=np.where(values.contribution_probability_units > 0, "#D55E00", "#0072B2"))
        axis.axvline(0, color="gray")
        axis.set(xlabel="Contribution to probability", title=f"{selection}: {row.case_id}; probability {row.model_probability:.3f}\n"
                 f"background {row.background_probability:.3f}, observed class {row.observed_charged_off}")
    save_figure(figure, directory, "local_examples")
    primary = tables["segment_metrics"]
    primary = primary[(primary.policy == "frozen_validation_f1") & primary.supported]
    colours = {"validation": "#0072B2", "exploratory_test": "#D55E00"}
    figure, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    for axis, dimension, metric in [(axes[0, 0], "income", "fpr"), (axes[0, 1], "income", "flag_rate"),
                                     (axes[1, 0], "fico", "tpr")]:
        observed = set(primary[primary.dimension == dimension].group)
        preferred = ["Q1_lowest", "Q2", "Q3", "Q4_highest"] if dimension == "income" else ["Below_680", "680_to_719", "720_to_759", "760_plus"]
        labels = [value for value in preferred if value in observed] + sorted(observed - set(preferred))
        for offset, split in [(-0.08, "validation"), (0.08, "exploratory_test")]:
            rows = primary[(primary.dimension == dimension) & (primary.split == split)].set_index("group").reindex(labels)
            x = np.arange(len(labels)) + offset
            axis.errorbar(x, rows[metric], yerr=[rows[metric] - rows[f"{metric}_lower_95"],
                rows[f"{metric}_upper_95"] - rows[metric]], fmt="o", capsize=3, label=split, color=colours[split])
        axis.set(xticks=np.arange(len(labels)), xticklabels=labels, ylabel=metric, title=f"Supported {dimension} segments")
        axis.tick_params(axis="x", labelrotation=20)
        axis.legend(fontsize=8)
    for split in ["validation", "exploratory_test"]:
        rows = primary[(primary.dimension == "income") & (primary.split == split)]
        axes[1, 1].scatter(rows.mean_probability, rows.observed_rate, label=split, color=colours[split])
        for row in rows.itertuples():
            offset = (-12, -11) if split == "validation" else (5, 5)
            axes[1, 1].annotate(row.group, (row.mean_probability, row.observed_rate), fontsize=7,
                xytext=offset, textcoords="offset points", color=colours[split])
    axes[1, 1].plot([0, 0.25], [0, 0.25], "--", color="gray")
    axes[1, 1].set(xlabel="Mean predicted probability", ylabel="Observed charged-off rate", title="Income-segment calibration")
    axes[1, 1].legend(fontsize=8)
    save_figure(figure, directory, "segment_disparities")


def write_report(manifest, tables):
    settings = manifest["explanation_settings"]
    report = "# InterpretML and borrower-segment bias analysis\n\n"
    report += ("This stage explains the unchanged histogram-gradient-boosting incumbent and measures "
        "descriptive disparities on 2014 validation and previously explored 2015 loans. It does not "
        "retrain a model, adjust thresholds or establish protected-group fairness.\n\n")
    leaders = ", ".join(tables["shap_global_importance"].feature.head(3))
    income = tables["segment_metrics"]
    income = income[(income.split == "exploratory_test") & (income.policy == "frozen_validation_f1") & (income.dimension == "income")].set_index("group")
    low, high = income.loc["Q1_lowest"], income.loc["Q4_highest"]
    report += (f"## Main findings\n\nThe top three sampled SHAP features are **{leaders}**; permutation importance "
        "provides a separate ranking cross-check. On 2015 loans, the lowest/highest training-defined income "
        f"quartiles have false-positive rates **{low.fpr:.2%} / {high.fpr:.2%}**, default-capture rates "
        f"**{low.tpr:.2%} / {high.tpr:.2%}**, and observed charged-off rates "
        f"**{low.observed_rate:.2%} / {high.observed_rate:.2%}**. These are material descriptive segment "
        "differences at a common risk threshold; they are not measured denial rates or proof of discrimination. "
        "Case mix, selection, label quality and decision context remain unresolved.\n\n")
    report += (
        "## InterpretML methods and sampling\n\n"
        f"InterpretML ShapKernel explains the positive-class probability using {settings['kernel_background_rows']} "
        f"uniformly sampled complete training rows and {settings['coalitions_per_case']} coalition samples per case. "
        f"Global mean absolute contributions use only {settings['random_cases']} uniformly sampled eligible 2014 cases. "
        f"The {settings['curated_cases']} additional TP/TN/FP/FN examples are diagnostic and excluded from that ranking. "
        "Numeric category codes are reversed before calling the original pipeline; no coded categories are added "
        "to model predictors. The scalar explained output is probability, not a hard decision or a new regression model.\n\n"
        f"InterpretML PartialDependence uses {settings['pdp_background_rows']} complete training rows. Bands show "
        "between-background-row spread, not confidence intervals. PDP/SHAP can combine correlated features into "
        "unusual profiles; contributions are background-dependent model diagnostics, not causal effects or "
        "validated adverse-action reasons. Counts in the training support table contextualize rare event levels. "
        "Permutation importance uses 10,000 stratified 2014 rows, including missing values, with five repeats. "
        "Its error bars are repeat standard deviations, not uncertainty about the population importance.\n\n"
        f"Eligible complete/training-known rows: training {settings['training_explanation_eligible_rows']:,}/"
        f"{settings['training_rows']:,}; validation {settings['validation_explanation_eligible_rows']:,}/"
        f"{settings['validation_rows']:,}. Missing/unseen rows are excluded only from InterpretML explanations, "
        "not the population metrics, permutation sample or segment audit. "
        f"Maximum SHAP reconstruction residual: {settings['maximum_additivity_residual']:.3g}.\n\n"
        "## What 'bias analysis' can establish here\n\n"
        "Structured race, ethnicity, sex/gender, age/birth date, disability, marital status, religion and "
        "national-origin fields are unavailable in the current source schema. We do not infer them from "
        "names, free text, credit history, income or geography. Income, FICO, home ownership, state, purpose, "
        "employment, adverse history, missingness, application type and two intersections are observed "
        "business segments, not substitutes for protected attributes. No legal/compliance or fairness-pass "
        "determination is made.\n\n"
        "The data contains accepted loans only. It cannot measure rejected-applicant outcomes, actual "
        "approval/denial disparities, or the selection and measurement biases in the original lending process. "
        "Labels are resolved-loan outcomes, not fixed-horizon regulatory defaults. Cohort comparisons remain "
        "retrospective; 2014 influenced the original model and threshold selection, and 2015 was previously explored.\n\n"
        "## Segment protocol\n\n"
        f"The same frozen threshold {manifest['frozen_threshold']:.9f} applies to every group. "
        "A risk flag is an audit decision proxy, not an observed rejection. False-positive rate means the "
        "fraction of Fully Paid loans flagged; TPR/recall means the fraction of Charged Off loans flagged. "
        "Income cut points come from training only: " + ", ".join(f"${value:,.2f}" for value in manifest["income_quartile_cutpoints_from_training"]) + ". "
        "Missing groups are retained. Supported groups require at least 500 rows, 50 charged-off and "
        "50 fully-paid loans. Unsupported groups stay in the tables and are excluded only from spread summaries. "
        "Undefined precision/AUC/error rates are missing, not falsely set to zero.\n\n"
        "Wilson 95% intervals are descriptive and assume independent Bernoulli observations; repeated-borrower "
        "and macroeconomic dependence are not modelled. Groups overlap and many slices are screened, so "
        "worst-group spreads are selection-influenced diagnostics without multiple-testing or causal claims. "
        "Case mix and base-rate differences must be considered. No group-specific threshold is fitted and "
        "no four-fifths or other automatic fairness acceptance rule is applied.\n\n"
        "The 0.5 comparison threshold can produce no flags at all. Zero flag/TPR/FPR spreads in that "
        "degenerate policy are not evidence of fairness: default capture is also zero.\n\n")
    for name in ["overall_metrics", "protected_attribute_coverage", "shap_global_importance", "permutation_importance"]:
        report += f"## {name.replace('_', ' ')}\n\n" + markdown_table(tables[name]) + "\n\n"
    supported = tables["segment_spreads"]
    supported = supported[supported.policy == "frozen_validation_f1"]
    report += "## Supported-segment spreads\n\n" + markdown_table(supported) + "\n\n"
    key = tables["segment_metrics"]
    key = key[(key.policy == "frozen_validation_f1") & key.dimension.isin(["income", "fico", "home", "missingness"])]
    report += "## Key segment metrics\n\n" + markdown_table(key) + "\n\n"
    for name in ["feature_importance", "partial_dependence", "local_examples", "segment_disparities"]:
        report += f"![{name.replace('_', ' ')}](../{manifest['figure_directory']}/{name}.png)\n\n"
    report += ("Native InterpretML interactive plots are saved beside the PNG/SVG figures. Their category "
        "values are display codes; readable values and the codebook are in the CSV/manifest. Interactive "
        "HTML uses a Plotly CDN; static images and tables work offline.\n\n"
        f"MLflow experiment `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`. "
        f"[Manifest and complete CSVs](../{manifest['result_directory']}/manifest.json). "
        "The main model-review notebook displays these results without refitting.\n\n"
        "References: [InterpretML ShapKernel](https://interpret.ml/docs/python/api/ShapKernel.html), "
        "[InterpretML PartialDependence](https://interpret.ml/docs/python/api/PartialDependence.html), "
        "[Fairlearn fairness-assessment guidance](https://fairlearn.org/v0.15/user_guide/assessment/perform_fairness_assessment.html).\n")
    (ROOT / "docs/interpret_bias.md").write_text(report)
    path = ROOT / "assets/statistics.md"
    marker = "<!-- interpret-bias-statistics -->"
    original = path.read_text().split(marker)[0].rstrip()
    toc = "26. [InterpretML and segment bias analysis](#26-interpretml-and-segment-bias-analysis)"
    if toc not in original:
        original = original.replace("25. [Logistic coefficient validation](#25-logistic-coefficient-validation)",
                                    "25. [Logistic coefficient validation](#25-logistic-coefficient-validation)\n" + toc)
    section = f"\n\n{marker}\n\n## 26. InterpretML and segment bias analysis\n\n" + report.split("\n", 1)[1]
    for name, table in tables.items():
        section += f"\n\n### {name}\n\n" + markdown_table(table)
    section += "\n\n### Full interpretation and bias manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n"
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Completed stage |"):
            lines[index] = "| Completed stage | InterpretML and descriptive segment bias analysis complete (section 26); incumbent unchanged |"
        elif line.startswith("| Saved result CSVs |"):
            lines[index] = f"| Saved result CSVs | {len(list((ROOT / 'assets/results').rglob('*.csv')))} |"
        elif line.startswith("| Saved figure sets |"):
            lines[index] = f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |"
        elif line.startswith("| Saved image files |"):
            lines[index] = f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |"
    path.write_text(("\n".join(lines) + section).rstrip() + "\n")
    return f"Saved interpretation and bias report: {ROOT / 'docs/interpret_bias.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
