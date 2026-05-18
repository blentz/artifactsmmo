"""Static-viewport NetHack-style map centered on the player."""

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import (
    CONTENT_GLYPHS,
    PLAYER_COLOR,
    PLAYER_GLYPH,
    UNMAPPED_GLYPH,
    WALKABLE_COLOR,
    WALKABLE_GLYPH,
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

    @staticmethod
    def _build_tile_index(gd: GameData) -> dict[tuple[int, int], tuple[str, str]]:
        """Map (x,y) → (glyph, color). Player position resolved at render time."""
        index: dict[tuple[int, int], tuple[str, str]] = {}
        # Resources — keyed by skill to pick glyph
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
                index[(x, y)] = CONTENT_GLYPHS[key]
        # Workshops
        for skill, loc in gd._workshop_locations.items():
            if loc is not None:
                index[loc] = CONTENT_GLYPHS["workshop"]
        # NPCs
        for npc_code, loc in gd._npc_locations.items():
            index[loc] = CONTENT_GLYPHS["npc"]
        # Bank
        if gd._bank_location is not None:
            index[gd._bank_location] = CONTENT_GLYPHS["bank"]
        # Taskmaster
        if gd._taskmaster_location is not None:
            index[gd._taskmaster_location] = CONTENT_GLYPHS["tasks_master"]
        # Monsters last so monsters at shared tiles win the cell
        for code, locs in gd._monster_locations.items():
            for (x, y) in locs:
                index[(x, y)] = CONTENT_GLYPHS["monster"]
        # Transitions
        for (x, y) in gd._transition_tiles:
            index[(x, y)] = CONTENT_GLYPHS["transition"]
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
        text = Text()
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
                else:
                    text.append(UNMAPPED_GLYPH)
            text.append("\n")
        # Header line: char coords + glyph legend
        header = Text(f" ({cx},{cy})  @=you  M=monster  T=tree  *=ore  ~=fish  $=bank  ?=tasks  !=npc  >=portal\n", style="dim")
        return header + text
