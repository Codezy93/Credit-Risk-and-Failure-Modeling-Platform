import numpy as np
import pandas as pd
import pytest

from util.temporal_xgboost import fit_temporal_xgboost


def inputs():
    rng = np.random.default_rng(42)
    years = np.repeat([2011, 2012, 2013], 40)
    frame = pd.DataFrame({"loan_amnt": rng.uniform(1000, 20000, 120),
        "home_ownership": np.where(years == 2013, "MORTGAGE", "RENT"), "charged_off": np.tile([0, 1], 60)})
    metadata = pd.DataFrame({"loan_id": range(120), "issue_year": years,
                             "issue_date": pd.to_datetime([f"{year}-01-01" for year in years])})
    return frame, metadata


def fit(frame, metadata, parameters=None):
    return fit_temporal_xgboost(frame, metadata, ["loan_amnt", "home_ownership"],
        ["loan_amnt"], ["home_ownership"], parameters or {"max_depth": 2, "n_jobs": 1,
        "random_state": 42, "eval_metric": "auc"}, max_estimators=12, patience=3)


def test_stopping_then_refit_uses_frozen_tree_budget():
    frame, metadata = inputs()
    model, curve, details = fit(frame, metadata)
    assert details["inner_fit_rows"] == 80 and details["stopping_rows"] == 40
    assert details["refit_rows"] == 120
    assert len(curve) <= 12
    assert model.named_steps["model"].get_booster().num_boosted_rounds() == details["selected_estimators"]
    assert model.named_steps["model"].get_params()["early_stopping_rounds"] is None
    assert not details["refit_used_eval_set"]
    categories = model.named_steps["prepare"].named_transformers_["categories"].named_steps["encode"].categories_[0]
    assert set(categories) == {"RENT", "MORTGAGE"}
    incoming = frame.head(2).copy()
    incoming["home_ownership"] = "UNSEEN"
    assert np.isfinite(model.predict_proba(incoming[["loan_amnt", "home_ownership"]])).all()


@pytest.mark.parametrize("change", ["validation_year", "overlapping_id", "inconsistent_year", "single_class"])
def test_temporal_contract_violations_fail(change):
    frame, metadata = inputs()
    if change == "validation_year":
        metadata.loc[119, "issue_year"] = 2014
    elif change == "overlapping_id":
        metadata.loc[119, "loan_id"] = 0
    elif change == "inconsistent_year":
        metadata.loc[119, "issue_date"] = pd.Timestamp("2014-01-01")
    else:
        frame.loc[metadata.issue_year == 2013, "charged_off"] = 0
    with pytest.raises(ValueError):
        fit(frame, metadata)
