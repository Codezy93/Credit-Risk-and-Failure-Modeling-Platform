# Current-code experiment refresh

Completed: 2026-11-11T21:12:03.598701+00:00. Refresh `20261111T130647666235Z`.

## Tests and CI

The complete local suite passed **110 tests**, with **zero failures, errors or skips**,
including Spark validation. The test environment passed `uv pip check`.
The new **Test suite** GitHub Actions workflow uses Python 3.14, Java 21 and
`requirements-streaming.lock`, runs pytest on main pushes and pull requests,
and uploads JUnit results. This record reports the local run; GitHub execution
starts after the workflow is pushed. Fixture tests do not reproduce model metrics
in CI or download Kaggle data.

## Fresh experiment batches

All seven stages ran against the existing real LendingClub prepared datasets.
Each new manifest records the executed current script hash. Its result CSV hashes
were verified. Historical runs were retained; latest manifest pointers now identify
the new batches.

| Stage | Previous batch | Fresh batch | Verified result CSVs |
| --- | --- | --- | --- |
| 05_train_models | `72061e0a7a1e4d68addcc79a2aae631d` | `6ccea4b79b8343cd971273181d93f680` | 6 |
| 07_improve_auc | `2d9a9d65b9004aa1ade7337465576f17` | `921ccc76e18340b89e608c1fcced9526` | 7 |
| 08_validate_models | `62955be6d71845418f95174c621c98d2` | `e7ebdf9092274ee3b039af91de5b5acb` | 8 |
| 09_basel_loss_experiment | `c072de3541e2496ab90ed6b7c2699137` | `bc7fbb6777cd4365b1a93a4d97fd872f` | 8 |
| 11_ann_experiments | `c85319471ca849758abb207d833f973b` | `fd10b18ae1ca40f18ddcdec526bfcc6b` | 8 |
| 13_review_validation | `da3c8ad1bee14f60ac5156def8b04b14` | `ada1537bb4c646d9baadfa73f78e09c0` | 12 |
| 14_interpret_bias | `86fe262241464da48d8c126660801e05` | `25ccff7634a34d3c893b37ea8ce0499d` | 14 |

## Baseline results

| Cohort | ROC-AUC | Gini | Exact KS | Brier |
| --- | --- | --- | --- | --- |
| Validation 2014 | 0.653889 | 0.307779 | 0.222796 | 0.114375 |
| Exploratory 2015 | 0.654350 | 0.308701 | 0.223789 | 0.122279 |

The 57 shared historical baseline metric values reproduced within relative
tolerance `1e-9` and absolute tolerance `1e-12`. New baseline comparison,
train/validation and selected-model tables include Gini and full-threshold KS.
No metric was inferred from a downsampled ROC curve. The selected model file is
byte-for-byte unchanged by its refit. These results do not create a fresh holdout
or change the [lifetime charge-off target](risk_terminology.md).

## Preservation and evidence

The refresh verified **159 historical files** and
**133 existing MLflow runs** were unchanged. Prepared
input hashes and execution source hashes stayed fixed throughout. Previous manifest
pointers are archived beside this verification. The historical teaching-data audit
and Kafka/ELK benchmark runs were not rerun; their execution-time evidence remains
historical. Their old source fingerprints are not described as current executions.

[Refresh verification](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/refresh/20261111T130647666235Z/verification.json),
[JUnit report](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/refresh/20261111T130647666235Z/pytest.xml),
[baseline comparison](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/refresh/20261111T130647666235Z/metric_comparison.json), and
[historical file hashes](https://github.com/Codezy93/Credit-Risk-and-Failure-Modeling-Platform/blob/main/assets/results/refresh/20261111T130647666235Z/historical_file_hashes.json).

Run `make refresh-experiments` to repeat this refresh with existing raw/prepared data.
Local logs and the previous selected model are retained in ignored
`models/refresh/20261111T130647666235Z/`.
