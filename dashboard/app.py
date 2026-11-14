"""Streamlit dashboard: delay risk for departures at Würzburg Hbf.

Input: a predictor from `predictor.load_predictor()` (saved model + lookup
table; never the raw data). Output: the interactive page.
Run from the repository root (as Streamlit Community Cloud does): `streamlit run dashboard/app.py`.

Layout (desktop, one screen): header with the "How it works" button; inputs;
result | route | risk through the day; explanation | usual delays by weekday and hour.
Sizes are set in ui/components.py.
"""
from datetime import date

import streamlit as st

from about import how_it_works
from predictor import HOURS, WEEKDAYS, Query, load_predictor
from ui import charts, components

st.set_page_config(page_title="Train delay risk · Würzburg Hbf", page_icon="🚉", layout="wide")

theme = "light" if st.context.theme.type == "light" else "dark"
predictor = load_predictor()

st.html(components.global_css(theme))

with st.container(key="topbar", horizontal=True, vertical_alignment="center"):
    st.html(components.header(), width="stretch")
    with st.popover("How it works", icon=":material/help:"):
        st.markdown(how_it_works(predictor.facts() if hasattr(predictor, "facts") else None, predictor.is_demo))

if predictor.is_demo:
    st.warning("Demo mode: the trained model is not connected yet. All numbers on this page are placeholders.", icon="⚠️")

lines = predictor.lines()
# The model-backed predictor answers for days of the test period only (its lookup tables end there).
first_day, last_day = getattr(predictor, "date_range", (None, None))
default_day = min(max(date.today(), first_day), last_day) if first_day else date.today()
if "query" not in st.session_state:
    st.session_state.query = Query(line=lines[0], day=default_day, hour=17, prev_stop_delay=None)

with st.form("inputs", border=False):
    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 3, 2], vertical_alignment="bottom")
    line = c1.selectbox("Train type / line", lines)
    day = c2.date_input("Date", value=st.session_state.query.day, min_value=first_day, max_value=last_day)
    hour = c3.selectbox("Departure hour", HOURS, index=HOURS.index(17), format_func=lambda h: f"{h:02d}:00")
    prev = c4.number_input(
        "Delay at previous stop (min)", min_value=0, max_value=120, value=None, step=1,
        placeholder="empty = before the trip", help="Fill in only if the train is already en route (scenario B).",
    )
    if c5.form_submit_button("Predict", use_container_width=True):
        st.session_state.query = Query(line=line, day=day, hour=hour, prev_stop_delay=prev)

query = st.session_state.query
pred = predictor.predict(query)

top_left, top_mid, top_right = st.columns([4, 4, 5])
top_left.html(components.hero(pred, predictor.calibration_note(pred.probability)))
top_mid.html(components.route(pred, query.prev_stop_delay))
top_right.html(components.card(
    "Risk through the day",
    charts.day_profile(predictor.hourly_profile(query), HOURS, query.hour, pred.threshold, pred.scenario),
    sub=f"{query.line} · {WEEKDAYS[query.day.weekday()]} {query.day:%d %b %Y}",
))

bottom_left, bottom_right = st.columns([5, 6])
bottom_left.html(components.shap_bars(pred))
bottom_right.html(components.card(
    "When is this line usually late?",
    charts.delay_heatmap(predictor.delay_rate_grid(query.line), WEEKDAYS, HOURS, theme, selected=(query.day.weekday(), query.hour)),
    sub="Share of departures delayed 6+ min, July 2024 – October 2026",
))
