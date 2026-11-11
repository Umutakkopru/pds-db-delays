"""
Tests of the enrichment step (src/03_enrich.py). Run with `pytest`.

Part 1 uses small made-up data and the tracked school holiday list.
Part 2 checks the real output in data/processed/ and is skipped when it is missing.

Reads:  reference/school_holidays_bavaria.csv; data/processed/weather_hourly.parquet,
        data/processed/calendar_daily.parquet (part 2)
Writes: nothing
"""
import importlib
from datetime import date

import pandas as pd
import pytest

import config

enrich = importlib.import_module("03_enrich")  # module name starts with a digit


# ----------------------------------------------------------------- weather: UTC to local time

def _raw(start_utc: str, hours: int, offset_seconds: int = 0) -> dict:
    times = pd.date_range(start_utc, periods=hours, freq="h")
    hourly = {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times]}
    for i, name in enumerate(config.WEATHER_VARIABLES):
        hourly[name] = [float(h + 100 * i) for h in range(hours)]   # value = hour index (+ offset per variable)
    return {"utc_offset_seconds": offset_seconds, "hourly": hourly}


def test_summer_time_is_two_hours_ahead_of_utc():
    local = enrich.weather_to_local_hours(_raw("2026-07-01 00:00", 3))
    assert list(local["local_hour"]) == list(pd.to_datetime(["2026-07-01 02:00", "2026-07-01 03:00", "2026-07-01 04:00"]))


def test_winter_time_is_one_hour_ahead_of_utc():
    local = enrich.weather_to_local_hours(_raw("2026-01-15 00:00", 2))
    assert list(local["local_hour"]) == list(pd.to_datetime(["2026-01-15 01:00", "2026-01-15 02:00"]))


def test_repeated_hour_in_autumn_is_averaged():
    # 25 Oct 2026: 00:00 and 01:00 UTC are both 02:00 local time.
    local = enrich.weather_to_local_hours(_raw("2026-10-24 23:00", 4))
    assert local["local_hour"].is_unique and len(local) == 3
    two = local.loc[local["local_hour"] == pd.Timestamp("2026-10-25 02:00"), "temperature_c"].iloc[0]
    assert two == pytest.approx((1 + 2) / 2)        # hour index 1 and 2 of the made-up series


def test_missing_hour_in_spring_has_no_row():
    # 29 Mar 2026: local time jumps from 01:59 to 03:00.
    local = enrich.weather_to_local_hours(_raw("2026-03-28 23:00", 4))
    hours = list(local["local_hour"])
    assert pd.Timestamp("2026-03-29 02:00") not in hours
    assert hours == list(pd.to_datetime(["2026-03-29 00:00", "2026-03-29 01:00", "2026-03-29 03:00", "2026-03-29 04:00"]))


def test_raw_weather_must_be_utc():
    with pytest.raises(ValueError):
        enrich.weather_to_local_hours(_raw("2026-07-01 00:00", 2, offset_seconds=3600))


# ----------------------------------------------------------------- calendar

def test_school_holiday_list_is_consistent():
    school = enrich.read_school_holidays()
    assert (school["first_day"] <= school["last_day"]).all()
    ordered = school.sort_values("first_day").reset_index(drop=True)
    assert (ordered["first_day"].iloc[1:].to_numpy() > ordered["last_day"].iloc[:-1].to_numpy()).all()   # no overlap
    assert ((school["last_day"] - school["first_day"]).dt.days <= 50).all()
    first, last = enrich.data_period()
    assert school["first_day"].min() <= pd.Timestamp(first) + pd.Timedelta(days=31)
    assert school["last_day"].max() >= pd.Timestamp(last)


def test_bridge_days():
    days = pd.date_range("2025-05-26", "2025-06-22", freq="D")
    public = {date(2025, 5, 29), date(2025, 6, 9), date(2025, 6, 17)}       # Thu, Mon, Tue
    found = enrich.bridge_days(days, public)
    assert found == {date(2025, 5, 30), date(2025, 6, 16)}                   # Fri after Thu; Mon before Tue


def test_calendar_known_days():
    cal = enrich.build_calendar(date(2025, 1, 1), date(2025, 12, 31), enrich.read_school_holidays()).set_index("service_date")
    assert len(cal) == 365
    assert cal.loc[date(2025, 12, 25), "is_public_holiday"]
    assert cal.loc[date(2025, 8, 15), "is_public_holiday"]                   # Mariä Himmelfahrt (Würzburg observes it)
    assert not cal.loc[date(2025, 8, 14), "is_public_holiday"]
    assert cal.loc[date(2025, 5, 30), "is_bridge_day"] and not cal.loc[date(2025, 5, 30), "is_public_holiday"]
    assert cal.loc[date(2025, 8, 10), "is_school_holiday"] and cal.loc[date(2025, 8, 10), "school_holiday_name"] == "Sommerferien"
    assert cal.loc[date(2025, 4, 14), "is_school_holiday"] and cal.loc[date(2025, 4, 25), "is_school_holiday"]   # both ends inclusive
    assert not cal.loc[date(2025, 4, 26), "is_school_holiday"]
    assert not cal.loc[date(2025, 2, 3), "is_school_holiday"]


# ----------------------------------------------------------------- real output

needs_output = pytest.mark.skipif(
    not (enrich.WEATHER_FILE.exists() and enrich.CALENDAR_FILE.exists()), reason="run src/03_enrich.py first")


@needs_output
def test_output_calendar_covers_every_day_once():
    cal = pd.read_parquet(enrich.CALENDAR_FILE)
    first, last = enrich.data_period()
    assert list(cal["service_date"]) == list(pd.date_range(first, last, freq="D").date)


@needs_output
def test_output_weather_covers_every_local_hour():
    weather = pd.read_parquet(enrich.WEATHER_FILE)
    first, last = enrich.data_period()
    assert weather["local_hour"].is_unique
    expected = pd.date_range(first, pd.Timestamp(last) + pd.Timedelta(hours=23), freq="h")
    missing = expected.difference(pd.DatetimeIndex(weather["local_hour"]))
    # only the hours that do not exist when clocks go forward may be missing
    spring_gaps = {pd.Timestamp(d) + pd.Timedelta(hours=2) for d in config.dst_change_days() if d.month == 3}
    assert set(missing) == spring_gaps
    assert not weather.drop(columns="local_hour").isna().any().any()
    assert weather["temperature_c"].between(-30, 45).all() and (weather["precipitation_mm"] >= 0).all()


@needs_output
def test_output_every_modelling_departure_gets_weather_and_calendar():
    clean = config.DATA_PROCESSED / "wuerzburg_clean.parquet"
    if not clean.exists():
        pytest.skip("run src/02_clean.py first")
    import duckdb
    n, no_weather, no_calendar = duckdb.sql(f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE w.local_hour IS NULL), COUNT(*) FILTER (WHERE c.service_date IS NULL)
        FROM read_parquet('{clean}') d
        LEFT JOIN read_parquet('{enrich.WEATHER_FILE}') w ON w.local_hour = date_trunc('hour', d.departure_planned_time)
        LEFT JOIN read_parquet('{enrich.CALENDAR_FILE}') c ON c.service_date = d.service_date
        WHERE d.exclude_reason IS NULL
    """).fetchone()
    assert n > 0 and no_weather == 0 and no_calendar == 0
