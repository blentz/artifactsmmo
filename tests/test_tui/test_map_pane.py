"""MapPane viewport rendering tests (no Textual app needed)."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
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


class TestMapPaneRender:
    def test_index_built_from_game_data(self):
        gd = _gd_with_world()
        pane = MapPane(gd)
        # Monster at (2,0) should map to ('M', 'red')
        assert pane._tile_index[(2, 0)] == ("M", "red")
        # Tree (woodcutting) at (-1,0)
        assert pane._tile_index[(-1, 0)] == ("T", "green")
        # Bank
        assert pane._tile_index[(4, 1)] == ("$", "yellow")
        # Taskmaster
        assert pane._tile_index[(1, 2)] == ("?", "cyan")

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
        assert "M" in rendered  # monster glyph
        assert "T" in rendered  # tree
        assert "?" in rendered  # taskmaster
