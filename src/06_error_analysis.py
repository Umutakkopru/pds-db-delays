"""
Step 6: error analysis of the models (where and why they fail).

Works on the scores that src/05_train.py saved for every row of an evaluation
set. Today that is the validation set; the final run will write the same files
for the test period and this script then runs unchanged (the analysis code is
developed on validation, CLAUDE.md evaluation protocol).

Parts:
  1. Slices: scores of B2 and M-A per service, line, hour, weekday, month,
     holiday and weather; scores of B3 and M-B per service, horizon and delay
     at the previous stop.
  2. Calibration: predicted probability against observed delay rate.
  3. Confusion matrices at the validation thresholds.
  4. The 20 largest errors of M-A and M-B, grouped into failure types.

Reads:  data/processed/predictions_val_a.parquet, predictions_val_b.parquet   (step 5)
        data/processed/features_a.parquet, features_b.parquet                 (step 4)
        data/processed/wuerzburg_clean.parquet                                (step 2; delay in minutes, train number)
Writes: reports/error_analysis_validation.md
        reports/checks/error_slices_validation.csv
        reports/figures/errors_calibration_validation.png
        reports/figures/errors_rule_vs_model_validation.png

Usage: python src/06_error_analysis.py
"""
import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
import evaluate
import plot_style

EVALUATION_SET = "validation"
PREDICTIONS = {
    "A": config.DATA_PROCESSED / "predictions_val_a.parquet",
    "B": config.DATA_PROCESSED / "predictions_val_b.parquet",
}
FEATURES = {
    "A": config.DATA_PROCESSED / "features_a.parquet",
    "B": config.DATA_PROCESSED / "features_b.parquet",
}
CLEAN = config.DATA_PROCESSED / "wuerzburg_clean.parquet"
REPORT = config.REPORTS / f"error_analysis_{EVALUATION_SET}.md"
MIN_SLICE_ROWS = 300          # smaller slices are too noisy to report
N_LARGEST_ERRORS = 20
TARGET = "delayed"


# ----------------------------------------------------------------- data

def load(scenario: str) -> pd.DataFrame:
    """Scores joined with the features and with the realised delay (for analysis only, never a model input)."""
    return duckdb.sql(f"""
        SELECT p.*, f.* EXCLUDE (id, service_date, delayed, split_a, split_b),
               c.dep_delay, c.train_type, c.train_number
        FROM read_parquet('{PREDICTIONS[scenario]}') p
        JOIN read_parquet('{FEATURES[scenario]}') f USING (id)
        JOIN read_parquet('{CLEAN}') c USING (id)
    """).df()


def add_slice_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hour_band"] = pd.cut(out["planned_hour"], [-1, 5, 9, 15, 19, 23],
                              labels=["00-05", "06-09", "10-15", "16-19", "20-23"]).astype(str)
    out["weekday_name"] = out["weekday"].map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
    out["month"] = out["departure_planned_time"].dt.strftime("%Y-%m")
    out["day_type"] = np.select(
        [out["is_public_holiday"], out["is_bridge_day"], out["is_school_holiday"]],
        ["public holiday", "bridge day", "school holiday"], default="normal day")
    out["precipitation"] = np.where(out["precipitation_mm"] > 0, "rain or snow in the hour", "dry hour")
    out["wind"] = np.where(out["wind_gust_kmh"] >= 50, "gusts 50 km/h or more", "gusts under 50 km/h")
    out["frost"] = np.where(out["temperature_c"] < 0, "below 0 °C", "0 °C or warmer")
    out["line"] = out["line_id"].fillna("(no line: long-distance, night)")
    if "prev_delay" in out:
        out["previous_stop_delay"] = pd.cut(
            out["prev_delay"], [-np.inf, 0, 2, 5, 9, 19, np.inf],
            labels=["0 or early", "1-2 min", "3-5 min", "6-9 min", "10-19 min", "20+ min"]).astype(str)
        out["horizon"] = pd.cut(out["prev_minutes_to_departure"], [0, 20, 45, np.inf],
                                labels=["10-20 min", "20-45 min", "over 45 min"]).astype(str)
    return out


# ----------------------------------------------------------------- 1. slices

def slice_table(df: pd.DataFrame, columns: list[str], models: dict[str, float | None], scenario: str) -> pd.DataFrame:
    """
    One row per slice value and model.

    models: {score column: class threshold}. Rank metrics are computed inside the
    slice; precision, recall and F1 use the model's overall threshold, so they
    show what one fixed decision rule does in each slice.
    """
    rows = []
    for column in columns:
        for value, part in df.groupby(column, observed=True):
            y = part[TARGET].to_numpy()
            if len(part) < MIN_SLICE_ROWS or y.min() == y.max():
                continue
            for model, threshold in models.items():
                s = part[model].to_numpy()
                probability = model != "b3"
                row = {"scenario": scenario, "slice": column, "value": value, "model": model, "n": len(part),
                       "base_rate": y.mean(), **evaluate.score_metrics(y, s, probability=probability)}
                row.update({k: v for k, v in evaluate.class_metrics(y, s, threshold).items() if k != "accuracy"})
                row["mean_predicted"] = s.mean() if probability else np.nan
                rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- 2. calibration

def calibration_table(y: np.ndarray, proba: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Equal-width probability bins: mean prediction, observed rate and number of rows."""
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(proba, edges[1:-1]), 0, bins - 1)
    out = pd.DataFrame({"bin": index, "p": proba, "y": y}).groupby("bin").agg(
        mean_predicted=("p", "mean"), observed_rate=("y", "mean"), n=("y", "size")).reset_index()
    out["range"] = [f"{edges[i]:.1f}-{edges[i + 1]:.1f}" for i in out["bin"]]
    return out[["range", "n", "mean_predicted", "observed_rate"]]


def expected_calibration_error(table: pd.DataFrame) -> float:
    """Average gap between prediction and observed rate, weighted by the rows in each bin."""
    return float(((table["mean_predicted"] - table["observed_rate"]).abs() * table["n"]).sum() / table["n"].sum())


def calibration_figure(tables: dict[str, pd.DataFrame], path) -> None:
    plot_style.apply()
    fig, axes = plt.subplots(1, len(tables), figsize=(4.4 * len(tables), 4), sharey=True)
    for ax, (title, table) in zip(np.atleast_1d(axes), tables.items()):
        ax.plot([0, 100], [0, 100], color=plot_style.MUTED, linewidth=1, linestyle=(0, (3, 3)), label="perfect calibration")
        ax.plot(100 * table["mean_predicted"], 100 * table["observed_rate"], marker="o", color=plot_style.BLUE, label="model")
        ax.set_title(title, fontsize=10)
        ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.set_aspect("equal")
        ax.xaxis.set_major_formatter(plot_style.PCT); ax.yaxis.set_major_formatter(plot_style.PCT)
        ax.set_xlabel("Predicted probability of a delay")
    np.atleast_1d(axes)[0].set_ylabel("Observed share delayed")
    np.atleast_1d(axes)[0].legend(loc="upper left")
    fig.suptitle(f"Calibration on {EVALUATION_SET}: points on the dashed line mean honest probabilities",
                 x=0.02, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------- 3. rule against model

def rule_vs_model(b: pd.DataFrame, threshold_m_b: float) -> pd.DataFrame:
    """Accuracy of B3 (6-minute rule) and M-B per delay at the previous stop."""
    order = ["0 or early", "1-2 min", "3-5 min", "6-9 min", "10-19 min", "20+ min"]
    y = b[TARGET].astype(bool)
    work = pd.DataFrame({
        "previous_stop_delay": b["previous_stop_delay"],
        "delayed": y,
        "rule_right": (b["b3"] >= config.DELAY_THRESHOLD_MIN) == y,
        "model_right": (b["m_b"] >= threshold_m_b) == y,
    })
    out = work.groupby("previous_stop_delay").agg(
        n=("delayed", "size"), share_delayed=("delayed", "mean"),
        accuracy_rule=("rule_right", "mean"), accuracy_model=("model_right", "mean"))
    out = out.reindex([value for value in order if value in out.index]).reset_index()   # keep the order, skip empty bins
    out["n"] = out["n"].astype(int)
    out["errors_rule"] = (out["n"] * (1 - out["accuracy_rule"])).round().astype(int)
    out["errors_model"] = (out["n"] * (1 - out["accuracy_model"])).round().astype(int)
    return out


def rule_vs_model_figure(table: pd.DataFrame, path) -> None:
    plot_style.apply()
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    x = np.arange(len(table)); width = 0.36
    for k, (column, label, color) in enumerate([("errors_rule", "B3: 6-minute rule", plot_style.MUTED),
                                                 ("errors_model", "M-B: LightGBM", plot_style.BLUE)]):
        bars = ax.bar(x + (k - 0.5) * (width + 0.03), table[column], width=width, color=color, label=label)
        for bar, v in zip(bars, table[column]):
            ax.text(bar.get_x() + bar.get_width() / 2, v + table[["errors_rule", "errors_model"]].max().max() * 0.015,
                    f"{v:,}", ha="center", va="bottom", color=plot_style.INK2, fontsize=8.5)
    ax.set_xticks(x); ax.set_xticklabels(table["previous_stop_delay"])
    ax.set_xlabel("Delay at the previous stop"); ax.set_ylabel("Wrong predictions (departures)")
    ax.set_title(f"Where the rule and the model go wrong ({EVALUATION_SET})")
    ax.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------- 4. largest errors

def failure_type(row: pd.Series) -> str:
    """
    Name the kind of failure behind one badly wrong prediction.

    `row` is one departure with, among others: delayed (0/1), score (the model's
    probability), dep_delay (realised delay in minutes), service, planned_hour,
    and for scenario B prev_delay and prev_minutes_to_departure (missing for
    scenario A rows).
    """
    # TODO(human): return a short label for the failure type of this row.
    return "unclassified"


def largest_errors(df: pd.DataFrame, model: str, extra: list[str]) -> pd.DataFrame:
    """The rows where the predicted probability is furthest from the outcome."""
    work = df.assign(score=df[model], error=(df[TARGET] - df[model]).abs())
    top = work.nlargest(N_LARGEST_ERRORS, "error").copy()
    top["failure_type"] = top.apply(failure_type, axis=1)
    top["planned"] = top["departure_planned_time"].dt.strftime("%Y-%m-%d %H:%M")
    top["train"] = top["train_type"].astype(str) + " " + top["train_number"].astype(str)
    return top[["planned", "train", "destination", TARGET, "dep_delay", "score", *extra, "failure_type"]]


# ----------------------------------------------------------------- report

def md(df: pd.DataFrame, digits: int = 3) -> str:
    def cell(v):
        if isinstance(v, (float, np.floating)):
            return "–" if np.isnan(v) else f"{v:.{digits}f}"
        if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
            return f"{v:,}"
        return str(v)
    lines = ["| " + " | ".join(df.columns) + " |", "| " + " | ".join("---" for _ in df.columns) + " |"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def confusion(y: np.ndarray, score: np.ndarray, threshold: float) -> pd.DataFrame:
    pred = score >= threshold
    y = y.astype(bool)
    return pd.DataFrame({
        "": ["actually on time", "actually delayed"],
        "predicted on time": [int((~pred & ~y).sum()), int((~pred & y).sum())],
        "predicted delayed": [int((pred & ~y).sum()), int((pred & y).sum())],
    })


def pivot_slices(slices: pd.DataFrame, scenario: str, slice_name: str, metric: str, models: list[str]) -> pd.DataFrame:
    """Slices of one scenario ("A" or "B") as a wide table: one row per slice value, one column per model."""
    part = slices[(slices["slice"] == slice_name) & slices["scenario"].str.startswith(scenario)]
    wide = part.pivot(index="value", columns="model", values=metric)[models]
    wide.columns = [f"{metric} {m}" for m in models]
    base = part.drop_duplicates("value").set_index("value")[["n", "base_rate"]]
    return base.join(wide).reset_index().rename(columns={"value": slice_name})


def main() -> None:
    a = add_slice_columns(load("A"))
    b = add_slice_columns(load("B"))
    y_a, y_b = a[TARGET].to_numpy(), b[TARGET].to_numpy()
    thresholds = {
        "b2": evaluate.best_f1_threshold(y_a, a["b2"]), "m_a": evaluate.best_f1_threshold(y_a, a["m_a"]),
        "b3": float(config.DELAY_THRESHOLD_MIN), "m_b": evaluate.best_f1_threshold(y_b, b["m_b"]),
        "m_a_prime": evaluate.best_f1_threshold(y_b, b["m_a_prime"]),
    }

    slices = pd.concat([
        slice_table(a, ["service", "line", "hour_band", "weekday_name", "month", "day_type", "precipitation", "wind", "frost"],
                    {"b2": thresholds["b2"], "m_a": thresholds["m_a"]}, "A: all departures"),
        slice_table(b, ["service", "horizon", "previous_stop_delay", "month"],
                    {"b3": thresholds["b3"], "m_a_prime": thresholds["m_a_prime"], "m_b": thresholds["m_b"]},
                    "B: through trains with an earlier stop"),
    ], ignore_index=True)
    config.CHECKS.mkdir(parents=True, exist_ok=True)
    slices.round(4).to_csv(config.CHECKS / f"error_slices_{EVALUATION_SET}.csv", index=False)

    calibration = {
        "M-A (all departures)": calibration_table(y_a, a["m_a"].to_numpy()),
        "M-B (through trains)": calibration_table(y_b, b["m_b"].to_numpy()),
    }
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    calibration_figure(calibration, config.FIGURES / f"errors_calibration_{EVALUATION_SET}.png")
    versus = rule_vs_model(b, thresholds["m_b"])
    rule_vs_model_figure(versus, config.FIGURES / f"errors_rule_vs_model_{EVALUATION_SET}.png")

    errors_a = largest_errors(a, "m_a", ["hist_rate_route"])
    errors_b = largest_errors(b, "m_b", ["prev_delay", "prev_minutes_to_departure"])

    parts = [
        f"# Error analysis ({EVALUATION_SET})",
        "",
        f"Written by `src/06_error_analysis.py` from the scores of `src/05_train.py`. Set: {EVALUATION_SET} "
        f"({len(a):,} departures in scenario A, {len(b):,} through trains with an earlier stop in scenario B). "
        f"Slices with fewer than {MIN_SLICE_ROWS} departures are left out. All slice values are in "
        f"`reports/checks/error_slices_{EVALUATION_SET}.csv`.",
        "",
        "## 1. Scenario A by service: is M-A more than a service detector?",
        "",
        "PR-AUC and ROC-AUC are computed inside each service, where the service itself can no longer help.",
        "",
        md(pivot_slices(slices, "A", "service", "pr_auc", ["b2", "m_a"]).merge(
            pivot_slices(slices, "A", "service", "roc_auc", ["b2", "m_a"])[["service", "roc_auc b2", "roc_auc m_a"]], on="service")),
        "",
        "## 2. Scenario A by time, day type and weather (M-A)",
        "",
    ]
    for name in ["hour_band", "weekday_name", "month", "day_type", "precipitation", "wind", "frost"]:
        part = slices[(slices["slice"] == name) & (slices["model"] == "m_a") & slices["scenario"].str.startswith("A")]
        parts += [md(part[["value", "n", "base_rate", "mean_predicted", "pr_auc", "roc_auc", "precision", "recall", "f1"]]
                     .rename(columns={"value": name})), ""]
    parts += [
        "## 3. Scenario A by regional line (M-A)",
        "",
        md(slices[(slices["slice"] == "line") & (slices["model"] == "m_a")]
           [["value", "n", "base_rate", "mean_predicted", "pr_auc", "roc_auc", "recall"]].rename(columns={"value": "line"})),
        "",
        "## 4. Scenario B by service and horizon",
        "",
        md(pivot_slices(slices, "B", "service", "pr_auc", ["m_a_prime", "b3", "m_b"])),
        "",
        md(pivot_slices(slices, "B", "horizon", "pr_auc", ["m_a_prime", "b3", "m_b"])),
        "",
        "## 5. Scenario B: the rule against the model, by delay at the previous stop",
        "",
        f"Share of right decisions: B3 with its 6-minute rule, M-B at its validation threshold ({thresholds['m_b']:.3f}).",
        "",
        md(versus),
        "",
        f"![Rule against model](figures/errors_rule_vs_model_{EVALUATION_SET}.png)",
        "",
        "## 6. Calibration",
        "",
    ]
    for title, table in calibration.items():
        parts += [f"**{title}** — expected calibration error {expected_calibration_error(table):.3f}", "", md(table), ""]
    parts += [
        f"![Calibration](figures/errors_calibration_{EVALUATION_SET}.png)",
        "",
        "## 7. Confusion matrices",
        "",
        f"**M-A**, threshold {thresholds['m_a']:.3f}", "", md(confusion(y_a, a["m_a"].to_numpy(), thresholds["m_a"])), "",
        f"**M-B**, threshold {thresholds['m_b']:.3f}", "", md(confusion(y_b, b["m_b"].to_numpy(), thresholds["m_b"])), "",
        f"**B3**, rule at {config.DELAY_THRESHOLD_MIN} minutes", "", md(confusion(y_b, b["b3"].to_numpy(), thresholds["b3"])), "",
        f"## 8. The {N_LARGEST_ERRORS} largest errors",
        "",
        "Rows where the predicted probability is furthest from what happened. `score` is the predicted probability, "
        "`dep_delay` the realised delay in minutes (used here for the analysis only).",
        "",
        "**M-A**", "", md(errors_a), "", md(errors_a["failure_type"].value_counts().rename_axis("failure type").reset_index(name="rows")), "",
        "**M-B**", "", md(errors_b), "", md(errors_b["failure_type"].value_counts().rename_axis("failure type").reset_index(name="rows")), "",
    ]
    REPORT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved: {REPORT}")
    print(md(pivot_slices(slices, "A", "service", "pr_auc", ["b2", "m_a"])))
    print(md(pivot_slices(slices, "B", "service", "pr_auc", ["m_a_prime", "b3", "m_b"])))
    print(md(versus))
    for title, table in calibration.items():
        print(title, "ECE", round(expected_calibration_error(table), 4))


if __name__ == "__main__":
    main()
