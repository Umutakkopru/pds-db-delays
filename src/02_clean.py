"""
Step 2: clean the Würzburg rows and compute the target.

Writes one row per planned departure at Würzburg Hbf. No departure is deleted:
rows that the models must not use get an `exclude_reason` (bus, no_plan_record,
canceled, dst_night, invalid_delay, duplicate_id); modelling rows have NULL
there. Adds the target (`dep_delay`, `delayed`), `service`, `line_id`,
`is_through`, `has_prev_stop`, `service_date` and the split of each scenario.
Rules: docs/decision_log.md D2, D7-D10, D19, D20.

Reads:  data/interim/wuerzburg_YYYY-MM.parquet            (step 1)
Writes: data/processed/wuerzburg_clean.parquet            (all planned departures)
        data/processed/wuerzburg_prev_stops.parquet       (earlier stops of these departures)
        reports/checks/cleaning_counts.csv                (rows per split and exclude_reason)
        reports/checks/through_train_counts.csv           (modelling rows by is_through / has_prev_stop)
        reports/checks/service_counts.csv                 (modelling rows per split and service)

Usage: python src/02_clean.py
"""
from pathlib import Path

import duckdb

import config

CLEAN_FILE = config.DATA_PROCESSED / "wuerzburg_clean.parquet"
PREV_FILE = config.DATA_PROCESSED / "wuerzburg_prev_stops.parquet"


def _quote(path: Path | str) -> str:
    return str(path).replace("'", "''")


def split_case(scenario: str, column: str = "departure_planned_time") -> str:
    """SQL CASE expression that names the split (train/val/test) of a timestamp column."""
    parts = [
        f"WHEN {column} >= TIMESTAMP '{start}' AND {column} < TIMESTAMP '{end}' THEN '{name}'"
        for name, (start, end) in config.SPLITS[scenario].items()
    ]
    return "CASE " + " ".join(parts) + " END"


def clean(con: duckdb.DuckDBPyConnection, files: str, clean_file: Path, prev_file: Path) -> None:
    """Run the cleaning SQL on the filtered months and write the two Parquet files."""
    sql = (config.SQL_DIR / "02_clean.sql").read_text(encoding="utf-8")
    dst_days = ", ".join(f"DATE '{d.isoformat()}'" for d in config.dst_change_days())
    sql = sql.format(
        files=_quote(files),
        threshold=config.DELAY_THRESHOLD_MIN,
        invalid_below=config.INVALID_DELAY_BELOW_MIN,
        dst_days=dst_days,
        dst_from=config.DST_EXCLUDE_HOURS[0],
        dst_to=config.DST_EXCLUDE_HOURS[1],
        split_a=split_case("A"),
        split_b=split_case("B"),
    )
    con.execute(f"COPY ({sql}) TO '{_quote(clean_file)}' (FORMAT PARQUET)")

    # Earlier stops of the cleaned departures, one row per (wuerzburg_id, id).
    con.execute(f"""
        COPY (
            SELECT DISTINCT ON (e.wuerzburg_id, e.id)
                   e.* EXCLUDE (row_role),
                   (epoch(COALESCE(e.departure_change_time, e.arrival_change_time))
                    - epoch(COALESCE(e.departure_planned_time, e.arrival_planned_time))) / 60 AS stop_delay,
                   COALESCE(e.departure_is_canceled, FALSE) AS stop_canceled
            FROM read_parquet('{_quote(files)}', union_by_name = true) e
            WHERE e.row_role = 'earlier_stop'
              AND e.wuerzburg_id IN (SELECT id FROM read_parquet('{_quote(clean_file)}'))
            ORDER BY e.wuerzburg_id, e.id
        ) TO '{_quote(prev_file)}' (FORMAT PARQUET)
    """)


def write_counts(con: duckdb.DuckDBPyConnection, clean_file: Path) -> None:
    """Rows per split and exclude_reason; modelling rows by through-train flags and by service."""
    f = _quote(clean_file)
    order = "CASE {col} WHEN 'train' THEN 1 WHEN 'val' THEN 2 WHEN 'test' THEN 3 ELSE 4 END"
    counts = con.sql(f"""
        WITH c AS (
            SELECT COALESCE(split_a, 'outside') AS split_a,
                   COALESCE(exclude_reason, 'modelling_row') AS exclude_reason,
                   COUNT(*) AS n_rows,
                   -- no label statistics on the test period before the final run (CLAUDE.md, evaluation protocol)
                   CASE WHEN COALESCE(split_a, 'outside') <> 'test' THEN ROUND(100 * AVG(delayed), 2) END AS pct_delayed
            FROM read_parquet('{f}')
            GROUP BY 1, 2
        )
        SELECT split_a, exclude_reason, n_rows,
               ROUND(100.0 * n_rows / SUM(n_rows) OVER (PARTITION BY split_a), 2) AS pct_of_split,
               pct_delayed
        FROM c
        ORDER BY {order.format(col="split_a")}, exclude_reason <> 'modelling_row', n_rows DESC, exclude_reason
    """).df()
    through = con.sql(f"""
        WITH c AS (
            SELECT COALESCE(split_b, 'outside') AS split_b, is_through, has_prev_stop,
                   COUNT(*) AS n_rows,
                   CASE WHEN COALESCE(split_b, 'outside') <> 'test' THEN ROUND(100 * AVG(delayed), 2) END AS pct_delayed
            FROM read_parquet('{f}')
            WHERE exclude_reason IS NULL
            GROUP BY 1, 2, 3
        )
        SELECT * FROM c
        ORDER BY {order.format(col="split_b")}, is_through DESC, has_prev_stop DESC
    """).df()
    service = con.sql(f"""
        SELECT split_a, service, COUNT(*) AS n_rows,
               COUNT(*) FILTER (WHERE train_type = 'ARV') AS n_arv,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY split_a), 2) AS pct_of_split,
               CASE WHEN split_a <> 'test' THEN ROUND(100 * AVG(delayed), 2) END AS pct_delayed
        FROM read_parquet('{f}')
        WHERE exclude_reason IS NULL
        GROUP BY split_a, service
        ORDER BY {order.format(col="split_a")}, n_rows DESC
    """).df()
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    service.to_csv(config.CHECKS / "service_counts.csv", index=False)
    counts.to_csv(config.CHECKS / "cleaning_counts.csv", index=False)
    through.to_csv(config.CHECKS / "through_train_counts.csv", index=False)

    total = con.sql(f"""
        SELECT COUNT(*) AS planned_departures,
               COUNT(*) FILTER (WHERE exclude_reason IS NULL) AS modelling_rows,
               ROUND(100 * AVG(delayed) FILTER (WHERE exclude_reason IS NULL AND split_a IN ('train', 'val')), 2) AS pct_delayed_train_val
        FROM read_parquet('{f}')
    """).df()
    print("\n=== Totals ===")
    print(total.to_string(index=False))
    print("\n=== Rows per scenario A split and exclude_reason ===")
    print(counts.to_string(index=False))
    print("\n=== Modelling rows per scenario B split: through trains and earlier stops ===")
    print(through.to_string(index=False))
    print("\n=== Modelling rows per scenario A split and service ===")
    print(service.to_string(index=False))
    print(f"\nChecks written to {config.CHECKS}")


def main() -> None:
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    files = str(config.DATA_INTERIM / "wuerzburg_*.parquet")
    clean(con, files, CLEAN_FILE, PREV_FILE)
    write_counts(con, CLEAN_FILE)
    print(f"Saved: {CLEAN_FILE}\n       {PREV_FILE}")


if __name__ == "__main__":
    main()
