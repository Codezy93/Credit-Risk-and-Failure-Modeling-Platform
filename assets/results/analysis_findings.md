# LendingClub analysis findings

## Data and population

- Raw rows: 2,260,701; clean rows: 2,260,668.
- Development originations (through 2015): 887,440.
- Resolved means ordinary Fully Paid or Charged Off; other statuses have no binary label.
- Detailed feature/outcome EDA uses development years only. All-year status coverage is a limited holdout inspection, not a completely untouched test set.

## Observations

- Charged off among resolved development loans: 18.43%.
- Grade A: 5.57% across 146,430 resolved loans; grade G: 46.74% across 4,865.
- Development annual income: median $65,000, p99 $250,000, maximum $9,500,000. The tail needs investigation before choosing a transform.
- Only 11.4% of the latest issue-year cohort has an ordinary resolved outcome. Do not label remaining loans as successful repayments.

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
