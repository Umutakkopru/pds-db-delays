"""
Step 4: feature tables for scenario A and scenario B.

Scenario A (asked the day before): timetable, calendar, weather at the planned
departure hour and delay rates of the 28 days that end two days before the
departure. Scenario B (asked when the train leaves its previous stop): the same
columns plus the delays at the last two earlier stops.

The columns are exactly features_config.FEATURES plus the key, split and target
columns in features_config.META_COLUMNS; tests/test_features.py checks this and
the leakage rules (time-travel test, earlier-stop timing).

Reads:  data/processed/wuerzburg_clean.parquet, wuerzburg_prev_stops.parquet   (step 2)
        data/processed/weather_hourly.parquet, calendar_daily.parquet          (step 3)
Writes: data/processed/features_a.parquet     (every modelling departure)
        data/processed/features_b.parquet     (through trains with an earlier stop, scenario B splits)
        reports/checks/feature_summary.csv    (missing values per feature and table)

Usage: python src/04_features.py
"""
from pathlib import Path

import duckdb
import pandas as pd

import config
import features_config

FEATURES_A = config.DATA_PROCESSED / "features_a.parquet"
FEATURES_B = config.DATA_PROCESSED / "features_b.parquet"


def parquet(path: Path) -> str:
    """SQL relation that reads a Parquet file."""
    return "read_parquet('" + str(path).replace("'", "''") + "')"


def features_a_sql(clean: str, weather: str, calendar: str) -> str:
    """SQL text of the scenario A feature table for the given relations."""
    sql = (config.SQL_DIR / "04_features.sql").read_text(encoding="utf-8")
    return sql.format(
        clean=clean, weather=weather, calendar=calendar,
        first_back=config.HISTORY_FIRST_DAY_BACK, last_back=config.HISTORY_LAST_DAY_BACK,
        min_rows=config.MIN_HISTORY_ROWS,
    )


def features_b_sql(features_a: str, clean: str, prev: str) -> str:
    """SQL text of the scenario B feature table for the given relations."""
    sql = (config.SQL_DIR / "04_features_b.sql").read_text(encoding="utf-8")
    return sql.format(features_a=features_a, clean=clean, prev=prev)


def build(con: duckdb.DuckDBPyConnection, clean: str, prev: str, weather: str, calendar: str,
          out_a: Path, out_b: Path) -> None:
    """Write both feature tables."""
    con.execute(f"COPY ({features_a_sql(clean, weather, calendar)}) TO '{str(out_a)}' (FORMAT PARQUET)")
    con.execute(f"COPY ({features_b_sql(parquet(out_a), clean, prev)}) TO '{str(out_b)}' (FORMAT PARQUET)")


def summary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Rows per split and share of missing values per feature."""
    rows = []
    for scenario, path, split in (("A", FEATURES_A, "split_a"), ("B", FEATURES_B, "split_b")):
        df = con.sql(f"SELECT * FROM {parquet(path)}").df()
        for name in features_config.FEATURES[scenario]:
            rows.append({
                "scenario": scenario, "feature": name, "dtype": str(df[name].dtype),
                "pct_missing": round(100 * df[name].isna().mean(), 2),
                "n_distinct": int(df[name].nunique()),
            })
        print(f"\nScenario {scenario}: {len(df):,} rows; per split:",
              df.groupby(split, dropna=False).size().to_dict())
    return pd.DataFrame(rows)


def main() -> None:
    con = duckdb.connect()
    build(
        con,
        clean=parquet(config.DATA_PROCESSED / "wuerzburg_clean.parquet"),
        prev=parquet(config.DATA_PROCESSED / "wuerzburg_prev_stops.parquet"),
        weather=parquet(config.DATA_PROCESSED / "weather_hourly.parquet"),
        calendar=parquet(config.DATA_PROCESSED / "calendar_daily.parquet"),
        out_a=FEATURES_A, out_b=FEATURES_B,
    )
    table = summary(con)
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.CHECKS / "feature_summary.csv", index=False)
    print()
    print(table.to_string(index=False))
    print(f"\nSaved: {FEATURES_A}\n       {FEATURES_B}")


if __name__ == "__main__":
    main()
