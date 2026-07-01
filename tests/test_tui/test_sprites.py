"""Sprite tileset data integrity + validator."""

import pytest

from artifactsmmo_cli.tui.sprites import (
    ALL_CURATED_SPRITES,
    BLANK_SPRITE,
    MONSTER_SPRITES,
    NPC_SPRITES,
    PLAYER_SPRITE,
    SPRITE_SIZE,
    TRANSPARENT,
    Sprite,
    SpriteCategory,
    recolor,
    validate_sprite,
)


def test_every_curated_sprite_is_8x8():
    for name, sprite in ALL_CURATED_SPRITES.items():
        assert len(sprite.rows) == SPRITE_SIZE, name
        assert all(len(row) == SPRITE_SIZE for row in sprite.rows), name


def test_every_used_palette_key_is_defined():
    for name, sprite in ALL_CURATED_SPRITES.items():
        for row in sprite.rows:
            for ch in row:
                if ch != TRANSPARENT:
                    assert ch in sprite.palette, f"{name}: {ch!r} undefined"


def test_blank_sprite_is_all_transparent():
    assert all(set(row) == {TRANSPARENT} for row in BLANK_SPRITE.rows)
    assert BLANK_SPRITE.palette == {}


def test_player_sprite_is_curated():
    assert PLAYER_SPRITE in ALL_CURATED_SPRITES.values()


def test_validate_rejects_wrong_row_count():
    bad = Sprite(rows=("#" * 8,) * 7, palette={"#": "white"})
    with pytest.raises(ValueError, match="rows"):
        validate_sprite("bad", bad)


def test_validate_rejects_wrong_col_count():
    bad = Sprite(rows=("#" * 7,) * 8, palette={"#": "white"})
    with pytest.raises(ValueError, match="cols"):
        validate_sprite("bad", bad)


def test_validate_rejects_undefined_palette_key():
    bad = Sprite(rows=("Z" + "." * 7,) + ("." * 8,) * 7, palette={})
    with pytest.raises(ValueError, match="palette"):
        validate_sprite("bad", bad)


def test_category_members():
    assert {c.value for c in SpriteCategory} == {
        "player", "monster", "npc", "structure", "resource",
    }


def test_recolor_keeps_shape_swaps_palette():
    base = Sprite(rows=("#" * 8,) * 8, palette={"#": "red"})
    out = recolor(base, {"#": "blue"})
    assert out.rows == base.rows
    assert out.palette == {"#": "blue"}
    validate_sprite("recolored", out)  # must stay a valid 8x8 with defined keys


@pytest.mark.parametrize("code", sorted(MONSTER_SPRITES))
def test_every_curated_monster_sprite_is_valid(code):
    validate_sprite(code, MONSTER_SPRITES[code])


@pytest.mark.parametrize("code", sorted(NPC_SPRITES))
def test_every_curated_npc_sprite_is_valid(code):
    validate_sprite(code, NPC_SPRITES[code])
