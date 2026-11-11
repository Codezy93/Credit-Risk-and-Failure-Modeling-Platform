import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    return Path, duckdb, mo, pd, plt, sns


@app.cell
def _(mo):
    mo.md("""
    # LendingClub: getting to know the loans

    Before fitting a model, I want to know what a row represents, which fields
    are usable at prediction time, and how much of the outcome we actually see.
    This notebook runs the SQL files in `sql/`; Python only displays the query
    results and draws the figures. Every query result is saved as a CSV.

    **Scope:** accepted loans only. This dataset cannot tell us the outcomes of
    rejected applications or justify claims about all applicants.

    Detailed feature and outcome exploration uses **2007–2015** originations.
    We inspect later years only for status coverage. The final modelling benchmark
    uses resolved 36-month loans: **2011–2013** for training, **2014** for validation,
    and the already-explored **2015** cohort for exploratory evaluation. Earlier
    split proposals in historical EDA tables were superseded by that decision.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## How to interpret the risk outputs

    **Lifetime charge-off probability (resolved 36-month cohort)** is the
    classification target: Charged Off = 1; Fully Paid = 0. Other statuses are
    excluded. This is not a 12-month forecast or a Basel default probability.
    EAD and LGD are retrospective snapshot proxies. Their product with the
    classifier score is a lifetime snapshot-loss proxy, not regulatory one-year EL.
    Capital/RWA panels use separately assumed one-year PDs, not classifier scores.
    The classifier is not annualised. Legacy `pd`/`basel` identifiers are retained
    for compatibility; historical result tables preserve their execution-time names.
    """)
    return


@app.cell
def _(Path, duckdb, mo, plt, sns):
    root = Path(__file__).resolve().parents[1]
    sql_dir = root / "sql"
    results_dir = root / "assets" / "results"
    figures_dir = root / "assets" / "figures"
    clean_dir = root / "data" / "clean"
    for _folder in [results_dir, figures_dir, clean_dir]:
        _folder.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(clean_dir / "lending_club.duckdb"))
    con.execute("SET memory_limit = '1GB'")
    con.execute("SET threads = 4")
    con.execute("SET VARIABLE raw_path = ?", [str(root / "data/raw/accepted_2007_to_2018Q4.csv")])
    sns.set_theme(style="whitegrid", context="notebook", palette="colorblind")
    plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})

    def query(filename):
        result = con.execute((sql_dir / filename).read_text()).df()
        result.to_csv(results_dir / (Path(filename).stem + ".csv"), index=False)
        return result

    def save_figure(figure, name):
        figure.tight_layout()
        figure.savefig(figures_dir / f"{name}.png", dpi=160, bbox_inches="tight")
        figure.savefig(figures_dir / f"{name}.svg", bbox_inches="tight")
        display = mo.as_html(figure)
        plt.close(figure)
        return display

    return clean_dir, con, figures_dir, query, results_dir, root, save_figure, sql_dir


@app.cell
def _(con, mo, query, sql_dir):
    con.execute((sql_dir / "00_load_raw.sql").read_text())
    raw_audit = query("01_raw_audit.sql")
    assert raw_audit.loc[0, "duplicate_ids"] == 0, "Inspect duplicate IDs before choosing a deduplication rule."
    mo.vstack([
        mo.md("""
        ## First look: rows, dates, and keys

        The raw CSV is read as text so mixed values cannot quietly change the
        inferred schema. Invalid IDs or dates are counted before removal.
        Duplicate IDs stop the notebook: choosing which loan record to keep
        should be an explicit decision, not an arbitrary `drop_duplicates()`.
        """),
        mo.ui.table(raw_audit, selection=None),
    ])
    return (raw_audit,)


@app.cell
def _(mo, plt, query, raw_audit, save_figure):
    missingness = query("02_raw_missingness.sql")
    _top = missingness.head(25).sort_values("missing_pct")
    _fig, _ax = plt.subplots(figsize=(10, 8))
    _ax.barh(_top["column_name"], _top["missing_pct"])
    _ax.set(xlabel="Missing values (%)", title="Raw data: 25 most incomplete fields", xlim=(0, 105))
    mo.vstack([
        mo.md(f"""
        ## How complete is the source?

        There are **{len(missingness):,} columns** across
        **{int(raw_audit.loc[0, 'raw_rows']):,} raw rows**.
        **{int((missingness.missing_pct == 100).sum())} columns are entirely missing**.
        Missing does not always mean bad data: joint-applicant and hardship
        fields can be inapplicable. I will not fill every blank with zero or
        drop every row that contains one.
        """),
        save_figure(_fig, "01_raw_missingness"),
        mo.ui.table(missingness, selection=None),
    ])
    return (missingness,)


@app.cell
def _(con, missingness, mo, query, raw_audit, results_dir, sql_dir):
    con.execute((sql_dir / "03_clean_loans.sql").read_text())
    cleaning_audit = query("04_cleaning_audit.sql")
    clean_summary = con.execute("""
        SELECT count(*) AS clean_rows, count(DISTINCT loan_id) AS unique_ids,
            count(*) FILTER (WHERE issue_year <= 2015) AS development_rows,
            count(*) FILTER (WHERE issue_year = 2016) AS validation_rows,
            count(*) FILTER (WHERE issue_year >= 2017) AS later_test_rows
        FROM loans
    """).df()
    clean_summary.to_csv(results_dir / "cleaning_summary.csv", index=False)
    assert clean_summary.loc[0, "clean_rows"] == clean_summary.loc[0, "unique_ids"]
    _dropped = int(raw_audit.loc[0, "raw_rows"] - clean_summary.loc[0, "clean_rows"])
    mo.vstack([
        mo.md(f"""
        ## Cleaning decisions

        **{_dropped:,} rows removed** because their loan ID or issue date could
        not be parsed. The original CSV stays unchanged.

        - Strip whitespace from categories; parse dates, percentages, and terms.
        - Treat nonpositive income, negative DTI/utilization, and credit dates
          after issue as missing. Keep high but possible values for inspection.
        - Preserve missing employment length; `< 1 year` becomes 0 and
          `10+ years` becomes 10, a capped category rather than an exact duration.
        - Keep unresolved loans in the clean table, with a missing outcome.
          Only ordinary `Fully Paid` and `Charged Off` statuses get labels 0 and 1.
          Historical policy-exception statuses remain outside this comparison.
        - Use an explicit set of fields. Repayments, recoveries, settlements,
          hardship outcomes, and updated FICO scores are unavailable at origination.

        No imputation, scaling, winsorization, or outlier deletion is fitted here.
        Those decisions belong inside the future training pipeline.
        """),
        mo.ui.table(cleaning_audit, selection=None),
        mo.ui.table(clean_summary, selection=None),
    ])
    return clean_summary, cleaning_audit


@app.cell
def _(clean_summary, mo, plt, query, save_figure):
    status_coverage = query("05_status_coverage.sql")
    cohorts = query("09_cohorts.sql")
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))
    _statuses = status_coverage.sort_values("loans")
    _axes[0].barh(_statuses.loan_status, _statuses.loans / 1000)
    _axes[0].set(xlabel="Loans (thousands)", title="All years: status at the dataset snapshot")
    for _term, _group in cohorts.groupby("term_months"):
        _axes[1].plot(_group.issue_year, _group.resolved_pct, marker="o", label=f"{int(_term)} months")
    _axes[1].set(xlabel="Issue year", ylabel="Fully paid or charged off (%)", ylim=(0, 105), title="Later cohorts have less observed outcome coverage")
    _axes[1].legend(title="Loan term")
    _resolved = status_coverage[status_coverage.loan_status.isin(["Fully Paid", "Charged Off"])].loans.sum()
    mo.vstack([
        mo.md(f"""
        ## What can we call an outcome?

        **{_resolved:,} of {int(clean_summary.loc[0, 'clean_rows']):,} loans** have
        an ordinary fully paid or charged-off status. A current loan is not a
        successful repayment. Labelling it 0 would mix unknown outcomes with
        known ones. Fully paid loans can also include early repayments.

        The coverage plot uses all years solely to check this limitation.
        Rates below are **charged-off shares among resolved loans**, not
        fixed-horizon default probabilities. Outcome selection and unequal
        follow-up still affect comparisons, especially for 60-month loans.
        """),
        save_figure(_fig, "02_status_and_followup"),
        mo.ui.table(status_coverage, selection=None),
    ])
    return cohorts, status_coverage


@app.cell
def _(clean_summary, mo, plt, query, save_figure):
    numeric_summary = query("06_numeric_summary.sql")
    distributions = query("07_distributions.sql")
    _fig, _axes = plt.subplots(2, 3, figsize=(14, 8))
    _labels = {"loan_amnt": "Loan amount ($)", "int_rate": "Interest rate (%)", "annual_inc": "Annual income ($)", "dti": "Debt-to-income ratio", "revol_util": "Revolving utilization (%)", "fico_mid": "Origination FICO midpoint"}
    for _ax, (_feature, _label) in zip(_axes.flat, _labels.items()):
        _hist = distributions[distributions.feature == _feature]
        _summary = numeric_summary[numeric_summary.feature == _feature].iloc[0]
        if _feature in ["annual_inc", "dti", "revol_util"]:
            _limit = _summary.p99
            _visible = _hist[_hist.bin_start <= _limit]
            _ax.set_xlim(0, _limit)
            _ax.set_title(f"{_feature}: view ends at p99 ({_limit:,.0f})")
        else:
            _visible = _hist
            _ax.set_title(_feature)
        _ax.bar(_visible.bin_start, _visible.loans / 1000, width=_visible.width, align="edge", edgecolor="white", linewidth=0.3)
        _ax.set(xlabel=_label, ylabel="Loans (thousands)")
    mo.vstack([
        mo.md("""
        ## Univariate: typical values and long tails

        These histograms use SQL counts over the full development period.
        Income, DTI, and utilization show values only up to the 99th percentile
        so the main distribution remains readable. **The underlying rows are
        not trimmed.** The table includes the maximum as well as percentiles;
        compare them before deciding whether an extreme value is plausible.
        """),
        save_figure(_fig, "03_numeric_distributions"),
        mo.ui.table(numeric_summary.round(2), selection=None),
    ])
    return distributions, numeric_summary


@app.cell
def _(clean_summary, mo, plt, query, save_figure):
    category_rates = query("08_category_rates.sql")
    _fig, _axes = plt.subplots(1, 3, figsize=(15, 6))
    for _ax, _feature in zip(_axes, ["grade", "purpose", "home_ownership"]):
        _group = category_rates[category_rates.feature == _feature].sort_values("total_loans")
        _ax.barh(_group.category, _group.total_loans / 1000)
        _ax.set(xlabel="Loans (thousands)", title=_feature)
    mo.vstack([
        mo.md("""
        ## Univariate: which loans dominate?

        Check category sizes before comparing their outcomes. A rare purpose or
        home-ownership label can have a striking rate supported by very few loans.
        Missing categories are excluded from these bars; source completeness is
        available above. These counts include unresolved development loans.
        """),
        save_figure(_fig, "04_category_counts"),
    ])
    return (category_rates,)


@app.cell
def _(category_rates, con, clean_summary, mo, plt, results_dir, save_figure):
    development_outcomes = con.execute("""
        SELECT CASE charged_off WHEN 0 THEN 'Fully Paid' WHEN 1 THEN 'Charged Off'
               ELSE 'Other / unresolved' END AS outcome, count(*) AS loans
        FROM eda_loans GROUP BY charged_off ORDER BY charged_off NULLS LAST
    """).df()
    development_outcomes.to_csv(results_dir / "development_outcomes.csv", index=False)
    _known = development_outcomes[development_outcomes.outcome != "Other / unresolved"]
    development_rate = 100 * _known.loc[_known.outcome == "Charged Off", "loans"].sum() / _known.loans.sum()
    _fig, _axes = plt.subplots(1, 2, figsize=(12, 4))
    _axes[0].bar(development_outcomes.outcome, development_outcomes.loans / 1000)
    _axes[0].set(ylabel="Loans (thousands)", title="Development-period outcome balance")
    _grades = category_rates[category_rates.feature == "grade"].sort_values("category")
    _axes[1].bar(_grades.category, _grades.charged_off_pct)
    for _x, _row in enumerate(_grades.itertuples()):
        _axes[1].text(_x, _row.charged_off_pct + 1, f"n={_row.resolved_loans:,}", ha="center", rotation=45, fontsize=8)
    _axes[1].axhline(development_rate, color="black", linestyle="--", label=f"Overall: {development_rate:.1f}%")
    _axes[1].set(xlabel="Assigned grade", ylabel="Charged off among resolved (%)", title="Bivariate: grade and outcome")
    _axes[1].set_ylim(0, max(_grades.charged_off_pct) + 16)
    _axes[1].legend()
    mo.vstack([
        mo.md(f"""
        ## Bivariate: does grade separate outcomes?

        The development-period charged-off share is **{development_rate:.1f}%**
        among resolved loans. Bar annotations show each denominator.
        Assigned grade and interest rate incorporate LendingClub's own underwriting;
        using them answers a different question from building an independent
        application-risk model. We should compare models with and without them later.
        """),
        save_figure(_fig, "05_outcomes_and_grade"),
    ])
    return development_outcomes, development_rate


@app.cell
def _(category_rates, development_rate, mo, plt, save_figure):
    _fig, _axes = plt.subplots(1, 2, figsize=(14, 6))
    for _ax, _feature in zip(_axes, ["purpose", "home_ownership"]):
        _group = category_rates[category_rates.feature == _feature].sort_values("charged_off_pct")
        _ax.barh(_group.category, _group.charged_off_pct)
        for _i, _row in enumerate(_group.itertuples()):
            _ax.text(_row.charged_off_pct + 0.5, _i, f"n={_row.resolved_loans:,}", va="center", fontsize=8)
        _ax.axvline(development_rate, color="black", linestyle="--")
        _ax.set(xlabel="Charged off among resolved (%)", title=_feature, xlim=(0, _group.charged_off_pct.max() + 16))
    mo.vstack([
        mo.md("""
        ## Bivariate: purpose and home ownership

        The dashed line is the overall resolved-loan rate. Read each rate beside
        its denominator. These are associations: different grades, incomes,
        issue years, and loan terms can account for apparent group differences.
        Home ownership is not a substitute for a protected demographic attribute,
        and this chart is not a fairness test.
        """),
        save_figure(_fig, "06_category_outcomes"),
        mo.ui.table(category_rates.round(2), selection=None),
    ])
    return


@app.cell
def _(clean_summary, development_rate, mo, plt, query, save_figure):
    numeric_rates = query("10_numeric_rates.sql")
    _fig, _axes = plt.subplots(1, 3, figsize=(14, 4))
    for _ax, _feature, _maximum in zip(_axes, ["fico_mid", "dti", "annual_inc"], [850, 60, 200000]):
        _group = numeric_rates[(numeric_rates.feature == _feature) & (numeric_rates.band <= _maximum) & (numeric_rates.resolved_loans >= 200)]
        _ax.plot(_group.band, _group.charged_off_pct, marker="o")
        _ax.axhline(development_rate, color="black", linestyle="--", linewidth=1)
        _ax.set(xlabel=f"{_feature} (band lower bound)", ylabel="Charged off among resolved (%)")
        _ax.ticklabel_format(axis="x", style="plain")
        _ax.tick_params(axis="x", rotation=30)
    mo.vstack([
        mo.md("""
        ## Bivariate: credit score, debt burden, and income

        SQL bins avoid a misleading scatterplot with hundreds of thousands of
        overlapping points. Only bins with **at least 200 resolved loans** are
        plotted; display limits are shown on the axes. All bins and denominators
        remain in `10_numeric_rates.csv`. Missing values have no numeric bin.
        These curves are descriptive and do not control for other variables.
        """),
        save_figure(_fig, "07_numeric_outcomes"),
    ])
    return (numeric_rates,)


@app.cell
def _(clean_summary, mo, plt, query, save_figure, sns):
    grade_term = query("11_grade_term.sql")
    _rates = grade_term.pivot(index="grade", columns="term_months", values="charged_off_pct")
    _counts = grade_term.pivot(index="grade", columns="term_months", values="resolved_loans")
    _fig, _axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.heatmap(_rates.where(_counts >= 200), annot=True, fmt=".1f", cmap="YlOrRd", ax=_axes[0], cbar_kws={"label": "Charged off among resolved (%)"})
    sns.heatmap(_counts, annot=True, fmt=",.0f", cmap="Blues", ax=_axes[1], cbar=False)
    _axes[0].set_title("Multivariate: outcome by grade and term")
    _axes[1].set_title("Resolved loans behind each cell")
    for _ax in _axes:
        _ax.set(xlabel="Term (months)", ylabel="Grade")
    mo.vstack([
        mo.md("""
        ## Multivariate: does the grade pattern hold within a term?

        Compare grades down a column, then compare terms within a grade. This
        helps separate two variables that are mixed together in the earlier chart.
        Rate cells with fewer than 200 resolved loans are blanked, while the count
        panel keeps every cell visible. Loan term also changes follow-up time;
        this is not evidence that a longer term causes a higher default rate.
        """),
        save_figure(_fig, "08_grade_term_outcomes"),
        mo.ui.table(grade_term.round(2), selection=None),
    ])
    return (grade_term,)


@app.cell
def _(clean_summary, mo, plt, query, save_figure, sns):
    grade_cohort = query("12_grade_cohort.sql")
    _rates = grade_cohort.pivot(index="grade", columns="issue_year", values="charged_off_pct")
    _counts = grade_cohort.pivot(index="grade", columns="issue_year", values="resolved_loans")
    _coverage = grade_cohort.pivot(index="grade", columns="issue_year", values="resolved_pct")
    _fig, _axes = plt.subplots(2, 1, figsize=(13, 9))
    sns.heatmap(_rates.where(_counts >= 200), annot=True, fmt=".1f", cmap="YlOrRd", ax=_axes[0], cbar_kws={"label": "Charged off among resolved (%)"})
    sns.heatmap(_coverage, annot=True, fmt=".0f", cmap="Blues", vmin=0, vmax=100, ax=_axes[1], cbar_kws={"label": "Resolved (%)"})
    _axes[0].set_title("Development cohorts: grade and observed outcome")
    _axes[1].set_title("Outcome coverage for the same groups")
    mo.vstack([
        mo.md("""
        ## Multivariate: grade, issue year, and outcome

        A single pooled rate can hide changes in underwriting or borrower mix.
        Here the upper panel is paired with outcome coverage, not read alone.
        Rate cells require at least 200 resolved loans. Even within development
        years, follow-up differs; these are not comparable lifetime default rates.
        """),
        save_figure(_fig, "09_grade_cohort_outcomes"),
    ])
    return (grade_cohort,)


@app.cell
def _(clean_summary, mo, plt, query, save_figure, sns):
    correlations = query("13_correlations.sql")
    _matrix = correlations.pivot(index="feature_x", columns="feature_y", values="correlation")
    _fig, _ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(_matrix, annot=True, fmt=".2f", cmap="vlag", center=0, vmin=-1, vmax=1, square=True, ax=_ax)
    _ax.set(title="Development data: Pearson feature correlations", xlabel="", ylabel="")
    mo.vstack([
        mo.md("""
        ## Multivariate: redundant information and skew

        Pearson correlations use all available pairs in the development period,
        without trimming extreme values. They describe linear association and can
        be sensitive to long tails. A small coefficient does not rule out a
        nonlinear relationship. Outcome and post-origination fields are excluded.
        Missingness means different pairs can use different rows.
        """),
        save_figure(_fig, "10_feature_correlations"),
    ])
    return (correlations,)


@app.cell
def _(clean_summary, con, mo, numeric_summary, plt, results_dir, save_figure):
    development_sample = con.execute("""
        SELECT loan_amnt, annual_inc, dti, fico_mid, int_rate, charged_off
        FROM eda_loans WHERE charged_off IS NOT NULL
        ORDER BY hash(loan_id, 42) LIMIT 20000
    """).df()
    _sample_stats = development_sample.groupby("charged_off").size().rename("sample_loans").reset_index()
    _sample_stats.to_csv(results_dir / "scatter_sample_counts.csv", index=False)
    _fig, _axes = plt.subplots(1, 2, figsize=(13, 5))
    for _outcome, _label, _color in [(0, "Fully Paid", "#0072B2"), (1, "Charged Off", "#D55E00")]:
        _points = development_sample[development_sample.charged_off == _outcome]
        _axes[0].scatter(_points.fico_mid, _points.int_rate, s=6, alpha=0.12, color=_color, label=_label, rasterized=True)
        _axes[1].scatter(_points.annual_inc, _points.loan_amnt, s=6, alpha=0.12, color=_color, label=_label, rasterized=True)
    _axes[0].set(xlabel="Origination FICO midpoint", ylabel="Interest rate (%)", title="Underwriting patterns and overlapping outcomes")
    _income_limit = numeric_summary.loc[numeric_summary.feature == "annual_inc", "p99"].iloc[0]
    _axes[1].set(xlabel="Annual income ($)", ylabel="Loan amount ($)", xlim=(0, _income_limit), title="Income and requested amount (income view to p99)")
    _axes[0].legend(markerscale=3)
    mo.vstack([
        mo.md("""
        ## A closer look at overlap

        These two scatterplots use a deterministic, unbalanced sample of up to
        **20,000 resolved development loans**, selected by a hash of loan ID.
        The sample is for plotting only; the preceding rates use the full
        development data. Dense overlap is a reminder that one feature cannot
        cleanly separate outcomes. Display clipping does not delete data.
        """),
        save_figure(_fig, "11_sampled_relationships"),
    ])
    return (development_sample,)


@app.cell
def _(category_rates, clean_summary, cleaning_audit, cohorts, correlations, development_rate, distributions, grade_cohort, grade_term, mo, numeric_rates, numeric_summary, raw_audit, results_dir):
    _income = numeric_summary[numeric_summary.feature == "annual_inc"].iloc[0]
    _grades = category_rates[category_rates.feature == "grade"].set_index("category")
    _latest = cohorts[cohorts.issue_year == cohorts.issue_year.max()]
    _latest_coverage = 100 * _latest.resolved_loans.sum() / _latest.total_loans.sum()
    findings = f"""# LendingClub analysis findings

## Data and population

- Raw rows: {int(raw_audit.loc[0, 'raw_rows']):,}; clean rows: {int(clean_summary.loc[0, 'clean_rows']):,}.
- Development originations (through 2015): {int(clean_summary.loc[0, 'development_rows']):,}.
- Resolved means ordinary Fully Paid or Charged Off; other statuses have no binary label.
- Detailed feature/outcome EDA uses development years only. All-year status coverage is a limited holdout inspection, not a completely untouched test set.

## Observations

- Charged off among resolved development loans: {development_rate:.2f}%.
- Grade A: {_grades.loc['A', 'charged_off_pct']:.2f}% across {int(_grades.loc['A', 'resolved_loans']):,} resolved loans; grade G: {_grades.loc['G', 'charged_off_pct']:.2f}% across {int(_grades.loc['G', 'resolved_loans']):,}.
- Development annual income: median ${_income['median']:,.0f}, p99 ${_income.p99:,.0f}, maximum ${_income.maximum:,.0f}. The tail needs investigation before choosing a transform.
- Only {_latest_coverage:.1f}% of the latest issue-year cohort has an ordinary resolved outcome. Do not label remaining loans as successful repayments.

## Decisions and limits

- Preserve missingness and extreme but possible values. Invalid nonpositive income and negative DTI/utilization become NULL; credit history cannot begin after issue.
- No imputation or clipping is learned from the full dataset. Fit future preprocessing on training rows only.
- The clean table is an analysis table, not a model-ready training matrix. It includes loan_status and charged_off for analysis; never use those as predictors.
- Grade and interest rate reflect existing underwriting. Later compare performance with and without them and decide whether predictions happen before or after pricing.
- Resolved-only comparisons have outcome-selection bias and unequal follow-up. Choose a fixed prediction horizon and sufficiently mature cohorts, or a survival approach, before model evaluation.
- Counts accompany category rates; small multivariate cells are suppressed below 200 resolved loans. Associations do not establish causality.
- The data contains accepted loans only. These plots do not establish fairness or outcomes for rejected applicants; protected demographic coverage is limited.

## Outputs

SQL results are in assets/results, PNG/SVG figures in assets/figures, and the local database and Parquet analysis table in data/clean. The source CSV is unchanged.
"""
    (results_dir / "analysis_findings.md").write_text(findings)
    mo.md(findings)
    return (findings,)


@app.cell
def _(clean_dir, con, findings, mo):
    _parquet_path = str(clean_dir / "loans.parquet").replace("'", "''")
    con.execute(f"COPY loans TO '{_parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    mo.md("""
    ## Saved for the next step

    The cleaned analysis table is in `data/clean/loans.parquet` and the local
    DuckDB database. Query summaries and findings are in `assets/results/`;
    each figure has PNG and SVG versions in `assets/figures/`.

    No model training has been started. The next decision is the prediction
    horizon and maturity rule for defining the training population.
    """)
    return


@app.cell
def _(mo, pd, root):
    import json as _review_json

    _review_outputs = [mo.md("""
    ## Current modelling results

    The EDA above records the original investigation. The completed validation
    and snapshot-loss proxy experiment below are separate later stages.
    Open `notebooks/10_model_review.py` for SQL summaries, calibration figures,
    loss diagnostics, and the explicit capital assumptions.
    """)]
    _validation_path = root / "assets/results/validation_hardening_latest.json"
    if _validation_path.exists():
        _validation_manifest = _review_json.loads(_validation_path.read_text())
        _validation_results = root / _validation_manifest["result_directory"]
        _review_outputs += [mo.md("### Exact charge-off validation and separate-year calibration"),
            mo.ui.table(pd.read_csv(_validation_results / "auc_confidence_intervals.csv")),
            mo.ui.table(pd.read_csv(_validation_results / "calibration_metrics.csv"))]
    _loss_path = root / "assets/results/basel_loss_latest.json"
    if _loss_path.exists():
        _loss_manifest = _review_json.loads(_loss_path.read_text())
        _loss_results = root / _loss_manifest["result_directory"]
        _review_outputs += [mo.md("""
        ### EAD, LGD, expected loss and capital scenarios

        EAD/LGD are bounded snapshot proxies. Recovery fields form loss targets,
        never classifier predictors. Capital uses assumed one-year PD scenarios;
        the classifier score remains a resolved-loan score. This is illustrative,
        with no regulatory compliance claim. charge-off probabilities are unchanged.
        """), mo.ui.table(pd.read_csv(_loss_results / "component_metrics.csv")),
            mo.ui.table(pd.read_csv(_loss_results / "portfolio_loss_metrics.csv")),
            mo.ui.table(pd.read_csv(_loss_results / "portfolio_capital_scenarios.csv"))]
    mo.vstack(_review_outputs)
    return


if __name__ == "__main__":
    app.run()
