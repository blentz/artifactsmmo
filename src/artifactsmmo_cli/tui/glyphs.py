"""Map (x,y) tile content → single character + color for the TUI map pane.

NetHack-faithful where possible. Pure data — no logic.
"""

PLAYER_GLYPH = "@"
PLAYER_COLOR = "bright_yellow"

# (glyph, color)
CONTENT_GLYPHS: dict[str, tuple[str, str]] = {
    "monster":              ("M", "red"),
    "resource_woodcutting": ("T", "green"),
    "resource_mining":      ("*", "yellow"),
    "resource_fishing":     ("~", "blue"),
    "resource_alchemy":     ("%", "magenta"),
    "bank":                 ("$", "yellow"),
    "tasks_master":         ("?", "cyan"),
    "npc":                  ("!", "cyan"),
    "workshop":             ("W", "white"),
    "transition":           (">", "magenta"),
}

UNMAPPED_GLYPH = " "
WALKABLE_GLYPH = "·"
WALKABLE_COLOR = "grey50"
