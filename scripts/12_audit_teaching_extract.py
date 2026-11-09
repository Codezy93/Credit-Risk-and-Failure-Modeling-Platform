"""Audit an external teaching extract; never add its postcode to project predictors."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")
import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.metrics import evaluate_model
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    source = ROOT / "data/raw/teaching_extract/lending_club_loan_two.csv"
    provenance = json.loads(source.with_name("source.json").read_text())
    if file_hash(source) != provenance["sha256"]:
        raise ValueError("Teaching file does not match its recorded download hash.")
    frame = pd.read_csv(source)
    shape = frame.shape
    columns = frame.columns.tolist()
    if set(frame.loan_status.unique()) != {"Fully Paid", "Charged Off"}:
        raise ValueError("This audit expects the two-status teaching extract.")
    frame["charged_off"] = frame.loan_status.map({"Fully Paid": 0, "Charged Off": 1})
    frame["audit_postcode"] = frame.address.astype("string").str.extract(r"(\d{5})\s*$", expand=False)
    if frame.audit_postcode.isna().any():
        raise ValueError("Some teaching addresses lack a final five-digit postcode.")
    counts = pd.crosstab(frame.audit_postcode, frame.loan_status).reset_index()
    counts["rows"] = counts["Fully Paid"] + counts["Charged Off"]
    counts["charged_off_rate"] = counts["Charged Off"] / counts.rows
    numeric = ["loan_amnt", "int_rate", "installment", "annual_inc", "dti", "open_acc", "pub_rec",
        "revol_bal", "revol_util", "total_acc", "mort_acc", "pub_rec_bankruptcies",
        "emp_length_years", "credit_history_years"]
    categorical = ["term", "grade", "sub_grade", "home_ownership", "verification_status", "purpose",
                   "initial_list_status", "application_type"]
    frame["emp_length_years"] = pd.to_numeric(frame.emp_length.str.extract(r"(\d+)", expand=False), errors="coerce")
    frame.loc[frame.emp_length.str.contains("<", na=False), "emp_length_years"] = 0
    issued = pd.to_datetime(frame.issue_d, format="%b-%Y")
    earliest = pd.to_datetime(frame.earliest_cr_line, format="%b-%Y")
    frame["credit_history_years"] = (issued - earliest).dt.days / 365.25
    frame[numeric] = frame[numeric].astype(float)
    train_index, test_index = train_test_split(np.arange(len(frame)), test_size=0.2,
        random_state=42, stratify=frame.charged_off)
    train, test = frame.iloc[train_index], frame.iloc[test_index]
    postcode_rates = train.groupby("audit_postcode").charged_off.mean()
    postcode_score = test.audit_postcode.map(postcode_rates).fillna(train.charged_off.mean()).astype(float)
    incumbent_path = ROOT / "models/selected_model.joblib"
    incumbent_hash = file_hash(incumbent_path)
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    experiment_name = "lendingclub_teaching_extract_audit"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    parameters = {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.05,
        "min_child_weight": 10, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 10,
        "tree_method": "hist", "n_jobs": 4, "random_state": 42, "eval_metric": "auc"}
    with mlflow.start_run(experiment_id=experiment_id, run_name="postcode_signal_ablation") as batch:
        result_dir = ROOT / "assets/results/teaching_extract_audit" / batch.info.run_id
        model_dir = ROOT / "models/teaching_extract_audit" / batch.info.run_id
        result_dir.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tags({"scope": "external_teaching_data_diagnostic", "production_eligible": "false"})
        mlflow.log_dict(provenance, "external_source.json")
        manifest = {"status": "running", "batch_run_id": batch.info.run_id, "experiment_id": experiment_id,
            "experiment_name": experiment_name, "source": provenance, "rows": shape[0], "columns": shape[1],
            "source_columns": columns, "charged_off_rows": int(frame.charged_off.sum()),
            "charged_off_rate": frame.charged_off.mean(), "postcode_values": frame.audit_postcode.nunique(),
            "train_rows": len(train), "test_rows": len(test), "split": "stratified random 80/20, seed 42",
            "notebook_exact_reproduction": False, "reviewers_exact_file_identity_verified": False,
            "construction_mechanism_verified": False, "production_feature_policy_changed": False,
            "xgboost_parameters": parameters, "incumbent_sha256": incumbent_hash,
            "result_directory": str(result_dir.relative_to(ROOT)), "model_directory": str(model_dir.relative_to(ROOT)),
            "model_uris": {}, "run_ids": {}, "selected_model": ""}
        rows = [{"model": "postcode_rate_only", **evaluate_model(test.charged_off, postcode_score)}]
        native_rows = []
        for include_postcode in (False, True):
            name = "xgboost_with_postcode" if include_postcode else "xgboost_without_postcode"
            cats = categorical + (["audit_postcode"] if include_postcode else [])
            features = numeric + cats
            prepare = ColumnTransformer([
                ("numeric", SimpleImputer(strategy="median"), numeric),
                ("categorical", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Missing")),
                    ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cats)])
            model = Pipeline([("prepare", prepare), ("model", XGBClassifier(**parameters))])
            datasets = {}
            for split, subset in (("train", train), ("test", test)):
                path = model_dir / f"{name}_{split}.parquet"
                subset[features + ["charged_off"]].to_parquet(path, index=False)
                datasets[split] = mlflow.data.from_pandas(subset[features + ["charged_off"]],
                    source=provenance["url"], targets="charged_off", name=f"teaching_{name}_{split}")
                mlflow.log_input(datasets[split], context=split)
                mlflow.log_artifact(str(path), artifact_path="datasets")
            print(f"Fitting controlled audit: {name}", flush=True)
            with mlflow.start_run(experiment_id=experiment_id, run_name=name, nested=True) as run:
                manifest["run_ids"][name] = run.info.run_id
                mlflow.log_params(parameters)
                mlflow.log_param("postcode_included", include_postcode)
                for split, dataset in datasets.items():
                    mlflow.log_input(dataset, context=split)
                model.fit(train[features], train.charged_off)
                scores = model.predict_proba(test[features])[:, 1]
                values = evaluate_model(test.charged_off, scores)
                rows.append({"model": name, **values})
                mlflow.log_metrics({f"test_{key}": float(value) for key, value in values.items()}, dataset=datasets["test"])
                joblib.dump(model, model_dir / f"{name}.joblib")
                info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle",
                    pyfunc_predict_fn="predict_proba", input_example=test[features].head(5),
                    signature=infer_signature(test[features].head(5), model.predict_proba(test[features].head(5))),
                    pip_requirements=[line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()
                                      if line.strip() and not line.startswith("#")])
                manifest["model_uris"][name] = info.model_uri
            native_rows.append(log_saved_model_evaluation({**manifest, "features": features}, name, "test", datasets["test"]))
        comparison = pd.DataFrame(rows)
        source_audit = pd.read_csv(ROOT / "assets/results/eda_source_column_audit.csv")
        schema = pd.DataFrame({"teaching_column": columns,
                              "present_in_project_source": [c in set(source_audit.source_column) for c in columns]})
        tables = {"postcode_status_counts": counts, "score_comparison": comparison,
                  "schema_comparison": schema, "native_evaluations": pd.DataFrame(native_rows)}
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        if file_hash(incumbent_path) != incumbent_hash:
            raise ValueError("The project incumbent changed during the audit.")
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
            pure_paid_postcodes=counts.loc[counts.charged_off_rate == 0, "audit_postcode"].tolist(),
            pure_charged_off_postcodes=counts.loc[counts.charged_off_rate == 1, "audit_postcode"].tolist(),
            postcode_only_heldout_auc=float(comparison.iloc[0].roc_auc),
            controlled_postcode_auc_gain=float(comparison.iloc[2].roc_auc - comparison.iloc[1].roc_auc),
            execution_script_sha256=file_hash(Path(__file__)), incumbent_unchanged=True,
            results_sha256={p.name: file_hash(p) for p in result_dir.glob("*.csv")})
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (ROOT / "assets/results/teaching_extract_audit_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifact(str(Path(__file__)), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "docs/teaching_extract_audit.md"), artifact_path="reports")
        print(report, flush=True)


def write_report(manifest, tables):
    report = "# External teaching extract: postcode audit\n\n"
    report += (f"Measured on a public copy of `lending_club_loan_two.csv`: {manifest['rows']:,} rows, "
        f"{manifest['columns']} columns, charged-off share {manifest['charged_off_rate']:.4%}, "
        f"{manifest['postcode_values']} postcodes. [Pinned source]({manifest['source']['url']}); "
        f"SHA-256 `{manifest['source']['sha256']}`. The reviewer supplied no file hash, so exact identity "
        "with their upload is unverified. No claim is made to have inspected their 120 notebook cells.\n\n"
        "## What was tested\n\n"
        "Postcodes are the final five digits of address, preserving leading zeros. The crosstab uses all "
        "rows as a descriptive audit. Postcode-only probabilities are learned on the training partition, "
        "then scored on the held-out partition.\n\n"
        "The controlled XGBoost ablation uses an identical stratified random 80/20 split (seed 42), "
        "fixed 300-tree settings, and train-only imputation/one-hot encoding. It uses 14 numeric and "
        "8 categorical origination/underwriting features, including grade and interest rate, with postcode "
        "as the sole additional column in the second model. Direct address, employment title, loan title "
        "and outcome fields are excluded from predictors. Employment length and credit-history age are "
        "derived deterministically. There is no early stopping or tuning on the holdout.\n\n"
        "This is a diagnostic of this teaching extract, not a reproduction of the unseen notebook's "
        "XGBoost settings or an estimate of how much of its exact 0.905 result is caused by postcode. "
        "A strong target association does not reveal how the added addresses were constructed. "
        "It does make this postcode-based result unsuitable as a real-world benchmark for the project.\n\n")
    for name, table in tables.items():
        report += f"## {name.replace('_', ' ')}\n\n" + markdown_table(table) + "\n\n"
    report += ("## Corrections to the comparison\n\n"
        "Our all-status charged-off share is 11.8796%, but among ordinary Fully Paid/Charged Off loans "
        "it is 19.9626%, comparable in population definition to this teaching file's resolved-only share. "
        "The project model cohorts still differ: 2014 validation is 13.7264% charged off and exploratory "
        "2015 is 14.8863%. Comparing a resolved-only share against all statuses is misleading.\n\n"
        "ROC-AUC computed on hard 0/1 predictions is mathematically defined and equals balanced accuracy "
        "for a binary decision rule. It is not the probability-score ranking AUC used by our experiments. "
        "Our 0.6913 research result is also selection-influenced: 2014 was reused for early stopping "
        "and candidate selection. Only the original selected model has the separately reported 2015 "
        "exploratory AUC of 0.6544. No fresh-holdout claim is appropriate.\n\n"
        "The current project data, feature policy, model artifacts, and model selection remain unchanged. "
        "The downloaded teaching file and audit model/data artifacts are ignored by Git. "
        f"MLflow experiment: `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`.\n\n"
        "[Scikit-learn score-based ROC-AUC documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html).\n")
    (ROOT / "docs/teaching_extract_audit.md").write_text(report)
    path = ROOT / "assets/statistics.md"
    marker = "<!-- teaching-extract-audit-statistics -->"
    original = path.read_text().split(marker)[0].rstrip()
    original = original.replace("23. [ANN challengers](#23-ann-challengers)",
        "23. [ANN challengers](#23-ann-challengers)\n24. [External teaching extract audit](#24-external-teaching-extract-audit)")
    path.write_text(original + f"\n\n{marker}\n\n## 24. External teaching extract audit\n\n" + report.split("\n", 1)[1] +
        "\n\n### Full audit manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n")
    return f"Saved controlled teaching-data audit: {ROOT / 'docs/teaching_extract_audit.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
