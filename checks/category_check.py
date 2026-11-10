"""
category_check.py - How do train types and line numbers change over time?

Answers four questions before the cleaning step is written:
  1. ARV appears in Dec 2025 while RE shrinks: did ARV take over existing RE/RB lines?
  2. Are delay rates of those lines comparable before (as RE/RB) and after (as ARV)?
  3. What are the rows with train_type = NaN (more frequent in 2026)?
  4. What are the Bus rows (many in summer 2024)?

Reads:  data/interim/wuerzburg_*.parquet
Writes: reports/checks/line_types_over_time.csv (printed as well)

Run: python checks/category_check.py
"""
from pathlib import Path
import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402  (shared paths and constants)

FILES = str(config.DATA_INTERIM / "wuerzburg_*.parquet").replace("'", "''")
OUT = config.CHECKS
OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 200)

con = duckdb.connect()
con.execute(f"""
    CREATE VIEW w AS
    SELECT *,
           regexp_extract(line_number, '([0-9]+)$', 1)                     AS line_digits,
           (epoch(departure_change_time) - epoch(departure_planned_time)) / 60 AS dep_delay,
           NOT COALESCE(arrival_is_canceled, FALSE) AND NOT COALESCE(departure_is_canceled, FALSE) AS not_canceled
    FROM read_parquet('{FILES}')
    WHERE row_role = 'wuerzburg'
""")

print("\n=== 1. Which train types run each line number? (Oct 2025 vs Mar 2026) ===")
lines = con.sql("""
    SELECT line_digits,
           string_agg(DISTINCT CASE WHEN source_month = '2025-10' THEN train_type || ':' || line_number END, ', '
                      ORDER BY CASE WHEN source_month = '2025-10' THEN train_type || ':' || line_number END) AS oct_2025,
           string_agg(DISTINCT CASE WHEN source_month = '2026-03' THEN train_type || ':' || line_number END, ', '
                      ORDER BY CASE WHEN source_month = '2026-03' THEN train_type || ':' || line_number END) AS mar_2026,
           COUNT(*) FILTER (WHERE source_month = '2025-10') AS n_oct_2025,
           COUNT(*) FILTER (WHERE source_month = '2026-03') AS n_mar_2026
    FROM w
    WHERE train_type IN ('RE', 'RB', 'ARV') AND line_digits <> ''
    GROUP BY line_digits
    ORDER BY n_mar_2026 + n_oct_2025 DESC, line_digits
""").df()
print(lines.to_string(index=False))
lines.to_csv(OUT / "line_types_over_time.csv", index=False)

print("\n=== 2. Share departing 6+ min late per line and period (lines run by ARV in 2026) ===")
print(con.sql("""
    WITH arv_lines AS (SELECT DISTINCT line_digits FROM w WHERE train_type = 'ARV' AND line_digits <> '')
    SELECT line_digits,
           CASE WHEN source_month < '2025-12' THEN '1 before Dec 2025' ELSE '2 from Dec 2025' END AS period,
           string_agg(DISTINCT train_type, '/' ORDER BY train_type) AS types,
           COUNT(*) AS departures,
           ROUND(100 * AVG(CASE WHEN dep_delay >= 6 THEN 1 ELSE 0 END), 1) AS pct_delayed_6
    FROM w
    WHERE line_digits IN (SELECT line_digits FROM arv_lines)
      AND train_type IN ('RE', 'RB', 'ARV') AND not_canceled AND dep_delay IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
""").df().to_string(index=False))

print("\n=== 3. Rows with train_type = NaN ===")
print(con.sql("""
    SELECT source_month,
           COUNT(*) AS n,
           COUNT(*) FILTER (WHERE departure_planned_time IS NOT NULL) AS with_planned_dep,
           COUNT(*) FILTER (WHERE has_plan_record) AS with_plan_record,
           string_agg(DISTINCT line_number, ', ' ORDER BY line_number) AS lines,
           string_agg(DISTINCT final_destination_station, ', ' ORDER BY final_destination_station) AS destinations
    FROM w WHERE train_type IS NULL
    GROUP BY 1 ORDER BY 1
""").df().to_string(index=False))

print("\n=== 4. Bus rows (replacement buses?) ===")
print(con.sql("""
    SELECT source_month, COUNT(*) AS n,
           string_agg(DISTINCT line_number, ', ' ORDER BY line_number) AS lines,
           ROUND(100 * AVG(CASE WHEN is_replacement_train THEN 1 ELSE 0 END), 1) AS pct_replacement_flag
    FROM w WHERE train_type = 'Bus'
    GROUP BY 1 ORDER BY 1
""").df().to_string(index=False))
print(f"\nSaved: {OUT / 'line_types_over_time.csv'}")
