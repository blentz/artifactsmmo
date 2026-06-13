"""Color palette constant tests."""

from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    MONSTER_COLOR,
    NPC_COLOR,
    PLAYER_COLOR,
    STRUCTURE_COLOR,
    UNMAPPED_COLOR,
    WALKABLE_COLOR,
)


def test_color_constants():
    assert PLAYER_COLOR == "bright_yellow"
    assert NPC_COLOR == "cyan"
    assert MONSTER_COLOR == "red"
    assert STRUCTURE_COLOR == "white"
    assert DOOR_COLOR == "magenta"
    assert UNMAPPED_COLOR == "grey15"
    assert WALKABLE_COLOR == "grey50"
