"""
Leakage and consistency tests of the feature step (src/04_features.py). Run with `pytest`.

Part 1 builds features from small made-up tables and checks the history window,
the time-travel property and the choice of the previous stop by hand.
Part 2 checks the real feature tables and is skipped when they are missing.

Reads:  data/processed/*.parquet (part 2)
Writes: nothing in the repository
"""
import importlib
from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

import config
import features_config

feat = importlib.import_module("04_features")  # module name starts with a digit

HISTORY = features_config.HISTORY_FEATURES


# ----------------------------------------------------------------- part 1: made-up data

def _departures(start: date, days: int, per_day: int, delayed_on=lambda d, k: 0) -> pd.DataFrame:
    """`per_day` regional departures at 08:00 on each of `days` days; delayed_on(day_index, k) gives the label."""
    rows = []
    for i in range(days):
        day = start + timedelta(days=i)
        for k in range(per_day):
            planned = pd.Timestamp(day) + pd.Timedelta(hours=8, minutes=k)
            rows.append({
                "id": f"{day}-{k}", "service_date": day, "departure_planned_time": planned,
                "arrival_planned_time": planned - pd.Timedelta(minutes=10), "split_a": "train", "split_b": "train",
                "delayed": int(delayed_on(i, k)), "service": "regional", "line_id": "RB53",
                "final_destination_station": "X", "is_through": True, "has_prev_stop": True,
                "train_line_station_num": 5, "exclude_reason": None,
            })
    return pd.DataFrame(rows)


def _build_a(con, clean: pd.DataFrame) -> pd.DataFrame:
    con.register("clean_t", clean)
    hours = pd.date_range(clean["departure_planned_time"].min().floor("h"), clean["departure_planned_time"].max().ceil("h"), freq="h")
    weather = pd.DataFrame({"local_hour": hours, **{c: 0.0 for c in config.WEATHER_VARIABLES.values()}})
    calendar = pd.DataFrame({"service_date": sorted(clean["service_date"].unique()),
                             "is_public_holiday": False, "is_school_holiday": False, "is_bridge_day": False})
    con.register("weather_t", weather)
    con.register("calendar_t", calendar)
    return con.sql(feat.features_a_sql("clean_t", "weather_t", "calendar_t")).df()


def test_history_window_by_hand():
    # 40 days, 10 departures a day; departure k of day i is delayed when k < i % 4.
    start = date(2026, 1, 1)
    clean = _departures(start, 40, 10, delayed_on=lambda i, k: k < i % 4)
    out = _build_a(duckdb.connect(), clean)
    day_index = 35
    row = out[out["service_date"] == pd.Timestamp(start + timedelta(days=day_index))].iloc[0]
    window = range(day_index - config.HISTORY_FIRST_DAY_BACK, day_index - config.HISTORY_LAST_DAY_BACK + 1)
    expected = sum(i % 4 for i in window) / (10 * len(window))
    assert len(window) == 28
    assert row["hist_rate_route"] == pytest.approx(expected)
    assert row["hist_rate_service_hour"] == pytest.approx(expected)
    assert row["hist_rate_all"] == pytest.approx(expected)
    assert row["hist_n_route"] == 10 * len(window)


def test_time_travel_later_labels_do_not_change_history():
    # Features of day D must not change when every label from D - 1 on is changed.
    start = date(2026, 1, 1)
    clean = _departures(start, 40, 10, delayed_on=lambda i, k: (i * 7 + k) % 3 == 0)
    target = start + timedelta(days=35)
    changed = clean.copy()
    late = changed["service_date"] >= target - timedelta(days=1)
    changed.loc[late, "delayed"] = 1 - changed.loc[late, "delayed"]
    a = _build_a(duckdb.connect(), clean)
    b = _build_a(duckdb.connect(), changed)
    pick = lambda df: df[df["service_date"] == pd.Timestamp(target)].sort_values("id")[HISTORY].reset_index(drop=True)
    pd.testing.assert_frame_equal(pick(a), pick(b))


def test_labels_two_days_before_do_change_history():
    # The counterpart: the last day inside the window (D - 2) must matter, otherwise the test above proves nothing.
    start = date(2026, 1, 1)
    clean = _departures(start, 40, 10)
    target = start + timedelta(days=35)
    changed = clean.copy()
    changed.loc[changed["service_date"] == target - timedelta(days=2), "delayed"] = 1
    a = _build_a(duckdb.connect(), clean)
    b = _build_a(duckdb.connect(), changed)
    rate = lambda df: df.loc[df["service_date"] == pd.Timestamp(target), "hist_rate_route"].iloc[0]
    assert rate(a) == 0 and rate(b) == pytest.approx(10 / 280)


def test_history_is_missing_when_the_window_is_too_small():
    clean = _departures(date(2026, 1, 1), 6, 3)     # at most 4 days x 3 rows = 12 < MIN_HISTORY_ROWS
    out = _build_a(duckdb.connect(), clean)
    assert config.MIN_HISTORY_ROWS > 12
    assert out["hist_rate_route"].isna().all() and out["hist_rate_all"].isna().all()


def test_excluded_rows_do_not_feed_history():
    start = date(2026, 1, 1)
    clean = _departures(start, 40, 10)
    extra = _departures(start, 40, 10, delayed_on=lambda i, k: 1)
    extra["id"] = "x" + extra["id"]
    extra["exclude_reason"] = "canceled"
    out = _build_a(duckdb.connect(), pd.concat([clean, extra], ignore_index=True))
    assert len(out) == len(clean)
    assert out["hist_rate_route"].dropna().eq(0).all()


def test_previous_stop_is_the_last_usable_stop_before_wuerzburg():
    con = duckdb.connect()
    clean = _departures(date(2026, 1, 1), 1, 1)
    a = _build_a(con, clean)
    con.register("features_a_t", a)
    wid = clean["id"].iloc[0]
    dep = clean["departure_planned_time"].iloc[0]
    stop = lambda id_, minutes_before, delay, num, canceled=False: {
        "id": id_, "wuerzburg_id": wid, "stop_delay": delay, "stop_canceled": canceled, "train_line_station_num": num,
        "departure_planned_time": dep - pd.Timedelta(minutes=minutes_before), "arrival_planned_time": pd.NaT}
    prev = pd.DataFrame([
        stop("far", 60, 2.0, 1),
        stop("middle", 40, 9.0, 2),
        stop("near", 25, 4.0, 3),
        stop("nearest_but_canceled", 15, 30.0, 4, canceled=True),     # must be skipped
    ])
    con.register("prev_t", prev)
    b = con.sql(feat.features_b_sql("features_a_t", "clean_t", "prev_t")).df()
    assert len(b) == 1
    row = b.iloc[0]
    assert row["prev_delay"] == 4.0 and row["prev_delay_2"] == 9.0
    assert row["prev_minutes_to_departure"] == 25
    assert row["prev_stops_between"] == 5 - 3 - 1


# ----------------------------------------------------------------- part 2: real tables

needs_output = pytest.mark.skipif(not (feat.FEATURES_A.exists() and feat.FEATURES_B.exists()),
                                  reason="run src/04_features.py first")
CLEAN = config.DATA_PROCESSED / "wuerzburg_clean.parquet"


@pytest.fixture(scope="module")
def table_a():
    return pd.read_parquet(feat.FEATURES_A)


@pytest.fixture(scope="module")
def table_b():
    return pd.read_parquet(feat.FEATURES_B)


@needs_output
@pytest.mark.parametrize("scenario", ["A", "B"])
def test_tables_have_exactly_the_whitelisted_columns(scenario, table_a, table_b):
    table = {"A": table_a, "B": table_b}[scenario]
    assert list(table.columns) == features_config.META_COLUMNS + features_config.FEATURES[scenario]
    assert not (set(table.columns) & features_config.FORBIDDEN_COLUMNS - set(features_config.META_COLUMNS))


@needs_output
def test_scenario_a_rows_are_the_modelling_rows(table_a):
    n = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('{CLEAN}') WHERE exclude_reason IS NULL").fetchone()[0]
    assert len(table_a) == n and table_a["id"].is_unique


@needs_output
def test_scenario_b_rows_are_through_trains_with_an_earlier_stop(table_a, table_b):
    n = duckdb.sql(f"""SELECT COUNT(*) FROM read_parquet('{CLEAN}')
                       WHERE exclude_reason IS NULL AND is_through AND has_prev_stop AND split_b IS NOT NULL""").fetchone()[0]
    assert len(table_b) == n and table_b["id"].is_unique
    assert table_b["is_through"].all() and table_b["split_b"].notna().all()
    # scenario B rows carry exactly the scenario A feature values (same rows for M-A', M-B and B3)
    merged = table_b.merge(table_a, on="id", suffixes=("", "_a"))
    assert len(merged) == len(table_b)
    for column in features_config.FEATURES["A"]:
        left, right = merged[column], merged[column + "_a"]
        assert ((left == right) | (left.isna() & right.isna())).all(), column


@needs_output
@pytest.mark.parametrize("scenario, column", [("A", "split_a"), ("B", "split_b")])
def test_no_row_in_two_splits_and_splits_are_in_time_order(scenario, column, table_a, table_b):
    table = {"A": table_a, "B": table_b}[scenario].dropna(subset=[column])
    spans = table.groupby(column)["departure_planned_time"].agg(["min", "max"])
    assert spans.loc["train", "max"] < spans.loc["val", "min"] < spans.loc["val", "max"] < spans.loc["test", "min"]
    for name, (start, end) in config.SPLITS[scenario].items():
        assert spans.loc[name, "min"] >= pd.Timestamp(start) and spans.loc[name, "max"] < pd.Timestamp(end)


@needs_output
def test_previous_stop_lies_before_the_wuerzburg_arrival(table_b):
    # minutes from the previous stop to the Würzburg departure must exceed the planned stop time at Würzburg
    assert (table_b["prev_minutes_to_departure"] > table_b["dwell_min"]).all()
    assert (table_b["prev_stops_between"].dropna() >= 0).all()
    assert table_b["prev_delay"].notna().all()


@needs_output
def test_weather_and_calendar_are_never_missing(table_a):
    columns = features_config.WEATHER_FEATURES + features_config.CALENDAR_FEATURES
    assert not table_a[columns].isna().any().any()


@needs_output
@pytest.mark.parametrize("target", ["2025-03-12", "2026-02-02", "2026-06-20"])   # training and validation days only
def test_time_travel_on_real_data(target, table_a):
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW changed AS
        SELECT * REPLACE (CASE WHEN service_date >= DATE '{target}' - INTERVAL 1 DAY THEN 1 - delayed ELSE delayed END AS delayed)
        FROM read_parquet('{CLEAN}')
    """)
    sql = feat.features_a_sql("changed", feat.parquet(config.DATA_PROCESSED / "weather_hourly.parquet"),
                              feat.parquet(config.DATA_PROCESSED / "calendar_daily.parquet"))
    again = con.sql(f"SELECT id, {', '.join(HISTORY)} FROM ({sql}) WHERE service_date = DATE '{target}'").df()
    stored = table_a.loc[table_a["service_date"] == pd.Timestamp(target).date(), ["id"] + HISTORY]
    merged = stored.merge(again, on="id", suffixes=("", "_again"))
    assert len(merged) == len(stored) > 100
    for column in HISTORY:
        np.testing.assert_allclose(merged[column], merged[column + "_again"], equal_nan=True)


@needs_output
def test_no_single_scenario_a_feature_is_suspiciously_strong(table_a):
    # Sanity check: each single feature clearly below ROC-AUC 0.9 (validation).
    train = table_a[table_a["split_a"] == "train"]
    val = table_a[table_a["split_a"] == "val"]
    scores = {}
    for name in features_config.FEATURES["A"]:
        if name in features_config.CATEGORICAL_FEATURES:
            rate = train.groupby(train[name].fillna("none"))["delayed"].mean()
            score = val[name].fillna("none").map(rate).fillna(train["delayed"].mean())
        else:
            score = val[name].astype(float).fillna(train[name].astype(float).median())
        auc = roc_auc_score(val["delayed"], score)
        scores[name] = max(auc, 1 - auc)
    print({k: round(v, 3) for k, v in sorted(scores.items(), key=lambda kv: -kv[1])})
    too_strong = {k: round(v, 3) for k, v in scores.items() if v >= 0.9}
    assert not too_strong, too_strong
