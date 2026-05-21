"""MapPane viewport rendering tests (no Textual app needed)."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import WALKABLE_GLYPH
from artifactsmmo_cli.tui.widgets.map_pane import MapPane, VIEWPORT_H, VIEWPORT_W


def _gd_with_world() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(2, 0)]}
    gd._resource_locations = {"ash_tree": [(-1, 0)]}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._bank_location = (4, 1)
    gd._taskmaster_location = (1, 2)
    return gd


def _snap(x: int, y: int) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=0, timestamp="2026-05-18T00:00:00Z", character="hero",
        x=x, y=y, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
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


class TestMapPaneRender:
    def test_index_built_from_game_data(self):
        gd = _gd_with_world()
        pane = MapPane(gd)
        # Monster at (2,0): chicken → ('c', 'red')
        assert pane._tile_index[(2, 0)] == ("c", "red")
        # Tree (woodcutting) at (-1,0)
        assert pane._tile_index[(-1, 0)] == ("T", "green")
        # Bank → structure box glyph
        assert pane._tile_index[(4, 1)] == ("╣", "white")
        # Taskmaster → structure box glyph
        assert pane._tile_index[(1, 2)] == ("╤", "white")

    def test_viewport_dimensions_are_odd(self):
        """Player must be at exact center → both dims odd."""
        assert VIEWPORT_W % 2 == 1
        assert VIEWPORT_H % 2 == 1

    def test_render_shows_player_at_center(self):
        gd = _gd_with_world()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        out = pane.render()
        rendered = str(out)
        # Player glyph @ must appear in the output
        assert "@" in rendered

    def test_render_includes_world_glyphs_in_view(self):
        """Player at (0,0); world has monster at (2,0) — should appear in viewport."""
        gd = _gd_with_world()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        rendered = str(pane.render())
        assert "c" in rendered  # monster glyph (chicken → 'c')
        assert "T" in rendered  # tree
        assert "╤" in rendered  # taskmaster structure glyph

    def test_body_rows_match_viewport_and_no_trailing_blank(self):
        """1 header + VIEWPORT_H body rows, every body row exactly VIEWPORT_W wide,
        and no trailing blank line (the old code left one)."""
        gd = _gd_with_world()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        lines = pane.render().plain.split("\n")
        assert len(lines) == 1 + VIEWPORT_H  # header + rows, no trailing empty line
        body = lines[1:]
        assert all(len(row) == VIEWPORT_W for row in body)

    def test_render_is_no_wrap_and_cropped(self):
        """The viewport must never wrap; the wide legend should crop, not fold."""
        gd = _gd_with_world()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        out = pane.render()
        assert out.no_wrap is True
        assert out.overflow == "crop"

    def test_known_empty_tile_renders_walkable_floor(self):
        """A known tile with no content renders the walkable glyph, not blank void."""
        gd = _gd_with_world()
        gd._known_tiles = {(1, 0)}  # in view from (0,0), no content there
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        assert WALKABLE_GLYPH in pane.render().plain


class TestMapPaneTypedGlyphs:
    def test_render_without_snapshot_shows_waiting(self):
        pane = MapPane(_gd_typed())
        assert "Waiting" in pane.render().plain

    def test_npc_renders_uppercase_letter(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(-1, 0)] == ("A", "cyan")

    def test_monster_renders_lowercase_letter(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 0)] == ("s", "red")
        assert idx[(0, 2)] == ("c", "red")

    def test_structures_render_box_glyphs(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(4, 1)] == ("╣", "white")
        assert idx[(-2, -2)] == ("╠", "white")
        assert idx[(3, 3)] == ("╬", "white")
        assert idx[(1, 2)] == ("╤", "white")

    def test_transition_renders_door(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(0, -3)] == ("+", "magenta")

    def test_resources_unchanged(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 2)] == ("T", "green")

    def test_legend_uses_category_key(self):
        gd = _gd_typed()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        header = pane.render().plain.split("\n")[0]
        assert "npc" in header and "monster" in header
        assert "structure" in header and "door" in header
        assert "M=monster" not in header
        assert ">=portal" not in header
