from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from util.segment_audit import disparity_summary, segment_metrics, wilson_interval


def test_metrics_use_shared_threshold_and_correct_error_denominators():
    row = segment_metrics([0, 1, 1, 0], [0.2, 0.1, 0.8, 0.7], 0.5, min_rows=1, min_class_rows=1)
    assert [row[name] for name in ["tp", "fp", "fn", "tn"]] == [1, 1, 1, 1]
    assert row["tpr"] == row["fpr"] == row["precision"] == row["flag_rate"] == 0.5
    assert row["roc_auc"] == 0.5
    assert row["brier_score"] == pytest.approx(0.345)
    assert row["calibration_bias"] == pytest.approx(-0.05)
    assert row["supported"]


def test_small_single_class_and_undefined_precision_are_visible():
    row = segment_metrics([0, 0], [0.1, 0.2], 0.5)
    assert not row["supported"] and "few_charged_off" in row["support_reason"]
    assert np.isnan(row["roc_auc"]) and np.isnan(row["precision"]) and np.isnan(row["tpr"])
    assert row["fpr"] == 0
    assert row["observed_rate_lower_95"] == 0


def test_zero_flags_do_not_look_like_a_fairness_pass():
    rows = []
    for label in ("A", "B"):
        rows.append({"split": "validation", "policy": "default", "dimension": "home", "group": label,
            **segment_metrics([0, 1, 0, 1], [0.1, 0.2, 0.2, 0.3], 0.5, min_rows=1, min_class_rows=1)})
    summary = disparity_summary(pd.DataFrame(rows))[0]
    assert summary["all_groups_zero_flags"]
    assert summary["flag_rate_spread"] == 0
    assert "fairness_pass" not in summary


def test_wilson_bounds_and_zero_denominators():
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2365930905)
    assert hi == pytest.approx(0.7634069095)
    assert all(np.isnan(x) for x in wilson_interval(0, 0))
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_sql_segments_keep_missing_loans_and_training_cut_boundaries():
    frame = pd.DataFrame({"loan_id": [1, 2, 3, 4], "split": "validation", "charged_off": [0, 1, 0, 1],
        "probability": [0.1, 0.2, 0.1, 0.3], "home_ownership": ["RENT", "OWN", None, "MORTGAGE"],
        "purpose": "credit_card", "annual_inc": [10000, 20000, 40000, None], "fico_mid": [670, 700, 740, None],
        "emp_length_years": [0, 5, 10, None], "delinq_2yrs": [0, 1, 0, None],
        "pub_rec_bankruptcies": [0, 0, 1, None], "has_missing_predictor": [False, False, False, True],
        "addr_state": ["NY", "CA", None, "TX"], "application_type": "Individual"})
    con = duckdb.connect()
    con.register("audit_population", frame)
    for name, value in [("income_q1", 10000), ("income_q2", 20000), ("income_q3", 30000)]:
        con.execute(f"SET VARIABLE {name}=?", [value])
    con.execute((Path(__file__).resolve().parents[1] / "sql/38_audit_segments.sql").read_text())
    result = con.execute("SELECT * FROM audit_segments ORDER BY loan_id").df()
    con.close()
    assert len(result) == 4 and result.loan_id.nunique() == 4
    assert result.income_group.tolist() == ["Q1_lowest", "Q2", "Q4_highest", "Missing"]
    assert result.fico_group.tolist() == ["Below_680", "680_to_719", "720_to_759", "Missing"]
    assert result.state_group.tolist() == ["NY", "CA", "Missing", "TX"]
