import numpy as np
import pandas as pd
import pytest

from util.modeling import build_models


@pytest.fixture
def examples():
    count = 120
    x = pd.DataFrame({"loan_amnt": np.arange(count) * 100 + 1000,
        "annual_inc": np.arange(count) * 500 + 30000.0,
        "revol_bal": np.arange(count) * 10.0, "dti": np.arange(count) % 30 + 1.0,
        "home_ownership": ["RENT", "OWN"] * (count // 2),
        "purpose": ["credit_card", "other"] * (count // 2)})
    x.loc[0, "annual_inc"] = np.nan
    return x, np.arange(count) % 2


@pytest.mark.parametrize("name", ["dummy_prior", "logistic_regression", "random_forest", "hist_gradient_boosting"])
def test_actual_pipelines_accept_missing_values_and_unseen_categories(name, examples):
    x, y = examples
    numeric = ["loan_amnt", "annual_inc", "revol_bal", "dti"]
    model = build_models(numeric, ["home_ownership", "purpose"])[name]
    model.fit(x, y)
    later = x.head(3).copy()
    later[numeric] = np.nan
    later["home_ownership"] = "ANY"
    later["purpose"] = "never_seen"
    probabilities = model.predict_proba(later)
    assert probabilities.shape == (3, 2)
    assert np.isfinite(probabilities).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1)


def test_validation_extremes_do_not_refit_imputation_scaling_or_vocabulary(examples):
    x, y = examples
    model = build_models(["loan_amnt", "annual_inc", "revol_bal", "dti"], ["home_ownership", "purpose"])["logistic_regression"]
    model.fit(x, y)
    numeric = model.named_steps["prepare"].named_transformers_["numeric"]
    original_mean = numeric.named_steps["scale"].mean_.copy()
    original_medians = numeric.named_steps["impute"].statistics_.copy()
    later = x.head(2).copy()
    later["loan_amnt"] = 1e12
    later["home_ownership"] = "ANY"
    model.predict_proba(later)
    np.testing.assert_array_equal(numeric.named_steps["scale"].mean_, original_mean)
    np.testing.assert_array_equal(numeric.named_steps["impute"].statistics_, original_medians)
    np.testing.assert_allclose(original_mean, x[["loan_amnt", "dti"]].mean().to_numpy())
    vocabulary = model.named_steps["prepare"].named_transformers_["categories"].named_steps["encode"].categories_[0]
    assert "ANY" not in vocabulary
