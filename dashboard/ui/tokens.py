"""Design tokens for the dashboard (light and dark).

Input: theme name ("light" or "dark"). Output: dict of CSS custom properties.
Colour values are adapted from DB's open design system; contrast ratios were
checked against WCAG AA (>= 4.5:1 for all text colours on their backgrounds).
"""

BRAND_RED = "#EC0016"  # shapes and lines only, never text

TOKENS = {
    "dark": {
        "bg": "#131821",
        "surface": "#282D37",
        "border": "#3C414B",
        "text": "#F0F3F5",
        "text-muted": "#AFB4BB",
        "brand": BRAND_RED,
        "action-bg": "#F0F3F5",
        "action-text": "#131821",
        "focus": "#73AEF4",
        "low": "#8CBC80",
        "medium": "#F8AB37",
        "high": "#F75056",
        "low-fill": "#1E3A2A",
        "medium-fill": "#40341F",
        "high-fill": "#45202A",
        "scenario-a": "#73AEF4",
        "scenario-b": "#3CB5AE",
        "baseline": "#878C96",
        "shap-up": "#F75056",
        "shap-down": "#73AEF4",
        "badge-bg": "#FFD800",
        "badge-text": "#131821",
    },
    "light": {
        "bg": "#F0F3F5",
        "surface": "#FFFFFF",
        "border": "#D7DCE1",
        "text": "#131821",
        "text-muted": "#646973",
        "brand": BRAND_RED,
        "action-bg": "#131821",
        "action-text": "#FFFFFF",
        "focus": "#1455C0",
        "low": "#2A7230",
        "medium": "#A24800",
        "high": "#C50014",
        "low-fill": "#E2F3E5",
        "medium-fill": "#FFF4D8",
        "high-fill": "#FEE6E6",
        "scenario-a": "#1455C0",
        "scenario-b": "#008984",
        "baseline": "#878C96",
        "shap-up": "#EC0016",
        "shap-down": "#1455C0",
        "badge-bg": "#FFD800",
        "badge-text": "#131821",
    },
}

# Single-hue sequential scale for the delay-rate heatmap (low -> high).
HEATMAP_SCALE = {
    "dark": ["#282D37", "#9B000E", "#EC0016", "#FA9090"],
    "light": ["#FEE6E6", "#FA9090", "#EC0016", "#740009"],
}


def css_variables(theme: str) -> str:
    """Return a ':root { --token: value; ... }' block for the given theme."""
    body = "".join(f"--{name}:{value};" for name, value in TOKENS[theme].items())
    return f":root{{{body}}}"
