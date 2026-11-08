from pathlib import Path

import duckdb
import pytest
from threadpoolctl import threadpool_limits


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def limit_threads():
    with threadpool_limits(limits=2):
        yield


@pytest.fixture
def database():
    con = duckdb.connect()
    con.execute("SET VARIABLE raw_path=?", [str(ROOT / "tests/fixtures/loans.csv")])
    for filename in ["00_load_raw.sql", "03_clean_loans.sql"]:
        con.execute((ROOT / "sql" / filename).read_text())
    yield con
    con.close()
