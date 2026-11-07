"""
Shared configuration for the pipeline: paths, station, months, splits, seed.

Reads:  nothing
Writes: nothing (other scripts import these constants)
"""
from pathlib import Path

# Repository root = parent of src/
ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "src" / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
CHECKS = REPORTS / "checks"

STATION = "Würzburg Hbf"

HF_REPO = "piebro/deutsche-bahn-data"
HF_FOLDER = "monthly_processed_data"

FIRST_MONTH = "2024-07"
LAST_MONTH = "2026-10"

# Date from which all stations (incl. small earlier stops of RB/RE) are in the archive.
FULL_COVERAGE_START = "2025-11-01"

SEED = 42

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
