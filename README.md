# Credit Risk and Failure Modeling Platform

A credit-risk project using LendingClub loan data. The current step sets up the
project folders and downloads the raw dataset.

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
cohorts are checked only for status coverage, with 2016 provisionally reserved for
validation and 2017–2018 for testing. A prediction horizon and maturity rule still
need to be chosen before training; these are not fixed-horizon default labels.

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
