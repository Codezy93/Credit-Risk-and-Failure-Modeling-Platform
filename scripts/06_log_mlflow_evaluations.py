"""Fill MLflow dataset/evaluation views using the existing fitted models."""

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from threadpoolctl import threadpool_limits
from util.mlflow_evaluation import add_native_evaluations


if __name__ == "__main__":
    manifest = json.loads((ROOT / "assets/results/model_experiments_latest.json").read_text())
    with threadpool_limits(limits=4):
        updated = add_native_evaluations(manifest)
    print("Attached train, validation, and exploratory datasets to the comparison run.")
    print("Linked model metrics to datasets and saved five native classifier evaluations.")
    print("Evaluation runs:", ", ".join(updated["native_evaluation_logging"]["evaluation_run_ids"]))
