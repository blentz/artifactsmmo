"""SpriteRegistry: curated hits + deterministic checksum-marked fallback."""

from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import (
    GREEN_SLIME_SPRITE,
    MARK_COLOR,
    MARK_KEY,
    PLAYER_SPRITE,
    SpriteCategory,
    validate_sprite,
)


def test_player_category_returns_player_sprite():
    reg = SpriteRegistry()
    assert reg.sprite_for("hero", SpriteCategory.PLAYER) is PLAYER_SPRITE


def test_curated_code_returns_curated_sprite():
    reg = SpriteRegistry()
    assert reg.sprite_for("green_slime", SpriteCategory.MONSTER) is GREEN_SLIME_SPRITE


def test_unknown_code_returns_valid_fallback_sprite():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("orc", SpriteCategory.MONSTER)
    validate_sprite("orc-fallback", sprite)  # raises if malformed


def test_fallback_is_cached_identical():
    reg = SpriteRegistry()
    a = reg.sprite_for("orc", SpriteCategory.MONSTER)
    b = reg.sprite_for("orc", SpriteCategory.MONSTER)
    assert a is b


def test_fallback_marking_differs_by_code():
    reg = SpriteRegistry()
    a = reg.sprite_for("orc", SpriteCategory.MONSTER)       # checksum 324
    b = reg.sprite_for("wolf", SpriteCategory.MONSTER)      # checksum 440
    assert a.rows != b.rows


def test_fallback_uses_category_color_and_mark_palette():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("orc", SpriteCategory.MONSTER)
    assert sprite.palette[MARK_KEY] == MARK_COLOR
    assert "#" in sprite.palette


def test_empty_code_fallback_has_no_marks():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("", SpriteCategory.MONSTER)  # checksum 0 -> no marks
    assert all(MARK_KEY not in row for row in sprite.rows)
