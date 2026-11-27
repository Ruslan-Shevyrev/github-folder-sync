"""Color palettes for the application widgets and canvas."""

THEMES = ("Dark", "Light")
WHITE = "#ffffff"

DARK = {
    "background": "#111522",
    "panel": "#191e2f",
    "field": "#23283c",
    "border": "#42495f",
    "panel_border": "#30374d",
    "text": "#f4f2fb",
    "muted": "#b9bdd1",
    "disabled_text": "#9398ad",
    "accent": "#7446ee",
    "accent_hover": "#895dff",
    "row_action": "#7446ee",
    "row_action_hover": "#865cff",
    "row_action_icon": WHITE,
    "delete_icon": WHITE,
    "hover": "#353d55",
    "table_frame": "#101421",
    "table": "#101321",
    "table_border": "#343956",
    "header": "#222740",
    "header_hover": "#343052",
    "header_pressed": "#4a347a",
    "selection": "#513ca0",
    "danger": "#983c53",
    "danger_hover": "#b94c67",
    "delete": "#813c51",
    "delete_hover": "#a24f67",
    "disabled_fill": "#3b4155",
    "disabled_icon": "#9297ac",
    "link": "#d4baff",
    "arrow": "#85839e",
    "branch_green": "#83eca4",
    "branch_yellow": "#ffe08a",
    "branch_red": "#ff999f",
    "branch_gray": "#c3c6d2",
    "both_bg": "#20372f",
    "both_fg": "#b8f5cf",
    "github_bg": "#2e3242",
    "github_fg": "#dcdfeb",
    "local_bg": "#432b37",
    "local_fg": "#ffc4cb",
}

LIGHT = {
    "background": "#f0f2f8",
    "panel": "#f8f9fd",
    "field": "#ffffff",
    "border": "#b7c1d4",
    "panel_border": "#c6cede",
    "text": "#20263a",
    "muted": "#4f5c73",
    "disabled_text": "#67758a",
    "accent": "#315a9c",
    "accent_hover": "#264a82",
    "row_action": "#e8effa",
    "row_action_hover": "#d5e3f8",
    "row_action_icon": "#315a9c",
    "delete_icon": "#a12642",
    "hover": "#e6e9f7",
    "table_frame": "#ffffff",
    "table": "#ffffff",
    "table_border": "#cbd3e3",
    "header": "#e8ecf6",
    "header_hover": "#dde2f2",
    "header_pressed": "#cfd6ed",
    "selection": "#5e2cb8",
    "danger": "#a12642",
    "danger_hover": "#821c34",
    "delete": "#fbe9ed",
    "delete_hover": "#f4d1da",
    "disabled_fill": "#d8deeb",
    "disabled_icon": "#647186",
    "link": "#5425ab",
    "arrow": "#5b6478",
    "branch_green": "#1f6b3b",
    "branch_yellow": "#805200",
    "branch_red": "#a32942",
    "branch_gray": "#4e5b70",
    "both_bg": "#e8f5eb",
    "both_fg": "#23543a",
    "github_bg": "#eaeffa",
    "github_fg": "#34486e",
    "local_bg": "#fbe9ed",
    "local_fg": "#7e3047",
}

_palette = DARK


def set_theme(theme):
    global _palette
    _palette = LIGHT if theme == "Light" else DARK


def theme_color(name):
    return _palette[name]
