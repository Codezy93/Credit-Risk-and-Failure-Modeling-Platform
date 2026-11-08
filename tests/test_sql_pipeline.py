from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_footer_invalid_date_and_keys(database):
    raw = database.execute((ROOT / "sql/01_raw_audit.sql").read_text()).df().iloc[0]
    assert raw.raw_rows == 16
    assert raw.invalid_id_rows == 1
    assert raw.invalid_issue_dates == 2
    clean = database.execute("SELECT * FROM loans").df()
    assert len(clean) == clean.loan_id.nunique() == 14
    assert len(clean.columns) == 26
    assert 1015 not in set(clean.loan_id)


def test_conversions_missingness_and_derived_values(database):
    rows = database.execute("SELECT * FROM loans").df().set_index("loan_id")
    assert pd.isna(rows.loc[1002, "annual_inc"])
    assert pd.isna(rows.loc[1002, "dti"])
    assert pd.isna(rows.loc[1003, ["annual_inc", "dti", "revol_util"]]).all()
    assert rows.loc[1001, "fico_mid"] == 682
    assert rows.loc[1001, "emp_length_years"] == 10
    assert rows.loc[1007, "emp_length_years"] == 0
    assert rows.loc[1001, "credit_history_years"] == 11
    assert pd.isna(rows.loc[1008, "credit_history_years"])
    audit = database.execute((ROOT / "sql/25_numeric_source_parsing.sql").read_text()).df().set_index("feature")
    assert audit.loc["annual_inc", "parse_failures"] == 1
    assert audit.loc["dti", "parse_failures"] == 1
    assert audit.parse_failures.sum() == 2


def test_exact_target_keeps_unresolved_and_policy_statuses_unlabeled(database):
    rows = database.execute("SELECT loan_id, charged_off FROM loans").df().set_index("loan_id")
    assert rows.loc[1001, "charged_off"] == 0
    assert rows.loc[1002, "charged_off"] == 1
    assert rows.loc[[1004, 1009, 1010, 1011, 1012], "charged_off"].isna().all()


def test_snapshot_payment_and_updated_fico_fields_never_enter_clean_table(database):
    names = set(database.execute("DESCRIBE loans").df().column_name)
    assert not names.intersection({"total_pymnt", "recoveries", "last_fico_range_low", "last_fico_range_high"})
    assert database.execute("SELECT fico_mid FROM loans WHERE loan_id=1001").fetchone()[0] == 682


def test_model_sql_filters_and_orders_periods(database, tmp_path):
    path = tmp_path / "clean.parquet"
    database.execute("COPY loans TO ? (FORMAT PARQUET)", [str(path)])
    database.execute("SET VARIABLE clean_path=?", [str(path)])
    database.execute((ROOT / "sql/26_model_population.sql").read_text())
    rows = database.execute("SELECT * FROM model_population ORDER BY issue_date, loan_id").df()
    assert rows.loan_id.tolist() == [1001, 1002, 1003, 1005, 1006, 1007, 1008]
    assert rows.split.tolist() == ["train"] * 3 + ["validation"] * 2 + ["exploratory_test"] * 2
    assert set(rows.charged_off) == {0, 1}
    # A fake extreme repayment amount and last-FICO value cannot change the input score fields.
    np.testing.assert_array_equal(rows.fico_mid, np.full(7, 682))
