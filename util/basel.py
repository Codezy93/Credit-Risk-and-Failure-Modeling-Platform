"""Loss proxies and the CRE31.16 other-retail formula for illustrative scenarios."""

import numpy as np
import pandas as pd
from scipy.stats import norm

from util.feature_policy import validate_features


def other_retail_capital(pd_one_year, lgd, ead):
    """Undefaulted other-retail scenario; no regulatory eligibility is implied."""
    pd_one_year, lgd, ead = np.broadcast_arrays(
        np.asarray(pd_one_year, dtype=float), np.asarray(lgd, dtype=float), np.asarray(ead, dtype=float))
    if not all(np.isfinite(x).all() for x in (pd_one_year, lgd, ead)):
        raise ValueError("Capital inputs must be finite.")
    if ((pd_one_year <= 0) | (pd_one_year >= 1)).any() or ((lgd < 0) | (lgd > 1)).any() or (ead < 0).any():
        raise ValueError("Require 0 < one-year PD < 1, 0 <= LGD <= 1, and EAD >= 0.")
    weight = -np.expm1(-35 * pd_one_year) / -np.expm1(-35)
    correlation = 0.03 * weight + 0.16 * (1 - weight)
    stressed_default = norm.cdf((norm.ppf(pd_one_year) + np.sqrt(correlation) * norm.ppf(0.999)) /
                               np.sqrt(1 - correlation))
    capital_ratio = lgd * (stressed_default - pd_one_year)
    return pd.DataFrame({"pd_one_year_assumed": pd_one_year.ravel(), "lgd": lgd.ravel(),
                         "ead": ead.ravel(), "correlation": correlation.ravel(),
                         "capital_ratio": capital_ratio.ravel(), "capital": (capital_ratio * ead).ravel(),
                         "risk_weight": (12.5 * capital_ratio).ravel(),
                         "rwa": (12.5 * capital_ratio * ead).ravel(),
                         "expected_loss_one_year_scenario": (pd_one_year * lgd * ead).ravel()})


def expected_loss(pd_score, lgd, ead):
    pd_score, lgd, ead = np.broadcast_arrays(np.asarray(pd_score, dtype=float),
        np.asarray(lgd, dtype=float), np.asarray(ead, dtype=float))
    if not all(np.isfinite(x).all() for x in (pd_score, lgd, ead)):
        raise ValueError("Loss inputs must be finite.")
    if ((pd_score < 0) | (pd_score > 1) | (lgd < 0) | (lgd > 1) | (ead < 0)).any():
        raise ValueError("Loss probabilities and LGD must be in [0,1]; EAD must be nonnegative.")
    return pd_score * lgd * ead


def score_loss_bundle(bundle, features, funded_amount):
    """Score origination predictors; funding is separate exposure scaling metadata."""
    validate_features(bundle["features"])
    if list(features.columns) != bundle["features"]:
        raise ValueError("Use exactly the bundle's ordered predictor columns.")
    funded = np.asarray(funded_amount, dtype=float)
    if funded.shape != (len(features),) or not np.isfinite(funded).all() or (funded <= 0).any():
        raise ValueError("Supply one positive finite funded amount per loan.")
    pd_score = bundle["pd_model"].predict_proba(features)[:, 1]
    ead = funded * np.clip(bundle["ead_ratio_model"].predict(features), 0, 1)
    lgd = np.clip(bundle["lgd_model"].predict(features), 0, 1)
    return pd.DataFrame({"pd_score_resolved_outcome": pd_score, "predicted_ead": ead,
        "predicted_lgd": lgd, "expected_loss_proxy": expected_loss(pd_score, lgd, ead)}, index=features.index)
