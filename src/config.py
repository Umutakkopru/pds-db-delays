"""
Shared configuration for the pipeline: paths, station, months, splits, seed.

Reads:  nothing
Writes: nothing (other scripts import these constants)
"""
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Repository root = parent of src/
ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
REFERENCE = ROOT / "reference"   # small tracked tables (school holidays)
SQL_DIR = ROOT / "src" / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
CHECKS = REPORTS / "checks"

STATION = "Würzburg Hbf"

# Step 03 (enrichment). Weather is requested for the station's location in UTC
# and converted to local time by us: with timezone=Europe/Berlin the Open-Meteo
# archive applies a fixed +1 h offset all year, which is one hour off in summer.
STATION_LATITUDE = 49.8018
STATION_LONGITUDE = 9.9358
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_VARIABLES = {            # Open-Meteo name -> our column name
    "temperature_2m": "temperature_c",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
    "wind_gusts_10m": "wind_gust_kmh",
    "snowfall": "snowfall_cm",
    "snow_depth": "snow_depth_m",
}
HOLIDAY_SUBDIVISION = "BY"       # Bavaria; Würzburg also observes Mariä Himmelfahrt (15 Aug)

# All timestamps in the archive are naive German local time (Europe/Berlin).
# We keep them as local time; weather is joined on local time as well.
TIMEZONE = "Europe/Berlin"

# On the nights of a DST change, durations between two naive local times can be
# off by 60 minutes. Departures planned in this local-time window on those
# nights are excluded from the target (a few dozen rows per night).
DST_EXCLUDE_HOURS = (0, 5)  # [00:00, 05:00) local time

# Target: a departure counts as delayed from this many minutes (decision log D2).
DELAY_THRESHOLD_MIN = 6

# Departure delays below this value are data errors (wrong date or hour in the
# change time) and are excluded as 'invalid_delay' (decision log D19).
INVALID_DELAY_BELOW_MIN = -30

# Cancellation handling: the main target excludes cancelled departures (DB's
# punctuality definition); a sensitivity check counts them as delayed.
CANCELED_AS_DELAYED_SENSITIVITY = True

HF_REPO = "piebro/deutsche-bahn-data"
HF_FOLDER = "monthly_processed_data"
# Commit of the Hugging Face dataset that all downloads use. The maintainer
# reprocesses past months from time to time (changelog 2026-05, -08, -09), so
# without a fixed revision two downloads can differ. Change it only together
# with a full re-run of the pipeline and the data checks.
HF_REVISION = "3830320ad81e2b96bc4bdf5bedfa61657a60ea0e"

FIRST_MONTH = "2024-07"
LAST_MONTH = "2026-10"

# All stations (incl. small earlier stops of RB/RE) are in the archive from
# 2 Nov 2025 (dataset changelog); 3 Nov 2025 is the first full day.
FULL_COVERAGE_START = "2025-11-03"

# History features (decision log D14, D22): for a departure on day D the delay
# rate is taken over the service dates D - 29 ... D - 2, i.e. [D - 29, D - 1 00:00).
# Scenario A is asked on D - 1, when that day is not complete yet.
HISTORY_FIRST_DAY_BACK = 29
HISTORY_LAST_DAY_BACK = 2
# A history rate is used only if its window holds at least this many departures.
MIN_HISTORY_ROWS = 20

SEED = 42

# Uncertainty: number of bootstrap resamples of whole days (decision log D13).
BOOTSTRAP_N = 1000

# Chronological splits as half-open intervals [start, end) on the planned
# departure time at Würzburg Hbf. Test period is identical for A and B.
SPLITS = {
    "A": {
        "train": ("2024-07-01", "2026-01-01"),
        "val": ("2026-01-01", "2026-07-01"),
        "test": ("2026-07-01", "2026-11-01"),
    },
    "B": {
        "train": (FULL_COVERAGE_START, "2026-05-01"),
        "val": ("2026-05-01", "2026-07-01"),
        "test": ("2026-07-01", "2026-11-01"),
    },
}


def month_range(first: str = FIRST_MONTH, last: str = LAST_MONTH) -> list[str]:
    """Return all months from first to last (inclusive) as 'YYYY-MM' strings."""
    y, m = map(int, first.split("-"))
    y_end, m_end = map(int, last.split("-"))
    months = []
    while (y, m) <= (y_end, m_end):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def dst_change_days(first: str = FIRST_MONTH, last: str = LAST_MONTH) -> list[date]:
    """Return the days in the data period on which Europe/Berlin changes its UTC offset."""
    tz = ZoneInfo(TIMEZONE)
    day = date.fromisoformat(first + "-01")
    y, m = map(int, last.split("-"))
    end = date(y + (m == 12), m % 12 + 1, 1)
    days = []
    while day < end:
        before = datetime(day.year, day.month, day.day, 0, tzinfo=tz).utcoffset()
        after = datetime(day.year, day.month, day.day, 12, tzinfo=tz).utcoffset()
        if before != after:
            days.append(day)
        day += timedelta(days=1)
    return days
