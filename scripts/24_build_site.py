"""Build the Pages showcase from committed results. Standard library only."""

import argparse
import csv
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform"
SOURCES = {}


def read_json(path):
    path = ROOT / path
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def table(manifest, filename):
    path = ROOT / manifest["result_directory"] / filename
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = manifest.get("results_sha256", {}).get(filename)
    if expected and expected != digest:
        raise ValueError(f"Result differs from its recorded fingerprint: {path}")
    SOURCES[str(path.relative_to(ROOT))] = digest
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def curve(points, split):
    return [[float(row["x"]), float(row["y"])] for row in points
            if row["model"] == "hist_gradient_boosting" and row["split"] == split and row["curve"] == "roc"]


def roc_path(points):
    return " ".join(("M" if index == 0 else "L") + f"{48+x*384:.2f},{252-y*208:.2f}"
                    for index, (x, y) in enumerate(points))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    model = read_json("assets/results/model_experiments_latest.json")
    preparation = read_json("assets/results/model_data_manifest.json")
    research = read_json("assets/results/auc_improvement_latest.json")
    ann = read_json("assets/results/ann_experiments_latest.json")
    loss = read_json("assets/results/basel_loss_latest.json")
    interpret = read_json("assets/results/interpret_bias_latest.json")
    load = read_json("assets/results/load_test_latest.json")
    recovery = read_json("assets/results/recovery_latest.json")
    if model["status"] != "complete" or recovery["status"] != "passed":
        raise ValueError("Showcase needs complete model results and a passed recovery batch.")
    if model["selected_model"] != "hist_gradient_boosting":
        raise ValueError("The selected model changed; review the showcase's model descriptions.")
    selected = table(model, "selected_model_metrics.csv")
    validation = next(row for row in selected if row["split"] == "validation" and row["policy"] == "validation_f1")
    later = next(row for row in selected if row["split"] == "exploratory_test" and row["policy"] == "validation_f1")
    baseline = table(model, "model_comparison.csv")
    neural = table(ann, "pd_comparison.csv")
    neural = max((row for row in neural if row["model"].startswith("ann_pd")), key=lambda row: float(row["roc_auc"]))
    importance = table(interpret, "shap_global_importance.csv")[:5]
    segments = [row for row in table(interpret, "segment_metrics.csv") if row["split"] == "exploratory_test"
                and row["policy"] == "frozen_validation_f1" and row["dimension"] == "income"]
    low_income = next(row for row in segments if row["group"] == "Q1_lowest")
    high_income = next(row for row in segments if row["group"] == "Q4_highest")
    load_rows = table(load, "stage_metrics.csv")
    portfolio = next(row for row in table(loss, "portfolio_loss_metrics.csv") if row["method"] == "selected_components")
    points = table(model, "curve_points.csv")
    clean_path = ROOT / "assets/results/05_status_coverage.csv"
    with clean_path.open(newline="") as stream:
        clean = list(csv.DictReader(stream))
    SOURCES[str(clean_path.relative_to(ROOT))] = hashlib.sha256(clean_path.read_bytes()).hexdigest()
    clean_rows = sum(int(row["loans"]) for row in clean)
    display_names = {"hist_gradient_boosting": "Histogram boosting", "random_forest": "Random forest",
                     "logistic_regression": "Logistic regression", "dummy_prior": "Prior baseline"}
    comparison = [{"name": display_names[row["model"]], "auc": float(row["validation_roc_auc"]),
                   "brier": float(row["validation_brier_score"]), "selected": row["model"] == model["selected_model"]}
                  for row in baseline]
    comparison.insert(1, {"name": "Neural network · 64 → 32", "auc": float(neural["roc_auc"]),
                         "brier": float(neural["brier_score"]), "selected": False})
    snapshot = {"repository": REPOSITORY, "updated": recovery["completed_at_utc"][:10],
        "clean_rows": clean_rows, "features": len(model["features"]),
        "cohorts": {"validation": {"name": "2014 · validation", "rows": int(validation["rows"]),
            "auc": float(validation["roc_auc"]), "brier": float(validation["brier_score"]),
            "average_precision": float(validation["average_precision"]), "curve": curve(points, "validation")},
            "exploratory_test": {"name": "2015 · exploratory", "rows": int(later["rows"]),
            "auc": float(later["roc_auc"]), "brier": float(later["brier_score"]),
            "average_precision": float(later["average_precision"]), "curve": curve(points, "exploratory_test")}},
        "comparison": comparison, "research_auc": research["best_independent_validation_roc_auc"],
        "pricing_auc": research["best_post_underwriting_validation_roc_auc"],
        "importance": [{"feature": row["feature"], "value": float(row["mean_absolute_contribution"])} for row in importance],
        "load": [{"rate": int(row["target_rows_per_second"]), "rows": int(row["scored_rows"]),
            "p95_seconds": float(row["end_to_end_p95_ms"]) / 1000,
            "completed_rate": float(row["completed_rows_per_second"])} for row in load_rows],
        "recovery": {key: recovery[key] for key in ["rows", "restart_to_first_outage_event_result_seconds",
            "suppressed_duplicate_deliveries", "deliberately_injected_duplicate_deliveries", "missing_main_scores",
            "indexed_monitoring_logs", "batch_id", "peak_checkpoint_lag", "end_checkpoint_lag", "elk_verified"]},
        "sources": {"model": model["batch_run_id"], "interpret": interpret["batch_run_id"],
                    "load": load["batch_id"], "recovery": recovery["batch_id"]}}
    model_rows = "".join(f'<tr><th scope="row">{escape(row["name"])}'
        + (' <span class="table-label">selected</span>' if row["selected"] else '')
        + f'</th><td>{row["auc"]:.4f}</td><td>{row["brier"]:.4f}</td></tr>' for row in comparison)
    load_table = "".join(f'<tr><th scope="row">{row["rate"]:,}/s</th><td>{row["rows"]:,}</td>'
        f'<td>{row["p95_seconds"]:.2f} s</td><td>{row["completed_rate"]:,.1f}/s</td></tr>' for row in snapshot["load"])
    artifacts = [("eda.png", ROOT / "assets/figures/03_numeric_distributions.png"),
        ("interpret.png", ROOT / interpret["figure_directory"] / "feature_importance.png"),
        ("recovery.png", ROOT / recovery["result_directory"] / "recovery_lag.png")]
    for name, path in artifacts:
        target = output / "assets" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    replacements = {"repo": REPOSITORY, "clean_rows": f"{clean_rows:,}", "feature_count": str(len(model["features"])),
        "auc": f"{float(later['roc_auc']):.4f}", "validation_auc": f"{float(validation['roc_auc']):.4f}",
        "test_rows": f"{int(later['rows']):,}", "roc_path": roc_path(snapshot["cohorts"]["exploratory_test"]["curve"]),
        "brier": f"{float(later['brier_score']):.4f}", "average_precision": f"{float(later['average_precision']):.4f}",
        "low_income_fpr": f"{float(low_income['fpr']) * 100:.1f}", "high_income_fpr": f"{float(high_income['fpr']) * 100:.1f}",
        "model_rows": model_rows, "load_rows": load_table, "updated": snapshot["updated"],
        "research_auc": f"{research['best_independent_validation_roc_auc']:.4f}",
        "pricing_auc": f"{research['best_post_underwriting_validation_roc_auc']:.4f}",
        "recovered_rows": f"{recovery['rows']:,}", "recovery_seconds": f"{recovery['restart_to_first_outage_event_result_seconds']:.2f}",
        "duplicates": str(recovery["suppressed_duplicate_deliveries"]), "logs": f"{recovery['indexed_monitoring_logs']:,}",
        "loss_observed": f"{float(portfolio['observed_loss_proxy_total']) / 1e6:.2f}",
        "loss_predicted": f"{float(portfolio['expected_loss_proxy_total']) / 1e6:.2f}"}
    template = (ROOT / "site/index.html").read_text()
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    if re.search(r"\{\{[^}]+\}\}", template):
        raise ValueError("Unresolved website template value.")
    (output / "index.html").write_text(template)
    for filename in ["styles.css", "app.js", "favicon.svg"]:
        shutil.copyfile(ROOT / "site" / filename, output / filename)
    (output / ".nojekyll").touch()
    (output / "assets/results.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    (output / "assets/provenance.json").write_text(json.dumps({"source_sha256": SOURCES,
        "note": "Built from committed aggregate results; no raw loans, model binaries or services are published."}, indent=2) + "\n")
    print(f"Built {output}; {len(SOURCES)} evidence files, no modelling dependencies required.")


if __name__ == "__main__":
    main()
