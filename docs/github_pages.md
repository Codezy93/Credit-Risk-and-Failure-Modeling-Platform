# GitHub Pages showcase

The site is a long-form, marimo-inspired case study in plain HTML, CSS and
JavaScript. Its 18 chapters follow data download, raw auditing, SQL cleaning,
univariate/bivariate/multivariate EDA, population design, MLflow, validation,
XGBoost and ANN research, loss proxies, InterpretML, streaming, load tests,
recovery, deduplication, ELK, reproduction and limitations. It uses recorded
project results; it is not an exported live marimo application or Python kernel.

The presentation is black and white, with no logo or favicon. Text uses Helvetica
Neue and code uses Menlo, with local system fallbacks when those fonts are absent.
Recorded figures display in grayscale through CSS; their original files are preserved.

## Preview locally

```bash
make site
make site-serve
```

Open **http://127.0.0.1:8000**. Stop the server with Ctrl+C.
Python 3.10+ is enough for the site build; the modelling environment, raw dataset,
model binaries, MLflow server, Kafka and ELK are not required. Node is used only
for the optional JavaScript syntax check:

```bash
make site-check
```

`scripts/24_build_site.py` reads the latest committed manifests and selected CSVs,
checks available result fingerprints, and copies 17 existing figures. Twelve
foldable source cells quote the checked-in scripts and SQL, with links to their
full files. True PNG dimensions reserve figure space before lazy loading.

The default page retains its narrative, tables, contribution bars and figures
without JavaScript. JavaScript adds searchable chapter navigation, active-section
highlighting, reading progress, a mobile outline, code copying/expand-collapse,
cohort-and-ROC switching, an enlarged-figure dialog and a print shortcut.

`scripts/25_check_site.py` checks local links, anchor IDs, image alternatives,
relative project URLs, strict JSON, all 18 chapter anchors and the exact public-file
allowlist. Only 23 files are published, including 17 figures. Raw loans, borrower-level predictions, model binaries,
SQLite databases, service logs and local service URLs are excluded. The build
artifact is ignored as `_site/`; commit the source and referenced results instead.

## Publish

1. This repository is already configured to publish with **GitHub Actions**.
   For another copy of the project, choose it in **Settings → Pages** first.
2. Commit the website, workflow, builder/checker and referenced aggregate results
   and figures, then push the update to `main`.
3. In **Actions**, open **Check and deploy GitHub Pages**. The build job checks
   the site and the deploy job publishes its artifact. You can also run the
   workflow manually on `main` using **Run workflow**.
4. Use the URL reported by the successful deployment. The expected project URL
   is **https://codezy93.github.io/Credit-Risk-and-Failure-Modeling-Platform/**.
   This expected URL is not a claim that a deployment has already completed.

The workflow uses GitHub's `configure-pages`, `upload-pages-artifact` and
`deploy-pages` actions. Pull requests run the build and checks without deploying.
Pushes to `main` affecting site sources, builders, aggregate assets or the
workflow trigger a new deployment. The workflow also watches scripts, SQL,
notebooks and utilities so quoted source changes are reflected in the page. Only the deploy job receives Pages write and
OIDC permissions; no personal access token or custom deployment secret is needed.
The `github-pages` environment can enforce any repository deployment protections.

GitHub's official [custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
describes the repository setting, artifact and environment requirements.

## Update the evidence

Run the relevant project experiment first and commit its aggregate results and
latest manifest. `make site` then rebuilds from those files. The site exposes
`assets/provenance.json`, listing SHA-256 fingerprints of its input evidence.
The builder stops when a result disagrees with an available recorded fingerprint,
or if the selected model changes and its descriptions need review.

The selected model's 2015 score remains exploratory because that year was seen
during EDA. XGBoost validation research is shown separately. EAD/LGD/EL figures
are loss proxies; fairness and regulatory limitations stay visible. Historical
load tests and current recovery tests retain their different Spark versions.
This is a public case-study website, not a hosted prediction service or live
Kibana dashboard.

## Verification

The notebook was checked in Chromium at 320, 375, 390, 768, 900, 1024 and
1440 pixels, including a project URL prefix. Checks cover whole-page horizontal
overflow, 18 chapters, source copying, source expand/collapse, the active outline
and search, mobile navigation, cohort values and ROC paths, figure opening/Escape
closing, browser errors and complete content without JavaScript. An axe audit
found no WCAG 2 A/AA or 2.1 AA violations; this automated check is not a complete
accessibility certification. The Actions workflow passed actionlint. Remote
deployment status is reported by the workflow after each push.

See [the verification record](../assets/results/site_verification.json).
