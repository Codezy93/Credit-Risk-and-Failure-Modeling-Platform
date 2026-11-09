"""ANN PD and loss challengers with 2013 stopping and 2014 model comparison."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
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
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.ann import fit_temporal_ann
from util.basel import score_loss_bundle
from util.feature_policy import validate_features
from util.metrics import evaluate_model
from util.mlflow_evaluation import log_saved_model_evaluation, markdown_table
from util.validation import validate_periods


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    execution_source = Path(__file__).read_text()
    results = ROOT / "assets/results"
    data = json.loads((results / "model_data_manifest.json").read_text())
    pd_reference = json.loads((results / "model_experiments_latest.json").read_text())
    loss_reference = json.loads((results / "basel_loss_latest.json").read_text())
    features = data["features"]
    policy = validate_features(features)
    frames, metadata, hashes = {}, {}, {}
    for item in data["artifacts"]:
        if item["split"] not in ("train", "validation"):
            continue
        path = ROOT / item["path"]
        if file_hash(path) != item["sha256"]:
            raise ValueError(f"Prepared input changed: {path}")
        hashes[item["path"]] = item["sha256"]
        destination = metadata if item["kind"] == "metadata" else frames
        destination[item["split"]] = pd.read_parquet(path)
    validate_periods(metadata)
    if features != pd_reference["features"] or features != loss_reference["features"]:
        raise ValueError("ANN and reference features differ.")
    pd_input_hashes = {a["path"]: a["sha256"] for a in pd_reference["data_decision_snapshot"]["artifacts"]}
    if any(pd_input_hashes.get(path) != value or loss_reference["input_sha256"].get(path) != value
           for path, value in hashes.items()):
        raise ValueError("Reference models used different inputs.")
    contracts = []
    for split in ("train", "validation"):
        frames[split][data["numeric_features"]] = frames[split][data["numeric_features"]].astype(float)
        frame = frames[split].copy()
        frame["loan_id"] = metadata[split].loan_id.to_numpy()
        frame["issue_year"] = metadata[split].issue_year.to_numpy()
        frame["split"] = split
        contracts.append(frame)
    contract = pd.concat(contracts, ignore_index=True)
    raw_path = ROOT / "data/raw/accepted_2007_to_2018Q4.csv"
    raw_hash = file_hash(raw_path)
    if raw_hash != loss_reference["raw_source_sha256"]:
        raise ValueError("The loss reference used a different raw snapshot.")
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=4")
    con.register("model_contract", contract)
    con.execute("SET VARIABLE raw_path=?", [str(raw_path)])
    con.execute((ROOT / "sql/34_loss_population.sql").read_text())
    population = con.execute("SELECT * FROM loss_population ORDER BY split, loan_id").df()
    con.close()
    if population.loan_id.duplicated().any() or len(population) != len(contract):
        raise ValueError("Loss source join changed the loan population.")
    defaults = population[(population.charged_off == 1) & population.bounded_target_valid].copy()
    loss_dir = ROOT / loss_reference["model_directory"]
    for component, target in [("ead", "ead_ratio_proxy"), ("lgd", "lgd_snapshot_proxy")]:
        for split in ("train", "validation"):
            saved_path = loss_dir / f"{component}_{split}.parquet"
            if file_hash(saved_path) != loss_reference["dataset_sha256"][saved_path.name]:
                raise ValueError("Reference loss dataset changed.")
            expected = defaults[defaults.split == split][features + [target]].reset_index(drop=True)
            pd.testing.assert_frame_equal(expected, pd.read_parquet(saved_path), check_dtype=False)
    pd_path = ROOT / "models/selected_model.joblib"
    pd_hash = file_hash(pd_path)
    if pd_hash != pd_reference["selected_joblib_sha256"] or pd_hash != loss_reference["pd_joblib_sha256"]:
        raise ValueError("The incumbent PD artifact changed.")
    loss_bundle_path = loss_dir / "loss_model_bundle.joblib"
    loss_bundle_hash = file_hash(loss_bundle_path)
    if loss_bundle_hash != loss_reference["model_sha256"][loss_bundle_path.name]:
        raise ValueError("The reference loss bundle changed.")
    versions = {name: importlib.metadata.version(name) for name in
                ["scikit-learn", "mlflow", "numpy", "pandas", "scipy", "joblib", "cloudpickle"]}
    mlflow.set_tracking_uri("sqlite:///" + str(ROOT / "models/mlflow.db"))
    experiment_name = "lendingclub_ann_challengers"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        experiment_name, artifact_location=(ROOT / "models/mlartifacts").as_uri())
    tasks = {"pd": (frames, metadata["train"].issue_year.to_numpy(), "charged_off", "classification"),
        "ead": ({s: defaults[defaults.split == s] for s in ("train", "validation")},
                defaults[defaults.split == "train"].issue_year.to_numpy(), "ead_ratio_proxy", "regression"),
        "lgd": ({s: defaults[defaults.split == s] for s in ("train", "validation")},
                defaults[defaults.split == "train"].issue_year.to_numpy(), "lgd_snapshot_proxy", "regression")}
    with mlflow.start_run(experiment_id=experiment_id, run_name="ann_pd_ead_lgd_comparison") as batch:
        batch_id = batch.info.run_id
        result_dir = results / "ann_experiments" / batch_id
        model_dir = ROOT / "models/ann_experiments" / batch_id
        figure_dir = ROOT / "assets/figures/ann_experiments" / batch_id
        for directory in (result_dir, model_dir, figure_dir):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {"status": "running", "experiment_name": experiment_name, "experiment_id": experiment_id,
            "batch_run_id": batch_id, "features": features, "feature_policy": policy, "seed": 42,
            "selected_model": "", "model_uris": {}, "run_ids": {}, "versions": versions,
            "input_sha256": hashes, "raw_source_sha256": raw_hash,
            "pd_reference_batch_id": pd_reference["batch_run_id"], "loss_reference_batch_id": loss_reference["batch_run_id"],
            "pd_incumbent_sha256": pd_hash, "loss_reference_bundle_sha256": loss_bundle_hash,
            "epoch_selection": "fit 2011-2012; stop on 2013 AUC or bounded MAE; refit 2011-2013 for fixed selected epochs",
            "model_selection": "2014 average precision for PD, bounded MAE for each loss component",
            "test_2015_read": False, "data_previously_explored": True, "single_seed_research": True,
            "incumbent_replaced": False, "capital_scope_changed": False,
            "result_directory": str(result_dir.relative_to(ROOT)), "model_directory": str(model_dir.relative_to(ROOT)),
            "figure_directory": str(figure_dir.relative_to(ROOT))}
        mlflow.log_params({"seed": 42, "max_epochs": 60, "patience": 8, "alpha": 0.01,
                           "batch_size": 1024, "learning_rate_init": 0.001, "epoch_stopping_year": 2013,
                           "comparison_year": 2014, "pd_incumbent_replaced": False})
        models, details, all_curves, pd_rows, loss_rows, native_rows, role_rows = {}, {}, [], [], [], [], []
        for component, (datasets_frames, years, target, task) in tasks.items():
            train = datasets_frames["train"][features + [target]].copy()
            validation = datasets_frames["validation"][features + [target]].copy()
            role_frames = {"inner_fit": train.loc[years <= 2012], "stopping": train.loc[years == 2013],
                           "train": train, "validation": validation}
            datasets = {}
            for role, frame in role_frames.items():
                path = model_dir / f"{component}_{role}.parquet"
                frame.to_parquet(path, index=False)
                datasets[role] = mlflow.data.from_pandas(frame, source=str(path), targets=target, name=f"ann_{component}_{role}")
                mlflow.log_input(datasets[role], context=f"{component}_{role}")
                mlflow.log_artifact(str(path), artifact_path="datasets")
                role_rows.append({"component": component, "role": role, "rows": len(frame),
                                  "target_mean": frame[target].mean(), "dataset_digest": datasets[role].digest})
            architectures = [(32,), (64, 32)] if component == "pd" else [(32, 16)]
            for hidden in architectures:
                name = f"ann_{component}_" + "x".join(map(str, hidden))
                print(f"Training {name}: 2013 stopping, then refitting all training years", flush=True)
                with mlflow.start_run(experiment_id=experiment_id, run_name=name, nested=True) as run:
                    manifest["run_ids"][name] = run.info.run_id
                    for role, dataset in datasets.items():
                        mlflow.log_input(dataset, context=role)
                    started = perf_counter()
                    model, curve, settings = fit_temporal_ann(train, years, features, data["numeric_features"],
                        data["categorical_features"], target, task, hidden=hidden)
                    seconds = perf_counter() - started
                    models[name], details[name] = model, settings
                    curve["model"], curve["component"] = name, component
                    all_curves.append(curve)
                    mlflow.log_dict(settings, "temporal_training_settings.json")
                    mlflow.log_metrics({"fit_and_stopping_seconds": seconds, "selected_epochs": settings["selected_epochs"]})
                    for split, frame in (("train", train), ("validation", validation)):
                        if task == "classification":
                            prediction = model.predict_proba(frame[features])[:, 1]
                            values = evaluate_model(frame[target], prediction)
                            pd_rows.append({"model": name, "split": split, **values})
                        else:
                            raw_prediction = model.predict(frame[features])
                            prediction = np.clip(raw_prediction, 0, 1)
                            values = {"rows": len(frame), "raw_mae": mean_absolute_error(frame[target], raw_prediction),
                                "bounded_mae": mean_absolute_error(frame[target], prediction),
                                "bounded_rmse": root_mean_squared_error(frame[target], prediction),
                                "bounded_r2": r2_score(frame[target], prediction), "observed_mean": frame[target].mean(),
                                "predicted_mean": prediction.mean(), "predictions_clipped": int((raw_prediction != prediction).sum())}
                            loss_rows.append({"model": name, "component": component, "split": split, **values})
                        mlflow.log_metrics({f"{split}_{key}": float(value) for key, value in values.items()}, dataset=datasets[split])
                    path = model_dir / f"{name}.joblib"
                    joblib.dump(model, path)
                    np.testing.assert_allclose(joblib.load(path).predict(validation[features].head(100)),
                                               model.predict(validation[features].head(100)), atol=1e-12)
                    info = mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle",
                        pyfunc_predict_fn="predict_proba" if task == "classification" else "predict",
                        input_example=validation[features].head(5), signature=infer_signature(validation[features].head(5),
                        model.predict_proba(validation[features].head(5)) if task == "classification" else model.predict(validation[features].head(5))),
                        pip_requirements=[f"{key}=={value}" for key, value in versions.items()])
                    manifest["model_uris"][name] = info.model_uri
                if task == "classification":
                    native_rows.append({"component": component, **log_saved_model_evaluation(manifest, name, "validation", datasets["validation"])})
                else:
                    with mlflow.start_run(experiment_id=experiment_id, run_name=f"evaluate_{name}", nested=True) as evaluation:
                        mlflow.set_tags({"run_kind": "evaluation", "source_training_run_id": run.info.run_id})
                        result = mlflow.models.evaluate(model=info.model_uri, model_id=info.model_uri.split("/")[-1],
                            data=datasets["validation"], model_type="regressor", evaluators="default",
                            evaluator_config={"log_model_explainability": False, "metric_prefix": "native_validation_"})
                        native_rows.append({"component": component, "model": name,
                            "evaluation_run_id": evaluation.info.run_id, **result.metrics})
                print(f"Finished {name}: selected {settings['selected_epochs']} epochs", flush=True)
        pd_metrics = pd.DataFrame(pd_rows)
        loss_metrics = pd.DataFrame(loss_rows)
        chosen_pd = pd_metrics[pd_metrics.split == "validation"].sort_values(["average_precision", "roc_auc"], ascending=False).iloc[0].model
        ann_bundle = {"features": features, "pd_model": models[chosen_pd],
            "ead_ratio_model": models["ann_ead_32x16"], "lgd_model": models["ann_lgd_32x16"],
            "bound_loss_predictions": [0, 1], "scope": "ANN challengers for resolved-outcome snapshot loss proxies"}
        joblib.dump(ann_bundle, model_dir / "ann_loss_bundle.joblib")
        portfolio = population[(population.split == "validation") & (population.charged_off.eq(0) | population.bounded_target_valid)].copy()
        reference_bundle = joblib.load(loss_bundle_path)
        choices = {"reference": reference_bundle,
            "ann_pd_only": {**reference_bundle, "pd_model": models[chosen_pd]},
            "ann_loss_only": {**ann_bundle, "pd_model": reference_bundle["pd_model"]},
            "all_ann": ann_bundle}
        portfolio_rows = []
        for method, bundle in choices.items():
            scored = score_loss_bundle(bundle, portfolio[features], portfolio.funded_amnt)
            portfolio_rows.append({"method": method, "rows": len(portfolio),
                "observed_loss_proxy_total": portfolio.observed_loss_proxy.sum(),
                "expected_loss_proxy_total": scored.expected_loss_proxy.sum(),
                "portfolio_relative_error": scored.expected_loss_proxy.sum() / portfolio.observed_loss_proxy.sum() - 1,
                "loan_dollar_mae": mean_absolute_error(portfolio.observed_loss_proxy, scored.expected_loss_proxy),
                "loan_dollar_rmse": root_mean_squared_error(portfolio.observed_loss_proxy, scored.expected_loss_proxy)})
        original_pd_metrics = []
        for name in ("logistic_regression", "hist_gradient_boosting"):
            model = joblib.load(ROOT / pd_reference["model_directory"] / f"{name}.joblib")
            original_pd_metrics.append({"model": name, "split": "validation", **evaluate_model(
                frames["validation"].charged_off, model.predict_proba(frames["validation"][features])[:, 1])})
        pd_comparison = pd.concat([pd.DataFrame(original_pd_metrics), pd_metrics[pd_metrics.split == "validation"]], ignore_index=True)
        old_loss = pd.read_csv(ROOT / loss_reference["result_directory"] / "component_metrics.csv")
        loss_comparison = pd.concat([old_loss[old_loss.split == "validation"], loss_metrics[loss_metrics.split == "validation"]], ignore_index=True)
        curves = pd.concat(all_curves, ignore_index=True)
        tables = {"pd_metrics": pd_metrics, "pd_comparison": pd_comparison,
            "loss_metrics": loss_metrics, "loss_comparison": loss_comparison, "learning_curves": curves,
            "portfolio_loss_comparison": pd.DataFrame(portfolio_rows), "dataset_roles": pd.DataFrame(role_rows),
            "native_evaluations": pd.DataFrame(native_rows)}
        for name, table in tables.items():
            table.to_csv(result_dir / f"{name}.csv", index=False)
        figure, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        for name, group in curves[curves.phase == "stopping_2013"].groupby("model"):
            axis = axes[0] if name.startswith("ann_pd") else axes[1]
            axis.plot(group.epoch, group.stopping_value, label=name)
            axis.axvline(details[name]["selected_epochs"], linestyle=":", alpha=0.5)
        axes[0].set(xlabel="Epoch", ylabel="2013 ROC-AUC", title="PD stopping, before 2014 comparison")
        axes[1].set(xlabel="Epoch", ylabel="2013 bounded MAE", title="Loss-component stopping")
        for axis in axes:
            axis.legend(fontsize=8)
        save_figure(figure, figure_dir, "temporal_learning_curves")
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
        axes[0].barh(pd_comparison.model, pd_comparison.roc_auc)
        axes[0].set(xlabel="2014 ROC-AUC", xlim=(0.5, 0.75), title="Same 13 features and final training years")
        axes[1].barh([r["method"] for r in portfolio_rows], [100*r["portfolio_relative_error"] for r in portfolio_rows])
        axes[1].axvline(0, color="gray")
        axes[1].set(xlabel="Expected versus observed loss error (%)", title="Same eligible validation portfolio")
        save_figure(figure, figure_dir, "ann_comparison")
        if file_hash(pd_path) != pd_hash or file_hash(loss_bundle_path) != loss_bundle_hash:
            raise ValueError("An incumbent artifact changed during ANN research.")
        source_paths = [Path(__file__), ROOT / "util/ann.py", ROOT / "util/modeling.py", ROOT / "util/basel.py",
                        ROOT / "util/metrics.py", ROOT / "util/feature_policy.json", ROOT / "requirements.lock"]
        manifest.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
            selected_ann_pd=chosen_pd, temporal_settings=details,
            execution_script_sha256=hashlib.sha256(execution_source.encode()).hexdigest(),
            source_sha256={str(path.relative_to(ROOT)): file_hash(path) for path in source_paths},
            results_sha256={path.name: file_hash(path) for path in result_dir.glob("*.csv")},
            model_sha256={path.name: file_hash(path) for path in model_dir.glob("*.joblib")},
            dataset_sha256={path.name: file_hash(path) for path in model_dir.glob("*.parquet")})
        report = write_report(manifest, tables)
        (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (results / "ann_experiments_latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(result_dir), artifact_path="results")
        mlflow.log_artifacts(str(figure_dir), artifact_path="figures")
        mlflow.log_artifact(str(model_dir / "ann_loss_bundle.joblib"), artifact_path="model_bundle")
        for path in source_paths:
            mlflow.log_artifact(str(path), artifact_path="source")
        mlflow.log_artifact(str(ROOT / "docs/ann_experiments.md"), artifact_path="reports")
        print(report, flush=True)


def save_figure(figure, directory, name):
    figure.savefig(directory / f"{name}.png", dpi=160)
    path = directory / f"{name}.svg"
    figure.savefig(path)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(figure)


def write_report(manifest, tables):
    report = "# ANN challengers\n\n"
    report += ("Two multilayer-perceptron classifiers (32 and 64→32 hidden units) and two "
        "32→16 regressors test whether neural networks improve PD discrimination or snapshot loss proxies. "
        "They use the same 13 origination predictors as the original benchmark. No PyTorch/TensorFlow dependency is added.\n\n"
        "## Protocol\n\n"
        "Preprocessing is median imputation, training-only scaling, log1p for income/revolving balance, "
        "numeric missing flags, and one-hot categories. Each stopping fit learns preprocessing on 2011–2012 only. "
        "Stopping uses 2013 ROC-AUC for PD and bounded MAE for losses, with at most 60 epochs and patience 8. "
        "The chosen epoch budget is frozen, then preprocessing and network are refitted from scratch on 2011–2013. "
        "2014 selects the ANN PD candidate by average precision and compares loss components by bounded MAE. "
        "2014 does not select the stopping epoch. Losses train only on the identical eligible defaulted population "
        "used in the Basel-style proxy experiment. Only origination features reach neural-network inputs.\n\n"
        "All networks use ReLU, Adam, alpha 0.01, learning rate 0.001, batch size 1024 and seed 42. "
        "Only one seed is studied; these are selection-influenced research results on already-explored cohorts. "
        "There is no new holdout claim. No 2015 rows are read, and incumbent PD/loss artifacts remain unchanged. "
        "The stopping cohort is subsequently included in the fixed-budget refit; it is not an independent final evaluation.\n\n"
        "## Loss composition\n\n"
        "Compare the reference bundle, ANN PD alone, ANN loss components alone, and all-ANN composition on "
        "the same eligible portfolio. Regressor predictions are explicitly bounded to [0,1] for loss composition. "
        "Raw errors/clipping counts are saved, while native regression evaluations use raw outputs. "
        "Expected-loss outputs retain the snapshot and residual-dependence limitations from the loss report. "
        "No capital assumptions or one-year-PD claims change.\n\n")
    for name in ["pd_comparison", "loss_comparison", "portfolio_loss_comparison", "dataset_roles"]:
        report += f"## {name.replace('_', ' ')}\n\n" + markdown_table(tables[name]) + "\n\n"
    report += (f"![Learning curves](../{manifest['figure_directory']}/temporal_learning_curves.png)\n\n"
        f"![ANN comparison](../{manifest['figure_directory']}/ann_comparison.png)\n\n"
        f"MLflow experiment `{manifest['experiment_name']}`, batch `{manifest['batch_run_id']}`. "
        f"[Manifest and complete CSVs](../{manifest['result_directory']}/manifest.json).\n\n"
        "References: [MLPClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html), "
        "[MLPRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPRegressor.html).\n")
    (ROOT / "docs/ann_experiments.md").write_text(report)
    marker = "<!-- ann-experiment-statistics -->"
    path = ROOT / "assets/statistics.md"
    original = path.read_text().split(marker)[0].rstrip()
    toc = "23. [ANN challengers](#23-ann-challengers)"
    if toc not in original:
        original = original.replace("22. [Basel-style loss experiment](#22-basel-style-loss-experiment)",
                                    "22. [Basel-style loss experiment](#22-basel-style-loss-experiment)\n" + toc)
    lines = original.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Completed stage |"):
            lines[index] = "| Completed stage | ANN challengers complete (section 23); incumbents unchanged |"
        elif line.startswith("| Saved result CSVs |"):
            lines[index] = f"| Saved result CSVs | {len(list((ROOT / 'assets/results').rglob('*.csv')))} |"
        elif line.startswith("| Saved figure sets |"):
            lines[index] = f"| Saved figure sets | {len(list((ROOT / 'assets/figures').rglob('*.png')))} |"
        elif line.startswith("| Saved image files |"):
            lines[index] = f"| Saved image files | {len(list((ROOT / 'assets/figures').rglob('*.png'))) + len(list((ROOT / 'assets/figures').rglob('*.svg')))} |"
    section = f"\n\n{marker}\n\n## 23. ANN challengers\n\n" + report.split("\n", 1)[1]
    for name, table in tables.items():
        section += f"\n\n### {name}\n\n" + markdown_table(table)
    section += "\n\n### Full ANN manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n"
    path.write_text(("\n".join(lines) + section).rstrip() + "\n")
    return f"Saved ANN report: {ROOT / 'docs/ann_experiments.md'}"


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
