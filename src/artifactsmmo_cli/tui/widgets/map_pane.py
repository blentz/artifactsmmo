"""Tile-map pane: each tile is an 8x8 half-block sprite, centered on the player."""

from typing import Any

from rich.text import Text
from textual.events import Resize
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import UNMAPPED_COLOR, WALKABLE_COLOR
from artifactsmmo_cli.tui.half_block import HalfBlockCompositor
from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import BLANK_SPRITE, PLAYER_SPRITE, Sprite, SpriteCategory

TILE_W = 8   # chars per tile column (8 pixels wide)
TILE_H = 4   # char-rows per tile (8 pixels tall, 2 px per char-row)
FALLBACK_W = 80
FALLBACK_H = 41

_SKILL_TO_RESOURCE_KEY = {
    "woodcutting": "resource_woodcutting",
    "mining": "resource_mining",
    "fishing": "resource_fishing",
    "alchemy": "resource_alchemy",
}
TileContent = tuple[SpriteCategory, str]


class MapPane(Static):
    """Renders an 8x8-sprite tile grid that fills the pane, centered on player."""

    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def __init__(self, game_data: GameData, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._game_data = game_data
        self._tile_index = self._build_tile_index(game_data)
        self._known_tiles = game_data.known_tiles
        self._registry = SpriteRegistry()
        self._compositor = HalfBlockCompositor()

    @staticmethod
    def _build_tile_index(gd: GameData) -> dict[tuple[int, int], TileContent]:
        """Map (x,y) -> (category, code). Player resolved at render time."""
        index: dict[tuple[int, int], TileContent] = {}
        for code, locs in gd.all_resource_locations.items():
            skill = gd.resource_skills.get(code)
            key = _SKILL_TO_RESOURCE_KEY.get(skill[0], "resource_mining") if skill else "resource_mining"
            for xy in locs:
                index[xy] = (SpriteCategory.RESOURCE, key)
        for _skill, loc in gd.workshop_locations.items():
            if loc is not None:
                index[loc] = (SpriteCategory.STRUCTURE, "workshop")
        for npc_code, loc in gd.npc_locations.items():
            index[loc] = (SpriteCategory.NPC, npc_code)
        bank_loc = gd.bank_location_or_none
        if bank_loc is not None:
            index[bank_loc] = (SpriteCategory.STRUCTURE, "bank")
        ge_loc = gd.grand_exchange_location()
        if ge_loc is not None:
            index[ge_loc] = (SpriteCategory.STRUCTURE, "grand_exchange")
        taskmaster_loc = gd.taskmaster_location_or_none
        if taskmaster_loc is not None:
            index[taskmaster_loc] = (SpriteCategory.STRUCTURE, "tasks_master")
        for code, locs in gd.all_monster_locations.items():
            for xy in locs:
                index[xy] = (SpriteCategory.MONSTER, code)
        for xy in gd.transition_tiles:
            index[xy] = (SpriteCategory.STRUCTURE, "door")
        return index

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        return self._render_viewport(snap, width, height)

    def on_resize(self, event: Resize) -> None:
        self.refresh()

    def _hud_line(self, snap: CycleSnapshot) -> str:
        content = self._tile_index.get((snap.x, snap.y))
        coords = f"({snap.x},{snap.y})"
        if content is None:
            return coords
        return f"{coords} · {content[1]}"

    def _tile_sprite_and_terrain(self, wx: int, wy: int, is_player: bool) -> tuple[Sprite, str]:
        if is_player:
            return PLAYER_SPRITE, WALKABLE_COLOR
        content = self._tile_index.get((wx, wy))
        if content is None:
            terrain = WALKABLE_COLOR if (wx, wy) in self._known_tiles else UNMAPPED_COLOR
            return BLANK_SPRITE, terrain
        category, code = content
        return self._registry.sprite_for(code, category), WALKABLE_COLOR

    def _render_viewport(self, snap: CycleSnapshot, width: int, height: int) -> Text:
        tiles_w = width // TILE_W
        tiles_h = (height - 1) // TILE_H
        half_w = tiles_w // 2
        half_h = tiles_h // 2
        cx, cy = snap.x, snap.y
        text = Text(no_wrap=True, overflow="crop")
        text.append(self._hud_line(snap), style="dim")
        for trow in range(tiles_h):
            text.append("\n")
            sublines = [Text(no_wrap=True, overflow="crop") for _ in range(TILE_H)]
            for tcol in range(tiles_w):
                wx = cx + tcol - half_w
                wy = cy + trow - half_h
                is_player = tcol == half_w and trow == half_h
                sprite, terrain = self._tile_sprite_and_terrain(wx, wy, is_player)
                rows4 = self._compositor.compose(sprite, terrain)
                for i in range(TILE_H):
                    sublines[i].append_text(rows4[i])
            for i in range(TILE_H):
                if i > 0:
                    text.append("\n")
                text.append_text(sublines[i])
        return text
