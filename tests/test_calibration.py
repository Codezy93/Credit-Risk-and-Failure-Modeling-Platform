import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from util.calibration import fit_sigmoid


def test_sigmoid_calibration_does_not_refit_the_base_model():
    x = np.linspace(-3, 3, 60).reshape(-1, 1)
    y = (x[:, 0] > 0).astype(int)
    base = LogisticRegression().fit(x, y)
    coefficients = base.coef_.copy()
    intercept = base.intercept_.copy()
    fit_meta = pd.DataFrame({"loan_id": np.arange(60), "issue_date": pd.Timestamp("2012-01-01")})
    cal_meta = pd.DataFrame({"loan_id": np.arange(60, 120), "issue_date": pd.Timestamp("2013-01-01")})
    calibrated = fit_sigmoid(base, x, y, fit_meta, cal_meta)
    np.testing.assert_array_equal(base.coef_, coefficients)
    np.testing.assert_array_equal(base.intercept_, intercept)
    assert np.isfinite(calibrated.predict_proba(x)).all()


def test_calibration_rejects_reused_loan_ids():
    x = np.array([[-1], [1], [-2], [2]])
    y = [0, 1, 0, 1]
    model = LogisticRegression().fit(x, y)
    fit = pd.DataFrame({"loan_id": [1, 2, 3, 4], "issue_date": pd.Timestamp("2012-01-01")})
    overlap = pd.DataFrame({"loan_id": [1, 6, 7, 8], "issue_date": pd.Timestamp("2013-01-01")})
    with pytest.raises(ValueError):
        fit_sigmoid(model, x, y, fit, overlap)
