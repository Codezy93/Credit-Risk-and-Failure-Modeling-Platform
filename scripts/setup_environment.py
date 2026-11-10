"""Create the isolated environment used by the locked Makefile workflow."""

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-dir", type=Path, default=ROOT / ".venv-locked")
    parser.add_argument("--streaming", action="store_true", help="Install the optional Kafka/PySpark lock.")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("The verified lock targets Python 3.14. Run setup with a Python 3.14 interpreter.")
    env_dir = args.env_dir.resolve()
    python = env_dir / "bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(env_dir)], check=True)
    config = (env_dir / "pyvenv.cfg").read_text().lower()
    if "include-system-site-packages = true" in config:
        parser.error("Use an isolated environment without system site packages.")
    uv_pin = next(line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines() if line.startswith("uv=="))
    uv = env_dir / "bin/uv"
    if not uv.exists():
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", uv_pin], check=True)
    lock = "requirements-streaming.lock" if args.streaming else "requirements.lock"
    subprocess.run([str(uv), "pip", "sync", "--python", str(python), "--require-hashes",
                    str(ROOT / lock)], check=True, cwd=ROOT)
    subprocess.run([str(uv), "pip", "check", "--python", str(python)], check=True)


if __name__ == "__main__":
    main()
