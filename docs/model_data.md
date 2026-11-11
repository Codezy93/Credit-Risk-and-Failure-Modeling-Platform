# Prepared model datasets

Terminology: [lifetime charge-off probability, snapshot loss proxies and illustrative capital](risk_terminology.md).

Prepared: 2026-11-08T15:27:11+00:00.

The clean analysis table has been filtered into the EDA-approved retrospective
benchmark: 36-month loans issued in 2011–2015 with an ordinary Fully Paid or
Charged Off outcome. The source Parquet is unchanged; its SHA-256 is
`51e966cd9162ff4fd77c6dafd4afe7143dca4e97ee4053cabe07eaa2ac6d3e20`. There are 603,589 eligible loans across the
three splits, matching the final EDA counts. The 147 other-status 2015 loans were
excluded by the existing outcome rule, not treated as negative labels.

## Split counts

| split | rows | unique_loan_ids | first_issue_month | last_issue_month | fully_paid | charged_off | charged_off_pct | label_mismatches | duplicate_ids_in_population |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 157,993 | 157,993 | 2011-01-01 00:00:00 | 2013-12-01 00:00:00 | 138,213 | 19,780 | 12.519542 | 0 | 0 |
| validation | 162,570 | 162,570 | 2014-01-01 00:00:00 | 2014-12-01 00:00:00 | 140,255 | 22,315 | 13.726395 | 0 | 0 |
| exploratory_test | 283,026 | 283,026 | 2015-01-01 00:00:00 | 2015-12-01 00:00:00 | 240,894 | 42,132 | 14.886265 | 0 | 0 |

## Features and preprocessing

The 14 EDA candidates were profiled using **training rows only**. The retained
predictor count is **13**: `loan_amnt`, `annual_inc`, `dti`, `revol_util`, `revol_bal`, `open_acc`, `delinq_2yrs`, `pub_rec_bankruptcies`, `emp_length_years`, `fico_mid`, `credit_history_years`, `home_ownership`, `purpose`.

Dropped from the candidate list: **application_type**. A feature is
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
