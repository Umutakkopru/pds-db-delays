"""
Checks of the shared configuration (time zone handling). Run with `pytest`.
"""
import config


def test_dst_change_days_in_data_period():
    # Europe/Berlin DST changes between Jul 2024 and Oct 2026
    expected = ["2024-10-27", "2025-03-30", "2025-10-26", "2026-03-29", "2026-10-25"]
    assert [d.isoformat() for d in config.dst_change_days()] == expected


def test_dst_window_is_a_night_window():
    start, end = config.DST_EXCLUDE_HOURS
    assert 0 <= start < end <= 6
