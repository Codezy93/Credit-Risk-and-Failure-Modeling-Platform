# Publishing the documentation

The project uses MkDocs 1.6.1 and its built-in `mkdocs` theme. There are no custom
templates, stylesheets or JavaScript. Markdown reports live in `docs/`, and
`mkdocs.yml` defines their navigation. Charts retain their original colors.

## Local preview

Install the documentation dependency in your chosen Python environment:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

Open the local URL printed by MkDocs. Because `site_url` includes the repository
name, the preview uses the same path prefix as GitHub Pages.

The equivalent Make targets are `make docs-setup`, `make site-serve` and
`make site`. To select an environment, use
`make site DOCS_PYTHON=/path/to/python`.

## Build

```bash
python -m mkdocs build --strict
```

The output is `_site/`, which is ignored by Git. A strict build fails on warnings
such as missing documentation links. Building the documentation does not require
the dataset, trained models or running services.

Reports link to committed result files on GitHub. Embedded figures use the
repository's raw image URLs. The HTML exports of the marimo notebooks are also
available from the documentation. Raw datasets, local databases and model
binaries are not copied into the site.

## GitHub Pages

The repository's Pages source is **GitHub Actions**. The workflow in
`.github/workflows/pages.yml` installs MkDocs, runs a strict build and uploads
`_site/`. Main-branch pushes deploy the artifact; pull requests build it without
deploying.

Update a report in `docs/` and add any new page to `mkdocs.yml`. Commit and push
to `main`, then check **Actions → Check and deploy GitHub Pages**.

The published site is
[Credit Risk and Failure Modeling](https://codezy93.github.io/Credit-Risk-and-Failure-Modeling-Platform/).

See the [MkDocs configuration guide](https://www.mkdocs.org/user-guide/configuration/)
for navigation and build options.
