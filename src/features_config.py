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
}

# Allowed feature columns per scenario (filled in week 3).
FEATURES: dict[str, list[str]] = {
    "A": [],
    "B": [],
}
