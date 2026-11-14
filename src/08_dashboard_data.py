"""
Step 8 (extension): the small lookup tables of the Streamlit dashboard.

The dashboard (dashboard/) asks "how likely is a departure of this line, on this
day, in this hour, to leave 6+ minutes late?". It never reads the raw or
processed data: this script exports everything the saved models need to answer
that question into dashboard/data/ (a few hundred kB, tracked in Git so that the
deployed app can read it). Nothing is fitted here.

A dashboard query is not one real departure but a "typical departure" of a line
in an hour of a day in the test period (July - October 2026, decision D15):

  timetable   service, line, destination, through train or not: the chosen line;
              stop position and planned stop time: median of the line in that hour
  calendar    the flags of the chosen day
  weather     the observed weather of the chosen day and hour
  history     the 28-day delay rates that the feature step computed for that day
  previous    typical minutes and stops between the previous stop and Würzburg;
  stops       the delay itself is typed in by the user

Allowed only after the final run (reports/final_run.json), because the
calibration table uses outcomes of the test period.

Reads:  data/processed/features_a.parquet, features_b.parquet                  (step 4)
        data/processed/weather_hourly.parquet, calendar_daily.parquet          (step 3)
        data/processed/wuerzburg_prev_stops.parquet                            (step 2)
        data/processed/predictions_test_a.parquet, predictions_test_b.parquet  (step 5 --final)
        reports/final_run.json                                                 (step 5 --final)
Writes: dashboard/data/lines.parquet      selectable lines with their typical values and usual earlier stops ('A|B')
        dashboard/data/profiles.parquet   typical stop position and stop time per line and hour
        dashboard/data/days.parquet       calendar flags and overall delay rate per day
        dashboard/data/weather.parquet    observed weather per day and hour
        dashboard/data/history.parquet    28-day delay rates per day (service x hour, route)
        dashboard/data/grid.parquet       delay rate per line, weekday and hour (whole data period)
        dashboard/data/meta.json          date range, reliability tables, source of the models

Usage: python src/08_dashboard_data.py
"""
import importlib
import json

import duckdb
import pandas as pd

import config
import features_config

train_step = importlib.import_module("05_train")          # module names start with a digit
error_step = importlib.import_module("06_error_analysis")

OUT = config.ROOT / "dashboard" / "data"
PROCESSED = config.DATA_PROCESSED
MIN_LINE_ROWS = 150        # a line needs this many test-period departures to be selectable
MIN_PROFILE_ROWS = 5       # line x hour cells below this fall back to the line's median
MIN_GRID_ROWS = 10         # line x weekday x hour cells below this stay empty in the heatmap
MIN_GRID_CELLS = 5         # a line with fewer filled cells is not selectable (its heatmap would be empty)
GRID_HOURS = (5, 23)       # hours the page offers; lines that run outside them (night trains) are not selectable
SERVICE_LABEL = {"long_distance": "ICE/IC", "night": "Night train", "regional": "", "other": "Other"}
LINE_KEY = ["service", "line_id", "destination", "is_through"]


def require_final_run() -> dict:
    """The reliability table uses test-period outcomes: refuse before the final run."""
    if not train_step.FINAL_MARKER.exists():
        raise RuntimeError("Dashboard data is written only after the final run (src/05_train.py --final).")
    return json.loads(train_step.FINAL_MARKER.read_text(encoding="utf-8"))


def rel(name: str) -> str:
    return "read_parquet('" + str(PROCESSED / name).replace("'", "''") + "')"


def line_label(service: str, line_id: str | None, destination: str, is_through: bool) -> str:
    """Name of a line in the selection box, e.g. 'RB53 to Bamberg (starts at Würzburg)'."""
    name = line_id if isinstance(line_id, str) else SERVICE_LABEL[service]
    return f"{name} to {destination}" + ("" if is_through else " (starts at Würzburg)")


def build_lines(con: duckdb.DuckDBPyConnection, test: tuple[str, str]) -> pd.DataFrame:
    """Selectable lines: timetable key, typical values and the usual earlier stops."""
    lines = con.sql(f"""
        WITH a AS (
            SELECT * FROM {rel("features_a.parquet")}
            WHERE departure_planned_time >= TIMESTAMP '{test[0]}' AND departure_planned_time < TIMESTAMP '{test[1]}'
        ),
        b AS (SELECT * FROM {rel("features_b.parquet")} WHERE split_b = 'test'),
        usable AS (
            -- same rule as src/sql/04_features_b.sql: earlier stops that give a delay, latest first
            SELECT wuerzburg_id, station_name,
                   row_number() OVER (PARTITION BY wuerzburg_id
                                      ORDER BY COALESCE(departure_planned_time, arrival_planned_time) DESC, id) AS rn
            FROM {rel("wuerzburg_prev_stops.parquet")}
            WHERE NOT stop_canceled AND stop_delay IS NOT NULL
        ),
        typical AS (
            SELECT a.service, a.line_id, a.destination, a.is_through,
                   COUNT(*) AS n_departures,
                   COUNT(*) FILTER (WHERE a.planned_hour BETWEEN {GRID_HOURS[0]} AND {GRID_HOURS[1]}) AS in_page_hours,
                   median(a.stop_position) AS stop_position, median(a.dwell_min) AS dwell_min,
                   COUNT(b.id) AS n_scenario_b,
                   median(b.prev_minutes_to_departure) AS prev_minutes_to_departure,
                   median(b.prev_stops_between) AS prev_stops_between,
                   -- the usual last two earlier stops, taken together so that they belong to one route
                   mode(COALESCE(u2.station_name || '|', '') || u1.station_name)
                       FILTER (WHERE b.id IS NOT NULL) AS earlier_stops
            FROM a
            LEFT JOIN b ON b.id = a.id
            LEFT JOIN usable u1 ON u1.wuerzburg_id = a.id AND u1.rn = 1
            LEFT JOIN usable u2 ON u2.wuerzburg_id = a.id AND u2.rn = 2
            GROUP BY ALL
        )
        SELECT * FROM typical
        WHERE n_departures >= {MIN_LINE_ROWS} AND in_page_hours >= 0.8 * n_departures
        ORDER BY service <> 'long_distance', service <> 'night', line_id, n_departures DESC
    """).df()
    lines.insert(0, "label", [line_label(r.service, r.line_id, r.destination, r.is_through) for r in lines.itertuples()])
    if lines["label"].duplicated().any():
        raise RuntimeError("Line labels are not unique: " + ", ".join(lines.loc[lines["label"].duplicated(), "label"]))
    # scenario B needs a through train with a usual earlier stop
    lines["has_scenario_b"] = lines["is_through"] & lines["earlier_stops"].notna() & (lines["n_scenario_b"] >= MIN_PROFILE_ROWS)
    return lines


def build_profiles(con: duckdb.DuckDBPyConnection, lines: pd.DataFrame, test: tuple[str, str]) -> pd.DataFrame:
    """Typical stop position and planned stop time per line and hour."""
    con.register("lines", lines[["label", *LINE_KEY]])
    return con.sql(f"""
        SELECT l.label, a.planned_hour AS hour, COUNT(*) AS n_departures,
               median(a.stop_position) AS stop_position, median(a.dwell_min) AS dwell_min
        FROM {rel("features_a.parquet")} a
        JOIN lines l ON l.service = a.service AND l.destination = a.destination AND l.is_through = a.is_through
                    AND l.line_id IS NOT DISTINCT FROM a.line_id
        WHERE a.departure_planned_time >= TIMESTAMP '{test[0]}' AND a.departure_planned_time < TIMESTAMP '{test[1]}'
        GROUP BY ALL HAVING COUNT(*) >= {MIN_PROFILE_ROWS}
        ORDER BY 1, 2
    """).df()


def build_days(con: duckdb.DuckDBPyConnection, test: tuple[str, str]) -> pd.DataFrame:
    """Calendar flags per day, and the overall 28-day delay rate that the feature step computed for it."""
    return con.sql(f"""
        SELECT c.service_date, c.is_public_holiday, c.is_school_holiday, c.is_bridge_day, h.hist_rate_all
        FROM {rel("calendar_daily.parquet")} c
        LEFT JOIN (SELECT service_date, any_value(hist_rate_all) AS hist_rate_all
                   FROM {rel("features_a.parquet")} GROUP BY 1) h USING (service_date)
        WHERE c.service_date >= DATE '{test[0]}' AND c.service_date < DATE '{test[1]}'
        ORDER BY 1
    """).df()


def build_weather(con: duckdb.DuckDBPyConnection, test: tuple[str, str]) -> pd.DataFrame:
    columns = ", ".join(features_config.WEATHER_FEATURES)
    return con.sql(f"""
        SELECT CAST(local_hour AS DATE) AS service_date, hour(local_hour) AS hour, {columns}
        FROM {rel("weather_hourly.parquet")}
        WHERE local_hour >= TIMESTAMP '{test[0]}' AND local_hour < TIMESTAMP '{test[1]}'
        ORDER BY 1, 2
    """).df()


def build_history(con: duckdb.DuckDBPyConnection, test: tuple[str, str]) -> pd.DataFrame:
    """
    The history features as the feature step computed them, per day.

    kind 'service_hour': key = service, hour = planned hour -> rate = hist_rate_service_hour
    kind 'route':        key = line (regional) or destination, hour = -1 -> rate = hist_rate_route, n = hist_n_route
    """
    period = f"departure_planned_time >= TIMESTAMP '{test[0]}' AND departure_planned_time < TIMESTAMP '{test[1]}'"
    return con.sql(f"""
        SELECT service_date, 'service_hour' AS kind, service AS key, planned_hour AS hour,
               any_value(hist_rate_service_hour) AS rate, CAST(NULL AS DOUBLE) AS n
        FROM {rel("features_a.parquet")} WHERE {period} GROUP BY ALL
        UNION ALL
        SELECT service_date, 'route', COALESCE(line_id, destination), -1,
               any_value(hist_rate_route), any_value(hist_n_route)
        FROM {rel("features_a.parquet")} WHERE {period} GROUP BY ALL
        ORDER BY 1, 2, 3, 4
    """).df()


def build_grid(con: duckdb.DuckDBPyConnection, lines: pd.DataFrame) -> pd.DataFrame:
    """Share of delayed departures per line, weekday and hour over the whole data period (28 months)."""
    start, end = config.SPLITS["A"]["train"][0], config.SPLITS["A"]["test"][1]
    con.register("lines", lines[["label", *LINE_KEY]])
    return con.sql(f"""
        SELECT l.label, a.weekday, a.planned_hour AS hour, COUNT(*) AS n_departures, AVG(a.delayed) AS delay_rate
        FROM {rel("features_a.parquet")} a
        JOIN lines l ON l.service = a.service AND l.destination = a.destination AND l.is_through = a.is_through
                    AND l.line_id IS NOT DISTINCT FROM a.line_id
        WHERE a.departure_planned_time >= TIMESTAMP '{start}' AND a.departure_planned_time < TIMESTAMP '{end}'
          AND a.planned_hour BETWEEN {GRID_HOURS[0]} AND {GRID_HOURS[1]}
        GROUP BY ALL HAVING COUNT(*) >= {MIN_GRID_ROWS}
        ORDER BY 1, 2, 3
    """).df()


def build_meta(marker: dict, test: tuple[str, str], lines: pd.DataFrame) -> dict:
    """Date range, reliability tables of the test period and where the models come from."""
    a = pd.read_parquet(PROCESSED / "predictions_test_a.parquet")
    b = pd.read_parquet(PROCESSED / "predictions_test_b.parquet")
    last_day = (pd.Timestamp(test[1]) - pd.Timedelta(days=1)).date().isoformat()
    return {
        "first_day": test[0], "last_day": last_day,
        "grid_period": [config.SPLITS["A"]["train"][0], last_day],
        "final_run": {"finished": marker["finished"], "commit": marker["commit"]},
        "selectable_lines": int(len(lines)),
        "departures_covered": int(lines["n_departures"].sum()), "departures_in_period": int(len(a)),
        "calibration": {
            "A": error_step.calibration_table(a["delayed"].to_numpy(), a["m_a"].to_numpy()).to_dict("records"),
            "B": error_step.calibration_table(b["delayed"].to_numpy(), b["m_b"].to_numpy()).to_dict("records"),
        },
    }


def main() -> None:
    marker = require_final_run()
    test = config.SPLITS["A"]["test"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    lines = build_lines(con, test)
    grid = build_grid(con, lines)
    filled = grid.groupby("label").size()
    lines = lines[lines["label"].map(filled).fillna(0) >= MIN_GRID_CELLS].reset_index(drop=True)
    grid = grid[grid["label"].isin(lines["label"])].reset_index(drop=True)
    tables = {
        "lines": lines,
        "profiles": build_profiles(con, lines, test),
        "days": build_days(con, test),
        "weather": build_weather(con, test),
        "history": build_history(con, test),
        "grid": grid,
    }
    for name, table in tables.items():
        table.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"dashboard/data/{name}.parquet: {len(table):,} rows, {(OUT / f'{name}.parquet').stat().st_size / 1e3:.0f} kB")
    meta = build_meta(marker, test, lines)
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(f"dashboard/data/meta.json: {meta['selectable_lines']} lines covering "
          f"{meta['departures_covered']:,} of {meta['departures_in_period']:,} test-period departures; "
          f"{int(lines['has_scenario_b'].sum())} lines with scenario B")


if __name__ == "__main__":
    main()
