# Download and setup

The source is the accepted-loans file from the LendingClub dataset
`wordsforthewise/lending-club` on Kaggle. Raw loan data stays outside Git.

## Environment

From the repository root:

```bash
make setup
```

This installs the locked modelling environment. The separate streaming setup
is described in the [Kafka and PySpark guide](streaming.md).

## Download

```bash
.venv-locked/bin/python scripts/download_data.py
```

The script downloads `accepted_2007_to_2018Q4.csv.gz` using `kagglehub`
and extracts it to `data/raw/accepted_2007_to_2018Q4.csv`.
Kaggle access and any required authentication must be available in your environment.
If the CSV already exists, the script leaves it in place. If the compressed file
already exists, it uses that file. Extraction writes a temporary `.csv.part`
file and renames it after completion.

## Analysis

SQL queries live in `sql/`; notebook sources live in `notebooks/`.
Raw and cleaned data live in `data/raw/` and `data/clean/`.
Saved tables and figures live in `assets/results/` and `assets/figures/`.

Read the [EDA report](eda_summary.md) for cleaning decisions and findings,
then the [model dataset report](model_data.md) for the feature contract and split.
The [reproducibility report](reproducibility.md) lists the executed workflow.
