"""Prediction interface used by the dashboard.

The app only talks to `Predictor`. `ModelPredictor` loads the saved LightGBM
models (scenario A: M-A, scenario B: M-B) and the small lookup tables written
by `src/08_dashboard_data.py`; it never reads the raw or processed data.
`DemoPredictor` returns deterministic PLACEHOLDER values and is used only when
the models or the lookup tables are missing.

Input:  ../models/m_a.{txt,json}, ../models/m_b.{txt,json}   (final run)
        data/*.parquet, data/meta.json                        (python src/08_dashboard_data.py)
Output: `Prediction` objects for the page.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MODELS_DIR = HERE.parent / "models"
DESTINATION = "Würzburg Hbf"
MIN_CALIBRATION_ROWS = 50   # a reliability bin with fewer test departures gives no note

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(5, 24))


@dataclass(frozen=True)
class Query:
    line: str
    day: date
    hour: int
    prev_stop_delay: int | None  # minutes; None -> scenario A


@dataclass(frozen=True)
class Prediction:
    probability: float  # P(departure delay >= 6 min)
    threshold: float  # decision threshold chosen on validation (max F1)
    base_value: float  # average predicted probability (SHAP base value)
    contributions: list[tuple[str, float]]  # (feature label, probability points)
    scenario: str  # "A" or "B"
    stops: list[str]  # earlier stops, ending with "Würzburg Hbf"


class Predictor(Protocol):
    is_demo: bool

    def lines(self) -> list[str]: ...
    def predict(self, query: Query) -> Prediction: ...
    def delay_rate_grid(self, line: str) -> list[list[float]]: ...
    def calibration_note(self, probability: float) -> str | None: ...


class DemoPredictor:
    """Placeholder values. Not model output and not real delay statistics."""

    is_demo = True
    _LINES = {
        "ICE (long-distance)": (0.10, ["Nürnberg Hbf", "Würzburg Hbf"]),
        "RE (regional express)": (0.02, ["Kitzingen", "Rottendorf", "Würzburg Hbf"]),
        "RB (regional)": (-0.04, ["Würzburg Süd", "Würzburg Hbf"]),
    }

    def lines(self) -> list[str]:
        return list(self._LINES)

    def _parts(self, q: Query) -> list[tuple[str, float]]:
        line_effect, _ = self._LINES[q.line]
        rush = 0.07 * math.exp(-((q.hour - 17) ** 2) / 8) + 0.04 * math.exp(-((q.hour - 8) ** 2) / 6)
        weekday = -0.04 if q.day.weekday() >= 5 else 0.02
        parts = [
            (f"Train type = {q.line.split(' ')[0]}", line_effect),
            (f"Hour = {q.hour:02d}:00", rush - 0.03),
            (f"Weekday = {WEEKDAYS[q.day.weekday()]}", weekday),
            ("Line delay rate, last 28 days", 0.03),
        ]
        if q.prev_stop_delay is not None:
            parts.append((f"Delay at previous stop = {q.prev_stop_delay} min", 0.045 * (q.prev_stop_delay - 3)))
        return parts

    def predict(self, q: Query) -> Prediction:
        base = 0.20
        parts = self._parts(q)
        raw = base + sum(v for _, v in parts)
        prob = min(0.97, max(0.02, raw))
        # keep contributions consistent with the clipped probability
        scale = (prob - base) / (raw - base) if raw != base else 1.0
        parts = [(label, v * scale) for label, v in parts]
        return Prediction(
            probability=prob,
            threshold=0.35,
            base_value=base,
            contributions=sorted(parts, key=lambda p: -abs(p[1])),
            scenario="A" if q.prev_stop_delay is None else "B",
            stops=self._LINES[q.line][1],
        )

    def delay_rate_grid(self, line: str) -> list[list[float]]:
        line_effect, _ = self._LINES[line]
        grid = []
        for d in range(7):
            row = []
            for h in HOURS:
                rush = 0.12 * math.exp(-((h - 17) ** 2) / 8) + 0.07 * math.exp(-((h - 8) ** 2) / 6)
                row.append(round(max(0.03, 0.14 + line_effect + rush - (0.05 if d >= 5 else 0)), 3))
            grid.append(row)
        return grid

    def calibration_note(self, probability: float) -> str | None:
        """Real predictor: e.g. 'When the model says ~40%, 38% of test departures were late.'"""
        return None  # needs the reliability table from the test set; nothing is shown in demo mode


# Plain-language labels of the model features: (text, unit or kind).
FEATURE_LABELS = {
    "service": ("Type of train", "service"),
    "line_id": ("Line", "text"),
    "destination": ("Destination", "text"),
    "planned_hour": ("Hour", "hour"),
    "weekday": ("Weekday", "weekday"),
    "is_through": ("Passes through Würzburg", "flag"),
    "stop_position": ("Stop number on the route", "count"),
    "dwell_min": ("Planned stop at Würzburg", "min"),
    "is_public_holiday": ("Public holiday", "flag"),
    "is_school_holiday": ("School holiday", "flag"),
    "is_bridge_day": ("Bridge day", "flag"),
    "temperature_c": ("Temperature", "°C"),
    "precipitation_mm": ("Precipitation", "mm"),
    "wind_speed_kmh": ("Wind", "km/h"),
    "wind_gust_kmh": ("Wind gusts", "km/h"),
    "snowfall_cm": ("Snowfall", "cm"),
    "snow_depth_m": ("Snow depth", "m"),
    "hist_rate_service_hour": ("Delay rate of this train type and hour, last 28 days", "rate"),
    "hist_rate_route": ("Delay rate of this route, last 28 days", "rate"),
    "hist_n_route": ("Departures on this route, last 28 days", "count"),
    "hist_rate_all": ("Delay rate of all departures, last 28 days", "rate"),
    "prev_delay": ("Delay at previous stop", "min"),
    "prev_delay_2": ("Delay at the stop before that", "min"),
    "prev_minutes_to_departure": ("Planned time since previous stop", "min"),
    "prev_stops_between": ("Stops skipped in the data", "count"),
}
SERVICE_NAMES = {"long_distance": "long-distance", "night": "night train", "regional": "regional", "other": "other"}
FLAGS = ("is_through", "is_public_holiday", "is_school_holiday", "is_bridge_day")


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def feature_label(name: str, value) -> str:
    """'Hour = 17:00', 'Delay at previous stop = 10 min', 'Temperature = not available'."""
    text, kind = FEATURE_LABELS[name]
    if _missing(value):
        return f"{text} = not available"
    if kind == "service":
        shown = SERVICE_NAMES.get(value, str(value))
    elif kind == "text":
        shown = str(value)
    elif kind == "hour":
        shown = f"{int(value):02d}:00"
    elif kind == "weekday":
        shown = WEEKDAYS[int(value)]
    elif kind == "flag":
        shown = "yes" if value else "no"
    elif kind == "rate":
        shown = f"{100 * float(value):.0f}%"
    elif kind == "count":
        shown = f"{float(value):.0f}"
    else:
        shown = f"{float(value):.0f} {kind}"
    return f"{text} = {shown}"


def to_probability_points(log_odds: list[float], base_log_odds: float) -> tuple[float, float, list[float]]:
    """
    Turn SHAP values in log-odds into contributions in probability points.

    SHAP values of a LightGBM classifier add up in log-odds: base + sum = raw score.
    A probability is not additive in the features, so the log-odds contributions are
    rescaled by one common factor such that base probability + contributions equals
    the predicted probability exactly. Every contribution keeps its sign and its share
    of the total. Returns (probability, base probability, contributions).
    """
    total = sum(log_odds)
    probability = 1 / (1 + math.exp(-(base_log_odds + total)))
    base = 1 / (1 + math.exp(-base_log_odds))
    if abs(total) < 1e-12:
        return probability, base, [0.0 for _ in log_odds]
    factor = (probability - base) / total
    return probability, base, [v * factor for v in log_odds]


class ModelPredictor:
    """
    The saved final models behind the page.

    A query (line, day, hour) is answered for a typical departure of that line in
    that hour: timetable values are the line's medians, calendar, weather and the
    28-day delay rates are those of the chosen day (see src/08_dashboard_data.py).
    Scenario A (model M-A) is used when no delay at the previous stop is given,
    scenario B (model M-B) when it is given. A line that starts at Würzburg has no
    previous stop: it is always answered by scenario A.
    """

    is_demo = False

    def __init__(self, data_dir: Path = DATA_DIR, models_dir: Path = MODELS_DIR) -> None:
        import lightgbm as lgb
        import pandas as pd

        self._pd = pd
        self._models = {}
        for scenario, slug in (("A", "m_a"), ("B", "m_b")):
            info = json.loads((models_dir / f"{slug}.json").read_text(encoding="utf-8"))
            self._models[scenario] = {
                "booster": lgb.Booster(model_file=str(models_dir / f"{slug}.txt")),
                "features": info["features"], "categories": info["categories"],
                "threshold": float(info["threshold"]),     # max-F1 threshold chosen on validation (final run)
            }
        self._meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
        lines = pd.read_parquet(data_dir / "lines.parquet")
        self._lines = {row["label"]: row for row in lines.to_dict("records")}
        profiles = pd.read_parquet(data_dir / "profiles.parquet")
        self._profiles = {(r["label"], int(r["hour"])): r for r in profiles.to_dict("records")}
        days = pd.read_parquet(data_dir / "days.parquet")
        self._days = {pd.Timestamp(r["service_date"]).date(): r for r in days.to_dict("records")}
        weather = pd.read_parquet(data_dir / "weather.parquet")
        self._weather = {(pd.Timestamp(r["service_date"]).date(), int(r["hour"])): r for r in weather.to_dict("records")}
        history = pd.read_parquet(data_dir / "history.parquet")
        self._history = {(pd.Timestamp(r["service_date"]).date(), r["kind"], r["key"], int(r["hour"])): r
                         for r in history.to_dict("records")}
        grid = pd.read_parquet(data_dir / "grid.parquet")
        self._grid = {(r["label"], int(r["weekday"]), int(r["hour"])): float(r["delay_rate"]) for r in grid.to_dict("records")}
        self._last_scenario = "A"

    # ------------------------------------------------------------- contract

    @property
    def date_range(self) -> tuple[date, date]:
        """First and last day the lookup tables cover (the test period)."""
        return date.fromisoformat(self._meta["first_day"]), date.fromisoformat(self._meta["last_day"])

    def lines(self) -> list[str]:
        return list(self._lines)

    def scenario_for(self, query: Query) -> str:
        """B when a previous-stop delay is given and the line has a previous stop, else A."""
        return "B" if query.prev_stop_delay is not None and self._lines[query.line]["has_scenario_b"] else "A"

    def features(self, query: Query, scenario: str) -> dict:
        """Feature values of the typical departure that the query describes."""
        line = self._lines[query.line]
        profile = self._profiles.get((query.line, query.hour), line)       # no train in that hour: the line's medians
        day = self._days.get(query.day, {})
        weather = self._weather.get((query.day, query.hour), {})
        route_key = line["line_id"] if isinstance(line["line_id"], str) else line["destination"]
        by_hour = self._history.get((query.day, "service_hour", line["service"], query.hour), {})
        by_route = self._history.get((query.day, "route", route_key, -1), {})
        nan = float("nan")
        values = {
            "service": line["service"], "line_id": line["line_id"], "destination": line["destination"],
            "planned_hour": query.hour, "weekday": query.day.weekday(), "is_through": bool(line["is_through"]),
            "stop_position": profile["stop_position"], "dwell_min": profile["dwell_min"],
            "is_public_holiday": bool(day.get("is_public_holiday", False)),
            "is_school_holiday": bool(day.get("is_school_holiday", False)),
            "is_bridge_day": bool(day.get("is_bridge_day", False)),
            "temperature_c": weather.get("temperature_c", nan), "precipitation_mm": weather.get("precipitation_mm", nan),
            "wind_speed_kmh": weather.get("wind_speed_kmh", nan), "wind_gust_kmh": weather.get("wind_gust_kmh", nan),
            "snowfall_cm": weather.get("snowfall_cm", nan), "snow_depth_m": weather.get("snow_depth_m", nan),
            "hist_rate_service_hour": by_hour.get("rate", nan), "hist_rate_route": by_route.get("rate", nan),
            "hist_n_route": by_route.get("n", nan), "hist_rate_all": day.get("hist_rate_all", nan),
        }
        if scenario == "B":
            values.update({
                "prev_delay": float(query.prev_stop_delay),
                # the stop before the previous one is not asked for: its delay is taken to be the same
                "prev_delay_2": float(query.prev_stop_delay),
                "prev_minutes_to_departure": line["prev_minutes_to_departure"],
                "prev_stops_between": line["prev_stops_between"],
            })
        return values

    def frame(self, rows: list[dict], scenario: str):
        """Model input: exactly the model's feature columns, text columns with the training categories."""
        pd = self._pd
        model = self._models[scenario]
        X = pd.DataFrame(rows)[model["features"]].copy()
        for name in model["features"]:
            if name in model["categories"]:
                X[name] = pd.Categorical(X[name], categories=model["categories"][name])
            elif name in FLAGS:
                X[name] = X[name].astype("int8")
            else:
                X[name] = X[name].astype("float64")
        return X

    def probabilities(self, rows: list[dict], scenario: str) -> list[float]:
        """Model probabilities for rows of feature values (used by the tests to compare with the final run)."""
        return [float(p) for p in self._models[scenario]["booster"].predict(self.frame(rows, scenario))]

    def predict(self, query: Query) -> Prediction:
        scenario = self.scenario_for(query)
        model = self._models[scenario]
        values = self.features(query, scenario)
        contrib = model["booster"].predict(self.frame([values], scenario), pred_contrib=True)[0]
        probability, base, points = to_probability_points([float(v) for v in contrib[:-1]], float(contrib[-1]))
        parts = [(feature_label(name, values[name]), value) for name, value in zip(model["features"], points)]
        line = self._lines[query.line]
        earlier = line["earlier_stops"].split("|") if line["has_scenario_b"] else []
        self._last_scenario = scenario
        return Prediction(
            probability=probability,
            threshold=model["threshold"],
            base_value=base,
            contributions=sorted(parts, key=lambda p: -abs(p[1])),
            scenario=scenario,
            stops=[*earlier, DESTINATION],
        )

    def delay_rate_grid(self, line: str) -> list[list[float]]:
        """7 x 19 grid (Mon-Sun x 05-23 h) of delay rates over the data period; None where the line rarely runs."""
        return [[self._grid.get((line, weekday, hour)) for hour in HOURS] for weekday in range(7)]

    def calibration_note(self, probability: float) -> str | None:
        """One sentence from the reliability table of the test period, for the model of the last prediction."""
        table = self._meta["calibration"][self._last_scenario]
        index = min(int(probability * 10), 9)
        row = next((r for r in table if r["range"] == f"{index / 10:.1f}-{(index + 1) / 10:.1f}"), None)
        if row is None or row["n"] < MIN_CALIBRATION_ROWS:
            return None
        return (f"Check on the test period: of {row['n']:,} real departures scored {index * 10}–{(index + 1) * 10}%, "
                f"{100 * row['observed_rate']:.0f}% left 6+ min late.")


@lru_cache(maxsize=1)
def load_predictor() -> Predictor:
    """The model-backed predictor; the placeholder one if the models or lookup tables are missing."""
    try:
        return ModelPredictor()
    except (FileNotFoundError, ImportError) as error:
        print(f"Dashboard runs in demo mode: {error}")
        return DemoPredictor()
