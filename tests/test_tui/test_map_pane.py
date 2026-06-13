"""MapPane tile-model viewport tests (mostly app-free; sizing uses run_test)."""

from textual.app import App, ComposeResult
from textual.geometry import Size

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import UNMAPPED_COLOR, WALKABLE_COLOR
from artifactsmmo_cli.tui.sprites import SpriteCategory
from artifactsmmo_cli.tui.widgets.map_pane import (
    FALLBACK_H,
    FALLBACK_W,
    TILE_H,
    TILE_W,
    MapPane,
)


def _gd_typed() -> GameData:
    gd = GameData()
    gd._monster_locations = {"green_slime": [(2, 0)], "chicken": [(0, 2)]}
    gd._npc_locations = {"archaeologist": (-1, 0)}
    gd._bank_location = (4, 1)
    gd._taskmaster_location = (1, 2)
    gd._workshop_locations = {"mining": (3, 3)}
    gd._grand_exchange_location = (-2, -2)
    gd._transition_tiles = {(0, -3)}
    gd._resource_locations = {"ash_tree": [(2, 2)]}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _snap(x: int, y: int) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=0, timestamp="2026-05-18T00:00:00Z", character="hero",
        x=x, y=y, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
    )


def _styles(text) -> list[str]:
    return [span.style for span in text.spans]


class TestBuildTileIndex:
    def test_index_stores_category_and_code(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 0)] == (SpriteCategory.MONSTER, "green_slime")
        assert idx[(0, 2)] == (SpriteCategory.MONSTER, "chicken")
        assert idx[(-1, 0)] == (SpriteCategory.NPC, "archaeologist")
        assert idx[(4, 1)] == (SpriteCategory.STRUCTURE, "bank")
        assert idx[(-2, -2)] == (SpriteCategory.STRUCTURE, "grand_exchange")
        assert idx[(3, 3)] == (SpriteCategory.STRUCTURE, "workshop")
        assert idx[(1, 2)] == (SpriteCategory.STRUCTURE, "tasks_master")
        assert idx[(0, -3)] == (SpriteCategory.STRUCTURE, "door")
        assert idx[(2, 2)] == (SpriteCategory.RESOURCE, "resource_woodcutting")


class TestViewportGeometry:
    def test_row_count_and_width_match_tiles(self):
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        lines = out.plain.split("\n")
        tiles_h = (41 - 1) // TILE_H
        tiles_w = 80 // TILE_W
        assert len(lines) == 1 + tiles_h * TILE_H        # 1 HUD + tile rows
        assert all(len(row) == tiles_w * TILE_W for row in lines[1:])

    def test_height_too_small_is_hud_only(self):
        pane = MapPane(_gd_typed())
        lines = pane._render_viewport(_snap(0, 0), 80, 1).plain.split("\n")
        assert len(lines) == 1                            # HUD only, no tile rows

    def test_render_is_no_wrap_and_cropped(self):
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert out.no_wrap is True
        assert out.overflow == "crop"


class TestLayers:
    def test_player_sprite_at_center(self):
        # PLAYER_COLOR (bright_yellow) appears only from the player sprite.
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any("bright_yellow" in s for s in _styles(out))

    def test_monster_sprite_in_view(self):
        # green_slime at (2,0) is in view from (0,0) -> green pixels present.
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any("green" in s for s in _styles(out))

    def test_unmapped_tiles_use_void_color(self):
        gd = GameData()  # nothing known, no content
        pane = MapPane(gd)
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any(UNMAPPED_COLOR in s for s in _styles(out))

    def test_known_empty_tile_uses_floor_color(self):
        gd = _gd_typed()
        gd._known_tiles = {(1, 0)}  # in view from (0,0), no content there
        pane = MapPane(gd)
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any(WALKABLE_COLOR in s for s in _styles(out))


class TestHud:
    def test_hud_shows_coords(self):
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(3, -4), 80, 41).plain.split("\n")[0]
        assert "(3,-4)" in hud

    def test_hud_shows_content_under_player(self):
        # Player standing on the woodcutting resource at (2,2).
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(2, 2), 80, 41).plain.split("\n")[0]
        assert "resource_woodcutting" in hud

    def test_hud_no_content_on_empty_tile(self):
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(9, 9), 80, 41).plain.split("\n")[0]
        assert hud.strip() == "(9,9)"


class TestRenderEntry:
    def test_render_without_snapshot_shows_waiting(self):
        assert "Waiting" in MapPane(_gd_typed()).render().plain

    def test_render_falls_back_when_size_zero(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        assert pane.size == Size(0, 0)
        lines = pane.render().plain.split("\n")
        tiles_h = (FALLBACK_H - 1) // TILE_H
        tiles_w = FALLBACK_W // TILE_W
        assert len(lines) == 1 + tiles_h * TILE_H
        assert all(len(row) == tiles_w * TILE_W for row in lines[1:])

    async def test_render_uses_pane_size(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))

        class _Host(App):
            CSS = "MapPane { width: 80; height: 41; }"

            def compose(self) -> ComposeResult:
                yield pane

        async with _Host().run_test(size=(100, 50)):
            assert pane.size == Size(80, 41)
            lines = pane.render().plain.split("\n")
        tiles_h = (41 - 1) // TILE_H
        assert len(lines) == 1 + tiles_h * TILE_H
