"""
Checks of the downloaded data against the tracked check files. Run with `pytest`.

These tests need data/interim/ (created by src/01_download.py) and are skipped
when the data is not on this computer.
"""
import duckdb
import pandas as pd
import pytest

import config

FILES = sorted(config.DATA_INTERIM.glob("wuerzburg_*.parquet"))
needs_data = pytest.mark.skipif(not FILES, reason="data/interim is empty (run src/01_download.py)")


def _query(sql: str) -> pd.DataFrame:
    pattern = str(config.DATA_INTERIM / "wuerzburg_*.parquet").replace("'", "''")
    return duckdb.sql(sql.format(files=f"read_parquet('{pattern}', union_by_name = true)")).df()


@needs_data
def test_all_months_present():
    months = [f.stem.replace("wuerzburg_", "") for f in FILES]
    assert months == config.month_range()


@needs_data
def test_row_counts_match_tracked_summary():
    # Same Würzburg rows per month as in reports/checks/monthly_summary.csv:
    # fails when a member has downloaded a different version of the dataset.
    expected = pd.read_csv(config.CHECKS / "monthly_summary.csv").set_index("month")["wuerzburg_rows"]
    actual = _query("""
        SELECT source_month AS month, COUNT(*) AS n
        FROM {files} WHERE row_role = 'wuerzburg' GROUP BY 1
    """).set_index("month")["n"]
    different = {m: (int(expected[m]), int(actual.get(m, 0))) for m in expected.index
                 if int(expected[m]) != int(actual.get(m, 0))}
    assert not different, f"(expected, found) rows per month differ: {different}"


@needs_data
def test_wuerzburg_ids_are_unique():
    n, n_ids = _query("""
        SELECT COUNT(*) AS n, COUNT(DISTINCT id) AS n_ids
        FROM {files} WHERE row_role = 'wuerzburg'
    """).iloc[0]
    assert n == n_ids
