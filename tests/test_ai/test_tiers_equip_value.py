from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value


def test_sums_attack_resistance_hp_restore():
    s = ItemStats(code="x", level=1, type_="weapon",
                  attack={"fire": 10, "air": 2}, resistance={"earth": 3}, hp_restore=5)
    assert equip_value(s) == 20.0


def test_zero_when_no_stats():
    assert equip_value(ItemStats(code="x", level=1, type_="resource")) == 0.0


def test_equip_value_excludes_skill_effects():
    """Combat axis must NOT include skill_effects — tools score 0 here so
    they don't dominate a weapon_slot pick over a real combat weapon."""
    pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                       skill_effects={"mining": -1})
    assert equip_value(pickaxe) == 0.0


def test_tool_value_returns_effect_magnitude_for_matching_skill():
    """tool_value must score by the absolute magnitude of the skill_effect
    for the requested skill (the API encodes the effect negatively to
    indicate cooldown reduction)."""
    pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                       skill_effects={"mining": -1})
    assert tool_value(pickaxe, "mining") == 1.0


def test_tool_value_zero_when_skill_not_in_effects():
    """A pickaxe scores 0 for woodcutting — the wrong tool brings no benefit."""
    pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                       skill_effects={"mining": -1})
    assert tool_value(pickaxe, "woodcutting") == 0.0


def test_tool_value_zero_when_no_skill_effects():
    """A combat weapon has no skill_effects — tool axis scores 0."""
    dagger = ItemStats(code="copper_dagger", level=1, type_="weapon",
                      attack={"earth": 5})
    assert tool_value(dagger, "mining") == 0.0
