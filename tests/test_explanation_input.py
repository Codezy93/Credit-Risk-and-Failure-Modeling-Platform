import numpy as np
import pandas as pd
import pytest

from util.explanation_input import category_codebook, decode_explanation_frame, encode_explanation_frame, explanation_eligible


def test_encoding_is_reversible_and_unseen_missing_cases_are_excluded():
    frame = pd.DataFrame({"loan_amnt": [1000.0, 2000.0], "purpose": ["car", "credit_card"]})
    features = frame.columns.tolist()
    book = category_codebook(frame, ["purpose"])
    array = encode_explanation_frame(frame, features, book)
    pd.testing.assert_frame_equal(decode_explanation_frame(array, features, book), frame, check_dtype=False)
    bad = frame.copy()
    bad.loc[0, "purpose"] = "UNSEEN"
    bad.loc[1, "loan_amnt"] = np.nan
    assert not explanation_eligible(bad, features, book).any()
    with pytest.raises(ValueError):
        encode_explanation_frame(bad, features, book)
    array[0, 1] = 0.5
    with pytest.raises(ValueError, match="interpolation"):
        decode_explanation_frame(array, features, book)


def test_real_interpretml_kernel_explanations_reconstruct_scalar_output():
    from interpret.blackbox import ShapKernel

    x = np.array([[i / 20, i % 2] for i in range(20)], dtype=float)
    predict = lambda values: 0.1 + 0.2 * np.asarray(values, dtype=float)[:, 0] + 0.1 * np.asarray(values, dtype=float)[:, 1]
    np.random.seed(42)
    explainer = ShapKernel(predict, x[:16], feature_names=["loan_amnt", "purpose_code"],
                           feature_types=["continuous", "nominal"])
    explanation = explainer.explain_local(x[16:], nsamples=32, l1_reg=0.0, silent=True)
    reconstructed = [sum(explanation.data(i)["scores"]) + explanation.data(i)["extra"]["scores"][0]
                     for i in range(4)]
    np.testing.assert_allclose(reconstructed, predict(x[16:]), atol=1e-10)


def test_native_unknown_metadata_is_strict_json_null():
    import json
    from util.interpretation import explanation_json

    payload = {"actual": np.nan, "scores": np.array([0.1, -0.1]), "nested": [np.float64(np.inf), None]}
    restored = json.loads(json.dumps(explanation_json(payload), allow_nan=False))
    assert restored == {"actual": None, "scores": [0.1, -0.1], "nested": [None, None]}
