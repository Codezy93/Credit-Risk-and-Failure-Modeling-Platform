"""Reversible category codes for InterpretML's numeric black-box interfaces."""

import numpy as np
import pandas as pd


def category_codebook(train, categorical):
    return {name: sorted(train[name].dropna().astype(str).unique().tolist()) for name in categorical}


def explanation_eligible(frame, features, codebook):
    eligible = frame[features].notna().all(axis=1)
    for name, levels in codebook.items():
        eligible &= frame[name].isin(levels)
    return eligible


def encode_explanation_frame(frame, features, codebook):
    if not explanation_eligible(frame, features, codebook).all():
        raise ValueError("Explanations require complete rows and training-known categories.")
    encoded = frame[features].copy()
    for name, levels in codebook.items():
        encoded[name] = frame[name].map({value: index for index, value in enumerate(levels)}).astype(float)
    array = encoded.astype(float).to_numpy()
    if not np.isfinite(array).all():
        raise ValueError("Explanation inputs must be finite.")
    return array


def decode_explanation_frame(values, features, codebook):
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(features) or not np.isfinite(values).all():
        raise ValueError("Explanation arrays must be finite and match the feature contract.")
    decoded = {}
    for index, name in enumerate(features):
        column = values[:, index]
        if name in codebook:
            codes = np.rint(column).astype(int)
            if not np.allclose(column, codes, atol=1e-10) or ((codes < 0) | (codes >= len(codebook[name]))).any():
                raise ValueError("Unsupported categorical interpolation or code.")
            decoded[name] = np.asarray(codebook[name], dtype=object)[codes]
        else:
            decoded[name] = column
    return pd.DataFrame(decoded, columns=features)
