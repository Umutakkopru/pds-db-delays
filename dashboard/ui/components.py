"""HTML/CSS building blocks: header, result card, route schematic, SHAP bars.

Every function returns an HTML string for `st.html`. Motion is pure CSS
(transform and opacity only; the counter is a rolling digit reel).
Streamlit only replaces a block when its HTML changes, so an animation plays
when the prediction changes and stays still on reruns with the same inputs.
"""
from __future__ import annotations

from html import escape

from predictor import Prediction

from .tokens import css_variables

STATIC_CSS = """
.dash, .dash * { box-sizing: border-box; }
.dash { color: var(--text); font-variant-numeric: tabular-nums; }
.dash .label { font-size: 13px; letter-spacing: .04em; text-transform: uppercase; color: var(--text-muted); margin: 0 0 8px; }
.dash .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; height: 100%; }
.dash .muted { color: var(--text-muted); }
.dash .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }

/* header */
.topbar { display: flex; flex-wrap: wrap; gap: 8px 24px; justify-content: space-between; align-items: baseline;
  background: var(--surface); border-bottom: 3px solid var(--brand); border-radius: 12px 12px 0 0; padding: 16px 24px; }
.topbar h1 { font-size: 22px; font-weight: 600; margin: 0; padding: 0; color: var(--text); }
.topbar .muted { font-size: 13px; }
.badge-dep { background: var(--badge-bg); color: var(--badge-text); font-size: 12px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; padding: 2px 8px; border-radius: 4px; margin-right: 10px; vertical-align: 3px; }

/* result card */
.hero-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; }
.hero-num { display: inline-flex; font-size: clamp(52px, 9vw, 72px); font-weight: 600; line-height: 1; }
.reel { display: inline-block; height: 1em; overflow: hidden; }
.reel-col { display: block; animation: roll .7s ease-out backwards; }
.reel-col span { display: block; height: 1em; }
.status { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; padding: 6px 12px;
  border-radius: 999px; animation: fade .3s ease-out .5s backwards; }
.status.low { color: var(--low); background: var(--low-fill); }
.status.medium { color: var(--medium); background: var(--medium-fill); }
.status.high { color: var(--high); background: var(--high-fill); }
.hero-text { font-size: 16px; margin: 16px 0 20px; }
.bar { position: relative; height: 10px; border-radius: 5px; background: var(--border); }
.bar-clip { position: absolute; inset: 0; border-radius: 5px; overflow: hidden; }
.bar-fill { width: 100%; height: 100%; animation: reveal .7s ease-out backwards;
  background: linear-gradient(to right, var(--low) 0 var(--mid), var(--medium) var(--mid) var(--thr), var(--high) var(--thr) 100%); }
.bar-tick { position: absolute; top: -5px; bottom: -5px; width: 2px; background: var(--text); }
.bar-scale { position: relative; height: 22px; margin-top: 8px; font-size: 13px; color: var(--text-muted); }
.bar-scale span { position: absolute; transform: translateX(-50%); white-space: nowrap; }

/* route schematic */
.route { position: relative; display: grid; grid-template-columns: repeat(var(--n), 1fr); margin-top: 28px; }
.route-rail { position: absolute; top: 9px; left: calc(50% / var(--n)); right: calc(50% / var(--n)); height: 0; }
.route-base { border-top: 2px dashed var(--border); }
.route-done { height: 3px; margin-top: -2.5px; border-radius: 2px; background: var(--line); transform-origin: left;
  transform: scaleX(var(--prog)); animation: grow .6s ease-out backwards; }
.route-train-wrap { position: absolute; left: 0; right: 0; top: -22px; transform: translateX(calc(var(--prog) * 100%));
  animation: glide .6s ease-out backwards; }
.route-train { width: 24px; height: 26px; margin-left: -12px; }
.train-body { display: block; position: relative; width: 24px; height: 22px; border-radius: 7px 7px 4px 4px; background: var(--line); }
.train-body::before { content: ''; position: absolute; left: 4px; right: 4px; top: 4px; height: 7px; border-radius: 2px; background: var(--surface); }
.train-body::after { content: ''; position: absolute; left: 5px; bottom: 4px; width: 4px; height: 4px; border-radius: 50%; background: var(--surface); box-shadow: 10px 0 0 var(--surface); }
.stop { text-align: center; padding: 0 4px; }
.stop .dot { display: block; width: 14px; height: 14px; margin: 3px auto 10px; border-radius: 50%;
  background: var(--surface); border: 3px solid var(--text-muted); position: relative; }
.stop.passed .dot { border-color: var(--line); }
.stop.dest .dot { border-color: var(--text); background: var(--text); }
.stop.live .dot::after { content: ''; position: absolute; inset: -7px; border-radius: 50%; border: 2px solid var(--line);
  animation: pulse 2.4s ease-out infinite; }
.stop .name { display: block; font-size: 14px; font-weight: 600; }
.stop .meta { display: block; font-size: 13px; color: var(--text-muted); min-height: 20px; }
.stop.live .meta { color: var(--text); font-weight: 600; animation: fade .3s ease-out .6s backwards; }
.route-note { font-size: 14px; margin: 20px 0 0; }

/* SHAP bars */
.shap-row { display: grid; grid-template-columns: minmax(120px, 2fr) 3fr 72px; gap: 12px; align-items: center; padding: 6px 0; }
.shap-name { font-size: 15px; }
.shap-track { position: relative; height: 18px; }
.shap-track::before { content: ''; position: absolute; left: 50%; top: -4px; bottom: -4px; width: 1px; background: var(--border); }
.shap-bar { position: absolute; top: 0; bottom: 0; border-radius: 3px; animation: grow .45s ease-out backwards; }
.shap-bar.up { left: 50%; background: var(--shap-up); transform-origin: left; }
.shap-bar.down { right: 50%; background: var(--shap-down); transform-origin: right; }
.shap-val { font-size: 15px; font-weight: 600; text-align: right; }
.shap-legend { display: flex; flex-wrap: wrap; gap: 6px 20px; font-size: 13px; margin-top: 14px; }
.shap-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; }

.calib { font-size: 14px; margin: 12px 0 0; }
.footer { font-size: 13px; line-height: 1.6; }

@keyframes roll { from { transform: translateY(0); } }
@keyframes grow { from { transform: scaleX(0); } }
@keyframes growY { from { transform: scaleY(0); } }
@keyframes glideY { from { transform: translateY(0); } }
@keyframes reveal { from { clip-path: inset(0 100% 0 0); } }
@keyframes fade { from { opacity: 0; } }
@keyframes glide { from { transform: translateX(0); } }
@keyframes pulse { 0% { transform: scale(.6); opacity: .9; } 100% { transform: scale(1.5); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .dash *, .dash *::after { animation: none !important; } }
@media (max-width: 640px) {
  .route { grid-template-columns: 1fr; grid-auto-rows: minmax(60px, 1fr); padding-left: 36px; margin-top: 12px; }
  .route-rail { top: calc(50% / var(--n)); bottom: calc(50% / var(--n)); left: 45px; right: auto; height: auto; width: 0; }
  .route-base { border-top: 0; border-left: 2px dashed var(--border); height: 100%; }
  .route-done { position: absolute; top: 0; left: -0.5px; width: 3px; height: 100%; margin: 0; transform-origin: top;
    transform: scaleY(var(--prog)); animation-name: growY; }
  .route-train-wrap { top: 0; bottom: 0; left: 0; right: auto; transform: translateY(calc(var(--prog) * 100%)); animation-name: glideY; }
  .route-train { margin: -13px 0 0 -40px; }
  .stop { display: grid; grid-template-columns: 20px 1fr; column-gap: 12px; align-content: center; text-align: left; padding: 0; }
  .stop .dot { grid-row: 1 / span 2; margin: 0 3px; align-self: center; }
  .stop .meta { min-height: 0; }
}
@media (max-width: 640px) { .shap-row { grid-template-columns: 1fr 64px; } .shap-track { grid-row: 2; grid-column: 1 / -1; } }

[data-testid="stMainBlockContainer"] { padding-top: 2.5rem; }

/* neutral primary action: red is reserved for "delayed" */
[data-testid="stFormSubmitButton"] button, [data-testid="stFormSubmitButton"] button:hover,
[data-testid="stFormSubmitButton"] button:active, [data-testid="stFormSubmitButton"] button:focus {
  background: var(--action-bg) !important; border-color: var(--action-bg) !important; color: var(--action-text) !important; font-weight: 600; }
[data-testid="stFormSubmitButton"] button * { color: inherit !important; }
[data-testid="stFormSubmitButton"] button:hover { opacity: .88; }
[data-testid="stFormSubmitButton"] button:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
"""

# Drawn with CSS: Streamlit's HTML sanitizer removes inline SVG.
TRAIN_HTML = '<span class="train-body"></span>'

RISK = {
    "low": ("&#10003;", "Low delay risk"),
    "medium": ("!", "Medium delay risk"),
    "high": ("&#9650;", "High delay risk"),
}


def _reel(value: int) -> str:
    """Digits as vertical reels that roll from 0 to their value (station-board feel)."""
    digits = "".join(f"<span>{d}</span>" for d in range(10))
    return "".join(
        f'<span class="reel"><span class="reel-col" style="transform:translateY(-{int(ch) * 10}%)">{digits}</span></span>'
        for ch in str(value)
    )


def risk_level(probability: float, threshold: float) -> str:
    """high: at or above the decision threshold; medium: upper half below it; else low."""
    if probability >= threshold:
        return "high"
    return "medium" if probability >= threshold / 2 else "low"


def global_css(theme: str) -> str:
    return f"<style>{css_variables(theme)}{STATIC_CSS}</style>"


def header() -> str:
    return (
        '<div class="dash"><div class="topbar"><h1><span class="badge-dep">Departure</span>'
        "Train delay risk at Würzburg Hbf</h1>"
        '<span class="muted">Data: Deutsche Bahn open data, CC BY 4.0</span></div></div>'
    )


def hero(pred: Prediction, calibration_note: str | None = None) -> str:
    note = f'<p class="calib muted">{escape(calibration_note)}</p>' if calibration_note else ""
    pct = round(pred.probability * 100)
    thr = round(pred.threshold * 100)
    level = risk_level(pred.probability, pred.threshold)
    icon, text = RISK[level]
    in_ten = round(pred.probability * 10)
    when = "before the trip" if pred.scenario == "A" else "with the train already en route"
    return f"""
<div class="dash"><div class="card">
  <p class="label">Probability of departing 6+ min late</p>
  <div class="hero-row">
    <span class="hero-num" aria-hidden="true">{_reel(pct)}<span>%</span></span><span class="sr-only">{pct}%</span>
    <span class="status {level}"><span aria-hidden="true">{icon}</span>{text}</span>
  </div>
  <p class="hero-text">About {in_ten} in 10 comparable departures leave at least 6 minutes late.
    <span class="muted">Estimated {when} (scenario {pred.scenario}).</span></p>
  <div class="bar" role="img" aria-label="Probability {pct}%, decision threshold {thr}%">
    <div class="bar-clip"><div class="bar-fill" style="--mid:{thr / 2:.1f}%;--thr:{thr}%;clip-path:inset(0 {100 - pct}% 0 0)"></div></div>
    <div class="bar-tick" style="left:{thr}%"></div>
  </div>
  <div class="bar-scale"><span style="left:{thr}%">decision threshold {thr}%</span></div>{note}
</div></div>"""


def route(pred: Prediction, prev_stop_delay: int | None) -> str:
    stops = pred.stops
    n = len(stops)
    live = n - 2 if pred.scenario == "B" else None  # last stop before Würzburg Hbf
    progress = (live / (n - 1)) if live else 0.0
    line = "var(--scenario-b)" if pred.scenario == "B" else "var(--scenario-a)"
    cells = []
    for i, name in enumerate(stops):
        cls, meta = "stop", ""
        if i == n - 1:
            cls, meta = "stop dest", "predicted here"
        elif live is not None and i == live:
            cls, meta = "stop passed live", f"+{prev_stop_delay} min"
        elif live is not None and i < live:
            cls = "stop passed"
        elif i == 0 and live is None:
            meta = "not departed"
        cells.append(f'<div class="{cls}"><span class="dot"></span><span class="name">{escape(name)}</span>'
                     f'<span class="meta">{meta}</span></div>')
    note = (
        "Scenario B: the delay at the previous stop is known and used by the model."
        if pred.scenario == "B"
        else "Scenario A: only timetable, calendar and history are known. Add the delay at the previous stop to switch to scenario B."
    )
    return f"""
<div class="dash"><div class="card">
  <p class="label">What the model knows</p>
  <div class="route" style="--n:{n};--line:{line};--prog:{progress:.3f}">
    <div class="route-rail">
      <div class="route-base"></div>
      <div class="route-done"></div>
      <div class="route-train-wrap"><div class="route-train" aria-hidden="true">{TRAIN_HTML}</div></div>
    </div>
    {''.join(cells)}
  </div>
  <p class="route-note muted">{note}</p>
</div></div>"""


def shap_bars(pred: Prediction, max_rows: int = 7) -> str:
    items = pred.contributions
    if len(items) > max_rows:
        rest = sum(v for _, v in items[max_rows - 1:])
        items = items[: max_rows - 1] + [("Other features", rest)]
    biggest = max((abs(v) for _, v in items), default=0) or 1
    rows = []
    for i, (label, value) in enumerate(items):
        direction = "up" if value >= 0 else "down"
        width = abs(value) / biggest * 50
        sign = "+" if value >= 0 else "&minus;"
        rows.append(
            f'<div class="shap-row"><span class="shap-name">{escape(label)}</span>'
            f'<span class="shap-track"><span class="shap-bar {direction}" style="width:{width:.1f}%;animation-delay:{i * 40}ms"></span></span>'
            f'<span class="shap-val">{sign}{abs(value) * 100:.0f} pts</span></div>'
        )
    return f"""
<div class="dash"><div class="card">
  <p class="label">Why this prediction?</p>
  {''.join(rows)}
  <div class="shap-legend muted">
    <span><i style="background:var(--shap-up)"></i>raises the delay risk</span>
    <span><i style="background:var(--shap-down)"></i>lowers the delay risk</span>
    <span>Average {pred.base_value * 100:.0f}% &rarr; this departure {pred.probability * 100:.0f}% (percentage points)</span>
  </div>
</div></div>"""


def footer() -> str:
    return (
        '<div class="dash"><p class="footer muted">University project (Practical Data Science, Uni Würzburg). '
        "Not affiliated with Deutsche Bahn. Predictions are statistical estimates from historical data and cannot "
        "see disruptions that are not in the data.</p></div>"
    )
