"""Glyph table structural tests."""

from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    DOOR_GLYPH,
    MONSTER_COLOR,
    NPC_COLOR,
    PLAYER_GLYPH,
    RESOURCE_GLYPHS,
    STRUCTURE_COLOR,
    WALKABLE_GLYPH,
    monster_glyph,
    npc_glyph,
    structure_glyph,
)


def test_player_glyph_is_at():
    assert PLAYER_GLYPH == "@"


def test_walkable_glyph():
    assert WALKABLE_GLYPH == "·"


def test_npc_glyph_curated():
    assert npc_glyph("archaeologist") == ("A", NPC_COLOR)
    assert npc_glyph("tasks_trader") == ("K", NPC_COLOR)


def test_npc_glyph_fallback_first_letter_upper():
    assert npc_glyph("new_vendor") == ("N", NPC_COLOR)


def test_monster_glyph_family_collapses_to_one_letter():
    for code in ("blue_slime", "green_slime", "red_slime", "yellow_slime", "king_slime"):
        assert monster_glyph(code) == ("s", MONSTER_COLOR)
    assert monster_glyph("chicken") == ("c", MONSTER_COLOR)
    assert monster_glyph("goblin") == ("g", MONSTER_COLOR)
    assert monster_glyph("goblin_wolfrider") == ("g", MONSTER_COLOR)


def test_monster_glyph_fallback_first_letter_lower():
    assert monster_glyph("Dragon") == ("d", MONSTER_COLOR)


def test_structure_glyph_curated_and_fallback():
    assert structure_glyph("bank") == ("╣", STRUCTURE_COLOR)
    assert structure_glyph("grand_exchange") == ("╠", STRUCTURE_COLOR)
    assert structure_glyph("workshop") == ("╬", STRUCTURE_COLOR)
    assert structure_glyph("tasks_master") == ("╤", STRUCTURE_COLOR)
    assert structure_glyph("unknown_struct") == ("▢", STRUCTURE_COLOR)


def test_door_constants():
    assert DOOR_GLYPH == "+"
    assert DOOR_COLOR == "magenta"


def test_resource_glyphs_unchanged():
    assert RESOURCE_GLYPHS["resource_woodcutting"] == ("T", "green")
    assert RESOURCE_GLYPHS["resource_mining"] == ("*", "yellow")
    assert RESOURCE_GLYPHS["resource_fishing"] == ("~", "blue")
    assert RESOURCE_GLYPHS["resource_alchemy"] == ("%", "magenta")
