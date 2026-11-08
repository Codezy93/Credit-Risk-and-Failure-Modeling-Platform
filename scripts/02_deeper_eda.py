import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from datetime import datetime, timezone
    import hashlib
    from pathlib import Path

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    return Path, datetime, duckdb, hashlib, mo, pd, plt, sns, timezone


@app.cell
def _(mo):
    mo.md("""
    # LendingClub: following up on the first EDA

    The first pass raised a few questions: why are some DTI and utilization
    values so large, does missing employment information matter, and do pooled
    relationships survive a closer look at borrower mix?

    This notebook reads the existing clean Parquet file. All six SQL queries
    use **development originations through 2015**. The credit-score/DTI comparison
    narrows this further to **36-month loans issued in 2011–2014**, with coverage
    reported explicitly. No training, data deletion, or feature imputation happens here.
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
    con.execute("""
        CREATE VIEW eda_loans AS
        SELECT * FROM read_parquet(getvariable('clean_path')) WHERE issue_year <= 2015
    """)
    sns.set_theme(style="whitegrid", palette="colorblind")
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})

    def query(filename):
        result = con.execute((root / "sql" / filename).read_text()).df()
        result.to_csv(results_dir / (Path(filename).stem + ".csv"), index=False)
        return result

    def save_figure(figure, name):
        figure.tight_layout()
        figure.savefig(figures_dir / f"{name}.png", dpi=160, bbox_inches="tight")
        figure.savefig(figures_dir / f"{name}.svg", bbox_inches="tight")
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
                    values.append(str(value).replace("|", "\\|"))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    return con, figures_dir, markdown_table, query, results_dir, root, save_figure


@app.cell
def _(mo, plt, query, save_figure):
    tail_checks = query("14_tail_investigation.sql")
    _flagged = tail_checks[tail_checks.value_group == "flagged"].set_index("check_name")
    _not_flagged = tail_checks[tail_checks.value_group == "not_flagged"].set_index("check_name")
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))
    _positions = list(range(len(_flagged)))
    _axes[0].barh(_positions, _flagged.loans)
    _axes[0].set_yticks(_positions, _flagged.index)
    _axes[0].set(xlabel="Flagged loans (log scale)", xscale="log", title="How many loans are in each tail?")
    for _i, _row in enumerate(_flagged.itertuples()):
        _axes[0].text(_row.loans * 1.1, _i, f"{_row.loans:,}", va="center")
    _axes[0].set_xlim(right=max(_flagged.loans) * 3)
    _axes[1].scatter(_not_flagged.loc[_flagged.index, "charged_off_pct"], _positions, label="Not flagged", marker="o")
    _supported = _flagged[_flagged.resolved_loans >= 200]
    _axes[1].scatter(_supported.charged_off_pct, [_flagged.index.get_loc(_index) for _index in _supported.index], label="Flagged (n ≥ 200 resolved)", marker="D")
    _axes[1].set_yticks(_positions, _flagged.index)
    _axes[1].set(xlabel="Charged off among resolved (%)", title="Tail comparisons with denominator checks")
    _axes[1].legend(loc="best", fontsize=8)
    mo.vstack([
        mo.md("""
        ## 1. Investigate extremes before deciding what to remove

        An income above the development p99, income above $1 million, DTI above
        100, DTI exactly 999, and utilization above 100% are diagnostic flags.
        The checks overlap; summing their counts would double-count loans.
        `dti_equals_999` is an equality check, not an above-threshold check.

        A high utilization can reflect over-limit borrowing, while 999 may be
        a source-specific code. This dataset alone does not establish the cause.
        I keep the records and show their counts and outcomes. Tiny groups do not
        receive a plotted outcome rate; every group remains in the table.
        """),
        save_figure(_fig, "12_tail_investigation"),
        mo.ui.table(tail_checks.round(4), selection=None),
    ])
    return (tail_checks,)


@app.cell
def _(mo, plt, query, save_figure, sns):
    missing_by_year = query("15_missingness_by_year.sql")
    _matrix = missing_by_year.pivot(index="feature", columns="issue_year", values="missing_pct")
    _fig, _ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(_matrix, annot=True, fmt=".2f", cmap="Blues", vmin=0, ax=_ax, cbar_kws={"label": "Missing (%)"})
    _ax.set(title="Missingness varies across development cohorts", xlabel="Issue year", ylabel="")
    mo.vstack([
        mo.md("""
        ## 2. Is missingness a stable property of a feature?

        A pooled missing percentage hides changes in data collection. These are
        percentages within each year after the existing cleaning rules; they mix
        original blanks with values that cleaning converted to NULL. A field that
        is often absent in early cohorts may behave differently in later ones.
        No missing values are filled here.
        """),
        save_figure(_fig, "13_missingness_by_year"),
        mo.ui.table(missing_by_year.round(4), selection=None),
    ])
    return (missing_by_year,)


@app.cell
def _(mo, plt, query, save_figure):
    missing_outcomes = query("16_missingness_outcomes.sql")
    _fig, _axes = plt.subplots(1, 2, figsize=(13, 5))
    for _ax, _column, _title in zip(_axes, ["charged_off_pct", "resolved_pct"], ["Charged off among resolved (%)", "Outcome coverage (%)"]):
        _pivot = missing_outcomes.pivot(index="feature", columns="value_group", values=_column)
        if _column == "charged_off_pct":
            _counts = missing_outcomes.pivot(index="feature", columns="value_group", values="resolved_loans")
            _pivot = _pivot.where(_counts >= 200)
        _pivot.plot.barh(ax=_ax)
        _ax.set(xlabel=_title, ylabel="", title=_title)
        _ax.legend(title="Feature value")
    mo.vstack([
        mo.md("""
        ## 3. Missing is a group worth examining

        Compare missing and present values using both the observed outcome rate
        and label coverage. Rate bars require 200 resolved loans; absent bars can
        mean insufficient support, not a zero rate. Missingness may reflect
        cohort, application, or reporting differences. These plots cannot establish
        that the information is missing at random or that missingness causes default.
        """),
        save_figure(_fig, "14_missingness_outcomes"),
        mo.ui.table(missing_outcomes.round(4), selection=None),
    ])
    return (missing_outcomes,)


@app.cell
def _(mo, plt, query, save_figure):
    affordability = query("17_affordability.sql")
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))
    for _ax, (_metric, _group) in zip(_axes, affordability.groupby("metric", sort=True)):
        _group = _group.sort_values("band_order")
        _rates = _group.charged_off_pct.where(_group.resolved_loans >= 200)
        _ax.bar(_group.ratio_band, _rates)
        for _i, _row in enumerate(_group.itertuples()):
            if _row.resolved_loans >= 200:
                _ax.text(_i, _row.charged_off_pct + 0.5, f"n={_row.resolved_loans:,}", ha="center", rotation=35, fontsize=8)
        _ax.set(title=_metric.replace("_", " "), xlabel="Ratio band", ylabel="Charged off among resolved (%)", ylim=(0, _rates.max() + 9))
        _ax.tick_params(axis="x", rotation=30)
    mo.vstack([
        mo.md("""
        ## 4. Put loan size in the context of income

        A $20,000 loan means something different at different income levels.
        Principal-to-income is `loan_amnt / annual_inc`; installment burden is
        `12 × installment / annual_inc`, the scheduled payment on this loan divided
        by stated monthly income. It does not represent all household expenses or
        all existing debt payments. These are different ratios, even though they
        use the same display bands.

        Installment reflects approved pricing and term, so this is descriptive
        EDA rather than a decision to use it for pre-pricing prediction. Missing
        income gets its own group. Rate bars need 200 resolved loans. Unusual
        ratios are retained and the maximum is included in the table.
        """),
        save_figure(_fig, "15_affordability_outcomes"),
        mo.ui.table(affordability.round(4), selection=None),
    ])
    return (affordability,)


@app.cell
def _(mo, plt, query, save_figure, sns):
    fico_dti = query("18_fico_dti_interaction.sql")
    _fico_order = fico_dti.sort_values("fico_order").fico_band.drop_duplicates()
    _dti_order = fico_dti.sort_values("dti_order").dti_band.drop_duplicates()
    _rates = fico_dti.pivot(index="fico_band", columns="dti_band", values="charged_off_pct").reindex(index=_fico_order, columns=_dti_order)
    _counts = fico_dti.pivot(index="fico_band", columns="dti_band", values="resolved_loans").reindex(index=_fico_order, columns=_dti_order)
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.heatmap(_rates.where(_counts >= 200), annot=True, fmt=".1f", cmap="YlOrRd", ax=_axes[0], cbar_kws={"label": "Charged off among resolved (%)"})
    sns.heatmap(_counts, annot=True, fmt=",.0f", cmap="Blues", ax=_axes[1], cbar=False)
    _axes[0].set_title("2011–2014, 36-month loans: FICO × DTI")
    _axes[1].set_title("Resolved loans supporting each comparison")
    for _ax in _axes:
        _ax.set(xlabel="DTI band", ylabel="Origination FICO midpoint band")
    _total = int(fico_dti.total_loans.sum())
    _resolved = int(fico_dti.resolved_loans.sum())
    mo.vstack([
        mo.md(f"""
        ## 5. Look at debt burden within credit-score bands

        This comparison uses **{_total:,} loans**, of which **{_resolved:,}**
        (**{100 * _resolved / _total:.2f}%**) have ordinary resolved outcomes.
        Holding loan term constant and narrowing the issue window reduces some
        follow-up differences. It does not control for every borrower or cohort
        difference. Read along each FICO row, then down a DTI column.
        Cells need at least 200 resolved loans for a displayed rate.
        """),
        save_figure(_fig, "16_fico_dti_interaction"),
        mo.ui.table(fico_dti.round(4), selection=None),
    ])
    return (fico_dti,)


@app.cell
def _(mo, plt, query, save_figure):
    composition = query("19_development_composition.sql")
    _fig, _axes = plt.subplots(2, 2, figsize=(13, 8))
    for _column in ["term_60_pct", "grade_ab_pct"]:
        _axes[0, 0].plot(composition.issue_year, composition[_column], marker="o", label=_column)
    _axes[0, 0].set(ylabel="Share of loans (%)", title="Loan mix changes over time")
    _axes[0, 0].legend()
    _axes[0, 1].plot(composition.issue_year, composition.median_loan_amnt, marker="o")
    _axes[0, 1].set(ylabel="Median principal ($)", title="Typical loan size")
    _axes[1, 0].plot(composition.issue_year, composition.median_fico, marker="o")
    _axes[1, 0].set(ylabel="Median origination FICO midpoint", title="Borrower credit profile")
    _axes[1, 1].plot(composition.issue_year, composition.median_dti, marker="o")
    _axes[1, 1].set(ylabel="Median DTI", title="Borrower debt burden")
    for _ax in _axes.flat:
        _ax.set_xlabel("Issue year")
    mo.vstack([
        mo.md("""
        ## 6. Check whether the population is staying the same

        Loan term, grade mix, principal, and borrower profiles can move together
        across years. That makes a pooled outcome comparison harder to interpret.
        Medians exclude missing numeric values; term and grade shares use all
        development loans within each year. These are descriptive cohort changes,
        not a fitted production drift detector or a causal explanation.
        """),
        save_figure(_fig, "17_development_composition"),
        mo.ui.table(composition.round(4), selection=None),
    ])
    return (composition,)


@app.cell
def _(affordability, composition, con, fico_dti, missing_by_year, missing_outcomes, tail_checks):
    _total, _resolved, _charged = con.execute("""
        SELECT count(*), count(charged_off), sum(charged_off) FROM eda_loans
    """).fetchone()
    assert int(composition.total_loans.sum()) == _total
    for _frame, _group, _count in [
        (tail_checks, "check_name", "loans"),
        (missing_by_year, "feature", "total_loans"),
        (missing_outcomes, "feature", "total_loans"),
        (affordability, "metric", "total_loans"),
    ]:
        assert (_frame.groupby(_group)[_count].sum() == _total).all()
    for _frame, _group in [
        (tail_checks, "check_name"),
        (missing_outcomes, "feature"),
        (affordability, "metric"),
    ]:
        assert (_frame.groupby(_group).resolved_loans.sum() == _resolved).all()
        assert (_frame.groupby(_group).charged_off_loans.sum() == _charged).all()
    _expected_grid = con.execute("""
        SELECT count(*), count(charged_off), sum(charged_off)
        FROM eda_loans WHERE issue_year BETWEEN 2011 AND 2014 AND term_months = 36
    """).fetchone()
    assert tuple(int(fico_dti[_column].sum()) for _column in ["total_loans", "resolved_loans", "charged_off_loans"]) == _expected_grid
    eda_checks_passed = True
    return (eda_checks_passed,)


@app.cell
def _(affordability, composition, eda_checks_passed, fico_dti, missing_by_year, missing_outcomes, mo, results_dir, tail_checks):
    _flags = tail_checks[tail_checks.value_group == "flagged"].set_index("check_name")
    _employment = missing_outcomes[missing_outcomes.feature == "emp_length_years"].set_index("value_group")
    _first = composition.iloc[0]
    _last = composition.iloc[-1]
    deeper_findings = f"""# Follow-up EDA findings

## Scope

All analyses use clean development loans issued through 2015. The FICO/DTI grid
uses 36-month loans issued in 2011–2014. No model training or cleaning changes were made.

## What the follow-up found

- Annual income above the development p99: {int(_flags.loc['income_above_p99', 'loans']):,} loans; above $1 million: {int(_flags.loc['income_above_1m', 'loans']):,}.
- DTI above 100: {int(_flags.loc['dti_above_100', 'loans']):,} loans; exactly 999: {int(_flags.loc['dti_equals_999', 'loans']):,}. These counts overlap.
- Revolving utilization above 100%: {int(_flags.loc['utilization_above_100', 'loans']):,} loans. These flags do not prove data errors, so records are retained.
- Missing employment length: {int(_employment.loc['missing', 'total_loans']):,} loans, with {_employment.loc['missing', 'charged_off_pct']:.2f}% charged off among {_employment.loc['missing', 'resolved_loans']:,.0f} resolved loans. Present employment: {_employment.loc['present', 'charged_off_pct']:.2f}% among {_employment.loc['present', 'resolved_loans']:,.0f} resolved loans. These are unadjusted associations.
- The FICO/DTI grid covers {int(fico_dti.total_loans.sum()):,} loans with {100 * fico_dti.resolved_loans.sum() / fico_dti.total_loans.sum():.2f}% ordinary outcome coverage. Its smaller population must not be confused with the full 887,440-loan development sample.
- Between {int(_first.issue_year)} and {int(_last.issue_year)}, median principal changed from ${_first.median_loan_amnt:,.0f} to ${_last.median_loan_amnt:,.0f}; the 60-month share changed from {_first.term_60_pct:.2f}% to {_last.term_60_pct:.2f}%. Borrower/loan mix is not constant over time.

## How to read the outputs

Missingness percentages are after cleaning and use each issue year's total loans.
Outcome rates use ordinary Fully Paid / Charged Off loans only. Missingness,
affordability, and interaction rate plots require at least 200 resolved loans per
displayed group; the complete CSV tables retain smaller groups. The tail comparison
suppresses flagged-group rates below 200 resolved loans. No confidence intervals
or causal estimates were calculated. The income p99 is an exploratory development
cutoff, not a future training-time preprocessing rule.

Principal-to-income and installment-to-income are distinct ratios. Installment is
post-pricing information. Neither ratio measures all living costs or total household
debt service. Missing income is shown as its own group rather than filled with zero.

No extreme values were deleted, no new predictor set was selected, and no claim
about protected-group fairness or model performance follows from these charts.

## Verification

Group totals reconcile to the development population. Tail, missingness, and
affordability outcome counts reconcile to the full development label counts.
The FICO/DTI grid reconciles independently to its narrower SQL population.
"""
    (results_dir / "deeper_eda_findings.md").write_text(deeper_findings)
    mo.md(deeper_findings)
    return (deeper_findings,)


@app.cell
def _(affordability, composition, datetime, deeper_findings, fico_dti, figures_dir, hashlib, markdown_table, missing_by_year, missing_outcomes, mo, results_dir, root, tail_checks, timezone):
    _tables = [
        ("14_tail_investigation", "Diagnostic tail groups", tail_checks),
        ("15_missingness_by_year", "Missingness by development year", missing_by_year),
        ("16_missingness_outcomes", "Missing versus present: outcomes and coverage", missing_outcomes),
        ("17_affordability", "Affordability ratios and outcome bands", affordability),
        ("18_fico_dti_interaction", "FICO and DTI: 2011–2014, 36-month loans", fico_dti),
        ("19_development_composition", "Development cohort composition", composition),
    ]
    _marker = "<!-- deeper-eda-statistics -->"
    _stats_path = root / "assets/statistics.md"
    _original = _stats_path.read_text().split(_marker)[0].rstrip()
    _image_count = len(list(figures_dir.glob("*.png"))) + len(list(figures_dir.glob("*.svg")))
    _csv_count = len(list(results_dir.glob("*.csv")))
    _original = _original.replace("| Saved figure sets | 11 |", f"| Saved figure sets | {_image_count // 2} |")
    _original = _original.replace("| Saved image files | 22 |", f"| Saved image files | {_image_count} |")
    _original = _original.replace("| Saved result CSVs | 15 |", f"| Saved result CSVs | {_csv_count} |")
    _original = _original.replace("All **15 existing result CSVs**", "All **15 original result CSVs**")
    _original = _original.replace("15. [Follow-up EDA](#15-follow-up-eda)\n", "")
    _original = _original.replace("14. [Source fingerprints and update rules](#14-source-fingerprints-and-update-rules)", "14. [Source fingerprints and update rules](#14-source-fingerprints-and-update-rules)\n15. [Follow-up EDA](#15-follow-up-eda)")
    _parts = [
        _marker,
        "## 15. Follow-up EDA",
        f"Updated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}. The original statistics and artifact inventory in sections 2–14 describe the first EDA snapshot. Quick-answer artifact counts include this follow-up. No model or stress-test measurements have been added.",
        "Source: [second marimo notebook](../scripts/02_deeper_eda.py), [HTML report](../docs/deeper_eda.html). It reads the existing clean Parquet; it does not repeat raw-data cleaning.",
        deeper_findings.replace("# Follow-up EDA findings", "### Follow-up interpretation").replace("\n## ", "\n#### "),
        "### Complete follow-up result tables",
        "All six new CSVs are transcribed below. Counts are integers; display rounding is at most six decimal places. Percentages use the denominators stated above. No group is omitted from these tables.",
    ]
    for _name, _title, _frame in _tables:
        _csv_path = results_dir / f"{_name}.csv"
        _parts.extend([
            f"#### {_title}",
            f"Source: [{_name}.csv](results/{_name}.csv). Records: {len(_frame)}. SHA-256: `{hashlib.sha256(_csv_path.read_bytes()).hexdigest()}`.",
            markdown_table(_frame),
        ])
    _parts.append("### Follow-up figure inventory")
    for _name in ["12_tail_investigation", "13_missingness_by_year", "14_missingness_outcomes", "15_affordability_outcomes", "16_fico_dti_interaction", "17_development_composition"]:
        _parts.append(f"- [{_name}.png](figures/{_name}.png) · [{_name}.svg](figures/{_name}.svg)")
    _parts.append("### Snapshot maintenance\n\nThis follow-up section is refreshed when the second notebook runs. The original sections retain their first-stage provenance; model and stress-test sections remain Not measured. The clean data is unchanged.")
    _stats_path.write_text(_original + "\n\n" + "\n\n".join(_parts) + "\n")
    mo.md("Saved six result CSVs, six PNG/SVG figures, the follow-up findings, and the detailed tables in section 15 of `assets/statistics.md`.")
    return


if __name__ == "__main__":
    app.run()
