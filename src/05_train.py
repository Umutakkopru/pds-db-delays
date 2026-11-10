"""
Step 5: train and evaluate the models.

Current state: baselines B0, B1 and B2 for scenario A, trained on the training
split and scored on the validation split. LightGBM (M-A, M-A', M-B), the
scenario B baseline B3 and the single final test run are added when the feature
tables of step 04 exist. Until then this script never loads test-period rows.

Reads:  data/processed/wuerzburg_clean.parquet            (step 2; modelling rows of train and validation)
Writes: reports/results_validation.md                     (validation scores with 95% intervals)

Usage: python src/05_train.py
       python src/05_train.py --resamples 200             # faster bootstrap while developing
"""
import argparse

import duckdb
import pandas as pd

import baselines
import config
import evaluate

CLEAN_FILE = config.DATA_PROCESSED / "wuerzburg_clean.parquet"
RESULTS_VALIDATION = config.REPORTS / "results_validation.md"
DEVELOPMENT_SPLITS = ("train", "val")  # the test split is loaded only by the final run


def load_modelling_rows(scenario: str = "A", splits: tuple[str, ...] = DEVELOPMENT_SPLITS) -> pd.DataFrame:
    """Load modelling rows of the given splits; refuses the test split (final run not built yet)."""
    if "test" in splits:
        raise ValueError("The test split is used once, by the final run only (evaluation protocol, D13).")
    column = {"A": "split_a", "B": "split_b"}[scenario]
    wanted = ", ".join(f"'{s}'" for s in splits)
    f = str(CLEAN_FILE).replace("'", "''")
    df = duckdb.sql(f"""
        SELECT *, {column} AS split
        FROM read_parquet('{f}')
        WHERE exclude_reason IS NULL AND {column} IN ({wanted})
    """).df()
    return baselines.add_timetable_columns(df)


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


def score_table(y, days, scores: dict, n_resamples: int) -> tuple[pd.DataFrame, dict]:
    """One row per model: rank metrics with day-block intervals, class metrics, Brier."""
    boot = evaluate.day_block_bootstrap(y, scores, days, n_resamples=n_resamples)
    rows = []
    for name, s in scores.items():
        m = evaluate.score_metrics(y, s)
        constant = float(s.min()) == float(s.max())
        # A constant score cannot rank: its "best threshold" would call every train delayed.
        threshold = 0.5 if constant else evaluate.best_f1_threshold(y, s)
        at_best = evaluate.class_metrics(y, s, threshold)
        at_half = evaluate.class_metrics(y, s, 0.5)
        pr_lo, pr_hi = evaluate.interval(boot[name]["pr_auc"])
        roc_lo, roc_hi = evaluate.interval(boot[name]["roc_auc"])
        rows.append({
            "Model": name,
            "PR-AUC [95% CI]": f"{m['pr_auc']:.3f} [{pr_lo:.3f}, {pr_hi:.3f}]",
            "ROC-AUC [95% CI]": f"{m['roc_auc']:.3f} [{roc_lo:.3f}, {roc_hi:.3f}]",
            "Threshold": f"{threshold:.3f}",
            "F1": f"{at_best['f1']:.3f}",
            "Precision": f"{at_best['precision']:.3f}",
            "Recall": f"{at_best['recall']:.3f}",
            "F1 at 0.5": f"{at_half['f1']:.3f}",
            "Accuracy at 0.5": f"{at_half['accuracy']:.3f}",
            "Brier": f"{m['brier']:.4f}",
        })
    return pd.DataFrame(rows), boot


def to_markdown(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "| " + " | ".join("---" for _ in df.columns) + " |"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate (currently: baselines on validation).")
    parser.add_argument("--resamples", type=int, default=config.BOOTSTRAP_N, help="bootstrap resamples of whole days")
    args = parser.parse_args()

    df = load_modelling_rows("A")
    train, val = df[df["split"] == "train"], df[df["split"] == "val"]
    models = fit_baselines(train)
    y = val[baselines.TARGET].to_numpy()
    scores = {name: predict(val) for name, predict in models.items()}
    table, boot = score_table(y, val["service_date"].to_numpy(), scores, args.resamples)

    names = list(scores)
    differences = []
    for model, reference in [(names[1], names[0]), (names[2], names[1])]:
        for metric in evaluate.RANK_METRICS:
            d = evaluate.paired_difference(boot, model, reference, metric)
            differences.append({
                "Comparison": f"{model} − {reference}",
                "Metric": metric,
                "Difference [95% CI]": f"{d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]",
                "Interval above zero": "yes" if d["better"] else "no",
            })
    differences = pd.DataFrame(differences)

    header = (
        "# Validation results (scenario A baselines)\n\n"
        "Written by `src/05_train.py`. Models are fitted on the scenario A training split "
        f"({len(train):,} departures, {100 * train[baselines.TARGET].mean():.1f}% delayed) and scored on the "
        f"validation split ({len(val):,} departures on {val['service_date'].nunique()} days, "
        f"{100 * y.mean():.1f}% delayed). Intervals: {args.resamples} bootstrap resamples of whole days. "
        "The threshold maximises F1 on validation (B0 has a constant score and keeps 0.5). "
        "The test period is not used.\n\n"
        "B2 uses only timetable columns so far ("
        + ", ".join(f"`{c}`" for c in baselines.features_config.BASELINE_FEATURES)
        + "); holidays follow with step 03.\n"
    )
    text = header + "\n" + to_markdown(table) + "\n\n## Paired differences (same day resamples)\n\n" + to_markdown(differences) + "\n"
    RESULTS_VALIDATION.write_text(text, encoding="utf-8")
    print(table.to_string(index=False))
    print()
    print(differences.to_string(index=False))
    print(f"\nSaved: {RESULTS_VALIDATION}")


if __name__ == "__main__":
    main()
