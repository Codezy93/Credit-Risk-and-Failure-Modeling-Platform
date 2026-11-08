# Project statistics reference

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

## 1. Quick answers

| Statistic | Value |
| --- | --- |
| Completed stage | Download, SQL cleaning, and marimo exploratory analysis |
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
| Saved figure sets | 17 |
| Saved image files | 34 |
| Saved result CSVs | 21 |
| Deterministic scatterplot sample | 20,000 |
| Models trained / MLflow evaluation metrics | Not measured; training stage not implemented |
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

**Current state: not implemented or measured.** No trained model, MLflow experiment result, fitted preprocessing pipeline, or selected champion exists in this stage. An empty model folder is not evidence of measured zero-valued metrics.

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

Updated: 2026-11-08T14:59:36+00:00. The original statistics and artifact inventory in sections 2–14 describe the first EDA snapshot. Quick-answer artifact counts include this follow-up. No model or stress-test measurements have been added.

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
