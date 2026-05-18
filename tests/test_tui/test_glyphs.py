"""Glyph table structural tests."""

from artifactsmmo_cli.tui.glyphs import CONTENT_GLYPHS, PLAYER_GLYPH


def test_player_glyph_is_at():
    assert PLAYER_GLYPH == "@"


def test_essential_keys_present():
    for key in (
        "monster", "resource_woodcutting", "resource_mining",
        "resource_fishing", "resource_alchemy",
        "bank", "tasks_master", "npc", "workshop", "transition",
    ):
        assert key in CONTENT_GLYPHS, f"missing glyph key: {key}"


def test_each_entry_is_glyph_color_tuple():
    for key, value in CONTENT_GLYPHS.items():
        assert len(value) == 2, f"{key} should be (glyph, color)"
        glyph, color = value
        assert len(glyph) == 1, f"{key} glyph must be a single char"
        assert isinstance(color, str)
