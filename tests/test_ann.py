import numpy as np
import pandas as pd
import pytest

from util.ann import fit_temporal_ann


def sample():
    rng = np.random.default_rng(42)
    years = np.repeat([2011, 2012, 2013], 30)
    frame = pd.DataFrame({"annual_inc": rng.uniform(20000, 100000, 90),
        "revol_bal": rng.uniform(0, 5000, 90), "loan_amnt": rng.uniform(1000, 20000, 90),
        "home_ownership": np.where(years == 2013, "MORTGAGE", "RENT"),
        "outcome": np.tile([0, 1], 45)})
    return frame, years


@pytest.mark.parametrize("task", ["classification", "regression"])
def test_temporal_selection_then_full_refit(task):
    frame, years = sample()
    numeric = ["annual_inc", "revol_bal", "loan_amnt"]
    categorical = ["home_ownership"]
    model, curve, details = fit_temporal_ann(frame, years, numeric + categorical,
        numeric, categorical, "outcome", task, hidden=(4,), max_epochs=3, patience=2, batch_size=16)
    assert details["inner_fit_rows"] == 60 and details["stopping_rows"] == 30
    assert details["refit_rows"] == 90
    assert 1 <= details["selected_epochs"] <= 3
    assert len(curve[curve.phase == "refit_2011_2013"]) == details["selected_epochs"]
    # The final preprocessor refits on 2013 too, after the stopping budget is frozen.
    vocabulary = model.named_steps["prepare"].named_transformers_["categories"].named_steps["encode"].categories_[0]
    assert set(vocabulary) == {"MORTGAGE", "RENT"}
    incoming = frame.head(3).copy()
    incoming["home_ownership"] = "UNSEEN"
    incoming["annual_inc"] = np.nan
    prediction = model.predict_proba(incoming[numeric + categorical]) if task == "classification" else model.predict(incoming[numeric + categorical])
    assert np.isfinite(prediction).all()


def test_validation_year_cannot_enter_epoch_selection():
    frame, years = sample()
    years[-1] = 2014
    with pytest.raises(ValueError, match="2011-2013"):
        fit_temporal_ann(frame, years, ["annual_inc", "revol_bal", "loan_amnt", "home_ownership"],
            ["annual_inc", "revol_bal", "loan_amnt"], ["home_ownership"], "outcome", "classification")
