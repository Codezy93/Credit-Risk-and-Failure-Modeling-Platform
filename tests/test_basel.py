from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from util.basel import expected_loss, other_retail_capital, score_loss_bundle
from util.feature_policy import validate_features


def test_expected_loss_and_capital_scaling():
    np.testing.assert_allclose(expected_loss([0.1, 0.2], 0.5, 10000), [500, 1000])
    a = other_retail_capital(0.01, 0.45, 10000).iloc[0]
    b = other_retail_capital(0.01, 0.9, 20000).iloc[0]
    assert 0.03 < a.correlation < 0.16
    assert 0 < a.capital_ratio < 0.45
    assert b.capital == pytest.approx(4 * a.capital)
    assert a.rwa == pytest.approx(a.capital * 12.5)
    assert a.expected_loss_one_year_scenario == pytest.approx(45)
    assert other_retail_capital(0.01, 0, 10000).capital.iloc[0] == 0


@pytest.mark.parametrize("pd_score,lgd,ead", [(0, 0.5, 1), (1, 0.5, 1), (0.1, -0.1, 1),
    (0.1, 1.1, 1), (0.1, 0.5, -1), (np.nan, 0.5, 1)])
def test_invalid_capital_inputs_are_rejected(pd_score, lgd, ead):
    with pytest.raises(ValueError):
        other_retail_capital(pd_score, lgd, ead)


def test_loss_outcomes_remain_outside_pd_features():
    for feature in ["funded_amnt", "ead_snapshot_proxy", "lgd_snapshot_proxy", "total_rec_prncp", "recoveries", "collection_recovery_fee"]:
        with pytest.raises(ValueError):
            validate_features(["loan_amnt", feature])


def test_loss_bundle_scoring_after_reload(tmp_path):
    import joblib
    from sklearn.dummy import DummyClassifier, DummyRegressor

    x = pd.DataFrame({"loan_amnt": [1000, 2000, 3000, 4000]})
    bundle = {"features": ["loan_amnt"],
        "pd_model": DummyClassifier(strategy="prior").fit(x, [0, 0, 0, 1]),
        "ead_ratio_model": DummyRegressor(strategy="constant", constant=0.5).fit(x, [0.5]*4),
        "lgd_model": DummyRegressor(strategy="constant", constant=0.8).fit(x, [0.8]*4)}
    path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, path)
    scored = score_loss_bundle(joblib.load(path), x, x.loan_amnt)
    np.testing.assert_allclose(scored.expected_loss_proxy, [100, 200, 300, 400])
    with pytest.raises(ValueError):
        score_loss_bundle(bundle, x.assign(recoveries=100), x.loan_amnt)
    with pytest.raises(ValueError):
        score_loss_bundle(bundle, x, [0, 1, 2, 3])


def test_loss_sql_handles_denominators_out_of_bounds_and_missing_values(tmp_path):
    path = tmp_path / "loss.csv"
    pd.DataFrame({"id": range(1, 9), "issue_d": "Jan-2013", "funded_amnt": [10000]*6 + [None, 10000],
        "total_rec_prncp": [2000, 10000, 11000, 2000, 2000, 2000, 2000, 2000],
        "recoveries": [1000, 0, 0, 9000, 0, "bad", 0, 0],
        "collection_recovery_fee": [200, 0, 0, 0, 100, 0, 0, 0]}).to_csv(path, index=False)
    contract = pd.DataFrame({"loan_id": range(1, 9), "charged_off": [1]*7+[0], "split": "train"})
    root = Path(__file__).resolve().parents[1]
    con = duckdb.connect()
    con.register("model_contract", contract)
    con.execute("SET VARIABLE raw_path=?", [str(path)])
    con.execute((root / "sql/34_loss_population.sql").read_text())
    rows = con.execute("SELECT * FROM loss_population").df().set_index("loan_id")
    audit = con.execute((root / "sql/35_loss_audit.sql").read_text()).df().iloc[0]
    con.close()
    assert rows.loc[1, "ead_snapshot_proxy"] == 8000
    assert rows.loc[1, "lgd_snapshot_proxy"] == pytest.approx(0.9)
    assert rows.loc[1, "observed_loss_proxy"] == 7200
    assert rows.loc[1, "bounded_target_valid"]
    assert not rows.loc[2:7, "bounded_target_valid"].any()
    assert rows.loc[8, "observed_loss_proxy"] == 0
    assert audit.eligible_defaults == 1
    assert audit.invalid_funded == 1
    assert audit.nonpositive_default_ead == 2
    assert audit.negative_lgd == 1
    assert audit.lgd_above_one == 1
