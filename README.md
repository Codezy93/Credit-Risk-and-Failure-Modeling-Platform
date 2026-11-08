# Credit Risk and Failure Modeling Platform

A credit-risk project using LendingClub loan data. EDA is complete, with SQL
audits, three marimo notebooks, saved figures, a feature-availability review, and
a documented retrospective benchmark. Model datasets are prepared; model training
has not started.

Start with the [final EDA report](docs/eda_summary.md) and
[complete statistics reference](assets/statistics.md). The
[clean-table dictionary](docs/data_dictionary.md) records the feature decisions.

## Folder structure

```text
sql/                SQL cleaning, validation, and EDA queries
data/raw/           Original downloaded data
data/clean/         Cleaned modeling data
models/             Saved models and metadata
scripts/            Data preparation, training, and streaming scripts
util/               Shared helpers and logging
util/elk/           ELK setup and monitoring scripts
docs/               GitHub Pages website and project documentation
assets/figures/     EDA plots and model explanations
assets/results/     Evaluation and benchmark results
```

## Download the data

Run from the project root with Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/download_data.py
```

Source: [All Lending Club loan data on Kaggle](https://www.kaggle.com/datasets/wordsforthewise/lending-club).
The script downloads only `accepted_2007_to_2018Q4.csv.gz` from the latest dataset
version and unpacks it as `data/raw/accepted_2007_to_2018Q4.csv`. It keeps the
compressed original too, so leave several GB of free disk space. It skips the
download if the final CSV already exists.

If Kaggle requests authentication, run:

```bash
python -c "import kagglehub; kagglehub.login()"
```

Follow the prompt using a token from your
[Kaggle API settings](https://www.kaggle.com/settings/api). If Kaggle asks you to
accept dataset terms, do that on the dataset page before rerunning the script.
See the [KaggleHub documentation](https://github.com/Kaggle/kagglehub) for details.

Raw data, cleaned data, and saved models are excluded from Git. Figures and
selected results can be committed for the project showcase.

## Explore and clean the data with marimo

After downloading the CSV, install the updated dependencies and open the notebook:

```bash
python -m pip install -r requirements.txt
marimo edit scripts/01_data_analysis.py
```

Run all cells in order. The notebook executes the numbered files in `sql/` using
DuckDB, so the large raw CSV is not loaded into a pandas DataFrame. It audits
source rows and missingness, creates a typed analysis table, and explores:

- Numeric distributions, percentiles, extreme values, and category counts.
- Outcome balance and bivariate relationships with grades, purposes, income,
  credit scores, and debt burden.
- Grade/term and grade/cohort interactions, feature correlations, and sampled
  relationships.
- Outcome coverage across years and the limitations of resolved-only comparisons.

Detailed feature and outcome exploration uses loans issued through 2015. Later
cohorts are checked only for status coverage. The initial proposal to validate on
2016 and test on 2017–2018 was superseded at EDA completion because of low outcome
coverage. The final retrospective benchmark uses resolved 36-month loans from
2011–2015; see the final EDA report for the split and limitations. These are not
fixed-horizon default labels.

The notebook writes:

| Location | Output |
| --- | --- |
| `data/clean/lending_club.duckdb` | Local SQL database with `loans` and development-only `eda_loans` |
| `data/clean/loans.parquet` | Clean analysis table, including unresolved loans |
| `assets/figures/` | PNG and SVG charts |
| `assets/results/` | Query result CSVs and `analysis_findings.md` |

`loans.parquet` is not a model feature matrix: it includes `loan_status` and
`charged_off` for analysis. Those must never be used as input features. Cleaning
preserves missing values; preprocessing will be fitted on training data later.

To run every cell and export a standalone report without opening the editor:

```bash
marimo export html scripts/01_data_analysis.py -o docs/data_analysis.html --no-include-code
```

This command executes the notebook before exporting, as described in the
[marimo export documentation](https://docs.marimo.io/guides/exporting/static_html/).
SQL uses [DuckDB's CSV reader](https://duckdb.org/docs/stable/data/csv/overview).
The first run scans the full CSV several times and needs a few minutes and extra
local disk space. Keep the notebook open for exploration, and close its kernel
before running a separate export against the same local database.

## Follow-up EDA

The second notebook investigates questions raised by the first pass:

```bash
marimo edit scripts/02_deeper_eda.py
```

It reads `data/clean/loans.parquet` and runs SQL files `14`–`19` to inspect extreme
values, missingness over time and by outcome, loan/income ratios, FICO/DTI
interactions, and changes in development-cohort composition. It uses originations
through 2015; the FICO/DTI comparison uses 36-month loans from 2011–2014 and reports
its outcome coverage. It preserves the clean data and performs no model training.

The notebook saves six additional PNG/SVG figures, six CSV tables, and
`assets/results/deeper_eda_findings.md`. It refreshes section 15 of
[the statistics reference](assets/statistics.md) with all follow-up tables.
Sections 2–14 retain their original EDA snapshot and provenance.

Export the follow-up report with:

```bash
marimo export html scripts/02_deeper_eda.py -o docs/deeper_eda.html --no-include-code
```

## EDA completion

```bash
marimo edit scripts/03_complete_eda.py
```

The final notebook runs SQL files `20`–`25`, completes numeric/category profiles
and parsing checks, audits all 151 source and 26 clean columns, and records 14
candidate features. It adds four figure sets, dictionaries, benchmark eligibility
counts, a completion manifest, and section 16 of `assets/statistics.md`.

The first benchmark is charged off among ordinary resolved **36-month loans
issued in 2011–2015**: training 2011–2013, validation 2014, exploratory evaluation
2015. All these years were inspected during EDA. The benchmark does not represent
a pristine holdout, a fixed-horizon default probability, or a deployment backtest.
It has no established point-in-time outcome availability. Those limits must
accompany future model results.

```bash
marimo export html scripts/03_complete_eda.py -o docs/eda_completion.html --no-include-code
```

Read [the final summary](docs/eda_summary.md),
[the final HTML report](docs/eda_completion.html), and
[the dictionary](docs/data_dictionary.md) without rerunning the notebooks.
Raw and clean data are preserved. The EDA stage fits no preprocessing; model-data
preparation is a separate step below.

## Prepare model datasets

```bash
python scripts/04_prepare_model_data.py
```

This reads the existing clean Parquet and executes SQL files `26`–`31`. It writes
three feature/target datasets and three matching metadata files to
`data/clean/modeling/`, with counts and fingerprints in
`assets/results/model_data_manifest.json`. No raw-data download or EDA rerun is
needed. All six dataset files are excluded from Git.

| Split | Issue years | Rows |
| --- | --- | --- |
| Training | 2011–2013 | 157,993 |
| Validation | 2014 | 162,570 |
| Exploratory evaluation | 2015 | 283,026 |

The training-only feature profile removes constant `application_type`, leaving
13 predictors. IDs, dates, application type, and target status are excluded from
predictors; application type remains in audit metadata. Dataset files contain
the exact predictor list plus the binary `charged_off` target. Read the feature
lists from the manifest rather than selecting every available column.

Missing values and extreme values are preserved. Imputation, scaling, category
encoding, and model fitting have not started. Validation/evaluation include some
categories not seen in training; future encoders must handle them explicitly.

See [the dataset contract](docs/model_data.md) and
[statistics section 17](assets/statistics.md#17-model-data-preparation) for the
full checks, category/missingness tables, and limitations. The evaluation remains
exploratory and does not establish fixed-horizon default risk or historical
deployment performance.
