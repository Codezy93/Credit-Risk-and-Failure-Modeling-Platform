"""Small neural networks with an explicit later-year stopping population."""

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline

from util.feature_policy import validate_features
from util.modeling import build_models


def fit_temporal_ann(frame, years, features, numeric, categorical, target, task,
                     hidden=(32,), max_epochs=60, patience=8, seed=42, batch_size=1024):
    validate_features(features)
    years = np.asarray(years)
    if len(years) != len(frame) or set(years) != {2011, 2012, 2013}:
        raise ValueError("ANN fitting must contain only the aligned 2011-2013 population.")
    if task not in ("classification", "regression") or min(max_epochs, patience) < 1:
        raise ValueError("Choose classification/regression and positive epoch/patience limits.")
    fit_mask, stop_mask = years <= 2012, years == 2013
    prepare = build_models(numeric, categorical)["logistic_regression"].named_steps["prepare"]
    inner_prepare = clone(prepare)
    x_fit = inner_prepare.fit_transform(frame.loc[fit_mask, features])
    x_stop = inner_prepare.transform(frame.loc[stop_mask, features])
    y_fit, y_stop = frame.loc[fit_mask, target], frame.loc[stop_mask, target]
    parameters = dict(hidden_layer_sizes=hidden, activation="relu", solver="adam", alpha=0.01,
                      learning_rate_init=0.001, batch_size=batch_size, shuffle=True,
                      early_stopping=False, random_state=seed)
    estimator_type = MLPClassifier if task == "classification" else MLPRegressor
    inner = estimator_type(**parameters)
    if task == "classification" and (set(y_fit.unique()) != {0, 1} or set(y_stop.unique()) != {0, 1}):
        raise ValueError("Both temporal populations need both binary classes.")
    best_score, best_epoch, stale = -np.inf, 0, 0
    rows = []
    tolerance = 1e-4 if task == "classification" else 1e-5
    for epoch in range(1, max_epochs + 1):
        if task == "classification":
            inner.partial_fit(x_fit, y_fit, classes=np.array([0, 1]))
            value = roc_auc_score(y_stop, inner.predict_proba(x_stop)[:, 1])
            objective = value
        else:
            inner.partial_fit(x_fit, y_fit)
            value = mean_absolute_error(y_stop, np.clip(inner.predict(x_stop), 0, 1))
            objective = -value
        if not np.isfinite(value) or not np.isfinite(inner.loss_):
            raise ValueError("Nonfinite ANN learning curve; inspect the training inputs.")
        rows.append({"phase": "stopping_2013", "epoch": epoch, "training_objective": inner.loss_,
                     "stopping_metric": "roc_auc" if task == "classification" else "bounded_mae",
                     "stopping_value": value})
        if objective > best_score + tolerance:
            best_score, best_epoch, stale = objective, epoch, 0
        else:
            stale += 1
        if stale >= patience:
            break
    # Refit from scratch using all training years; no 2014 label enters epoch selection.
    final_prepare = clone(prepare)
    x_train = final_prepare.fit_transform(frame[features])
    final = estimator_type(**parameters)
    for epoch in range(1, best_epoch + 1):
        if task == "classification":
            final.partial_fit(x_train, frame[target], classes=np.array([0, 1]))
        else:
            final.partial_fit(x_train, frame[target])
        rows.append({"phase": "refit_2011_2013", "epoch": epoch, "training_objective": final.loss_,
                     "stopping_metric": None, "stopping_value": np.nan})
    pipeline = Pipeline([("prepare", final_prepare), ("model", final)])
    details = {"hidden_layers": list(hidden), "selected_epochs": best_epoch,
               "stopping_epochs_run": len([r for r in rows if r["phase"] == "stopping_2013"]),
               "stopping_best_value": best_score if task == "classification" else -best_score,
               "inner_fit_rows": int(fit_mask.sum()), "stopping_rows": int(stop_mask.sum()),
               "refit_rows": len(frame), "max_epochs": max_epochs, "patience": patience,
               "improvement_tolerance": tolerance, "seed": seed, "parameters": parameters}
    return pipeline, pd.DataFrame(rows), details
