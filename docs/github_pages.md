# GitHub Pages showcase

The showcase is plain HTML, CSS and JavaScript in `site/`. It presents data
exploration, temporal model comparisons, InterpretML, loss proxies, paced load
tests, and crash recovery. Its headline numbers and charts are built from the
committed aggregate results, not hand-entered benchmark values.

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
checks available result fingerprints, and copies three existing figures. It
renders a useful default page without JavaScript; JavaScript adds cohort
switching, contribution bars and an accessible enlarged-figure dialog.

`scripts/25_check_site.py` checks local links, anchor IDs, image alternatives,
relative project URLs, strict JSON and the exact public-file allowlist. Only ten
files are published. Raw loans, borrower-level predictions, model binaries,
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
workflow trigger a new deployment. Only the deploy job receives Pages write and
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

The site was checked in Chromium at 375, 390, 768, 1024 and 1440 pixels, including
a project URL prefix. Checks cover whole-page horizontal overflow, the recorded
cohort values, figure dialog opening/Escape closing, browser errors and useful
content with JavaScript disabled. An axe audit found no WCAG 2 A/AA or 2.1 AA
violations; this automated check is not a complete accessibility certification.
The Actions workflow passed actionlint. These local checks do not replace the
first successful remote deployment.

See [the verification record](../assets/results/site_verification.json).
