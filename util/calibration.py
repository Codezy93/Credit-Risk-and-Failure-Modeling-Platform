"""Sigmoid calibration of a frozen model on a separate, later loan population."""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

from util.validation import validate_periods


def fit_sigmoid(model, x_calibration, y_calibration, fit_metadata, calibration_metadata):
    validate_periods({"model_fit": fit_metadata, "calibration": calibration_metadata})
    if len(x_calibration) != len(calibration_metadata) or len(y_calibration) != len(calibration_metadata):
        raise ValueError("Calibration inputs, labels, and metadata must have matching row counts.")
    if set(np.unique(y_calibration)) != {0, 1}:
        raise ValueError("Calibration needs both binary classes.")
    calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrated.fit(x_calibration, y_calibration)
    return calibrated
