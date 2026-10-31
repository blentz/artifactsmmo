"""Sprite tileset data integrity + validator."""

import pytest

from artifactsmmo_cli.tui.palette import BLOOD_RAMP, LEAF_RAMP, SLIME_RAMP, TUNIC_RAMP, Ramp
from artifactsmmo_cli.tui.sprites import (
    ALL_CURATED_SPRITES,
    BLANK_SPRITE,
    CURATED_BY_CATEGORY,
    GREEN_SLIME_SPRITE,
    MONSTER_SPRITES,
    NPC_SPRITES,
    PLAYER_SPRITE,
    SPRITE_SIZE,
    TRANSPARENT,
    Sprite,
    SpriteCategory,
    palette_of,
    reramp,
    shade_keys,
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


def test_shade_keys_names_the_four_shades_in_order():
    ramp = Ramp("#000001", "#000002", "#000003", "#000004")
    assert shade_keys(ramp, "odmL") == {"o": "#000001", "d": "#000002", "m": "#000003", "L": "#000004"}
    assert shade_keys(ramp, "_d_L") == {"d": "#000002", "L": "#000004"}


def test_palette_of_merges_later_fragments_over_earlier():
    assert palette_of({"a": "#000001", "b": "#000002"}, {"b": "#000003"}) == {"a": "#000001", "b": "#000003"}


def test_reramp_keeps_shape_and_swaps_every_shade_in_place():
    out = reramp(GREEN_SLIME_SPRITE, {SLIME_RAMP: TUNIC_RAMP})
    assert out.rows == GREEN_SLIME_SPRITE.rows
    for key, color in GREEN_SLIME_SPRITE.palette.items():
        if color in (SLIME_RAMP.outline, SLIME_RAMP.dark, SLIME_RAMP.mid, SLIME_RAMP.light):
            shade = [SLIME_RAMP.outline, SLIME_RAMP.dark, SLIME_RAMP.mid, SLIME_RAMP.light].index(color)
            assert out.palette[key] == [TUNIC_RAMP.outline, TUNIC_RAMP.dark, TUNIC_RAMP.mid,
                                        TUNIC_RAMP.light][shade]
        else:
            assert out.palette[key] == color          # eyes, glint: untouched
    validate_sprite("reramped", out)


def test_reramp_swaps_simultaneously():
    # {A: B, B: A} exchanges the two ramps rather than collapsing both to A.
    base = Sprite(rows=("ab" * 4,) * 8, palette={"a": LEAF_RAMP.mid, "b": BLOOD_RAMP.mid})
    out = reramp(base, {LEAF_RAMP: BLOOD_RAMP, BLOOD_RAMP: LEAF_RAMP})
    assert out.palette == {"a": BLOOD_RAMP.mid, "b": LEAF_RAMP.mid}


def _mask(sprite: Sprite) -> tuple[str, ...]:
    return tuple("".join("." if ch == TRANSPARENT else "#" for ch in row) for row in sprite.rows)


def test_no_two_drawings_share_a_silhouette():
    # The old tileset drew every humanoid as the same rounded box in a different
    # fill. Reramped variants share their base's ROWS (that is the point of a
    # family); two sprites drawn differently must also differ in outline.
    drawings: dict[tuple[str, ...], str] = {}
    sprites = {"player": PLAYER_SPRITE}
    for category in CURATED_BY_CATEGORY.values():
        sprites.update(category)
    for name, sprite in sorted(sprites.items()):
        drawings.setdefault(sprite.rows, name)
    masks: dict[tuple[str, ...], str] = {}
    for rows, name in drawings.items():
        mask = _mask(Sprite(rows=rows, palette={}))
        assert mask not in masks, f"{name} has the same silhouette as {masks.get(mask)}"
        masks[mask] = name


@pytest.mark.parametrize("code", sorted(MONSTER_SPRITES))
def test_every_curated_monster_sprite_is_valid(code):
    validate_sprite(code, MONSTER_SPRITES[code])


@pytest.mark.parametrize("code", sorted(NPC_SPRITES))
def test_every_curated_npc_sprite_is_valid(code):
    validate_sprite(code, NPC_SPRITES[code])
