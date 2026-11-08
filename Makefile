BOOTSTRAP_PYTHON ?= python3
ENV_DIR ?= .venv-locked
PYTHON := $(ENV_DIR)/bin/python

.PHONY: setup test all validate auc full

setup:
	$(BOOTSTRAP_PYTHON) scripts/setup_environment.py --env-dir $(ENV_DIR)

test: setup
	$(PYTHON) -m pytest -q

all: setup
	$(PYTHON) scripts/run_project.py $(if $(RAW_DATA),--raw-data "$(RAW_DATA)")

validate: setup
	$(PYTHON) -m pytest -q
	$(PYTHON) scripts/08_validate_models.py

auc: setup
	$(PYTHON) scripts/07_improve_auc.py

full: setup
	$(PYTHON) scripts/run_project.py --include-auc $(if $(RAW_DATA),--raw-data "$(RAW_DATA)")
