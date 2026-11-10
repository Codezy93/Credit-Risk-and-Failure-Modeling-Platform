"""InterpretML explanations of a frozen charged-off probability function."""

import json
from time import perf_counter

from interpret.blackbox import PartialDependence, ShapKernel
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from util.explanation_input import category_codebook, decode_explanation_frame, encode_explanation_frame, explanation_eligible


def explanation_json(value):
    """Use JSON null for unknown native explanation metadata, never NaN tokens."""
    if isinstance(value, dict):
        return {key: explanation_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [explanation_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return explanation_json(value.tolist())
    if isinstance(value, np.generic):
        return explanation_json(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def explain_incumbent(model, train, validation, features, categorical, threshold, model_dir,
                       random_cases=128, background_rows=64, pdp_rows=1000, coalitions=512, seed=42):
    started = perf_counter()
    codebook = category_codebook(train, categorical)
    train_mask = explanation_eligible(train, features, codebook)
    validation_mask = explanation_eligible(validation, features, codebook)
    train_positions = np.flatnonzero(train_mask)
    validation_positions = np.flatnonzero(validation_mask)
    if len(train_positions) < max(background_rows, pdp_rows) or len(validation_positions) < random_cases:
        raise ValueError("Not enough complete training-known rows for the declared explanation samples.")
    rng = np.random.default_rng(seed)
    background_positions = rng.choice(train_positions, background_rows, replace=False)
    pdp_positions = rng.choice(train_positions, pdp_rows, replace=False)
    random_positions = np.sort(rng.choice(validation_positions, random_cases, replace=False))
    positions = list(random_positions)
    selections = ["random_sample"] * len(positions)
    all_scores = model.predict_proba(validation[features])[:, 1]
    y = validation.charged_off.to_numpy()
    risk = all_scores >= threshold
    for kind, mask in [("TP", risk & (y == 1)), ("TN", ~risk & (y == 0)),
                       ("FP", risk & (y == 0)), ("FN", ~risk & (y == 1))]:
        candidates = np.array([i for i in validation_positions[mask[validation_positions]] if i not in positions])
        for position in rng.choice(candidates, min(2, len(candidates)), replace=False):
            positions.append(int(position))
            selections.append(f"curated_{kind}")
    cases = validation.iloc[positions].copy()
    background = train.iloc[background_positions][features].copy()
    pdp_background = train.iloc[pdp_positions][features].copy()
    encoded_background = encode_explanation_frame(background, features, codebook)
    encoded_cases = encode_explanation_frame(cases, features, codebook)
    encoded_pdp = encode_explanation_frame(pdp_background, features, codebook)

    def probability(values):
        return model.predict_proba(decode_explanation_frame(values, features, codebook))[:, 1]

    np.testing.assert_allclose(probability(encoded_cases), all_scores[positions], atol=1e-12)
    np.testing.assert_allclose(probability(encoded_background), model.predict_proba(background)[:, 1], atol=1e-12)
    feature_types = ["nominal" if name in categorical + ["delinq_2yrs", "pub_rec_bankruptcies"]
                     else "continuous" for name in features]
    np.random.seed(seed)
    print(f"InterpretML Kernel SHAP: {len(cases)} cases, {background_rows} background rows, {coalitions} coalitions", flush=True)
    kernel = ShapKernel(probability, encoded_background, feature_names=features, feature_types=feature_types)
    local = kernel.explain_local(encoded_cases, name="Incumbent charged-off probability contributions",
        nsamples=coalitions, l1_reg=0.0, silent=True)
    case_rows, contributions, local_raw = [], [], []
    for index, position in enumerate(positions):
        detail = local.data(index)
        base = float(detail["extra"]["scores"][0])
        scores = np.asarray(detail["scores"], dtype=float)
        residual = all_scores[position] - base - scores.sum()
        if not np.isfinite(scores).all() or abs(residual) > 1e-8:
            raise ValueError("Local explanations failed finite/additivity checks.")
        case_id = f"case_{index:03d}"
        case_rows.append({"case_id": case_id, "selection": selections[index],
            "validation_row_position": position, "observed_charged_off": int(y[position]),
            "model_probability": all_scores[position], "flagged_risk": bool(risk[position]),
            "background_probability": base, "contribution_sum": scores.sum(), "additivity_residual": residual})
        for feature, contribution in zip(detail["names"], scores):
            contributions.append({"case_id": case_id, "selection": selections[index], "feature": feature,
                "feature_value": str(cases.iloc[index][feature]), "contribution_probability_units": contribution})
        local_raw.append({"case_id": case_id, "data": detail})
    contributions = pd.DataFrame(contributions)
    random_values = contributions[contributions.selection == "random_sample"].copy()
    random_values["absolute_contribution"] = random_values.contribution_probability_units.abs()
    importance = random_values.groupby("feature").agg(mean_absolute_contribution=("absolute_contribution", "mean"),
        mean_signed_contribution=("contribution_probability_units", "mean")).reset_index()
    importance = importance.sort_values("mean_absolute_contribution", ascending=False)
    print(f"InterpretML partial dependence: {pdp_rows} training-background rows", flush=True)
    np.random.seed(seed)
    global_explanation = PartialDependence(probability, encoded_pdp, feature_names=features,
        feature_types=feature_types, num_points=15, std_coef=1.0).explain_global(name="Incumbent probability partial dependence")
    pdp_points, ice_rows, pdp_raw = [], [], []
    for index, feature in enumerate(features):
        detail = global_explanation.data(index)
        for grid_index, (value, score) in enumerate(zip(detail["names"], detail["scores"])):
            display = codebook[feature][int(value)] if feature in codebook else value
            pdp_points.append({"feature": feature, "grid_value": value, "display_value": str(display),
                "mean_probability": score, "lower_row_spread": detail["lower_bounds"][grid_index],
                "upper_row_spread": detail["upper_bounds"][grid_index]})
            for ice_index, line in enumerate(detail["background_scores"]):
                ice_rows.append({"feature": feature, "grid_value": value, "ice_row": ice_index,
                                 "model_probability": line[grid_index]})
        pdp_raw.append({"feature": feature, "data": detail})
    sample_positions, _ = train_test_split(np.arange(len(validation)), train_size=10000,
        stratify=validation.charged_off, random_state=seed)
    sample = validation.iloc[sample_positions]
    print("Permutation importance: 10,000 stratified validation rows, 5 repeats", flush=True)
    permutation = permutation_importance(model, sample[features], sample.charged_off, scoring="roc_auc",
        n_repeats=5, random_state=seed, n_jobs=1)
    permutation_rows = [{"feature": feature, "repeat": repeat,
                         "roc_auc_drop": float(permutation.importances[index, repeat])}
                        for index, feature in enumerate(features) for repeat in range(5)]
    permutation_summary = pd.DataFrame({"feature": features, "roc_auc_drop_mean": permutation.importances_mean,
        "repeat_standard_deviation": permutation.importances_std}).sort_values("roc_auc_drop_mean", ascending=False)
    case_table = pd.DataFrame(case_rows)
    metadata = {"method": "InterpretML ShapKernel and PartialDependence; permutation importance as a cross-check",
        "explained_quantity": "incumbent positive-class probability, scalar output; identity link",
        "random_seed": seed, "random_cases": random_cases, "curated_cases": len(cases) - random_cases,
        "kernel_background_rows": background_rows, "coalitions_per_case": coalitions, "kernel_l1_reg": 0,
        "pdp_background_rows": pdp_rows, "pdp_max_continuous_points": 15, "pdp_ice_rows_per_feature": 10,
        "pdp_bands": "mean +/- one between-background-row standard deviation; not confidence intervals",
        "global_shap_importance_sample": "random complete training-known 2014 cases only; curated cases excluded",
        "training_rows": len(train), "training_explanation_eligible_rows": int(train_mask.sum()),
        "validation_rows": len(validation), "validation_explanation_eligible_rows": int(validation_mask.sum()),
        "maximum_additivity_residual": float(case_table.additivity_residual.abs().max()),
        "numeric_missing_rows_excluded_from_interpret_only": True,
        "all_rows_included_in_segment_and_overall_metrics": True,
        "permutation_rows": len(sample), "permutation_repeats": 5,
        "permutation_sample_baseline_auc": roc_auc_score(sample.charged_off, model.predict_proba(sample[features])[:, 1]),
        "elapsed_seconds": perf_counter() - started, "category_codebook": codebook}
    model_dir.mkdir(parents=True, exist_ok=True)
    background.to_parquet(model_dir / "kernel_background.parquet", index=False)
    pdp_background.to_parquet(model_dir / "pdp_background.parquet", index=False)
    cases[features + ["charged_off"]].to_parquet(model_dir / "explanation_cases.parquet", index=False)
    sample[features + ["charged_off"]].to_parquet(model_dir / "permutation_sample.parquet", index=False)
    (model_dir / "explanation_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (model_dir / "interpretml_native_explanations.json").write_text(json.dumps(explanation_json(
        {"local": local_raw, "partial_dependence": pdp_raw}), allow_nan=False) + "\n")
    return {"local_cases": case_table, "local_contributions": contributions,
        "shap_global_importance": importance, "partial_dependence": pd.DataFrame(pdp_points),
        "ice_curves": pd.DataFrame(ice_rows), "permutation_repeats": pd.DataFrame(permutation_rows),
        "permutation_importance": permutation_summary}, metadata, local, global_explanation
