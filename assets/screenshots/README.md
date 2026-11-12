# README screenshot provenance

Captured on **12 November 2026** from the project's existing local MkDocs build,
using Chromium headless at **1440 × 1050**. These first two images are browser screenshots of real MkDocs reports.
The MLflow screenshots documented below show the actual local tracking interface.
The capture did not retrain models or repeat the historical experiments.

| Image | Built page | Report source | Experiment batch |
| --- | --- | --- | --- |
| [Model experiment report](model-experiment-report.png) | `_site/model_experiments/index.html` | [Baseline report](../../docs/model_experiments.md) | `6ccea4b79b8343cd971273181d93f680` |
| [Scorecard report](scorecard-report.png) | `_site/scorecard/index.html` | [Scorecard report](../../docs/scorecard.md) | `7e8db47185e94b90aeec59a0e9bdca57` |

The images show the first viewport, not the complete report. Wide tables and
content below the viewport should be read in the linked Markdown reports or
published documentation. Captions in the root README distinguish screenshots
from saved analytical figures. Only aggregate results are shown.

To refresh, build the current reports with `make site-check`, then capture each
page in a browser. The command used was equivalent to the following, with an
absolute `file:///.../_site/...` URL and a locally installed Chromium executable:

```bash
chromium --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --user-data-dir=/tmp/credit-risk-readme-browser \
  --window-size=1440,1050 \
  --screenshot=assets/screenshots/model-experiment-report.png \
  file:///absolute/path/to/project/_site/model_experiments/index.html
```

Screenshot hashes and report-source hashes at capture time are recorded in
[capture_manifest.json](capture_manifest.json). Those identify these snapshots;
they are not a replacement for experiment verification manifests.

## MLflow interface captures

Captured on **12 November 2026** at **1600 × 1100**, using MLflow **3.18.0**
with the existing SQLite tracking database `models/mlflow.db`. The Model training
view is selected; the unrelated GenAI onboarding view is not shown. The assistant
panel was closed through its normal UI control. No displayed metrics or data were
edited, and no models were retrained.

| Image | Local UI route | Evidence shown |
| --- | --- | --- |
| [Experiment runs](mlflow-scorecard-experiments.png) | `/#/experiments/13/runs?workflowType=machine_learning` | Historical runs, statuses, datasets and digests; expanded dataset rows |
| [Training run](mlflow-scorecard-run.png) | `/#/experiments/13/runs/e6af28c681144dcab734e0ed24824f81?workflowType=machine_learning` | Saved scorecard training run, metrics and dataset associations |
| [Native evaluation](mlflow-native-evaluation.png) | `/#/experiments/13/runs/cd123cbfd43748f0bbd6ff1811285cf5?workflowType=machine_learning` | Validation evaluation metrics, dataset and finished status |

All routes are relative to `http://127.0.0.1:5000`. This local server is not a
publicly hosted MLflow service. These screenshots show the scorecard challenger,
not the incumbent. Its validation AUC is **0.629116**. The evaluation's default
threshold of 0.50 yields zero flags and zero recall; accuracy alone is misleading.
See the [scorecard report](../../docs/scorecard.md) for the interpretation.

The experiment table retains failed and diagnostic historical runs. Source git
labels shown by MLflow are metadata recorded at execution; source-hash manifests
provide the more precise fingerprint for runs made with uncommitted changes.
