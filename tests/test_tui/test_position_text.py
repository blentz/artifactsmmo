"""Position rendering names the layer whenever it is not the overworld."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.position_text import position_text
from artifactsmmo_cli.tui.screens.character_screen import build_character_detail
from artifactsmmo_cli.tui.screens.log_screen import build_debug_log_line


def _snap(layer: str = "overworld") -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=3, timestamp="2026-08-08T12:00:00Z", character="hero",
        x=5, y=-2, layer=layer, level=10, xp=0, max_xp=100, hp=50, max_hp=50, gold=0,
        selected_goal="G", action="A", outcome="ok",
    )


def test_overworld_position_is_coordinates_alone():
    assert position_text(_snap()) == "(5,-2)"


def test_off_overworld_position_names_the_layer():
    assert position_text(_snap("underground")) == "(5,-2) underground"
    assert position_text(_snap("interior")) == "(5,-2) interior"


def test_character_detail_shows_the_layer():
    rendered = build_character_detail(_snap("interior"))
    cells = [str(cell) for column in rendered.columns for cell in column.cells]
    assert "(5,-2) interior" in cells
    assert "(5,-2)" not in cells  # the bare coordinates would name another tile


def test_debug_log_line_shows_the_layer():
    assert "pos (5,-2) underground" in build_debug_log_line(_snap("underground"))
    assert "pos (5,-2) next" in build_debug_log_line(_snap())
