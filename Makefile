BOOTSTRAP_PYTHON ?= python3
ENV_DIR ?= .venv-locked
PYTHON := $(ENV_DIR)/bin/python

.PHONY: setup test all validate auc full loss ann review

setup:
	$(BOOTSTRAP_PYTHON) scripts/setup_environment.py --env-dir $(ENV_DIR)

test: setup
	$(PYTHON) -m pytest -q

all: setup
	$(PYTHON) scripts/run_project.py $(if $(RAW_DATA),--raw-data "$(RAW_DATA)")

validate: setup
	$(PYTHON) -m pytest -q
	$(PYTHON) scripts/08_validate_models.py

review: setup
	$(PYTHON) -m pytest -q
	$(PYTHON) scripts/07_improve_auc.py
	$(PYTHON) scripts/13_review_validation.py
	$(PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

auc: setup
	$(PYTHON) scripts/07_improve_auc.py

loss: setup
	$(PYTHON) scripts/09_basel_loss_experiment.py
	$(PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

ann: setup
	$(PYTHON) scripts/11_ann_experiments.py
	$(PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

full: setup
	$(PYTHON) scripts/run_project.py --include-auc --include-ann $(if $(RAW_DATA),--raw-data "$(RAW_DATA)")
