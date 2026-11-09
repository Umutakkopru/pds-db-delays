"""
Step 1: download monthly DB files and filter them to Würzburg Hbf.

For every month, downloads data-YYYY-MM.parquet from Hugging Face (skipped if it
is already in data/raw), keeps the Würzburg Hbf rows plus the earlier stops of
the same trips (src/sql/01_filter_month.sql) and saves a small file.
After all months, writes per-month checks: row counts, daily continuity,
train types and line-number formats (to detect category changes over time).

Reads:  Hugging Face dataset piebro/deutsche-bahn-data (monthly files, at the
        fixed revision config.HF_REVISION)
Writes: data/raw/monthly_processed_data/data-YYYY-MM.parquet  (raw, gitignored)
        data/interim/wuerzburg_YYYY-MM.parquet                (filtered month)
        reports/checks/monthly_summary.csv
        reports/checks/train_types_by_month.csv
        reports/checks/line_formats_by_month.csv

Usage:
    python src/01_download.py --months 2026-10 --show-example   # first test
    python src/01_download.py                                   # all months
    python src/01_download.py --delete-raw                      # save disk
"""
from pathlib import Path
import argparse
import time

import duckdb
import pandas as pd

import config


def download_month(month: str) -> Path:
    """Return the local raw file for a month, downloading it if needed."""
    name = f"data-{month}.parquet"
    target = config.DATA_RAW / config.HF_FOLDER / name
    if target.exists():
        return target
    from huggingface_hub import hf_hub_download
    print(f"  downloading {name} ...")
    path = hf_hub_download(
        repo_id=config.HF_REPO,
        repo_type="dataset",
        revision=config.HF_REVISION,
        filename=f"{config.HF_FOLDER}/{name}",
        local_dir=config.DATA_RAW,
    )
    return Path(path)


def filter_month(con: duckdb.DuckDBPyConnection, raw: Path, out: Path, month: str) -> None:
    """Run the filter SQL on one raw file and write the result as Parquet."""
    sql = (config.SQL_DIR / "01_filter_month.sql").read_text(encoding="utf-8")
    sql = sql.format(
        source=str(raw).replace("'", "''"),
        station=config.STATION.replace("'", "''"),
        month=month,
    )
    target = str(out).replace("'", "''")
    con.execute(f"COPY ({sql}) TO '{target}' (FORMAT PARQUET)")


def show_example(con: duckdb.DuckDBPyConnection, out: Path) -> None:
    """Print one RB trip arriving at Würzburg on the 15th with its earlier stops."""
    f = str(out).replace("'", "''")
    ex = con.sql(f"""
        SELECT wuerzburg_id, line_number, departure_planned_time
        FROM read_parquet('{f}')
        WHERE row_role = 'wuerzburg' AND train_type = 'RB'
          AND arrival_planned_time IS NOT NULL AND departure_planned_time IS NOT NULL
          AND day(departure_planned_time) = 15
        ORDER BY departure_planned_time
        LIMIT 1
    """).fetchone()
    if ex is None:
        print("  (no RB example found)")
        return
    wid, line, dep = ex
    print(f"\n  Example RB trip: line {line}, Würzburg departure {dep}")
    stops = con.execute(f"""
        SELECT row_role, train_line_station_num AS num, station_name,
               arrival_planned_time, departure_planned_time, delay_in_min
        FROM read_parquet('{f}')
        WHERE wuerzburg_id = ?
        ORDER BY num
    """, [wid]).df()
    print(stops.to_string(index=False))


def write_checks(con: duckdb.DuckDBPyConnection) -> None:
    """Per-month checks over all filtered files in data/interim."""
    pattern = str(config.DATA_INTERIM / "wuerzburg_*.parquet").replace("'", "''")
    base = f"""
        SELECT *,
               source_month AS month,
               CAST(COALESCE(departure_planned_time, arrival_planned_time, time) AS DATE)     AS day
        FROM read_parquet('{pattern}')
        WHERE row_role = 'wuerzburg'
    """
    config.CHECKS.mkdir(parents=True, exist_ok=True)

    summary = con.sql(f"""
        WITH b AS ({base}),
        daily AS (SELECT month, day, COUNT(*) AS n FROM b GROUP BY month, day)
        SELECT month,
               SUM(n)            AS wuerzburg_rows,
               COUNT(*)          AS days,
               MIN(n)            AS min_rows_per_day,
               MEDIAN(n)         AS median_rows_per_day
        FROM daily GROUP BY month ORDER BY month
    """).df()
    summary.to_csv(config.CHECKS / "monthly_summary.csv", index=False)

    types = con.sql(f"""
        WITH b AS ({base})
        SELECT month, train_type, COUNT(*) AS n
        FROM b GROUP BY month, train_type
    """).df().pivot(index="train_type", columns="month", values="n").fillna(0).astype(int)
    types.to_csv(config.CHECKS / "train_types_by_month.csv")

    lines = con.sql(f"""
        WITH b AS ({base})
        SELECT month,
               ROUND(100 * AVG(CASE WHEN regexp_matches(line_number, '^[0-9]+$') THEN 1 ELSE 0 END), 1)
                   AS pct_digits_only,
               ROUND(100 * AVG(CASE WHEN regexp_matches(line_number, '^[A-Za-z]') THEN 1 ELSE 0 END), 1)
                   AS pct_with_prefix,
               ROUND(100 * AVG(CASE WHEN line_number IS NULL THEN 1 ELSE 0 END), 1) AS pct_missing,
               string_agg(DISTINCT line_number, ', ') AS line_values
        FROM b GROUP BY month ORDER BY month
    """).df()
    lines.to_csv(config.CHECKS / "line_formats_by_month.csv", index=False)

    print("\n=== Monthly summary (Würzburg rows, by source file) ===")
    print(summary.to_string(index=False))
    print("\n=== Train types by month ===")
    print(types.to_string())
    print("\n=== Line-number format by month ===")
    print(lines.drop(columns="line_values").to_string(index=False))
    print(f"\nChecks written to {config.CHECKS}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and filter monthly DB files.")
    parser.add_argument("--months", nargs="+", default=config.month_range())
    parser.add_argument("--force", action="store_true", help="re-filter months that already exist")
    parser.add_argument("--delete-raw", action="store_true", help="delete each raw file after filtering")
    parser.add_argument("--show-example", action="store_true", help="print one RB trip per month")
    args = parser.parse_args()

    config.DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    for month in args.months:
        out = config.DATA_INTERIM / f"wuerzburg_{month}.parquet"
        if out.exists() and not args.force:
            print(f"{month}: already filtered, skipped")
            continue
        t0 = time.time()
        raw = download_month(month)
        filter_month(con, raw, out, month)
        n_w, n_prev = con.sql(f"""
            SELECT COUNT(*) FILTER (WHERE row_role = 'wuerzburg'),
                   COUNT(*) FILTER (WHERE row_role = 'earlier_stop')
            FROM read_parquet('{str(out).replace("'", "''")}')
        """).fetchone()
        print(f"{month}: {n_w:,} Würzburg rows, {n_prev:,} earlier-stop rows ({time.time() - t0:.0f} s)")
        if args.show_example:
            show_example(con, out)
        if args.delete_raw:
            raw.unlink()

    write_checks(con)


if __name__ == "__main__":
    main()
