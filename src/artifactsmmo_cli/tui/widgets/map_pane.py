"""Tile-map pane: each tile is an 8x8 half-block sprite, centered on the player."""

import time
from typing import Any

from rich.text import Text
from textual.events import Resize
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import UNMAPPED_COLOR, WALKABLE_COLOR
from artifactsmmo_cli.tui.half_block import HalfBlockCompositor
from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import (
    BLANK_SPRITE, PICKAXE_HEAD, PLANNING_SPRITE, PLAYER_SPRITE, Sprite, SpriteCategory,
    overlay_sprites,
)
from artifactsmmo_cli.tui.path_interpolate import glide_path
from artifactsmmo_cli.tui.swing_frames import (
    SWING_FRAME_COUNT, Mode, current_mode, glide_index, swing_frame_index, swing_overlay,
)

TILE_W = 8   # chars per tile column (8 pixels wide)
TILE_H = 4   # char-rows per tile (8 pixels tall, 2 px per char-row)
FALLBACK_W = 80
FALLBACK_H = 41
MAX_ANIM_STEPS = 12       # cap glide frames so big jumps still finish fast
ANIM_FRAME_SECONDS = 0.05  # ~50ms/frame -> persistent timer interval
SWING_SWEEP_SECONDS = 0.8  # one chop/strike; loops over the cooldown

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
        self._anim_frames: list[tuple[int, int]] = []
        self._anim_start = 0.0
        self._anim_timer: Timer | None = None
        self._planning_active = False

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
        prior = self.snapshot
        self.snapshot = snap
        self._anim_start = time.monotonic()
        self._planning_active = False
        if prior is not None and (prior.x, prior.y) != (snap.x, snap.y):
            self._anim_frames = glide_path((prior.x, prior.y), (snap.x, snap.y), MAX_ANIM_STEPS)
        else:
            self._anim_frames = []
        self.refresh()

    def on_mount(self) -> None:
        # pragma: no cover — Textual timer glue: on_mount is only called by the
        # Textual framework when the widget is mounted into a real app; headless
        # tests construct MapPane without mounting, so this line cannot be reached
        # by the unit test suite without a full async Textual integration test.
        # The timer behavior is instead tested indirectly via _is_animating (which
        # exercises the same elapsed-vs-cooldown logic) and the mounted timer test
        # in TestGlideAnimation.test_timer_created_when_mounted_and_unmount_cancels.
        self._anim_timer = self.set_interval(ANIM_FRAME_SECONDS, self._tick)  # pragma: no cover

    def _tick(self) -> None:
        if self._is_animating():
            self.refresh()

    def _is_animating(self) -> bool:
        if self._planning_active:
            return True
        snap = self.snapshot
        if snap is None:
            return False
        elapsed = time.monotonic() - self._anim_start
        return elapsed < snap.cooldown_remaining

    def on_unmount(self) -> None:
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None

    def set_planning(self, active: bool) -> None:
        self._planning_active = active
        self.refresh()

    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        now = time.monotonic()
        center = self._glide_center(now)
        return self._render_viewport(
            snap, width, height, center, self._player_sprite(now), self._swing_overlay(now)
        )

    def on_resize(self, event: Resize) -> None:
        self.refresh()

    def _hud_line(self, cx: int, cy: int) -> str:
        content = self._tile_index.get((cx, cy))
        coords = f"({cx},{cy})"
        if content is None:
            return coords
        return f"{coords} · {content[1]}"

    def _player_sprite(self, now: float) -> Sprite:
        snap = self.snapshot
        if snap is None:
            return PLAYER_SPRITE
        elapsed = now - self._anim_start
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        if mode is Mode.PLANNING:
            return PLANNING_SPRITE
        return PLAYER_SPRITE

    def _swing_overlay(self, now: float) -> dict[tuple[int, int], Sprite]:
        """The per-tile tool overlay map for the current swing frame ({} when not
        gathering/fighting). Head in the arc-neighbor tile + grip in the player tile."""
        snap = self.snapshot
        if snap is None:
            return {}
        elapsed = now - self._anim_start
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        idx = swing_frame_index(elapsed, SWING_FRAME_COUNT, SWING_SWEEP_SECONDS)
        # TODO(Task 4): replace PICKAXE_HEAD with select_swing_head(mode, ...)
        return swing_overlay(mode, idx, PICKAXE_HEAD)

    def _glide_center(self, now: float) -> tuple[int, int] | None:
        if not self._anim_frames:
            return None
        snap = self.snapshot
        duration = snap.cooldown_remaining if snap is not None else 0.0
        idx = glide_index(now - self._anim_start, duration, len(self._anim_frames))
        return self._anim_frames[idx]

    def _tile_sprite_and_terrain(self, wx: int, wy: int, is_player: bool,
                                 player_sprite: Sprite) -> tuple[Sprite, str]:
        if is_player:
            return player_sprite, WALKABLE_COLOR
        content = self._tile_index.get((wx, wy))
        if content is None:
            terrain = WALKABLE_COLOR if (wx, wy) in self._known_tiles else UNMAPPED_COLOR
            return BLANK_SPRITE, terrain
        category, code = content
        return self._registry.sprite_for(code, category), WALKABLE_COLOR

    def _render_viewport(
        self,
        snap: CycleSnapshot,
        width: int,
        height: int,
        center: tuple[int, int] | None = None,
        player_sprite: Sprite = PLAYER_SPRITE,
        overlay: dict[tuple[int, int], Sprite] | None = None,
    ) -> Text:
        overlay = overlay or {}
        tiles_w = width // TILE_W
        tiles_h = (height - 1) // TILE_H
        half_w = tiles_w // 2
        half_h = tiles_h // 2
        cx, cy = center if center is not None else (snap.x, snap.y)
        text = Text(no_wrap=True, overflow="crop")
        text.append(self._hud_line(cx, cy), style="dim")
        for trow in range(tiles_h):
            text.append("\n")
            sublines = [Text(no_wrap=True, overflow="crop") for _ in range(TILE_H)]
            for tcol in range(tiles_w):
                wx = cx + tcol - half_w
                wy = cy + trow - half_h
                is_player = tcol == half_w and trow == half_h
                sprite, terrain = self._tile_sprite_and_terrain(wx, wy, is_player, player_sprite)
                tool = overlay.get((tcol - half_w, trow - half_h))
                if tool is not None:
                    sprite = overlay_sprites(sprite, tool)
                rows4 = self._compositor.compose(sprite, terrain)
                for i in range(TILE_H):
                    sublines[i].append_text(rows4[i])
            for i in range(TILE_H):
                if i > 0:
                    text.append("\n")
                text.append_text(sublines[i])
        return text
