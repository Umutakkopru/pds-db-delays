"""
Step 5: train and evaluate all models.

Three modes share one code path (decision log D13, D17, D21):

  validation (default)  Fit on the training split, score the validation split.
                        Used during development; also runs the weather ablations (M-A, M-A', M-B)
                        and the sanity checks.
  --rehearsal           The final procedure shifted one step back in time: the
                        validation period plays the test period, the end of the
                        training period plays validation. Tests the final code
                        on real data without touching the test period, and gives
                        scores for the validation period that are not biased by
                        early stopping, tuning or threshold choice.
  --final               The single run on the test period. Settings, tree counts
                        and thresholds come from training-only models on
                        validation; all models are refitted on training +
                        validation and scored once on the test period. Writes a
                        marker file and refuses to run a second time.

Models: B0, B1, B2 and LightGBM M-A on all departures; on the scenario B rows
(through trains with an earlier stop) also the persistence rule B3 and LightGBM
M-A' (scenario A features) and M-B (plus earlier-stop features).

Reads:  data/processed/features_a.parquet, features_b.parquet, features_a_sensitivity.parquet   (step 4)
Writes: reports/results_validation.md | results_rehearsal.md | results.md
        data/processed/predictions_{val|rehearsal|test}_{a|b}.parquet    (scores per row, for step 6)
        reports/checks/tuning_*.csv                                      (validation mode: all settings tried)
        reports/checks/thresholds_{val|rehearsal|test}.json              (class thresholds chosen on validation rows)
        --final only: reports/final_run.json (marker), models/*.txt and models/*.json (final models)

Usage: python src/05_train.py
       python src/05_train.py --resamples 200      # faster bootstrap while developing
       python src/05_train.py --rehearsal
       python src/05_train.py --final              # once, after the group has agreed
"""
import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

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
SENSITIVITY_FILE = config.DATA_PROCESSED / "features_a_sensitivity.parquet"
MODES = {
    # mode: (file suffix, results file, name of the scored period)
    "validation": ("val", config.REPORTS / "results_validation.md", "validation"),
    "rehearsal": ("rehearsal", config.REPORTS / "results_rehearsal.md", "validation (rehearsal of the final run)"),
    "final": ("test", config.REPORTS / "results.md", "test"),
}
RESULTS_VALIDATION = MODES["validation"][1]
FINAL_MARKER = config.REPORTS / "final_run.json"
MODELS_DIR = config.ROOT / "models"
DEVELOPMENT_SPLITS = ("train", "val")   # the test split is loaded only by the final run

B0, B1, B2 = "B0 majority", "B1 service x hour", "B2 logistic regression"
B3 = "B3 previous-stop delay"
M_A, M_A_NO_WEATHER = "M-A LightGBM", "M-A without weather"
M_A_ON_B = "M-A LightGBM (A training period)"
M_A_PRIME = "M-A′ LightGBM (A features, B period)"
M_B = "M-B LightGBM (with earlier stops)"
M_A_PRIME_NO_WEATHER, M_B_NO_WEATHER = "M-A′ without weather", "M-B without weather"
NO_WEATHER = "without weather"          # ablation models: scored on validation only, never saved
MIN_ROWS_OWN_THRESHOLD = 300            # a service with fewer validation rows keeps the overall threshold
TOP_SHARES = (0.05, 0.10)               # "delay rate among the departures with the highest scores"
SHORT_NAMES = {"B0": "b0", "B1": "b1", "B2": "b2", "B3": "b3", "M-A′": "m_a_prime", "M-A": "m_a", "M-B": "m_b"}
SHUFFLE_REPEATS = 5


# ----------------------------------------------------------------- data

def prediction_file(mode: str, scenario: str) -> Path:
    return config.DATA_PROCESSED / f"predictions_{MODES[mode][0]}_{scenario.lower()}.parquet"


def threshold_file(mode: str) -> Path:
    """Class thresholds chosen on validation rows, read by src/06_error_analysis.py."""
    return config.CHECKS / f"thresholds_{MODES[mode][0]}.json"


def load_modelling_rows(scenario: str = "A", splits: tuple[str, ...] = DEVELOPMENT_SPLITS,
                        allow_test: bool = False) -> pd.DataFrame:
    """Load feature rows of the given splits. The test split needs allow_test=True (final run only)."""
    if "test" in splits and not allow_test:
        raise ValueError("The test split is used once, by the final run only (CLAUDE.md, evaluation protocol).")
    column = {"A": "split_a", "B": "split_b"}[scenario]
    wanted = ", ".join(f"'{s}'" for s in splits)
    f = str(FEATURE_FILES[scenario]).replace("'", "''")
    return duckdb.sql(f"SELECT *, {column} AS split FROM read_parquet('{f}') WHERE {column} IN ({wanted})").df()


def load_sensitivity_rows(period: tuple[str, str], allow_test: bool = False) -> pd.DataFrame:
    """Cancelled departures and departures without timetable record planned in [start, end)."""
    start, end = period
    if pd.Timestamp(end) > pd.Timestamp(config.SPLITS["A"]["test"][0]) and not allow_test:
        raise ValueError("Sensitivity rows of the test period are loaded by the final run only.")
    f = str(SENSITIVITY_FILE).replace("'", "''")
    return duckdb.sql(f"""
        SELECT * FROM read_parquet('{f}')
        WHERE departure_planned_time >= TIMESTAMP '{start}' AND departure_planned_time < TIMESTAMP '{end}'
    """).df()


def between(df: pd.DataFrame, period: tuple[str, str]) -> pd.DataFrame:
    start, end = period
    t = df["departure_planned_time"]
    return df[(t >= pd.Timestamp(start)) & (t < pd.Timestamp(end))]


def frames_for(mode: str, scenario: str) -> dict:
    """
    Training, validation and evaluation rows of one scenario for a mode.

    Returns {"train", "val", "eval", "eval_period"}; in validation mode the
    evaluation rows are the validation rows themselves.
    """
    if mode == "final":
        rows = load_modelling_rows(scenario, ("train", "val", "test"), allow_test=True)
        return {"train": rows[rows["split"] == "train"], "val": rows[rows["split"] == "val"],
                "eval": rows[rows["split"] == "test"], "eval_period": config.SPLITS[scenario]["test"]}
    rows = load_modelling_rows(scenario)
    if mode == "rehearsal":
        periods = config.REHEARSAL_SPLITS[scenario]
        return {"train": between(rows, periods["train"]), "val": between(rows, periods["val"]),
                "eval": between(rows, periods["eval"]), "eval_period": periods["eval"]}
    val = rows[rows["split"] == "val"]
    return {"train": rows[rows["split"] == "train"], "val": val, "eval": val,
            "eval_period": config.SPLITS[scenario]["val"]}


# ----------------------------------------------------------------- models

def fit_baselines(train: pd.DataFrame) -> dict:
    """Fit B0, B1 and B2 on the given rows; returns {name: function(df) -> probabilities}."""
    b0 = baselines.MajorityBaseline().fit(train)
    b1 = baselines.RateBaseline().fit(train)
    b2 = baselines.make_logistic_baseline().fit(baselines.logistic_frame(train), train[baselines.TARGET])
    return {
        B0: b0.predict_proba,
        B1: b1.predict_proba,
        B2: lambda df: b2.predict_proba(baselines.logistic_frame(df))[:, 1],
    }


def tune_model(name: str, train: pd.DataFrame, val: pd.DataFrame, features: list[str], save_table: bool) -> dict:
    """Run the fixed hyperparameter grid for one model; optionally save the table of all settings."""
    best, table = models.tune(train, val, features)
    if save_table:
        slug = name.lower().replace("′", "_prime").replace("-", "_")
        table.round(5).to_csv(config.CHECKS / f"tuning_{slug}.csv", index=False)
    print(f"{name}: best setting {best['params']} with {best['n_trees']} trees "
          f"(validation PR-AUC {best['pr_auc']:.4f}; {len(table)} settings tried)")
    return {**best, "features": features}


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


# ----------------------------------------------------------------- tables

def score_table(y, days, scores: dict, n_resamples: int, fixed_threshold: dict | None = None,
                not_a_probability: tuple[str, ...] = ()) -> tuple[pd.DataFrame, dict]:
    """
    One row per model: rank metrics with day-block intervals, class metrics, Brier.

    fixed_threshold: models whose threshold is given (by a rule, or chosen earlier on validation)
                     instead of being tuned on the scored rows.
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


def sensitivity_table(eval_rows: pd.DataFrame, extra: pd.DataFrame, predictors: dict) -> pd.DataFrame:
    """
    Sensitivity checks D9 and D18: the same models scored on the evaluation rows plus
    (a) cancelled departures counted as delayed, (b) departures without timetable record.

    predictors: {model name: function(df) -> probabilities}.
    """
    sets = {
        "Main evaluation rows": eval_rows,
        "+ cancelled departures counted as delayed (D9)":
            pd.concat([eval_rows, extra[extra["sensitivity_set"] == "canceled"]], ignore_index=True),
        "+ departures without timetable record (D18)":
            pd.concat([eval_rows, extra[extra["sensitivity_set"] == "no_plan_record"]], ignore_index=True),
    }
    rows = []
    for label, rows_set in sets.items():
        y = rows_set[baselines.TARGET].to_numpy()
        row = {"Rows": label, "n": f"{len(rows_set):,}", "Delayed": f"{100 * y.mean():.1f}%"}
        for name, predict in predictors.items():
            m = evaluate.score_metrics(y, predict(rows_set))
            row[f"PR-AUC {name.split()[0]}"] = f"{m['pr_auc']:.3f}"
            row[f"ROC-AUC {name.split()[0]}"] = f"{m['roc_auc']:.3f}"
        rows.append(row)
    return pd.DataFrame(rows)


def service_thresholds(val: pd.DataFrame, val_score: np.ndarray, overall: float) -> dict[str, float]:
    """
    One class threshold per service, chosen on validation rows (max F1 inside the service).

    A service with fewer than MIN_ROWS_OWN_THRESHOLD validation rows, or with only one class,
    keeps the overall threshold.
    """
    out = {}
    y = val[baselines.TARGET].to_numpy()
    for service in sorted(val["service"].unique()):
        mask = (val["service"] == service).to_numpy()
        enough = mask.sum() >= MIN_ROWS_OWN_THRESHOLD and 0 < y[mask].sum() < mask.sum()
        out[service] = float(evaluate.best_f1_threshold(y[mask], val_score[mask])) if enough else float(overall)
    return out


def operating_point_table(rows: pd.DataFrame, score: np.ndarray, overall: float, per_service: dict[str, float]) -> pd.DataFrame:
    """
    Class metrics per service at the overall threshold and at the service's own threshold,
    and the delay rate among the departures with the highest scores (TOP_SHARES).

    The last row applies the per-service thresholds to all rows together. A service that is
    not in per_service (unseen on validation) uses the overall threshold.
    """
    y = rows[baselines.TARGET].to_numpy()
    service = rows["service"].to_numpy()
    own = np.array([per_service.get(s, overall) for s in service])

    def line(label: str, mask: np.ndarray, threshold_text: str) -> dict:
        at_overall = evaluate.class_metrics(y[mask], score[mask], overall)
        flagged = (score[mask] >= own[mask]).astype(float)          # 1.0 where the own threshold calls "delayed"
        at_own = evaluate.class_metrics(y[mask], flagged, 0.5)
        order = np.argsort(-score[mask], kind="stable")
        out = {"Service": label, "Rows": f"{mask.sum():,}", "Delayed": f"{100 * y[mask].mean():.1f}%",
               "Overall threshold: P / R / F1": f"{at_overall['precision']:.3f} / {at_overall['recall']:.3f} / {at_overall['f1']:.3f}",
               "Own threshold": threshold_text,
               "Own threshold: P / R / F1": f"{at_own['precision']:.3f} / {at_own['recall']:.3f} / {at_own['f1']:.3f}"}
        for share in TOP_SHARES:
            k = max(1, int(round(share * mask.sum())))
            few = mask.sum() < MIN_ROWS_OWN_THRESHOLD      # a handful of rows says nothing
            out[f"Delayed in top {share:.0%}"] = "–" if few else f"{100 * y[mask][order[:k]].mean():.1f}%"
        return out

    table = [line(s, service == s, f"{per_service.get(s, overall):.3f}") for s in sorted(set(service))]
    table.append(line("All departures", np.ones(len(rows), dtype=bool), "per service"))
    return pd.DataFrame(table)


def to_markdown(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "| " + " | ".join("---" for _ in df.columns) + " |"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def describe(rows: pd.DataFrame) -> str:
    return (f"{len(rows):,} departures on {rows['service_date'].nunique()} days, "
            f"{100 * rows[baselines.TARGET].mean():.1f}% delayed")


def save_predictions(rows: pd.DataFrame, scores: dict, path: Path) -> None:
    """Write id, day, outcome and one score column per model (column name = short model name)."""
    out = rows[["id", "service_date", baselines.TARGET]].copy()
    for name, values in scores.items():
        if NO_WEATHER in name:
            continue
        short = next(v for k, v in SHORT_NAMES.items() if name.startswith(k))
        out[short] = np.asarray(values, dtype=float)
    out.to_parquet(path, index=False)


# ----------------------------------------------------------------- final-run guard

def git_state() -> tuple[str, bool]:
    """Current commit hash and whether tracked files have uncommitted changes."""
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=config.ROOT,
                                capture_output=True, text=True).stdout.strip())
    return commit, dirty


def check_final_run_allowed(marker: Path = FINAL_MARKER, dirty: bool | None = None) -> None:
    """The final run happens once, from committed code. Raise otherwise."""
    if marker.exists():
        raise RuntimeError(
            f"The final run has already been done ({marker.name} exists). The test period is used once; "
            "nothing may be changed and re-run afterwards (CLAUDE.md, evaluation protocol)."
        )
    if dirty is None:
        dirty = git_state()[1]
    if dirty:
        raise RuntimeError("Uncommitted changes in tracked files: commit first, so that the final run "
                           "can be traced to one exact version of the code.")


def write_final_marker(info: dict, marker: Path = FINAL_MARKER) -> None:
    commit, _ = git_state()
    marker.write_text(json.dumps({"finished": datetime.now().isoformat(timespec="seconds"), "commit": commit, **info},
                                 indent=2), encoding="utf-8")


def save_final_models(fitted: dict, thresholds: dict) -> None:
    """Final models for the dashboard: LightGBM text files plus features, categories, setting and threshold."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in fitted.items():
        slug = SHORT_NAMES["M-A′" if name == M_A_PRIME else name.split()[0]]
        model["model"].booster_.save_model(str(MODELS_DIR / f"{slug}.txt"))
        (MODELS_DIR / f"{slug}.json").write_text(json.dumps({
            "name": name, "features": model["features"], "categories": model["categories"],
            "params": model["params"], "n_trees": model["n_trees"], "threshold": thresholds[name],
        }, indent=2, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------- one run

def run(mode: str, n_resamples: int) -> None:
    suffix, results_file, period_name = MODES[mode]
    final_like = mode != "validation"
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    features_a, features_b = features_config.FEATURES["A"], features_config.FEATURES["B"]
    a, b = frames_for(mode, "A"), frames_for(mode, "B")

    # ---- development models: fitted on training rows, tuned and thresholded on validation rows
    base_dev = fit_baselines(a["train"])
    dev = {
        M_A: tune_model("M-A", a["train"], a["val"], features_a, save_table=not final_like),
        M_A_PRIME: tune_model("M-A′", b["train"], b["val"], features_a, save_table=not final_like),
        M_B: tune_model("M-B", b["train"], b["val"], features_b, save_table=not final_like),
    }
    val_scores_a = {name: predict(a["val"]) for name, predict in base_dev.items()}
    val_scores_a[M_A] = dev[M_A]["val_proba"]
    val_scores_b = {name: predict(b["val"]) for name, predict in base_dev.items() if name != B0}
    val_scores_b[M_A_ON_B] = models.predict(dev[M_A], b["val"], features_a)
    val_scores_b[M_A_PRIME] = dev[M_A_PRIME]["val_proba"]
    val_scores_b[M_B] = dev[M_B]["val_proba"]
    y_val_a, y_val_b = a["val"][baselines.TARGET].to_numpy(), b["val"][baselines.TARGET].to_numpy()
    thresholds_a = {n: evaluate.best_f1_threshold(y_val_a, s) for n, s in val_scores_a.items() if n != B0}
    thresholds_a[B0] = 0.5
    thresholds_b = {n: evaluate.best_f1_threshold(y_val_b, s) for n, s in val_scores_b.items()}
    thresholds_b[B3] = float(config.DELAY_THRESHOLD_MIN)

    # operating points per service (P1): thresholds from validation rows, applied to the scored rows
    per_service = service_thresholds(a["val"], np.asarray(dev[M_A]["val_proba"]), thresholds_a[M_A])

    threshold_file(mode).write_text(json.dumps({
        "b2": thresholds_a[B2], "m_a": thresholds_a[M_A], "b3": thresholds_b[B3],
        "m_a_prime": thresholds_b[M_A_PRIME], "m_b": thresholds_b[M_B],
        "m_a_per_service": per_service,
    }, indent=2), encoding="utf-8")

    # ---- models that are scored: the development models, or the refit on training + validation
    if final_like:
        fit_a, fit_b = pd.concat([a["train"], a["val"]]), pd.concat([b["train"], b["val"]])
        base = fit_baselines(fit_a)
        fitted = {
            M_A: {**models.refit(fit_a, features_a, dev[M_A]["params"], dev[M_A]["n_trees"]), "features": features_a, "params": dev[M_A]["params"]},
            M_A_PRIME: {**models.refit(fit_b, features_a, dev[M_A_PRIME]["params"], dev[M_A_PRIME]["n_trees"]), "features": features_a, "params": dev[M_A_PRIME]["params"]},
            M_B: {**models.refit(fit_b, features_b, dev[M_B]["params"], dev[M_B]["n_trees"]), "features": features_b, "params": dev[M_B]["params"]},
        }
    else:
        fit_a, fit_b, base, fitted = a["train"], b["train"], base_dev, dev

    # ---- scenario A: all departures of the scored period
    eval_a, eval_b = a["eval"], b["eval"]
    y = eval_a[baselines.TARGET].to_numpy()
    scores = {name: predict(eval_a) for name, predict in base.items()}
    scores[M_A] = models.predict(fitted[M_A], eval_a, features_a)
    pairs_a = [(B1, B0), (B2, B1), (M_A, B2)]
    checks = []
    if not final_like:
        # weather ablation (D21) and sanity checks belong to development
        no_weather = [f for f in features_a if f not in features_config.WEATHER_FEATURES]
        scores[M_A_NO_WEATHER] = models.fit(a["train"], a["val"], no_weather, dev[M_A]["params"])["val_proba"]
        pairs_a.append((M_A, M_A_NO_WEATHER))
        checks = sanity_checks(dev[M_A], a["train"], a["val"], dev[M_A]["val_proba"])
    table_a, boot_a = score_table(y, eval_a["service_date"].to_numpy(), scores, n_resamples,
                                  fixed_threshold=thresholds_a if final_like else None)
    diff_a = difference_table(boot_a, pairs_a)
    save_predictions(eval_a, scores, prediction_file(mode, "A"))
    operating = operating_point_table(eval_a, np.asarray(scores[M_A]), thresholds_a[M_A], per_service)

    # ---- scenario B rows: through trains with an earlier stop
    y_b = eval_b[baselines.TARGET].to_numpy()
    scores_b = {name: predict(eval_b) for name, predict in base.items() if name != B0}
    scores_b[B3] = eval_b["prev_delay"].to_numpy(dtype=float)
    scores_b[M_A_ON_B] = models.predict(fitted[M_A], eval_b, features_a)
    scores_b[M_A_PRIME] = models.predict(fitted[M_A_PRIME], eval_b, features_a)
    scores_b[M_B] = models.predict(fitted[M_B], eval_b, features_b)
    pairs_b = [(B3, B2), (M_A_PRIME, M_A_ON_B), (M_B, M_A_PRIME), (M_B, B3)]
    if not final_like:
        # weather ablation for the scenario B models (P2): same settings, weather features left out
        for full, ablated in ((M_A_PRIME, M_A_PRIME_NO_WEATHER), (M_B, M_B_NO_WEATHER)):
            kept = [f for f in dev[full]["features"] if f not in features_config.WEATHER_FEATURES]
            scores_b[ablated] = models.fit(b["train"], b["val"], kept, dev[full]["params"])["val_proba"]
            pairs_b.append((full, ablated))
    table_b, boot_b = score_table(
        y_b, eval_b["service_date"].to_numpy(), scores_b, n_resamples,
        fixed_threshold=thresholds_b if final_like else {B3: thresholds_b[B3]}, not_a_probability=(B3,),
    )
    diff_b = difference_table(boot_b, pairs_b)
    save_predictions(eval_b, scores_b, prediction_file(mode, "B"))

    # ---- sensitivity checks (D9, D18) on scenario A
    extra = load_sensitivity_rows(a["eval_period"], allow_test=(mode == "final"))
    sensitivity = sensitivity_table(eval_a, extra, {
        B2: base[B2], M_A: lambda df: models.predict(fitted[M_A], df, features_a)})

    chosen = pd.DataFrame([
        {"Model": n, "Fitted on": f"{rows:,} rows", "Features": len(dev[key]["features"]), "Trees": dev[key]["n_trees"],
         "Setting": ", ".join(f"{k}={v}" for k, v in dev[key]["params"].items())}
        for n, key, rows in (("M-A", M_A, len(fit_a)), ("M-A′", M_A_PRIME, len(fit_b)), ("M-B", M_B, len(fit_b)))
    ])

    if final_like:
        how = ("Settings, tree counts and thresholds come from training-only models on the validation rows; all models "
               "are then refitted on training + validation and scored on the period below, which played no part in "
               "any choice. ")
        how += ("**This is a rehearsal of the final run: the test period is not used.** The periods are those of "
                "`REHEARSAL_SPLITS` in `src/config.py`." if mode == "rehearsal" else
                "**This is the single final run on the test period.** Nothing was changed afterwards.")
        fitted_a = f"training + validation ({describe(fit_a)})"
        fitted_b = f"training + validation of scenario B ({describe(fit_b)})"
    else:
        how = ("Thresholds maximise F1 on validation unless stated (B0 has a constant score and keeps 0.5). "
               "**The test period is not used.** Validation scores of the LightGBM models are optimistic: the same "
               "validation rows stop the training early, choose the setting and choose the threshold. "
               "The unbiased comparison is the single final run on the test period.")
        fitted_a = f"the scenario A training split ({describe(fit_a)})"
        fitted_b = f"the scenario B training split ({describe(fit_b)})"

    text = [
        {"validation": "# Validation results", "rehearsal": "# Rehearsal of the final run", "final": "# Final results (test period)"}[mode],
        "",
        f"Written by `src/05_train.py`{'' if mode == 'validation' else ' --' + mode}. Scored period: {period_name}. "
        f"Intervals: {n_resamples} bootstrap resamples of whole days. " + how,
        "",
        "## Scenario A: all departures",
        "",
        f"Models are fitted on {fitted_a} and scored on {describe(eval_a)}. B2 uses timetable and calendar columns ("
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
        f"Scored on {describe(eval_b)}. B1, B2 and M-A are the scenario A models above, scored on these rows. "
        f"M-A′ and M-B are fitted on {fitted_b}. B3 is the persistence rule of D17: its score is the delay in "
        f"minutes at the previous stop, its class rule is \"{config.DELAY_THRESHOLD_MIN} or more minutes late at the "
        "previous stop\" (nothing is fitted or tuned; it has no probability, hence no Brier score).",
        "",
        to_markdown(table_b),
        "",
        "Paired differences (same day resamples): M-A′ − M-A is the effect of the training period, "
        "M-B − M-A′ the effect of the earlier-stop features, M-B − B3 the gain over the simple rule.",
        "",
        to_markdown(diff_b),
        "",
        "## M-A: operating points per service",
        "",
        "The overall threshold maximises F1 over all departures; with it, M-A flags almost no regional train, "
        "because regional trains are delayed far less often than long-distance trains. This table shows in addition "
        "what a threshold per service gives (chosen inside each service on the validation rows; services with fewer "
        f"than {MIN_ROWS_OWN_THRESHOLD} validation rows keep the overall threshold of {thresholds_a[M_A]:.3f}), and how "
        "often the departures with the highest scores are delayed. P / R / F1 = precision / recall / F1. "
        + ("The thresholds were fixed before these rows were scored." if final_like else
           "In this mode the thresholds are chosen on the scored rows themselves, so the numbers are optimistic."),
        "",
        to_markdown(operating),
        "",
        "## Sensitivity checks (scenario A)",
        "",
        "The same models scored once more with rows that the main evaluation excludes (D9, D18). These rows are "
        "never used for fitting. A cancelled departure counts as delayed here.",
        "",
        to_markdown(sensitivity),
        "",
        "## Chosen settings",
        "",
        f"Grid of {len(models.TUNING_GRID)} settings fixed in advance (`src/models.py`, D21). Learning rate 0.05, "
        f"early stopping after {models.EARLY_STOPPING_ROUNDS} rounds without improvement of the validation log loss, "
        "no class weights. Trees = number found with the training-only model"
        + (", kept unchanged in the refit (D21)." if final_like else "; all settings per model are in `reports/checks/tuning_*.csv`."),
        "",
        to_markdown(chosen),
        "",
    ]
    if checks:
        text += ["## Sanity checks", "", *checks, ""]
    results_file.write_text("\n".join(text), encoding="utf-8")

    if mode == "final":
        thresholds = {M_A: thresholds_a[M_A], M_A_PRIME: thresholds_b[M_A_PRIME], M_B: thresholds_b[M_B]}
        save_final_models(fitted, thresholds)
        write_final_marker({"results": results_file.name, "resamples": n_resamples,
                            "rows_a": len(eval_a), "rows_b": len(eval_b), "thresholds": thresholds})

    for title, table in (("Scenario A", table_a), ("", diff_a), ("Scenario B rows", table_b), ("", diff_b),
                         ("M-A operating points per service", operating), ("Sensitivity", sensitivity), ("Chosen settings", chosen)):
        print(("\n=== " + title + " ===\n" if title else "\n") + table.to_string(index=False))
    if checks:
        print("\n" + "\n".join(checks))
    print(f"\nSaved: {results_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate all models (default: on validation).")
    parser.add_argument("--resamples", type=int, default=config.BOOTSTRAP_N, help="bootstrap resamples of whole days")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rehearsal", action="store_true", help="final procedure one step back in time; test period untouched")
    group.add_argument("--final", action="store_true", help="the single run on the test period")
    args = parser.parse_args()
    mode = "final" if args.final else "rehearsal" if args.rehearsal else "validation"
    if mode == "final":
        check_final_run_allowed()
    run(mode, args.resamples)


if __name__ == "__main__":
    main()
