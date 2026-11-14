"""Plotly charts styled with the dashboard tokens."""
from __future__ import annotations

import plotly.graph_objects as go

from .tokens import HEATMAP_SCALE, TOKENS


def delay_heatmap(grid: list[list[float]], weekdays: list[str], hours: list[int], theme: str,
                  selected: tuple[int, int] | None = None) -> go.Figure:
    """Weekday x hour heatmap of the share of departures delayed >= 6 min."""
    t = TOKENS[theme]
    scale = HEATMAP_SCALE[theme]
    colorscale = [[i / (len(scale) - 1), c] for i, c in enumerate(scale)]
    fig = go.Figure(
        go.Heatmap(
            z=grid,
            x=hours,
            y=weekdays,
            colorscale=colorscale,
            zmin=0,
            xgap=2,
            ygap=2,
            colorbar=dict(title="Delayed", tickformat=".0%", thickness=10, outlinewidth=0),
            hovertemplate="%{y} %{x}<br>%{z:.0%} delayed<extra></extra>",
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["text-muted"], size=13),
        xaxis=dict(title="Hour of departure", showgrid=False, fixedrange=True, dtick=2, ticksuffix=":00"),
        yaxis=dict(autorange="reversed", showgrid=False, fixedrange=True),
    )
    if selected and selected[1] in hours:
        d, h = selected
        fig.add_shape(type="rect", x0=h - 0.5, x1=h + 0.5, y0=d - 0.5, y1=d + 0.5, line=dict(color=t["text"], width=3))
    return fig
