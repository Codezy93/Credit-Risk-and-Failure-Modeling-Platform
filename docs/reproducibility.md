# Reproducibility verification

Notebook sources now live in `notebooks/`. Historical verification records retain
their execution-time `scripts/` paths and hashes; current commands use the new folder.

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

The core validation stage had **72 passing tests**, with no failures. The full workflow
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

The original validation report had a later reporting revision, recorded with separate
execution and reporting hashes. To close that evidence gap, the committed
`scripts/08_validate_models.py` was rerun unchanged. Its current file hash,
`HEAD` file hash, execution hash, and manifest source hash now all equal
`34e3be3c4c298f15e3a6266aba3aa515373e88b7aa61265c952d1f5f11837a25`.

The fresh batch is `62955be6d71845418f95174c621c98d2`. All seven comparable numerical
CSV tables reproduce the prior reference results at the same tolerances. All eight
result CSV hashes, four saved model hashes, four logged models, and four native
evaluation runs were checked. The 72 tests passed again; the incumbent is unchanged.

[Fresh committed-script verification](../assets/results/validation_hardening_fresh_verification.json).

Machine-readable evidence and source hashes are in the
[verification record](../assets/results/validation_hardening_verification.json).
Full metrics, coefficients, bin counts, and intervals are in the
[validation report](validation_hardening.md) and
[statistics reference, section 21](../assets/statistics.md#21-validation-hardening).

## EAD/LGD experiment and updated notebooks

The later loss stage was executed directly on the existing hashed prepared data.
The final experiment's executed script matches its current source hash, and all
model, input-dataset, and result hashes were verified. Four component models and
four native MLflow regression evaluations were checked; each evaluation used
22,308 eligible validation defaults. The saved bundle reproduced scores for all
162,563 eligible validation loans. PD predictions remained identical.

At completion of the loss stage, the suite had 82 passing tests. All three updated EDA notebooks exported
successfully in the isolated workspace using identical notebook sources, the same
raw CSV, and copies of the final measured model results. Their HTML exports were
written back to `docs/`. The new model-review notebook exported directly in the
project. This notebook work did not overwrite the project's clean or prepared data.

The workflow now appends the loss experiment and model-review export. `make loss`
runs those stages using existing prepared data and the incumbent. The earlier
full-core verification retains its original date and source fingerprints.

See the [loss/notebook verification record](../assets/results/basel_loss_verification.json)
and [experiment report](basel_loss_experiment.md). Capital outputs are assumed-PD
scenarios; no one-year PD estimation or regulatory compliance claim is made.

## ANN challengers

The ANN stage adds two PD classifiers and EAD/LGD regressors. Epoch selection uses
2013 after fitting on 2011–2012. The selected epoch budgets are then frozen for
refitting on 2011–2013; 2014 compares candidates. No 2015 rows enter the experiment.
At completion of the ANN stage, the suite had **85 passing tests**.

All four saved/logged ANN pipelines reproduced their full validation predictions.
Four native MLflow evaluations finished and matched the custom aggregate metrics.
The saved learning curves match the fixed refit epoch counts. The ANN bundle's
full 162,563-loan loss total reproduced, and the updated model-review notebook
exported successfully. Source, dataset, result, and model hashes were checked.
Incumbent PD and reference loss-bundle artifacts stayed unchanged.

The loss report writer was updated to preserve the later ANN statistics section.
Its experiment was rerun from the unchanged modelling logic, and its current
script hash matches that fresh execution. Numerical loss/audit results matched
the earlier reference. The ANN manifest retains the exact historical loss batch
used for its comparison rather than silently switching references.

See the [ANN verification record](../assets/results/ann_experiments_verification.json)
and [ANN experiment report](ann_experiments.md). `make ann` reruns the ANN stage;
`make full` now includes both optional XGBoost and ANN research stages.

## Temporal XGBoost and coefficient validation review

XGBoost protocol v2 separates 2013 stopping from 2014 candidate selection. The
seven final pipelines refit on 2011–2013 using frozen tree counts and no eval_set.
All counts, role-specific dataset hashes, stopping curves and previous/current
protocol comparisons are archived. This does not make the previously explored
2014 cohort a fresh holdout.

The coefficient review refits whole pipelines in 200 year/outcome-stratified
bootstrap samples, records yearly and univariate associations, and compares four
feature-removal variants on 2014. Its paired interval concerns two fixed fitted
models and does not include model-selection or training uncertainty.

The current suite has **93 passing tests**. Current script/source hashes match
both executions. The updated model-review notebook includes both batch IDs and
the remaining model-use limitations. No incumbent artifact or 2015 evaluation
result was changed. Reproduce these review stages using `make review`.

See the [validation gap review](validation_gaps.md) and
[verification record](../assets/results/validation_gaps_verification.json).
