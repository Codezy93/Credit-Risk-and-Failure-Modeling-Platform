"""Fit separate EAD/LGD snapshot proxies and run illustrative retail IRB scenarios."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import itertools
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
import mlflow.sklearn
from mlflow.models import infer_signature
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.basel import expected_loss, other_retail_capital, score_loss_bundle
from util.feature_policy import validate_features
from util.metrics import evaluate_model
from util.mlflow_evaluation import markdown_table
from util.modeling import build_models
from util.validation import validate_periods


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    source_text = Path(__file__).read_text()
    results = ROOT / "assets/results"
    data = json.loads((results / "model_data_manifest.json").read_text())
    pd_manifest = json.loads((results / "model_experiments_latest.json").read_text())
    features = data["features"]
    policy = validate_features(features)
    frames, metadata, input_hashes = {}, {}, {}
    for artifact in data["artifacts"]:
        if artifact["split"] not in ("train", "validation"):
            continue
        path = ROOT / artifact["path"]
        if file_hash(path) != artifact["sha256"]:
            raise ValueError(f"Prepared input changed: {path}")
        input_hashes[artifact["path"]] = artifact["sha256"]
        destination = metadata if artifact["kind"] == "metadata" else frames
        destination[artifact["split"]] = pd.read_parquet(path)
    historical = {item["path"]: item["sha256"] for item in pd_manifest["data_decision_snapshot"]["artifacts"]}
    if any(historical.get(path) != digest for path, digest in input_hashes.items()) or features != pd_manifest["features"]:
        raise ValueError("PD model inputs differ from the prepared loss inputs.")
    validate_periods(metadata)
    contracts = []
    for split in ("train", "validation"):
        frame = frames[split].copy()
        frame[data["numeric_features"]] = frame[data["numeric_features"]].astype(float)
        frame["loan_id"] = metadata[split].loan_id.to_numpy()
        frame["split"] = split
        contracts.append(frame)
    contract = pd.concat(contracts, ignore_index=True)
    raw = ROOT / "data/raw/accepted_2007_to_2018Q4.csv"
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=4")
    con.register("model_contract", contract)
    con.execute("SET VARIABLE raw_path=?", [str(raw)])
    print("Joining separate loss-outcome fields to 2011-2014 loans", flush=True)
    con.execute((ROOT / "sql/34_loss_population.sql").read_text())
    audit = con.execute((ROOT / "sql/35_loss_audit.sql").read_text()).df()
    population = con.execute("SELECT * FROM loss_population ORDER BY split, loan_id").df()
    con.close()
    if population.loan_id.duplicated().any() or len(population) != len(contract) or audit.missing_source.sum():
        raise ValueError("The loss-source join is not one-to-one and complete.")
    if audit.invalid_funded.sum():
        raise ValueError("Missing or invalid funded amounts; inspect the source before scoring.")
    defaults = population[(population.charged_off == 1) & population.bounded_target_valid].copy()
    default_train = defaults[defaults.split == "train"]
    default_validation = defaults[defaults.split == "validation"]
    if min(len(default_train), len(default_validation)) == 0:
        raise ValueError("Both periods need eligible defaulted loans.")
    pd_path = ROOT / "models/selected_model.joblib"
    pd_hash = file_hash(pd_path)
    if pd_hash != pd_manifest["selected_joblib_sha256"]:
        raise ValueError("The incumbent PD artifact changed.")
    pd_model = joblib.load(pd_path)
    before_scores = pd_model.predict_proba(frames["validation"][features])[:, 1]
    pd_metrics = evaluate_model(frames["validation"].charged_off, before_scores)

    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    experiment_name = "lendingclub_basel_loss_proxies"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    versions = {name: importlib.metadata.version(name) for name in
                ["scikit-learn", "numpy", "pandas", "scipy", "joblib", "mlflow", "cloudpickle"]}
    preprocessor = build_models(data["numeric_features"], data["categorical_features"])["hist_gradient_boosting"].named_steps["prepare"]
    targets = {"ead": "ead_ratio_proxy", "lgd": "lgd_snapshot_proxy"}
    with mlflow.start_run(experiment_id=experiment_id, run_name="ead_lgd_el_capital_proxies") as batch:
        batch_id = batch.info.run_id
        result_dir = results / "basel_loss" / batch_id
        model_dir = ROOT / "models/basel_loss" / batch_id
        figure_dir = ROOT / "assets/figures/basel_loss" / batch_id
        for directory in (result_dir, model_dir, figure_dir):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {"status": "running", "batch_run_id": batch_id, "experiment_id": experiment_id,
            "experiment_name": experiment_name, "features": features, "feature_policy": policy,
            "seed": 42, "target_scope": "bounded_snapshot_loss_proxies_on_charged_off_loans",
            "train_years": [2011, 2012, 2013], "validation_years": [2014],
            "test_2015_read": False, "regulatory_compliance_claim": False,
            "one_year_pd_estimated": False, "capital_pd_source": "explicit scenario assumptions",
            "prediction_bounds": "clip regressor predictions to [0,1]; raw and bounded metrics both saved",
            "loss_field_scope": "targets, exposure scaling, audit and retrospective dollar evaluation only",
            "selection_rule": "lowest 2014 bounded MAE per component; exploratory selection cohort",
            "ead_formula": "funded_amnt - total_rec_prncp; snapshot proxy, not observed default-event EAD",
            "lgd_formula": "1 - (recoveries - collection_recovery_fee) / snapshot_ead_proxy",
            "el_formula": "unchanged resolved-loan PD score * predicted LGD * predicted EAD",
            "el_assumption": "product of conditional means ignores residual EAD/LGD dependence",
            "pd_source_run_id": pd_manifest["selected_run_id"], "pd_joblib_sha256": pd_hash,
            "input_sha256": input_hashes, "raw_source_sha256": file_hash(raw), "versions": versions,
            "result_directory": str(result_dir.relative_to(ROOT)), "model_directory": str(model_dir.relative_to(ROOT)),
            "figure_directory": str(figure_dir.relative_to(ROOT)), "model_uris": {}, "run_ids": {}}
        mlflow.set_tags({"scope": "illustrative_loss_and_capital", "regulatory_compliance": "false"})
        mlflow.log_dict(manifest, "experiment_scope.json")
        mlflow.log_params({"fit_years": "2011-2013", "selection_year": 2014, "seed": 42,
                           "pd_model_retrained": False, "capital_pd_estimated": False})
        models, metric_rows, native_rows = {}, [], []
        for component, target in targets.items():
            train = default_train[features + [target]].copy()
            validation = default_validation[features + [target]].copy()
            datasets = {}
            for split, frame in (("train", train), ("validation", validation)):
                path = model_dir / f"{component}_{split}.parquet"
                frame.to_parquet(path, index=False)
                datasets[split] = mlflow.data.from_pandas(frame, source=str(path), targets=target, name=f"{component}_{split}")
                mlflow.log_input(datasets[split], context=f"{component}_{split}")
                mlflow.log_artifact(str(path), artifact_path="datasets")
            for name, estimator in [("mean", DummyRegressor(strategy="mean")),
                ("boosting", HistGradientBoostingRegressor(max_iter=150, learning_rate=0.05,
                    max_leaf_nodes=15, min_samples_leaf=50, l2_regularization=1,
                    early_stopping=False, categorical_features=list(range(len(data["numeric_features"]), len(features))), random_state=42))]:
                label = f"{component}_{name}"
                print(f"Fitting {label}: {len(train):,} defaulted training loans", flush=True)
                model = Pipeline([("prepare", clone(preprocessor)), ("model", estimator)])
                with mlflow.start_run(experiment_id=experiment_id, run_name=label, nested=True) as run:
                    manifest["run_ids"][label] = run.info.run_id
                    model.fit(train[features], train[target])
                    models[label] = model
                    mlflow.log_input(datasets["train"], context="training")
                    mlflow.log_input(datasets["validation"], context="validation")
                    mlflow.log_dict(json.loads(json.dumps(model.get_params(), default=str)), "parameters.json")
                    for split, frame in (("train", train), ("validation", validation)):
                        raw_predictions = model.predict(frame[features])
                        bounded = np.clip(raw_predictions, 0, 1)
                        values = {"rows": len(frame), "raw_mae": mean_absolute_error(frame[target], raw_predictions),
                            "bounded_mae": mean_absolute_error(frame[target], bounded),
                            "bounded_rmse": root_mean_squared_error(frame[target], bounded),
                            "bounded_r2": r2_score(frame[target], bounded), "observed_mean": frame[target].mean(),
                            "predicted_mean": bounded.mean(), "predictions_clipped": int((raw_predictions != bounded).sum())}
                        metric_rows.append({"model": label, "component": component, "split": split, **values})
                        mlflow.log_metrics({f"{split}_{key}": float(value) for key, value in values.items()}, dataset=datasets[split])
                    path = model_dir / f"{label}.joblib"
                    joblib.dump(model, path)
                    np.testing.assert_allclose(joblib.load(path).predict(validation[features].head(100)),
                                               model.predict(validation[features].head(100)), atol=1e-12)
                    info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle",
                        signature=infer_signature(train[features].head(5), model.predict(train[features].head(5))),
                        input_example=train[features].head(5), pip_requirements=[f"{key}=={value}" for key, value in versions.items()])
                    manifest["model_uris"][label] = info.model_uri
                with mlflow.start_run(experiment_id=experiment_id, run_name=f"evaluate_{label}", nested=True) as evaluation:
                    mlflow.set_tags({"run_kind": "evaluation", "source_training_run_id": run.info.run_id})
                    result = mlflow.models.evaluate(model=info.model_uri, model_id=info.model_uri.split("/")[-1],
                        data=datasets["validation"], model_type="regressor", evaluators="default",
                        evaluator_config={"log_model_explainability": False, "metric_prefix": "native_validation_"})
                    native_rows.append({"model": label, "evaluation_run_id": evaluation.info.run_id, **result.metrics})
        metrics = pd.DataFrame(metric_rows)
        chosen = metrics[metrics.split == "validation"].sort_values(["bounded_mae", "model"]).groupby("component").first()
        selected = {component: chosen.loc[component, "model"] for component in targets}
        portfolio = population[(population.split == "validation") & (population.charged_off.eq(0) | population.bounded_target_valid)].copy()
        portfolio["pd_score"] = pd_model.predict_proba(portfolio[features])[:, 1]
        el_rows, portfolio_scores = [], {}
        methods = {"mean_baseline": {c: f"{c}_mean" for c in targets},
                   "boosting": {c: f"{c}_boosting" for c in targets}, "selected_components": selected}
        for method, choices in methods.items():
            ead = portfolio.funded_amnt.to_numpy() * np.clip(models[choices["ead"]].predict(portfolio[features]), 0, 1)
            lgd = np.clip(models[choices["lgd"]].predict(portfolio[features]), 0, 1)
            predicted = expected_loss(portfolio.pd_score, lgd, ead)
            portfolio_scores[method] = (ead, lgd, predicted)
            el_rows.append({"method": method, "ead_model": choices["ead"], "lgd_model": choices["lgd"],
                "rows": len(portfolio), "observed_loss_proxy_total": portfolio.observed_loss_proxy.sum(),
                "expected_loss_proxy_total": predicted.sum(),
                "portfolio_relative_error": predicted.sum() / portfolio.observed_loss_proxy.sum() - 1,
                "loan_dollar_mae": mean_absolute_error(portfolio.observed_loss_proxy, predicted),
                "loan_dollar_rmse": root_mean_squared_error(portfolio.observed_loss_proxy, predicted)})
        ead, lgd, predicted = portfolio_scores["selected_components"]
        portfolio["predicted_ead"], portfolio["predicted_lgd"], portfolio["expected_loss_proxy"] = ead, lgd, predicted
        portfolio["loss_decile"] = pd.qcut(portfolio.expected_loss_proxy.rank(method="first"), 10, labels=False) + 1
        deciles = portfolio.groupby("loss_decile").agg(rows=("loan_id", "size"),
            expected_loss=("expected_loss_proxy", "sum"), observed_loss=("observed_loss_proxy", "sum"),
            mean_pd=("pd_score", "mean")).reset_index()
        scenarios = []
        for assumed_pd, lgd_addition in itertools.product([0.01, 0.03, 0.05], [0, 0.10]):
            scenario = other_retail_capital(assumed_pd, np.minimum(lgd + lgd_addition, 1), ead)
            scenarios.append({"pd_one_year_assumed": assumed_pd, "lgd_addition": lgd_addition,
                "rows": len(scenario), "predicted_ead_total": ead.sum(), "capital": scenario.capital.sum(),
                "rwa": scenario.rwa.sum(), "scenario_one_year_el": scenario.expected_loss_one_year_scenario.sum()})
        sensitivity = other_retail_capital(*np.array(list(itertools.product([0.005, 0.01, 0.03, 0.05], [0.25, 0.45, 0.65, 0.85], [10000]))).T)
        after_scores = pd_model.predict_proba(frames["validation"][features])[:, 1]
        if not np.array_equal(before_scores, after_scores) or file_hash(pd_path) != pd_hash:
            raise ValueError("The PD model changed during the loss experiment.")
        pd_check = pd.DataFrame([{"stage": "before_loss_layers", **pd_metrics},
                                 {"stage": "after_loss_layers", **evaluate_model(frames["validation"].charged_off, after_scores)}])
        tables = {"loss_audit": audit, "component_metrics": metrics, "portfolio_loss_metrics": pd.DataFrame(el_rows),
            "loss_deciles": deciles, "capital_sensitivity": sensitivity, "portfolio_capital_scenarios": pd.DataFrame(scenarios),
            "pd_unchanged_check": pd_check, "native_regression_evaluations": pd.DataFrame(native_rows)}
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        portfolio[["loan_id", "pd_score", "funded_amnt", "predicted_ead", "predicted_lgd", "expected_loss_proxy", "observed_loss_proxy"]].to_parquet(model_dir / "validation_loss_scores.parquet", index=False)
        bundle = {"features": features, "ead_ratio_model": models[selected["ead"]], "lgd_model": models[selected["lgd"]],
                  "pd_model": pd_model, "bound_loss_predictions": [0, 1], "scope": manifest["target_scope"]}
        joblib.dump(bundle, model_dir / "loss_model_bundle.joblib")
        reloaded_scores = score_loss_bundle(joblib.load(model_dir / "loss_model_bundle.joblib"),
            portfolio[features], portfolio.funded_amnt)
        np.testing.assert_allclose(reloaded_scores.expected_loss_proxy, predicted, atol=1e-10)
        figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
        axes[0].hist(default_train.ead_ratio_proxy, bins=30)
        axes[0].set(title="Training defaults: EAD / funded", xlabel="Snapshot EAD ratio", ylabel="Loans")
        axes[1].hist(default_train.lgd_snapshot_proxy, bins=30)
        axes[1].set(title="Training defaults: LGD proxy", xlabel="Bounded LGD", ylabel="Loans")
        save_figure(figure, figure_dir, "loss_targets")
        figure, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        axes[0].plot(deciles.loss_decile, deciles.expected_loss, "o-", label="Expected proxy")
        axes[0].plot(deciles.loss_decile, deciles.observed_loss, "o-", label="Observed proxy")
        axes[0].set(xlabel="Predicted loss decile", ylabel="USD", title="2014 loss totals by decile")
        axes[0].legend()
        for value, group in sensitivity.groupby("lgd"):
            axes[1].plot(group.pd_one_year_assumed, group.capital, "o-", label=f"LGD {value:.0%}")
        axes[1].set(xlabel="Assumed one-year PD", ylabel="Capital, USD per $10,000 EAD", title="Illustrative other-retail IRB sensitivity")
        axes[1].legend()
        save_figure(figure, figure_dir, "loss_and_capital")
        source_files = [Path(__file__), ROOT / "util/basel.py", ROOT / "util/modeling.py", ROOT / "util/feature_policy.json",
                        ROOT / "sql/34_loss_population.sql", ROOT / "sql/35_loss_audit.sql", ROOT / "requirements.lock"]
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(), selected_components=selected,
            execution_script_sha256=hashlib.sha256(source_text.encode()).hexdigest(), pd_predictions_identical=True,
            source_sha256={str(path.relative_to(ROOT)): file_hash(path) for path in source_files},
            results_sha256={path.name: file_hash(path) for path in result_dir.glob("*.csv")},
            model_sha256={path.name: file_hash(path) for path in model_dir.glob("*.joblib")},
            dataset_sha256={path.name: file_hash(path) for path in model_dir.glob("*.parquet")})
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (results / "basel_loss_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifacts(str(figure_dir), artifact_path="figures")
        mlflow.log_artifact(str(model_dir / "loss_model_bundle.joblib"), artifact_path="model_bundle")
        mlflow.log_artifact(str(ROOT / "docs/basel_loss_experiment.md"), artifact_path="reports")
        for path in source_files:
            mlflow.log_artifact(str(path), artifact_path="source")
        print(report, flush=True)


def save_figure(figure, directory, name):
    figure.savefig(directory / f"{name}.png", dpi=160)
    path = directory / f"{name}.svg"
    figure.savefig(path)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(figure)


def write_report(manifest, tables):
    report = "# Basel-style loss experiment\n\n"
    report += ("This experiment adds separate EAD and LGD models, resolved-outcome expected-loss proxies, "
        "and illustrative CRE31.16 other-retail capital calculations. It is not a regulatory model. "
        "The incumbent PD model is unchanged. Fit: 2011–2013; selection/evaluation: already-explored 2014. No 2015 rows are used.\n\n"
        "## Targets and exclusions\n\n"
        "On charged-off loans only, snapshot EAD = funded amount − principal received; LGD = "
        "1 − net recoveries / snapshot EAD. Positive funded amounts, nonnegative source inputs, positive EAD, "
        "and LGD in [0,1] define this bounded experiment. Out-of-range targets are quarantined and counted, "
        "not silently clipped. LGD above one can represent costs rather than a parsing error. "
        "Fully-paid rows have zero observed loss and do not train EAD/LGD.\n\n"
        "Snapshot principal and recoveries are not event-time EAD or discounted economic loss. "
        "Recovery dates, indirect costs and unresolved recovery tails are unavailable. "
        "The fitted sample therefore has retrospective selection and recovery-maturity limitations.\n\n"
        "## Component models\n\n"
        "Mean baselines and fixed gradient-boosting regressors use the same 13 origination predictors. "
        "All preprocessing is fitted on eligible training defaults only. Outcome fields form targets and "
        "dollar diagnostics; they never enter PD or loss predictor matrices. Predictions are explicitly "
        "bounded to [0,1] for composition; raw regression errors and clipping counts are also saved. "
        "Native MLflow regression evaluations use raw predictions. Selection uses validation bounded MAE.\n\n"
        "## Expected loss and capital interpretation\n\n"
        "Resolved-outcome EL proxy = unchanged PD score × predicted LGD × predicted EAD. "
        "EAD prediction = funded amount × predicted EAD ratio. Multiplying conditional EAD and LGD means "
        "ignores residual dependence; validation dollar errors expose this approximation. The observed "
        "loss comparator uses the same eligible portfolio and snapshot convention.\n\n"
        "Capital uses explicitly assumed one-year PD scenarios, never the resolved-loan PD score. "
        "CRE31.16 correlation R = 0.03w + 0.16(1−w), w = (1−exp(−35PD))/(1−exp(−35)); "
        "K = LGD × [Phi((Phi^-1(PD)+sqrt(R)Phi^-1(0.999))/sqrt(1−R))−PD]; "
        "capital = K × EAD and RWA = 12.5 × capital. Scenario one-year EL uses the assumed PD. "
        "The scenario treats the loans as a hypothetical performing portfolio at origination; "
        "it does not apply the performing-exposure formula to their realised default state. "
        "Other-retail eligibility is assumed for illustration. No regulatory parameter floors, output floor, "
        "buffers, provisions adjustment, downturn-LGD validation or approval requirements are implemented. "
        "These are sensitivities, not a measured regulatory capital requirement.\n\n")
    for name, table in tables.items():
        report += f"## {name.replace('_', ' ')}\n\n" + markdown_table(table) + "\n\n"
    report += (f"![Loss targets](../{manifest['figure_directory']}/loss_targets.png)\n\n"
        f"![Loss and capital](../{manifest['figure_directory']}/loss_and_capital.png)\n\n"
        "Sources: [BIS CRE31.16 risk-weight functions](https://www.bis.org/committees/bcbs/basel-framework/standard/cre/31/inforce/2023-01-01/published/2020-03-27), "
        "[BIS CRE36 economic-loss requirements](https://www.bis.org/committees/bcbs/basel-framework/standard/cre/36/inforce/2023-01-01/published/2022-12-08).\n\n"
        f"MLflow experiment: `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`. "
        f"[Full manifest](../{manifest['result_directory']}/manifest.json). "
        "The local model directory contains four component pipelines and the selected loss-model bundle.\n")
    (ROOT / "docs/basel_loss_experiment.md").write_text(report)
    marker = "<!-- basel-loss-statistics -->"
    path = ROOT / "assets/statistics.md"
    contents = path.read_text()
    later_marker = "<!-- ann-experiment-statistics -->"
    later = "\n\n" + later_marker + contents.split(later_marker, 1)[1] if later_marker in contents else ""
    original = contents.split(marker)[0].rstrip()
    toc = "22. [Basel-style loss experiment](#22-basel-style-loss-experiment)"
    if toc not in original:
        original = original.replace("21. [Validation hardening](#21-validation-hardening)",
                                    "21. [Validation hardening](#21-validation-hardening)\n" + toc)
    section = f"\n\n{marker}\n\n## 22. Basel-style loss experiment\n\n" + report.split("\n", 1)[1]
    section += "\n\n### Full loss experiment manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n"
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Completed stage |"):
            lines[index] = "| Completed stage | Basel-style loss experiment complete (section 22); PD unchanged |"
        elif line.startswith("| Saved result CSVs |"):
            lines[index] = f"| Saved result CSVs | {len(list((ROOT / 'assets/results').rglob('*.csv')))} |"
        elif line.startswith("| Saved figure sets |"):
            lines[index] = f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |"
        elif line.startswith("| Saved image files |"):
            lines[index] = f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |"
    path.write_text(("\n".join(lines) + section + later).rstrip() + "\n")
    return f"Saved loss experiment: {ROOT / 'docs/basel_loss_experiment.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
