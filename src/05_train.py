"""
Step 5: train and evaluate the models.

Current state: baselines on the validation splits.
  Scenario A: B0, B1 and B2, fitted on the scenario A training split.
  Scenario B rows (through trains with an earlier stop): the same B1 and B2 plus
  the persistence rule B3, which needs no fitting (decision log D17).
LightGBM (M-A, M-A', M-B) and the single final test run are added next. Until
then this script never loads test-period rows.

Reads:  data/processed/features_a.parquet, features_b.parquet   (step 4; rows of train and validation)
Writes: reports/results_validation.md                           (validation scores with 95% intervals)

Usage: python src/05_train.py
       python src/05_train.py --resamples 200                   # faster bootstrap while developing
"""
import argparse

import duckdb
import numpy as np
import pandas as pd

import baselines
import config
import evaluate
import features_config

FEATURE_FILES = {
    "A": config.DATA_PROCESSED / "features_a.parquet",
    "B": config.DATA_PROCESSED / "features_b.parquet",
}
RESULTS_VALIDATION = config.REPORTS / "results_validation.md"
DEVELOPMENT_SPLITS = ("train", "val")  # the test split is loaded only by the final run


def load_modelling_rows(scenario: str = "A", splits: tuple[str, ...] = DEVELOPMENT_SPLITS) -> pd.DataFrame:
    """Load feature rows of the given splits; refuses the test split (final run not built yet)."""
    if "test" in splits:
        raise ValueError("The test split is used once, by the final run only (CLAUDE.md, evaluation protocol).")
    column = {"A": "split_a", "B": "split_b"}[scenario]
    wanted = ", ".join(f"'{s}'" for s in splits)
    f = str(FEATURE_FILES[scenario]).replace("'", "''")
    return duckdb.sql(f"SELECT *, {column} AS split FROM read_parquet('{f}') WHERE {column} IN ({wanted})").df()


def fit_baselines(train: pd.DataFrame) -> dict:
    """Fit B0, B1 and B2 on training rows; returns {name: function(df) -> probabilities}."""
    b0 = baselines.MajorityBaseline().fit(train)
    b1 = baselines.RateBaseline().fit(train)
    b2 = baselines.make_logistic_baseline().fit(baselines.logistic_frame(train), train[baselines.TARGET])
    return {
        "B0 majority": b0.predict_proba,
        "B1 service x hour": b1.predict_proba,
        "B2 logistic regression": lambda df: b2.predict_proba(baselines.logistic_frame(df))[:, 1],
    }


def score_table(y, days, scores: dict, n_resamples: int, fixed_threshold: dict | None = None,
                not_a_probability: tuple[str, ...] = ()) -> tuple[pd.DataFrame, dict]:
    """
    One row per model: rank metrics with day-block intervals, class metrics, Brier.

    fixed_threshold: models whose threshold is given by their rule instead of being tuned.
    not_a_probability: models whose score is not a probability (no Brier score, no 0.5 threshold).
    """
    fixed_threshold = fixed_threshold or {}
    boot = evaluate.day_block_bootstrap(y, scores, days, n_resamples=n_resamples)
    rows = []
    for name, s in scores.items():
        probability = name not in not_a_probability
        m = evaluate.score_metrics(y, s, probability=probability)
        constant = float(np.min(s)) == float(np.max(s))
        if name in fixed_threshold:
            threshold = fixed_threshold[name]
        elif constant:
            threshold = 0.5   # a constant score cannot rank: its "best threshold" would call every train delayed
        else:
            threshold = evaluate.best_f1_threshold(y, s)
        at_threshold = evaluate.class_metrics(y, s, threshold)
        at_half = evaluate.class_metrics(y, s, 0.5) if probability else None
        pr_lo, pr_hi = evaluate.interval(boot[name]["pr_auc"])
        roc_lo, roc_hi = evaluate.interval(boot[name]["roc_auc"])
        rows.append({
            "Model": name,
            "PR-AUC [95% CI]": f"{m['pr_auc']:.3f} [{pr_lo:.3f}, {pr_hi:.3f}]",
            "ROC-AUC [95% CI]": f"{m['roc_auc']:.3f} [{roc_lo:.3f}, {roc_hi:.3f}]",
            "Threshold": f"{threshold:.3f}" if probability else f"{threshold:g} min (rule)",
            "F1": f"{at_threshold['f1']:.3f}",
            "Precision": f"{at_threshold['precision']:.3f}",
            "Recall": f"{at_threshold['recall']:.3f}",
            "Accuracy": f"{at_threshold['accuracy']:.3f}",
            "F1 at 0.5": f"{at_half['f1']:.3f}" if probability else "–",
            "Brier": f"{m['brier']:.4f}" if probability else "–",
        })
    return pd.DataFrame(rows), boot


def difference_table(boot: dict, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Paired differences (model − reference) of the rank metrics on the same day resamples."""
    rows = []
    for model, reference in pairs:
        for metric in evaluate.RANK_METRICS:
            d = evaluate.paired_difference(boot, model, reference, metric)
            rows.append({
                "Comparison": f"{model} − {reference}",
                "Metric": metric,
                "Difference [95% CI]": f"{d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]",
                "Interval above zero": "yes" if d["better"] else "no",
            })
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "| " + " | ".join("---" for _ in df.columns) + " |"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def describe(rows: pd.DataFrame) -> str:
    return (f"{len(rows):,} departures on {rows['service_date'].nunique()} days, "
            f"{100 * rows[baselines.TARGET].mean():.1f}% delayed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate (currently: baselines on validation).")
    parser.add_argument("--resamples", type=int, default=config.BOOTSTRAP_N, help="bootstrap resamples of whole days")
    args = parser.parse_args()

    # ---- scenario A: all departures
    a = load_modelling_rows("A")
    train, val = a[a["split"] == "train"], a[a["split"] == "val"]
    models = fit_baselines(train)
    y = val[baselines.TARGET].to_numpy()
    scores = {name: predict(val) for name, predict in models.items()}
    table_a, boot_a = score_table(y, val["service_date"].to_numpy(), scores, args.resamples)
    names = list(scores)
    diff_a = difference_table(boot_a, [(names[1], names[0]), (names[2], names[1])])

    # ---- scenario B rows: through trains with an earlier stop (validation of the B window)
    b = load_modelling_rows("B")
    val_b = b[b["split"] == "val"]
    y_b = val_b[baselines.TARGET].to_numpy()
    rule = "B3 previous-stop delay"
    scores_b = {name: predict(val_b) for name, predict in models.items() if not name.startswith("B0")}
    scores_b[rule] = val_b["prev_delay"].to_numpy(dtype=float)
    table_b, boot_b = score_table(
        y_b, val_b["service_date"].to_numpy(), scores_b, args.resamples,
        fixed_threshold={rule: float(config.DELAY_THRESHOLD_MIN)}, not_a_probability=(rule,),
    )
    diff_b = difference_table(boot_b, [(rule, names[2])])

    text = "\n".join([
        "# Validation results (baselines)",
        "",
        f"Written by `src/05_train.py`. Intervals: {args.resamples} bootstrap resamples of whole days. "
        "Thresholds maximise F1 on validation unless stated (B0 has a constant score and keeps 0.5). "
        "The test period is not used.",
        "",
        "## Scenario A: all departures",
        "",
        f"B0–B2 are fitted on the scenario A training split ({describe(train)}) and scored on its "
        f"validation split ({describe(val)}). B2 uses timetable and calendar columns ("
        + ", ".join(f"`{c}`" for c in features_config.BASELINE_FEATURES) + ").",
        "",
        to_markdown(table_a),
        "",
        "Paired differences (same day resamples):",
        "",
        to_markdown(diff_a),
        "",
        "## Scenario B rows: through trains with an earlier stop",
        "",
        f"Validation split of scenario B ({describe(val_b)}). B1 and B2 are the scenario A models above, scored on "
        "these rows. B3 is the persistence rule of D17: its score is the delay in minutes at the previous stop, "
        f"its class rule is \"{config.DELAY_THRESHOLD_MIN} or more minutes late at the previous stop\" "
        "(a fixed rule, nothing is fitted or tuned; it has no probability, hence no Brier score).",
        "",
        to_markdown(table_b),
        "",
        "Paired differences (same day resamples):",
        "",
        to_markdown(diff_b),
        "",
    ])
    RESULTS_VALIDATION.write_text(text, encoding="utf-8")
    for title, table in (("Scenario A", table_a), ("", diff_a), ("Scenario B rows", table_b), ("", diff_b)):
        print(("\n=== " + title + " ===\n" if title else "\n") + table.to_string(index=False))
    print(f"\nSaved: {RESULTS_VALIDATION}")


if __name__ == "__main__":
    main()
