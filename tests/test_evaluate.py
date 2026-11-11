"""
Tests of the shared evaluation code and the baselines. Run with `pytest`.

Reads:  nothing from data/ (small made-up data)
Writes: nothing
"""
import importlib

import numpy as np
import pandas as pd
import pytest

import baselines
import evaluate
import features_config

train_step = importlib.import_module("05_train")  # module name starts with a digit


# ----------------------------------------------------------------- metrics

def test_perfect_and_reversed_scores():
    y = np.array([0, 0, 1, 1])
    assert evaluate.score_metrics(y, np.array([0.1, 0.2, 0.8, 0.9]))["roc_auc"] == 1.0
    assert evaluate.score_metrics(y, np.array([0.1, 0.2, 0.8, 0.9]))["pr_auc"] == 1.0
    assert evaluate.score_metrics(y, np.array([0.9, 0.8, 0.2, 0.1]))["roc_auc"] == 0.0
    assert evaluate.score_metrics(y, np.array([0.0, 0.0, 1.0, 1.0]))["brier"] == 0.0


def test_class_metrics_by_hand():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.2, 0.7, 0.1, 0.1, 0.1, 0.1])
    m = evaluate.class_metrics(y, s, threshold=0.5)   # predicted delayed: rows 0, 1, 3
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["accuracy"] == pytest.approx(6 / 8)


def test_class_metrics_without_positive_predictions():
    m = evaluate.class_metrics(np.array([0, 1]), np.array([0.1, 0.2]), threshold=0.5)
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0


def test_best_f1_threshold_is_the_best_of_all_thresholds():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 300)
    s = np.clip(0.3 * y + rng.normal(0.4, 0.2, 300), 0, 1)
    best = evaluate.best_f1_threshold(y, s)
    f1_best = evaluate.class_metrics(y, s, best)["f1"]
    assert all(f1_best >= evaluate.class_metrics(y, s, t)["f1"] - 1e-12 for t in np.unique(s))


# ----------------------------------------------------------------- bootstrap

def _toy(n_days=40, per_day=25, seed=1):
    rng = np.random.default_rng(seed)
    days = np.repeat(np.arange(n_days), per_day)
    y = rng.integers(0, 2, n_days * per_day)
    good = np.clip(0.5 * y + rng.normal(0.25, 0.2, len(y)), 0, 1)
    noise = rng.random(len(y))
    return y, days, good, noise


def test_bootstrap_is_reproducible_and_has_the_right_shape():
    y, days, good, noise = _toy()
    a = evaluate.day_block_bootstrap(y, {"good": good, "noise": noise}, days, n_resamples=50, seed=7)
    b = evaluate.day_block_bootstrap(y, {"good": good, "noise": noise}, days, n_resamples=50, seed=7)
    assert set(a) == {"good", "noise"} and set(a["good"]) == set(evaluate.RANK_METRICS)
    assert a["good"]["pr_auc"].shape == (50,)
    assert np.array_equal(a["good"]["roc_auc"], b["good"]["roc_auc"])


def test_bootstrap_resamples_whole_days():
    # Each day is either all positive or all negative and the score equals the label of
    # the day. Whole-day resamples keep that perfect; row-level resampling could not be
    # told apart here, so we also check that every resample has a multiple of the day size.
    days = np.repeat(np.arange(20), 10)
    y = (days % 2).astype(int)
    seen_sizes = []

    def spy(y_true, y_score):
        seen_sizes.append(len(y_true))
        return 1.0

    original = dict(evaluate.RANK_METRICS)
    evaluate.RANK_METRICS.clear()
    evaluate.RANK_METRICS["spy"] = spy
    try:
        evaluate.day_block_bootstrap(y, {"m": y.astype(float)}, days, n_resamples=30, seed=3)
    finally:
        evaluate.RANK_METRICS.clear()
        evaluate.RANK_METRICS.update(original)
    assert seen_sizes and all(size == 200 for size in seen_sizes)   # 20 days x 10 rows each time


def test_bootstrap_days_of_different_size_stay_together():
    days = np.array(["a"] * 3 + ["b"] * 50)
    y = np.array([1, 0, 1] + [0, 1] * 25)
    sizes = []

    def spy(y_true, y_score):
        sizes.append(len(y_true))
        return 0.0

    original = dict(evaluate.RANK_METRICS)
    evaluate.RANK_METRICS.clear()
    evaluate.RANK_METRICS["spy"] = spy
    try:
        evaluate.day_block_bootstrap(y, {"m": y.astype(float)}, days, n_resamples=40, seed=5)
    finally:
        evaluate.RANK_METRICS.clear()
        evaluate.RANK_METRICS.update(original)
    assert set(sizes) <= {6, 53, 100}      # a+a, a+b, b+b
    assert len(set(sizes)) > 1


def test_paired_difference():
    y, days, good, noise = _toy()
    boot = evaluate.day_block_bootstrap(y, {"good": good, "noise": noise, "copy": good}, days, n_resamples=200, seed=11)
    same = evaluate.paired_difference(boot, "copy", "good", "pr_auc")
    assert same["mean"] == 0.0 and not same["better"]
    better = evaluate.paired_difference(boot, "good", "noise", "roc_auc")
    assert better["better"] and better["low"] > 0
    worse = evaluate.paired_difference(boot, "noise", "good", "roc_auc")
    assert not worse["better"]


# ----------------------------------------------------------------- baselines

def _frame(rows):
    df = pd.DataFrame(rows, columns=["service", "planned_hour", "delayed"])
    return df


def test_majority_baseline_is_constant_training_rate():
    train = _frame([("regional", 8, 1), ("regional", 8, 0), ("regional", 9, 0), ("regional", 9, 0)])
    p = baselines.MajorityBaseline().fit(train).predict_proba(train.head(3))
    assert list(p) == [0.25, 0.25, 0.25]


def test_rate_baseline_uses_cell_then_service_then_overall():
    rows = [("regional", 8, 1)] * 20 + [("regional", 8, 0)] * 20          # cell with 40 rows: 0.5
    rows += [("regional", 9, 1)] * 1 + [("regional", 9, 0)] * 9           # small cell (10 rows): falls back
    rows += [("long_distance", 8, 1)] * 30 + [("long_distance", 8, 0)] * 10
    b1 = baselines.RateBaseline().fit(_frame(rows))
    new = _frame([("regional", 8, 0), ("regional", 9, 0), ("regional", 23, 0), ("night", 8, 0)])
    p = b1.predict_proba(new)
    assert p[0] == pytest.approx(0.5)
    regional_rate = 21 / 50
    assert p[1] == pytest.approx(regional_rate)          # cell too small
    assert p[2] == pytest.approx(regional_rate)          # hour never seen
    assert p[3] == pytest.approx(51 / 90)                # service never seen: overall rate


def test_logistic_baseline_handles_unseen_categories_and_missing_lines():
    rng = np.random.default_rng(0)
    n = 400
    train = pd.DataFrame({
        "service": rng.choice(["regional", "long_distance"], n),
        "line_id": rng.choice(["RB53", None], n),
        "planned_hour": rng.integers(5, 23, n),
        "weekday": rng.integers(0, 7, n),
        "is_through": rng.choice([True, False], n),
        "is_public_holiday": rng.random(n) < 0.05,
        "is_school_holiday": rng.random(n) < 0.25,
        "is_bridge_day": rng.random(n) < 0.02,
    })
    train["delayed"] = ((train["service"] == "long_distance") & (rng.random(n) < 0.7)).astype(int)
    model = baselines.make_logistic_baseline().fit(baselines.logistic_frame(train), train["delayed"])
    new = pd.DataFrame({"service": ["long_distance", "regional", "brand_new"], "line_id": [None, "RE99", None],
                        "planned_hour": [8, 8, 3], "weekday": [0, 0, 0], "is_through": [True, False, True],
                        "is_public_holiday": [False, True, False], "is_school_holiday": [False, False, True],
                        "is_bridge_day": [False, False, False]})
    p = model.predict_proba(baselines.logistic_frame(new))[:, 1]
    assert p.shape == (3,) and np.all((p >= 0) & (p <= 1))
    assert p[0] > p[1]


def test_baseline_features_are_not_forbidden():
    assert not (set(features_config.BASELINE_FEATURES) & features_config.FORBIDDEN_COLUMNS)


def test_training_script_refuses_the_test_split():
    with pytest.raises(ValueError):
        train_step.load_modelling_rows("A", splits=("train", "test"))


needs_features = pytest.mark.skipif(not all(f.exists() for f in train_step.FEATURE_FILES.values()),
                                    reason="run src/04_features.py first")


@needs_features
@pytest.mark.parametrize("scenario", ["A", "B"])
def test_training_script_loads_only_development_rows(scenario):
    df = train_step.load_modelling_rows(scenario)
    assert set(df["split"]) == {"train", "val"}
    assert df["departure_planned_time"].max() < pd.Timestamp(train_step.config.SPLITS[scenario]["test"][0])


def test_rule_score_gets_no_brier_score():
    y = np.array([0, 1, 1, 0])
    minutes = np.array([0.0, 12.0, 30.0, 3.0])      # a delay in minutes, not a probability
    m = evaluate.score_metrics(y, minutes, probability=False)
    assert "brier" not in m and m["roc_auc"] == 1.0


def test_fixed_rule_threshold_is_not_tuned():
    y = np.array([0, 1, 1, 0, 1, 0] * 20)
    minutes = np.array([0.0, 4.0, 30.0, 3.0, 9.0, 7.0] * 20)
    days = np.repeat(np.arange(12), 10)
    table, _ = train_step.score_table(y, days, {"rule": minutes}, n_resamples=20,
                                      fixed_threshold={"rule": 6.0}, not_a_probability=("rule",))
    row = table.iloc[0]
    assert row["Threshold"] == "6 min (rule)" and row["Brier"] == "–"
    # at 6 minutes: predicted delayed = 30, 9, 7 -> 2 of 3 right; found 2 of 3 delayed
    assert row["Precision"] == "0.667" and row["Recall"] == "0.667"
