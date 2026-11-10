BOOTSTRAP_PYTHON ?= python3
ENV_DIR ?= .venv-locked
STREAM_ENV_DIR ?= .venv-streaming
STREAM_PYTHON := $(STREAM_ENV_DIR)/bin/python
STREAM_JAVA_HOME ?= /usr/lib/jvm/java-21-openjdk-amd64
SPARK_ENV = JAVA_HOME="$(STREAM_JAVA_HOME)" SPARK_LOCAL_IP=127.0.0.1
PYTHON := $(ENV_DIR)/bin/python

.PHONY: setup test all validate auc full loss ann review interpret streaming-setup kafka-up kafka-down replay stream stream-test stream-check load-test elk-up elk-down monitor-check store-scores recovery-test

.PHONY: site site-check site-serve

site:
	$(BOOTSTRAP_PYTHON) scripts/24_build_site.py
	$(BOOTSTRAP_PYTHON) scripts/25_check_site.py

site-check:
	$(BOOTSTRAP_PYTHON) scripts/25_check_site.py
	node --check site/app.js

site-serve: site
	$(BOOTSTRAP_PYTHON) -m http.server 8000 --bind 127.0.0.1 --directory _site

load-test:
	$(SPARK_ENV) $(STREAM_PYTHON) scripts/18_run_load_test.py $(ARGS)
	$(STREAM_PYTHON) scripts/19_report_load_test.py
	$(STREAM_PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

streaming-setup:
	$(BOOTSTRAP_PYTHON) scripts/setup_environment.py --env-dir $(STREAM_ENV_DIR) --streaming

kafka-up:
	mkdir -p models/streaming/kafka-data
	docker compose up -d --wait kafka

elk-up:
	mkdir -p models/streaming/logs
	docker compose --profile monitoring up -d --wait --wait-timeout 240 elasticsearch logstash kibana
	$(STREAM_PYTHON) scripts/22_setup_elk.py

elk-down:
	docker compose --profile monitoring stop kibana logstash elasticsearch

monitor-check:
	$(STREAM_PYTHON) scripts/22_setup_elk.py --check

store-scores:
	$(STREAM_PYTHON) scripts/20_store_scores.py $(ARGS)

recovery-test: kafka-up elk-up
	$(SPARK_ENV) $(STREAM_PYTHON) scripts/21_test_recovery.py $(ARGS)
	$(STREAM_PYTHON) scripts/23_report_recovery.py
	$(STREAM_PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

kafka-down:
	docker compose stop kafka

replay:
	$(STREAM_PYTHON) scripts/15_replay_loans.py $(ARGS)

stream:
	$(SPARK_ENV) $(STREAM_PYTHON) scripts/16_stream_score.py $(ARGS)

stream-test:
	$(SPARK_ENV) $(STREAM_PYTHON) -m pytest -q tests/test_streaming.py tests/test_score_store.py

stream-check:
	$(STREAM_PYTHON) scripts/17_check_stream_scores.py $(ARGS)

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
	$(PYTHON) scripts/14_interpret_bias.py
	$(PYTHON) -m marimo export html notebooks/10_model_review.py -o docs/model_review.html --no-include-code

interpret: setup
	$(PYTHON) scripts/14_interpret_bias.py
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
