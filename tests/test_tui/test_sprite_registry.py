"""SpriteRegistry: curated hits + deterministic checksum-marked fallback."""

from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import (
    ALCHEMY_SPRITE,
    BLUE_SLIME_SPRITE,
    CHICKEN_SPRITE,
    COW_SPRITE,
    CULTIST_ACOLYTE_SPRITE,
    CULTIST_WIZARD_SPRITE,
    CYCLOPS_SPRITE,
    FISHING_SPRITE,
    FLYING_SNAKE_SPRITE,
    GOBLIN_SPRITE,
    GOBLIN_WOLFRIDER_SPRITE,
    GRAND_EXCHANGE_SPRITE,
    GREEN_SLIME_SPRITE,
    HIGHWAYMAN_SPRITE,
    IMP_SPRITE,
    MARK_COLOR,
    MARK_KEY,
    MINING_SPRITE,
    OGRE_SPRITE,
    ORC_SPRITE,
    OWLBEAR_SPRITE,
    PIG_SPRITE,
    PLAYER_SPRITE,
    RED_SLIME_SPRITE,
    RUNE_VENDOR_SPRITE,
    SAND_SNAKE_SPRITE,
    SANDWHISPER_TRADER_SPRITE,
    SHEEP_SPRITE,
    SPIDER_SPRITE,
    SpriteCategory,
    TAILOR_SPRITE,
    TASKS_MASTER_SPRITE,
    TASKS_TRADER_SPRITE,
    WOLF_SPRITE,
    WORKSHOP_SPRITE,
    YELLOW_SLIME_SPRITE,
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
    sprite = reg.sprite_for("dragon", SpriteCategory.MONSTER)
    validate_sprite("dragon-fallback", sprite)  # raises if malformed


def test_fallback_is_cached_identical():
    reg = SpriteRegistry()
    a = reg.sprite_for("dragon", SpriteCategory.MONSTER)
    b = reg.sprite_for("dragon", SpriteCategory.MONSTER)
    assert a is b


def test_fallback_marking_differs_by_code():
    reg = SpriteRegistry()
    a = reg.sprite_for("dragon", SpriteCategory.MONSTER)    # checksum 630
    b = reg.sprite_for("troll", SpriteCategory.MONSTER)     # checksum 539
    assert a.rows != b.rows


def test_fallback_uses_category_color_and_mark_palette():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("dragon", SpriteCategory.MONSTER)
    assert sprite.palette[MARK_KEY] == MARK_COLOR
    assert "#" in sprite.palette


def test_empty_code_fallback_has_no_marks():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("", SpriteCategory.MONSTER)  # checksum 0 -> no marks
    assert all(MARK_KEY not in row for row in sprite.rows)


def test_b1_structures_and_resources_are_curated():
    reg = SpriteRegistry()
    assert reg.sprite_for("grand_exchange", SpriteCategory.STRUCTURE) is GRAND_EXCHANGE_SPRITE
    assert reg.sprite_for("workshop", SpriteCategory.STRUCTURE) is WORKSHOP_SPRITE
    assert reg.sprite_for("tasks_master", SpriteCategory.STRUCTURE) is TASKS_MASTER_SPRITE
    assert reg.sprite_for("resource_mining", SpriteCategory.RESOURCE) is MINING_SPRITE
    assert reg.sprite_for("resource_fishing", SpriteCategory.RESOURCE) is FISHING_SPRITE
    assert reg.sprite_for("resource_alchemy", SpriteCategory.RESOURCE) is ALCHEMY_SPRITE


def test_b2_npcs_are_curated():
    reg = SpriteRegistry()
    assert reg.sprite_for("tailor", SpriteCategory.NPC) is TAILOR_SPRITE
    assert reg.sprite_for("cultist_wizard", SpriteCategory.NPC) is CULTIST_WIZARD_SPRITE
    assert reg.sprite_for("rune_vendor", SpriteCategory.NPC) is RUNE_VENDOR_SPRITE
    assert reg.sprite_for("sandwhisper_trader", SpriteCategory.NPC) is SANDWHISPER_TRADER_SPRITE
    assert reg.sprite_for("tasks_trader", SpriteCategory.NPC) is TASKS_TRADER_SPRITE


def test_b3_beasts_are_curated():
    reg = SpriteRegistry()
    cases = {
        "blue_slime": BLUE_SLIME_SPRITE, "red_slime": RED_SLIME_SPRITE,
        "yellow_slime": YELLOW_SLIME_SPRITE, "chicken": CHICKEN_SPRITE,
        "cow": COW_SPRITE, "pig": PIG_SPRITE, "sheep": SHEEP_SPRITE,
        "wolf": WOLF_SPRITE, "owlbear": OWLBEAR_SPRITE, "spider": SPIDER_SPRITE,
        "flying_snake": FLYING_SNAKE_SPRITE, "sand_snake": SAND_SNAKE_SPRITE,
    }
    for code, sprite in cases.items():
        assert reg.sprite_for(code, SpriteCategory.MONSTER) is sprite


def test_b4_humanoids_are_curated():
    reg = SpriteRegistry()
    cases = {
        "goblin": GOBLIN_SPRITE, "goblin_wolfrider": GOBLIN_WOLFRIDER_SPRITE,
        "orc": ORC_SPRITE, "ogre": OGRE_SPRITE, "cyclops": CYCLOPS_SPRITE,
        "imp": IMP_SPRITE, "highwayman": HIGHWAYMAN_SPRITE,
        "cultist_acolyte": CULTIST_ACOLYTE_SPRITE,
    }
    for code, sprite in cases.items():
        assert reg.sprite_for(code, SpriteCategory.MONSTER) is sprite
