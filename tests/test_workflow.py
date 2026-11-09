import gzip
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("compressed", [False, True])
def test_manual_data_runs_without_kaggle(tmp_path, monkeypatch, compressed):
    runner = load_script("run_project")
    downloader = load_script("download_data")
    monkeypatch.setitem(sys.modules, "kagglehub", None)
    contents = b"id,loan_status\n123,Fully Paid\n"
    source = tmp_path / ("manual.csv.gz" if compressed else "manual.csv")
    source.write_bytes(gzip.compress(contents) if compressed else contents)
    project = tmp_path / "project"
    runner.use_local_data(source, root=project)
    downloader.main(project / "data/raw")
    assert (project / "data/raw/accepted_2007_to_2018Q4.csv").read_bytes() == contents
    assert not list((project / "data/raw").glob("*.part"))
    downloader.main(project / "data/raw")


def test_manual_data_never_replaces_existing_source(tmp_path):
    runner = load_script("run_project")
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("original")
    second.write_text("different")
    runner.use_local_data(first, root=tmp_path / "project")
    with pytest.raises(FileExistsError):
        runner.use_local_data(second, root=tmp_path / "project")
    assert first.read_text() == "original"
    with pytest.raises(ValueError):
        runner.use_local_data(tmp_path / "missing.csv", root=tmp_path)


def test_runner_exports_notebooks_and_runs_validation():
    runner = load_script("run_project")
    commands = runner.commands()
    exports = [command for command in commands if "marimo" in command]
    assert len(exports) == 4
    assert all("export" in command and "--no-include-code" in command for command in exports)
    for command in exports:
        notebook = next(value for value in command if value.endswith(".py"))
        assert notebook.startswith("notebooks/")
        assert (ROOT / notebook).is_file()
    assert commands[-4][-1] == "scripts/08_validate_models.py"
    assert commands[-3][-1] == "scripts/09_basel_loss_experiment.py"
    assert commands[-2][-1] == "scripts/13_review_validation.py"
    assert "notebooks/10_model_review.py" in commands[-1]
    assert not any("scripts/07_improve_auc.py" in command for command in commands)
    assert any("scripts/07_improve_auc.py" in command for command in runner.commands(include_auc=True))
    assert not any("scripts/11_ann_experiments.py" in command for command in commands)
    ann_steps = runner.commands(include_ann=True)
    assert ann_steps[-3][-1] == "scripts/11_ann_experiments.py"
    assert ann_steps[-2][-1] == "scripts/13_review_validation.py"
    assert "notebooks/10_model_review.py" in ann_steps[-1]
