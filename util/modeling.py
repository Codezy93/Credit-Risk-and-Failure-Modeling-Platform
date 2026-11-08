"""Fixed first-pass sklearn pipelines, shared by training and tests."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler


def build_models(numeric, categorical, seed=42):
    linear_log = ["annual_inc", "revol_bal"]
    linear_other = [name for name in numeric if name not in linear_log]
    linear = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("scale", StandardScaler())]), linear_other),
        ("log_numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                                  ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                                  ("scale", StandardScaler())]), linear_log),
        ("missing_flags", MissingIndicator(features="all", error_on_new=False), numeric),
        ("categories", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Missing")),
                                 ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
    ])

    def tree_preprocessor():
        return ColumnTransformer([
            ("numeric", SimpleImputer(strategy="median"), numeric),
            ("missing_flags", MissingIndicator(features="all", error_on_new=False), numeric),
            ("categories", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Missing")),
                                     ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
        ])

    boosting = ColumnTransformer([
        ("numeric", "passthrough", numeric),
        ("categories", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Missing")),
                                 ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))]), categorical),
    ])
    return {
        "dummy_prior": Pipeline([("prepare", tree_preprocessor()), ("model", DummyClassifier(strategy="prior"))]),
        "logistic_regression": Pipeline([("prepare", linear),
            ("model", LogisticRegression(C=1.0, max_iter=1000, random_state=seed))]),
        "random_forest": Pipeline([("prepare", tree_preprocessor()),
            ("model", RandomForestClassifier(n_estimators=150, max_depth=12,
                                              min_samples_leaf=50, n_jobs=4, random_state=seed))]),
        "hist_gradient_boosting": Pipeline([("prepare", boosting),
            ("model", HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                max_leaf_nodes=15, min_samples_leaf=50, l2_regularization=1.0,
                early_stopping=False, categorical_features=list(range(len(numeric), len(numeric) + len(categorical))),
                random_state=seed))]),
    }


