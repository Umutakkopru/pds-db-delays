"""
Step 3: weather and calendar tables for the features.

Weather: hourly observed weather at Würzburg from the Open-Meteo archive
(reanalysis), downloaded once in UTC, stored as raw JSON and converted to naive
local time (Europe/Berlin), the time base of the whole project. In the hour
that occurs twice when clocks go back, the two values are averaged; the hour
that does not exist when clocks go forward has no row.
Calendar: one row per day with public holidays (Bavaria, `holidays` package,
including Mariä Himmelfahrt), school holidays (reference/school_holidays_bavaria.csv)
and bridge days.

Both tables are joined to the departures in step 04. Observed weather stands
in for a forecast in scenario A (stated limitation, CLAUDE.md leakage rule 5).

Reads:  Open-Meteo archive API (only if the raw file is missing)
        reference/school_holidays_bavaria.csv
Writes: data/raw/weather/open_meteo_wuerzburg_utc.json     (raw download, gitignored)
        data/processed/weather_hourly.parquet              (one row per local hour)
        data/processed/calendar_daily.parquet              (one row per day)
        reports/checks/enrichment_summary.csv

Usage: python src/03_enrich.py
"""
import json
from datetime import date, timedelta
from pathlib import Path

import holidays
import pandas as pd

import config

WEATHER_RAW = config.DATA_RAW / "weather" / "open_meteo_wuerzburg_utc.json"
WEATHER_FILE = config.DATA_PROCESSED / "weather_hourly.parquet"
CALENDAR_FILE = config.DATA_PROCESSED / "calendar_daily.parquet"
SCHOOL_HOLIDAYS = config.REFERENCE / "school_holidays_bavaria.csv"


def data_period() -> tuple[date, date]:
    """First and last calendar day of the data period (config.FIRST_MONTH .. LAST_MONTH)."""
    first = date.fromisoformat(config.FIRST_MONTH + "-01")
    last = (pd.Timestamp(config.LAST_MONTH + "-01") + pd.offsets.MonthEnd(1)).date()
    return first, last


# ----------------------------------------------------------------- weather

def download_weather(path: Path = WEATHER_RAW) -> dict:
    """Return the raw Open-Meteo response; download it once if the file is missing."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    import requests

    first, last = data_period()
    params = {
        "latitude": config.STATION_LATITUDE,
        "longitude": config.STATION_LONGITUDE,
        # one day more on each side so that every local hour of the period is covered
        "start_date": (first - timedelta(days=1)).isoformat(),
        "end_date": (last + timedelta(days=1)).isoformat(),
        "hourly": ",".join(config.WEATHER_VARIABLES),
        "timezone": "GMT",
    }
    print("  downloading weather from Open-Meteo ...")
    response = requests.get(config.WEATHER_URL, params=params, timeout=120)
    response.raise_for_status()
    raw = response.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw), encoding="utf-8")
    return raw


def weather_to_local_hours(raw: dict) -> pd.DataFrame:
    """Convert the UTC series to one row per naive local hour (Europe/Berlin)."""
    if raw.get("utc_offset_seconds") != 0:
        raise ValueError("The raw weather file must be in UTC (timezone=GMT).")
    hourly = pd.DataFrame(raw["hourly"]).rename(columns=config.WEATHER_VARIABLES)
    utc = pd.to_datetime(hourly.pop("time"), utc=True)
    hourly["local_hour"] = utc.dt.tz_convert(config.TIMEZONE).dt.tz_localize(None)
    # The hour repeated in autumn appears twice here: average its two values.
    out = hourly.groupby("local_hour", as_index=False).mean(numeric_only=True)
    return out.sort_values("local_hour").reset_index(drop=True)


# ----------------------------------------------------------------- calendar

def read_school_holidays(path: Path = SCHOOL_HOLIDAYS) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["first_day", "last_day"])
    if (df["first_day"] > df["last_day"]).any():
        raise ValueError("School holiday with first_day after last_day.")
    return df


def bridge_days(days: pd.DatetimeIndex, public_holidays: set) -> set:
    """Working days squeezed between a public holiday and a weekend (Fri after Thu, Mon before Tue)."""
    result = set()
    for day in days:
        d = day.date()
        if d in public_holidays:
            continue
        if d.weekday() == 4 and (d - timedelta(days=1)) in public_holidays:
            result.add(d)
        if d.weekday() == 0 and (d + timedelta(days=1)) in public_holidays:
            result.add(d)
    return result


def build_calendar(first: date, last: date, school: pd.DataFrame) -> pd.DataFrame:
    """One row per day: public holiday, school holiday, bridge day."""
    days = pd.date_range(first, last, freq="D")
    years = range(first.year, last.year + 1)
    public = holidays.Germany(subdiv=config.HOLIDAY_SUBDIVISION, years=years, categories=("public", "catholic"))
    public_days = set(public.keys())

    school_name = pd.Series(pd.NA, index=days, dtype="string")
    for row in school.itertuples(index=False):
        school_name[(days >= row.first_day) & (days <= row.last_day)] = row.holiday

    bridges = bridge_days(days, public_days)
    return pd.DataFrame({
        "service_date": days.date,
        "is_public_holiday": [d.date() in public_days for d in days],
        "public_holiday_name": pd.array([public.get(d.date()) for d in days], dtype="string"),
        "is_school_holiday": school_name.notna().to_numpy(),
        "school_holiday_name": school_name.to_numpy(),
        "is_bridge_day": [d.date() in bridges for d in days],
    })


# ----------------------------------------------------------------- main

def main() -> None:
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    first, last = data_period()

    weather = weather_to_local_hours(download_weather())
    in_period = (weather["local_hour"] >= pd.Timestamp(first)) & (weather["local_hour"] < pd.Timestamp(last) + pd.Timedelta(days=1))
    weather = weather[in_period].reset_index(drop=True)
    weather.to_parquet(WEATHER_FILE, index=False)

    calendar = build_calendar(first, last, read_school_holidays())
    calendar.to_parquet(CALENDAR_FILE, index=False)

    expected_hours = len(pd.date_range(first, pd.Timestamp(last) + pd.Timedelta(hours=23), freq="h"))
    summary = pd.DataFrame([
        ("calendar days", len(calendar)),
        ("public holidays", int(calendar["is_public_holiday"].sum())),
        ("school holiday days", int(calendar["is_school_holiday"].sum())),
        ("bridge days", int(calendar["is_bridge_day"].sum())),
        ("weather local hours", len(weather)),
        ("local hours without weather (clock goes forward)", expected_hours - len(weather)),
        ("weather values missing", int(weather.drop(columns="local_hour").isna().sum().sum())),
        ("temperature min (C)", round(float(weather["temperature_c"].min()), 1)),
        ("temperature max (C)", round(float(weather["temperature_c"].max()), 1)),
        ("hours with precipitation > 0", int((weather["precipitation_mm"] > 0).sum())),
        ("hours with snowfall > 0", int((weather["snowfall_cm"] > 0).sum())),
        ("wind gust max (km/h)", round(float(weather["wind_gust_kmh"].max()), 1)),
    ], columns=["quantity", "value"])
    summary["value"] = summary["value"].map(lambda v: f"{v:g}")
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    summary.to_csv(config.CHECKS / "enrichment_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\nPublic holidays and bridge days:")
    special = calendar[calendar["is_public_holiday"] | calendar["is_bridge_day"]]
    print(special[["service_date", "public_holiday_name", "is_bridge_day"]].to_string(index=False))
    print(f"\nSaved: {WEATHER_FILE}\n       {CALENDAR_FILE}")


if __name__ == "__main__":
    main()
