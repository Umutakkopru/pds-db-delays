"""
Feature whitelist per scenario and the list of forbidden columns.

Models may only use the columns listed in FEATURES[scenario]. The lists are
filled when src/04_features.py is written (week 3); tests/test_leakage.py
checks them against FORBIDDEN_COLUMNS on every run.

Reads:  nothing
Writes: nothing
"""

# Columns that contain (or are derived from) the outcome at Würzburg Hbf.
# They must never be used as features, in any scenario.
FORBIDDEN_COLUMNS = {
    "arrival_change_time",
    "departure_change_time",
    "delay_in_min",
    "dep_delay",
    "arr_delay",
    "delayed",
    "arrival_is_canceled",
    "departure_is_canceled",
    "canceled",
    # identifiers and raw timestamps: no predictive meaning, risk of memorising
    "id",
    "wuerzburg_id",
    "train_line_ride_id",
    "time",
    # high cardinality and may change at the December timetable change;
    # used only as a key for history rates (decision log D14)
    "train_number",
    # raw labels that change over time (ARV relabel and line-format change in
    # Dec 2025): models use `service` and `line_id` instead (decision log D7)
    "train_type",
    "line_number",
    # disruption flags filled from DB's change feed (known only once the
    # disruption happens): filters only, never features (decision log D16)
    "is_additional_stop",
    "is_replacement_train",
    "replaced_train_type",
    "replaced_train_number",
    "has_plan_record",
    # pipeline bookkeeping
    "source_month",
    "row_role",
    # added by src/02_clean.py: filters and split labels, never features
    # (has_prev_stop depends on what the archive contains, not on the train)
    "exclude_reason",
    "split_a",
    "split_b",
    "has_prev_stop",
    # the calendar date itself would let a model memorise single days;
    # features are derived from it (weekday, holiday, history window)
    "service_date",
}

# Raw columns of the archive that are not forbidden: they may be used to build
# features, splits or joins. Every raw column must be in exactly one of the two
# sets (tests/test_data.py), so a new upstream column cannot slip in unnoticed.
ALLOWED_RAW_INPUTS = {
    "station_name",
    "xml_station_name",
    "eva",
    "final_destination_station",
    "train_line_station_num",
    "arrival_planned_time",
    "departure_planned_time",
}

# Columns added by src/02_clean.py that may be used as features or to build them.
ALLOWED_DERIVED_INPUTS = {"service", "line_id", "is_through"}

# Naming rule: every feature built from earlier stops of the same trip starts
# with this prefix. tests/test_leakage.py uses it to keep such features out of
# scenario A.
PROPAGATION_PREFIX = "prev_"

# Columns of the logistic-regression baseline B2: timetable and calendar, all
# known the day before. The route group follows with step 04.
BASELINE_FEATURES = [
    "service", "line_id", "planned_hour", "weekday", "is_through",
    "is_public_holiday", "is_school_holiday", "is_bridge_day",
]

# Allowed feature columns per scenario (filled in week 3).
FEATURES: dict[str, list[str]] = {
    "A": [],
    "B": [],
}
