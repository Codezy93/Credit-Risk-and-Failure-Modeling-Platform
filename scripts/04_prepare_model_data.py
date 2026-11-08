"""Prepare the EDA-approved temporal splits without fitting preprocessing."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from util.feature_policy import validate_features
from util.validation import validate_model_population
RESULTS = ROOT / "assets/results"


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        chunk = stream.read(1024 * 1024)
        while chunk:
            digest.update(chunk)
            chunk = stream.read(1024 * 1024)
    return digest.hexdigest()


def markdown_table(frame):
    lines = ["| " + " | ".join(frame.columns) + " |",
             "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append("—")
            elif isinstance(value, float):
                values.append(f"{value:,.6f}".rstrip("0").rstrip("."))
            elif isinstance(value, int):
                values.append(f"{value:,}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main():
    eda_path = RESULTS / "eda_completion_manifest.json"
    eda = json.loads(eda_path.read_text())
    assert eda["status"] == "complete" and eda["checks_passed"]
    assert eda["benchmark_term_months"] == 36
    assert eda["train_years"] == [2011, 2012, 2013]
    assert eda["validation_years"] == [2014]
    assert eda["exploratory_test_years"] == [2015]
    candidates = eda["candidate_features"]
    validate_features(candidates)
    decisions = pd.read_csv(RESULTS / "eda_feature_decisions.csv")
    assert candidates == decisions.loc[decisions.initial_feature_decision == "candidate", "column"].tolist()
    assert all(name.isidentifier() for name in candidates)

    source = ROOT / "data/clean/loans.parquet"
    output_dir = ROOT / "data/clean/modeling"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = file_hash(source)
    con = duckdb.connect()
    con.execute("SET memory_limit = '1GB'")
    con.execute("SET threads = 4")
    con.execute("SET VARIABLE clean_path = ?", [str(source)])
    con.execute((ROOT / "sql/26_model_population.sql").read_text())

    tables = {}
    for name in ["27_training_feature_profile", "28_model_split_summary", "29_model_missingness",
                 "30_model_category_coverage", "31_model_unknown_categories"]:
        frame = con.execute((ROOT / "sql" / f"{name}.sql").read_text()).df()
        frame.to_csv(RESULTS / f"{name}.csv", index=False)
        tables[name] = frame

    profile = tables["27_training_feature_profile"]
    summary = tables["28_model_split_summary"]
    assert set(profile.feature) == set(candidates)
    assert (summary.rows == summary.unique_loan_ids).all()
    assert (summary.fully_paid + summary.charged_off == summary.rows).all()
    assert (summary.label_mismatches == 0).all()
    assert (summary.duplicate_ids_in_population == 0).all()

    # A single nonmissing value plus missing entries can still carry information.
    # Drop all-missing columns, or constant columns with no missing entries.
    drop_mask = (profile.distinct_nonmissing == 0) | ((profile.distinct_nonmissing == 1) & (profile.missing == 0))
    dropped = profile.loc[drop_mask, "feature"].tolist()
    features = [name for name in candidates if name not in dropped]
    feature_policy = validate_features(features)
    profile["retained"] = ~drop_mask
    profile.to_csv(RESULTS / "27_training_feature_profile.csv", index=False)
    assert features
    population_metadata = con.execute("SELECT loan_id, issue_date, loan_status, charged_off, split FROM model_population").df()
    validate_model_population(population_metadata)

    expected = {row["proposed_split"]: row for row in eda["splits"]}
    assert set(summary.split) == set(expected)
    for row in summary.itertuples():
        assert row.rows == expected[row.split]["eligible_resolved_loans"]
        assert row.charged_off == expected[row.split]["charged_off"]
        assert row.fully_paid == expected[row.split]["fully_paid"]
    train = summary[summary.split == "train"].iloc[0]
    validation = summary[summary.split == "validation"].iloc[0]
    test = summary[summary.split == "exploratory_test"].iloc[0]
    assert train.last_issue_month < validation.first_issue_month
    assert validation.last_issue_month < test.first_issue_month

    metadata_columns = ["loan_id", "issue_date", "issue_year", "application_type"]
    artifacts = []
    for row in summary.itertuples():
        for suffix, columns in [("", features + ["charged_off"]), ("_metadata", metadata_columns)]:
            path = output_dir / f"{row.split}{suffix}.parquet"
            # Identical explicit ordering keeps predictor/label rows aligned with metadata.
            con.execute(
                f"COPY (SELECT {', '.join(columns)} FROM model_population WHERE split = ? "
                "ORDER BY issue_date, loan_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [row.split, str(path)],
            )
            saved = con.read_parquet(str(path))
            assert saved.columns == columns
            assert saved.count("*").fetchall()[0][0] == row.rows
            artifacts.append({"path": str(path.relative_to(ROOT)), "split": row.split,
                              "kind": "metadata" if suffix else "features_and_target",
                              "rows": row.rows, "columns": len(columns),
                              "bytes": path.stat().st_size, "sha256": file_hash(path)})
        print(f"Saved {row.split}: {row.rows:,} rows, {len(features)} predictors")

    assert file_hash(source) == source_hash, "Clean source changed while splits were being prepared."
    numeric = [name for name in features if name not in ["home_ownership", "purpose", "application_type"]]
    categorical = [name for name in features if name not in numeric]
    manifest = {
        "stage": "model_data_preparation", "status": "complete",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_path": str(source.relative_to(ROOT)), "source_sha256": source_hash,
        "eda_manifest_sha256": file_hash(eda_path),
        "eda_decision_snapshot": eda,
        "candidate_features": candidates, "features": features,
        "numeric_features": numeric, "categorical_features": categorical,
        "training_only_dropped_features": dropped, "target": "charged_off",
        "positive_class": 1, "positive_class_meaning": "Charged Off",
        "negative_class_meaning": "Fully Paid", "benchmark_term_months": 36,
        "train_years": eda["train_years"], "validation_years": eda["validation_years"],
        "exploratory_test_years": eda["exploratory_test_years"],
        "fixed_horizon": False, "deployment_backtest": False,
        "test_previously_explored": True, "preprocessing_fitted": False,
        "model_training_started": False, "row_order": ["issue_date", "loan_id"],
        "feature_policy": feature_policy,
        "artifacts": artifacts,
        "sql_sha256": {path.name: file_hash(path) for path in sorted((ROOT / "sql").glob("*.sql")) if 26 <= int(path.name[:2]) <= 31},
        "script_sha256": file_hash(Path(__file__)),
        "versions": {"duckdb": duckdb.__version__, "pandas": pd.__version__},
    }
    (RESULTS / "model_data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    report = f"""# Prepared model datasets

Prepared: {manifest['completed_at_utc']}.

The clean analysis table has been filtered into the EDA-approved retrospective
benchmark: 36-month loans issued in 2011–2015 with an ordinary Fully Paid or
Charged Off outcome. The source Parquet is unchanged; its SHA-256 is
`{source_hash}`. There are {int(summary.rows.sum()):,} eligible loans across the
three splits, matching the final EDA counts. The 147 other-status 2015 loans were
excluded by the existing outcome rule, not treated as negative labels.

## Split counts

{markdown_table(summary)}

## Features and preprocessing

The 14 EDA candidates were profiled using **training rows only**. The retained
predictor count is **{len(features)}**: {', '.join(f'`{name}`' for name in features)}.

Dropped from the candidate list: **{', '.join(dropped) or 'none'}**. A feature is
dropped only if it is all missing in training, or has a single nonmissing value
and no missing rows. A single value plus missingness is retained. The decision is
not learned from validation or evaluation data. Candidate category coverage is
still reported, including dropped application type, so new joint applications
remain visible in the audit metadata.

No imputation, scaling, log transform, clipping, rare-category grouping, class
rebalancing, synthetic sampling, or new risk flag was fitted. Missing values and
extreme values are preserved. The next training script must fit all learned
preprocessing using training rows only and handle unknown categories explicitly.

## Files and loading contract

Each of `train.parquet`, `validation.parquet`, and `exploratory_test.parquet` in
`data/clean/modeling/` contains exactly the retained predictors plus `charged_off`.
Separate `_metadata.parquet` files contain loan ID, issue month/year, and application
type. Both files use the same explicit `(issue_date, loan_id)` ordering; they
correspond row for row. If later processing shuffles or filters rows, carry the
metadata through the same operation. Metadata must never be selected as predictors.

Use the exact `features`, `numeric_features`, `categorical_features`, and `target`
lists from `assets/results/model_data_manifest.json`; do not infer predictors by
selecting every column in a table. The target is 1 = Charged Off, 0 = Fully Paid.
File sizes, schemas, source hash, output hashes, SQL hashes, and software versions
are recorded in the manifest. Local dataset files are excluded from Git.

## Evaluation limits

The 2015 split is exploratory: EDA inspected it before model selection. The labels
are resolved-loan outcomes, not a fixed 12-/36-month default horizon. Snapshot
labels on training loans were not necessarily available before later issue years.
This is not a deployment backtest, a pristine holdout, or a portfolio-wide default
probability estimate. Accepted-only selection, joint-applicant financial omissions,
and the prediction-time availability caveats in the final EDA report remain.

## Validation

Counts and positive/negative labels match the EDA manifest. IDs are unique across
the entire population; split date ranges do not overlap. Label/status consistency
checks pass. Every written Parquet has the expected row count and ordered columns.
The clean source fingerprint is unchanged before/after preparation. Dataset and
metadata files are fingerprinted individually. No model training has started.

Run `python scripts/04_prepare_model_data.py` to regenerate these artifacts from
the existing clean Parquet. This does not rerun EDA or read the raw CSV.
"""
    (ROOT / "docs/model_data.md").write_text(report)

    stats_path = ROOT / "assets/statistics.md"
    marker = "<!-- model-data-statistics -->"
    existing = stats_path.read_text()
    experiment_marker = "<!-- model-experiment-statistics -->"
    experiment_section = ""
    if experiment_marker in existing:
        experiment_section = experiment_marker + existing.split(experiment_marker, 1)[1]
    original = existing.split(marker)[0].rstrip()
    if not experiment_section:
        original = re.sub(r"\| Completed stage \| [^\n]+ \|", "| Completed stage | EDA and model-data preparation complete; training not started |", original)
    original = re.sub(r"\| Saved result CSVs \| [\d,]+ \|", f"| Saved result CSVs | {len(list(RESULTS.rglob('*.csv')))} |", original)
    original = original.replace("17. [Model-data preparation](#17-model-data-preparation)\n", "")
    original = original.replace("16. [EDA completion](#16-eda-completion)", "16. [EDA completion](#16-eda-completion)\n17. [Model-data preparation](#17-model-data-preparation)")
    parts = [marker, "## 17. Model-data preparation",
             f"Completed: {manifest['completed_at_utc']}.",
             "Full contract and limitations: [prepared dataset report](../docs/model_data.md). Source and output fingerprints: [manifest](results/model_data_manifest.json).",
             f"Prepared {int(summary.rows.sum()):,} loans and {len(features)} predictors from 14 candidates. Training-only dropped columns: {', '.join(dropped) or 'none'}. No preprocessing was fitted and no models were trained. Clean source SHA-256: `{source_hash}`.",
             "The target is the resolved-loan charged-off label, not fixed-horizon default. 2015 remains exploratory; this is not a historical deployment backtest."]
    for name, frame in tables.items():
        parts.extend([f"### {name}",
                      f"Source: [{name}.csv](results/{name}.csv). SHA-256: `{file_hash(RESULTS / (name + '.csv'))}`.",
                      markdown_table(frame)])
    parts.extend(["### Prepared file inventory", markdown_table(pd.DataFrame(artifacts)),
                  f"All six files are local and Git-ignored. Feature/target and metadata pairs share the same explicit issue-month/ID ordering. Nulls and tails are preserved. The manifest records {len(numeric)} numeric and {len(categorical)} categorical features; its exact lists are authoritative.",
                  "### Verification", "EDA count/label reconciliation, unique IDs across splits, separated date ranges, exact output columns/row counts, and unchanged clean-source fingerprint passed. No MLflow, InterpretML, Kafka, or ELK measurements have been produced."])
    stats_path.write_text(original + "\n\n" + "\n\n".join(parts) + "\n\n" + experiment_section)
    con.close()
    print(f"Prepared {int(summary.rows.sum()):,} loans. Updated docs/model_data.md and assets/statistics.md.")


if __name__ == "__main__":
    main()
