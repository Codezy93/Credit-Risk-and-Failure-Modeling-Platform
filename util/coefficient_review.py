"""Align scaled numeric coefficients and refit conditional bootstrap samples."""

import numpy as np
import pandas as pd
from sklearn.base import clone


def numeric_coefficients(model, numeric):
    prepare = model.named_steps["prepare"]
    coefficients = pd.Series(model.named_steps["model"].coef_[0], index=prepare.get_feature_names_out())
    rows = []
    for feature in numeric:
        group = "log_numeric" if feature in ("annual_inc", "revol_bal") else "numeric"
        transform = prepare.named_transformers_[group]
        columns = next(columns for name, _, columns in prepare.transformers_ if name == group)
        retained = transform.named_steps["impute"].get_feature_names_out(columns).tolist()
        estimable = feature in retained and f"{group}__{feature}" in coefficients.index
        coefficient = float(coefficients[f"{group}__{feature}"]) if estimable else np.nan
        scale = float(transform.named_steps["scale"].scale_[retained.index(feature)]) if estimable else np.nan
        rows.append({"feature": feature, "coefficient_standardized": coefficient,
            "coefficient_per_transformed_unit": coefficient / scale if estimable else np.nan,
            "input_transform": "log1p" if group == "log_numeric" else "identity",
            "training_scale": scale, "estimable": estimable})
    return pd.DataFrame(rows)


def bootstrap_numeric_coefficients(model, frame, years, features, numeric, resamples=200, seed=42):
    years = np.asarray(years)
    if len(years) != len(frame) or set(years) != {2011, 2012, 2013}:
        raise ValueError("Use aligned training years 2011-2013 only for coefficient bootstraps.")
    if resamples < 2:
        raise ValueError("At least two bootstrap resamples are required.")
    strata = [np.flatnonzero((years == year) & frame.charged_off.eq(label).to_numpy())
              for year in (2011, 2012, 2013) for label in (0, 1)]
    if any(len(stratum) == 0 for stratum in strata):
        raise ValueError("Both classes must be represented in each training year.")
    rng = np.random.default_rng(seed)
    rows = []
    for iteration in range(resamples):
        indices = np.concatenate([rng.choice(stratum, len(stratum), replace=True) for stratum in strata])
        indices = rng.permutation(indices)
        sample = frame.iloc[indices]
        fitted = clone(model).fit(sample[features], sample.charged_off)
        table = numeric_coefficients(fitted, numeric)
        table["resample"] = iteration
        rows.append(table)
        if (iteration + 1) % 25 == 0:
            print(f"Coefficient bootstrap: {iteration + 1}/{resamples}", flush=True)
    return pd.concat(rows, ignore_index=True)
