"""Full-prediction binary metrics and paired, stratified AUC uncertainty."""

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score, log_loss,
                             precision_recall_curve, precision_score, recall_score,
                             roc_auc_score, roc_curve)


def binary_scores(y, probabilities):
    labels = np.asarray(y, dtype=float)
    scores = np.asarray(probabilities, dtype=float)
    if labels.ndim != 1 or scores.ndim != 1 or len(labels) != len(scores) or len(labels) == 0:
        raise ValueError("Labels and probabilities must be aligned, nonempty one-dimensional arrays.")
    if not np.isfinite(labels).all() or set(np.unique(labels)) != {0, 1}:
        raise ValueError("Evaluation requires both binary classes, 0 and 1, without missing labels.")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Probabilities must be finite values from zero to one.")
    return labels.astype(int), scores


def calibration_table(y, probabilities):
    labels, scores = binary_scores(y, probabilities)
    bins = np.minimum((scores * 10).astype(int), 9)
    frame = pd.DataFrame({"bin": bins, "probability": scores, "outcome": labels})
    result = frame.groupby("bin").agg(rows=("outcome", "size"),
        mean_probability=("probability", "mean"), observed_positive_rate=("outcome", "mean")).reset_index()
    result["bin_lower"] = result.bin / 10
    result["bin_upper"] = (result.bin + 1) / 10
    return result


def evaluate_model(y, probabilities, threshold=0.5):
    labels, scores = binary_scores(y, probabilities)
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("The classification threshold must be finite and between zero and one.")
    decisions = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, decisions, labels=[0, 1]).ravel()
    auc = float(roc_auc_score(labels, scores))
    # No plotting downsampling: every distinct score threshold is considered.
    fpr, tpr, _ = roc_curve(labels, scores, drop_intermediate=False)
    bins = calibration_table(labels, scores)
    ece = np.average(abs(bins.mean_probability - bins.observed_positive_rate), weights=bins.rows)
    return {"rows": len(labels), "observed_positive_rate": float(np.mean(labels)),
        "mean_predicted_probability": float(scores.mean()), "threshold": float(threshold),
        "roc_auc": auc, "gini": 2 * auc - 1, "ks": float(np.max(np.abs(tpr - fpr))),
        "average_precision": float(average_precision_score(labels, scores)),
        "brier_score": float(brier_score_loss(labels, scores)), "log_loss": float(log_loss(labels, scores)),
        "ece_10_uniform_bins": float(ece), "accuracy": float(accuracy_score(labels, decisions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, decisions)),
        "precision": float(precision_score(labels, decisions, zero_division=0)),
        "recall": float(recall_score(labels, decisions, zero_division=0)),
        "specificity": float(tn / (tn + fp)), "f1": float(f1_score(labels, decisions, zero_division=0)),
        "predicted_positive_rate": float(decisions.mean()),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def choose_threshold(y, probabilities):
    labels, scores = binary_scores(y, probabilities)
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    denominator = precision[:-1] + recall[:-1]
    f1 = np.divide(2 * precision[:-1] * recall[:-1], denominator,
                   out=np.zeros_like(denominator), where=denominator > 0)
    return float(thresholds[int(np.argmax(f1))])


def paired_auc_bootstrap(y, scores_a, scores_b, n_resamples=500, seed=42):
    labels, a = binary_scores(y, scores_a)
    _, b = binary_scores(y, scores_b)
    if n_resamples < 2:
        raise ValueError("At least two bootstrap resamples are required.")
    positives = np.flatnonzero(labels == 1)
    negatives = np.flatnonzero(labels == 0)
    rng = np.random.default_rng(seed)
    rows = []
    for iteration in range(n_resamples):
        # Both models use the SAME loans; strata retain observed class counts.
        indices = np.concatenate([rng.choice(positives, len(positives), replace=True),
                                  rng.choice(negatives, len(negatives), replace=True)])
        auc_a = float(roc_auc_score(labels[indices], a[indices]))
        auc_b = float(roc_auc_score(labels[indices], b[indices]))
        rows.append({"resample": iteration, "auc_a": auc_a, "auc_b": auc_b, "delta_b_minus_a": auc_b - auc_a})
    return pd.DataFrame(rows)
