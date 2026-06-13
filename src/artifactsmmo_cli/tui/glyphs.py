"""Color palette for the TUI map pane.

Each content category has its own color so sprites stay visually distinct
across categories. The sprite renderer (``sprites.py``) and the map pane
(``widgets/map_pane.py``) import these constants; the single-glyph letter
helpers that once lived here were retired when the sprite path replaced them.
"""

PLAYER_COLOR = "bright_yellow"

NPC_COLOR = "cyan"
MONSTER_COLOR = "red"
STRUCTURE_COLOR = "white"
DOOR_COLOR = "magenta"

UNMAPPED_COLOR = "grey15"  # faint void texture so the viewport fills the pane
WALKABLE_COLOR = "grey50"  # explored floor — brighter than unmapped void
