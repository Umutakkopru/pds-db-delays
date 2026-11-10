"""
Tests of the cleaning step (src/02_clean.py, src/sql/02_clean.sql). Run with `pytest`.

Part 1 runs the cleaning SQL on a small hand-made month and checks every rule.
Part 2 checks the real output in data/processed/ and is skipped when it is missing.

Reads:  data/processed/wuerzburg_clean.parquet, reports/checks/cleaning_counts.csv (part 2)
Writes: nothing in the repository
"""
import importlib

import duckdb
import pandas as pd
import pytest

import config

clean_step = importlib.import_module("02_clean")  # module name starts with a digit

REASONS = {"bus", "no_plan_record", "canceled", "dst_night", "invalid_delay", "duplicate_id"}


# ----------------------------------------------------------------- part 1: fixture

def _dep(id_, planned, delay, train_type="RE", line="10", number="1", **extra):
    """One Würzburg row with a planned departure; `delay` in minutes."""
    planned = pd.Timestamp(planned)
    row = {
        "id": id_, "row_role": "wuerzburg", "source_month": planned.strftime("%Y-%m"), "wuerzburg_id": id_,
        "train_type": train_type, "train_number": number, "line_number": line,
        "has_plan_record": True, "departure_is_canceled": False,
        "arrival_planned_time": pd.NaT, "arrival_change_time": pd.NaT,
        "departure_planned_time": planned, "departure_change_time": planned + pd.Timedelta(minutes=delay),
    }
    row.update(extra)
    return row


def _stop(id_, wuerzburg_id, planned, canceled=False):
    planned = pd.Timestamp(planned)
    return {
        "id": id_, "row_role": "earlier_stop", "source_month": planned.strftime("%Y-%m"), "wuerzburg_id": wuerzburg_id,
        "train_type": "ICE", "train_number": "500", "line_number": None,
        "has_plan_record": True, "departure_is_canceled": canceled,
        "arrival_planned_time": pd.NaT, "arrival_change_time": pd.NaT,
        "departure_planned_time": planned, "departure_change_time": planned,
    }


@pytest.fixture(scope="module")
def cleaned(tmp_path_factory):
    folder = tmp_path_factory.mktemp("clean")
    arr = {"arrival_planned_time": pd.Timestamp("2026-08-03 09:55"), "arrival_change_time": pd.Timestamp("2026-08-03 09:55")}
    rows = [
        _dep("late7", "2025-06-02 08:00", 7),                                   # digit-only line, RE
        _dep("late6", "2025-06-02 09:00", 6, train_type="NJ", line=None),       # exactly at the threshold
        _dep("late5", "2025-06-02 10:00", 5, train_type="RB", line="RE10"),     # type RB, line prefix RE
        _dep("space", "2025-06-02 11:00", 0, line="RE 80"),
        _dep("arv_digits", "2026-08-03 08:00", 0, train_type="ARV", line="8", number="77"),
        _dep("arv_named", "2026-08-04 08:00", 0, train_type="ARV", line="RB8", number="77"),
        _dep("arv_unknown", "2026-08-03 08:30", 0, train_type="ARV", line="80", number="78"),
        _dep("bus", "2025-06-02 12:00", 0, train_type="Bus", line="EV"),
        _dep("no_plan", "2025-06-02 13:00", 30, has_plan_record=False, departure_is_canceled=True),
        _dep("canceled", "2025-06-02 14:00", 0, departure_is_canceled=True),
        _dep("dst", "2026-03-29 03:30", 0),
        _dep("dst_day_later_hour", "2026-03-29 05:00", 0),
        _dep("invalid", "2025-06-02 15:00", -59),
        _dep("early", "2025-06-02 16:00", -3),
        _dep("through", "2026-08-03 10:00", 0, train_type="ICE", line=None, number="500", **arr),
        _dep("through_no_stop", "2026-08-03 10:00", 0, train_type="ICE", line=None, number="501", **arr),
        _dep("twice", "2025-06-30 23:50", 0),
        {**_dep("twice", "2025-06-30 23:50", 0), "source_month": "2025-07"},     # same id in the next file
        # a train that ends at Würzburg: no planned departure, not part of the target
        {**_dep("ends_here", "2025-06-02 17:00", 0), "departure_planned_time": pd.NaT, "departure_change_time": pd.NaT,
         "arrival_planned_time": pd.Timestamp("2025-06-02 17:00"), "arrival_change_time": pd.Timestamp("2025-06-02 17:00")},
        _stop("s1", "through", "2026-08-03 09:00"),
        _stop("s2", "through_no_stop", "2026-08-03 09:00", canceled=True),
    ]
    pd.DataFrame(rows).to_parquet(folder / "wuerzburg_2026-01.parquet")
    con = duckdb.connect()
    clean_step.clean(con, str(folder / "wuerzburg_*.parquet"), folder / "clean.parquet", folder / "prev.parquet")
    return pd.read_parquet(folder / "clean.parquet"), pd.read_parquet(folder / "prev.parquet")


def _one(df, id_):
    rows = df[df["id"] == id_]
    assert len(rows) == 1, id_
    return rows.iloc[0]


def test_only_planned_departures_and_no_row_deleted(cleaned):
    df, _ = cleaned
    assert "ends_here" not in set(df["id"])
    assert len(df) == 18  # every planned departure of the fixture, including the duplicate


def test_target_threshold(cleaned):
    df, _ = cleaned
    assert _one(df, "late7")["delayed"] == 1
    assert _one(df, "late6")["delayed"] == 1
    assert _one(df, "late5")["delayed"] == 0
    assert _one(df, "early")["delayed"] == 0 and pd.isna(_one(df, "early")["exclude_reason"])


@pytest.mark.parametrize("id_, reason", [
    ("bus", "bus"), ("no_plan", "no_plan_record"), ("canceled", "canceled"),
    ("dst", "dst_night"), ("invalid", "invalid_delay"),
])
def test_exclude_reasons(cleaned, id_, reason):
    df, _ = cleaned
    assert _one(df, id_)["exclude_reason"] == reason


def test_dst_rule_covers_only_the_night_hours(cleaned):
    df, _ = cleaned
    assert pd.isna(_one(df, "dst_day_later_hour")["exclude_reason"])


def test_duplicate_id_keeps_the_first_copy(cleaned):
    df, _ = cleaned
    twice = df[df["id"] == "twice"].sort_values("source_month")
    assert list(twice["exclude_reason"].fillna("")) == ["", "duplicate_id"]


@pytest.mark.parametrize("id_, line_id, service", [
    ("late7", "RE10", "regional"),         # digit-only line gets the train type
    ("late5", "RE10", "regional"),         # line prefix wins over the train type
    ("space", "RE80", "regional"),
    ("arv_digits", "RB8", "regional"),     # usual line of the same train number
    ("arv_unknown", "RE80", "regional"),   # no other row of that train number
    ("late6", None, "night"),
    ("through", None, "long_distance"),
])
def test_line_id_and_service(cleaned, id_, line_id, service):
    df, _ = cleaned
    row = _one(df, id_)
    assert row["service"] == service
    assert (row["line_id"] == line_id) if line_id else pd.isna(row["line_id"])


def test_through_and_previous_stop_flags(cleaned):
    df, prev = cleaned
    assert _one(df, "through")["is_through"] and _one(df, "through")["has_prev_stop"]
    # an earlier stop that was cancelled does not count
    assert _one(df, "through_no_stop")["is_through"] and not _one(df, "through_no_stop")["has_prev_stop"]
    assert not _one(df, "late7")["is_through"] and not _one(df, "late7")["has_prev_stop"]
    assert sorted(prev["id"]) == ["s1", "s2"]


def test_splits(cleaned):
    df, _ = cleaned
    assert _one(df, "late7")["split_a"] == "train" and pd.isna(_one(df, "late7")["split_b"])
    assert _one(df, "through")["split_a"] == "test" and _one(df, "through")["split_b"] == "test"
    assert _one(df, "dst")["split_a"] == "val" and _one(df, "dst")["split_b"] == "train"


# ----------------------------------------------------------------- part 2: real output

needs_output = pytest.mark.skipif(not clean_step.CLEAN_FILE.exists(), reason="run src/02_clean.py first")


def _q(sql: str) -> pd.DataFrame:
    return duckdb.sql(sql.format(f=f"read_parquet('{str(clean_step.CLEAN_FILE)}')")).df()


@needs_output
def test_output_ids_unique_among_modelling_rows():
    n, ids = _q("SELECT COUNT(*) AS n, COUNT(DISTINCT id) AS ids FROM {f} WHERE exclude_reason IS NULL").iloc[0]
    assert n == ids


@needs_output
def test_output_modelling_rows_follow_the_rules():
    bad = _q(f"""
        SELECT COUNT(*) FILTER (WHERE train_type = 'Bus')              AS bus,
               COUNT(*) FILTER (WHERE canceled)                        AS canceled,
               COUNT(*) FILTER (WHERE NOT has_plan_record)             AS no_plan,
               COUNT(*) FILTER (WHERE dep_delay IS NULL OR dep_delay < {config.INVALID_DELAY_BELOW_MIN}) AS invalid,
               COUNT(*) FILTER (WHERE departure_planned_time IS NULL)  AS no_departure,
               COUNT(*) FILTER (WHERE delayed <> CAST(dep_delay >= {config.DELAY_THRESHOLD_MIN} AS INTEGER)) AS wrong_target,
               COUNT(*) FILTER (WHERE service = 'regional' AND line_id IS NULL) AS regional_without_line
        FROM {{f}} WHERE exclude_reason IS NULL
    """).iloc[0]
    assert bad.sum() == 0, bad.to_dict()


@needs_output
def test_output_no_modelling_row_in_a_dst_night():
    days = ", ".join(f"DATE '{d.isoformat()}'" for d in config.dst_change_days())
    lo, hi = config.DST_EXCLUDE_HOURS
    n = _q(f"""SELECT COUNT(*) AS n FROM {{f}} WHERE exclude_reason IS NULL AND service_date IN ({days})
               AND hour(departure_planned_time) >= {lo} AND hour(departure_planned_time) < {hi}""").iloc[0, 0]
    assert n == 0


@needs_output
def test_output_reasons_and_counts_file():
    reasons = set(_q("SELECT DISTINCT exclude_reason FROM {f} WHERE exclude_reason IS NOT NULL")["exclude_reason"])
    assert reasons <= REASONS
    counts = pd.read_csv(config.CHECKS / "cleaning_counts.csv")
    assert counts["n_rows"].sum() == _q("SELECT COUNT(*) AS n FROM {f}").iloc[0, 0]
    # no delay rate of the test period is written before the final run
    assert counts.loc[counts["split_a"] == "test", "pct_delayed"].isna().all()


@needs_output
def test_output_line_ids_are_stable_over_the_format_change():
    # every regional line with many departures before Dec 2025 still exists after (RE57 was withdrawn)
    df = _q("""
        SELECT line_id,
               COUNT(*) FILTER (WHERE departure_planned_time <  TIMESTAMP '2025-12-01') AS before,
               COUNT(*) FILTER (WHERE departure_planned_time >= TIMESTAMP '2025-12-01') AS after
        FROM {f} WHERE exclude_reason IS NULL AND service = 'regional' GROUP BY 1
    """)
    assert df["line_id"].str.fullmatch(r"(RE|RB)\d{1,2}").all(), sorted(df["line_id"])
    lost = df[(df["before"] > 1000) & (df["after"] == 0)]
    assert lost.empty, lost
