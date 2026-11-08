# Reproducibility verification

The core workflow was executed successfully on the real accepted-loans CSV in a
separate checkout using an isolated Python 3.14.9 environment on Linux x86_64.
Dependencies were installed from the complete SHA-256 lock and passed `uv pip check`.
The existing project datasets and incumbent model were preserved.

```bash
make all RAW_DATA=/absolute/path/to/accepted_2007_to_2018Q4.csv
```

Use `BOOTSTRAP_PYTHON=/path/to/python3.14` if needed. The command runs fixture
tests, uses the local CSV, exports three marimo notebooks, prepares data, trains
the baseline comparison, logs native MLflow evaluations, and runs validation
hardening. A local `.csv.gz` also works. The local-data tests explicitly prevent
Kaggle imports, covering environments where the dataset host is blocked.

The final test suite has **72 passing tests**, with no failures. The full workflow
started when the suite had 70 tests; the two added prepared-data export tests were
subsequently run with the complete suite in the same isolated environment.

The repeated workflow reproduced:

- All six prepared predictor/target and metadata file hashes exactly.
- Eight historical train/validation metric rows, including full-threshold KS.
- All 500 paired bootstrap rows and all five AUC/Gini interval rows.
- Four separate-year calibration metric rows.
- All three headless notebook HTML exports.

Numerical table comparisons used relative tolerance `1e-9` and absolute tolerance
`1e-12`. The main validation batch's four logged models loaded successfully; its
four native evaluation runs finished and each used all 162,570 evaluation rows.
CSV hashes and the unchanged incumbent hash were checked.

The optional seven-trial XGBoost search was not rerun during this verification.
`make full` includes it. Its previously measured results remain historical research
snapshots. Kafka, ELK, InterpretML, and bias evaluation remain future stages.

The first validation-hardening logging attempt failed under MLflow's default model
serializer. It remains recorded as a failed run. The completed workflow uses the
same explicit cloudpickle format as the baseline trainer. Model artifacts should
be loaded from this project's trusted local runs.

The report was revised after training to improve presentation and references.
`execution_script_sha256` identifies the preserved executed source snapshot in
MLflow; `reporting_script_sha256` identifies the final report-generation source.
The changes did not retrain models or alter evaluation metrics.

Machine-readable evidence and source hashes are in the
[verification record](../assets/results/validation_hardening_verification.json).
Full metrics, coefficients, bin counts, and intervals are in the
[validation report](validation_hardening.md) and
[statistics reference, section 21](../assets/statistics.md#21-validation-hardening).
