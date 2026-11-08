import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import csv
    from datetime import datetime, timezone
    import hashlib
    import json
    from pathlib import Path
    import re

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    return Path, csv, datetime, duckdb, hashlib, json, mo, pd, plt, re, sns, timezone


@app.cell
def _(mo):
    mo.md("""
    # Completing the LendingClub EDA

    This final pass closes the open data questions and records the decisions
    that the modeling stage will inherit. It adds complete numeric profiles,
    category support checks, outcome boxplots, source parsing checks, a feature
    availability audit, and a cohort decision. It does not train a model.

    All detailed profiles use development originations through 2015. The original
    CSV and clean Parquet remain unchanged. Earlier notebooks and their reports
    remain part of the EDA evidence.
    """)
    return


@app.cell
def _(Path, duckdb, mo, pd, plt, sns):
    root = Path(__file__).resolve().parents[1]
    results_dir = root / "assets/results"
    figures_dir = root / "assets/figures"
    con = duckdb.connect()
    con.execute("SET memory_limit = '1GB'")
    con.execute("SET threads = 4")
    con.execute("SET VARIABLE clean_path = ?", [str(root / "data/clean/loans.parquet")])
    con.execute("SET VARIABLE raw_path = ?", [str(root / "data/raw/accepted_2007_to_2018Q4.csv")])
    con.execute("""
        CREATE VIEW eda_loans AS SELECT * FROM read_parquet(getvariable('clean_path'))
        WHERE issue_year <= 2015
    """)
    sns.set_theme(style="whitegrid", palette="colorblind")
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})

    def query(filename):
        frame = con.execute((root / "sql" / filename).read_text()).df()
        frame.to_csv(results_dir / f"{Path(filename).stem}.csv", index=False)
        return frame

    def save_figure(figure, name):
        figure.tight_layout()
        figure.savefig(figures_dir / f"{name}.png", dpi=160, bbox_inches="tight")
        svg_path = figures_dir / f"{name}.svg"
        figure.savefig(svg_path, bbox_inches="tight")
        svg_lines = svg_path.read_text().splitlines()
        svg_path.write_text("\n".join(line.rstrip() for line in svg_lines) + "\n")
        display = mo.as_html(figure)
        plt.close(figure)
        return display

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
                    values.append(str(value).replace("|", "\\|").replace("\n", " "))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    return con, figures_dir, markdown_table, query, results_dir, root, save_figure


@app.cell
def _(mo, query):
    full_numeric = query("20_complete_numeric_profile.sql")
    value_checks = query("24_clean_value_checks.sql")
    source_parsing = query("25_numeric_source_parsing.sql")
    mo.vstack([
        mo.md("""
        ## Complete numeric profile and conversion checks

        The numeric profile covers all 14 continuous/count/term fields in the
        clean table, excluding identifiers, calendar year, and target. Means,
        sample standard deviations, skewness, and excess kurtosis supplement
        the earlier percentiles. A normal distribution has excess kurtosis 0;
        large values can be dominated by a few extreme observations.

        Conversion checks revisit 16 source inputs for valid development rows,
        including the dates, employment length, and term. Blank strings are
        missing; employment `n/a` is also treated as missing. The issue-date
        parsing result is conditional on the rows already admitted to development;
        the 33 unusable source rows remain documented by the original raw audit.
        These checks do not certify the meaning of extreme but parseable numbers.
        """),
        mo.ui.table(full_numeric.round(4), selection=None),
        mo.ui.table(source_parsing, selection=None),
        mo.ui.table(value_checks, selection=None),
    ])
    return full_numeric, source_parsing, value_checks


@app.cell
def _(mo, pd, plt, query, save_figure):
    outcome_numeric = query("22_numeric_by_outcome.sql")
    _features = ["annual_inc", "loan_amnt", "dti", "fico_mid", "revol_util", "credit_history_years"]
    _units = {"annual_inc": "Annual income ($, log scale)", "loan_amnt": "Loan principal ($)",
              "dti": "DTI", "fico_mid": "FICO midpoint", "revol_util": "Utilization (%)",
              "credit_history_years": "Credit history (years)"}
    _fig, _axes = plt.subplots(2, 3, figsize=(13, 8))
    for _ax, _feature in zip(_axes.flat, _features):
        _group = outcome_numeric[outcome_numeric.feature == _feature].sort_values("charged_off")
        _boxes = []
        for _row in _group.itertuples():
            _boxes.append({"label": "Fully paid" if _row.charged_off == 0 else "Charged off",
                           "q1": _row.p25, "med": _row.median, "q3": _row.p75,
                           "whislo": _row.p01, "whishi": _row.p99, "fliers": []})
        _ax.bxp(_boxes, showfliers=False)
        if _feature == "annual_inc":
            _ax.set_yscale("log")
        _ax.set(title=_feature.replace("_", " "), ylabel=_units[_feature])
    mo.vstack([
        mo.md("""
        ## Outcome distributions: compare overlap, not only averages

        These boxes use exact full-development SQL quantiles among ordinary
        resolved loans. The box spans p25–p75, the middle line is the median,
        and **whiskers are p01–p99**, not the usual Tukey rule. Income uses a log
        axis. The table retains minimum and maximum values, so hiding outlying
        points does not remove them from the analysis. Distributions overlap;
        their differences are not model performance or causal estimates.
        """),
        save_figure(_fig, "18_outcome_boxplots"),
        mo.ui.table(outcome_numeric.round(4), selection=None),
    ])
    return (outcome_numeric,)


@app.cell
def _(mo, plt, query, save_figure):
    category_profile = query("21_complete_category_profile.sql")
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 7))
    _states = category_profile[category_profile.feature == "addr_state"].sort_values("total_loans").tail(20)
    _axes[0].barh(_states.category, _states.total_loans / 1000)
    _axes[0].set(title="20 largest state groups", xlabel="Development loans (thousands)")
    _rare = category_profile[category_profile.rare_in_development].copy()
    _rare["label"] = _rare.feature + ": " + _rare.category
    _rare = _rare.sort_values("total_loans")
    _axes[1].barh(_rare.label, _rare.total_loans)
    _axes[1].set(title="Rare categories: fewer than 200 development loans", xlabel="Loans")
    mo.vstack([
        mo.md("""
        ## Category support and rare groups

        This audit includes every category of grade, subgrade, purpose, ownership,
        verification, application type, and state. A rare-category flag means
        fewer than 200 **total** development loans; it differs from the 200
        **resolved** loans required to plot an outcome rate in earlier figures.

        Rare labels remain in the analysis table. Future encoding should handle
        unseen categories and learn any rare-category grouping on training rows
        only. State is retained for descriptive review, not included in the initial
        predictor shortlist. Removing state alone would not establish fairness.
        """),
        save_figure(_fig, "19_category_support"),
        mo.ui.table(category_profile.round(4), selection=None),
    ])
    return (category_profile,)


@app.cell
def _(mo, pd, plt, query, results_dir, save_figure):
    cohort_audit = query("23_final_cohort_audit.sql")
    _eligible = cohort_audit[cohort_audit.proposed_split != "outside_benchmark"]
    benchmark_splits = _eligible.groupby("proposed_split", sort=False)[
        ["all_loans", "eligible_resolved_loans", "excluded_other_status", "fully_paid", "charged_off"]
    ].sum().reset_index()
    benchmark_splits["resolved_pct"] = 100 * benchmark_splits.eligible_resolved_loans / benchmark_splits.all_loans
    benchmark_splits["charged_off_pct"] = 100 * benchmark_splits.charged_off / benchmark_splits.eligible_resolved_loans
    benchmark_splits.to_csv(results_dir / "eda_benchmark_splits.csv", index=False)
    _fig, _axes = plt.subplots(1, 2, figsize=(12, 5))
    _axes[0].bar(benchmark_splits.proposed_split, benchmark_splits.eligible_resolved_loans / 1000)
    _axes[0].set(ylabel="Eligible resolved loans (thousands)", title="Retrospective benchmark population")
    _axes[1].bar(benchmark_splits.proposed_split, benchmark_splits.resolved_pct)
    _axes[1].set(ylabel="Ordinary resolved outcomes (%)", ylim=(0, 105), title="Outcome coverage before exclusions")
    for _ax in _axes:
        _ax.tick_params(axis="x", rotation=15)
    mo.vstack([
        mo.md("""
        ## Final cohort decision for the first benchmark

        Use **36-month loans issued in 2011–2015** whose status is exactly
        Fully Paid or Charged Off. Train: 2011–2013; validation: 2014;
        exploratory test: 2015. The table reports exclusions before filtering.
        This supersedes the initial 2016 / 2017–2018 split proposal, whose low
        outcome coverage made it unsuitable for this first resolved-loan benchmark.

        The target is **charged off among the selected resolved loans**, not
        default within 12 or 36 months. No common observation cutoff or historical
        label-availability timestamps have been established. Therefore, this is
        neither a deployment backtest nor a fixed-horizon probability-of-default
        dataset. High coverage does not by itself prove unbiased outcomes.

        EDA already inspected every proposed split. In particular, 2015 is an
        exploratory evaluation set, not a pristine holdout. Model preprocessing
        and tuning must still use training and validation only. No model-ready
        files are created in this stage. Joint loans remain included; the focused
        table does not contain co-applicant financial details, a further limitation.
        """),
        save_figure(_fig, "20_benchmark_coverage"),
        mo.ui.table(benchmark_splits.round(4), selection=None),
        mo.ui.table(cohort_audit.round(4), selection=None),
    ])
    return benchmark_splits, cohort_audit


@app.cell
def _(con, csv, mo, pd, plt, results_dir, root, save_figure):
    # Explicit decisions for all 26 columns in the focused clean table.
    _definitions = [
        ("loan_id", "id", "Loan identifier", "identifier", "exclude", "Join/audit key; never a risk predictor"),
        ("issue_date", "issue_d", "Issue month parsed to its first day", "split_metadata", "exclude", "Cohort assignment; no exact daily issue timestamp"),
        ("issue_year", "issue_d", "Year of issue month", "split_metadata", "exclude", "Time split and monitoring"),
        ("loan_status", "loan_status", "Status in the source snapshot", "outcome", "exclude", "Outcome information; direct target leakage"),
        ("charged_off", "loan_status", "1 charged off, 0 fully paid, otherwise missing", "target", "exclude", "Analysis label, never an input"),
        ("term_months", "term", "Contract term in months", "constant_in_benchmark", "exclude", "First benchmark fixes term to 36 months"),
        ("grade", "grade", "Assigned LendingClub grade", "underwriting_output", "exclude", "Existing underwriting output; defer to a separate ablation"),
        ("sub_grade", "sub_grade", "Assigned LendingClub subgrade", "underwriting_output", "exclude", "Existing underwriting output; defer to a separate ablation"),
        ("int_rate", "int_rate", "Assigned interest rate in percentage points", "underwriting_output", "exclude", "Pricing output; not independent borrower information"),
        ("installment", "installment", "Scheduled payment on the approved loan", "underwriting_output", "exclude", "Depends on pricing and term"),
        ("verification_status", "verification_status", "Reported income-verification status", "workflow_review", "exclude", "Availability depends on the scoring point in the workflow"),
        ("addr_state", "addr_state", "Reported state", "geographic_review", "exclude", "Descriptive group review; excluding it does not prove fairness"),
        ("loan_amnt", "loan_amnt", "Loan principal in USD", "candidate", "candidate", "Use only if requested principal is known at the chosen scoring point"),
        ("annual_inc", "annual_inc", "Reported annual income in USD", "candidate", "candidate", "Keep missing; consider training-only log1p and missingness indicator"),
        ("dti", "dti", "Source debt-to-income measure", "candidate", "candidate", "Keep extremes; investigate 999; consider a greater-than-100 flag"),
        ("revol_util", "revol_util", "Revolving utilization in percentage points", "candidate", "candidate", "Keep values above 100; consider a high-utilization flag"),
        ("revol_bal", "revol_bal", "Reported revolving balance in USD", "candidate", "candidate", "Keep zero; consider training-only log1p for linear models"),
        ("open_acc", "open_acc", "Reported open credit-account count", "candidate", "candidate", "Preserve missing; fit imputation on training only if needed"),
        ("delinq_2yrs", "delinq_2yrs", "Reported delinquency count over the stated two-year window", "candidate", "candidate", "Keep zero distinct from missing"),
        ("pub_rec_bankruptcies", "pub_rec_bankruptcies", "Reported public-record bankruptcy count", "candidate", "candidate", "Keep zero distinct from missing"),
        ("emp_length_years", "emp_length", "Employment category converted to capped years", "candidate", "candidate", "0 is less than one year; 10 includes 10+; preserve missing"),
        ("fico_mid", "fico_range_low,fico_range_high", "Midpoint of the source origination FICO range", "candidate", "candidate", "Use original FICO bounds, never last_fico fields"),
        ("credit_history_years", "earliest_cr_line,issue_d", "Month-based credit-history length at issue", "candidate", "candidate", "Derived at issue; scoring before issue needs an as-of application date"),
        ("home_ownership", "home_ownership", "Reported home-ownership category", "candidate", "candidate", "Keep categories; training-only rare grouping and unknown handling"),
        ("purpose", "purpose", "Reported loan purpose", "candidate", "candidate", "Training-only rare grouping and unknown handling"),
        ("application_type", "application_type", "Individual or joint application category", "candidate", "candidate", "Joint group is small; co-applicant financial fields are not retained"),
    ]
    clean_dictionary = pd.DataFrame(_definitions, columns=["column", "source_fields", "meaning", "role", "initial_feature_decision", "reason_or_handling"])
    _schema = con.execute("DESCRIBE eda_loans").df()[["column_name", "column_type"]]
    clean_dictionary = clean_dictionary.merge(_schema, left_on="column", right_on="column_name", validate="one_to_one").drop(columns="column_name")
    clean_dictionary.to_csv(results_dir / "eda_clean_dictionary.csv", index=False)
    feature_decisions = clean_dictionary[["column", "initial_feature_decision", "reason_or_handling"]].copy()
    feature_decisions.to_csv(results_dir / "eda_feature_decisions.csv", index=False)

    with (root / "data/raw/accepted_2007_to_2018Q4.csv").open(newline="") as _stream:
        _source_columns = next(csv.reader(_stream))
    _missing = pd.read_csv(results_dir / "02_raw_missingness.csv").set_index("column_name")
    _source_to_clean = {}
    for _row in clean_dictionary.itertuples():
        for _source in _row.source_fields.split(","):
            _source_to_clean.setdefault(_source, []).append(_row)
    _outcomes = {
        "out_prncp", "out_prncp_inv", "total_pymnt", "total_pymnt_inv",
        "total_rec_prncp", "total_rec_int", "total_rec_late_fee", "recoveries",
        "collection_recovery_fee", "last_pymnt_d", "last_pymnt_amnt", "next_pymnt_d",
        "last_credit_pull_d", "last_fico_range_high", "last_fico_range_low",
        "pymnt_plan", "deferral_term", "payment_plan_start_date",
        "orig_projected_additional_accrued_interest", "disbursement_method",
    }
    _rows = []
    for _column in _source_columns:
        _used = _source_to_clean.get(_column, [])
        if _column == "loan_status":
            _role, _decision, _reason = "outcome", "exclude", "Snapshot outcome; used only to define labels"
        elif _column in _outcomes or _column.startswith(("hardship_", "settlement_", "debt_settlement_")):
            _role, _decision, _reason = "post_origination_or_workflow", "exclude", "Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline"
        elif _column == "member_id":
            _role, _decision, _reason = "identifier", "exclude", "Entirely missing identifier in this source snapshot"
        elif _column in {"url", "emp_title", "title", "desc", "zip_code"}:
            _role, _decision, _reason = "text_or_identifier", "exclude", "Identifier, free text, or detailed geography; outside the focused numeric/category baseline"
        elif _column in {"funded_amnt", "funded_amnt_inv", "initial_list_status", "policy_code"}:
            _role, _decision, _reason = "funding_or_policy_workflow", "exclude", "Funding/policy workflow field; not part of independent borrower features"
        elif _used:
            _candidate = any(_row.initial_feature_decision == "candidate" for _row in _used)
            _role = "candidate_source" if _candidate else _used[0].role
            _decision = "candidate_source" if _candidate else "exclude_as_predictor"
            _reason = "; ".join(dict.fromkeys(_row.reason_or_handling for _row in _used))
            if _column == "issue_d":
                _role, _decision = "split_and_derivation", "exclude_raw_predictor"
        else:
            _role, _decision, _reason = "not_selected_needs_source_review", "exclude", "Not retained in the focused clean table; meaning and as-of availability have not been source-certified"
        _rows.append({"source_column": _column, "role": _role, "initial_decision": _decision,
                      "clean_mapping": ", ".join(_row.column for _row in _used),
                      "raw_missing_count": int(_missing.loc[_column, "missing_count"]),
                      "raw_missing_pct": _missing.loc[_column, "missing_pct"], "reason": _reason})
    source_audit = pd.DataFrame(_rows)
    source_audit.to_csv(results_dir / "eda_source_column_audit.csv", index=False)
    _fig, _ax = plt.subplots(figsize=(11, 6))
    _roles = source_audit.role.value_counts().sort_values()
    _ax.barh(_roles.index, _roles.values)
    _ax.set(xlabel="Source columns", title="Every source column has an explicit initial disposition")
    mo.vstack([
        mo.md(f"""
        ## Feature and leakage decisions

        All **{len(source_audit)} source columns** and **{len(clean_dictionary)}
        clean columns** are accounted for. The initial shortlist contains
        **{int((feature_decisions.initial_feature_decision == 'candidate').sum())} candidates**.
        They still require a scoring-point availability check during implementation;
        these are proposals, not a fitted model's final feature count.

        The audit is a conservative project disposition, **not an official
        LendingClub data dictionary**. Unselected fields whose meaning/timing has
        not been source-certified remain excluded. Issue month is split metadata
        and contributes to credit-history derivation; it is not a direct predictor.
        Origination-derived credit history must be recomputed as of the application
        date for a genuinely pre-issue service.
        """),
        save_figure(_fig, "21_source_column_disposition"),
        mo.ui.table(clean_dictionary, selection=None),
        mo.ui.table(source_audit, selection=None),
    ])
    return clean_dictionary, feature_decisions, source_audit


@app.cell
def _(benchmark_splits, category_profile, clean_dictionary, cohort_audit, con, feature_decisions, full_numeric, outcome_numeric, source_audit, source_parsing, value_checks):
    _total, _resolved, _positive = con.execute("SELECT count(*), count(charged_off), sum(charged_off) FROM eda_loans").fetchone()
    assert (full_numeric.nonmissing + full_numeric.missing == _total).all()
    assert (source_parsing.development_rows == _total).all()
    assert (source_parsing.nonblank_source_values + source_parsing.missing_source_values == _total).all()
    assert int(source_parsing.parse_failures.sum()) == 0
    assert int(source_parsing.nonfinite_values.sum()) == 0
    assert int(value_checks.affected_loans.sum()) == 0
    assert (category_profile.groupby("feature").total_loans.sum() == _total).all()
    for _label, _count in [(0, _resolved - _positive), (1, _positive)]:
        _rows = outcome_numeric[outcome_numeric.charged_off == _label]
        assert (_rows.nonmissing + _rows.missing == _count).all()
    assert int(cohort_audit.all_loans.sum()) == _total
    assert (benchmark_splits.fully_paid + benchmark_splits.charged_off == benchmark_splits.eligible_resolved_loans).all()
    assert (benchmark_splits.all_loans - benchmark_splits.excluded_other_status == benchmark_splits.eligible_resolved_loans).all()
    assert len(source_audit) == source_audit.source_column.nunique() == 151
    assert len(clean_dictionary) == clean_dictionary.column.nunique() == 26
    assert len(full_numeric) == 14
    assert len(source_parsing) == 16
    assert int((feature_decisions.initial_feature_decision == "candidate").sum()) == 14
    completion_checks_passed = True
    return (completion_checks_passed,)


@app.cell
def _(benchmark_splits, category_profile, clean_dictionary, completion_checks_passed, datetime, feature_decisions, full_numeric, json, markdown_table, mo, pd, results_dir, root, source_audit, source_parsing, timezone, value_checks):
    _existing_numeric = pd.read_csv(results_dir / "06_numeric_summary.csv").set_index("feature")
    _employment = pd.read_csv(results_dir / "16_missingness_outcomes.csv")
    _employment = _employment[_employment.feature == "emp_length_years"].set_index("value_group")
    _tail = pd.read_csv(results_dir / "14_tail_investigation.csv")
    _tail = _tail[_tail.value_group == "flagged"].set_index("check_name")
    _rare = category_profile[category_profile.rare_in_development]
    _candidate_names = feature_decisions.loc[feature_decisions.initial_feature_decision == "candidate", "column"].tolist()
    completion_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    final_report = f"""# LendingClub EDA: final report and decisions

Completed: {completion_time}. Scope: exploratory data analysis and its handoff to
model preparation. No models, MLflow experiments, InterpretML evaluations, Kafka
benchmarks, or ELK performance measurements have been run.

## Population and evidence

The source has 2,260,701 rows and 151 columns. Cleaning removed 33 rows with
unusable loan IDs/issue dates, leaving 2,260,668 unique loan IDs and 26 columns.
Detailed analysis uses 887,440 loans issued through 2015. Counts are loans, not
unique borrowers. Rejected applications are outside this dataset.

The completed EDA consists of three marimo notebooks, SQL files 00–25, saved CSV
tables, and 21 figure sets (PNG and SVG). The first report covers missingness,
numeric/category distributions, outcomes, correlations, and cohort coverage.
The second covers tails, missingness patterns, affordability, interactions, and
changing borrower mix. The final pass audits all source/clean fields, completes
descriptive moments and category support, compares outcome distributions, checks
16 source conversions and 15 value rules, and fixes the first benchmark definition.

## Findings that matter

- Ordinary resolved development loans: 826,604, including 152,302 charged off
  (18.425026%). This is a conditional observed share, not a model score or
  fixed-horizon default probability.
- Development income median: ${_existing_numeric.loc['annual_inc', 'median']:,.0f};
  p99: ${_existing_numeric.loc['annual_inc', 'p99']:,.0f}; maximum:
  ${_existing_numeric.loc['annual_inc', 'maximum']:,.0f}. Means and correlations
  need to be read with the heavy tail in mind.
- {_tail.loc['income_above_1m', 'loans']:,.0f} loans have income above $1 million;
  {_tail.loc['dti_above_100', 'loans']:,.0f} have DTI above 100 (including one at
  exactly 999); {_tail.loc['utilization_above_100', 'loans']:,.0f} have utilization
  above 100%. These are investigation flags, not proven errors.
- Missing employment has {_employment.loc['missing', 'charged_off_pct']:.2f}%
  charged off among {_employment.loc['missing', 'resolved_loans']:,.0f} resolved
  loans, versus {_employment.loc['present', 'charged_off_pct']:.2f}% among
  {_employment.loc['present', 'resolved_loans']:,.0f} with employment present.
  This is an unadjusted association, not evidence of causation or random missingness.
- Within 320,563 resolved 36-month loans from 2011–2014, the FICO/DTI grid shows
  increasing observed charged-off shares across higher DTI bands within each
  displayed FICO band. Even within this narrower population, confounding remains.
- {len(_rare)} category labels across the seven profiled fields have fewer than
  200 development loans. Keep their counts visible; do not trust tiny-group rates.
- Borrower and loan mix changes over time. Term, credit score, DTI, and amount
  comparisons must be read alongside cohort composition and outcome coverage.
- Only 11.4% of 2018 loans have ordinary resolved outcomes. The initial plan to
  use 2017–2018 for this resolved-loan evaluation is superseded below.

## Final cleaning and preprocessing decisions

The raw CSV and existing clean Parquet are preserved. The existing rules stand:
nonpositive income, negative DTI/utilization, and impossible credit-history dates
become missing. Numeric parsing and value-range checks now complete without
failures on the development population; they do not establish that every source
observation is economically correct.

1. Keep high but parseable income, DTI, and utilization values. Do not automatically
   recode 999 as missing without a source definition. Keep investigation flags
   available for later sensitivity analysis. Overlapping flags are not additive.
2. Preserve missingness in the analysis table. For a future linear baseline, fit
   numeric median imputation and missingness indicators on training rows only.
   Models supporting missing values can retain them. Missing is not zero.
3. Consider log1p for nonnegative income/balance inputs in a linear baseline;
   do not fit transformations or caps to validation/test data. No scaler,
   imputer, clipping threshold, or rare-category encoder has been fitted here.
4. Preserve all source category labels in EDA. Future grouping/encoding must
   learn its vocabulary on training data, preserve missingness explicitly, and
   handle unseen categories. The exploratory 200-loan flag is not an encoder.
5. Employment is capped: 0 means under one year and 10 includes 10+ years.
   Treating those as exact durations would be misleading.

## Prediction-time feature decision

Initial candidates ({len(_candidate_names)}): {', '.join(f'`{name}`' for name in _candidate_names)}.

This shortlist assumes the values are available from the application and its
initial credit report at the chosen scoring point. The accepted-loan principal
must be checked against the requested principal used by a real application.
Credit history is currently measured at issue month, so a pre-issue service must
recompute it using an application-time reference date. Availability must be
verified in the serving contract; the offline file does not prove an exact event time.

Exclude IDs and outcome fields; use issue date/year only for split/monitoring.
Exclude assigned grade, subgrade, interest rate, and installment from the initial
independent-risk baseline. They may be assessed later in a clearly labeled
post-underwriting ablation. Exclude verification status until its workflow timing
is established, and state from the initial shortlist. A 36-month-only benchmark
does not need term as a predictor. Application type may be constant in an early
training window; inspect training-only cardinality during model preparation.
Co-applicant financial details are not in the focused table, limiting joint-loan
interpretation. No protected-group fairness conclusion is supported by this EDA.

The source audit is a project disposition, not an official source dictionary.
Unselected fields without source-certified meaning/timing are explicitly excluded;
there is no implicit permission to add them to a model.

## Target, cohort, and split decision

Use ordinary Fully Paid versus Charged Off outcomes for **36-month loans issued
in 2011–2015**. This is a retrospective resolved-loan classification benchmark.
Its target is charged off among the selected resolved loans; all other statuses
are excluded from this benchmark, not labeled as fully paid. The literal status
`Default` and historical policy-exception statuses remain outside this label.

{markdown_table(benchmark_splits)}

Train: 2011–2013; validation: 2014; exploratory evaluation: 2015. These counts
include the eligibility filter but no additional model-preparation exclusions.
No ready-to-train split files have been written. The all-loan 2016/2017–2018
counts in earlier snapshot tables remain historical proposals, not this decision.

The benchmark is **not** a 12-/36-month default-probability estimate, a pristine
holdout evaluation, or a historical deployment simulation. EDA already inspected
the proposed years, and training-loan labels in the snapshot were not necessarily
available before the later issue years. A common outcome cutoff, event timestamps,
and label availability must be established before a production or fixed-horizon
claim. High resolved coverage reduces one visible limitation but does not prove
absence of selection bias or equal follow-up.

## What is complete and what is not

EDA is complete for this focused project scope: row/key audits, parsing checks,
missingness, cleaning decisions, univariate/bivariate/multivariate exploration,
tail and rare-group review, outcome coverage, feature disposition, and a bounded
benchmark definition. No p-values, confidence intervals, causal estimates, protected
demographic fairness claims, model metrics, or serving/stress-test metrics were
calculated. The source snapshot/version and observation-cutoff limitations remain
documented rather than inferred away.

Next implementation work is model-data preparation and MLflow experiments, not
more EDA. Fit all learned preprocessing on training rows, choose models and policy
thresholds using validation, and report the 2015 evaluation with its exploratory
status. Actual deployment claims need a separate point-in-time dataset design.

## Evidence and reproduction

- [Initial EDA](data_analysis.html), [follow-up EDA](deeper_eda.html), and
  [final notebook report](eda_completion.html).
- [Statistics reference](../assets/statistics.md), including complete tables in section 16.
- [Source-column audit](../assets/results/eda_source_column_audit.csv),
  [clean dictionary](../assets/results/eda_clean_dictionary.csv), and
  [feature decisions](../assets/results/eda_feature_decisions.csv).
- [Numeric profile](../assets/results/20_complete_numeric_profile.csv),
  [category profile](../assets/results/21_complete_category_profile.csv),
  [outcome distributions](../assets/results/22_numeric_by_outcome.csv),
  [cohort audit](../assets/results/23_final_cohort_audit.csv),
  [value checks](../assets/results/24_clean_value_checks.csv), and
  [source conversion checks](../assets/results/25_numeric_source_parsing.csv).

Run `marimo edit scripts/03_complete_eda.py` from the project root. Export with
`marimo export html scripts/03_complete_eda.py -o docs/eda_completion.html --no-include-code`.
The final notebook refreshes its reports/statistics and does not change clean data.
"""
    (root / "docs/eda_summary.md").write_text(final_report)
    _dictionary_report = "# Focused clean-table dictionary\n\nProject meanings and initial feature dispositions; not a source-certified dictionary.\n\n" + markdown_table(clean_dictionary) + "\n"
    (root / "docs/data_dictionary.md").write_text(_dictionary_report)
    _manifest = {"stage": "eda", "status": "complete", "completed_at_utc": completion_time,
                 "source_columns": len(source_audit), "clean_columns": len(clean_dictionary),
                 "candidate_feature_count": len(_candidate_names), "candidate_features": _candidate_names,
                 "target": "charged_off_among_selected_resolved_loans", "fixed_horizon": False,
                 "benchmark_term_months": 36, "train_years": [2011, 2012, 2013],
                 "validation_years": [2014], "exploratory_test_years": [2015],
                 "test_previously_explored": True, "deployment_backtest": False,
                 "checks_passed": completion_checks_passed, "model_training_started": False,
                 "splits": benchmark_splits.to_dict(orient="records")}
    (results_dir / "eda_completion_manifest.json").write_text(json.dumps(_manifest, indent=2) + "\n")
    mo.md(final_report)
    return completion_time, final_report


@app.cell
def _(benchmark_splits, category_profile, clean_dictionary, cohort_audit, completion_time, feature_decisions, figures_dir, full_numeric, hashlib, markdown_table, mo, outcome_numeric, re, results_dir, root, source_audit, source_parsing, value_checks, final_report):
    _tables = [
        ("20_complete_numeric_profile", full_numeric), ("21_complete_category_profile", category_profile),
        ("22_numeric_by_outcome", outcome_numeric), ("23_final_cohort_audit", cohort_audit),
        ("24_clean_value_checks", value_checks), ("25_numeric_source_parsing", source_parsing),
        ("eda_benchmark_splits", benchmark_splits), ("eda_clean_dictionary", clean_dictionary),
        ("eda_feature_decisions", feature_decisions), ("eda_source_column_audit", source_audit),
    ]
    _marker = "<!-- final-eda-statistics -->"
    _path = root / "assets/statistics.md"
    _existing = _path.read_text()
    _model_marker = "<!-- model-data-statistics -->"
    _model_section = ""
    if _model_marker in _existing:
        _model_section = _model_marker + _existing.split(_model_marker, 1)[1]
    _original = _existing.split(_marker)[0].rstrip()
    if not _model_section:
        _original = re.sub(r"\| Completed stage \| [^\n]+ \|", "| Completed stage | EDA complete: audits, exploration, feature decisions, and benchmark definition |", _original)
    _original = re.sub(r"\| Saved figure sets \| [\d,]+ \|", f"| Saved figure sets | {len(list(figures_dir.glob('*.png')))} |", _original)
    _original = re.sub(r"\| Saved image files \| [\d,]+ \|", f"| Saved image files | {len(list(figures_dir.glob('*.png'))) + len(list(figures_dir.glob('*.svg')))} |", _original)
    _original = re.sub(r"\| Saved result CSVs \| [\d,]+ \|", f"| Saved result CSVs | {len(list(results_dir.glob('*.csv')))} |", _original)
    _original = _original.replace("16. [EDA completion](#16-eda-completion)\n", "")
    _original = _original.replace("15. [Follow-up EDA](#15-follow-up-eda)", "15. [Follow-up EDA](#15-follow-up-eda)\n16. [EDA completion](#16-eda-completion)")
    _notice = "> EDA is complete. The final cohort, feature, and preprocessing decisions are in section 16 and docs/eda_summary.md. Earlier split proposals remain historical snapshot records. No models or stress tests have been run."
    if _notice not in _original:
        _original = _original.replace("# Project statistics reference\n", "# Project statistics reference\n\n" + _notice + "\n", 1)
    _parts = [_marker, "## 16. EDA completion", f"Completed: {completion_time}.",
              "Final decisions: [EDA summary](../docs/eda_summary.md); [clean dictionary](../docs/data_dictionary.md); [HTML report](../docs/eda_completion.html). The original source and clean data are unchanged.",
              "### Final benchmark and interpretation",
              "36-month loans issued in 2011–2015 with exact Fully Paid / Charged Off status. Train 2011–2013, validation 2014, exploratory evaluation 2015. This supersedes the original 2016 / 2017–2018 proposal. EDA previously inspected these years. No fixed prediction horizon, deployment backtest, or pristine holdout claim is made.",
              "### Verification",
              "All 151 source and 26 clean columns accounted for; 14 candidate features recorded. All numeric/category/outcome and cohort totals reconcile. Sixteen source conversions have zero parse/nonfinite failures on valid development rows; all 15 clean-value checks pass. None of this certifies the economic meaning of extremes or source timing.",
              "### Complete final-stage tables",
              "All ten new result CSVs are transcribed below. Counts are exact; displayed noninteger values are rounded to six places. Numeric moments exclude NULLs. Category percentages use all development loans; outcome percentages use ordinary resolved loans. Dictionary dispositions are project judgments, not an official source dictionary."]
    for _name, _frame in _tables:
        _csv_path = results_dir / f"{_name}.csv"
        _parts.extend([f"#### {_name}",
                       f"Source: [{_name}.csv](results/{_name}.csv). Records: {len(_frame)}. SHA-256: `{hashlib.sha256(_csv_path.read_bytes()).hexdigest()}`.",
                       markdown_table(_frame)])
    _parts.append("### Final-stage figures")
    for _name in ["18_outcome_boxplots", "19_category_support", "20_benchmark_coverage", "21_source_column_disposition"]:
        _parts.append(f"- [{_name}.png](figures/{_name}.png) · [{_name}.svg](figures/{_name}.svg)")
    _path.write_text(_original + "\n\n" + "\n\n".join(_parts) + "\n\n" + _model_section)
    mo.md("EDA complete. Saved the final report, dictionaries, benchmark counts, four figures, ten result CSVs, and full statistics in section 16.")
    return


if __name__ == "__main__":
    app.run()
