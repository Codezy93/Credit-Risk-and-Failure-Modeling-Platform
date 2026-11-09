"""Run the core workflow headlessly; optional AUC research remains a separate step."""

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def use_local_data(source, root=ROOT):
    source = Path(source).expanduser().resolve()
    if not source.is_file() or not source.name.lower().endswith((".csv", ".csv.gz")):
        raise ValueError("Local data must be an existing LendingClub .csv or .csv.gz file.")
    name = "accepted_2007_to_2018Q4.csv.gz" if source.name.lower().endswith(".gz") else "accepted_2007_to_2018Q4.csv"
    destination = root / "data/raw" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.resolve() != source:
            raise FileExistsError(f"Raw data already exists at {destination}; it will not be replaced.")
    else:
        destination.symlink_to(source)


def commands(include_auc=False, include_ann=False):
    steps = [[sys.executable, "-m", "pytest", "-q"], [sys.executable, "scripts/download_data.py"]]
    for script, output in [("01_data_analysis.py", "data_analysis.html"),
                           ("02_deeper_eda.py", "deeper_eda.html"),
                           ("03_complete_eda.py", "eda_completion.html")]:
        steps.append([sys.executable, "-m", "marimo", "export", "html", f"notebooks/{script}",
                      "-o", f"docs/{output}", "--no-include-code"])
    steps += [[sys.executable, "scripts/04_prepare_model_data.py"],
              [sys.executable, "scripts/05_train_models.py"]]
    if include_auc:
        steps.append([sys.executable, "scripts/07_improve_auc.py"])
    steps.append([sys.executable, "scripts/08_validate_models.py"])
    steps.append([sys.executable, "scripts/09_basel_loss_experiment.py"])
    if include_ann:
        steps.append([sys.executable, "scripts/11_ann_experiments.py"])
    steps.append([sys.executable, "scripts/13_review_validation.py"])
    steps.append([sys.executable, "-m", "marimo", "export", "html", "notebooks/10_model_review.py",
                  "-o", "docs/model_review.html", "--no-include-code"])
    return steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-data", type=Path, help="Use a manually obtained CSV/GZ; no Kaggle download needed.")
    parser.add_argument("--include-auc", action="store_true", help="Also rerun the seven optional AUC research trials.")
    parser.add_argument("--include-ann", action="store_true", help="Also fit the optional ANN PD/EAD/LGD challengers.")
    args = parser.parse_args()
    if args.raw_data:
        use_local_data(args.raw_data)
    for command in commands(args.include_auc, args.include_ann):
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
