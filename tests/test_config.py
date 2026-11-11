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


def test_month_range_covers_the_data_period():
    months = config.month_range()
    assert len(months) == 28
    assert months[0] == config.FIRST_MONTH and months[-1] == config.LAST_MONTH


def test_split_boundaries_are_month_starts_or_full_coverage_start():
    for scenario, parts in config.SPLITS.items():
        for part, bounds in parts.items():
            for bound in bounds:
                assert bound.endswith("-01") or bound == config.FULL_COVERAGE_START, (scenario, part, bound)


def test_scenario_b_validation_lies_inside_scenario_a_validation():
    # B models are tuned on rows that scenario A never trains on.
    a0, a1 = config.SPLITS["A"]["val"]
    b0, b1 = config.SPLITS["B"]["val"]
    assert a0 <= b0 < b1 <= a1


def test_pdf_export_takes_the_text_between_the_two_rules():
    import sys
    sys.path.insert(0, str(config.ROOT / "tools"))
    import export_pdf

    assert export_pdf.section_text("notes\n\n---\n\n## 3 Data\n\ntext\n\n---\n\n## Open points\n").strip() == "## 3 Data\n\ntext"
    assert export_pdf.section_text("# Sheet\n\nno rules here\n") == "# Sheet\n\nno rules here\n"
