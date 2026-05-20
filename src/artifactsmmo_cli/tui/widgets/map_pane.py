"""Static-viewport NetHack-style map centered on the player."""

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    DOOR_GLYPH,
    PLAYER_COLOR,
    PLAYER_GLYPH,
    RESOURCE_GLYPHS,
    UNMAPPED_GLYPH,
    WALKABLE_COLOR,
    WALKABLE_GLYPH,
    monster_glyph,
    npc_glyph,
    structure_glyph,
)

VIEWPORT_W = 41  # odd so the player sits in the exact center
VIEWPORT_H = 21


class MapPane(Static):
    """Renders a VIEWPORT_W x VIEWPORT_H grid centered on the player."""

    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def __init__(self, game_data: GameData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._game_data = game_data
        # Pre-index the world for fast (x,y) lookup. NetHack-style maps need
        # constant-time "what's at this cell" so the viewport renders fast.
        self._tile_index = self._build_tile_index(game_data)
        # Known-but-empty tiles render as walkable floor; everything else is
        # unmapped void. Without this set the map is content islands in blank.
        self._known_tiles = game_data._known_tiles

    @staticmethod
    def _build_tile_index(gd: GameData) -> dict[tuple[int, int], tuple[str, str]]:
        """Map (x,y) → (glyph, color). Player position resolved at render time."""
        index: dict[tuple[int, int], tuple[str, str]] = {}
        skill_to_key = {
            "woodcutting": "resource_woodcutting",
            "mining": "resource_mining",
            "fishing": "resource_fishing",
            "alchemy": "resource_alchemy",
        }
        for code, locs in gd._resource_locations.items():
            skill_lvl = gd._resource_skill.get(code)
            key = skill_to_key.get(skill_lvl[0], "resource_mining") if skill_lvl else "resource_mining"
            for (x, y) in locs:
                index[(x, y)] = RESOURCE_GLYPHS[key]
        for _skill, loc in gd._workshop_locations.items():
            if loc is not None:
                index[loc] = structure_glyph("workshop")
        for npc_code, loc in gd._npc_locations.items():
            index[loc] = npc_glyph(npc_code)
        if gd._bank_location is not None:
            index[gd._bank_location] = structure_glyph("bank")
        if gd._grand_exchange_location is not None:
            index[gd._grand_exchange_location] = structure_glyph("grand_exchange")
        if gd._taskmaster_location is not None:
            index[gd._taskmaster_location] = structure_glyph("tasks_master")
        for code, locs in gd._monster_locations.items():
            glyph = monster_glyph(code)
            for (x, y) in locs:
                index[(x, y)] = glyph
        for (x, y) in gd._transition_tiles:
            index[(x, y)] = (DOOR_GLYPH, DOOR_COLOR)
        return index

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        return self._render_viewport(snap)

    def _render_viewport(self, snap: CycleSnapshot) -> Text:
        half_w = VIEWPORT_W // 2
        half_h = VIEWPORT_H // 2
        cx, cy = snap.x, snap.y
        # no_wrap + crop: the viewport is a fixed grid. Letting Rich wrap it (the
        # default) folds the wide legend and long rows onto extra lines, shoving
        # the bottom of the map out of the pane — the "pinched and incomplete"
        # symptom. Crop instead so the grid keeps its shape and overflow is hidden.
        text = Text(no_wrap=True, overflow="crop")
        # Header line: char coords + glyph legend.
        text.append(
            f" ({cx},{cy})  @=you  M=monster  T=tree  *=ore  ~=fish  $=bank  ?=tasks  !=npc  >=portal\n",
            style="dim",
        )
        for dy in range(-half_h, half_h + 1):
            for dx in range(-half_w, half_w + 1):
                world_x = cx + dx
                world_y = cy + dy
                if dx == 0 and dy == 0:
                    text.append(PLAYER_GLYPH, style=PLAYER_COLOR)
                    continue
                cell = self._tile_index.get((world_x, world_y))
                if cell is not None:
                    glyph, color = cell
                    text.append(glyph, style=color)
                elif (world_x, world_y) in self._known_tiles:
                    text.append(WALKABLE_GLYPH, style=WALKABLE_COLOR)
                else:
                    text.append(UNMAPPED_GLYPH)
            # Newline between rows only — no trailing newline after the last row.
            if dy != half_h:
                text.append("\n")
        return text
