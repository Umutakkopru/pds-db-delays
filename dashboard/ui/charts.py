"""
Charts drawn with HTML and CSS (no Plotly): they stretch with their card, so the
page keeps the same proportions on every screen size, and they use the same
colour tokens as the rest of the page.

Input: lists of rates or probabilities from the predictor. Output: HTML strings for `st.html`.
"""
from __future__ import annotations

from html import escape

from .tokens import HEATMAP_SCALE

LABELLED_HOURS = {6, 9, 12, 15, 18, 21}
BEST_HOUR_WINDOW = 2       # hours before and after the chosen hour that count as a realistic alternative
BEST_HOUR_MIN_GAIN = 0.03  # smaller differences are within the model's noise: no suggestion


def _mix(scale: list[str], t: float) -> str:
    """Colour at position t (0..1) of a piecewise-linear colour scale given as hex strings."""
    t = min(max(t, 0.0), 1.0) * (len(scale) - 1)
    i = min(int(t), len(scale) - 2)
    a, b = scale[i], scale[i + 1]
    frac = t - i
    rgb = [round(int(a[k:k + 2], 16) + (int(b[k:k + 2], 16) - int(a[k:k + 2], 16)) * frac) for k in (1, 3, 5)]
    return "#" + "".join(f"{c:02X}" for c in rgb)


def delay_heatmap(grid: list[list[float | None]], weekdays: list[str], hours: list[int], theme: str,
                  selected: tuple[int, int] | None = None) -> str:
    """Weekday x hour grid of the share of departures delayed >= 6 min; empty where the line rarely runs."""
    scale = HEATMAP_SCALE[theme]
    top = max((v for row in grid for v in row if v is not None), default=0) or 1
    cells = []
    for d, (day, row) in enumerate(zip(weekdays, grid)):
        cells.append(f'<span class="hm-y">{day}</span>')
        for h, value in zip(hours, row):
            outline = " sel" if selected == (d, h) else ""
            if value is None:
                cells.append(f'<span class="hm-cell empty{outline}" title="{day} {h:02d}:00 · too few departures"></span>')
            else:
                cells.append(f'<span class="hm-cell{outline}" style="background:{_mix(scale, value / top)}" '
                             f'title="{day} {h:02d}:00 · {value:.0%} delayed"></span>')
    cells.append('<span></span>')
    cells += [f'<span class="hm-x">{f"{h:02d}" if h in LABELLED_HOURS else ""}</span>' for h in hours]
    gradient = ", ".join(scale)
    return f"""
<div class="hm" style="--cols:{len(hours)}" role="img" aria-label="Share of departures delayed 6+ minutes by weekday and hour">
  {''.join(cells)}
</div>
<div class="hm-legend muted"><span>0%</span><i style="background:linear-gradient(to right, {gradient})"></i><span>{top:.0%} delayed</span>
  <span class="hm-legend-sel">outlined: your selection</span></div>"""


def best_hour(profile: list[float], hours: list[int], selected_hour: int, threshold: float) -> int | None:
    """
    The hour to point out in the day-profile chart as a better alternative, or None.

    profile[i] is the predicted probability for hours[i] (same line, day and inputs);
    threshold is the model's decision threshold (at or above it the page says "high risk").

    Rule: only hours within BEST_HOUR_WINDOW of the chosen hour count (a passenger can
    shift a trip a little, not to the evening); the lowest risk among them is suggested
    if it is at least BEST_HOUR_MIN_GAIN lower than the chosen hour. On a tie the hour
    closest to the chosen one wins. The threshold is not used: a drop from 60% to 45%
    is worth showing even if both are "high risk".
    """
    chosen = profile[hours.index(selected_hour)]
    nearby = [(p, abs(h - selected_hour), h) for h, p in zip(hours, profile)
              if h != selected_hour and abs(h - selected_hour) <= BEST_HOUR_WINDOW]
    if not nearby:
        return None
    risk, _, hour = min(nearby)
    return hour if chosen - risk >= BEST_HOUR_MIN_GAIN else None


def day_profile(profile: list[float], hours: list[int], selected_hour: int, threshold: float, scenario: str) -> str:
    """Predicted probability for every hour of the chosen day; selected hour, threshold and best hour marked."""
    top = max(max(profile, default=0), threshold) * 1.15 or 1
    best = best_hour(profile, hours, selected_hour, threshold)
    bars = []
    for h, p in zip(hours, profile):
        level = "high" if p >= threshold else "medium" if p >= threshold / 2 else "low"
        classes = f"dp-bar {level}" + (" sel" if h == selected_hour else "") + (" best" if h == best else "")
        tag = f'<em>{p:.0%}</em>' if h in (selected_hour, best) else ""
        bars.append(f'<span class="dp-col" title="{h:02d}:00 · {p:.0%}"><span class="{classes}" style="height:{p / top * 100:.1f}%">{tag}</span></span>')
    labels = "".join(f'<span>{f"{h:02d}" if h in LABELLED_HOURS else ""}</span>' for h in hours)
    note = f"Best nearby choice: {best:02d}:00. " if best is not None else ""
    return f"""
<div class="dp" role="img" aria-label="Predicted delay risk for every hour of the chosen day">
  <div class="dp-plot">
    <span class="dp-thr" style="bottom:{threshold / top * 100:.1f}%"><b>threshold {threshold:.0%}</b></span>
    {''.join(bars)}
  </div>
  <div class="dp-x">{labels}</div>
</div>
<p class="dp-note muted">{escape(note)}Same line and day, every hour (scenario {scenario}).</p>"""
