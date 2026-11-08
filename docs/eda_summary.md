# LendingClub EDA: final report and decisions

Completed: 2026-11-08T15:19:48+00:00. Scope: exploratory data analysis and its handoff to
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
- Development income median: $65,000;
  p99: $250,000; maximum:
  $9,500,000. Means and correlations
  need to be read with the heavy tail in mind.
- 153 loans have income above $1 million;
  9 have DTI above 100 (including one at
  exactly 999); 3,506 have utilization
  above 100%. These are investigation flags, not proven errors.
- Missing employment has 23.65%
  charged off among 42,577 resolved
  loans, versus 18.14% among
  784,027 with employment present.
  This is an unadjusted association, not evidence of causation or random missingness.
- Within 320,563 resolved 36-month loans from 2011–2014, the FICO/DTI grid shows
  increasing observed charged-off shares across higher DTI bands within each
  displayed FICO band. Even within this narrower population, confounding remains.
- 5 category labels across the seven profiled fields have fewer than
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

Initial candidates (14): `loan_amnt`, `annual_inc`, `dti`, `revol_util`, `revol_bal`, `open_acc`, `delinq_2yrs`, `pub_rec_bankruptcies`, `emp_length_years`, `fico_mid`, `credit_history_years`, `home_ownership`, `purpose`, `application_type`.

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

| proposed_split | all_loans | eligible_resolved_loans | excluded_other_status | fully_paid | charged_off | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | 157,993 | 157,993 | 0 | 138,213 | 19,780 | 100 | 12.519542 |
| validation | 162,570 | 162,570 | 0 | 140,255 | 22,315 | 100 | 13.726395 |
| exploratory_test | 283,173 | 283,026 | 147 | 240,894 | 42,132 | 99.948088 | 14.886265 |

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
