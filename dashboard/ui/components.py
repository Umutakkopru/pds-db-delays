"""HTML/CSS building blocks: header, result card, route schematic, SHAP bars, chart cards.

Every function returns an HTML string for `st.html`. Motion is pure CSS
(transform and opacity only; the counter is a rolling digit reel).
Streamlit only replaces a block when its HTML changes, so an animation plays
when the prediction changes and stays still on reruns with the same inputs.

Sizing: every length is in rem, and on desktop screens the root font size follows
the window (`html { font-size: clamp(...) }`), so the whole page, Streamlit's own
widgets included, scales as one piece and looks the same on a laptop and on a 4K
screen. From 1024 x 600 px up the page fits one screen without scrolling: the two
card rows share the height left below the header and the inputs (`--row-h`).
Smaller screens (phones, tablets, short windows) stack the cards and scroll.
"""
from __future__ import annotations

from html import escape

from predictor import Prediction

from .tokens import css_variables

STATIC_CSS = """
.dash, .dash * { box-sizing: border-box; }
.dash { color: var(--text); font-variant-numeric: tabular-nums; }
.dash .label { font-size: .8125rem; letter-spacing: .04em; text-transform: uppercase; color: var(--text-muted); margin: 0 0 .5rem; }
.dash .card { background: var(--surface); border: 1px solid var(--border); border-radius: .75rem; padding: 1.25rem 1.5rem;
  display: flex; flex-direction: column; }
.dash .card-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.dash .muted { color: var(--text-muted); }
.dash .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }

/* header: the bar is the Streamlit container "topbar" (title + "How it works" button) */
.st-key-topbar { background: var(--surface); border-bottom: .1875rem solid var(--brand); border-radius: .75rem .75rem 0 0;
  padding: .9rem 1.5rem; }
.topbar h1 { font-size: 1.875rem; font-weight: 650; line-height: 1.2; margin: 0; padding: 0; color: var(--text); }
.topbar .sub { font-size: .875rem; margin: .3rem 0 0; }
.badge-dep { display: inline-block; background: var(--badge-bg); color: var(--badge-text); font-size: .8rem; font-weight: 650;
  letter-spacing: .05em; text-transform: uppercase; padding: .15rem .55rem; border-radius: .25rem; margin-right: .75rem;
  vertical-align: .3rem; }

/* result card */
.hero-row { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem 1.25rem; }
.hero-num { display: inline-flex; font-size: 3.75rem; font-weight: 600; line-height: 1; }
.reel { display: inline-block; height: 1em; overflow: hidden; }
.reel-col { display: block; animation: roll .7s ease-out backwards; }
.reel-col span { display: block; height: 1em; }
.status { display: inline-flex; align-items: center; gap: .5rem; font-weight: 600; font-size: 1rem; padding: .375rem .75rem;
  border-radius: 999px; animation: fade .3s ease-out .5s backwards; }
.status.low { color: var(--low); background: var(--low-fill); }
.status.medium { color: var(--medium); background: var(--medium-fill); }
.status.high { color: var(--high); background: var(--high-fill); }
.hero-text { font-size: 1rem; margin: .9rem 0 1rem; }
.bar { position: relative; height: .625rem; border-radius: .3125rem; background: var(--border); }
.bar-clip { position: absolute; inset: 0; border-radius: .3125rem; overflow: hidden; }
.bar-fill { width: 100%; height: 100%; animation: reveal .7s ease-out backwards;
  background: linear-gradient(to right, var(--low) 0 var(--mid), var(--medium) var(--mid) var(--thr), var(--high) var(--thr) 100%); }
.bar-tick { position: absolute; top: -.3125rem; bottom: -.3125rem; width: .125rem; background: var(--text); }
.bar-scale { position: relative; height: 1.375rem; margin-top: .5rem; font-size: .8125rem; color: var(--text-muted); }
.bar-scale span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.calib { font-size: .875rem; margin: .5rem 0 0; }

/* route schematic */
.route { position: relative; display: grid; grid-template-columns: repeat(var(--n), 1fr); margin-top: 1.75rem; }
.route-rail { position: absolute; top: .5625rem; left: calc(50% / var(--n)); right: calc(50% / var(--n)); height: 0; }
.route-base { border-top: .125rem dashed var(--border); }
.route-done { height: .1875rem; margin-top: -.15625rem; border-radius: .125rem; background: var(--line); transform-origin: left;
  transform: scaleX(var(--prog)); animation: grow .6s ease-out backwards; }
.route-train-wrap { position: absolute; left: 0; right: 0; top: -1.375rem; transform: translateX(calc(var(--prog) * 100%));
  animation: glide .6s ease-out backwards; }
.route-train { width: 1.5rem; height: 1.625rem; margin-left: -.75rem; }
.train-body { display: block; position: relative; width: 1.5rem; height: 1.375rem; border-radius: .4375rem .4375rem .25rem .25rem; background: var(--line); }
.train-body::before { content: ''; position: absolute; left: .25rem; right: .25rem; top: .25rem; height: .4375rem; border-radius: .125rem; background: var(--surface); }
.train-body::after { content: ''; position: absolute; left: .3125rem; bottom: .25rem; width: .25rem; height: .25rem; border-radius: 50%;
  background: var(--surface); box-shadow: .625rem 0 0 var(--surface); }
.stop { text-align: center; padding: 0 .25rem; }
.stop .dot { display: block; width: .875rem; height: .875rem; margin: .1875rem auto .625rem; border-radius: 50%;
  background: var(--surface); border: .1875rem solid var(--text-muted); position: relative; }
.stop.passed .dot { border-color: var(--line); }
.stop.dest .dot { border-color: var(--text); background: var(--text); }
.stop.live .dot::after { content: ''; position: absolute; inset: -.4375rem; border-radius: 50%; border: .125rem solid var(--line);
  animation: pulse 2.4s ease-out infinite; }
.stop .name { display: block; font-size: .875rem; font-weight: 600; }
.stop .meta { display: block; font-size: .8125rem; color: var(--text-muted); min-height: 1.25rem; }
.stop.live .meta { color: var(--text); font-weight: 600; animation: fade .3s ease-out .6s backwards; }
.route-note { font-size: .875rem; margin: auto 0 0; padding-top: 1rem; }

/* SHAP bars: the rows share the card height */
.shap-rows { flex: 1; display: flex; flex-direction: column; justify-content: space-evenly; min-height: 0; }
.shap-row { display: grid; grid-template-columns: minmax(7.5rem, 2.2fr) 3fr 4rem; gap: .75rem; align-items: center; padding: .2rem 0; }
.shap-name { font-size: .9rem; line-height: 1.25; }
.shap-track { position: relative; height: 1rem; }
.shap-track::before { content: ''; position: absolute; left: 50%; top: -.25rem; bottom: -.25rem; width: 1px; background: var(--border); }
.shap-bar { position: absolute; top: 0; bottom: 0; border-radius: .1875rem; animation: grow .45s ease-out backwards; }
.shap-bar.up { left: 50%; background: var(--shap-up); transform-origin: left; }
.shap-bar.down { right: 50%; background: var(--shap-down); transform-origin: right; }
.shap-val { font-size: .9rem; font-weight: 600; text-align: right; }
.shap-legend { display: flex; flex-wrap: wrap; gap: .25rem 1.25rem; font-size: .8125rem; margin-top: .6rem; }
.shap-legend i { display: inline-block; width: .625rem; height: .625rem; border-radius: .125rem; margin-right: .375rem; }

/* heatmap (HTML grid, stretches with its card) */
.chart-sub { font-size: .8125rem; margin: -.25rem 0 .6rem; }
.hm { flex: 1; min-height: 9rem; display: grid; grid-template-columns: 2.25rem repeat(var(--cols), 1fr);
  grid-template-rows: repeat(7, 1fr) auto; gap: .125rem; }
.hm-y { font-size: .75rem; color: var(--text-muted); align-self: center; }
.hm-x { font-size: .75rem; color: var(--text-muted); text-align: center; padding-top: .25rem; }
.hm-cell { border-radius: .1875rem; min-height: .5rem; }
.hm-cell.empty { background: repeating-linear-gradient(45deg, transparent 0 .25rem, var(--border) .25rem .3rem); opacity: .5; }
.hm-cell.sel { outline: .1875rem solid var(--text); outline-offset: -.0625rem; position: relative; z-index: 1; }
.hm-legend { display: flex; flex-wrap: wrap; align-items: center; gap: .25rem .5rem; font-size: .75rem; margin-top: .5rem; }
.hm-legend i { display: inline-block; width: 7rem; height: .5rem; border-radius: .25rem; }
.hm-legend-sel { margin-left: auto; }

/* day profile: one bar per hour */
.dp { flex: 1; min-height: 8rem; display: flex; flex-direction: column; }
.dp-plot { position: relative; flex: 1; display: flex; align-items: flex-end; gap: .2rem; border-bottom: 1px solid var(--border); }
.dp-col { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.dp-bar { position: relative; width: 100%; border-radius: .1875rem .1875rem 0 0; opacity: .45; transform-origin: bottom;
  animation: growY .5s ease-out backwards; }
.dp-bar.low { background: var(--low); } .dp-bar.medium { background: var(--medium); } .dp-bar.high { background: var(--high); }
.dp-bar.sel, .dp-bar.best { opacity: 1; }
.dp-bar.sel { box-shadow: 0 0 0 .125rem var(--text); }
.dp-bar.best { box-shadow: 0 0 0 .125rem var(--focus); }
.dp-bar em { position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: .2rem;
  font-style: normal; font-size: .75rem; font-weight: 650; color: var(--text); white-space: nowrap; }
.dp-thr { position: absolute; left: 0; right: 0; border-top: .125rem dashed var(--text-muted); z-index: 1; pointer-events: none; }
.dp-thr b { position: absolute; right: 0; bottom: .15rem; font-size: .7rem; font-weight: 500; color: var(--text-muted);
  background: var(--surface); padding: 0 .25rem; }
.dp-x { display: flex; gap: .2rem; }
.dp-x span { flex: 1; text-align: center; font-size: .75rem; color: var(--text-muted); padding-top: .25rem; }
.dp-note { font-size: .8125rem; margin: .5rem 0 0; }

@keyframes roll { from { transform: translateY(0); } }
@keyframes grow { from { transform: scaleX(0); } }
@keyframes growY { from { transform: scaleY(0); } }
@keyframes glideY { from { transform: translateY(0); } }
@keyframes reveal { from { clip-path: inset(0 100% 0 0); } }
@keyframes fade { from { opacity: 0; } }
@keyframes glide { from { transform: translateX(0); } }
@keyframes pulse { 0% { transform: scale(.6); opacity: .9; } 100% { transform: scale(1.5); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .dash *, .dash *::after { animation: none !important; } }

/* Streamlit chrome: less empty space, neutral primary action (red is reserved for "delayed") */
[data-testid="stMainBlockContainer"] { padding: 3.5rem 1.5rem 1.5rem; }
[data-testid="stFormSubmitButton"] button, [data-testid="stFormSubmitButton"] button:hover,
[data-testid="stFormSubmitButton"] button:active, [data-testid="stFormSubmitButton"] button:focus {
  background: var(--action-bg) !important; border-color: var(--action-bg) !important; color: var(--action-text) !important; font-weight: 600; }
[data-testid="stFormSubmitButton"] button * { color: inherit !important; }
[data-testid="stFormSubmitButton"] button:hover { opacity: .88; }
[data-testid="stFormSubmitButton"] button:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }

/* One screen on desktop: fluid root size, the two card rows share the remaining height */
@media (min-width: 1024px) and (min-height: 600px) {
  html { font-size: clamp(12px, min(1.06vw, 1.72vh), 26px); }
  [data-testid="stHeader"] { background: transparent; height: 0; }
  [data-testid="stToolbar"] { top: .4rem; right: .4rem; }
  [data-testid="stMainBlockContainer"] { padding: .75rem 1.5rem .75rem; max-width: none; }
  .st-key-topbar { margin-right: 2.75rem; }
  :root { --row-h: calc((100dvh - var(--chrome, 15.5rem)) / 2); }
  .dash .card.fit { height: var(--row-h); overflow: hidden; }
}
@media (max-width: 1023px), (max-height: 599px) {
  .hm { min-height: 13rem; } .dp { min-height: 11rem; }
}
@media (max-width: 640px) {
  .hero-num { font-size: 3.25rem; }
  .topbar h1 { font-size: 1.4rem; }
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
  .shap-row { grid-template-columns: 1fr 64px; } .shap-track { grid-row: 2; grid-column: 1 / -1; }
}
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
    """Title and source line; sits in the "topbar" container next to the "How it works" button."""
    return (
        '<div class="dash topbar"><h1><span class="badge-dep">Departure</span>Train delay risk at Würzburg Hbf</h1>'
        '<p class="sub muted">Data: Deutsche Bahn open data, CC BY 4.0 · University project (Practical Data Science, '
        "Uni Würzburg), not affiliated with Deutsche Bahn</p></div>"
    )


def card(label: str, body: str, sub: str = "") -> str:
    """A card that fills its row on desktop; `body` is stretched to the remaining height."""
    sub_html = f'<p class="chart-sub muted">{sub}</p>' if sub else ""
    return (f'<div class="dash"><div class="card fit"><p class="label">{label}</p>{sub_html}'
            f'<div class="card-body">{body}</div></div></div>')


def hero(pred: Prediction, calibration_note: str | None = None) -> str:
    note = f'<p class="calib muted">{escape(calibration_note)}</p>' if calibration_note else ""
    pct = round(pred.probability * 100)
    thr = round(pred.threshold * 100)
    level = risk_level(pred.probability, pred.threshold)
    icon, text = RISK[level]
    in_ten = round(pred.probability * 10)
    when = "before the trip" if pred.scenario == "A" else "with the train already en route"
    body = f"""
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
  <div class="bar-scale"><span style="left:{thr}%">decision threshold {thr}%</span></div>{note}"""
    return card("Probability of departing 6+ min late", body)


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
    body = f"""
  <div class="route" style="--n:{n};--line:{line};--prog:{progress:.3f}">
    <div class="route-rail">
      <div class="route-base"></div>
      <div class="route-done"></div>
      <div class="route-train-wrap"><div class="route-train" aria-hidden="true">{TRAIN_HTML}</div></div>
    </div>
    {''.join(cells)}
  </div>
  <p class="route-note muted">{note}</p>"""
    return card("What the model knows", body)


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
    body = f"""
  <div class="shap-rows">{''.join(rows)}</div>
  <div class="shap-legend muted">
    <span><i style="background:var(--shap-up)"></i>raises the delay risk</span>
    <span><i style="background:var(--shap-down)"></i>lowers the delay risk</span>
    <span>Average {pred.base_value * 100:.0f}% &rarr; this departure {pred.probability * 100:.0f}% (percentage points)</span>
  </div>"""
    return card("Why this prediction?", body)
