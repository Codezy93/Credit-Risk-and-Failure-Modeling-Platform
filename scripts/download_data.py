"""Download LendingClub accepted loans and unpack the raw CSV."""

import gzip
from pathlib import Path
import shutil

import kagglehub


def main():
    raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    csv_path = raw_dir / "accepted_2007_to_2018Q4.csv"

    if csv_path.exists():
        print(f"Data already exists: {csv_path}")
        return

    raw_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading LendingClub accepted loans from Kaggle...")
    compressed_path = kagglehub.dataset_download(
        "wordsforthewise/lending-club",
        path="accepted_2007_to_2018Q4.csv.gz",
        output_dir=str(raw_dir),
    )

    # Stream the large file to disk instead of loading it into memory.
    # Rename only after extraction finishes so interrupted runs can be rerun.
    temporary_path = csv_path.with_suffix(".csv.part")
    print("Unpacking the CSV...")
    with gzip.open(compressed_path, "rb") as source:
        with temporary_path.open("wb") as destination:
            shutil.copyfileobj(source, destination)

    temporary_path.rename(csv_path)
    print(f"Saved raw data to {csv_path}")


if __name__ == "__main__":
    main()
