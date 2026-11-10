"""Descriptive borrower-segment metrics; not protected-group fairness certification."""

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def wilson_interval(successes, trials, z=1.959963984540054):
    if trials == 0:
        return np.nan, np.nan
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("Counts must satisfy 0 <= successes <= trials.")
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    radius = z * np.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def segment_metrics(y, probabilities, threshold, min_rows=500, min_class_rows=50):
    y = np.asarray(y, dtype=float)
    p = np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or p.shape != y.shape or len(y) == 0:
        raise ValueError("Use aligned, nonempty one-dimensional labels and probabilities.")
    if not np.isfinite(y).all() or not np.isin(y, [0, 1]).all():
        raise ValueError("Labels must be nonmissing binary outcomes.")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any() or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Probabilities and threshold must be finite values in [0,1].")
    decision = p >= threshold
    positive = y == 1
    tp = int((decision & positive).sum())
    fp = int((decision & ~positive).sum())
    fn = int((~decision & positive).sum())
    tn = int((~decision & ~positive).sum())
    positives, negatives, flagged = tp + fn, tn + fp, tp + fp
    divide = lambda numerator, denominator: numerator / denominator if denominator else np.nan
    reasons = []
    if len(y) < min_rows:
        reasons.append("small_total")
    if positives < min_class_rows:
        reasons.append("few_charged_off")
    if negatives < min_class_rows:
        reasons.append("few_fully_paid")
    result = {"rows": len(y), "positives": positives, "negatives": negatives,
        "flagged": flagged, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "observed_rate": float(y.mean()), "mean_probability": float(p.mean()),
        "calibration_bias": float(p.mean() - y.mean()), "brier_score": float(np.mean((p - y) ** 2)),
        "roc_auc": float(roc_auc_score(y, p)) if positives and negatives else np.nan,
        "average_precision": float(average_precision_score(y, p)) if positives and negatives else np.nan,
        "flag_rate": flagged / len(y), "tpr": divide(tp, positives), "fpr": divide(fp, negatives),
        "fnr": divide(fn, positives), "precision": divide(tp, flagged),
        "supported": not reasons, "support_reason": ",".join(reasons) if reasons else "supported",
        "threshold": float(threshold)}
    for name, successes, trials in [("observed_rate", positives, len(y)), ("flag_rate", flagged, len(y)),
                                     ("tpr", tp, positives), ("fpr", fp, negatives)]:
        lower, upper = wilson_interval(successes, trials)
        result[f"{name}_lower_95"], result[f"{name}_upper_95"] = lower, upper
    bins = np.minimum((p * 10).astype(int), 9)
    result["ece_10_uniform_bins"] = float(sum(abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).sum()
        for b in np.unique(bins)) / len(y))
    return result


def disparity_summary(frame):
    """Screen supported observed segments, without pass/fail thresholds or causal claims."""
    rows = []
    for (split, policy, dimension), group in frame.groupby(["split", "policy", "dimension"], sort=True):
        supported = group[group.supported]
        row = {"split": split, "policy": policy, "dimension": dimension,
            "observed_groups": len(group), "supported_groups": len(supported),
            "supported_rows": int(supported.rows.sum()),
            "all_groups_zero_flags": bool(group.flagged.sum() == 0)}
        for metric in ["flag_rate", "tpr", "fpr", "roc_auc", "calibration_bias", "brier_score"]:
            values = supported[metric].dropna()
            row[f"{metric}_spread"] = float(values.max() - values.min()) if len(values) >= 2 else np.nan
        rows.append(row)
    return rows
