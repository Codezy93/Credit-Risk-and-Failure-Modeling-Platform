from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from util.coefficient_review import bootstrap_numeric_coefficients, numeric_coefficients
from util.modeling import build_models


def inputs():
    rng = np.random.default_rng(42)
    numeric = ["annual_inc", "revol_bal", "delinq_2yrs", "pub_rec_bankruptcies", "fico_mid"]
    frame = pd.DataFrame({"annual_inc": rng.uniform(20000, 100000, 120),
        "revol_bal": rng.uniform(0, 10000, 120), "delinq_2yrs": rng.integers(0, 4, 120),
        "pub_rec_bankruptcies": rng.integers(0, 3, 120), "fico_mid": rng.uniform(650, 800, 120),
        "purpose": "credit_card", "charged_off": np.tile([0, 1], 60)})
    model = build_models(numeric, ["purpose"])["logistic_regression"]
    return frame, numeric, numeric + ["purpose"], model


def test_numeric_names_and_units_remain_aligned_across_transform_groups():
    frame, numeric, features, model = inputs()
    model.fit(frame[features], frame.charged_off)
    result = numeric_coefficients(model, numeric).set_index("feature")
    assert result.index.tolist() == numeric
    assert result.loc["annual_inc", "input_transform"] == "log1p"
    assert result.loc["delinq_2yrs", "input_transform"] == "identity"
    assert result.estimable.all()
    np.testing.assert_allclose(result.coefficient_per_transformed_unit * result.training_scale,
                               result.coefficient_standardized)


def test_bootstrap_is_reproducible_and_rejects_future_years():
    frame, numeric, features, model = inputs()
    years = np.repeat([2011, 2012, 2013], 40)
    a = bootstrap_numeric_coefficients(model, frame, years, features, numeric, resamples=3)
    b = bootstrap_numeric_coefficients(model, frame, years, features, numeric, resamples=3)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 3 * len(numeric)
    years[-1] = 2014
    with pytest.raises(ValueError, match="2011-2013"):
        bootstrap_numeric_coefficients(model, frame, years, features, numeric, resamples=3)


def test_sql_slices_reconcile_to_training_population():
    frame, _, _, _ = inputs()
    frame["issue_year"] = np.repeat([2011, 2012, 2013], 40)
    con = duckdb.connect()
    con.register("coefficient_population", frame)
    path = Path(__file__).resolve().parents[1] / "sql/37_coefficient_outcomes.sql"
    result = con.execute(path.read_text()).df()
    con.close()
    for feature in ["delinq_2yrs", "pub_rec_bankruptcies"]:
        subset = result[(result.feature == feature) & (result.cohort == "pooled")]
        assert subset.rows.sum() == 120 and subset.charged_off.sum() == 60
