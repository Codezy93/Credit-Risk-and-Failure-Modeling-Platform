# Project statistics reference

> Latest measured model results are in section 18 and docs/model_experiments.md. Earlier sections retain their stage-specific snapshots. Kafka stress tests, InterpretML, and bias evaluations have not run.

Snapshot assembled: **2026-11-08T14:17:16+00:00**. This is a static record of the completed data-analysis stage, assembled from existing result CSVs, local file metadata, and the clean Parquet schema. The download, cleaning, and EDA pipeline was **not rerun** to create this document.

Use this file for factual project answers. Counts are exact integers; displayed noninteger values are rounded to at most six decimal places. Linked CSVs retain the original exported precision. Future measurements are marked **Not measured** rather than assigned invented values or zeros. A static snapshot becomes stale when code, data, or results change; update this file after each completed project stage.

## Contents

1. [Quick answers](#1-quick-answers)
2. [Data provenance and scope](#2-data-provenance-and-scope)
3. [Rows, cleaning, schema, and missingness](#3-rows-cleaning-schema-and-missingness)
4. [Populations, outcomes, and time coverage](#4-populations-outcomes-and-time-coverage)
5. [Univariate statistics](#5-univariate-statistics)
6. [Bivariate statistics](#6-bivariate-statistics)
7. [Multivariate statistics](#7-multivariate-statistics)
8. [Figures, sampling, and display rules](#8-figures-sampling-and-display-rules)
9. [Model experiments and evaluation](#9-model-experiments-and-evaluation)
10. [Interpretability and bias evaluation](#10-interpretability-and-bias-evaluation)
11. [Kafka stress testing and ELK monitoring](#11-kafka-stress-testing-and-elk-monitoring)
12. [Artifacts, environment, and verification](#12-artifacts-environment-and-verification)
13. [Complete SQL histogram bins](#13-complete-sql-histogram-bins)
14. [Source fingerprints and update rules](#14-source-fingerprints-and-update-rules)
15. [Follow-up EDA](#15-follow-up-eda)
16. [EDA completion](#16-eda-completion)
17. [Model-data preparation](#17-model-data-preparation)
18. [Model experiments](#18-model-experiments)
19. [MLflow datasets and evaluations](#19-mlflow-datasets-and-evaluations)

## 1. Quick answers

| Statistic | Value |
| --- | --- |
| Completed stage | First MLflow model comparison complete |
| Dataset | LendingClub accepted loans, June 2007–December 2018 |
| Raw rows | 2,260,701 |
| Raw columns | 151 |
| Rows excluded during cleaning | 33 |
| Excluded share of raw rows (%) | 0.00146 |
| Clean rows | 2,260,668 |
| Clean unique loan IDs | 2,260,668 |
| Clean columns | 26 |
| Duplicate valid numeric IDs in raw data | 0 |
| Development rows: issue year <= 2015 | 887,440 |
| Provisional validation rows: 2016 | 434,407 |
| Provisional later-test rows: 2017–2018 | 938,821 |
| Resolved development loans | 826,604 |
| Fully paid development loans | 674,302 |
| Charged-off development loans | 152,302 |
| Other / unresolved development loans | 60,836 |
| Charged off among resolved development loans (%) | 18.425026 |
| Resolved loans, all years | 1,345,310 |
| Other / unresolved loans, all years | 915,358 |
| Charged off among resolved loans, all years (%) | 19.962611 |
| Entirely missing source columns | 1 |
| Saved figure sets | 24 |
| Saved image files | 48 |
| Saved result CSVs | 42 |
| Deterministic scatterplot sample | 20,000 |
| Models trained / MLflow evaluation metrics | Four fitted pipelines; current measured results in section 18 |
| Kafka stress-test performance | Not measured; streaming/stress-test stage not implemented |

The headline charged-off rate is a **resolved-loan share**, not a validated fixed-horizon probability of default or a model metric. The provisional split counts above include unresolved loans; they are not final model-training sample sizes.

## 2. Data provenance and scope

- Source: [All Lending Club loan data on Kaggle](https://www.kaggle.com/datasets/wordsforthewise/lending-club), handle `wordsforthewise/lending-club`.
- Download script: [`scripts/download_data.py`](../scripts/download_data.py).
- Downloaded filename: `accepted_2007_to_2018Q4.csv.gz`; extracted filename: `accepted_2007_to_2018Q4.csv`.
- Unit of analysis: one accepted loan record, keyed by numeric loan ID. Counts are loans, not distinct borrowers.
- First and last valid issue months: **2007-06-01** and **2018-12-01**. Dates parsed from month/year strings use the first day of that month; the source does not establish an exact daily origination date here.
- The script requests the latest Kaggle dataset version. An explicit dataset version number and raw-file content hash were not recorded at download time.
- Raw source is preserved. Rejected loans were not downloaded or analyzed.
- This is historical snapshot data. The report generation date is not the outcome observation date. An authoritative common outcome cutoff was not established during this stage.
- Detailed feature and outcome EDA uses loans issued through 2015. All-year missingness, cleaning audits, and status coverage were inspected. The later split is therefore reserved from detailed feature exploration, but is not completely unseen in every respect.

## 3. Rows, cleaning, schema, and missingness

### Raw row audit

| raw_rows | invalid_id_rows | duplicate_ids | invalid_issue_dates | first_issue_date | last_issue_date |
| --- | --- | --- | --- | --- | --- |
| 2,260,701 | 33 | 0 | 33 | 2007-06-01 | 2018-12-01 |

Source: [`01_raw_audit.csv`](results/01_raw_audit.csv).

Both invalid-ID and invalid-issue-date counts are 33. The union of those conditions removes 33 rows, so these are the same rows; do not add the two counts and report 66 removals. Duplicate-ID counts concern parsed numeric IDs, excluding invalid/missing IDs.

### Clean row and split reconciliation

| clean_rows | unique_ids | development_rows | validation_rows | later_test_rows |
| --- | --- | --- | --- | --- |
| 2,260,668 | 2,260,668 | 887,440 | 434,407 | 938,821 |

Source: [`cleaning_summary.csv`](results/cleaning_summary.csv).

Reconciliations:

- Raw minus excluded: 2,260,701 − 33 = **2,260,668**.
- Development + validation + later test: 887,440 + 434,407 + 938,821 = **2,260,668**.
- Clean rows equal unique clean IDs: **2,260,668**.

### Cleaning changes and parsing audit

Counts below are over the **raw source**, not development rows only. Checks can overlap and must not be summed as a distinct count of affected loans.

| check_name | affected_rows |
| --- | --- |
| nonpositive_income | 1,667 |
| negative_dti | 2 |
| negative_revol_util | 0 |
| credit_date_after_issue | 0 |
| income_parse_failures | 0 |
| dti_parse_failures | 0 |

Source: [`04_cleaning_audit.csv`](results/04_cleaning_audit.csv).

Cleaning rules implemented in [`03_clean_loans.sql`](../sql/03_clean_loans.sql):

- Read the raw CSV as text, then explicitly parse selected values with DuckDB `try_cast` / `try_strptime`. Unparseable values become NULL.
- Exclude rows with an unparseable loan ID or issue date. Do not deduplicate arbitrarily; the notebook stops if valid numeric IDs repeat.
- Strip surrounding whitespace from selected categories and turn empty category strings into NULL.
- Strip percent signs from interest rate values when present; rates remain in percentage points, not fractions.
- Extract numeric loan term in months.
- Convert `< 1 year` employment to 0; `10+ years` to 10. Employment is capped, not an exact duration for the last category. Missing employment stays missing.
- Annual income <= 0 becomes NULL; negative DTI and revolving utilization become NULL. Zero DTI/utilization remain valid.
- Keep high income, DTI, and utilization values. Some may be unusual or sentinel values; their meaning has not been resolved. No outlier deletion or winsorization was performed.
- FICO midpoint = `(fico_range_low + fico_range_high) / 2` at origination.
- Credit-history years = number of month boundaries between earliest credit month and issue month, divided by 12. A credit date after issue becomes NULL.
- Label `Charged Off` as 1 and `Fully Paid` as 0; every other status has a NULL outcome, including the 40 records whose literal status is `Default` and the historical policy-exception statuses.
- No imputation, scaling, model feature selection, or learned preprocessing was fitted.
- Exclude repayment, recovery, settlement, hardship outcome, and updated FICO fields from the focused analysis table.
- The numeric parsing audit explicitly checks income and DTI conversion failures; it is not an exhaustive per-field conversion-failure audit.

### Clean table schema

The analysis table includes identifiers and outcomes. The column count below is **not** the number of model predictors. `loan_status` and `charged_off` must never be predictors; `loan_id` is an identifier. Other fields still need a prediction-time availability review.

| Column | DuckDB type |
| --- | --- |
| loan_id | BIGINT |
| issue_date | DATE |
| loan_amnt | DOUBLE |
| int_rate | DOUBLE |
| installment | DOUBLE |
| term_months | INTEGER |
| grade | VARCHAR |
| sub_grade | VARCHAR |
| home_ownership | VARCHAR |
| verification_status | VARCHAR |
| application_type | VARCHAR |
| purpose | VARCHAR |
| addr_state | VARCHAR |
| loan_status | VARCHAR |
| emp_length_years | INTEGER |
| revol_bal | DOUBLE |
| open_acc | DOUBLE |
| delinq_2yrs | DOUBLE |
| pub_rec_bankruptcies | DOUBLE |
| fico_mid | DOUBLE |
| annual_inc | DOUBLE |
| dti | DOUBLE |
| revol_util | DOUBLE |
| credit_history_years | DOUBLE |
| charged_off | INTEGER |
| issue_year | BIGINT |

`loans` contains all clean years. `eda_loans` is a view with `issue_year <= 2015`. The Parquet export contains `loans`, not just the development population.

### Source missingness: every column

Denominator: **2,260,701 raw rows**. Both SQL NULL and whitespace-only/empty strings count as missing. Structural missingness (such as fields that apply only to joint loans) is mixed with ordinary missingness; these percentages do not justify blanket dropping or filling with zero.

| column_name | missing_count | missing_pct |
| --- | --- | --- |
| member_id | 2,260,701 | 100 |
| orig_projected_additional_accrued_interest | 2,252,050 | 99.617331 |
| deferral_term | 2,249,784 | 99.517097 |
| hardship_amount | 2,249,784 | 99.517097 |
| hardship_dpd | 2,249,784 | 99.517097 |
| hardship_end_date | 2,249,784 | 99.517097 |
| hardship_last_payment_amount | 2,249,784 | 99.517097 |
| hardship_length | 2,249,784 | 99.517097 |
| hardship_loan_status | 2,249,784 | 99.517097 |
| hardship_payoff_balance_amount | 2,249,784 | 99.517097 |
| hardship_reason | 2,249,784 | 99.517097 |
| hardship_start_date | 2,249,784 | 99.517097 |
| hardship_status | 2,249,784 | 99.517097 |
| hardship_type | 2,249,784 | 99.517097 |
| payment_plan_start_date | 2,249,784 | 99.517097 |
| debt_settlement_flag_date | 2,226,455 | 98.48516 |
| settlement_amount | 2,226,455 | 98.48516 |
| settlement_date | 2,226,455 | 98.48516 |
| settlement_percentage | 2,226,455 | 98.48516 |
| settlement_status | 2,226,455 | 98.48516 |
| settlement_term | 2,226,455 | 98.48516 |
| sec_app_mths_since_last_major_derog | 2,224,759 | 98.410139 |
| sec_app_revol_util | 2,154,517 | 95.30305 |
| revol_bal_joint | 2,152,681 | 95.221836 |
| sec_app_chargeoff_within_12_mths | 2,152,680 | 95.221792 |
| sec_app_collections_12_mths_ex_med | 2,152,680 | 95.221792 |
| sec_app_earliest_cr_line | 2,152,680 | 95.221792 |
| sec_app_fico_range_high | 2,152,680 | 95.221792 |
| sec_app_fico_range_low | 2,152,680 | 95.221792 |
| sec_app_inq_last_6mths | 2,152,680 | 95.221792 |
| sec_app_mort_acc | 2,152,680 | 95.221792 |
| sec_app_num_rev_accts | 2,152,680 | 95.221792 |
| sec_app_open_acc | 2,152,680 | 95.221792 |
| sec_app_open_act_il | 2,152,680 | 95.221792 |
| verification_status_joint | 2,144,971 | 94.880791 |
| dti_joint | 2,139,995 | 94.660683 |
| annual_inc_joint | 2,139,991 | 94.660506 |
| desc | 2,134,887 | 94.434735 |
| mths_since_last_record | 1,901,545 | 84.113069 |
| mths_since_recent_bc_dlq | 1,741,000 | 77.011511 |
| mths_since_last_major_derog | 1,679,926 | 74.30996 |
| mths_since_recent_revol_delinq | 1,520,342 | 67.25091 |
| next_pymnt_d | 1,345,343 | 59.509993 |
| mths_since_last_delinq | 1,158,535 | 51.246715 |
| il_util | 1,068,883 | 47.281042 |
| mths_since_rcnt_il | 909,957 | 40.251099 |
| all_util | 866,381 | 38.323555 |
| inq_last_12m | 866,163 | 38.313912 |
| open_acc_6m | 866,163 | 38.313912 |
| total_cu_tl | 866,163 | 38.313912 |
| inq_fi | 866,162 | 38.313868 |
| max_bal_bc | 866,162 | 38.313868 |
| open_act_il | 866,162 | 38.313868 |
| open_il_12m | 866,162 | 38.313868 |
| open_il_24m | 866,162 | 38.313868 |
| open_rv_12m | 866,162 | 38.313868 |
| open_rv_24m | 866,162 | 38.313868 |
| total_bal_il | 866,162 | 38.313868 |
| mths_since_recent_inq | 295,468 | 13.069751 |
| emp_title | 167,005 | 7.38731 |
| num_tl_120dpd_2m | 153,690 | 6.798334 |
| emp_length | 146,940 | 6.499754 |
| mo_sin_old_il_acct | 139,104 | 6.153136 |
| bc_util | 76,104 | 3.366389 |
| percent_bc_gt_75 | 75,412 | 3.335779 |
| bc_open_to_buy | 74,968 | 3.31614 |
| mths_since_recent_bc | 73,445 | 3.248771 |
| pct_tl_nvr_dlq | 70,464 | 3.116909 |
| avg_cur_bal | 70,379 | 3.113149 |
| mo_sin_old_rev_tl_op | 70,310 | 3.110097 |
| mo_sin_rcnt_rev_tl_op | 70,310 | 3.110097 |
| num_rev_accts | 70,310 | 3.110097 |
| mo_sin_rcnt_tl | 70,309 | 3.110053 |
| num_accts_ever_120_pd | 70,309 | 3.110053 |
| num_actv_bc_tl | 70,309 | 3.110053 |
| num_actv_rev_tl | 70,309 | 3.110053 |
| num_bc_tl | 70,309 | 3.110053 |
| num_il_tl | 70,309 | 3.110053 |
| num_op_rev_tl | 70,309 | 3.110053 |
| num_rev_tl_bal_gt_0 | 70,309 | 3.110053 |
| num_tl_30dpd | 70,309 | 3.110053 |
| num_tl_90g_dpd_24m | 70,309 | 3.110053 |
| num_tl_op_past_12m | 70,309 | 3.110053 |
| tot_coll_amt | 70,309 | 3.110053 |
| tot_cur_bal | 70,309 | 3.110053 |
| tot_hi_cred_lim | 70,309 | 3.110053 |
| total_il_high_credit_limit | 70,309 | 3.110053 |
| total_rev_hi_lim | 70,309 | 3.110053 |
| num_bc_sats | 58,623 | 2.593134 |
| num_sats | 58,623 | 2.593134 |
| acc_open_past_24mths | 50,063 | 2.21449 |
| mort_acc | 50,063 | 2.21449 |
| total_bal_ex_mort | 50,063 | 2.21449 |
| total_bc_limit | 50,063 | 2.21449 |
| title | 23,358 | 1.033219 |
| last_pymnt_d | 2,460 | 0.108816 |
| revol_util | 1,835 | 0.08117 |
| dti | 1,744 | 0.077144 |
| pub_rec_bankruptcies | 1,398 | 0.061839 |
| chargeoff_within_12_mths | 178 | 0.007874 |
| collections_12_mths_ex_med | 178 | 0.007874 |
| tax_liens | 138 | 0.006104 |
| last_credit_pull_d | 105 | 0.004645 |
| inq_last_6mths | 63 | 0.002787 |
| acc_now_delinq | 62 | 0.002743 |
| delinq_2yrs | 62 | 0.002743 |
| delinq_amnt | 62 | 0.002743 |
| earliest_cr_line | 62 | 0.002743 |
| open_acc | 62 | 0.002743 |
| pub_rec | 62 | 0.002743 |
| total_acc | 62 | 0.002743 |
| annual_inc | 37 | 0.001637 |
| zip_code | 34 | 0.001504 |
| addr_state | 33 | 0.00146 |
| application_type | 33 | 0.00146 |
| collection_recovery_fee | 33 | 0.00146 |
| debt_settlement_flag | 33 | 0.00146 |
| disbursement_method | 33 | 0.00146 |
| fico_range_high | 33 | 0.00146 |
| fico_range_low | 33 | 0.00146 |
| funded_amnt | 33 | 0.00146 |
| funded_amnt_inv | 33 | 0.00146 |
| grade | 33 | 0.00146 |
| hardship_flag | 33 | 0.00146 |
| home_ownership | 33 | 0.00146 |
| initial_list_status | 33 | 0.00146 |
| installment | 33 | 0.00146 |
| int_rate | 33 | 0.00146 |
| issue_d | 33 | 0.00146 |
| last_fico_range_high | 33 | 0.00146 |
| last_fico_range_low | 33 | 0.00146 |
| last_pymnt_amnt | 33 | 0.00146 |
| loan_amnt | 33 | 0.00146 |
| loan_status | 33 | 0.00146 |
| out_prncp | 33 | 0.00146 |
| out_prncp_inv | 33 | 0.00146 |
| policy_code | 33 | 0.00146 |
| purpose | 33 | 0.00146 |
| pymnt_plan | 33 | 0.00146 |
| recoveries | 33 | 0.00146 |
| revol_bal | 33 | 0.00146 |
| sub_grade | 33 | 0.00146 |
| term | 33 | 0.00146 |
| total_pymnt | 33 | 0.00146 |
| total_pymnt_inv | 33 | 0.00146 |
| total_rec_int | 33 | 0.00146 |
| total_rec_late_fee | 33 | 0.00146 |
| total_rec_prncp | 33 | 0.00146 |
| url | 33 | 0.00146 |
| verification_status | 33 | 0.00146 |
| id | 0 | 0 |

Source: [`02_raw_missingness.csv`](results/02_raw_missingness.csv).

## 4. Populations, outcomes, and time coverage

### Outcome definitions and denominators

- **Resolved**: exactly `Fully Paid` or `Charged Off`.
- **Charged-off share (%)**: 100 × charged-off loans / resolved loans in the stated group.
- **Outcome coverage (%)**: 100 × resolved loans / all clean loans in the stated group.
- **Other / unresolved**: all remaining statuses, including policy-exception statuses. It is a label-availability category, not a claim that every record is still active.
- A fully paid loan may have repaid early. A current/late/default-status loan is not automatically a negative label.
- Conditioning on resolved loans introduces selection bias and unequal follow-up. Before modeling, choose a horizon and maturity rule or a survival approach.

### All-year status counts

`pct_of_loans` uses all **2,260,668 clean loans**, not only resolved loans.

| loan_status | loans | pct_of_loans |
| --- | --- | --- |
| Fully Paid | 1,076,751 | 47.629771 |
| Current | 878,317 | 38.8521 |
| Charged Off | 268,559 | 11.87963 |
| Late (31-120 days) | 21,467 | 0.949587 |
| In Grace Period | 8,436 | 0.373164 |
| Late (16-30 days) | 4,349 | 0.192377 |
| Does not meet the credit policy. Status:Fully Paid | 1,988 | 0.087939 |
| Does not meet the credit policy. Status:Charged Off | 761 | 0.033663 |
| Default | 40 | 0.001769 |

Source: [`05_status_coverage.csv`](results/05_status_coverage.csv).

| Population | Total loans | Resolved | Other / unresolved | Coverage (%) | Charged-off share among resolved (%) |
| --- | --- | --- | --- | --- | --- |
| All clean years | 2,260,668 | 1,345,310 | 915,358 | 59.509402 | 19.962611 |
| Development through 2015 | 887,440 | 826,604 | 60,836 | 93.144776 | 18.425026 |

### Development outcome balance

| Outcome | Loans | Share of all development loans (%) |
| --- | --- | --- |
| Fully Paid | 674,302 | 75.982827 |
| Charged Off | 152,302 | 17.161949 |
| Other / unresolved | 60,836 | 6.855224 |

Source: [`development_outcomes.csv`](results/development_outcomes.csv).

Among resolved development loans, fully paid : charged off = **4.427401 : 1**. A classifier always predicting Fully Paid would have **81.574974% accuracy on that specific resolved development population**. This is arithmetic from label counts, not a trained model or a validation/test result.

### All-year cohort coverage by term

The exported cohort query also contains charged-off shares for later years. They are transcribed below for completeness, but are not holdout model evaluation results. `charged_off_pct` is conditional on resolution; `resolved_pct` is conditional on all loans in that year and term.

| issue_year | term_months | total_loans | resolved_loans | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- |
| 2,007 | 36 | 603 | 251 | 41.625207 | 17.928287 |
| 2,008 | 36 | 2,393 | 1,562 | 65.273715 | 15.81306 |
| 2,009 | 36 | 5,281 | 4,716 | 89.301269 | 12.59542 |
| 2,010 | 36 | 9,156 | 8,466 | 92.463958 | 9.945665 |
| 2,010 | 60 | 3,381 | 3,070 | 90.801538 | 21.009772 |
| 2,011 | 36 | 14,101 | 14,101 | 100 | 10.630452 |
| 2,011 | 60 | 7,620 | 7,620 | 100 | 23.595801 |
| 2,012 | 36 | 43,470 | 43,470 | 100 | 13.57948 |
| 2,012 | 60 | 9,897 | 9,897 | 100 | 27.695261 |
| 2,013 | 36 | 100,422 | 100,422 | 100 | 12.325984 |
| 2,013 | 60 | 34,392 | 34,382 | 99.970923 | 25.146879 |
| 2,014 | 36 | 162,570 | 162,570 | 100 | 13.726395 |
| 2,014 | 60 | 73,059 | 60,532 | 82.853584 | 31.133946 |
| 2,015 | 36 | 283,173 | 283,026 | 99.948088 | 14.886265 |
| 2,015 | 60 | 137,922 | 92,519 | 67.080669 | 36.393606 |
| 2,016 | 36 | 323,495 | 232,353 | 71.82584 | 19.845666 |
| 2,016 | 60 | 110,912 | 60,742 | 54.765941 | 36.432781 |
| 2,017 | 36 | 320,419 | 128,538 | 40.115599 | 20.010425 |
| 2,017 | 60 | 123,160 | 40,762 | 33.096785 | 32.939993 |
| 2,018 | 36 | 344,671 | 41,268 | 11.973157 | 13.240283 |
| 2,018 | 60 | 150,571 | 15,043 | 9.990636 | 22.621817 |

Source: [`09_cohorts.csv`](results/09_cohorts.csv).

### Cohort totals across terms

Derived from the preceding export. Charged-off counts are reconstructed by rounding `resolved_loans × charged_off_pct / 100`; every reconstructed value was checked to be within 0.000001 of an integer. Annual rates use combined counts, not an unweighted mean of term rates.

| Year | All loans | Resolved | Other / unresolved | Charged off | Coverage (%) | Charged off among resolved (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 2,007 | 603 | 251 | 352 | 45 | 41.625207 | 17.928287 |
| 2,008 | 2,393 | 1,562 | 831 | 247 | 65.273715 | 15.81306 |
| 2,009 | 5,281 | 4,716 | 565 | 594 | 89.301269 | 12.59542 |
| 2,010 | 12,537 | 11,536 | 1,001 | 1,487 | 92.015634 | 12.890083 |
| 2,011 | 21,721 | 21,721 | 0 | 3,297 | 100 | 15.178859 |
| 2,012 | 53,367 | 53,367 | 0 | 8,644 | 100 | 16.197275 |
| 2,013 | 134,814 | 134,804 | 10 | 21,024 | 99.992582 | 15.595976 |
| 2,014 | 235,629 | 223,102 | 12,527 | 41,161 | 94.683592 | 18.449409 |
| 2,015 | 421,095 | 375,545 | 45,550 | 75,803 | 89.182963 | 20.184798 |
| 2,016 | 434,407 | 293,095 | 141,312 | 68,242 | 67.470137 | 23.283236 |
| 2,017 | 443,579 | 169,300 | 274,279 | 39,148 | 38.16682 | 23.123449 |
| 2,018 | 495,242 | 56,311 | 438,931 | 8,867 | 11.370401 | 15.746479 |

## 5. Univariate statistics

### Numeric summary: development loans only

All rows below use the **887,440 development loans**. Percentiles, minimum, and maximum exclude NULLs; no trimming is applied to the exported summary. `p01`, `p25`, `p75`, and `p99` are the 1st, 25th, 75th, and 99th percentiles, calculated using continuous quantiles. The middle value is the median, not the mean. Numeric means, standard deviations, skewness, and kurtosis were not exported at this stage.

Units: loan amount/income are USD; interest and revolving utilization are percentage points; DTI is the source debt-to-income ratio expressed on its percentage scale; FICO is a score midpoint; employment and credit history are years.

| feature | nonmissing | missing | minimum | p01 | p25 | median | p75 | p99 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| annual_inc | 887,434 | 6 | 1,200 | 19,000 | 45,000 | 65,000 | 90,000 | 250,000 | 9,500,000 |
| credit_history_years | 887,411 | 29 | 0.5 | 4 | 11.25 | 14.833333 | 20.083333 | 39.5 | 71 |
| dti | 887,438 | 2 | 0 | 1.98 | 11.91 | 17.66 | 23.95 | 37.48 | 999 |
| emp_length_years | 842,605 | 44,835 | 0 | 0 | 3 | 6 | 10 | 10 | 10 |
| fico_mid | 887,440 | 0 | 612 | 662 | 672 | 692 | 712 | 797 | 847.5 |
| int_rate | 887,440 | 0 | 5.32 | 5.32 | 9.99 | 12.99 | 16.2 | 24.99 | 28.99 |
| loan_amnt | 887,440 | 0 | 500 | 1,800 | 8,000 | 13,000 | 20,000 | 35,000 | 35,000 |
| revol_util | 886,938 | 502 | 0 | 2.2 | 37.7 | 56 | 73.6 | 98.5 | 892.3 |

Source: [`06_numeric_summary.csv`](results/06_numeric_summary.csv).

### Development numeric missingness rates

| Feature | Nonmissing | Missing | Missing (%) |
| --- | --- | --- | --- |
| annual_inc | 887,434 | 6 | 0.000676 |
| credit_history_years | 887,411 | 29 | 0.003268 |
| dti | 887,438 | 2 | 0.000225 |
| emp_length_years | 842,605 | 44,835 | 5.052173 |
| fico_mid | 887,440 | 0 | 0 |
| int_rate | 887,440 | 0 | 0 |
| loan_amnt | 887,440 | 0 | 0 |
| revol_util | 886,938 | 502 | 0.056567 |

Interpretation reminders:

- Income median is $65,000, p99 is $250,000, and maximum is $9,500,000. A typical value and an extreme maximum answer different questions.
- DTI reaches 999 and utilization reaches 892.3. These were retained for investigation, not certified as realistic borrower values.
- Employment has a much larger missing share than the other summarized development features. A missingness indicator may be useful later, but none has been fitted here.

### Category counts and shares: development only

These proportions use **all development loans**, including unresolved loans. Missing categories are not emitted by the SQL UNPIVOT; do not interpret omission as an explicit missing category.

#### application_type

| Category | Total loans | Share of all development loans (%) |
| --- | --- | --- |
| Individual | 886,929 | 99.942419 |
| Joint App | 511 | 0.057581 |

#### grade

| Category | Total loans | Share of all development loans (%) |
| --- | --- | --- |
| A | 148,207 | 16.700509 |
| B | 254,553 | 28.683967 |
| C | 245,881 | 27.706775 |
| D | 139,554 | 15.725457 |
| E | 70,707 | 7.967525 |
| F | 23,049 | 2.597246 |
| G | 5,489 | 0.618521 |

#### home_ownership

| Category | Total loans | Share of all development loans (%) |
| --- | --- | --- |
| ANY | 3 | 0.000338 |
| MORTGAGE | 443,591 | 49.985464 |
| NONE | 50 | 0.005634 |
| OTHER | 182 | 0.020508 |
| OWN | 87,478 | 9.857342 |
| RENT | 356,136 | 40.130713 |

#### purpose

| Category | Total loans | Share of all development loans (%) |
| --- | --- | --- |
| car | 8,864 | 0.998828 |
| credit_card | 206,194 | 23.234698 |
| debt_consolidation | 524,253 | 59.074754 |
| educational | 423 | 0.047665 |
| home_improvement | 51,834 | 5.840846 |
| house | 3,707 | 0.417718 |
| major_purchase | 17,277 | 1.946836 |
| medical | 8,541 | 0.962431 |
| moving | 5,415 | 0.610182 |
| other | 42,896 | 4.833679 |
| renewable_energy | 575 | 0.064793 |
| small_business | 10,378 | 1.169431 |
| vacation | 4,736 | 0.53367 |
| wedding | 2,347 | 0.264469 |

#### verification_status

| Category | Total loans | Share of all development loans (%) |
| --- | --- | --- |
| Not Verified | 259,410 | 29.231272 |
| Source Verified | 336,925 | 37.965947 |
| Verified | 291,105 | 32.802781 |

Source: [`08_category_rates.csv`](results/08_category_rates.csv).

## 6. Bivariate statistics

### Outcome by category: development only

Rates use resolved loans, not total loans. Each table includes the exact denominator and charged-off count. Verification groups, purposes, and home-ownership groups differ in other variables; these are unadjusted associations, not causal effects or fairness measures.

### application_type: outcome comparison

| Category | Total loans | Resolved loans | Charged-off loans | Charged off among resolved (%) |
| --- | --- | --- | --- | --- |
| Individual | 886,929 | 826,203 | 152,203 | 18.421986 |
| Joint App | 511 | 401 | 99 | 24.688279 |

### grade: outcome comparison

| Category | Total loans | Resolved loans | Charged-off loans | Charged off among resolved (%) |
| --- | --- | --- | --- | --- |
| A | 148,207 | 146,430 | 8,154 | 5.568531 |
| B | 254,553 | 241,510 | 29,063 | 12.03387 |
| C | 245,881 | 225,234 | 45,872 | 20.366375 |
| D | 139,554 | 126,002 | 35,442 | 28.128125 |
| E | 70,707 | 61,870 | 22,739 | 36.752869 |
| F | 23,049 | 20,693 | 8,758 | 42.323491 |
| G | 5,489 | 4,865 | 2,274 | 46.742035 |

### home_ownership: outcome comparison

| Category | Total loans | Resolved loans | Charged-off loans | Charged off among resolved (%) |
| --- | --- | --- | --- | --- |
| ANY | 3 | 3 | 0 | 0 |
| MORTGAGE | 443,591 | 409,456 | 66,741 | 16.29992 |
| NONE | 50 | 45 | 7 | 15.555556 |
| OTHER | 182 | 144 | 27 | 18.75 |
| OWN | 87,478 | 81,421 | 15,464 | 18.992643 |
| RENT | 356,136 | 335,535 | 70,063 | 20.880981 |

### purpose: outcome comparison

| Category | Total loans | Resolved loans | Charged-off loans | Charged off among resolved (%) |
| --- | --- | --- | --- | --- |
| car | 8,864 | 8,473 | 1,135 | 13.395492 |
| credit_card | 206,194 | 190,950 | 29,519 | 15.459021 |
| debt_consolidation | 524,253 | 487,230 | 95,788 | 19.659709 |
| educational | 423 | 326 | 56 | 17.177914 |
| home_improvement | 51,834 | 48,295 | 7,954 | 16.469614 |
| house | 3,707 | 3,530 | 734 | 20.793201 |
| major_purchase | 17,277 | 16,264 | 2,641 | 16.238318 |
| medical | 8,541 | 8,164 | 1,580 | 19.353258 |
| moving | 5,415 | 5,223 | 1,105 | 21.156424 |
| other | 42,896 | 40,825 | 7,942 | 19.453766 |
| renewable_energy | 575 | 558 | 122 | 21.863799 |
| small_business | 10,378 | 9,833 | 2,651 | 26.960236 |
| vacation | 4,736 | 4,642 | 797 | 17.169324 |
| wedding | 2,347 | 2,291 | 278 | 12.134439 |

### verification_status: outcome comparison

| Category | Total loans | Resolved loans | Charged-off loans | Charged off among resolved (%) |
| --- | --- | --- | --- | --- |
| Not Verified | 259,410 | 244,096 | 32,799 | 13.436926 |
| Source Verified | 336,925 | 308,528 | 61,189 | 19.83256 |
| Verified | 291,105 | 273,980 | 58,314 | 21.284035 |

Source: [`08_category_rates.csv`](results/08_category_rates.csv).

### Numeric bands and outcomes: every exported band

Bands are based on **lower boundaries**. FICO width is 20 score points, DTI width is 5, and annual-income width is $20,000. For example, the income band 60,000 represents [60,000, 80,000). NULL feature values are excluded. The CSV includes all bands, including rare/extreme ones; the figure is filtered as described in section 8.

#### annual_inc: all numeric bands

| band | total_loans | resolved_loans | charged_off_loans | charged_off_pct |
| --- | --- | --- | --- | --- |
| 0 | 10,203 | 10,054 | 2,172 | 21.603342 |
| 20,000 | 129,427 | 124,014 | 26,780 | 21.594336 |
| 40,000 | 241,613 | 225,736 | 45,792 | 20.285643 |
| 60,000 | 203,741 | 188,689 | 35,120 | 18.612638 |
| 80,000 | 127,550 | 117,550 | 19,555 | 16.635474 |
| 100,000 | 69,334 | 63,724 | 9,473 | 14.865671 |
| 120,000 | 42,618 | 39,134 | 5,627 | 14.378801 |
| 140,000 | 23,738 | 21,724 | 3,061 | 14.090407 |
| 160,000 | 12,076 | 11,086 | 1,556 | 14.035721 |
| 180,000 | 7,063 | 6,482 | 845 | 13.0361 |
| 200,000 | 5,908 | 5,438 | 682 | 12.541376 |
| 220,000 | 3,181 | 2,941 | 388 | 13.192792 |
| 240,000 | 3,278 | 2,986 | 410 | 13.730743 |
| 260,000 | 1,377 | 1,249 | 147 | 11.769416 |
| 280,000 | 724 | 661 | 87 | 13.161876 |
| 300,000 | 1,464 | 1,363 | 173 | 12.69259 |
| 320,000 | 554 | 498 | 62 | 12.449799 |
| 340,000 | 684 | 632 | 68 | 10.759494 |
| 360,000 | 326 | 298 | 36 | 12.080537 |
| 380,000 | 194 | 178 | 26 | 14.606742 |
| 400,000 | 513 | 466 | 57 | 12.23176 |
| 420,000 | 186 | 168 | 18 | 10.714286 |
| 440,000 | 257 | 238 | 19 | 7.983193 |
| 460,000 | 84 | 77 | 6 | 7.792208 |
| 480,000 | 81 | 77 | 10 | 12.987013 |
| 500,000 | 258 | 236 | 24 | 10.169492 |
| 520,000 | 72 | 68 | 4 | 5.882353 |
| 540,000 | 111 | 95 | 15 | 15.789474 |
| 560,000 | 34 | 31 | 3 | 9.677419 |
| 580,000 | 25 | 21 | 3 | 14.285714 |
| 600,000 | 144 | 126 | 16 | 12.698413 |
| 620,000 | 27 | 24 | 3 | 12.5 |
| 640,000 | 66 | 61 | 3 | 4.918033 |
| 660,000 | 21 | 17 | 1 | 5.882353 |
| 680,000 | 9 | 8 | 1 | 12.5 |
| 700,000 | 64 | 57 | 6 | 10.526316 |
| 720,000 | 17 | 15 | 1 | 6.666667 |
| 740,000 | 55 | 51 | 6 | 11.764706 |
| 760,000 | 11 | 10 | 2 | 20 |
| 780,000 | 13 | 13 | 2 | 15.384615 |
| 800,000 | 36 | 32 | 6 | 18.75 |
| 820,000 | 9 | 8 | 1 | 12.5 |
| 840,000 | 28 | 26 | 3 | 11.538462 |
| 860,000 | 10 | 9 | 1 | 11.111111 |
| 880,000 | 4 | 4 | 0 | 0 |
| 900,000 | 23 | 21 | 2 | 9.52381 |
| 920,000 | 5 | 5 | 2 | 40 |
| 940,000 | 17 | 16 | 2 | 12.5 |
| 960,000 | 5 | 5 | 1 | 20 |
| 980,000 | 14 | 12 | 0 | 0 |
| 1,000,000 | 30 | 26 | 3 | 11.538462 |
| 1,020,000 | 1 | 1 | 1 | 100 |
| 1,040,000 | 3 | 3 | 0 | 0 |
| 1,080,000 | 3 | 3 | 0 | 0 |
| 1,100,000 | 16 | 16 | 1 | 6.25 |
| 1,120,000 | 2 | 2 | 0 | 0 |
| 1,140,000 | 1 | 0 | — | — |
| 1,160,000 | 1 | 1 | 0 | 0 |
| 1,200,000 | 17 | 16 | 1 | 6.25 |
| 1,220,000 | 1 | 1 | 0 | 0 |
| 1,240,000 | 11 | 10 | 2 | 20 |
| 1,280,000 | 1 | 1 | 0 | 0 |
| 1,300,000 | 7 | 7 | 1 | 14.285714 |
| 1,340,000 | 3 | 3 | 0 | 0 |
| 1,360,000 | 2 | 2 | 0 | 0 |
| 1,380,000 | 1 | 0 | — | — |
| 1,400,000 | 3 | 3 | 0 | 0 |
| 1,440,000 | 2 | 1 | 0 | 0 |
| 1,460,000 | 1 | 1 | 0 | 0 |
| 1,500,000 | 11 | 11 | 2 | 18.181818 |
| 1,600,000 | 1 | 1 | 0 | 0 |
| 1,640,000 | 1 | 1 | 1 | 100 |
| 1,700,000 | 2 | 2 | 0 | 0 |
| 1,740,000 | 1 | 1 | 0 | 0 |
| 1,780,000 | 1 | 1 | 0 | 0 |
| 1,800,000 | 2 | 2 | 0 | 0 |
| 1,840,000 | 1 | 1 | 0 | 0 |
| 1,900,000 | 3 | 2 | 0 | 0 |
| 1,940,000 | 1 | 1 | 0 | 0 |
| 2,000,000 | 5 | 5 | 0 | 0 |
| 2,020,000 | 1 | 1 | 0 | 0 |
| 2,100,000 | 2 | 1 | 1 | 100 |
| 2,140,000 | 1 | 1 | 1 | 100 |
| 2,240,000 | 1 | 1 | 0 | 0 |
| 2,300,000 | 2 | 2 | 0 | 0 |
| 2,500,000 | 1 | 1 | 0 | 0 |
| 2,540,000 | 1 | 1 | 1 | 100 |
| 2,840,000 | 1 | 1 | 0 | 0 |
| 3,000,000 | 2 | 2 | 1 | 50 |
| 3,120,000 | 1 | 1 | 0 | 0 |
| 3,200,000 | 1 | 1 | 1 | 100 |
| 3,900,000 | 1 | 1 | 0 | 0 |
| 3,960,000 | 1 | 1 | 0 | 0 |
| 4,000,000 | 1 | 1 | 0 | 0 |
| 4,300,000 | 2 | 2 | 1 | 50 |
| 4,560,000 | 1 | 0 | — | — |
| 4,640,000 | 1 | 1 | 0 | 0 |
| 4,680,000 | 1 | 1 | 0 | 0 |
| 4,800,000 | 1 | 1 | 1 | 100 |
| 4,900,000 | 1 | 1 | 0 | 0 |
| 5,000,000 | 4 | 3 | 0 | 0 |
| 6,000,000 | 4 | 3 | 0 | 0 |
| 6,100,000 | 1 | 1 | 0 | 0 |
| 7,000,000 | 2 | 2 | 0 | 0 |
| 7,140,000 | 1 | 1 | 0 | 0 |
| 7,440,000 | 1 | 1 | 0 | 0 |
| 7,500,000 | 1 | 1 | 1 | 100 |
| 7,600,000 | 1 | 1 | 0 | 0 |
| 8,120,000 | 1 | 1 | 0 | 0 |
| 8,240,000 | 1 | 1 | 0 | 0 |
| 8,500,000 | 1 | 1 | 0 | 0 |
| 8,700,000 | 2 | 2 | 1 | 50 |
| 8,900,000 | 1 | 1 | 1 | 100 |
| 9,000,000 | 1 | 1 | 0 | 0 |
| 9,500,000 | 1 | 1 | 1 | 100 |

#### dti: all numeric bands

| band | total_loans | resolved_loans | charged_off_loans | charged_off_pct |
| --- | --- | --- | --- | --- |
| 0 | 41,178 | 39,469 | 5,004 | 12.678304 |
| 5 | 116,616 | 111,138 | 15,164 | 13.644298 |
| 10 | 181,337 | 170,846 | 26,214 | 15.343643 |
| 15 | 194,139 | 181,373 | 32,217 | 17.762842 |
| 20 | 162,806 | 150,668 | 30,550 | 20.276369 |
| 25 | 110,118 | 101,300 | 23,260 | 22.9615 |
| 30 | 60,650 | 54,162 | 14,400 | 26.586906 |
| 35 | 20,506 | 17,577 | 5,477 | 31.160039 |
| 40 | 29 | 22 | 4 | 18.181818 |
| 45 | 17 | 14 | 4 | 28.571429 |
| 50 | 7 | 7 | 3 | 42.857143 |
| 55 | 8 | 5 | 1 | 20 |
| 60 | 5 | 4 | 2 | 50 |
| 65 | 4 | 4 | 1 | 25 |
| 70 | 4 | 1 | 0 | 0 |
| 75 | 1 | 0 | — | — |
| 80 | 2 | 2 | 0 | 0 |
| 85 | 1 | 1 | 0 | 0 |
| 90 | 1 | 1 | 0 | 0 |
| 100 | 2 | 2 | 0 | 0 |
| 120 | 1 | 1 | 0 | 0 |
| 125 | 1 | 1 | 0 | 0 |
| 135 | 2 | 1 | 0 | 0 |
| 380 | 1 | 1 | 0 | 0 |
| 670 | 1 | 1 | 0 | 0 |
| 995 | 1 | 1 | 0 | 0 |

#### fico_mid: all numeric bands

| band | total_loans | resolved_loans | charged_off_loans | charged_off_pct |
| --- | --- | --- | --- | --- |
| 600 | 3 | 0 | — | — |
| 620 | 14 | 2 | 0 | 0 |
| 640 | 472 | 0 | — | — |
| 660 | 306,372 | 286,809 | 66,674 | 23.24683 |
| 680 | 246,124 | 228,593 | 45,060 | 19.71189 |
| 700 | 164,484 | 151,880 | 23,865 | 15.713063 |
| 720 | 85,371 | 79,133 | 9,925 | 12.542176 |
| 740 | 41,469 | 39,097 | 3,914 | 10.010998 |
| 760 | 22,345 | 21,234 | 1,685 | 7.935387 |
| 780 | 12,822 | 12,256 | 785 | 6.405026 |
| 800 | 6,038 | 5,756 | 314 | 5.455177 |
| 820 | 1,729 | 1,654 | 70 | 4.232164 |
| 840 | 197 | 190 | 10 | 5.263158 |

Source: [`10_numeric_rates.csv`](results/10_numeric_rates.csv).

## 7. Multivariate statistics

### Grade × term × outcome: development only

`mean_interest_rate` is the mean over all available loans in the cell, including unresolved loans. `charged_off_pct` uses resolved loans only. Do not treat their denominators as interchangeable.

| grade | term_months | total_loans | resolved_loans | charged_off_pct | mean_interest_rate |
| --- | --- | --- | --- | --- | --- |
| A | 36 | 143,020 | 142,911 | 5.475436 | 7.215795 |
| A | 60 | 5,187 | 3,519 | 9.349247 | 7.997852 |
| B | 36 | 212,025 | 211,634 | 11.191963 | 10.863927 |
| B | 60 | 42,528 | 29,876 | 17.997724 | 10.655488 |
| C | 36 | 162,436 | 161,809 | 17.913095 | 13.921118 |
| C | 60 | 83,445 | 63,425 | 26.625148 | 14.090379 |
| D | 36 | 76,692 | 76,045 | 23.326977 | 17.160809 |
| D | 60 | 62,862 | 49,957 | 35.436475 | 17.187538 |
| E | 36 | 21,843 | 21,403 | 28.566089 | 19.764 |
| E | 60 | 48,864 | 40,467 | 41.082858 | 19.951345 |
| F | 36 | 4,467 | 4,263 | 32.817265 | 23.325301 |
| F | 60 | 18,582 | 16,430 | 44.790018 | 23.638221 |
| G | 36 | 686 | 519 | 39.884393 | 23.953732 |
| G | 60 | 4,803 | 4,346 | 47.560976 | 25.857402 |

Source: [`11_grade_term.csv`](results/11_grade_term.csv).

### Grade × issue year × outcome: development only

The figure masks rate cells with fewer than 200 resolved loans. This table retains every exported group and its counts, so rare cells remain auditable.

| issue_year | grade | total_loans | resolved_loans | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- |
| 2,007 | A | 78 | 57 | 73.076923 | 1.754386 |
| 2,007 | B | 98 | 61 | 62.244898 | 13.114754 |
| 2,007 | C | 141 | 75 | 53.191489 | 18.666667 |
| 2,007 | D | 99 | 37 | 37.373737 | 40.540541 |
| 2,007 | E | 100 | 14 | 14 | 35.714286 |
| 2,007 | F | 52 | 7 | 13.461538 | 28.571429 |
| 2,007 | G | 35 | 0 | 0 | — |
| 2,008 | A | 318 | 295 | 92.767296 | 5.762712 |
| 2,008 | B | 594 | 507 | 85.353535 | 14.595661 |
| 2,008 | C | 580 | 438 | 75.517241 | 17.808219 |
| 2,008 | D | 419 | 222 | 52.983294 | 24.324324 |
| 2,008 | E | 285 | 75 | 26.315789 | 16 |
| 2,008 | F | 111 | 21 | 18.918919 | 47.619048 |
| 2,008 | G | 86 | 4 | 4.651163 | 50 |
| 2,009 | A | 1,203 | 1,178 | 97.921862 | 6.706282 |
| 2,009 | B | 1,445 | 1,365 | 94.463668 | 11.428571 |
| 2,009 | C | 1,348 | 1,193 | 88.501484 | 14.752724 |
| 2,009 | D | 817 | 657 | 80.416157 | 17.199391 |
| 2,009 | E | 308 | 236 | 76.623377 | 21.610169 |
| 2,009 | F | 105 | 64 | 60.952381 | 17.1875 |
| 2,009 | G | 55 | 23 | 41.818182 | 34.782609 |
| 2,010 | A | 2,830 | 2,801 | 98.975265 | 4.748304 |
| 2,010 | B | 3,687 | 3,537 | 95.931652 | 11.393837 |
| 2,010 | C | 2,729 | 2,463 | 90.25284 | 14.819326 |
| 2,010 | D | 1,885 | 1,613 | 85.570292 | 18.784873 |
| 2,010 | E | 962 | 794 | 82.536383 | 23.425693 |
| 2,010 | F | 311 | 240 | 77.170418 | 30 |
| 2,010 | G | 133 | 88 | 66.165414 | 28.409091 |
| 2,011 | A | 5,754 | 5,754 | 100 | 6.465068 |
| 2,011 | B | 6,565 | 6,565 | 100 | 12.063976 |
| 2,011 | C | 3,942 | 3,942 | 100 | 18.340944 |
| 2,011 | D | 2,796 | 2,796 | 100 | 23.06867 |
| 2,011 | E | 1,739 | 1,739 | 100 | 27.084531 |
| 2,011 | F | 722 | 722 | 100 | 31.578947 |
| 2,011 | G | 203 | 203 | 100 | 32.512315 |
| 2,012 | A | 10,901 | 10,901 | 100 | 7.237868 |
| 2,012 | B | 18,507 | 18,507 | 100 | 12.968066 |
| 2,012 | C | 11,875 | 11,875 | 100 | 18.4 |
| 2,012 | D | 7,323 | 7,323 | 100 | 23.473986 |
| 2,012 | E | 3,185 | 3,185 | 100 | 30.706436 |
| 2,012 | F | 1,315 | 1,315 | 100 | 35.361217 |
| 2,012 | G | 261 | 261 | 100 | 41.37931 |
| 2,013 | A | 17,679 | 17,679 | 100 | 4.700492 |
| 2,013 | B | 44,116 | 44,115 | 99.997733 | 10.17341 |
| 2,013 | C | 38,134 | 38,130 | 99.989511 | 17.521637 |
| 2,013 | D | 20,569 | 20,566 | 99.985415 | 22.367014 |
| 2,013 | E | 9,059 | 9,059 | 100 | 28.502042 |
| 2,013 | F | 4,393 | 4,392 | 99.977237 | 34.836066 |
| 2,013 | G | 864 | 863 | 99.884259 | 36.152955 |
| 2,014 | A | 36,108 | 35,875 | 99.354714 | 5.427178 |
| 2,014 | B | 61,935 | 59,937 | 96.774037 | 11.366935 |
| 2,014 | C | 66,565 | 62,502 | 93.896192 | 19.517775 |
| 2,014 | D | 42,992 | 39,308 | 91.430964 | 27.304874 |
| 2,014 | E | 20,121 | 18,233 | 90.616769 | 35.633193 |
| 2,014 | F | 6,223 | 5,720 | 91.917082 | 39.265734 |
| 2,014 | G | 1,685 | 1,527 | 90.623145 | 47.544204 |
| 2,015 | A | 73,336 | 71,890 | 98.028254 | 5.543191 |
| 2,015 | B | 117,606 | 106,916 | 90.910328 | 13.027985 |
| 2,015 | C | 120,567 | 104,616 | 86.770012 | 22.416265 |
| 2,015 | D | 62,654 | 53,480 | 85.357679 | 32.273747 |
| 2,015 | E | 34,948 | 28,535 | 81.64988 | 41.902926 |
| 2,015 | F | 9,817 | 8,212 | 83.65081 | 51.071603 |
| 2,015 | G | 2,167 | 1,896 | 87.494232 | 54.166667 |

Source: [`12_grade_cohort.csv`](results/12_grade_cohort.csv).

### Pearson feature correlation matrix: development only

Calculated on untrimmed numeric values with pairwise NULL exclusion. These are Pearson linear correlations, not Spearman rank correlations, model coefficients, feature importances, or causal effects. Pairwise sample sizes were not exported. Diagonal values are 1 within floating-point precision; rounding displays them as 1.

| Feature | annual_inc | credit_history_years | dti | fico_mid | int_rate | loan_amnt | revol_util |
| --- | --- | --- | --- | --- | --- | --- | --- |
| annual_inc | 1 | 0.150729 | -0.175503 | 0.081159 | -0.072709 | 0.332697 | 0.036724 |
| credit_history_years | 0.150729 | 1 | 0.051626 | 0.10171 | -0.116078 | 0.186029 | 0.003422 |
| dti | -0.175503 | 0.051626 | 1 | -0.086243 | 0.162126 | 0.043177 | 0.177561 |
| fico_mid | 0.081159 | 0.10171 | -0.086243 | 1 | -0.431483 | 0.115446 | -0.441845 |
| int_rate | -0.072709 | -0.116078 | 0.162126 | -0.431483 | 1 | 0.144843 | 0.268987 |
| loan_amnt | 0.332697 | 0.186029 | 0.043177 | 0.115446 | 0.144843 | 1 | 0.119559 |
| revol_util | 0.036724 | 0.003422 | 0.177561 | -0.441845 | 0.268987 | 0.119559 | 1 |

Source: [`13_correlations.csv`](results/13_correlations.csv).

### Largest absolute correlations, excluding diagonal and mirrored pairs

| feature_x | feature_y | correlation |
| --- | --- | --- |
| fico_mid | revol_util | -0.441845 |
| fico_mid | int_rate | -0.431483 |
| annual_inc | loan_amnt | 0.332697 |
| int_rate | revol_util | 0.268987 |
| credit_history_years | loan_amnt | 0.186029 |
| dti | revol_util | 0.177561 |
| annual_inc | dti | -0.175503 |
| dti | int_rate | 0.162126 |
| annual_inc | credit_history_years | 0.150729 |
| int_rate | loan_amnt | 0.144843 |

## 8. Figures, sampling, and display rules

There are **11 figure sets**, each saved as PNG and SVG, for **22 image files**. PNG resolution is 160 DPI. Full-data distributions and rates are calculated in SQL; only the scatterplots are sampled.

| Figure | Scope / rule |
| --- | --- |
| [01_raw_missingness](figures/01_raw_missingness.png) | 25 source columns with the highest missing percentage; all raw rows. |
| [02_status_and_followup](figures/02_status_and_followup.png) | All-year status counts and outcome coverage by year/term. |
| [03_numeric_distributions](figures/03_numeric_distributions.png) | Development histograms. Income, DTI, and utilization views end at their development p99; no underlying rows are removed. |
| [04_category_counts](figures/04_category_counts.png) | Development grade, purpose, and home-ownership counts, including unresolved loans. |
| [05_outcomes_and_grade](figures/05_outcomes_and_grade.png) | Development outcome balance and resolved-loan charged-off share by grade, with denominators. |
| [06_category_outcomes](figures/06_category_outcomes.png) | Purpose/home-ownership charged-off shares with resolved denominators; dashed line is the overall development resolved-loan rate. |
| [07_numeric_outcomes](figures/07_numeric_outcomes.png) | FICO, DTI, and income band rates; at least 200 resolved loans per plotted band. Band lower bounds limited to 850, 60, and 200,000 respectively. |
| [08_grade_term_outcomes](figures/08_grade_term_outcomes.png) | Grade/term rate heatmap and resolved-count heatmap. Rate cells require 200 resolved loans. |
| [09_grade_cohort_outcomes](figures/09_grade_cohort_outcomes.png) | Development grade/year rates and coverage heatmaps. Rate cells require 200 resolved loans. |
| [10_feature_correlations](figures/10_feature_correlations.png) | Pearson correlations across seven development features; all available pairs, no trimming. |
| [11_sampled_relationships](figures/11_sampled_relationships.png) | FICO vs interest and income vs loan amount, colored by outcome. Deterministic sample of resolved development loans; income view ends at development p99. |

### Scatterplot sample

Selection SQL: `FROM eda_loans WHERE charged_off IS NOT NULL ORDER BY hash(loan_id, 42) LIMIT 20000`. This is a deterministic hash ordering, not class balancing or a stratified sample. It is repeatable for this dataset and DuckDB implementation; hash behavior is not guaranteed across engine versions. The full-data rates are not estimated from this sample.

| Label | Outcome | Sample loans | Share of sample (%) |
| --- | --- | --- | --- |
| 0 | Fully Paid | 16,304 | 81.52 |
| 1 | Charged Off | 3,696 | 18.48 |

Source: [`scatter_sample_counts.csv`](results/scatter_sample_counts.csv).

Histogram widths: loan amount $1,000; annual income $10,000; FICO midpoint 10 points; interest rate 1 percentage point; DTI and revolving utilization 5 points. A bin starts at `floor(value / width) × width`. Complete exported bin counts appear in section 13.

## 9. Model experiments and evaluation

**Historical EDA-stage snapshot.** The original metric register below predates training. Current measured model results, fitted pipelines, and selection decisions are recorded in section 18. An empty model folder is not evidence of measured zero-valued metrics.

The following is a record of missing measurements to fill after actual runs, not a claim that all listed evaluations have been configured.

| Measurement | Current value / status |
| --- | --- |
| Prediction target / horizon | Not finalized; EDA uses resolved-loan labels only |
| Final maturity / censoring rule | Not finalized |
| Final feature list and number of predictors | Not finalized |
| Final training / validation / test labeled row counts | Not measured; provisional all-loan split counts are in section 1 |
| Dataset version / fingerprint for training | Not recorded |
| MLflow experiment ID, run ID, model version | Not recorded |
| Algorithm, hyperparameters, seed, feature transforms | Not fitted |
| ROC-AUC | Not measured |
| PR-AUC / average precision | Not measured; record the exact definition, as these are not interchangeable |
| Accuracy, precision, recall, specificity, F1 | Not measured |
| Threshold and confusion matrix TP / FP / TN / FN | Not selected / measured |
| Brier score, log loss, calibration curve / error | Not measured |
| Baseline and improvement over baseline | No model comparison; only the arithmetic majority-label reference in section 4 |
| Approval / rejection rate and bad rate at a policy threshold | Not measured; hypothetical policy assumptions must be documented |
| Expected loss / cost / savings | Not estimated; no LGD, exposure, or decision-cost assumptions fixed |
| Training duration, memory, artifact size, inference latency | Not measured |
| Confidence intervals and performance by cohort | Not measured |

When results exist, record separate metrics for each model and each split, the positive class, probability/decision threshold, exact sample sizes, preprocessing version, MLflow run link/ID, and measurement date. Never present development EDA rates as test performance. Confidence intervals and significance tests were not computed in this EDA stage.

## 10. Interpretability and bias evaluation

**Current state: InterpretML and bias evaluation have not been run.** No feature weights, local explanations, subgroup error rates, or fairness conclusions have been measured.

| Measurement | Current value / status |
| --- | --- |
| InterpretML explainer / model / package version | Not measured |
| Global contributions / importances and direction of association | Not measured |
| Local prediction explanations and representative example IDs | Not measured |
| Subgroup definitions, protected-attribute availability, subgroup sample sizes | Not measured |
| Subgroup positive rate, predicted approval rate, actual outcome rate | Not measured |
| Subgroup TP / FP / TN / FN, TPR, FPR, FNR, precision, and calibration | Not measured |
| Between-group differences / ratios, uncertainty, and selected reference group | Not measured |
| Models with vs without assigned grade / interest rate | Not measured |

Explanations describe model behavior; they do not establish fairness. Home ownership, location, and loan-purpose charts are not protected-demographic fairness evaluations. Accepted-only data limits generalization and can introduce selection bias. A review must establish what attributes are actually available and suitable before choosing subgroup metrics.

## 11. Kafka stress testing and ELK monitoring

**Current state: Kafka, model serving, load generation, and ELK monitoring have not been implemented or benchmarked.** No traffic was generated; no stress-test metric has been recorded. No latency, throughput, reliability, or scaling claim can be made yet.

### Workload and infrastructure metadata

| Required context | Current value / status |
| --- | --- |
| Benchmark ID, timestamp, code revision, and selected model version | Not configured / recorded |
| CPU / memory allocation, host or container limits, hardware topology | Not configured / recorded |
| Kafka version, broker count, replication factor, partition count | Not configured / recorded |
| Producer configuration: acks, batching, compression, retries, idempotence | Not configured / recorded |
| Consumer groups, consumer count, concurrency, offset commit policy | Not configured / recorded |
| Application event schema, payload size distribution, event ID handling | Not configured / recorded |
| Offered event rate, ramp pattern, burst size, test duration, warm-up | Not configured / recorded |
| Latency clock source, timestamps, measurement boundaries, units | Not configured / recorded |
| Success criterion / latency SLO / tolerated error and loss rate | Not configured / recorded |

### Performance and reliability measurement register

| Measurement | Definition / reporting requirement | Current result |
| --- | --- | --- |
| Offered throughput (events/s) | Events attempted / measurement seconds | Not measured |
| Broker-acknowledged throughput (events/s) | Successfully acknowledged input events / measurement seconds | Not measured |
| Completed prediction throughput (events/s) | Successfully completed distinct predictions / measurement seconds | Not measured |
| End-to-end latency p50 / p90 / p95 / p99 / maximum (ms) | Quantiles from input event timestamp to published/available prediction; state the exact boundary | Not measured |
| Model-only inference latency (ms) | Separate scoring time from queue and transport delay | Not measured |
| Producer acknowledgement latency (ms) | Time to acknowledgement under the selected durability setting | Not measured |
| Consumer lag: average / p95 / maximum | Record units and aggregation: offset backlog per partition and/or event-time lag | Not measured |
| Event count reconciliation | Attempted, acknowledged, consumed, predicted, failed, retried, duplicate, and dead-letter counts | Not measured |
| Error / timeout rate (%) | Failures / explicitly defined attempted or acknowledged population; state denominator | Not measured |
| Duplicate and deduplication counts | Repeated event IDs observed and successfully suppressed | Not measured |
| Unaccounted acknowledged events / loss rate | Reconcile acknowledged unique inputs to terminal outputs after draining and accounting for in-flight events | Not measured |
| CPU / memory / network / disk utilization | Measure producer, brokers, consumers, and serving processes separately | Not measured |
| Maximum sustainable load | Highest sustained offered load meeting a declared latency/error/lag criterion | Not measured |
| Backlog drain time (s) | Time from traffic reduction/stop until lag reaches the declared baseline | Not measured |
| Failure recovery time (s) | Time from injected failure to the declared healthy state | Not measured |
| Post-restart replay / duplicate / missing counts | Record offset handling and idempotency behavior | Not measured |
| ELK ingestion delay and dropped log count | Application event timestamp to searchable log record; account for delivery gaps | Not measured |

### Scenario register

| Scenario | Status |
| --- | --- |
| Steady baseline traffic | Not run |
| Sustained load ramp | Not run |
| Sudden burst / overload | Not run |
| Consumer termination and restart | Not run |
| Broker interruption and recovery | Not run |
| Malformed application event | Not run |
| Duplicate event delivery / replay | Not run |
| Backlog drain after a burst | Not run |
| Long-running soak test | Not run |

ELK will store and visualize logs and calculated metrics; logging alone does not compute model drift, fairness, or predictive performance. Drift baselines/windows, thresholds, delayed-label coverage, alert rules, and dashboard links are **not configured**. Economic credit-risk stress scenarios are also **not designed or measured**; Kafka traffic testing evaluates serving-system behavior, not economic portfolio stress.

## 12. Artifacts, environment, and verification

### Execution settings

- Analysis engine: DuckDB; SQL files run from a marimo Python notebook.
- DuckDB configured memory limit: `1GB`; threads: `4`. These are settings, not measured peak memory or CPU usage.
- Source read: `header = true`, `all_varchar = true`, `sample_size = 20000`. The reader's sampling configuration is not a 20,000-row cap on analysis; the full CSV is processed.
- Clean export: Parquet with ZSTD compression.
- Plot style: seaborn `whitegrid`, colorblind palette; notebook figure DPI 110, saved PNG DPI 160.
- Total runtime, peak process memory, and SQL query durations were not captured.
- Installed versions below were inspected while assembling this reference; dependencies are not a complete pinned environment lockfile.

| Component | Installed version |
| --- | --- |
| Python | 3.14.9 |
| duckdb | 2.0.0 |
| marimo | 0.25.2 |
| pandas | 3.1.0 |
| matplotlib | 3.11.2 |
| seaborn | 0.13.2 |
| kagglehub | Not installed in the inspected environment |

### Artifact inventory and exact file sizes

| Artifact | Bytes | MiB (bytes / 1,048,576) |
| --- | --- | --- |
| [data/raw/accepted_2007_to_2018Q4.csv.gz](../data/raw/accepted_2007_to_2018Q4.csv.gz) | 392,582,231 | 374.395591 |
| [data/raw/accepted_2007_to_2018Q4.csv](../data/raw/accepted_2007_to_2018Q4.csv) | 1,675,133,810 | 1,597.532091 |
| [data/clean/lending_club.duckdb](../data/clean/lending_club.duckdb) | 154,152,960 | 147.011719 |
| [data/clean/loans.parquet](../data/clean/loans.parquet) | 49,162,607 | 46.885116 |
| [docs/data_analysis.html](../docs/data_analysis.html) | 4,429,065 | 4.223886 |
| [assets/figures/01_raw_missingness.png](figures/01_raw_missingness.png) | 139,405 | 0.132947 |
| [assets/figures/02_status_and_followup.png](figures/02_status_and_followup.png) | 148,210 | 0.141344 |
| [assets/figures/03_numeric_distributions.png](figures/03_numeric_distributions.png) | 190,714 | 0.181879 |
| [assets/figures/04_category_counts.png](figures/04_category_counts.png) | 104,085 | 0.099263 |
| [assets/figures/05_outcomes_and_grade.png](figures/05_outcomes_and_grade.png) | 96,043 | 0.091594 |
| [assets/figures/06_category_outcomes.png](figures/06_category_outcomes.png) | 139,544 | 0.13308 |
| [assets/figures/07_numeric_outcomes.png](figures/07_numeric_outcomes.png) | 154,156 | 0.147015 |
| [assets/figures/08_grade_term_outcomes.png](figures/08_grade_term_outcomes.png) | 115,665 | 0.110307 |
| [assets/figures/09_grade_cohort_outcomes.png](figures/09_grade_cohort_outcomes.png) | 223,633 | 0.213273 |
| [assets/figures/10_feature_correlations.png](figures/10_feature_correlations.png) | 126,013 | 0.120175 |
| [assets/figures/11_sampled_relationships.png](figures/11_sampled_relationships.png) | 756,753 | 0.721696 |
| [assets/figures/01_raw_missingness.svg](figures/01_raw_missingness.svg) | 78,645 | 0.075002 |
| [assets/figures/02_status_and_followup.svg](figures/02_status_and_followup.svg) | 69,971 | 0.06673 |
| [assets/figures/03_numeric_distributions.svg](figures/03_numeric_distributions.svg) | 129,404 | 0.123409 |
| [assets/figures/04_category_counts.svg](figures/04_category_counts.svg) | 65,884 | 0.062832 |
| [assets/figures/05_outcomes_and_grade.svg](figures/05_outcomes_and_grade.svg) | 57,101 | 0.054456 |
| [assets/figures/06_category_outcomes.svg](figures/06_category_outcomes.svg) | 75,154 | 0.071672 |
| [assets/figures/07_numeric_outcomes.svg](figures/07_numeric_outcomes.svg) | 61,487 | 0.058639 |
| [assets/figures/08_grade_term_outcomes.svg](figures/08_grade_term_outcomes.svg) | 63,919 | 0.060958 |
| [assets/figures/09_grade_cohort_outcomes.svg](figures/09_grade_cohort_outcomes.svg) | 121,965 | 0.116315 |
| [assets/figures/10_feature_correlations.svg](figures/10_feature_correlations.svg) | 72,978 | 0.069597 |
| [assets/figures/11_sampled_relationships.svg](figures/11_sampled_relationships.svg) | 541,879 | 0.516776 |
| [assets/results/.gitkeep](results/.gitkeep) | 0 | 0 |
| [assets/results/01_raw_audit.csv](results/01_raw_audit.csv) | 130 | 0.000124 |
| [assets/results/02_raw_missingness.csv](results/02_raw_missingness.csv) | 6,234 | 0.005945 |
| [assets/results/04_cleaning_audit.csv](results/04_cleaning_audit.csv) | 157 | 0.00015 |
| [assets/results/05_status_coverage.csv](results/05_status_coverage.csv) | 451 | 0.00043 |
| [assets/results/06_numeric_summary.csv](results/06_numeric_summary.csv) | 593 | 0.000566 |
| [assets/results/07_distributions.csv](results/07_distributions.csv) | 8,339 | 0.007953 |
| [assets/results/08_category_rates.csv](results/08_category_rates.csv) | 1,828 | 0.001743 |
| [assets/results/09_cohorts.csv](results/09_cohorts.csv) | 1,201 | 0.001145 |
| [assets/results/10_numeric_rates.csv](results/10_numeric_rates.csv) | 6,127 | 0.005843 |
| [assets/results/11_grade_term.csv](results/11_grade_term.csv) | 830 | 0.000792 |
| [assets/results/12_grade_cohort.csv](results/12_grade_cohort.csv) | 3,103 | 0.002959 |
| [assets/results/13_correlations.csv](results/13_correlations.csv) | 2,063 | 0.001967 |
| [assets/results/analysis_findings.md](results/analysis_findings.md) | 2,126 | 0.002028 |
| [assets/results/cleaning_summary.csv](results/cleaning_summary.csv) | 108 | 0.000103 |
| [assets/results/development_outcomes.csv](results/development_outcomes.csv) | 76 | 0.000072 |
| [assets/results/scatter_sample_counts.csv](results/scatter_sample_counts.csv) | 40 | 0.000038 |

Sizes are a local filesystem snapshot, not model inference costs or runtime measurements. The DuckDB database may change physical size after checkpointing without changing logical rows. Raw/clean data and model artifacts are ignored by Git; summary CSVs, figures, and the HTML report are available for the showcase.

### Completed verification

The previous analysis run completed all notebook cells and exported the HTML report successfully. Verification checked:

- Raw numeric IDs had zero duplicates before cleaning.
- Clean row count equaled distinct clean loan IDs.
- Clean DuckDB and Parquet row counts both equaled **2,260,668**.
- No non-NULL binary outcome contradicted its exact `Fully Paid` / `Charged Off` status.
- Each exported histogram's counts summed to that feature's nonmissing development count.
- All **11 PNG and 11 SVG** files were present.
- Representative grade/outcome and grade/term figures were visually inspected.
- Python syntax compilation and Git whitespace checks passed.

The standalone `marimo check` lint command did not finish in the environment (a bounded attempt timed out). This does not replace or negate the successful full notebook execution, but a lint pass is not claimed.

## 13. Complete SQL histogram bins

These are **every saved histogram bin**, not just the visible figure range. Columns are bin lower bound, width, and loan count. The upper bound is exclusive. Rows with NULL feature values have no numeric bin. Counts sum to the nonmissing totals in section 5.

### annual_inc: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 0 | 10,000 | 511 |
| 10,000 | 10,000 | 9,692 |
| 20,000 | 10,000 | 40,330 |
| 30,000 | 10,000 | 89,097 |
| 40,000 | 10,000 | 120,958 |
| 50,000 | 10,000 | 120,655 |
| 60,000 | 10,000 | 112,531 |
| 70,000 | 10,000 | 91,210 |
| 80,000 | 10,000 | 72,584 |
| 90,000 | 10,000 | 54,966 |
| 100,000 | 10,000 | 42,480 |
| 110,000 | 10,000 | 26,854 |
| 120,000 | 10,000 | 27,418 |
| 130,000 | 10,000 | 15,200 |
| 140,000 | 10,000 | 11,479 |
| 150,000 | 10,000 | 12,259 |
| 160,000 | 10,000 | 6,769 |
| 170,000 | 10,000 | 5,307 |
| 180,000 | 10,000 | 4,735 |
| 190,000 | 10,000 | 2,328 |
| 200,000 | 10,000 | 4,339 |
| 210,000 | 10,000 | 1,569 |
| 220,000 | 10,000 | 2,179 |
| 230,000 | 10,000 | 1,002 |
| 240,000 | 10,000 | 1,136 |
| 250,000 | 10,000 | 2,142 |
| 260,000 | 10,000 | 625 |
| 270,000 | 10,000 | 752 |
| 280,000 | 10,000 | 477 |
| 290,000 | 10,000 | 247 |
| 300,000 | 10,000 | 1,256 |
| 310,000 | 10,000 | 208 |
| 320,000 | 10,000 | 392 |
| 330,000 | 10,000 | 162 |
| 340,000 | 10,000 | 141 |
| 350,000 | 10,000 | 543 |
| 360,000 | 10,000 | 175 |
| 370,000 | 10,000 | 151 |
| 380,000 | 10,000 | 118 |
| 390,000 | 10,000 | 76 |
| 400,000 | 10,000 | 448 |
| 410,000 | 10,000 | 65 |
| 420,000 | 10,000 | 128 |
| 430,000 | 10,000 | 58 |
| 440,000 | 10,000 | 44 |
| 450,000 | 10,000 | 213 |
| 460,000 | 10,000 | 31 |
| 470,000 | 10,000 | 53 |
| 480,000 | 10,000 | 53 |
| 490,000 | 10,000 | 28 |
| 500,000 | 10,000 | 236 |
| 510,000 | 10,000 | 22 |
| 520,000 | 10,000 | 52 |
| 530,000 | 10,000 | 20 |
| 540,000 | 10,000 | 29 |
| 550,000 | 10,000 | 82 |
| 560,000 | 10,000 | 19 |
| 570,000 | 10,000 | 15 |
| 580,000 | 10,000 | 17 |
| 590,000 | 10,000 | 8 |
| 600,000 | 10,000 | 136 |
| 610,000 | 10,000 | 8 |
| 620,000 | 10,000 | 17 |
| 630,000 | 10,000 | 10 |
| 640,000 | 10,000 | 7 |
| 650,000 | 10,000 | 59 |
| 660,000 | 10,000 | 9 |
| 670,000 | 10,000 | 12 |
| 680,000 | 10,000 | 4 |
| 690,000 | 10,000 | 5 |
| 700,000 | 10,000 | 59 |
| 710,000 | 10,000 | 5 |
| 720,000 | 10,000 | 14 |
| 730,000 | 10,000 | 3 |
| 740,000 | 10,000 | 4 |
| 750,000 | 10,000 | 51 |
| 760,000 | 10,000 | 7 |
| 770,000 | 10,000 | 4 |
| 780,000 | 10,000 | 11 |
| 790,000 | 10,000 | 2 |
| 800,000 | 10,000 | 36 |
| 820,000 | 10,000 | 5 |
| 830,000 | 10,000 | 4 |
| 840,000 | 10,000 | 5 |
| 850,000 | 10,000 | 23 |
| 860,000 | 10,000 | 4 |
| 870,000 | 10,000 | 6 |
| 880,000 | 10,000 | 1 |
| 890,000 | 10,000 | 3 |
| 900,000 | 10,000 | 23 |
| 920,000 | 10,000 | 3 |
| 930,000 | 10,000 | 2 |
| 940,000 | 10,000 | 2 |
| 950,000 | 10,000 | 15 |
| 960,000 | 10,000 | 3 |
| 970,000 | 10,000 | 2 |
| 980,000 | 10,000 | 9 |
| 990,000 | 10,000 | 5 |
| 1,000,000 | 10,000 | 30 |
| 1,030,000 | 10,000 | 1 |
| 1,050,000 | 10,000 | 3 |
| 1,080,000 | 10,000 | 2 |
| 1,090,000 | 10,000 | 1 |
| 1,100,000 | 10,000 | 15 |
| 1,110,000 | 10,000 | 1 |
| 1,120,000 | 10,000 | 1 |
| 1,130,000 | 10,000 | 1 |
| 1,150,000 | 10,000 | 1 |
| 1,170,000 | 10,000 | 1 |
| 1,200,000 | 10,000 | 17 |
| 1,230,000 | 10,000 | 1 |
| 1,240,000 | 10,000 | 2 |
| 1,250,000 | 10,000 | 9 |
| 1,280,000 | 10,000 | 1 |
| 1,300,000 | 10,000 | 7 |
| 1,350,000 | 10,000 | 3 |
| 1,360,000 | 10,000 | 1 |
| 1,370,000 | 10,000 | 1 |
| 1,380,000 | 10,000 | 1 |
| 1,400,000 | 10,000 | 3 |
| 1,440,000 | 10,000 | 2 |
| 1,470,000 | 10,000 | 1 |
| 1,500,000 | 10,000 | 10 |
| 1,510,000 | 10,000 | 1 |
| 1,600,000 | 10,000 | 1 |
| 1,650,000 | 10,000 | 1 |
| 1,700,000 | 10,000 | 2 |
| 1,750,000 | 10,000 | 1 |
| 1,780,000 | 10,000 | 1 |
| 1,800,000 | 10,000 | 2 |
| 1,840,000 | 10,000 | 1 |
| 1,900,000 | 10,000 | 3 |
| 1,950,000 | 10,000 | 1 |
| 2,000,000 | 10,000 | 5 |
| 2,030,000 | 10,000 | 1 |
| 2,100,000 | 10,000 | 2 |
| 2,140,000 | 10,000 | 1 |
| 2,250,000 | 10,000 | 1 |
| 2,300,000 | 10,000 | 2 |
| 2,500,000 | 10,000 | 1 |
| 2,540,000 | 10,000 | 1 |
| 2,850,000 | 10,000 | 1 |
| 3,000,000 | 10,000 | 2 |
| 3,120,000 | 10,000 | 1 |
| 3,200,000 | 10,000 | 1 |
| 3,900,000 | 10,000 | 1 |
| 3,960,000 | 10,000 | 1 |
| 4,000,000 | 10,000 | 1 |
| 4,300,000 | 10,000 | 2 |
| 4,560,000 | 10,000 | 1 |
| 4,640,000 | 10,000 | 1 |
| 4,690,000 | 10,000 | 1 |
| 4,800,000 | 10,000 | 1 |
| 4,900,000 | 10,000 | 1 |
| 5,000,000 | 10,000 | 4 |
| 6,000,000 | 10,000 | 4 |
| 6,100,000 | 10,000 | 1 |
| 7,000,000 | 10,000 | 2 |
| 7,140,000 | 10,000 | 1 |
| 7,440,000 | 10,000 | 1 |
| 7,500,000 | 10,000 | 1 |
| 7,600,000 | 10,000 | 1 |
| 8,120,000 | 10,000 | 1 |
| 8,250,000 | 10,000 | 1 |
| 8,500,000 | 10,000 | 1 |
| 8,700,000 | 10,000 | 2 |
| 8,900,000 | 10,000 | 1 |
| 9,000,000 | 10,000 | 1 |
| 9,500,000 | 10,000 | 1 |

### dti: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 0 | 5 | 41,178 |
| 5 | 5 | 116,616 |
| 10 | 5 | 181,337 |
| 15 | 5 | 194,139 |
| 20 | 5 | 162,806 |
| 25 | 5 | 110,118 |
| 30 | 5 | 60,650 |
| 35 | 5 | 20,506 |
| 40 | 5 | 29 |
| 45 | 5 | 17 |
| 50 | 5 | 7 |
| 55 | 5 | 8 |
| 60 | 5 | 5 |
| 65 | 5 | 4 |
| 70 | 5 | 4 |
| 75 | 5 | 1 |
| 80 | 5 | 2 |
| 85 | 5 | 1 |
| 90 | 5 | 1 |
| 100 | 5 | 2 |
| 120 | 5 | 1 |
| 125 | 5 | 1 |
| 135 | 5 | 2 |
| 380 | 5 | 1 |
| 670 | 5 | 1 |
| 995 | 5 | 1 |

### fico_mid: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 610 | 10 | 3 |
| 620 | 10 | 3 |
| 630 | 10 | 11 |
| 640 | 10 | 214 |
| 650 | 10 | 258 |
| 660 | 10 | 156,961 |
| 670 | 10 | 149,411 |
| 680 | 10 | 131,730 |
| 690 | 10 | 114,394 |
| 700 | 10 | 93,024 |
| 710 | 10 | 71,460 |
| 720 | 10 | 50,869 |
| 730 | 10 | 34,502 |
| 740 | 10 | 23,723 |
| 750 | 10 | 17,746 |
| 760 | 10 | 12,628 |
| 770 | 10 | 9,717 |
| 780 | 10 | 7,418 |
| 790 | 10 | 5,404 |
| 800 | 10 | 3,816 |
| 810 | 10 | 2,222 |
| 820 | 10 | 1,221 |
| 830 | 10 | 508 |
| 840 | 10 | 197 |

### int_rate: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 5 | 1 | 12,794 |
| 6 | 1 | 49,858 |
| 7 | 1 | 61,934 |
| 8 | 1 | 46,702 |
| 9 | 1 | 64,229 |
| 10 | 1 | 58,839 |
| 11 | 1 | 61,728 |
| 12 | 1 | 94,518 |
| 13 | 1 | 90,522 |
| 14 | 1 | 66,656 |
| 15 | 1 | 56,327 |
| 16 | 1 | 50,875 |
| 17 | 1 | 45,964 |
| 18 | 1 | 39,996 |
| 19 | 1 | 27,876 |
| 20 | 1 | 15,280 |
| 21 | 1 | 12,496 |
| 22 | 1 | 9,075 |
| 23 | 1 | 7,722 |
| 24 | 1 | 7,558 |
| 25 | 1 | 4,850 |
| 26 | 1 | 809 |
| 27 | 1 | 581 |
| 28 | 1 | 251 |

### loan_amnt: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 0 | 1,000 | 33 |
| 1,000 | 1,000 | 9,589 |
| 2,000 | 1,000 | 16,140 |
| 3,000 | 1,000 | 23,395 |
| 4,000 | 1,000 | 26,364 |
| 5,000 | 1,000 | 43,179 |
| 6,000 | 1,000 | 43,182 |
| 7,000 | 1,000 | 35,930 |
| 8,000 | 1,000 | 45,434 |
| 9,000 | 1,000 | 30,517 |
| 10,000 | 1,000 | 79,060 |
| 11,000 | 1,000 | 23,856 |
| 12,000 | 1,000 | 63,825 |
| 13,000 | 1,000 | 19,207 |
| 14,000 | 1,000 | 28,657 |
| 15,000 | 1,000 | 57,111 |
| 16,000 | 1,000 | 34,321 |
| 17,000 | 1,000 | 15,359 |
| 18,000 | 1,000 | 30,630 |
| 19,000 | 1,000 | 13,869 |
| 20,000 | 1,000 | 54,036 |
| 21,000 | 1,000 | 18,549 |
| 22,000 | 1,000 | 11,929 |
| 23,000 | 1,000 | 7,842 |
| 24,000 | 1,000 | 27,629 |
| 25,000 | 1,000 | 27,995 |
| 26,000 | 1,000 | 5,382 |
| 27,000 | 1,000 | 5,517 |
| 28,000 | 1,000 | 17,776 |
| 29,000 | 1,000 | 3,911 |
| 30,000 | 1,000 | 19,158 |
| 31,000 | 1,000 | 2,507 |
| 32,000 | 1,000 | 4,597 |
| 33,000 | 1,000 | 2,843 |
| 34,000 | 1,000 | 1,743 |
| 35,000 | 1,000 | 36,368 |

### revol_util: all histogram bins

| bin_start | width | loans |
| --- | --- | --- |
| 0 | 5 | 15,095 |
| 5 | 5 | 14,640 |
| 10 | 5 | 19,303 |
| 15 | 5 | 25,538 |
| 20 | 5 | 32,030 |
| 25 | 5 | 39,673 |
| 30 | 5 | 47,094 |
| 35 | 5 | 53,216 |
| 40 | 5 | 57,230 |
| 45 | 5 | 61,833 |
| 50 | 5 | 64,394 |
| 55 | 5 | 65,164 |
| 60 | 5 | 64,409 |
| 65 | 5 | 62,374 |
| 70 | 5 | 58,859 |
| 75 | 5 | 53,790 |
| 80 | 5 | 48,207 |
| 85 | 5 | 41,457 |
| 90 | 5 | 34,669 |
| 95 | 5 | 24,177 |
| 100 | 5 | 3,225 |
| 105 | 5 | 300 |
| 110 | 5 | 119 |
| 115 | 5 | 47 |
| 120 | 5 | 27 |
| 125 | 5 | 26 |
| 130 | 5 | 16 |
| 135 | 5 | 4 |
| 140 | 5 | 4 |
| 145 | 5 | 3 |
| 150 | 5 | 5 |
| 155 | 5 | 1 |
| 160 | 5 | 1 |
| 165 | 5 | 1 |
| 175 | 5 | 1 |
| 180 | 5 | 3 |
| 190 | 5 | 1 |
| 365 | 5 | 1 |
| 890 | 5 | 1 |

Source: [`07_distributions.csv`](results/07_distributions.csv).

## 14. Source fingerprints and update rules

### Result CSV fingerprints

SHA-256 values below fingerprint the exported summaries used to assemble this file. They do not fingerprint the raw loan records. All **15 original result CSVs** are transcribed into the tables above, either directly or as an equivalent complete matrix. The separate findings Markdown is summarized by the interpretations and limitations in this reference.

| CSV | Records (excluding header) | SHA-256 |
| --- | --- | --- |
| 01_raw_audit.csv | 1 | a6732f72035dcc77fc2085bd5e109bee87c4c24c6ac4cf67cb7227ebb8087ea1 |
| 02_raw_missingness.csv | 151 | 2c5fca069ef1ee98dfca42bcf58a9ab29062682132d31d65e9fabf0317eba901 |
| 04_cleaning_audit.csv | 6 | 67ee7609043be09dc1591ce12801186adfe7d6b857c742ac96e4488a8c20cfbb |
| 05_status_coverage.csv | 9 | 326d91ac3f3390c2b9dce8f7158d14a58fb3a34302d0a9e3a91032f284e454df |
| 06_numeric_summary.csv | 8 | b4422375d04213c8f7e61daf43864e1dd17a15df2034697c7f91cc990c5272f8 |
| 07_distributions.csv | 318 | 2cbeac38b5d0fd043140bdd2aa3e91b3aca215d81f153120382e969e10caf64a |
| 08_category_rates.csv | 32 | 5bd4a5dcf33c8b241ae469b06fda6857ba32d01d3f86263a0a293125b12142c6 |
| 09_cohorts.csv | 21 | 966db3e84acb9a35ab60b0a9349979fe363a261be11ebbbb76c479929e74a6c8 |
| 10_numeric_rates.csv | 154 | 873125d7e9f1c3e2b3b8c225704a2649ed175387c1b947aeef051fd903bf0478 |
| 11_grade_term.csv | 14 | 525fe7c2d63799f529abb22206afb64ec731dfd03df3275c63c8284eb3144954 |
| 12_grade_cohort.csv | 63 | c706b6e6674e6cc6242042ecc35b929314416c636e8f1fdbad1cf2f8e1b1fe34 |
| 13_correlations.csv | 49 | 8a51d97151b83af1d154c219d0ed936ed652a0a7394eef0b43d94695bf9b26e4 |
| cleaning_summary.csv | 1 | abf0fcfe566875b3a1b107450f59f81d694c187eec6aa6cab4be3e6a621c79aa |
| development_outcomes.csv | 3 | aac3fdab806d74bc07764e88b3e57d3eaddfd7aa368b35dccd14f7a76a261c36 |
| scatter_sample_counts.csv | 2 | 5dab461b88361e15f9bc32718388433ae7e7d2056e6e10d5c28d0763b92caf29 |

### How to keep this file reliable

After a completed stage, update this file with the new values, source artifact paths, relevant dataset/model/code version, measurement date, units, and denominators. Keep pending results explicitly marked Not measured. Preserve the distinction between all loans, resolved loans, development loans, plotted samples, validation rows, and final test rows.

For model experiments, add one row per model/run/split rather than overwriting comparisons with only the best result. For stress tests, add one row per workload/scenario with offered load, infrastructure, duration, successful predictions, latency quantiles, lag, and failures. For subgroup metrics, include sample sizes and label availability. Report measured results only; projected targets and SLOs must be labeled as targets.

The original notebook remains the reproducible analysis source: [`scripts/01_data_analysis.py`](../scripts/01_data_analysis.py). This document is the factual reading reference; it does not trigger computation or refresh itself when the notebook changes.

<!-- deeper-eda-statistics -->

## 15. Follow-up EDA

Updated: 2026-11-08T15:10:49+00:00. The original statistics and artifact inventory in sections 2–14 describe the first EDA snapshot. Quick-answer artifact counts include this follow-up. No model or stress-test measurements have been added.

Source: [second marimo notebook](../scripts/02_deeper_eda.py), [HTML report](../docs/deeper_eda.html). It reads the existing clean Parquet; it does not repeat raw-data cleaning.

### Follow-up interpretation

#### Scope

All analyses use clean development loans issued through 2015. The FICO/DTI grid
uses 36-month loans issued in 2011–2014. No model training or cleaning changes were made.

#### What the follow-up found

- Annual income above the development p99: 7,967 loans; above $1 million: 153.
- DTI above 100: 9 loans; exactly 999: 1. These counts overlap.
- Revolving utilization above 100%: 3,506 loans. These flags do not prove data errors, so records are retained.
- Missing employment length: 44,835 loans, with 23.65% charged off among 42,577 resolved loans. Present employment: 18.14% among 784,027 resolved loans. These are unadjusted associations.
- The FICO/DTI grid covers 320,563 loans with 100.00% ordinary outcome coverage. Its smaller population must not be confused with the full 887,440-loan development sample.
- Between 2007 and 2015, median principal changed from $6,000 to $14,000; the 60-month share changed from 0.00% to 32.75%. Borrower/loan mix is not constant over time.

#### How to read the outputs

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

#### Verification

Group totals reconcile to the development population. Tail, missingness, and
affordability outcome counts reconcile to the full development label counts.
The FICO/DTI grid reconciles independently to its narrower SQL population.


### Complete follow-up result tables

All six new CSVs are transcribed below. Counts are integers; display rounding is at most six decimal places. Percentages use the denominators stated above. No group is omitted from these tables.

#### Diagnostic tail groups

Source: [14_tail_investigation.csv](results/14_tail_investigation.csv). Records: 15. SHA-256: `0206be052ea55a5725da2f881c7095a8cf3c4d487c827a4540f125651620c996`.

| check_name | cutoff | value_group | loans | resolved_loans | charged_off_loans | charged_off_pct | minimum | median | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dti_above_100 | 100 | flagged | 9 | 8 | 0 | 0 | 100.09 | 136.97 | 999 |
| dti_above_100 | 100 | missing | 2 | 2 | 1 | 50 | — | — | — |
| dti_above_100 | 100 | not_flagged | 887,429 | 826,594 | 152,301 | 18.425128 | 0 | 17.66 | 90 |
| dti_equals_999 | 999 | flagged | 1 | 1 | 0 | 0 | 999 | 999 | 999 |
| dti_equals_999 | 999 | missing | 2 | 2 | 1 | 50 | — | — | — |
| dti_equals_999 | 999 | not_flagged | 887,437 | 826,601 | 152,301 | 18.424972 | 0 | 17.66 | 672.52 |
| income_above_1m | 1,000,000 | flagged | 153 | 143 | 20 | 13.986014 | 1,007,787 | 1,473,000 | 9,500,000 |
| income_above_1m | 1,000,000 | missing | 6 | 2 | 1 | 50 | — | — | — |
| income_above_1m | 1,000,000 | not_flagged | 887,281 | 826,459 | 152,281 | 18.425717 | 1,200 | 65,000 | 1,000,000 |
| income_above_p99 | 250,000 | flagged | 7,967 | 7,285 | 875 | 12.010981 | 250,142 | 322,000 | 9,500,000 |
| income_above_p99 | 250,000 | missing | 6 | 2 | 1 | 50 | — | — | — |
| income_above_p99 | 250,000 | not_flagged | 879,467 | 819,317 | 151,426 | 18.48198 | 1,200 | 64,000 | 250,000 |
| utilization_above_100 | 100 | flagged | 3,506 | 3,075 | 783 | 25.463415 | 100.1 | 101.3 | 892.3 |
| utilization_above_100 | 100 | missing | 502 | 444 | 96 | 21.621622 | — | — | — |
| utilization_above_100 | 100 | not_flagged | 883,432 | 823,085 | 151,423 | 18.397006 | 0 | 55.8 | 100 |

#### Missingness by development year

Source: [15_missingness_by_year.csv](results/15_missingness_by_year.csv). Records: 54. SHA-256: `4e6c20b4cd9a22dc268b5b4cf559f63a49b89ec2732dd748951a5b9ba47167c5`.

| issue_year | feature | total_loans | missing_loans | missing_pct |
| --- | --- | --- | --- | --- |
| 2,007 | annual_inc | 603 | 4 | 0.66335 |
| 2,008 | annual_inc | 2,393 | 0 | 0 |
| 2,009 | annual_inc | 5,281 | 0 | 0 |
| 2,010 | annual_inc | 12,537 | 0 | 0 |
| 2,011 | annual_inc | 21,721 | 0 | 0 |
| 2,012 | annual_inc | 53,367 | 0 | 0 |
| 2,013 | annual_inc | 134,814 | 0 | 0 |
| 2,014 | annual_inc | 235,629 | 0 | 0 |
| 2,015 | annual_inc | 421,095 | 2 | 0.000475 |
| 2,007 | credit_history_years | 603 | 29 | 4.809287 |
| 2,008 | credit_history_years | 2,393 | 0 | 0 |
| 2,009 | credit_history_years | 5,281 | 0 | 0 |
| 2,010 | credit_history_years | 12,537 | 0 | 0 |
| 2,011 | credit_history_years | 21,721 | 0 | 0 |
| 2,012 | credit_history_years | 53,367 | 0 | 0 |
| 2,013 | credit_history_years | 134,814 | 0 | 0 |
| 2,014 | credit_history_years | 235,629 | 0 | 0 |
| 2,015 | credit_history_years | 421,095 | 0 | 0 |
| 2,007 | dti | 603 | 0 | 0 |
| 2,008 | dti | 2,393 | 0 | 0 |
| 2,009 | dti | 5,281 | 0 | 0 |
| 2,010 | dti | 12,537 | 0 | 0 |
| 2,011 | dti | 21,721 | 0 | 0 |
| 2,012 | dti | 53,367 | 0 | 0 |
| 2,013 | dti | 134,814 | 0 | 0 |
| 2,014 | dti | 235,629 | 0 | 0 |
| 2,015 | dti | 421,095 | 2 | 0.000475 |
| 2,007 | emp_length_years | 603 | 0 | 0 |
| 2,008 | emp_length_years | 2,393 | 0 | 0 |
| 2,009 | emp_length_years | 5,281 | 0 | 0 |
| 2,010 | emp_length_years | 12,537 | 353 | 2.815666 |
| 2,011 | emp_length_years | 21,721 | 759 | 3.494314 |
| 2,012 | emp_length_years | 53,367 | 1,925 | 3.607098 |
| 2,013 | emp_length_years | 134,814 | 5,962 | 4.422389 |
| 2,014 | emp_length_years | 235,629 | 12,019 | 5.100815 |
| 2,015 | emp_length_years | 421,095 | 23,817 | 5.655968 |
| 2,007 | pub_rec_bankruptcies | 603 | 583 | 96.68325 |
| 2,008 | pub_rec_bankruptcies | 2,393 | 779 | 32.55328 |
| 2,009 | pub_rec_bankruptcies | 5,281 | 3 | 0.056807 |
| 2,010 | pub_rec_bankruptcies | 12,537 | 0 | 0 |
| 2,011 | pub_rec_bankruptcies | 21,721 | 0 | 0 |
| 2,012 | pub_rec_bankruptcies | 53,367 | 0 | 0 |
| 2,013 | pub_rec_bankruptcies | 134,814 | 0 | 0 |
| 2,014 | pub_rec_bankruptcies | 235,629 | 0 | 0 |
| 2,015 | pub_rec_bankruptcies | 421,095 | 0 | 0 |
| 2,007 | revol_util | 603 | 32 | 5.306799 |
| 2,008 | revol_util | 2,393 | 12 | 0.501463 |
| 2,009 | revol_util | 5,281 | 16 | 0.302973 |
| 2,010 | revol_util | 12,537 | 21 | 0.167504 |
| 2,011 | revol_util | 21,721 | 9 | 0.041435 |
| 2,012 | revol_util | 53,367 | 47 | 0.088069 |
| 2,013 | revol_util | 134,814 | 78 | 0.057857 |
| 2,014 | revol_util | 235,629 | 125 | 0.053049 |
| 2,015 | revol_util | 421,095 | 162 | 0.038471 |

#### Missing versus present: outcomes and coverage

Source: [16_missingness_outcomes.csv](results/16_missingness_outcomes.csv). Records: 12. SHA-256: `0b726befff7731ba39c06ade9548f76a868ccb82a9adb3b3be8250db405f24bd`.

| feature | value_group | total_loans | resolved_loans | charged_off_loans | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- |
| annual_inc | missing | 6 | 2 | 1 | 33.333333 | 50 |
| annual_inc | present | 887,434 | 826,602 | 152,301 | 93.14518 | 18.424949 |
| credit_history_years | missing | 29 | 0 | — | 0 | — |
| credit_history_years | present | 887,411 | 826,604 | 152,302 | 93.14782 | 18.425026 |
| dti | missing | 2 | 2 | 1 | 100 | 50 |
| dti | present | 887,438 | 826,602 | 152,301 | 93.144761 | 18.424949 |
| emp_length_years | missing | 44,835 | 42,577 | 10,070 | 94.963756 | 23.651267 |
| emp_length_years | present | 842,605 | 784,027 | 142,232 | 93.047988 | 18.141212 |
| pub_rec_bankruptcies | missing | 1,365 | 697 | 118 | 51.062271 | 16.929699 |
| pub_rec_bankruptcies | present | 886,075 | 825,907 | 152,184 | 93.209604 | 18.426288 |
| revol_util | missing | 502 | 444 | 96 | 88.446215 | 21.621622 |
| revol_util | present | 886,938 | 826,160 | 152,206 | 93.147435 | 18.423308 |

#### Affordability ratios and outcome bands

Source: [17_affordability.csv](results/17_affordability.csv). Records: 12. SHA-256: `d81ae6a28b03bc0f7081722cf04ffdd7eecb43bd9302e82c47e1fb7779b72f89`.

| metric | band_order | ratio_band | total_loans | resolved_loans | charged_off_loans | resolved_pct | charged_off_pct | median_ratio | maximum_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| installment_to_monthly_income | 1 | <10% | 629,555 | 585,685 | 94,879 | 93.031586 | 16.199664 | 0.059613 | 0.099999 |
| installment_to_monthly_income | 2 | 10-<20% | 254,939 | 238,024 | 56,676 | 93.365079 | 23.811044 | 0.125144 | 0.199993 |
| installment_to_monthly_income | 3 | 20-<30% | 2,905 | 2,871 | 743 | 98.829604 | 25.879485 | 0.20979 | 0.297558 |
| installment_to_monthly_income | 4 | 30-<50% | 26 | 15 | 2 | 57.692308 | 13.333333 | 0.377772 | 0.48209 |
| installment_to_monthly_income | 5 | 50%+ | 9 | 7 | 1 | 77.777778 | 14.285714 | 0.672169 | 4.4591 |
| installment_to_monthly_income | 6 | Missing | 6 | 2 | 1 | 33.333333 | 50 | — | — |
| principal_to_annual_income | 1 | <10% | 126,940 | 124,549 | 14,862 | 98.116433 | 11.932653 | 0.069444 | 0.099998 |
| principal_to_annual_income | 2 | 10-<20% | 281,819 | 268,710 | 39,227 | 95.348433 | 14.598266 | 0.15 | 0.2 |
| principal_to_annual_income | 3 | 20-<30% | 252,223 | 232,138 | 45,061 | 92.036809 | 19.411298 | 0.242857 | 0.299998 |
| principal_to_annual_income | 4 | 30-<50% | 221,319 | 196,936 | 51,907 | 88.982871 | 26.357294 | 0.359687 | 0.499999 |
| principal_to_annual_income | 5 | 50%+ | 5,133 | 4,269 | 1,244 | 83.167738 | 29.140314 | 0.5 | 10 |
| principal_to_annual_income | 6 | Missing | 6 | 2 | 1 | 33.333333 | 50 | — | — |

#### FICO and DTI: 2011–2014, 36-month loans

Source: [18_fico_dti_interaction.csv](results/18_fico_dti_interaction.csv). Records: 16. SHA-256: `6be9ad9637332829188c0a64a32f6312e907b9c29482a7b31dd8c48e39fe2c00`.

| fico_order | fico_band | dti_order | dti_band | total_loans | resolved_loans | charged_off_loans | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 660-<680 | 1 | <10 | 22,282 | 22,282 | 2,947 | 100 | 13.225922 |
| 2 | 660-<680 | 2 | 10-<20 | 48,225 | 48,225 | 7,794 | 100 | 16.161742 |
| 2 | 660-<680 | 3 | 20-<30 | 31,693 | 31,693 | 6,495 | 100 | 20.493484 |
| 2 | 660-<680 | 4 | 30+ | 6,586 | 6,586 | 1,521 | 100 | 23.094443 |
| 3 | 680-<700 | 1 | <10 | 16,119 | 16,119 | 1,829 | 100 | 11.346858 |
| 3 | 680-<700 | 2 | 10-<20 | 40,138 | 40,138 | 5,187 | 100 | 12.922916 |
| 3 | 680-<700 | 3 | 20-<30 | 27,933 | 27,933 | 4,550 | 100 | 16.288977 |
| 3 | 680-<700 | 4 | 30+ | 5,760 | 5,760 | 1,086 | 100 | 18.854167 |
| 4 | 700-<740 | 1 | <10 | 16,897 | 16,897 | 1,464 | 100 | 8.66426 |
| 4 | 700-<740 | 2 | 10-<20 | 40,545 | 40,545 | 3,611 | 100 | 8.906154 |
| 4 | 700-<740 | 3 | 20-<30 | 27,032 | 27,032 | 3,080 | 100 | 11.393904 |
| 4 | 700-<740 | 4 | 30+ | 5,231 | 5,231 | 753 | 100 | 14.394953 |
| 5 | 740+ | 1 | <10 | 10,725 | 10,725 | 540 | 100 | 5.034965 |
| 5 | 740+ | 2 | 10-<20 | 13,733 | 13,733 | 698 | 100 | 5.082648 |
| 5 | 740+ | 3 | 20-<30 | 6,732 | 6,732 | 461 | 100 | 6.847891 |
| 5 | 740+ | 4 | 30+ | 932 | 932 | 79 | 100 | 8.476395 |

#### Development cohort composition

Source: [19_development_composition.csv](results/19_development_composition.csv). Records: 9. SHA-256: `8bb59ddc9a49e92bee47292d3bad3970e35b5babb640dca1e36562884fe3539e`.

| issue_year | total_loans | term_60_pct | grade_ab_pct | median_loan_amnt | median_annual_inc | median_dti | median_fico | median_int_rate | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2,007 | 603 | 0 | 29.187396 | 6,000 | 50,000 | 10 | 682 | 11.54 | 41.625207 | 17.928287 |
| 2,008 | 2,393 | 0 | 38.111158 | 7,500 | 52,500 | 13.1 | 692 | 11.91 | 65.273715 | 15.81306 |
| 2,009 | 5,281 | 0 | 50.142019 | 8,800 | 57,000 | 12.59 | 712 | 12.53 | 89.301269 | 12.59542 |
| 2,010 | 12,537 | 26.968174 | 51.982133 | 9,300 | 57,996 | 13.24 | 712 | 11.86 | 92.015634 | 12.890083 |
| 2,011 | 21,721 | 35.081258 | 56.7147 | 10,000 | 60,000 | 13.92 | 712 | 11.99 | 100 | 15.178859 |
| 2,012 | 53,367 | 18.545168 | 55.105215 | 12,000 | 60,000 | 16.48 | 697 | 13.67 | 100 | 16.197275 |
| 2,013 | 134,814 | 25.510704 | 45.837228 | 13,000 | 64,000 | 16.89 | 692 | 14.33 | 99.992582 | 15.595976 |
| 2,014 | 235,629 | 31.005946 | 41.609055 | 13,000 | 65,000 | 17.63 | 687 | 13.65 | 94.683592 | 18.449409 |
| 2,015 | 421,095 | 32.753179 | 45.344162 | 14,000 | 65,000 | 18.6 | 687 | 12.29 | 89.182963 | 20.184798 |

### Follow-up figure inventory

- [12_tail_investigation.png](figures/12_tail_investigation.png) · [12_tail_investigation.svg](figures/12_tail_investigation.svg)

- [13_missingness_by_year.png](figures/13_missingness_by_year.png) · [13_missingness_by_year.svg](figures/13_missingness_by_year.svg)

- [14_missingness_outcomes.png](figures/14_missingness_outcomes.png) · [14_missingness_outcomes.svg](figures/14_missingness_outcomes.svg)

- [15_affordability_outcomes.png](figures/15_affordability_outcomes.png) · [15_affordability_outcomes.svg](figures/15_affordability_outcomes.svg)

- [16_fico_dti_interaction.png](figures/16_fico_dti_interaction.png) · [16_fico_dti_interaction.svg](figures/16_fico_dti_interaction.svg)

- [17_development_composition.png](figures/17_development_composition.png) · [17_development_composition.svg](figures/17_development_composition.svg)

### Snapshot maintenance

This follow-up section is refreshed when the second notebook runs. The original sections retain their first-stage provenance; model and stress-test sections remain Not measured. The clean data is unchanged.

<!-- final-eda-statistics -->

## 16. EDA completion

Completed: 2026-11-08T15:19:48+00:00.

Final decisions: [EDA summary](../docs/eda_summary.md); [clean dictionary](../docs/data_dictionary.md); [HTML report](../docs/eda_completion.html). The original source and clean data are unchanged.

### Final benchmark and interpretation

36-month loans issued in 2011–2015 with exact Fully Paid / Charged Off status. Train 2011–2013, validation 2014, exploratory evaluation 2015. This supersedes the original 2016 / 2017–2018 proposal. EDA previously inspected these years. No fixed prediction horizon, deployment backtest, or pristine holdout claim is made.

### Verification

All 151 source and 26 clean columns accounted for; 14 candidate features recorded. All numeric/category/outcome and cohort totals reconcile. Sixteen source conversions have zero parse/nonfinite failures on valid development rows; all 15 clean-value checks pass. None of this certifies the economic meaning of extremes or source timing.

### Complete final-stage tables

All ten new result CSVs are transcribed below. Counts are exact; displayed noninteger values are rounded to six places. Numeric moments exclude NULLs. Category percentages use all development loans; outcome percentages use ordinary resolved loans. Dictionary dispositions are project judgments, not an official source dictionary.

#### 20_complete_numeric_profile

Source: [20_complete_numeric_profile.csv](results/20_complete_numeric_profile.csv). Records: 14. SHA-256: `817d95c0918e56ff0733a91fed2ad1a3743edadbb49a6fc7988c376eb824185d`.

| feature | nonmissing | missing | missing_pct | distinct_values | minimum | p01 | p25 | median | mean | standard_deviation | p75 | p99 | maximum | skewness | excess_kurtosis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| annual_inc | 887,434 | 6 | 0.000676 | 49,388 | 1,200 | 19,000 | 45,000 | 65,000 | 75,026.445863 | 64,696.673972 | 90,000 | 250,000 | 9,500,000 | 44.478935 | 4,808.359191 |
| credit_history_years | 887,411 | 29 | 0.003268 | 728 | 0.5 | 4 | 11.25 | 14.833333 | 16.344135 | 7.463974 | 20.083333 | 39.5 | 71 | 1.064661 | 1.580715 |
| delinq_2yrs | 887,411 | 29 | 0.003268 | 29 | 0 | 0 | 0 | 0 | 0.314439 | 0.862233 | 0 | 4 | 39 | 5.473726 | 57.308357 |
| dti | 887,438 | 2 | 0.000225 | 4,085 | 0 | 1.98 | 11.91 | 17.66 | 18.134669 | 8.413134 | 23.95 | 37.48 | 999 | 2.643529 | 252.863814 |
| emp_length_years | 842,605 | 44,835 | 5.052173 | 11 | 0 | 0 | 3 | 6 | 6.008783 | 3.666145 | 10 | 10 | 10 | -0.243431 | -1.472534 |
| fico_mid | 887,440 | 0 | 0 | 48 | 612 | 662 | 672 | 692 | 696.943984 | 30.492781 | 712 | 797 | 847.5 | 1.299438 | 1.82563 |
| installment | 887,440 | 0 | 0 | 68,783 | 4.93 | 60.65 | 260.6375 | 382.55 | 436.691727 | 244.176822 | 572.59 | 1,184.86 | 1,445.46 | 0.937023 | 0.68628 |
| int_rate | 887,440 | 0 | 0 | 544 | 5.32 | 5.32 | 9.99 | 12.99 | 13.245226 | 4.382606 | 16.2 | 24.99 | 28.99 | 0.429265 | -0.155824 |
| loan_amnt | 887,440 | 0 | 0 | 1,372 | 500 | 1,800 | 8,000 | 13,000 | 14,755.167673 | 8,435.379336 | 20,000 | 35,000 | 35,000 | 0.681691 | -0.256685 |
| open_acc | 887,411 | 29 | 0.003268 | 77 | 0 | 3 | 8 | 11 | 11.548394 | 5.31725 | 14 | 28 | 90 | 1.249382 | 3.104 |
| pub_rec_bankruptcies | 886,075 | 1,365 | 0.153813 | 12 | 0 | 0 | 0 | 0 | 0.11927 | 0.359222 | 0 | 1 | 12 | 3.75523 | 24.497173 |
| revol_bal | 887,440 | 0 | 0 | 73,741 | 0 | 309 | 6,443 | 11,875 | 16,920.605872 | 22,426.235824 | 20,828 | 93,407.66 | 2,904,836 | 15.949428 | 985.921431 |
| revol_util | 886,938 | 502 | 0.056567 | 1,356 | 0 | 2.2 | 37.7 | 56 | 55.068132 | 23.834234 | 73.6 | 98.5 | 892.3 | -0.123885 | 1.027192 |
| term_months | 887,440 | 0 | 0 | 2 | 36 | 36 | 36 | 36 | 43.201055 | 10.998648 | 60 | 60 | 60 | 0.872645 | -1.238494 |

#### 21_complete_category_profile

Source: [21_complete_category_profile.csv](results/21_complete_category_profile.csv). Records: 118. SHA-256: `e8f857a53aeeb275fe7987bde58e58311cf31a77666d7179a536691b6713b59b`.

| feature | category | total_loans | pct_of_development | resolved_loans | charged_off_loans | charged_off_pct | rare_in_development |
| --- | --- | --- | --- | --- | --- | --- | --- |
| addr_state | CA | 129,527 | 14.595578 | 123,084 | 21,974 | 17.852848 | 0 |
| addr_state | NY | 74,089 | 8.348621 | 69,172 | 13,769 | 19.905453 | 0 |
| addr_state | TX | 71,139 | 8.016204 | 66,345 | 11,819 | 17.814455 | 0 |
| addr_state | FL | 60,941 | 6.867056 | 57,189 | 11,284 | 19.731067 | 0 |
| addr_state | IL | 35,477 | 3.997679 | 32,650 | 5,354 | 16.398162 | 0 |
| addr_state | NJ | 33,258 | 3.747634 | 30,786 | 5,991 | 19.460144 | 0 |
| addr_state | PA | 31,393 | 3.537479 | 28,864 | 5,573 | 19.307788 | 0 |
| addr_state | OH | 29,632 | 3.339043 | 27,208 | 5,353 | 19.67436 | 0 |
| addr_state | GA | 29,088 | 3.277743 | 26,823 | 4,550 | 16.963054 | 0 |
| addr_state | VA | 26,257 | 2.958735 | 24,291 | 4,561 | 18.776502 | 0 |
| addr_state | NC | 24,724 | 2.785991 | 22,893 | 4,429 | 19.346525 | 0 |
| addr_state | MI | 22,986 | 2.590147 | 21,430 | 3,978 | 18.562762 | 0 |
| addr_state | MD | 21,033 | 2.370076 | 19,376 | 3,743 | 19.317713 | 0 |
| addr_state | MA | 20,594 | 2.320608 | 19,121 | 3,267 | 17.085926 | 0 |
| addr_state | AZ | 20,412 | 2.300099 | 19,234 | 3,543 | 18.420505 | 0 |
| addr_state | WA | 19,435 | 2.190007 | 18,261 | 2,769 | 15.163463 | 0 |
| addr_state | CO | 18,807 | 2.119242 | 17,732 | 2,622 | 14.786826 | 0 |
| addr_state | MN | 15,957 | 1.798093 | 14,795 | 2,724 | 18.411626 | 0 |
| addr_state | MO | 14,208 | 1.60101 | 13,119 | 2,595 | 19.780471 | 0 |
| addr_state | IN | 13,791 | 1.554021 | 12,592 | 2,547 | 20.227128 | 0 |
| addr_state | CT | 13,532 | 1.524835 | 12,367 | 2,022 | 16.349964 | 0 |
| addr_state | TN | 12,888 | 1.452267 | 11,821 | 2,459 | 20.801963 | 0 |
| addr_state | NV | 12,445 | 1.402348 | 11,857 | 2,487 | 20.974952 | 0 |
| addr_state | WI | 11,575 | 1.304314 | 10,718 | 1,784 | 16.644896 | 0 |
| addr_state | AL | 11,204 | 1.262508 | 10,361 | 2,298 | 22.179326 | 0 |
| addr_state | OR | 10,894 | 1.227576 | 10,303 | 1,446 | 14.034747 | 0 |
| addr_state | SC | 10,640 | 1.198954 | 9,729 | 1,519 | 15.613115 | 0 |
| addr_state | LA | 10,588 | 1.193095 | 9,773 | 2,070 | 21.180804 | 0 |
| addr_state | KY | 8,550 | 0.963445 | 7,848 | 1,547 | 19.712029 | 0 |
| addr_state | OK | 8,086 | 0.91116 | 7,474 | 1,646 | 22.023013 | 0 |
| addr_state | KS | 7,927 | 0.893243 | 7,254 | 1,124 | 15.494899 | 0 |
| addr_state | AR | 6,640 | 0.74822 | 6,162 | 1,355 | 21.989614 | 0 |
| addr_state | UT | 6,265 | 0.705963 | 5,978 | 1,031 | 17.246571 | 0 |
| addr_state | NM | 4,941 | 0.55677 | 4,615 | 931 | 20.173348 | 0 |
| addr_state | HI | 4,570 | 0.514964 | 4,287 | 829 | 19.337532 | 0 |
| addr_state | WV | 4,386 | 0.494231 | 3,959 | 613 | 15.483708 | 0 |
| addr_state | NH | 4,294 | 0.483864 | 3,944 | 518 | 13.133874 | 0 |
| addr_state | RI | 3,894 | 0.43879 | 3,615 | 620 | 17.150761 | 0 |
| addr_state | MS | 3,819 | 0.430339 | 3,383 | 818 | 24.179722 | 0 |
| addr_state | MT | 2,559 | 0.288358 | 2,385 | 384 | 16.100629 | 0 |
| addr_state | DE | 2,511 | 0.282949 | 2,293 | 429 | 18.709115 | 0 |
| addr_state | DC | 2,433 | 0.274159 | 2,317 | 285 | 12.300388 | 0 |
| addr_state | AK | 2,205 | 0.248468 | 2,068 | 372 | 17.988395 | 0 |
| addr_state | WY | 2,028 | 0.228522 | 1,903 | 293 | 15.396742 | 0 |
| addr_state | SD | 1,815 | 0.204521 | 1,702 | 349 | 20.505288 | 0 |
| addr_state | VT | 1,797 | 0.202493 | 1,607 | 211 | 13.130056 | 0 |
| addr_state | NE | 1,176 | 0.132516 | 1,040 | 265 | 25.480769 | 0 |
| addr_state | ME | 525 | 0.059159 | 439 | 62 | 14.123007 | 0 |
| addr_state | ND | 479 | 0.053975 | 421 | 88 | 20.902613 | 0 |
| addr_state | IA | 14 | 0.001578 | 7 | 1 | 14.285714 | 1 |
| addr_state | ID | 12 | 0.001352 | 9 | 1 | 11.111111 | 1 |
| application_type | Individual | 886,929 | 99.942419 | 826,203 | 152,203 | 18.421986 | 0 |
| application_type | Joint App | 511 | 0.057581 | 401 | 99 | 24.688279 | 0 |
| grade | B | 254,553 | 28.683967 | 241,510 | 29,063 | 12.03387 | 0 |
| grade | C | 245,881 | 27.706775 | 225,234 | 45,872 | 20.366375 | 0 |
| grade | A | 148,207 | 16.700509 | 146,430 | 8,154 | 5.568531 | 0 |
| grade | D | 139,554 | 15.725457 | 126,002 | 35,442 | 28.128125 | 0 |
| grade | E | 70,707 | 7.967525 | 61,870 | 22,739 | 36.752869 | 0 |
| grade | F | 23,049 | 2.597246 | 20,693 | 8,758 | 42.323491 | 0 |
| grade | G | 5,489 | 0.618521 | 4,865 | 2,274 | 46.742035 | 0 |
| home_ownership | MORTGAGE | 443,591 | 49.985464 | 409,456 | 66,741 | 16.29992 | 0 |
| home_ownership | RENT | 356,136 | 40.130713 | 335,535 | 70,063 | 20.880981 | 0 |
| home_ownership | OWN | 87,478 | 9.857342 | 81,421 | 15,464 | 18.992643 | 0 |
| home_ownership | OTHER | 182 | 0.020508 | 144 | 27 | 18.75 | 1 |
| home_ownership | NONE | 50 | 0.005634 | 45 | 7 | 15.555556 | 1 |
| home_ownership | ANY | 3 | 0.000338 | 3 | 0 | 0 | 1 |
| purpose | debt_consolidation | 524,253 | 59.074754 | 487,230 | 95,788 | 19.659709 | 0 |
| purpose | credit_card | 206,194 | 23.234698 | 190,950 | 29,519 | 15.459021 | 0 |
| purpose | home_improvement | 51,834 | 5.840846 | 48,295 | 7,954 | 16.469614 | 0 |
| purpose | other | 42,896 | 4.833679 | 40,825 | 7,942 | 19.453766 | 0 |
| purpose | major_purchase | 17,277 | 1.946836 | 16,264 | 2,641 | 16.238318 | 0 |
| purpose | small_business | 10,378 | 1.169431 | 9,833 | 2,651 | 26.960236 | 0 |
| purpose | car | 8,864 | 0.998828 | 8,473 | 1,135 | 13.395492 | 0 |
| purpose | medical | 8,541 | 0.962431 | 8,164 | 1,580 | 19.353258 | 0 |
| purpose | moving | 5,415 | 0.610182 | 5,223 | 1,105 | 21.156424 | 0 |
| purpose | vacation | 4,736 | 0.53367 | 4,642 | 797 | 17.169324 | 0 |
| purpose | house | 3,707 | 0.417718 | 3,530 | 734 | 20.793201 | 0 |
| purpose | wedding | 2,347 | 0.264469 | 2,291 | 278 | 12.134439 | 0 |
| purpose | renewable_energy | 575 | 0.064793 | 558 | 122 | 21.863799 | 0 |
| purpose | educational | 423 | 0.047665 | 326 | 56 | 17.177914 | 0 |
| sub_grade | B3 | 56,327 | 6.347133 | 53,247 | 6,310 | 11.850433 | 0 |
| sub_grade | B4 | 55,629 | 6.26848 | 52,211 | 7,036 | 13.476087 | 0 |
| sub_grade | C1 | 53,393 | 6.016519 | 49,623 | 8,411 | 16.949802 | 0 |
| sub_grade | C2 | 52,241 | 5.886708 | 48,358 | 9,052 | 18.718723 | 0 |
| sub_grade | C3 | 50,167 | 5.653002 | 45,671 | 9,448 | 20.687088 | 0 |
| sub_grade | C4 | 48,860 | 5.505724 | 43,859 | 10,103 | 23.035181 | 0 |
| sub_grade | B5 | 48,839 | 5.503358 | 46,476 | 6,909 | 14.865737 | 0 |
| sub_grade | B2 | 48,783 | 5.497048 | 46,842 | 4,857 | 10.3689 | 0 |
| sub_grade | B1 | 44,975 | 5.067948 | 42,734 | 3,951 | 9.245566 | 0 |
| sub_grade | A5 | 44,818 | 5.050257 | 43,378 | 3,336 | 7.690534 | 0 |
| sub_grade | C5 | 41,220 | 4.644821 | 37,723 | 8,858 | 23.481696 | 0 |
| sub_grade | D1 | 36,239 | 4.083544 | 32,765 | 8,321 | 25.396002 | 0 |
| sub_grade | A4 | 34,531 | 3.89108 | 34,227 | 2,126 | 6.21147 | 0 |
| sub_grade | D2 | 29,804 | 3.358424 | 27,163 | 7,466 | 27.485918 | 0 |
| sub_grade | D3 | 26,560 | 2.992878 | 24,082 | 6,697 | 27.809152 | 0 |
| sub_grade | D4 | 25,560 | 2.880195 | 22,821 | 6,961 | 30.502607 | 0 |
| sub_grade | A3 | 23,458 | 2.643334 | 23,444 | 1,140 | 4.862651 | 0 |
| sub_grade | A1 | 22,915 | 2.582146 | 22,911 | 631 | 2.754136 | 0 |
| sub_grade | A2 | 22,485 | 2.533692 | 22,470 | 921 | 4.098798 | 0 |
| sub_grade | D5 | 21,391 | 2.410416 | 19,171 | 5,997 | 31.281623 | 0 |
| sub_grade | E1 | 18,269 | 2.058618 | 16,018 | 5,450 | 34.024223 | 0 |
| sub_grade | E2 | 17,004 | 1.916073 | 14,840 | 5,332 | 35.929919 | 0 |
| sub_grade | E3 | 14,135 | 1.592784 | 12,311 | 4,600 | 37.364958 | 0 |
| sub_grade | E4 | 11,724 | 1.321103 | 10,254 | 3,995 | 38.960406 | 0 |
| sub_grade | E5 | 9,575 | 1.078946 | 8,447 | 3,362 | 39.801113 | 0 |
| sub_grade | F1 | 7,219 | 0.813463 | 6,432 | 2,529 | 39.31903 | 0 |
| sub_grade | F2 | 5,393 | 0.607703 | 4,816 | 2,028 | 42.109635 | 0 |
| sub_grade | F3 | 4,433 | 0.499527 | 4,008 | 1,695 | 42.290419 | 0 |
| sub_grade | F4 | 3,410 | 0.384251 | 3,096 | 1,418 | 45.801034 | 0 |
| sub_grade | F5 | 2,594 | 0.292301 | 2,341 | 1,088 | 46.475865 | 0 |
| sub_grade | G1 | 1,871 | 0.210831 | 1,687 | 777 | 46.058091 | 0 |
| sub_grade | G2 | 1,398 | 0.157532 | 1,265 | 570 | 45.059289 | 0 |
| sub_grade | G3 | 981 | 0.110543 | 876 | 426 | 48.630137 | 0 |
| sub_grade | G4 | 663 | 0.074709 | 571 | 263 | 46.059545 | 0 |
| sub_grade | G5 | 576 | 0.064906 | 466 | 238 | 51.072961 | 0 |
| verification_status | Source Verified | 336,925 | 37.965947 | 308,528 | 61,189 | 19.83256 | 0 |
| verification_status | Verified | 291,105 | 32.802781 | 273,980 | 58,314 | 21.284035 | 0 |
| verification_status | Not Verified | 259,410 | 29.231272 | 244,096 | 32,799 | 13.436926 | 0 |

#### 22_numeric_by_outcome

Source: [22_numeric_by_outcome.csv](results/22_numeric_by_outcome.csv). Records: 24. SHA-256: `dee6090a681423230c41483621ee7c567ade27bad049c5889f6e3901b0e137c3`.

| feature | charged_off | group_loans | nonmissing | missing | minimum | p01 | p25 | median | mean | standard_deviation | p75 | p99 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| annual_inc | 0 | 674,302 | 674,301 | 1 | 1,200 | 18,900 | 45,600 | 65,000 | 75,851.154601 | 64,376.906818 | 90,000 | 250,000 | 9,000,000 |
| annual_inc | 1 | 152,302 | 152,301 | 1 | 4,000 | 18,000 | 42,500 | 60,000 | 68,714.178928 | 65,738.997454 | 81,500 | 223,000 | 9,500,000 |
| credit_history_years | 0 | 674,302 | 674,302 | 0 | 3 | 4 | 11.25 | 14.916667 | 16.361061 | 7.468725 | 20.166667 | 39.5 | 71 |
| credit_history_years | 1 | 152,302 | 152,302 | 0 | 3 | 3.833333 | 10.833333 | 14.25 | 15.716639 | 7.317794 | 19.166667 | 39.416667 | 70.166667 |
| delinq_2yrs | 0 | 674,302 | 674,302 | 0 | 0 | 0 | 0 | 0 | 0.305126 | 0.845309 | 0 | 4 | 39 |
| delinq_2yrs | 1 | 152,302 | 152,302 | 0 | 0 | 0 | 0 | 0 | 0.339483 | 0.912316 | 0 | 4 | 27 |
| dti | 0 | 674,302 | 674,301 | 1 | 0 | 1.85 | 11.43 | 17.03 | 17.549498 | 8.301356 | 23.21 | 36.89 | 999 |
| dti | 1 | 152,302 | 152,301 | 1 | 0 | 2.48 | 13.6 | 19.62 | 19.842882 | 8.449486 | 25.97 | 38.26 | 67.5 |
| emp_length_years | 0 | 674,302 | 641,795 | 32,507 | 0 | 0 | 3 | 6 | 5.994198 | 3.662789 | 10 | 10 | 10 |
| emp_length_years | 1 | 152,302 | 142,232 | 10,070 | 0 | 0 | 3 | 6 | 5.945631 | 3.665192 | 10 | 10 | 10 |
| fico_mid | 0 | 674,302 | 674,302 | 0 | 627 | 662 | 677 | 692 | 698.839235 | 31.55839 | 717 | 802 | 847.5 |
| fico_mid | 1 | 152,302 | 152,302 | 0 | 662 | 662 | 672 | 682 | 688.953733 | 24.735238 | 702 | 772 | 847.5 |
| int_rate | 0 | 674,302 | 674,302 | 0 | 5.32 | 5.32 | 9.17 | 12.39 | 12.616406 | 4.24072 | 15.31 | 24.08 | 28.99 |
| int_rate | 1 | 152,302 | 152,302 | 0 | 5.32 | 6.62 | 12.49 | 15.31 | 15.468892 | 4.332833 | 18.25 | 25.83 | 28.99 |
| loan_amnt | 0 | 674,302 | 674,302 | 0 | 500 | 1,600 | 8,000 | 12,000 | 14,149.207736 | 8,350.730144 | 20,000 | 35,000 | 35,000 |
| loan_amnt | 1 | 152,302 | 152,302 | 0 | 900 | 2,000 | 9,500 | 14,400 | 15,489.484708 | 8,427.62589 | 20,000 | 35,000 | 35,000 |
| open_acc | 0 | 674,302 | 674,302 | 0 | 0 | 3 | 8 | 10 | 11.401666 | 5.236454 | 14 | 28 | 90 |
| open_acc | 1 | 152,302 | 152,302 | 0 | 0 | 3 | 8 | 11 | 11.878977 | 5.468953 | 15 | 29 | 76 |
| pub_rec_bankruptcies | 0 | 674,302 | 673,723 | 579 | 0 | 0 | 0 | 0 | 0.117565 | 0.355277 | 0 | 1 | 12 |
| pub_rec_bankruptcies | 1 | 152,302 | 152,184 | 118 | 0 | 0 | 0 | 0 | 0.140416 | 0.391223 | 0 | 1 | 11 |
| revol_bal | 0 | 674,302 | 674,302 | 0 | 0 | 291 | 6,295 | 11,623 | 16,721.630784 | 22,488.849712 | 20,497 | 94,177.91 | 2,904,836 |
| revol_bal | 1 | 152,302 | 152,302 | 0 | 0 | 350 | 6,312 | 11,438 | 15,601.437972 | 18,798.790111 | 19,604 | 74,434.94 | 1,746,716 |
| revol_util | 0 | 674,302 | 673,954 | 348 | 0 | 2 | 36.5 | 54.8 | 54.075777 | 23.957058 | 72.6 | 98.2 | 892.3 |
| revol_util | 1 | 152,302 | 152,206 | 96 | 0 | 3.2 | 41 | 58.7 | 57.519246 | 23.189908 | 75.5 | 98.9 | 366.6 |

#### 23_final_cohort_audit

Source: [23_final_cohort_audit.csv](results/23_final_cohort_audit.csv). Records: 15. SHA-256: `c7fe6171460c26ff8f6d1f5ec86ba232e9ecd74eb3a9040639a9a598119e8378`.

| issue_year | term_months | proposed_split | all_loans | eligible_resolved_loans | excluded_other_status | fully_paid | charged_off | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2,007 | 36 | outside_benchmark | 603 | 251 | 352 | 206 | 45 | 41.625207 | 17.928287 |
| 2,008 | 36 | outside_benchmark | 2,393 | 1,562 | 831 | 1,315 | 247 | 65.273715 | 15.81306 |
| 2,009 | 36 | outside_benchmark | 5,281 | 4,716 | 565 | 4,122 | 594 | 89.301269 | 12.59542 |
| 2,010 | 36 | outside_benchmark | 9,156 | 8,466 | 690 | 7,624 | 842 | 92.463958 | 9.945665 |
| 2,010 | 60 | outside_benchmark | 3,381 | 3,070 | 311 | 2,425 | 645 | 90.801538 | 21.009772 |
| 2,011 | 36 | train | 14,101 | 14,101 | 0 | 12,602 | 1,499 | 100 | 10.630452 |
| 2,011 | 60 | outside_benchmark | 7,620 | 7,620 | 0 | 5,822 | 1,798 | 100 | 23.595801 |
| 2,012 | 36 | train | 43,470 | 43,470 | 0 | 37,567 | 5,903 | 100 | 13.57948 |
| 2,012 | 60 | outside_benchmark | 9,897 | 9,897 | 0 | 7,156 | 2,741 | 100 | 27.695261 |
| 2,013 | 36 | train | 100,422 | 100,422 | 0 | 88,044 | 12,378 | 100 | 12.325984 |
| 2,013 | 60 | outside_benchmark | 34,392 | 34,382 | 10 | 25,736 | 8,646 | 99.970923 | 25.146879 |
| 2,014 | 36 | validation | 162,570 | 162,570 | 0 | 140,255 | 22,315 | 100 | 13.726395 |
| 2,014 | 60 | outside_benchmark | 73,059 | 60,532 | 12,527 | 41,686 | 18,846 | 82.853584 | 31.133946 |
| 2,015 | 36 | exploratory_test | 283,173 | 283,026 | 147 | 240,894 | 42,132 | 99.948088 | 14.886265 |
| 2,015 | 60 | outside_benchmark | 137,922 | 92,519 | 45,403 | 58,848 | 33,671 | 67.080669 | 36.393606 |

#### 24_clean_value_checks

Source: [24_clean_value_checks.csv](results/24_clean_value_checks.csv). Records: 15. SHA-256: `994515322dbb348a18d41c683b1244943493e606f2b6ecbfa4efe86d20c726b6`.

| check_name | affected_loans |
| --- | --- |
| nonpositive_loan_amount | 0 |
| missing_loan_amount | 0 |
| interest_outside_0_to_100 | 0 |
| nonpositive_installment | 0 |
| unexpected_term | 0 |
| nonpositive_clean_income | 0 |
| negative_clean_dti | 0 |
| negative_clean_utilization | 0 |
| negative_revolving_balance | 0 |
| negative_open_accounts | 0 |
| negative_delinquencies | 0 |
| negative_bankruptcies | 0 |
| employment_outside_0_to_10 | 0 |
| fico_outside_300_to_850 | 0 |
| negative_credit_history | 0 |

#### 25_numeric_source_parsing

Source: [25_numeric_source_parsing.csv](results/25_numeric_source_parsing.csv). Records: 16. SHA-256: `3f4b05c5149ed412735eef73b407813b7aaae90e0c4d2db781bcb8342dd9b1e9`.

| feature | development_rows | nonblank_source_values | missing_source_values | parse_failures | nonfinite_values |
| --- | --- | --- | --- | --- | --- |
| annual_inc | 887,440 | 887,436 | 4 | 0 | 0 |
| delinq_2yrs | 887,440 | 887,411 | 29 | 0 | 0 |
| dti | 887,440 | 887,438 | 2 | 0 | 0 |
| earliest_cr_line | 887,440 | 887,411 | 29 | 0 | 0 |
| emp_length | 887,440 | 842,605 | 44,835 | 0 | 0 |
| fico_range_high | 887,440 | 887,440 | 0 | 0 | 0 |
| fico_range_low | 887,440 | 887,440 | 0 | 0 | 0 |
| installment | 887,440 | 887,440 | 0 | 0 | 0 |
| int_rate | 887,440 | 887,440 | 0 | 0 | 0 |
| issue_d | 887,440 | 887,440 | 0 | 0 | 0 |
| loan_amnt | 887,440 | 887,440 | 0 | 0 | 0 |
| open_acc | 887,440 | 887,411 | 29 | 0 | 0 |
| pub_rec_bankruptcies | 887,440 | 886,075 | 1,365 | 0 | 0 |
| revol_bal | 887,440 | 887,440 | 0 | 0 | 0 |
| revol_util | 887,440 | 886,938 | 502 | 0 | 0 |
| term | 887,440 | 887,440 | 0 | 0 | 0 |

#### eda_benchmark_splits

Source: [eda_benchmark_splits.csv](results/eda_benchmark_splits.csv). Records: 3. SHA-256: `3b1e3988df16b04c6cf49e4dfea991c632e501779c11c492d9c14b2a2db91dae`.

| proposed_split | all_loans | eligible_resolved_loans | excluded_other_status | fully_paid | charged_off | resolved_pct | charged_off_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | 157,993 | 157,993 | 0 | 138,213 | 19,780 | 100 | 12.519542 |
| validation | 162,570 | 162,570 | 0 | 140,255 | 22,315 | 100 | 13.726395 |
| exploratory_test | 283,173 | 283,026 | 147 | 240,894 | 42,132 | 99.948088 | 14.886265 |

#### eda_clean_dictionary

Source: [eda_clean_dictionary.csv](results/eda_clean_dictionary.csv). Records: 26. SHA-256: `c8f70e7e311e03a4f50c1348709e3b45ef6a457fc033d21f555d7ad371010212`.

| column | source_fields | meaning | role | initial_feature_decision | reason_or_handling | column_type |
| --- | --- | --- | --- | --- | --- | --- |
| loan_id | id | Loan identifier | identifier | exclude | Join/audit key; never a risk predictor | BIGINT |
| issue_date | issue_d | Issue month parsed to its first day | split_metadata | exclude | Cohort assignment; no exact daily issue timestamp | DATE |
| issue_year | issue_d | Year of issue month | split_metadata | exclude | Time split and monitoring | BIGINT |
| loan_status | loan_status | Status in the source snapshot | outcome | exclude | Outcome information; direct target leakage | VARCHAR |
| charged_off | loan_status | 1 charged off, 0 fully paid, otherwise missing | target | exclude | Analysis label, never an input | INTEGER |
| term_months | term | Contract term in months | constant_in_benchmark | exclude | First benchmark fixes term to 36 months | INTEGER |
| grade | grade | Assigned LendingClub grade | underwriting_output | exclude | Existing underwriting output; defer to a separate ablation | VARCHAR |
| sub_grade | sub_grade | Assigned LendingClub subgrade | underwriting_output | exclude | Existing underwriting output; defer to a separate ablation | VARCHAR |
| int_rate | int_rate | Assigned interest rate in percentage points | underwriting_output | exclude | Pricing output; not independent borrower information | DOUBLE |
| installment | installment | Scheduled payment on the approved loan | underwriting_output | exclude | Depends on pricing and term | DOUBLE |
| verification_status | verification_status | Reported income-verification status | workflow_review | exclude | Availability depends on the scoring point in the workflow | VARCHAR |
| addr_state | addr_state | Reported state | geographic_review | exclude | Descriptive group review; excluding it does not prove fairness | VARCHAR |
| loan_amnt | loan_amnt | Loan principal in USD | candidate | candidate | Use only if requested principal is known at the chosen scoring point | DOUBLE |
| annual_inc | annual_inc | Reported annual income in USD | candidate | candidate | Keep missing; consider training-only log1p and missingness indicator | DOUBLE |
| dti | dti | Source debt-to-income measure | candidate | candidate | Keep extremes; investigate 999; consider a greater-than-100 flag | DOUBLE |
| revol_util | revol_util | Revolving utilization in percentage points | candidate | candidate | Keep values above 100; consider a high-utilization flag | DOUBLE |
| revol_bal | revol_bal | Reported revolving balance in USD | candidate | candidate | Keep zero; consider training-only log1p for linear models | DOUBLE |
| open_acc | open_acc | Reported open credit-account count | candidate | candidate | Preserve missing; fit imputation on training only if needed | DOUBLE |
| delinq_2yrs | delinq_2yrs | Reported delinquency count over the stated two-year window | candidate | candidate | Keep zero distinct from missing | DOUBLE |
| pub_rec_bankruptcies | pub_rec_bankruptcies | Reported public-record bankruptcy count | candidate | candidate | Keep zero distinct from missing | DOUBLE |
| emp_length_years | emp_length | Employment category converted to capped years | candidate | candidate | 0 is less than one year; 10 includes 10+; preserve missing | INTEGER |
| fico_mid | fico_range_low,fico_range_high | Midpoint of the source origination FICO range | candidate | candidate | Use original FICO bounds, never last_fico fields | DOUBLE |
| credit_history_years | earliest_cr_line,issue_d | Month-based credit-history length at issue | candidate | candidate | Derived at issue; scoring before issue needs an as-of application date | DOUBLE |
| home_ownership | home_ownership | Reported home-ownership category | candidate | candidate | Keep categories; training-only rare grouping and unknown handling | VARCHAR |
| purpose | purpose | Reported loan purpose | candidate | candidate | Training-only rare grouping and unknown handling | VARCHAR |
| application_type | application_type | Individual or joint application category | candidate | candidate | Joint group is small; co-applicant financial fields are not retained | VARCHAR |

#### eda_feature_decisions

Source: [eda_feature_decisions.csv](results/eda_feature_decisions.csv). Records: 26. SHA-256: `a9cbf9d21570eb71888ced5c1058c2614689338dc86a49edda44282441e7bee6`.

| column | initial_feature_decision | reason_or_handling |
| --- | --- | --- |
| loan_id | exclude | Join/audit key; never a risk predictor |
| issue_date | exclude | Cohort assignment; no exact daily issue timestamp |
| issue_year | exclude | Time split and monitoring |
| loan_status | exclude | Outcome information; direct target leakage |
| charged_off | exclude | Analysis label, never an input |
| term_months | exclude | First benchmark fixes term to 36 months |
| grade | exclude | Existing underwriting output; defer to a separate ablation |
| sub_grade | exclude | Existing underwriting output; defer to a separate ablation |
| int_rate | exclude | Pricing output; not independent borrower information |
| installment | exclude | Depends on pricing and term |
| verification_status | exclude | Availability depends on the scoring point in the workflow |
| addr_state | exclude | Descriptive group review; excluding it does not prove fairness |
| loan_amnt | candidate | Use only if requested principal is known at the chosen scoring point |
| annual_inc | candidate | Keep missing; consider training-only log1p and missingness indicator |
| dti | candidate | Keep extremes; investigate 999; consider a greater-than-100 flag |
| revol_util | candidate | Keep values above 100; consider a high-utilization flag |
| revol_bal | candidate | Keep zero; consider training-only log1p for linear models |
| open_acc | candidate | Preserve missing; fit imputation on training only if needed |
| delinq_2yrs | candidate | Keep zero distinct from missing |
| pub_rec_bankruptcies | candidate | Keep zero distinct from missing |
| emp_length_years | candidate | 0 is less than one year; 10 includes 10+; preserve missing |
| fico_mid | candidate | Use original FICO bounds, never last_fico fields |
| credit_history_years | candidate | Derived at issue; scoring before issue needs an as-of application date |
| home_ownership | candidate | Keep categories; training-only rare grouping and unknown handling |
| purpose | candidate | Training-only rare grouping and unknown handling |
| application_type | candidate | Joint group is small; co-applicant financial fields are not retained |

#### eda_source_column_audit

Source: [eda_source_column_audit.csv](results/eda_source_column_audit.csv). Records: 151. SHA-256: `244b38d10e129bbf2f41ad6f282397576ddb9fc6244e8c574fdf21daea385f04`.

| source_column | role | initial_decision | clean_mapping | raw_missing_count | raw_missing_pct | reason |
| --- | --- | --- | --- | --- | --- | --- |
| id | identifier | exclude_as_predictor | loan_id | 0 | 0 | Join/audit key; never a risk predictor |
| member_id | identifier | exclude |  | 2,260,701 | 100 | Entirely missing identifier in this source snapshot |
| loan_amnt | candidate_source | candidate_source | loan_amnt | 33 | 0.00146 | Use only if requested principal is known at the chosen scoring point |
| funded_amnt | funding_or_policy_workflow | exclude |  | 33 | 0.00146 | Funding/policy workflow field; not part of independent borrower features |
| funded_amnt_inv | funding_or_policy_workflow | exclude |  | 33 | 0.00146 | Funding/policy workflow field; not part of independent borrower features |
| term | constant_in_benchmark | exclude_as_predictor | term_months | 33 | 0.00146 | First benchmark fixes term to 36 months |
| int_rate | underwriting_output | exclude_as_predictor | int_rate | 33 | 0.00146 | Pricing output; not independent borrower information |
| installment | underwriting_output | exclude_as_predictor | installment | 33 | 0.00146 | Depends on pricing and term |
| grade | underwriting_output | exclude_as_predictor | grade | 33 | 0.00146 | Existing underwriting output; defer to a separate ablation |
| sub_grade | underwriting_output | exclude_as_predictor | sub_grade | 33 | 0.00146 | Existing underwriting output; defer to a separate ablation |
| emp_title | text_or_identifier | exclude |  | 167,005 | 7.38731 | Identifier, free text, or detailed geography; outside the focused numeric/category baseline |
| emp_length | candidate_source | candidate_source | emp_length_years | 146,940 | 6.499754 | 0 is less than one year; 10 includes 10+; preserve missing |
| home_ownership | candidate_source | candidate_source | home_ownership | 33 | 0.00146 | Keep categories; training-only rare grouping and unknown handling |
| annual_inc | candidate_source | candidate_source | annual_inc | 37 | 0.001637 | Keep missing; consider training-only log1p and missingness indicator |
| verification_status | workflow_review | exclude_as_predictor | verification_status | 33 | 0.00146 | Availability depends on the scoring point in the workflow |
| issue_d | split_and_derivation | exclude_raw_predictor | issue_date, issue_year, credit_history_years | 33 | 0.00146 | Cohort assignment; no exact daily issue timestamp; Time split and monitoring; Derived at issue; scoring before issue needs an as-of application date |
| loan_status | outcome | exclude | loan_status, charged_off | 33 | 0.00146 | Snapshot outcome; used only to define labels |
| pymnt_plan | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| url | text_or_identifier | exclude |  | 33 | 0.00146 | Identifier, free text, or detailed geography; outside the focused numeric/category baseline |
| desc | text_or_identifier | exclude |  | 2,134,887 | 94.434735 | Identifier, free text, or detailed geography; outside the focused numeric/category baseline |
| purpose | candidate_source | candidate_source | purpose | 33 | 0.00146 | Training-only rare grouping and unknown handling |
| title | text_or_identifier | exclude |  | 23,358 | 1.033219 | Identifier, free text, or detailed geography; outside the focused numeric/category baseline |
| zip_code | text_or_identifier | exclude |  | 34 | 0.001504 | Identifier, free text, or detailed geography; outside the focused numeric/category baseline |
| addr_state | geographic_review | exclude_as_predictor | addr_state | 33 | 0.00146 | Descriptive group review; excluding it does not prove fairness |
| dti | candidate_source | candidate_source | dti | 1,744 | 0.077144 | Keep extremes; investigate 999; consider a greater-than-100 flag |
| delinq_2yrs | candidate_source | candidate_source | delinq_2yrs | 62 | 0.002743 | Keep zero distinct from missing |
| earliest_cr_line | candidate_source | candidate_source | credit_history_years | 62 | 0.002743 | Derived at issue; scoring before issue needs an as-of application date |
| fico_range_low | candidate_source | candidate_source | fico_mid | 33 | 0.00146 | Use original FICO bounds, never last_fico fields |
| fico_range_high | candidate_source | candidate_source | fico_mid | 33 | 0.00146 | Use original FICO bounds, never last_fico fields |
| inq_last_6mths | not_selected_needs_source_review | exclude |  | 63 | 0.002787 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_last_delinq | not_selected_needs_source_review | exclude |  | 1,158,535 | 51.246715 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_last_record | not_selected_needs_source_review | exclude |  | 1,901,545 | 84.113069 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_acc | candidate_source | candidate_source | open_acc | 62 | 0.002743 | Preserve missing; fit imputation on training only if needed |
| pub_rec | not_selected_needs_source_review | exclude |  | 62 | 0.002743 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| revol_bal | candidate_source | candidate_source | revol_bal | 33 | 0.00146 | Keep zero; consider training-only log1p for linear models |
| revol_util | candidate_source | candidate_source | revol_util | 1,835 | 0.08117 | Keep values above 100; consider a high-utilization flag |
| total_acc | not_selected_needs_source_review | exclude |  | 62 | 0.002743 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| initial_list_status | funding_or_policy_workflow | exclude |  | 33 | 0.00146 | Funding/policy workflow field; not part of independent borrower features |
| out_prncp | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| out_prncp_inv | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| total_pymnt | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| total_pymnt_inv | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| total_rec_prncp | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| total_rec_int | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| total_rec_late_fee | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| recoveries | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| collection_recovery_fee | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| last_pymnt_d | post_origination_or_workflow | exclude |  | 2,460 | 0.108816 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| last_pymnt_amnt | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| next_pymnt_d | post_origination_or_workflow | exclude |  | 1,345,343 | 59.509993 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| last_credit_pull_d | post_origination_or_workflow | exclude |  | 105 | 0.004645 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| last_fico_range_high | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| last_fico_range_low | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| collections_12_mths_ex_med | not_selected_needs_source_review | exclude |  | 178 | 0.007874 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_last_major_derog | not_selected_needs_source_review | exclude |  | 1,679,926 | 74.30996 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| policy_code | funding_or_policy_workflow | exclude |  | 33 | 0.00146 | Funding/policy workflow field; not part of independent borrower features |
| application_type | candidate_source | candidate_source | application_type | 33 | 0.00146 | Joint group is small; co-applicant financial fields are not retained |
| annual_inc_joint | not_selected_needs_source_review | exclude |  | 2,139,991 | 94.660506 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| dti_joint | not_selected_needs_source_review | exclude |  | 2,139,995 | 94.660683 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| verification_status_joint | not_selected_needs_source_review | exclude |  | 2,144,971 | 94.880791 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| acc_now_delinq | not_selected_needs_source_review | exclude |  | 62 | 0.002743 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| tot_coll_amt | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| tot_cur_bal | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_acc_6m | not_selected_needs_source_review | exclude |  | 866,163 | 38.313912 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_act_il | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_il_12m | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_il_24m | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_rcnt_il | not_selected_needs_source_review | exclude |  | 909,957 | 40.251099 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_bal_il | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| il_util | not_selected_needs_source_review | exclude |  | 1,068,883 | 47.281042 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_rv_12m | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| open_rv_24m | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| max_bal_bc | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| all_util | not_selected_needs_source_review | exclude |  | 866,381 | 38.323555 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_rev_hi_lim | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| inq_fi | not_selected_needs_source_review | exclude |  | 866,162 | 38.313868 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_cu_tl | not_selected_needs_source_review | exclude |  | 866,163 | 38.313912 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| inq_last_12m | not_selected_needs_source_review | exclude |  | 866,163 | 38.313912 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| acc_open_past_24mths | not_selected_needs_source_review | exclude |  | 50,063 | 2.21449 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| avg_cur_bal | not_selected_needs_source_review | exclude |  | 70,379 | 3.113149 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| bc_open_to_buy | not_selected_needs_source_review | exclude |  | 74,968 | 3.31614 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| bc_util | not_selected_needs_source_review | exclude |  | 76,104 | 3.366389 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| chargeoff_within_12_mths | not_selected_needs_source_review | exclude |  | 178 | 0.007874 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| delinq_amnt | not_selected_needs_source_review | exclude |  | 62 | 0.002743 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mo_sin_old_il_acct | not_selected_needs_source_review | exclude |  | 139,104 | 6.153136 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mo_sin_old_rev_tl_op | not_selected_needs_source_review | exclude |  | 70,310 | 3.110097 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mo_sin_rcnt_rev_tl_op | not_selected_needs_source_review | exclude |  | 70,310 | 3.110097 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mo_sin_rcnt_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mort_acc | not_selected_needs_source_review | exclude |  | 50,063 | 2.21449 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_recent_bc | not_selected_needs_source_review | exclude |  | 73,445 | 3.248771 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_recent_bc_dlq | not_selected_needs_source_review | exclude |  | 1,741,000 | 77.011511 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_recent_inq | not_selected_needs_source_review | exclude |  | 295,468 | 13.069751 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| mths_since_recent_revol_delinq | not_selected_needs_source_review | exclude |  | 1,520,342 | 67.25091 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_accts_ever_120_pd | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_actv_bc_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_actv_rev_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_bc_sats | not_selected_needs_source_review | exclude |  | 58,623 | 2.593134 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_bc_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_il_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_op_rev_tl | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_rev_accts | not_selected_needs_source_review | exclude |  | 70,310 | 3.110097 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_rev_tl_bal_gt_0 | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_sats | not_selected_needs_source_review | exclude |  | 58,623 | 2.593134 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_tl_120dpd_2m | not_selected_needs_source_review | exclude |  | 153,690 | 6.798334 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_tl_30dpd | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_tl_90g_dpd_24m | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| num_tl_op_past_12m | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| pct_tl_nvr_dlq | not_selected_needs_source_review | exclude |  | 70,464 | 3.116909 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| percent_bc_gt_75 | not_selected_needs_source_review | exclude |  | 75,412 | 3.335779 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| pub_rec_bankruptcies | candidate_source | candidate_source | pub_rec_bankruptcies | 1,398 | 0.061839 | Keep zero distinct from missing |
| tax_liens | not_selected_needs_source_review | exclude |  | 138 | 0.006104 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| tot_hi_cred_lim | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_bal_ex_mort | not_selected_needs_source_review | exclude |  | 50,063 | 2.21449 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_bc_limit | not_selected_needs_source_review | exclude |  | 50,063 | 2.21449 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| total_il_high_credit_limit | not_selected_needs_source_review | exclude |  | 70,309 | 3.110053 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| revol_bal_joint | not_selected_needs_source_review | exclude |  | 2,152,681 | 95.221836 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_fico_range_low | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_fico_range_high | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_earliest_cr_line | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_inq_last_6mths | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_mort_acc | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_open_acc | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_revol_util | not_selected_needs_source_review | exclude |  | 2,154,517 | 95.30305 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_open_act_il | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_num_rev_accts | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_chargeoff_within_12_mths | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_collections_12_mths_ex_med | not_selected_needs_source_review | exclude |  | 2,152,680 | 95.221792 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| sec_app_mths_since_last_major_derog | not_selected_needs_source_review | exclude |  | 2,224,759 | 98.410139 | Not retained in the focused clean table; meaning and as-of availability have not been source-certified |
| hardship_flag | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_type | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_reason | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_status | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| deferral_term | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_amount | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_start_date | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_end_date | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| payment_plan_start_date | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_length | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_dpd | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_loan_status | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| orig_projected_additional_accrued_interest | post_origination_or_workflow | exclude |  | 2,252,050 | 99.617331 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_payoff_balance_amount | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| hardship_last_payment_amount | post_origination_or_workflow | exclude |  | 2,249,784 | 99.517097 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| disbursement_method | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| debt_settlement_flag | post_origination_or_workflow | exclude |  | 33 | 0.00146 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| debt_settlement_flag_date | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| settlement_status | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| settlement_date | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| settlement_amount | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| settlement_percentage | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |
| settlement_term | post_origination_or_workflow | exclude |  | 2,226,455 | 98.48516 | Payment/performance or later workflow information; unavailable for the initial independent application-risk baseline |

### Final-stage figures

- [18_outcome_boxplots.png](figures/18_outcome_boxplots.png) · [18_outcome_boxplots.svg](figures/18_outcome_boxplots.svg)

- [19_category_support.png](figures/19_category_support.png) · [19_category_support.svg](figures/19_category_support.svg)

- [20_benchmark_coverage.png](figures/20_benchmark_coverage.png) · [20_benchmark_coverage.svg](figures/20_benchmark_coverage.svg)

- [21_source_column_disposition.png](figures/21_source_column_disposition.png) · [21_source_column_disposition.svg](figures/21_source_column_disposition.svg)

<!-- model-data-statistics -->

## 17. Model-data preparation

Completed: 2026-11-08T15:27:11+00:00.

Full contract and limitations: [prepared dataset report](../docs/model_data.md). Source and output fingerprints: [manifest](results/model_data_manifest.json).

Prepared 603,589 loans and 13 predictors from 14 candidates. Training-only dropped columns: application_type. No preprocessing was fitted and no models were trained. Clean source SHA-256: `51e966cd9162ff4fd77c6dafd4afe7143dca4e97ee4053cabe07eaa2ac6d3e20`.

The target is the resolved-loan charged-off label, not fixed-horizon default. 2015 remains exploratory; this is not a historical deployment backtest.

### 27_training_feature_profile

Source: [27_training_feature_profile.csv](results/27_training_feature_profile.csv). SHA-256: `684e0dc6c5324e1973b1ab00e78a7b261db028f1b479ebaffc9e47fe4c859e99`.

| feature | train_rows | nonmissing | missing | distinct_nonmissing | retained |
| --- | --- | --- | --- | --- | --- |
| annual_inc | 157,993 | 157,993 | 0 | 13,325 | 1 |
| application_type | 157,993 | 157,993 | 0 | 1 | 0 |
| credit_history_years | 157,993 | 157,993 | 0 | 603 | 1 |
| delinq_2yrs | 157,993 | 157,993 | 0 | 19 | 1 |
| dti | 157,993 | 157,993 | 0 | 3,499 | 1 |
| emp_length_years | 157,993 | 150,714 | 7,279 | 11 | 1 |
| fico_mid | 157,993 | 157,993 | 0 | 38 | 1 |
| home_ownership | 157,993 | 157,993 | 0 | 5 | 1 |
| loan_amnt | 157,993 | 157,993 | 0 | 1,175 | 1 |
| open_acc | 157,993 | 157,993 | 0 | 53 | 1 |
| pub_rec_bankruptcies | 157,993 | 157,993 | 0 | 9 | 1 |
| purpose | 157,993 | 157,993 | 0 | 13 | 1 |
| revol_bal | 157,993 | 157,993 | 0 | 39,758 | 1 |
| revol_util | 157,993 | 157,889 | 104 | 1,101 | 1 |

### 28_model_split_summary

Source: [28_model_split_summary.csv](results/28_model_split_summary.csv). SHA-256: `15353a5a6f5d37dd0e32c6794687307c2d750ffde5ee1b47eb7f1856311a5c1e`.

| split | rows | unique_loan_ids | first_issue_month | last_issue_month | fully_paid | charged_off | charged_off_pct | label_mismatches | duplicate_ids_in_population |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 157,993 | 157,993 | 2011-01-01 00:00:00 | 2013-12-01 00:00:00 | 138,213 | 19,780 | 12.519542 | 0 | 0 |
| validation | 162,570 | 162,570 | 2014-01-01 00:00:00 | 2014-12-01 00:00:00 | 140,255 | 22,315 | 13.726395 | 0 | 0 |
| exploratory_test | 283,026 | 283,026 | 2015-01-01 00:00:00 | 2015-12-01 00:00:00 | 240,894 | 42,132 | 14.886265 | 0 | 0 |

### 29_model_missingness

Source: [29_model_missingness.csv](results/29_model_missingness.csv). SHA-256: `2d60462c1dc0fdfbb68facbdb94c719f9c3d6d7ac0e64df934f48dc8ef425cfb`.

| split | feature | rows | missing | missing_pct |
| --- | --- | --- | --- | --- |
| exploratory_test | annual_inc | 283,026 | 2 | 0.000707 |
| exploratory_test | application_type | 283,026 | 0 | 0 |
| exploratory_test | credit_history_years | 283,026 | 0 | 0 |
| exploratory_test | delinq_2yrs | 283,026 | 0 | 0 |
| exploratory_test | dti | 283,026 | 2 | 0.000707 |
| exploratory_test | emp_length_years | 283,026 | 18,960 | 6.699031 |
| exploratory_test | fico_mid | 283,026 | 0 | 0 |
| exploratory_test | home_ownership | 283,026 | 0 | 0 |
| exploratory_test | loan_amnt | 283,026 | 0 | 0 |
| exploratory_test | open_acc | 283,026 | 0 | 0 |
| exploratory_test | pub_rec_bankruptcies | 283,026 | 0 | 0 |
| exploratory_test | purpose | 283,026 | 0 | 0 |
| exploratory_test | revol_bal | 283,026 | 0 | 0 |
| exploratory_test | revol_util | 283,026 | 126 | 0.044519 |
| train | annual_inc | 157,993 | 0 | 0 |
| train | application_type | 157,993 | 0 | 0 |
| train | credit_history_years | 157,993 | 0 | 0 |
| train | delinq_2yrs | 157,993 | 0 | 0 |
| train | dti | 157,993 | 0 | 0 |
| train | emp_length_years | 157,993 | 7,279 | 4.607166 |
| train | fico_mid | 157,993 | 0 | 0 |
| train | home_ownership | 157,993 | 0 | 0 |
| train | loan_amnt | 157,993 | 0 | 0 |
| train | open_acc | 157,993 | 0 | 0 |
| train | pub_rec_bankruptcies | 157,993 | 0 | 0 |
| train | purpose | 157,993 | 0 | 0 |
| train | revol_bal | 157,993 | 0 | 0 |
| train | revol_util | 157,993 | 104 | 0.065826 |
| validation | annual_inc | 162,570 | 0 | 0 |
| validation | application_type | 162,570 | 0 | 0 |
| validation | credit_history_years | 162,570 | 0 | 0 |
| validation | delinq_2yrs | 162,570 | 0 | 0 |
| validation | dti | 162,570 | 0 | 0 |
| validation | emp_length_years | 162,570 | 9,646 | 5.933444 |
| validation | fico_mid | 162,570 | 0 | 0 |
| validation | home_ownership | 162,570 | 0 | 0 |
| validation | loan_amnt | 162,570 | 0 | 0 |
| validation | open_acc | 162,570 | 0 | 0 |
| validation | pub_rec_bankruptcies | 162,570 | 0 | 0 |
| validation | purpose | 162,570 | 0 | 0 |
| validation | revol_bal | 162,570 | 0 | 0 |
| validation | revol_util | 162,570 | 77 | 0.047364 |

### 30_model_category_coverage

Source: [30_model_category_coverage.csv](results/30_model_category_coverage.csv). SHA-256: `3474dbddb35ff800d9c433fa645bb29b5a2a45943f53ae7c6fabb042c4a3e1c3`.

| split | feature | category | loans | seen_in_training |
| --- | --- | --- | --- | --- |
| exploratory_test | application_type | Individual | 282,787 | 1 |
| exploratory_test | application_type | Joint App | 239 | 0 |
| exploratory_test | home_ownership | ANY | 1 | 0 |
| exploratory_test | home_ownership | MORTGAGE | 129,762 | 1 |
| exploratory_test | home_ownership | OWN | 31,800 | 1 |
| exploratory_test | home_ownership | RENT | 121,463 | 1 |
| exploratory_test | purpose | car | 2,768 | 1 |
| exploratory_test | purpose | credit_card | 70,650 | 1 |
| exploratory_test | purpose | debt_consolidation | 160,983 | 1 |
| exploratory_test | purpose | educational | 1 | 0 |
| exploratory_test | purpose | home_improvement | 17,160 | 1 |
| exploratory_test | purpose | house | 1,004 | 1 |
| exploratory_test | purpose | major_purchase | 5,342 | 1 |
| exploratory_test | purpose | medical | 3,146 | 1 |
| exploratory_test | purpose | moving | 2,061 | 1 |
| exploratory_test | purpose | other | 15,227 | 1 |
| exploratory_test | purpose | renewable_energy | 185 | 1 |
| exploratory_test | purpose | small_business | 2,425 | 1 |
| exploratory_test | purpose | vacation | 2,071 | 1 |
| exploratory_test | purpose | wedding | 3 | 1 |
| train | application_type | Individual | 157,993 | 1 |
| train | home_ownership | MORTGAGE | 75,212 | 1 |
| train | home_ownership | NONE | 35 | 1 |
| train | home_ownership | OTHER | 40 | 1 |
| train | home_ownership | OWN | 13,339 | 1 |
| train | home_ownership | RENT | 69,367 | 1 |
| train | purpose | car | 2,187 | 1 |
| train | purpose | credit_card | 37,337 | 1 |
| train | purpose | debt_consolidation | 88,484 | 1 |
| train | purpose | home_improvement | 8,792 | 1 |
| train | purpose | house | 927 | 1 |
| train | purpose | major_purchase | 3,756 | 1 |
| train | purpose | medical | 1,621 | 1 |
| train | purpose | moving | 1,201 | 1 |
| train | purpose | other | 8,359 | 1 |
| train | purpose | renewable_energy | 152 | 1 |
| train | purpose | small_business | 2,613 | 1 |
| train | purpose | vacation | 1,045 | 1 |
| train | purpose | wedding | 1,519 | 1 |
| validation | application_type | Individual | 162,570 | 1 |
| validation | home_ownership | ANY | 1 | 0 |
| validation | home_ownership | MORTGAGE | 76,326 | 1 |
| validation | home_ownership | OWN | 16,493 | 1 |
| validation | home_ownership | RENT | 69,750 | 1 |
| validation | purpose | car | 1,516 | 1 |
| validation | purpose | credit_card | 40,100 | 1 |
| validation | purpose | debt_consolidation | 94,822 | 1 |
| validation | purpose | home_improvement | 8,654 | 1 |
| validation | purpose | house | 511 | 1 |
| validation | purpose | major_purchase | 2,888 | 1 |
| validation | purpose | medical | 1,885 | 1 |
| validation | purpose | moving | 1,133 | 1 |
| validation | purpose | other | 8,252 | 1 |
| validation | purpose | renewable_energy | 102 | 1 |
| validation | purpose | small_business | 1,634 | 1 |
| validation | purpose | vacation | 1,065 | 1 |
| validation | purpose | wedding | 8 | 1 |

### 31_model_unknown_categories

Source: [31_model_unknown_categories.csv](results/31_model_unknown_categories.csv). SHA-256: `b0e6db0632922d68584cca46917009067e3540ed5e98ff038cda711d40f19bfa`.

| split | feature | nonmissing_loans | unseen_category_loans | unseen_pct | unseen_categories |
| --- | --- | --- | --- | --- | --- |
| exploratory_test | application_type | 283,026 | 239 | 0.084445 | Joint App |
| exploratory_test | home_ownership | 283,026 | 1 | 0.000353 | ANY |
| exploratory_test | purpose | 283,026 | 1 | 0.000353 | educational |
| train | application_type | 157,993 | 0 | 0 | — |
| train | home_ownership | 157,993 | 0 | 0 | — |
| train | purpose | 157,993 | 0 | 0 | — |
| validation | application_type | 162,570 | 0 | 0 | — |
| validation | home_ownership | 162,570 | 1 | 0.000615 | ANY |
| validation | purpose | 162,570 | 0 | 0 | — |

### Prepared file inventory

| path | split | kind | rows | columns | bytes | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| data/clean/modeling/train.parquet | train | features_and_target | 157,993 | 14 | 2,051,149 | eac423f260cc81fd8eb9f11c1639e4cecd0f452b5ac8f9d57d12a788fb9d29c4 |
| data/clean/modeling/train_metadata.parquet | train | metadata | 157,993 | 4 | 239,324 | f7306739e7011bbc4493b9473090e3674446e8e73f3109b2127632f182052738 |
| data/clean/modeling/validation.parquet | validation | features_and_target | 162,570 | 14 | 2,119,125 | c645fc9a7eebc4d8755155be63c8ffd44a1cd3b606f127ccb294d4b998a24fbc |
| data/clean/modeling/validation_metadata.parquet | validation | metadata | 162,570 | 4 | 239,708 | 8703286db2f5e6143a9e9282224a14f42acd6b098fdbc9a981e774fd8309a0d2 |
| data/clean/modeling/exploratory_test.parquet | exploratory_test | features_and_target | 283,026 | 14 | 3,662,090 | 7d98e6c095b38287a1599aa241a061d8ca786a5894370e2ab6a4aeb16a553564 |
| data/clean/modeling/exploratory_test_metadata.parquet | exploratory_test | metadata | 283,026 | 4 | 394,587 | b94fdee9a5ae2d64badf43666f53d8f4f3c0c2c5f5100934a3f6aaeb15952c60 |

All six files are local and Git-ignored. Feature/target and metadata pairs share the same explicit issue-month/ID ordering. Nulls and tails are preserved. The manifest records 11 numeric and 2 categorical features; its exact lists are authoritative.

### Verification

EDA count/label reconciliation, unique IDs across splits, separated date ranges, exact output columns/row counts, and unchanged clean-source fingerprint passed. No MLflow, InterpretML, Kafka, or ELK measurements have been produced.

<!-- model-experiment-statistics -->

## 18. Model experiments

Completed: 2026-11-08T15:45:23+00:00.

Batch `72061e0a7a1e4d68addcc79a2aae631d`; selected `hist_gradient_boosting`. Selection uses validation average precision; threshold maximizes validation F1 before exploratory scoring. No refitting on validation and no fixed-horizon/deployment claim.

[Report](../docs/model_experiments.md), [latest manifest](results/model_experiments_latest.json). All rates below are fractions, not percentages. Fit/prediction times are single wall-clock observations, not stress-test metrics.

### Run and artifact identifiers

| model | run_id | model_uri | train_average_precision | validation_average_precision | validation_roc_auc | validation_brier_score | validation_log_loss | fit_seconds | validation_batch_predict_seconds | model_bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | 2bb4ea9b1159440bb0b51b66925247f3 | models:/m-c0cd1df22fa24744b5d207306fd84ac1 | 0.239525 | 0.216483 | 0.653889 | 0.114375 | 0.382348 | 2.025974 | 0.765676 | 412,754 |
| random_forest | 9b8a327a8a694086819d1818c141ba76 | models:/m-d5af0b19e25b4b169c0f5b3414373ad9 | 0.266368 | 0.213944 | 0.649133 | 0.114923 | 0.384513 | 13.763563 | 0.92611 | 11,497,147 |
| logistic_regression | b6cd84c99ba24a8f854b2b7941ee3b88 | models:/m-9b48e925f4a54600a0eeeacf7eb183c1 | 0.199628 | 0.21028 | 0.646231 | 0.114869 | 0.384341 | 0.958238 | 0.273507 | 7,242 |
| dummy_prior | e017e1e02bb743669f6f3f8e804a1c36 | models:/m-c6c8b6403be04d378ecd4ee0149b6fdd | 0.125195 | 0.137264 | 0.5 | 0.118568 | 0.400613 | 0.555652 | 0.235392 | 4,882 |

### All training and validation metrics at threshold 0.5

| model | split | rows | observed_positive_rate | threshold | roc_auc | average_precision | brier_score | log_loss | ece_10_uniform_bins | accuracy | balanced_accuracy | precision | recall | specificity | f1 | predicted_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dummy_prior | train | 157,993 | 0.125195 | 0.5 | 0.5 | 0.125195 | 0.109522 | 0.37715 | 0 | 0.874805 | 0.5 | 0 | 0 | 1 | 0 | 0 | 138,213 | 0 | 19,780 | 0 |
| dummy_prior | validation | 162,570 | 0.137264 | 0.5 | 0.5 | 0.137264 | 0.118568 | 0.400613 | 0.012069 | 0.862736 | 0.5 | 0 | 0 | 1 | 0 | 0 | 140,255 | 0 | 22,315 | 0 |
| logistic_regression | train | 157,993 | 0.125195 | 0.5 | 0.650936 | 0.199628 | 0.106127 | 0.36132 | 0.002319 | 0.874792 | 0.500101 | 0.416667 | 0.000253 | 0.999949 | 0.000505 | 0.000076 | 138,206 | 7 | 19,775 | 5 |
| logistic_regression | validation | 162,570 | 0.137264 | 0.5 | 0.646231 | 0.21028 | 0.114869 | 0.384341 | 0.006675 | 0.862705 | 0.500152 | 0.391304 | 0.000403 | 0.9999 | 0.000806 | 0.000141 | 140,241 | 14 | 22,306 | 9 |
| random_forest | train | 157,993 | 0.125195 | 0.5 | 0.711889 | 0.266368 | 0.103944 | 0.352131 | 0.019663 | 0.874805 | 0.5 | 0 | 0 | 1 | 0 | 0 | 138,213 | 0 | 19,780 | 0 |
| random_forest | validation | 162,570 | 0.137264 | 0.5 | 0.649133 | 0.213944 | 0.114923 | 0.384513 | 0.013567 | 0.862736 | 0.5 | 0 | 0 | 1 | 0 | 0 | 140,255 | 0 | 22,315 | 0 |
| hist_gradient_boosting | train | 157,993 | 0.125195 | 0.5 | 0.684525 | 0.239525 | 0.104177 | 0.353495 | 0.008189 | 0.874805 | 0.5 | 0 | 0 | 1 | 0 | 0 | 138,213 | 0 | 19,780 | 0 |
| hist_gradient_boosting | validation | 162,570 | 0.137264 | 0.5 | 0.653889 | 0.216483 | 0.114375 | 0.382348 | 0.005851 | 0.862736 | 0.5 | 0 | 0 | 1 | 0 | 0 | 140,255 | 0 | 22,315 | 0 |

### Frozen-threshold and default-threshold evaluations

| model | split | policy | rows | observed_positive_rate | threshold | roc_auc | average_precision | brier_score | log_loss | ece_10_uniform_bins | accuracy | balanced_accuracy | precision | recall | specificity | f1 | predicted_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | validation | validation_f1 | 162,570 | 0.137264 | 0.147853 | 0.653889 | 0.216483 | 0.114375 | 0.382348 | 0.005851 | 0.651689 | 0.607648 | 0.207851 | 0.546942 | 0.668354 | 0.301228 | 0.361198 | 93,740 | 46,515 | 10,110 | 12,205 |
| hist_gradient_boosting | exploratory_test | default_0.5 | 283,026 | 0.148863 | 0.5 | 0.65435 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.851137 | 0.5 | 0 | 0 | 1 | 0 | 0 | 240,894 | 0 | 42,132 | 0 |
| hist_gradient_boosting | exploratory_test | validation_f1 | 283,026 | 0.148863 | 0.147853 | 0.65435 | 0.235027 | 0.122279 | 0.402502 | 0.01664 | 0.650467 | 0.606918 | 0.22352 | 0.544906 | 0.668929 | 0.317005 | 0.362903 | 161,141 | 79,753 | 19,174 | 22,958 |

### Complete calibration bins

| bin | rows | mean_probability | observed_positive_rate | bin_lower | bin_upper | model | split |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 162,570 | 0.125195 | 0.137264 | 0.1 | 0.2 | dummy_prior | validation |
| 0 | 53,522 | 0.069943 | 0.072363 | 0 | 0.1 | logistic_regression | validation |
| 1 | 87,824 | 0.142997 | 0.15153 | 0.1 | 0.2 | logistic_regression | validation |
| 2 | 19,082 | 0.233308 | 0.237187 | 0.2 | 0.3 | logistic_regression | validation |
| 3 | 1,898 | 0.333182 | 0.285037 | 0.3 | 0.4 | logistic_regression | validation |
| 4 | 221 | 0.429823 | 0.262443 | 0.4 | 0.5 | logistic_regression | validation |
| 5 | 19 | 0.525766 | 0.368421 | 0.5 | 0.6 | logistic_regression | validation |
| 6 | 3 | 0.635431 | 0.666667 | 0.6 | 0.7 | logistic_regression | validation |
| 7 | 1 | 0.712114 | 0 | 0.7 | 0.8 | logistic_regression | validation |
| 0 | 44,870 | 0.075431 | 0.065099 | 0 | 0.1 | random_forest | validation |
| 1 | 106,839 | 0.143105 | 0.154625 | 0.1 | 0.2 | random_forest | validation |
| 2 | 10,859 | 0.217648 | 0.264665 | 0.2 | 0.3 | random_forest | validation |
| 3 | 2 | 0.302169 | 0 | 0.3 | 0.4 | random_forest | validation |
| 0 | 56,022 | 0.069814 | 0.070008 | 0 | 0.1 | hist_gradient_boosting | validation |
| 1 | 83,144 | 0.143583 | 0.151917 | 0.1 | 0.2 | hist_gradient_boosting | validation |
| 2 | 22,039 | 0.232513 | 0.242434 | 0.2 | 0.3 | hist_gradient_boosting | validation |
| 3 | 1,333 | 0.325751 | 0.304576 | 0.3 | 0.4 | hist_gradient_boosting | validation |
| 4 | 32 | 0.423127 | 0.40625 | 0.4 | 0.5 | hist_gradient_boosting | validation |
| 0 | 97,697 | 0.069638 | 0.076686 | 0 | 0.1 | hist_gradient_boosting | exploratory_test |
| 1 | 143,382 | 0.143601 | 0.164916 | 0.1 | 0.2 | hist_gradient_boosting | exploratory_test |
| 2 | 39,387 | 0.233228 | 0.255694 | 0.2 | 0.3 | hist_gradient_boosting | exploratory_test |
| 3 | 2,491 | 0.326595 | 0.358491 | 0.3 | 0.4 | hist_gradient_boosting | exploratory_test |
| 4 | 69 | 0.428431 | 0.434783 | 0.4 | 0.5 | hist_gradient_boosting | exploratory_test |

### Configuration and reproducibility

```json
{
  "seed": 42,
  "thread_limit": 4,
  "features": [
    "loan_amnt",
    "annual_inc",
    "dti",
    "revol_util",
    "revol_bal",
    "open_acc",
    "delinq_2yrs",
    "pub_rec_bankruptcies",
    "emp_length_years",
    "fico_mid",
    "credit_history_years",
    "home_ownership",
    "purpose"
  ],
  "selected_threshold": 0.147852896338396,
  "threshold_rule": "maximum validation F1; ties choose lowest threshold",
  "versions": {
    "scikit-learn": "1.9.1",
    "mlflow": "3.18.0",
    "numpy": "2.5.4",
    "pandas": "3.1.0",
    "scipy": "1.18.1",
    "joblib": "1.6.0",
    "cloudpickle": "3.1.2",
    "threadpoolctl": "3.8.0"
  },
  "selected_model_uri": "models:/m-c0cd1df22fa24744b5d207306fd84ac1",
  "selected_run_id": "2bb4ea9b1159440bb0b51b66925247f3",
  "selected_joblib_sha256": "beb4491348dfa7022290768ef79c8150fd7d14a722ef5b3ac78902fa9f0cc078",
  "data_manifest_sha256": "30c0f906e863958036341518c8ed53fccf3f558e1a371887c18880430bbdb2f9",
  "training_script_sha256": "b5b42c0665874508f73fff0040e6e80d56fa2658a7e0bc1ed987de4041952c4a"
}
```

Full estimator and preprocessing parameters for every model are preserved under `configurations` in the linked experiment manifest and in each MLflow run. Numeric indicators cover all numeric features; all learned preprocessing was fitted only on training data. No oversampling or class weighting was used.

### Earlier failed attempts

| run_id | status | tags.mlflow.runName |
| --- | --- | --- |
| 6af601cdfa0e4a64b4782434a2365f14 | FAILED | logistic_regression |
| 18a7762e46144ccf86a18277cf2013f7 | FAILED | first_model_comparison |

Earlier failed run records are retained for transparency; the completed-batch comparisons above do not combine their results. The first logging attempt stopped on a duplicated class-weight parameter with inconsistent string values before logistic regression fitting.

### Saved result fingerprints

- [model_comparison.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/model_comparison.csv): `f244f43833288f427cb13abcb642781007870738197c484a3203d3e671159466`

- [train_validation_metrics.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/train_validation_metrics.csv): `f07a3991f29c1b4afb336740a615867a38e2da8a4360b587ff1329cba4622525`

- [selected_model_metrics.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/selected_model_metrics.csv): `8112374b3b17a95cc5f9fc7ab0078820a4184c7cda6e62b89c4d6d4b17bba351`

- [calibration_bins.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/calibration_bins.csv): `314ef5ebdbce94be0df605279462a834f0a99ce4e4e0126d1e727ba9830a0904`

- [curve_points.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/curve_points.csv): `e5336e06d2c95b302d3dbe92b19ba4ee8941cd9baadbcc81f1a8624683493392`

Curve-point files retain at most 256 points per model/curve. They are plotting data; scalar metrics and threshold choice use all predictions. Full bin counts, confusion matrices, batch timings, model sizes, versions, identifiers, and aggregate metrics are recorded above or in the manifest. Uncertainty, bias, interpretability, and stress-test metrics remain Not measured.

### Verification

Prepared dataset hashes matched; all four local pipelines reloaded with equivalent scores. Selected native and MLflow sklearn/pyfunc probability outputs matched. Model selection and threshold fitting used validation only; only the selected model scored the exploratory dataset.

<!-- mlflow-evaluation-visibility-statistics -->

## 19. MLflow datasets and evaluations

Completed: 2026-11-08T16:15:06+00:00. Parent run: `72061e0a7a1e4d68addcc79a2aae631d`. Models, selection, and frozen threshold are unchanged.

### Dataset inputs on the comparison run

| dataset | digest | rows |
| --- | --- | --- |
| train | 3fc22603 | 157993 |
| validation | 722bf1f9 | 162570 |
| exploratory_test | 38c881ae | 283026 |

The full three Parquet datasets and their manifest are stored under the parent run's datasets/ artifacts. Parent previews are 200 rows each. Model metrics have explicit dataset name/digest associations, verified through MlflowClient.get_logged_model.

### All native evaluation metrics and identifiers

| model | split | evaluation_run_id | source_training_run_id | model_id | dataset_name | dataset_digest | decision_threshold | score | true_negatives | false_positives | false_negatives | true_positives | example_count | accuracy_score | recall_score | precision_score | f1_score | log_loss | roc_auc | precision_recall_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dummy_prior | validation | 76124a42a3c84a639a451e8c0bf94edd | e017e1e02bb743669f6f3f8e804a1c36 | m-c6c8b6403be04d378ecd4ee0149b6fdd | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.400613 | 0.5 | 0.137264 |
| logistic_regression | validation | 737b3f235d1949e5a15552a9ce68d142 | b6cd84c99ba24a8f854b2b7941ee3b88 | m-9b48e925f4a54600a0eeeacf7eb183c1 | validation | 722bf1f9 | 0.5 | 0.862705 | 140241 | 14 | 22306 | 9 | 162570 | 0.862705 | 0.000403 | 0.391304 | 0.000806 | 0.384341 | 0.646231 | 0.21028 |
| random_forest | validation | 8dcf18dc8f7744c7950bb7c0e29fba88 | 9b8a327a8a694086819d1818c141ba76 | m-d5af0b19e25b4b169c0f5b3414373ad9 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.384513 | 0.649133 | 0.213944 |
| hist_gradient_boosting | validation | 19d602239b3a43a595bcd17d8a39fc4a | 2bb4ea9b1159440bb0b51b66925247f3 | m-c0cd1df22fa24744b5d207306fd84ac1 | validation | 722bf1f9 | 0.5 | 0.862736 | 140255 | 0 | 22315 | 0 | 162570 | 0.862736 | 0 | 0 | 0 | 0.382348 | 0.653889 | 0.216483 |
| hist_gradient_boosting | exploratory_test | 0ba9fd0f56b8480f842795151fbfabb2 | 2bb4ea9b1159440bb0b51b66925247f3 | m-c0cd1df22fa24744b5d207306fd84ac1 | exploratory_test | 38c881ae | 0.5 | 0.851137 | 240894 | 0 | 42132 | 0 | 283026 | 0.851137 | 0 | 0 | 0 | 0.402502 | 0.65435 | 0.235027 |

Source: [mlflow_native_evaluations.csv](results/experiments/72061e0a7a1e4d68addcc79a2aae631d/mlflow_native_evaluations.csv). SHA-256: `92d09f5f1082f8c1fe19e71856556c3cef476edc4b14f3958fb56b1259c02eb8`.

Native metrics evaluate the full 162,570 validation rows for each model and 283,026 exploratory rows for the selected model. The classifier's default rule is 0.5; custom frozen-threshold metrics remain separate on the selected training run. Native binary precision_recall_auc matches this MLflow version's average precision; no selection was changed.

Each evaluation run has ROC, PR, lift, calibration, and confusion-matrix artifacts, a dataset input, model linkage, and a 1,000-row uniformly sampled evaluation table (seed 42). Sample rows are not the population used to compute metrics. No explanation/SHAP evaluation was enabled.

### Verification

All five evaluation runs finished successfully. Each has its full dataset input and a logged table artifact. All four logged models have dataset-linked train/validation metrics, and the selected model also has exploratory metrics. All three comparison dataset inputs are persisted. Original validation ROC-AUC values and cohort counts match; no retraining or policy change occurred. These checks concern classic ML evaluations, not the separate GenAI dataset/scorer system.
