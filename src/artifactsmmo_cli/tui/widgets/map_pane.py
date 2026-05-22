"""NetHack-style map: a grid that fills the pane, centered on the player."""

from typing import Any

from rich.text import Text
from textual.events import Resize
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
    UNMAPPED_COLOR,
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
    """Renders a grid that fills the pane, centered on the player."""

    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def __init__(self, game_data: GameData, **kwargs: Any) -> None:
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
        width = self.size.width or VIEWPORT_W
        height = self.size.height or VIEWPORT_H
        return self._render_viewport(snap, width, height)

    def on_resize(self, event: Resize) -> None:
        """Recompute the grid whenever the pane is resized."""
        self.refresh()

    def _render_viewport(self, snap: CycleSnapshot, width: int, height: int) -> Text:
        """Render a width x height block: 1 legend line + (height-1) map rows,
        player centered at (width//2, (height-1)//2)."""
        map_h = height - 1
        half_w = width // 2
        half_h = map_h // 2
        cx, cy = snap.x, snap.y
        text = Text(no_wrap=True, overflow="crop")
        header_nl = "\n" if map_h > 0 else ""
        text.append(
            f" ({cx},{cy})  @ you  A-Z npc  a-z monster  ╬ structure  + door  T/*/~/% resource{header_nl}",
            style="dim",
        )
        for row in range(map_h):
            for col in range(width):
                world_x = cx + col - half_w
                world_y = cy + row - half_h
                if col == half_w and row == half_h:
                    text.append(PLAYER_GLYPH, style=PLAYER_COLOR)
                    continue
                cell = self._tile_index.get((world_x, world_y))
                if cell is not None:
                    glyph, color = cell
                    text.append(glyph, style=color)
                elif (world_x, world_y) in self._known_tiles:
                    text.append(WALKABLE_GLYPH, style=WALKABLE_COLOR)
                else:
                    text.append(UNMAPPED_GLYPH, style=UNMAPPED_COLOR)
            if row != map_h - 1:
                text.append("\n")
        return text
