"""Choose tree budgets on 2013, then refit without an evaluation set."""

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from util.feature_policy import validate_features
from util.validation import validate_periods


def fit_temporal_xgboost(train, metadata, features, numeric, categorical, parameters,
                         scope="independent_baseline", max_estimators=1200, patience=60):
    validate_features(features, scope)
    if len(train) != len(metadata) or set(metadata.issue_year) != {2011, 2012, 2013}:
        raise ValueError("Aligned 2011-2013 training rows are required; never pass 2014.")
    if not np.array_equal(pd.to_datetime(metadata.issue_date).dt.year, metadata.issue_year):
        raise ValueError("Metadata years contradict issue dates.")
    if set(numeric + categorical) != set(features) or set(numeric).intersection(categorical):
        raise ValueError("Numeric and categorical columns must partition the feature contract.")
    inner_mask = metadata.issue_year.to_numpy() <= 2012
    stop_mask = metadata.issue_year.to_numpy() == 2013
    validate_periods({"inner_fit": metadata.loc[inner_mask], "stopping": metadata.loc[stop_mask]})
    if min(max_estimators, patience) < 1:
        raise ValueError("Tree and patience budgets must be positive.")
    for mask in (inner_mask, stop_mask):
        if set(train.loc[mask, "charged_off"].unique()) != {0, 1}:
            raise ValueError("Both stopping populations need both binary classes.")
    prepare = ColumnTransformer([
        ("numeric", "passthrough", numeric),
        ("categories", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Missing")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical)], sparse_threshold=0)
    inner_prepare = clone(prepare)
    x_inner = inner_prepare.fit_transform(train.loc[inner_mask, features])
    x_stop = inner_prepare.transform(train.loc[stop_mask, features])
    # Budgets/evaluation settings cannot be overridden by a candidate configuration.
    reserved = {"n_estimators", "early_stopping_rounds", "callbacks"}
    if reserved.intersection(parameters):
        raise ValueError("Pass tree/patience budgets separately from model parameters.")
    stopping_model = XGBClassifier(**parameters, n_estimators=max_estimators, early_stopping_rounds=patience)
    stopping_model.fit(x_inner, train.loc[inner_mask, "charged_off"],
        eval_set=[(x_inner, train.loc[inner_mask, "charged_off"]),
                  (x_stop, train.loc[stop_mask, "charged_off"])], verbose=False)
    selected = int(stopping_model.best_iteration) + 1
    curve = stopping_model.evals_result()
    learning = pd.DataFrame({"iteration": np.arange(1, len(curve["validation_1"]["auc"]) + 1),
        "inner_fit_auc": curve["validation_0"]["auc"], "stopping_2013_auc": curve["validation_1"]["auc"]})
    final_prepare = clone(prepare)
    x_train = final_prepare.fit_transform(train[features])
    final_model = XGBClassifier(**parameters, n_estimators=selected)
    final_model.fit(x_train, train.charged_off, verbose=False)
    if final_model.get_booster().num_boosted_rounds() != selected:
        raise ValueError("Final model did not fit the frozen tree budget.")
    details = {"inner_fit_rows": int(inner_mask.sum()), "stopping_rows": int(stop_mask.sum()),
        "refit_rows": len(train), "selected_estimators": selected,
        "stopping_best_iteration": selected - 1, "stopping_best_auc": float(stopping_model.best_score),
        "stopping_rounds_run": len(learning), "max_estimators": max_estimators, "patience": patience,
        "refit_used_eval_set": False, "final_boosted_rounds": final_model.get_booster().num_boosted_rounds()}
    return Pipeline([("prepare", final_prepare), ("model", final_model)]), learning, details
