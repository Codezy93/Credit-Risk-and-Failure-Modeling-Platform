"""Audit logistic coefficient signs and document unresolved model-use limitations."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import warnings

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
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.coefficient_review import bootstrap_numeric_coefficients, numeric_coefficients
from util.feature_policy import validate_features
from util.metrics import evaluate_model, paired_auc_bootstrap
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table
from util.modeling import build_models
from util.validation import validate_periods

CONCERNS = ["delinq_2yrs", "pub_rec_bankruptcies"]


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    execution_source = Path(__file__).read_text()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", type=int, default=200)
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("At least two bootstrap resamples are required.")
    warnings.simplefilter("error", ConvergenceWarning)
    results = ROOT / "assets/results"
    data = json.loads((results / "model_data_manifest.json").read_text())
    reference = json.loads((results / "model_experiments_latest.json").read_text())
    features, numeric, categorical = data["features"], data["numeric_features"], data["categorical_features"]
    policy = validate_features(features)
    frames, metadata, input_hashes = {}, {}, {}
    reference_hashes = {a["path"]: a["sha256"] for a in reference["data_decision_snapshot"]["artifacts"]}
    for item in data["artifacts"]:
        if item["split"] not in ("train", "validation"):
            continue
        path = ROOT / item["path"]
        if file_hash(path) != item["sha256"] or reference_hashes.get(item["path"]) != item["sha256"]:
            raise ValueError(f"Changed training/reference input: {path}")
        input_hashes[item["path"]] = item["sha256"]
        destination = metadata if item["kind"] == "metadata" else frames
        destination[item["split"]] = pd.read_parquet(path)
    validate_periods(metadata)
    if set(metadata["train"].issue_year) != {2011, 2012, 2013} or set(metadata["validation"].issue_year) != {2014}:
        raise ValueError("Unexpected temporal populations.")
    for frame in frames.values():
        frame[numeric] = frame[numeric].astype(float)
    train, validation = frames["train"], frames["validation"]
    years = metadata["train"].issue_year.to_numpy()
    original_path = ROOT / reference["model_directory"] / "logistic_regression.joblib"
    original = joblib.load(original_path)
    incumbent = ROOT / "models/selected_model.joblib"
    protected_hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in (incumbent, original_path)}
    loss_path = results / "basel_loss_latest.json"
    loss_scope = json.loads(loss_path.read_text())
    if loss_scope["regulatory_compliance_claim"] or loss_scope["one_year_pd_estimated"]:
        raise ValueError("The loss experiment is incorrectly claiming regulatory PD/compliance.")
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    experiment_name = "lendingclub_coefficient_validation"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    versions = {name: importlib.metadata.version(name) for name in
        ["scikit-learn", "numpy", "pandas", "scipy", "joblib", "cloudpickle", "mlflow"]}
    with mlflow.start_run(experiment_id=experiment_id, run_name="logistic_sign_stability_and_ablation") as batch:
        batch_id = batch.info.run_id
        result_dir = results / "validation_review" / batch_id
        model_dir = ROOT / "models/validation_review" / batch_id
        figure_dir = ROOT / "assets/figures/validation_review" / batch_id
        for directory in (result_dir, model_dir, figure_dir):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {"status": "running", "batch_run_id": batch_id, "experiment_id": experiment_id,
            "experiment_name": experiment_name, "features": features, "feature_policy": policy,
            "selected_model": "", "model_uris": {}, "run_ids": {}, "seed": 42,
            "bootstrap_resamples": args.bootstrap, "bootstrap_strata": "issue year x observed binary outcome",
            "bootstrap_refits_preprocessing": True, "input_sha256": input_hashes,
            "reference_batch_id": reference["batch_run_id"], "protected_artifact_sha256": protected_hashes,
            "test_2015_read": False, "incumbent_replaced": False, "scorecard_claim": False,
            "loss_scope_batch_id": loss_scope["batch_run_id"],
            "regulatory_compliance_claim": False, "one_year_pd_estimated": False,
            "versions": versions, "result_directory": str(result_dir.relative_to(ROOT)),
            "model_directory": str(model_dir.relative_to(ROOT)), "figure_directory": str(figure_dir.relative_to(ROOT))}
        mlflow.log_params({"bootstrap_resamples": args.bootstrap, "seed": 42,
            "bootstrap_strata": "year_and_outcome", "fit_years": "2011-2013", "comparison_year": 2014})
        datasets = {}
        for split, frame in frames.items():
            datasets[split] = mlflow.data.from_pandas(frame, source=str(ROOT / f"data/clean/modeling/{split}.parquet"),
                targets="charged_off", name=f"coefficient_review_{split}")
            mlflow.log_input(datasets[split], context=split)
        point = numeric_coefficients(original, numeric)
        yearly_rows = []
        for year in (2011, 2012, 2013):
            mask = years == year
            fitted = clone(original).fit(train.loc[mask, features], train.loc[mask, "charged_off"])
            table = numeric_coefficients(fitted, numeric)
            table["fit_year"], table["rows"] = year, int(mask.sum())
            yearly_rows.append(table)
            joblib.dump(fitted, model_dir / f"logistic_{year}.joblib")
        yearly = pd.concat(yearly_rows, ignore_index=True)
        outcomes = train.copy()
        outcomes["issue_year"] = years
        con = duckdb.connect()
        con.register("coefficient_population", outcomes)
        bucket_outcomes = con.execute((ROOT / "sql/37_coefficient_outcomes.sql").read_text()).df()
        con.close()
        univariate_rows = []
        for feature in CONCERNS:
            model = Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler()), ("model", LogisticRegression(C=1, max_iter=1000, random_state=42))])
            model.fit(train[[feature]], train.charged_off)
            univariate_rows.append({"feature": feature, "univariate_standardized_coefficient": model.named_steps["model"].coef_[0, 0],
                "adjusted_standardized_coefficient": point.set_index("feature").loc[feature, "coefficient_standardized"],
                "univariate_input_includes_missing_flag_if_needed": True})
        correlations = train[numeric].corr(method="spearman")[CONCERNS].reset_index(names="other_feature")
        bootstrap = bootstrap_numeric_coefficients(original, train, years, features, numeric,
                                                   resamples=args.bootstrap, seed=42)
        summary_rows = []
        for feature, group in bootstrap.groupby("feature"):
            values = group.coefficient_standardized.dropna()
            summary_rows.append({"feature": feature, "point_coefficient": point.set_index("feature").loc[feature, "coefficient_standardized"],
                "estimable_resamples": len(values), "median": values.median(),
                "lower_95": values.quantile(0.025), "upper_95": values.quantile(0.975),
                "negative_fraction": (values < 0).mean(), "positive_fraction": (values > 0).mean()})
        summary = pd.DataFrame(summary_rows)
        for row in summary[summary.feature.isin(CONCERNS)].itertuples():
            mlflow.log_metrics({f"{row.feature}_negative_fraction": float(row.negative_fraction),
                f"{row.feature}_coefficient_lower_95": float(row.lower_95),
                f"{row.feature}_coefficient_upper_95": float(row.upper_95)})
        ablation_rows, native_rows, predictions = [], [], {}
        variants = {"full_reference_refit": [], "drop_delinq": ["delinq_2yrs"],
                    "drop_bankruptcies": ["pub_rec_bankruptcies"], "drop_both": CONCERNS}
        for name, removed in variants.items():
            current_features = [feature for feature in features if feature not in removed]
            current_numeric = [feature for feature in numeric if feature not in removed]
            validate_features(current_features)
            model = build_models(current_numeric, categorical)["logistic_regression"]
            with mlflow.start_run(experiment_id=experiment_id, run_name=name, nested=True) as run:
                manifest["run_ids"][name] = run.info.run_id
                mlflow.log_input(datasets["train"], context="training")
                mlflow.log_input(datasets["validation"], context="validation")
                mlflow.log_dict({"features": current_features, "removed": removed}, "ablation_features.json")
                model.fit(train[current_features], train.charged_off)
                p = model.predict_proba(validation[current_features])[:, 1]
                predictions[name] = p
                if name == "full_reference_refit":
                    np.testing.assert_allclose(p, original.predict_proba(validation[features])[:, 1], atol=1e-10)
                metrics = evaluate_model(validation.charged_off, p)
                ablation_rows.append({"model": name, "removed": ",".join(removed), **metrics})
                mlflow.log_metrics({f"validation_{key}": float(value) for key, value in metrics.items()}, dataset=datasets["validation"])
                joblib.dump(model, model_dir / f"{name}.joblib")
                info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle", pyfunc_predict_fn="predict_proba",
                    input_example=validation[current_features].head(5),
                    signature=infer_signature(validation[current_features].head(5), model.predict_proba(validation[current_features].head(5))),
                    pip_requirements=[f"{key}=={value}" for key, value in versions.items()])
                manifest["model_uris"][name] = info.model_uri
            evaluation_data = mlflow.data.from_pandas(validation[current_features + ["charged_off"]],
                targets="charged_off", name=f"validation_{name}")
            native_rows.append(log_saved_model_evaluation({**manifest, "features": current_features}, name, "validation", evaluation_data))
        paired = paired_auc_bootstrap(validation.charged_off, predictions["full_reference_refit"],
                                     predictions["drop_both"], n_resamples=args.bootstrap, seed=42)
        auc_difference = pd.DataFrame([{"comparison": "drop_both_minus_full_logistic",
            "point_difference": ablation_rows[-1]["roc_auc"] - ablation_rows[0]["roc_auc"],
            "lower_95": paired.delta_b_minus_a.quantile(0.025), "upper_95": paired.delta_b_minus_a.quantile(0.975)}])
        limitations = pd.DataFrame([
            {"item": "target", "status": "limitation", "finding": "Charged-off versus fully-paid among resolved 36-month accepted loans; no fixed one-year default horizon."},
            {"item": "test", "status": "limitation", "finding": "2015 was previously explored and is not read in this review; no fresh holdout exists."},
            {"item": "label timing", "status": "limitation", "finding": "Snapshot training labels may not have been known at later origination dates; not a point-in-time backtest."},
            {"item": "bureau timing", "status": "limitation", "finding": "Added bureau-field collection/update times remain uncertified; expanded results are research only."},
            {"item": "logistic interpretation", "status": "reviewed", "finding": "Year, bootstrap, univariate and removal checks recorded; negative conditional coefficients are not causal protective effects or scorecard approval."},
            {"item": "loss targets", "status": "proxy only", "finding": "EAD is residual snapshot principal; LGD uses snapshot net recoveries without event-time/discounted economic-loss validation."},
            {"item": "capital", "status": "illustrative only", "finding": "Capital uses assumed one-year PD scenarios; no regulatory floors, buffers, downturn-LGD validation or compliance claim."},
        ])
        tables = {"point_coefficients": point, "year_coefficients": yearly,
            "univariate_vs_adjusted": pd.DataFrame(univariate_rows), "training_outcome_buckets": bucket_outcomes,
            "spearman_correlations": correlations, "coefficient_bootstrap": bootstrap, "coefficient_summary": summary,
            "ablation_metrics": pd.DataFrame(ablation_rows), "paired_ablation_auc_bootstrap": paired,
            "ablation_auc_interval": auc_difference, "native_evaluations": pd.DataFrame(native_rows), "limitations": limitations}
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        figure, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        for axis, feature in zip(axes, CONCERNS):
            values = bootstrap[bootstrap.feature == feature].coefficient_standardized.dropna()
            axis.hist(values, bins=25, label="Training bootstrap")
            axis.axvline(0, color="red", linestyle="--")
            axis.axvline(point.set_index("feature").loc[feature, "coefficient_standardized"], color="black", label="Original")
            axis.set(title=feature, xlabel="Adjusted coefficient per training standard deviation", ylabel="Resamples")
            axis.legend(fontsize=8)
        for suffix in ("png", "svg"):
            figure.savefig(figure_dir / f"coefficient_stability.{suffix}", dpi=160)
        plt.close(figure)
        for name, value in protected_hashes.items():
            if file_hash(ROOT / name) != value:
                raise ValueError("A protected incumbent artifact changed.")
        source_paths = [Path(__file__), ROOT / "util/coefficient_review.py", ROOT / "util/modeling.py",
                        ROOT / "sql/37_coefficient_outcomes.sql", ROOT / "util/feature_policy.json", ROOT / "requirements.lock"]
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
            execution_script_sha256=hashlib.sha256(execution_source.encode()).hexdigest(),
            source_sha256={str(p.relative_to(ROOT)): file_hash(p) for p in source_paths},
            results_sha256={p.name: file_hash(p) for p in result_dir.glob("*.csv")},
            model_sha256={p.name: file_hash(p) for p in model_dir.glob("*.joblib")})
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (results / "validation_review_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifacts(str(figure_dir), artifact_path="figures")
        mlflow.log_artifacts(str(model_dir), artifact_path="fitted_models")
        for path in source_paths:
            mlflow.log_artifact(str(path), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "docs/coefficient_validation.md"), artifact_path="reports")
        print(report, flush=True)


def write_report(manifest, tables):
    report = "# Logistic coefficient validation\n\n"
    report += ("This review investigates the two questioned negative logistic coefficients using only "
        "2011–2013 training data. Four feature-removal variants are compared on the already-explored "
        "2014 cohort. No 2015 rows are read, no model is promoted, and no coefficients are forced to "
        "have a preferred sign. Positive class is Charged Off.\n\n"
        "## What the signs mean\n\n"
        "The original logistic pipeline uses scaled numeric inputs and log1p for annual income and "
        "revolving balance. Coefficients are conditional associations within accepted, resolved loans. "
        "A negative coefficient does not establish that delinquency or bankruptcy protects against loss. "
        "Year-specific estimates use different training scales; signs are comparable, while raw magnitudes "
        "also depend on those scales. The CSV includes coefficients per transformed input unit.\n\n"
        "Univariate fits, observed outcome buckets and FICO-stratified slices give context. Correlation "
        "and conditional/marginal sign changes are diagnostics, not proof of a causal explanation.\n\n")
    report += f"## Bootstrap protocol\n\n{manifest['bootstrap_resamples']} resamples, seed 42, stratified by training issue year × outcome. "
    report += ("Every resample refits imputation, scaling, encoding and regularized logistic regression. "
        "Intervals use empirical 2.5th/97.5th percentiles; sign fractions and estimable counts are saved. "
        "They condition on observed year/class counts and omit repeated-borrower dependence, macroeconomic "
        "uncertainty, and model-selection uncertainty. They are not unpenalized inferential p-values.\n\n")
    for name in ["univariate_vs_adjusted", "coefficient_summary", "year_coefficients", "ablation_metrics", "ablation_auc_interval", "limitations"]:
        report += f"## {name.replace('_', ' ')}\n\n" + markdown_table(tables[name]) + "\n\n"
    report += ("## Use decision\n\n"
        "Keep the incumbent histogram-boosting model unchanged. The plain logistic baseline is not a "
        "WoE scorecard and this review does not certify monotonic economic interpretation. If a model "
        "requires monotonic delinquency/bankruptcy effects, that requirement must be enforced and "
        "validated in a separate constrained model; do not relabel conditional negative effects as "
        "beneficial borrower behaviour. Feature-removal comparisons and their paired interval show "
        "the discrimination trade-off, without turning 2014 into a fresh holdout.\n\n"
        f"![Coefficient stability](../{manifest['figure_directory']}/coefficient_stability.png)\n\n"
        "[Scikit-learn coefficient-interpretation guidance](https://scikit-learn.org/stable/auto_examples/inspection/plot_linear_model_coefficient_interpretation.html). "
        f"MLflow experiment `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`. "
        f"[Full CSVs and manifest](../{manifest['result_directory']}/manifest.json).\n")
    (ROOT / "docs/coefficient_validation.md").write_text(report)
    marker = "<!-- coefficient-validation-statistics -->"
    path = ROOT / "assets/statistics.md"
    original = path.read_text().split(marker)[0].rstrip()
    toc = "25. [Logistic coefficient validation](#25-logistic-coefficient-validation)"
    if toc not in original:
        original = original.replace("24. [External teaching extract audit](#24-external-teaching-extract-audit)",
                                    "24. [External teaching extract audit](#24-external-teaching-extract-audit)\n" + toc)
    section = f"\n\n{marker}\n\n## 25. Logistic coefficient validation\n\n" + report.split("\n", 1)[1]
    for name, table in tables.items():
        section += f"\n\n### {name}\n\n" + markdown_table(table)
    section += "\n\n### Full review manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n"
    path.write_text((original + section).rstrip() + "\n")
    return f"Saved coefficient validation: {ROOT / 'docs/coefficient_validation.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
