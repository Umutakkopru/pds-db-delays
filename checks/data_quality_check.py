"""
data_quality_check.py - Collection gaps, missing delay values, cancellations,
and the exact start of full station coverage.

Background: the archive is collected four times a day (03, 09, 15, 21 UTC);
each run stores changes reaching back 6+ hours. When a run is skipped or late
(documented API errors between Nov 2025 and Jul 2026), stops can be missing or
their delay can be the last forecast instead of the realised value.

Reads:  data/interim/wuerzburg_*.parquet
Writes: reports/checks/quality_by_month.csv
        reports/checks/low_count_days.csv
        reports/checks/coverage_nov_2025_daily.csv
        reports/checks/suspicious_days.csv

Run: python checks/data_quality_check.py
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
    CREATE VIEW allrows AS SELECT * FROM read_parquet('{FILES}');
    CREATE VIEW w AS
    SELECT *,
           CAST(departure_planned_time AS DATE) AS dep_day,
           COALESCE(departure_is_canceled, FALSE) AS canceled  -- rule in CLAUDE.md: departure cancelled at Würzburg
    FROM allrows
    WHERE row_role = 'wuerzburg' AND departure_planned_time IS NOT NULL AND train_type IS DISTINCT FROM 'Bus';
""")

print("\n=== 1. Per month: duplicates, missing change times, cancellations ===")
q1 = con.sql("""
    SELECT source_month AS month,
           COUNT(*) AS planned_departures,
           COUNT(*) - COUNT(DISTINCT id) AS duplicate_ids,
           ROUND(100 * AVG(CASE WHEN NOT canceled AND departure_change_time IS NULL THEN 1 ELSE 0 END), 2) AS pct_no_change_time,
           ROUND(100 * AVG(CASE WHEN canceled THEN 1 ELSE 0 END), 2) AS pct_canceled,
           ROUND(100 * AVG(CASE WHEN NOT canceled AND
                 (epoch(departure_change_time) - epoch(departure_planned_time)) / 60 >= 6 THEN 1 ELSE 0 END), 1) AS pct_delayed_6,
           -- pct_delayed_6 is a share of ALL planned departures (cancelled ones in the
           -- denominator). The target's delay rate counts only departures that ran:
           ROUND(100 * AVG(CASE WHEN NOT canceled THEN
                 CASE WHEN (epoch(departure_change_time) - epoch(departure_planned_time)) / 60 >= 6 THEN 1.0 ELSE 0 END
                 END), 1) AS pct_delayed_6_not_canceled
    FROM w GROUP BY 1 ORDER BY 1
""").df()
print(q1.to_string(index=False))
print("Duplicate ids across ALL files (Würzburg rows):",
      con.sql("SELECT COUNT(*) - COUNT(DISTINCT id) FROM allrows WHERE row_role = 'wuerzburg'").fetchone()[0])
q1.to_csv(OUT / "quality_by_month.csv", index=False)

print("\n=== 2. Days with unusually few planned departures (< 70% of the median for that weekday) ===")
first_day = config.FIRST_MONTH + "-01"
last_day = (pd.Timestamp(config.LAST_MONTH + "-01") + pd.offsets.MonthEnd(1)).date().isoformat()
q2 = con.sql(f"""
    WITH d AS (SELECT dep_day, dayofweek(dep_day) AS dow, COUNT(*) AS n FROM w GROUP BY 1, 2),
    m AS (SELECT dow, MEDIAN(n) AS med FROM d GROUP BY dow)
    SELECT d.dep_day, d.n, m.med AS weekday_median, ROUND(d.n / m.med, 2) AS ratio
    FROM d JOIN m USING (dow)
    WHERE d.n < 0.7 * m.med
      AND d.dep_day BETWEEN DATE '{first_day}' AND DATE '{last_day}'
    ORDER BY d.dep_day
""").df()
print(q2.to_string(index=False) if len(q2) else "none")
q2.to_csv(OUT / "low_count_days.csv", index=False)

print("\n=== 3. November 2025: daily share of RB/RE through trains with the directly preceding stop ===")
q3 = con.sql("""
    WITH a AS (
        SELECT id, train_line_station_num AS w_num, dep_day
        FROM w
        WHERE source_month IN ('2025-10', '2025-11') AND arrival_planned_time IS NOT NULL
          AND (line_number SIMILAR TO '(RE|RB)?[0-9]+') AND train_type IN ('RE', 'RB', 'ARV')
    ),
    p AS (
        SELECT wuerzburg_id, MAX(train_line_station_num) AS last_prev
        FROM allrows WHERE row_role = 'earlier_stop' GROUP BY 1
    )
    SELECT a.dep_day, COUNT(*) AS through_trains,
           ROUND(100 * AVG(CASE WHEN p.last_prev = a.w_num - 1 THEN 1 ELSE 0 END), 1) AS pct_direct_prev
    FROM a LEFT JOIN p ON p.wuerzburg_id = a.id
    WHERE a.dep_day BETWEEN DATE '2025-10-28' AND DATE '2025-11-10'
    GROUP BY 1 ORDER BY 1
""").df()
print(q3.to_string(index=False))
q3.to_csv(OUT / "coverage_nov_2025_daily.csv", index=False)
print("\n=== 4. Days that look 'too punctual' (possible collection gaps) ===")
# departure_change_time is never empty, so a stop whose changes were not
# collected probably shows change time = planned time (0 min delay). Such days
# have an unusually high share of exactly-on-time departures and an unusually
# low delay rate compared with the same month.
q4 = con.sql("""
    WITH d AS (
        SELECT dep_day, source_month,
               COUNT(*) AS n,
               AVG(CASE WHEN departure_change_time = departure_planned_time THEN 1.0 ELSE 0 END) AS share_exact,
               AVG(CASE WHEN (epoch(departure_change_time) - epoch(departure_planned_time)) / 60 >= 6 THEN 1.0 ELSE 0 END) AS share_delayed
        FROM w WHERE NOT canceled
        GROUP BY 1, 2
    ),
    s AS (
        SELECT *,
               MEDIAN(share_exact) OVER (PARTITION BY source_month) AS med_exact
        FROM d
    ),
    g AS (SELECT MEDIAN(share_exact) AS gm, QUANTILE_CONT(share_exact, 0.99) AS p99 FROM d)
    SELECT dep_day, n,
           ROUND(100 * share_exact, 1)   AS pct_exactly_on_time,
           ROUND(100 * med_exact, 1)     AS month_median_pct,
           ROUND(100 * share_delayed, 1) AS pct_delayed_6
    FROM s, g
    WHERE share_exact > g.p99 OR share_exact > med_exact + 0.20
    ORDER BY dep_day
""").df()
print(q4.to_string(index=False) if len(q4) else "none")
q4.to_csv(OUT / "suspicious_days.csv", index=False)

print("\nShare of exactly-on-time departures per month (%):")
print(con.sql("""
    SELECT source_month AS month,
           ROUND(100 * AVG(CASE WHEN departure_change_time = departure_planned_time THEN 1.0 ELSE 0 END), 1) AS pct_exactly_on_time
    FROM w WHERE NOT canceled GROUP BY 1 ORDER BY 1
""").df().T.to_string(header=False))
print(f"\nSaved to {OUT}")
