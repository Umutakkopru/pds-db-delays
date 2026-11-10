"""
Tests of src/sql/01_filter_month.sql on a tiny hand-made month. Run with `pytest`.

Reads:  nothing from data/ (builds a small Parquet file in a temporary folder)
Writes: nothing in the repository
"""
import importlib

import duckdb
import pandas as pd
import pytest

import config

download = importlib.import_module("01_download")  # module name starts with a digit

T = pd.Timestamp


def _row(id_, station, num, arr, dep, ride="R1"):
    return {
        "id": id_,
        "station_name": station,
        "train_line_ride_id": ride,
        "train_line_station_num": num,
        "arrival_planned_time": T(arr) if arr else pd.NaT,
        "departure_planned_time": T(dep) if dep else pd.NaT,
    }


@pytest.fixture(scope="module")
def filtered(tmp_path_factory):
    folder = tmp_path_factory.mktemp("filter")
    rows = [
        # Day 1: the trip reaches Würzburg just after midnight.
        _row("too_early", "A-Stadt", 1, None, "2026-01-01 11:00"),               # 13 h 20 min before: outside the window
        _row("before_midnight", "B-Dorf", 3, "2026-01-01 23:38", "2026-01-01 23:40"),
        _row("w_day1", config.STATION, 5, "2026-01-02 00:20", "2026-01-02 00:25"),
        _row("after_wuerzburg", "C-Heim", 7, "2026-01-02 01:00", "2026-01-02 01:02"),
        # Day 2: the same ride id runs again (ride ids repeat every day).
        _row("day2_stop", "B-Dorf", 3, "2026-01-02 23:38", "2026-01-02 23:40"),
        _row("w_day2", config.STATION, 5, "2026-01-03 00:20", "2026-01-03 00:25"),
        # A train that starts at Würzburg (no arrival) on another ride.
        _row("other_stop", "D-Burg", 1, None, "2026-01-05 07:00", ride="R2"),
        _row("w_start", config.STATION, 2, None, "2026-01-05 08:00", ride="R2"),
        # A second Würzburg row of ride R1 with a lower stop number, shortly before w_day1.
        _row("w_twice", config.STATION, 2, "2026-01-01 23:50", "2026-01-01 23:52"),
    ]
    raw = folder / "raw.parquet"
    pd.DataFrame(rows).to_parquet(raw)
    out = folder / "out.parquet"
    con = duckdb.connect()
    download.filter_month(con, raw, out, "2026-01")
    return pd.read_parquet(out)


def _earlier_stops(df, wuerzburg_id):
    sel = df[(df["row_role"] == "earlier_stop") & (df["wuerzburg_id"] == wuerzburg_id)]
    return sorted(sel["id"])


def test_every_wuerzburg_row_is_kept_once(filtered):
    w = filtered[filtered["row_role"] == "wuerzburg"]
    assert sorted(w["id"]) == ["w_day1", "w_day2", "w_start", "w_twice"]
    assert (w["id"] == w["wuerzburg_id"]).all()
    assert (filtered["source_month"] == "2026-01").all()


def test_trip_across_midnight_keeps_its_earlier_stop(filtered):
    assert _earlier_stops(filtered, "w_day1") == ["before_midnight"]


def test_stops_outside_the_12_hour_window_or_after_wuerzburg_are_dropped(filtered):
    ids = set(filtered["id"])
    assert "too_early" not in ids
    assert "after_wuerzburg" not in ids


def test_same_ride_id_on_two_days_is_not_mixed(filtered):
    assert _earlier_stops(filtered, "w_day2") == ["day2_stop"]


def test_train_starting_at_wuerzburg_has_no_earlier_stops(filtered):
    assert _earlier_stops(filtered, "w_start") == []
    assert "other_stop" not in set(filtered["id"])


def test_wuerzburg_is_never_an_earlier_stop(filtered):
    earlier = filtered[filtered["row_role"] == "earlier_stop"]
    assert (earlier["station_name"] != config.STATION).all()
