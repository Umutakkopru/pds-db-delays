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


@needs_data
def test_previous_stop_coverage_from_full_coverage_start():
    # Decision log D6: from FULL_COVERAGE_START the directly preceding stop of
    # regional through trains is in the data. Fails if the constant is moved to
    # a date before the archive covered all stations.
    df = _query(f"""
        WITH p AS (
            SELECT wuerzburg_id, MAX(train_line_station_num) AS last_prev
            FROM {{files}} WHERE row_role = 'earlier_stop' GROUP BY 1
        )
        SELECT strftime(w.departure_planned_time, '%Y-%m') AS month,
               AVG(CASE WHEN p.last_prev = w.train_line_station_num - 1 THEN 1.0 ELSE 0 END) AS share
        FROM {{files}} w LEFT JOIN p ON p.wuerzburg_id = w.id
        WHERE w.row_role = 'wuerzburg'
          AND w.train_type IN ('RE', 'RB', 'ARV')
          AND w.arrival_planned_time IS NOT NULL
          AND w.departure_planned_time >= TIMESTAMP '{config.FULL_COVERAGE_START}'
          AND NOT COALESCE(w.departure_is_canceled, FALSE)
        GROUP BY 1 ORDER BY 1
    """)
    low = df[df["share"] < 0.95]
    assert len(df) > 0 and low.empty, f"Months with low previous-stop coverage:\n{low}"
