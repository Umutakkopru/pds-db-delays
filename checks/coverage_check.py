"""
coverage_check.py - Scenario B coverage check (earlier stops of each trip).

Question: for trains that ARRIVE at Würzburg Hbf and depart again, do the
earlier stops of the same trip exist in the data? Is this different before
and after November 2025, when the archive expanded to all stations?

Reads:  monthly DB files in data/raw/monthly_processed_data/ (downloaded by
        src/01_download.py; this script never downloads or deletes data)
Writes: reports/checks/coverage_by_month.csv

Note: the 12-hour window here ends at the Würzburg planned DEPARTURE; the
pipeline (src/sql/01_filter_month.sql) uses the planned ARRIVAL. The numbers
in the decision log (D6) come from this script.

Run:    python checks/coverage_check.py
        python checks/coverage_check.py --months 2025-10 2025-11
"""
from pathlib import Path
import argparse
import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402  (shared paths and constants)

STATION = config.STATION
# Old period (100 largest stations) vs. new period (all stations).
DEFAULT_MONTHS = ["2024-07", "2025-03", "2025-10", "2025-11", "2026-10"]


def get_file(month: str) -> Path:
    """Return the local path of a monthly raw file; stop if it is missing."""
    path = config.DATA_RAW / config.HF_FOLDER / f"data-{month}.parquet"
    if not path.exists():
        sys.exit(
            f"{path} is missing. Download it with the pipeline step first:\n"
            f"  python src/01_download.py --months {month} --force"
        )
    return path


# Step 1: how many distinct stations does the month contain?
STATIONS_SQL = "SELECT COUNT(DISTINCT station_name) AS n_stations FROM read_parquet('{f}')"

# Step 2: coverage of earlier stops, per train type.
# A trip = same train_line_ride_id, earlier stop number, and an earlier stop time
# within 12 hours before the Würzburg departure (handles midnight; the ride ID
# alone repeats on every day of the month).
COVERAGE_SQL = """
WITH f AS (SELECT * FROM read_parquet('{f}')),
w AS (
    SELECT train_line_ride_id     AS ride,
           train_line_station_num AS w_num,
           departure_planned_time AS w_dep,
           CASE WHEN train_type IN ('ICE', 'RE', 'RB', 'ARV', 'NJ')
                THEN train_type ELSE 'Other' END AS ttype
    FROM f
    WHERE station_name = '{station}'
      AND arrival_planned_time   IS NOT NULL   -- train comes from somewhere
      AND departure_planned_time IS NOT NULL   -- and departs again
      AND NOT COALESCE(departure_is_canceled, FALSE)
),
p AS (
    SELECT train_line_ride_id     AS ride,
           train_line_station_num AS num,
           COALESCE(departure_planned_time, arrival_planned_time) AS t,
           departure_change_time IS NOT NULL AS has_delay_info
    FROM f
    WHERE train_line_ride_id IN (SELECT ride FROM w)
      AND station_name <> '{station}'
),
j AS (
    SELECT w.ride, w.w_dep, w.ttype, w.w_num,
           COUNT(p.num) AS n_prev,
           MAX(CASE WHEN p.num = w.w_num - 1 THEN 1 ELSE 0 END) AS direct_prev,
           MAX(CASE WHEN p.has_delay_info THEN 1 ELSE 0 END)     AS prev_delay_known
    FROM w
    LEFT JOIN p
      ON  p.ride = w.ride
      AND p.num  < w.w_num
      AND p.t    < w.w_dep
      AND p.t   >= w.w_dep - INTERVAL 12 HOUR
    GROUP BY w.ride, w.w_dep, w.ttype, w.w_num
)
SELECT ttype AS train_type,
       COUNT(*) AS departures,
       ROUND(100 * AVG(CASE WHEN n_prev > 0 THEN 1 ELSE 0 END), 1) AS pct_any_prev,
       ROUND(100 * AVG(direct_prev), 1)      AS pct_direct_prev,
       ROUND(100 * AVG(prev_delay_known), 1) AS pct_prev_delay_known,
       MEDIAN(n_prev)                        AS median_prev_stops
FROM j
GROUP BY ttype
ORDER BY departures DESC
"""

# Step 3: one example RB trip on the 15th, all its stops that day.
EXAMPLE_RIDE_SQL = """
SELECT train_line_ride_id AS ride, departure_planned_time AS w_dep, line_number
FROM read_parquet('{f}')
WHERE station_name = '{station}' AND train_type = 'RB'
  AND arrival_planned_time IS NOT NULL AND departure_planned_time IS NOT NULL
  AND day(departure_planned_time) = 15
ORDER BY departure_planned_time
LIMIT 1
"""

EXAMPLE_STOPS_SQL = """
SELECT train_line_station_num AS num, station_name,
       arrival_planned_time, departure_planned_time, delay_in_min
FROM read_parquet('{f}')
WHERE train_line_ride_id = '{ride}'
  AND COALESCE(departure_planned_time, arrival_planned_time)
      BETWEEN TIMESTAMP '{w_dep}' - INTERVAL 12 HOUR
          AND TIMESTAMP '{w_dep}' + INTERVAL 12 HOUR
ORDER BY num
"""


def check_month(con: duckdb.DuckDBPyConnection, month: str) -> pd.DataFrame:
    f = str(get_file(month)).replace("'", "''")
    print(f"\n=== {month} ===")

    n_st = con.sql(STATIONS_SQL.format(f=f)).fetchone()[0]
    print(f"Distinct stations in file: {n_st}")

    cov = con.sql(COVERAGE_SQL.format(f=f, station=STATION)).df()
    cov.insert(0, "month", month)
    cov.insert(1, "n_stations", n_st)
    print(cov.to_string(index=False))

    ex = con.sql(EXAMPLE_RIDE_SQL.format(f=f, station=STATION)).df()
    if len(ex):
        ride, w_dep, line = ex.iloc[0]["ride"], ex.iloc[0]["w_dep"], ex.iloc[0]["line_number"]
        print(f"\nExample RB trip (line {line}, Würzburg departure {w_dep}) - all stops in the data:")
        stops = con.sql(EXAMPLE_STOPS_SQL.format(f=f, ride=ride, w_dep=w_dep)).df()
        print(stops.to_string(index=False))

    return cov


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--months", nargs="+", default=DEFAULT_MONTHS)
    args = parser.parse_args()

    con = duckdb.connect()
    result = pd.concat([check_month(con, m) for m in args.months], ignore_index=True)

    config.CHECKS.mkdir(parents=True, exist_ok=True)
    out = config.CHECKS / "coverage_by_month.csv"
    result.to_csv(out, index=False)

    print("\n=== Summary: % of arriving trains with at least one earlier stop ===")
    print(result.pivot(index="train_type", columns="month", values="pct_any_prev").to_string())
    print("\n=== Summary: % with the directly preceding stop ===")
    print(result.pivot(index="train_type", columns="month", values="pct_direct_prev").to_string())
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
