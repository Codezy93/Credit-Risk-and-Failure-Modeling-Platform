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


def csv_file(relative):
    path = ROOT / relative
    SOURCES[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def code_cell(relative, first=1, last=None, opened=False):
    path = ROOT / relative
    SOURCES[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    lines = path.read_text().splitlines()
    snippet = "\n".join(lines[first - 1:last])
    language = {".sql": "SQL", ".py": "Python", ".conf": "Logstash"}.get(path.suffix, "Source")
    pattern = r'''(?P<comment>\#[^\n]*|--[^\n]*)|(?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(?P<keyword>\b(?:def|if|else|elif|return|import|from|with|as|for|in|True|False|None|SELECT|FROM|WHERE|CASE|WHEN|THEN|END|AS|AND|OR|CREATE|REPLACE|TABLE|VIEW|WITH|BETWEEN|IN|IS|NOT|NULL|EXCLUDE)\b)|(?P<number>\b\d+(?:\.\d+)?\b)'''
    pieces, position = [], 0
    for match in re.finditer(pattern, snippet):
        pieces.append(escape(snippet[position:match.start()]))
        pieces.append(f'<span class="token-{match.lastgroup}">{escape(match.group())}</span>')
        position = match.end()
    pieces.append(escape(snippet[position:]))
    return (f'<details class="code-cell"{" open" if opened else ""}><summary><span class="language">{language}</span>'
        f'<span>{escape(relative)}</span><span class="source-label">source excerpt</span></summary>'
        f'<div class="code-tools"><a href="{REPOSITORY}/blob/main/{relative}#L{first}">Full source ↗</a>'
        f'<button type="button" data-copy aria-label="Copy {escape(relative)} excerpt">Copy code</button></div>'
        f'<pre tabindex="0" aria-label="{escape(relative)} source excerpt"><code>{"".join(pieces)}</code></pre></details>')


def row_cells(values, heading=True):
    cells = []
    for index, value in enumerate(values):
        tag = "th" if heading and index == 0 else "td"
        attributes = ' scope="row"' if tag == "th" else ""
        cells.append(f"<{tag}{attributes}>{escape(str(value))}</{tag}>")
    return "<tr>" + "".join(cells) + "</tr>"


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
    raw = csv_file("assets/results/01_raw_audit.csv")[0]
    cleaning = csv_file("assets/results/04_cleaning_audit.csv")
    numeric = csv_file("assets/results/20_complete_numeric_profile.csv")
    eda = read_json("assets/results/eda_completion_manifest.json")
    income = next(row for row in numeric if row["feature"] == "annual_inc")
    tails = csv_file("assets/results/14_tail_investigation.csv")
    missingness = csv_file("assets/results/16_missingness_outcomes.csv")
    profile_rows = ""
    for feature in ["loan_amnt", "annual_inc", "dti", "revol_util", "fico_mid", "credit_history_years"]:
        row = next(item for item in numeric if item["feature"] == feature)
        profile_rows += row_cells([feature, f"{float(row['missing_pct']):.3f}%",
            f"{float(row['median']):,.2f}", f"{float(row['p99']):,.2f}", f"{float(row['maximum']):,.2f}"])
    status_rows = "".join(row_cells([row["loan_status"], f"{int(row['loans']):,}", f"{float(row['pct_of_loans']):.2f}%"]) for row in clean)
    cleaning_names = {"nonpositive_income": "Nonpositive income → missing", "negative_dti": "Negative DTI → missing",
        "negative_revol_util": "Negative utilization → missing", "credit_date_after_issue": "Credit history after issue date",
        "income_parse_failures": "Income parsing failures", "dti_parse_failures": "DTI parsing failures"}
    cleaning_rows = "".join(row_cells([cleaning_names[row["check_name"]], f"{int(row['affected_rows']):,}"]) for row in cleaning)
    cohort_rows = "".join(row_cells([row["proposed_split"].replace("_", " "),
        f"{int(row['eligible_resolved_loans']):,}", f"{int(row['fully_paid']):,}", f"{int(row['charged_off']):,}",
        f"{float(row['charged_off_pct']):.2f}%"]) for row in eda["splits"])
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
    hardening = read_json("assets/results/validation_hardening_latest.json")
    artifacts = [("eda.png", ROOT / "assets/figures/03_numeric_distributions.png"),
        ("raw-missingness.png", ROOT / "assets/figures/01_raw_missingness.png"),
        ("status-coverage.png", ROOT / "assets/figures/02_status_and_followup.png"),
        ("tail-review.png", ROOT / "assets/figures/12_tail_investigation.png"),
        ("category-outcomes.png", ROOT / "assets/figures/06_category_outcomes.png"),
        ("numeric-outcomes.png", ROOT / "assets/figures/07_numeric_outcomes.png"),
        ("correlations.png", ROOT / "assets/figures/10_feature_correlations.png"),
        ("fico-dti.png", ROOT / "assets/figures/16_fico_dti_interaction.png"),
        ("cohort-coverage.png", ROOT / "assets/figures/20_benchmark_coverage.png"),
        ("calibration.png", ROOT / hardening["figure_directory"] / "calibration.png"),
        ("ann.png", ROOT / ann["figure_directory"] / "ann_comparison.png"),
        ("loss.png", ROOT / loss["figure_directory"] / "loss_and_capital.png"),
        ("interpret.png", ROOT / interpret["figure_directory"] / "feature_importance.png"),
        ("partial-dependence.png", ROOT / interpret["figure_directory"] / "partial_dependence.png"),
        ("segments.png", ROOT / interpret["figure_directory"] / "segment_disparities.png"),
        ("load.png", ROOT / load["result_directory"] / "load_results.png"),
        ("recovery.png", ROOT / recovery["result_directory"] / "recovery_lag.png")]
    image_dimensions = {}
    for name, path in artifacts:
        target = output / "assets" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        contents = path.read_bytes()
        SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(contents).hexdigest()
        image_dimensions[name] = (int.from_bytes(contents[16:20], "big"), int.from_bytes(contents[20:24], "big"))
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
    replacements.update({"raw_rows": f"{int(raw['raw_rows']):,}", "raw_columns": str(eda["source_columns"]),
        "clean_columns": str(eda["clean_columns"]), "dropped_rows": f"{int(raw['invalid_id_rows']):,}",
        "development_rows": f"{int(income['nonmissing']) + int(income['missing']):,}",
        "income_median": f"{float(income['median']):,.0f}", "income_p99": f"{float(income['p99']):,.0f}",
        "income_max": f"{float(income['maximum']):,.0f}", "status_rows": status_rows,
        "cleaning_rows": cleaning_rows, "profile_rows": profile_rows, "cohort_rows": cohort_rows,
        "validation_rows": f"{int(validation['rows']):,}", "validation_brier": f"{float(validation['brier_score']):.4f}",
        "threshold": f"{float(validation['threshold']):.6f}",
        "test_recall": f"{float(later['recall']) * 100:.2f}%", "test_precision": f"{float(later['precision']) * 100:.2f}%",
        "peak_lag": f"{recovery['peak_checkpoint_lag']:,}", "sink_recovery_seconds": f"{recovery['sink_restart_to_kafka_offsets_caught_up_seconds']:.2f}",
        "recovery_p95": f"{recovery['end_to_end_p95_ms'] / 1000:.2f}",
        "load_total": f"{sum(int(row['scored_rows']) for row in load_rows):,}",
        "load_rates": ", ".join(f"{rate:,}" for rate in load["rates"]),
        "load_duration": str(load["duration_seconds_per_stage"]), "replay_rate": str(recovery["rate"]),
        "downtime": str(recovery["configured_downtime_seconds"]),
        "income_tail_count": f"{int(next(row for row in tails if row['check_name'] == 'income_above_1m' and row['value_group'] == 'flagged')['loans']):,}",
        "dti_tail_count": f"{int(next(row for row in tails if row['check_name'] == 'dti_above_100' and row['value_group'] == 'flagged')['loans']):,}",
        "util_tail_count": f"{int(next(row for row in tails if row['check_name'] == 'utilization_above_100' and row['value_group'] == 'flagged')['loans']):,}",
        "employment_missing_rate": f"{float(next(row for row in missingness if row['feature'] == 'emp_length_years' and row['value_group'] == 'missing')['charged_off_pct']):.2f}",
        "employment_present_rate": f"{float(next(row for row in missingness if row['feature'] == 'emp_length_years' and row['value_group'] == 'present')['charged_off_pct']):.2f}",
        "feature_tags": "".join(f"<code>{escape(name)}</code>" for name in model["features"]),
        "importance_rows": "".join('<div class="importance-row"><div class="importance-label"><span>'
            + escape({"fico_mid": "FICO midpoint", "annual_inc": "Annual income", "loan_amnt": "Loan amount", "dti": "Debt-to-income ratio", "purpose": "Purpose"}.get(row['feature'], row['feature']))
            + f"</span><span>{float(row['mean_absolute_contribution']):.4f}</span></div><div class=\"importance-track\" aria-hidden=\"true\"><div class=\"importance-fill\" style=\"width:{float(row['mean_absolute_contribution']) / float(importance[0]['mean_absolute_contribution']) * 100:.1f}%\"></div></div></div>" for row in importance),
        "code_download": code_cell("scripts/download_data.py", 20, 42),
        "code_load": code_cell("sql/00_load_raw.sql", opened=True),
        "code_clean": code_cell("sql/03_clean_loans.sql"),
        "code_notebook": code_cell("notebooks/01_data_analysis.py", 52, 69),
        "code_population": code_cell("sql/26_model_population.sql", opened=True),
        "code_preprocessing": code_cell("util/modeling.py", 14, 45),
        "code_mlflow": code_cell("scripts/05_train_models.py", 191, 229),
        "code_loss": code_cell("util/basel.py", 28, 37),
        "code_interpret": code_cell("util/interpretation.py", 70, 83),
        "code_stream": code_cell("scripts/16_stream_score.py", 73, 77),
        "code_store": code_cell("util/score_store.py", 34, 57),
        "code_elk": code_cell("util/elk/logstash.conf"),
        "code_site": code_cell("scripts/24_build_site.py", 1, 22)})
    template = (ROOT / "site/index.html").read_text()
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    # Reserve the true figure aspect ratios before lazy images load.
    for name, (width, height) in image_dimensions.items():
        pattern = r'<img\b[^>]*src="assets/' + re.escape(name) + r'"[^>]*>'
        def correct_dimensions(match):
            tag = re.sub(r'width="[0-9]+"', f'width="{width}"', match.group())
            return re.sub(r'height="[0-9]+"', f'height="{height}"', tag)
        template = re.sub(pattern, correct_dimensions, template)
    if re.search(r"\{\{[^}]+\}\}", template):
        raise ValueError("Unresolved website template value.")
    (output / "index.html").write_text(template)
    (output / "favicon.svg").unlink(missing_ok=True)
    for filename in ["styles.css", "app.js"]:
        shutil.copyfile(ROOT / "site" / filename, output / filename)
    (output / ".nojekyll").touch()
    (output / "assets/results.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    (output / "assets/provenance.json").write_text(json.dumps({"source_sha256": SOURCES,
        "note": "Built from committed aggregate results; no raw loans, model binaries or services are published."}, indent=2) + "\n")
    print(f"Built {output}; {len(SOURCES)} evidence files, no modelling dependencies required.")


if __name__ == "__main__":
    main()
