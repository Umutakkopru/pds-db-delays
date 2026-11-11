"""
Step 5: train and evaluate the models.

Current state: all models on the validation splits.
  Scenario A (all departures): baselines B0, B1, B2 and LightGBM M-A, fitted on
  the scenario A training split; weather ablation of M-A (D21).
  Scenario B rows (through trains with an earlier stop): B1, B2 and M-A from
  above, the persistence rule B3 (no fitting, D17), and LightGBM M-A' (scenario A
  features) and M-B (plus earlier-stop features), fitted on the scenario B
  training split.
LightGBM settings come from the fixed grid in src/models.py, chosen on
validation. The single final test run is the next addition; until then this
script never loads test-period rows.

Reads:  data/processed/features_a.parquet, features_b.parquet   (step 4; rows of train and validation)
Writes: reports/results_validation.md                           (validation scores with 95% intervals)
        reports/checks/tuning_m_a.csv, tuning_m_a_prime.csv, tuning_m_b.csv   (all settings tried)

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
import models

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


def tune_model(name: str, train: pd.DataFrame, val: pd.DataFrame, features: list[str]) -> dict:
    """Run the fixed hyperparameter grid for one model and save the table of all settings."""
    best, table = models.tune(train, val, features)
    slug = name.lower().replace("′", "_prime").replace("-", "_")
    table.round(5).to_csv(config.CHECKS / f"tuning_{slug}.csv", index=False)
    print(f"{name}: best setting {best['params']} with {best['n_trees']} trees "
          f"(validation PR-AUC {best['pr_auc']:.4f}; {len(table)} settings tried)")
    return {**best, "features": features, "tuning": table}


SHUFFLE_REPEATS = 5


def sanity_checks(m_a: dict, train: pd.DataFrame, val: pd.DataFrame, val_scores: np.ndarray) -> list[str]:
    """
    Leakage alarms from CLAUDE.md: the scenario A ROC-AUC limit and models fitted on shuffled labels.

    The shuffled models use M-A's setting and tree count without early stopping, so the true
    validation labels never touch them. One shuffle alone scatters around 0.5 (a random function
    of strong features such as the service still orders the trains), so the mean of several
    shuffles is judged.
    """
    roc = evaluate.score_metrics(val[models.TARGET], val_scores)["roc_auc"]
    shuffled_rocs = []
    for repeat in range(SHUFFLE_REPEATS):
        shuffled = train.copy()
        rng = np.random.default_rng(config.SEED + repeat)
        shuffled[models.TARGET] = rng.permutation(shuffled[models.TARGET].to_numpy())
        fitted = models.refit(shuffled, m_a["features"], m_a["params"], m_a["n_trees"])
        proba = models.predict(fitted, val, m_a["features"])
        shuffled_rocs.append(evaluate.score_metrics(val[models.TARGET], proba)["roc_auc"])
    mean = float(np.mean(shuffled_rocs))
    if roc >= 0.95:
        raise RuntimeError(f"Scenario A ROC-AUC {roc:.3f} >= 0.95: stop and check for leakage (CLAUDE.md).")
    if abs(mean - 0.5) > 0.03:
        raise RuntimeError(f"Shuffled-target ROC-AUC {mean:.3f} (mean of {SHUFFLE_REPEATS}) is not close to 0.5: check for leakage.")
    return [
        f"- Scenario A ROC-AUC of M-A on validation: {roc:.3f} (alarm limit 0.95).",
        f"- M-A's setting fitted on shuffled training labels, {SHUFFLE_REPEATS} shuffles, no early stopping: "
        f"validation ROC-AUC mean {mean:.3f}, range {min(shuffled_rocs):.3f}–{max(shuffled_rocs):.3f} (expected about 0.5).",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate on validation (the test period is not used).")
    parser.add_argument("--resamples", type=int, default=config.BOOTSTRAP_N, help="bootstrap resamples of whole days")
    args = parser.parse_args()
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    features_a, features_b = features_config.FEATURES["A"], features_config.FEATURES["B"]

    # ---- data: scenario A (all departures) and scenario B rows (through trains with an earlier stop)
    a = load_modelling_rows("A")
    train, val = a[a["split"] == "train"], a[a["split"] == "val"]
    b = load_modelling_rows("B")
    train_b, val_b = b[b["split"] == "train"], b[b["split"] == "val"]

    # ---- fit: baselines on the A training split; LightGBM with the fixed grid, chosen on validation
    base = fit_baselines(train)
    m_a = tune_model("M-A", train, val, features_a)
    m_a_prime = tune_model("M-A′", train_b, val_b, features_a)
    m_b = tune_model("M-B", train_b, val_b, features_b)

    # ---- scenario A: all validation departures
    y = val[baselines.TARGET].to_numpy()
    scores = {name: predict(val) for name, predict in base.items()}
    scores["M-A LightGBM"] = m_a["val_proba"]
    # weather ablation (D21): same setting as M-A, without the weather columns
    no_weather = [f for f in features_a if f not in features_config.WEATHER_FEATURES]
    scores["M-A without weather"] = models.fit(train, val, no_weather, m_a["params"])["val_proba"]
    table_a, boot_a = score_table(y, val["service_date"].to_numpy(), scores, args.resamples)
    b0, b1, b2 = list(base)
    diff_a = difference_table(boot_a, [(b1, b0), (b2, b1), ("M-A LightGBM", b2), ("M-A LightGBM", "M-A without weather")])
    checks = sanity_checks(m_a, train, val, m_a["val_proba"])

    # ---- scenario B rows: validation split of scenario B
    y_b = val_b[baselines.TARGET].to_numpy()
    rule = "B3 previous-stop delay"
    scores_b = {name: predict(val_b) for name, predict in base.items() if name != b0}
    scores_b[rule] = val_b["prev_delay"].to_numpy(dtype=float)
    scores_b["M-A LightGBM (A training period)"] = models.predict(m_a, val_b, features_a)
    scores_b["M-A′ LightGBM (A features, B period)"] = m_a_prime["val_proba"]
    scores_b["M-B LightGBM (with earlier stops)"] = m_b["val_proba"]
    table_b, boot_b = score_table(
        y_b, val_b["service_date"].to_numpy(), scores_b, args.resamples,
        fixed_threshold={rule: float(config.DELAY_THRESHOLD_MIN)}, not_a_probability=(rule,),
    )
    name_a, name_ap, name_b = list(scores_b)[-3:]
    diff_b = difference_table(boot_b, [(rule, b2), (name_ap, name_a), (name_b, name_ap), (name_b, rule)])

    chosen = pd.DataFrame([
        {"Model": n, "Training rows": f"{rows:,}", "Features": len(m["features"]), "Trees": m["n_trees"],
         "Setting": ", ".join(f"{k}={v}" for k, v in m["params"].items())}
        for n, m, rows in (("M-A", m_a, len(train)), ("M-A′", m_a_prime, len(train_b)), ("M-B", m_b, len(train_b)))
    ])

    text = "\n".join([
        "# Validation results",
        "",
        f"Written by `src/05_train.py`. Intervals: {args.resamples} bootstrap resamples of whole days. "
        "Thresholds maximise F1 on validation unless stated (B0 has a constant score and keeps 0.5). "
        "**The test period is not used.** Validation scores of the LightGBM models are optimistic: the same "
        "validation rows stop the training early, choose the setting and choose the threshold. "
        "The unbiased comparison is the single final run on the test period.",
        "",
        "## Scenario A: all departures",
        "",
        f"Models are fitted on the scenario A training split ({describe(train)}) and scored on its "
        f"validation split ({describe(val)}). B2 uses timetable and calendar columns ("
        + ", ".join(f"`{c}`" for c in features_config.BASELINE_FEATURES) + f"); M-A uses the {len(features_a)} "
        "scenario A features.",
        "",
        to_markdown(table_a),
        "",
        "Paired differences (same day resamples):",
        "",
        to_markdown(diff_a),
        "",
        "## Scenario B rows: through trains with an earlier stop",
        "",
        f"Validation split of scenario B ({describe(val_b)}). B1, B2 and M-A are the scenario A models above, scored "
        f"on these rows. M-A′ and M-B are fitted on the scenario B training split ({describe(train_b)}). B3 is the "
        "persistence rule of D17: its score is the delay in minutes at the previous stop, its class rule is "
        f"\"{config.DELAY_THRESHOLD_MIN} or more minutes late at the previous stop\" (nothing is fitted or tuned; "
        "it has no probability, hence no Brier score).",
        "",
        to_markdown(table_b),
        "",
        "Paired differences (same day resamples): M-A′ − M-A is the effect of the training period, "
        "M-B − M-A′ the effect of the earlier-stop features, M-B − B3 the gain over the simple rule.",
        "",
        to_markdown(diff_b),
        "",
        "## Chosen settings",
        "",
        f"Grid of {len(models.TUNING_GRID)} settings fixed in advance (`src/models.py`, D21); all settings per model "
        "are in `reports/checks/tuning_*.csv`. Learning rate 0.05, early stopping after "
        f"{models.EARLY_STOPPING_ROUNDS} rounds without improvement of the validation log loss, no class weights.",
        "",
        to_markdown(chosen),
        "",
        "## Sanity checks",
        "",
        *checks,
        "",
    ])
    RESULTS_VALIDATION.write_text(text, encoding="utf-8")
    for title, table in (("Scenario A", table_a), ("", diff_a), ("Scenario B rows", table_b), ("", diff_b), ("Chosen settings", chosen)):
        print(("\n=== " + title + " ===\n" if title else "\n") + table.to_string(index=False))
    print("\n" + "\n".join(checks))
    print(f"\nSaved: {RESULTS_VALIDATION}")


if __name__ == "__main__":
    main()
