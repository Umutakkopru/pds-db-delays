"""Plain-language explanation of the page ("How does this work?").

Input: the facts dictionary of the predictor (row counts and test-period results
from data/meta.json; None if it has none) and whether the page runs in demo mode. Output: Markdown for the expander.
No number is typed in here: every figure comes from the lookup tables.
"""
from __future__ import annotations


def _of_100(share: float) -> str:
    return f"{round(100 * share)} of 100"


def how_it_works(facts: dict | None, is_demo: bool = False) -> str:
    """Short explanation for visitors who have not read the report; without facts the two number paragraphs are left out."""
    parts = [
        "**What you see.** For a train leaving Würzburg Hbf, this page estimates how likely it is to depart "
        "**6 or more minutes late**. Six minutes is the limit Deutsche Bahn uses to call a train punctual.",
        "**Two moments.**\n"
        "- *Before the trip* (leave the delay field empty): the estimate uses only what is known the day before: "
        "the timetable, the weekday and holidays, the weather, and how often similar trains were late in the last four weeks.\n"
        "- *On the way* (enter the delay at the previous stop): the estimate also knows how late the train already is. "
        "That is usually far more reliable.",
    ]
    if facts and not is_demo:
        a, b = facts["performance"]["A"], facts["performance"]["B"]
        parts += [
            f"**How it was built.** A model (gradient-boosted decision trees) learned from {facts['training_rows']:,} real "
            f"departures between {facts['training_period']}. It was then checked once on {a['rows']:,} departures from "
            f"{facts['test_period']} that it had never seen. The days you can pick are from that period.",
            f"**How good is it?** In that check, {round(100 * a['base_rate'])} of 100 departures were late.\n"
            f"- Before the trip: when the page says \"High delay risk\", the train was late in {_of_100(a['precision'])} cases, "
            f"and {_of_100(a['recall'])} late trains were flagged.\n"
            f"- On the way: {_of_100(b['precision'])} flagged trains were late, and {_of_100(b['recall'])} late trains were flagged.",
        ]
    if is_demo:
        parts.append("**Demo mode.** The trained model is not connected; the numbers on this page are placeholders.")
    parts += [
        "**Reading the page.** The big number is the share of comparable departures that leave late. "
        "The bars under it show what pushed this estimate up or down. The grid at the bottom shows when this line is usually late.",
        "**Limits.** The estimate is for a typical train of the line at that hour, not for one particular train. "
        "It cannot see disruptions that are not in the data. Regional trains are rarely late and hard to call the day before. "
        "The check covered July to October, so winter is not included.",
    ]
    return "\n\n".join(parts)
