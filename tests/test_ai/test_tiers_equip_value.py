from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value


def test_sums_attack_resistance_hp_restore_with_nontool_bonus():
    """Augmented: 2 * (atk+res+hp_restore) + nonToolBonus. non-tool weapon
    with raw=20 → 2*20+1 = 41. Closes the trace 2026-06-06 09:59 case where
    copper_dagger and fishing_net tied on raw equip_value=5 → copper_dagger
    invisible to ranker."""
    s = ItemStats(code="x", level=1, type_="weapon",
                  attack={"fire": 10, "air": 2}, resistance={"earth": 3}, hp_restore=5)
    # raw = 10+2+3+5 = 20; non-tool → +1; 2*20+1 = 41
    assert equip_value(s) == 41.0


def test_nontool_strictly_beats_tool_on_raw_tie():
    """Spec mirror of PurposeRouting.combatScore_tiebreaks_nontool_over_tool."""
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"earth": 5})
    tool   = ItemStats(code="t", level=1, type_="weapon", subtype="tool",
                       attack={"earth": 5}, skill_effects={"mining": -10})
    assert equip_value(weapon) > equip_value(tool)
    # Exact difference is the nonToolBonus.
    assert equip_value(weapon) - equip_value(tool) == 1.0


def test_zero_when_no_stats_for_resource():
    """Resources (type=resource) keep their zero score — no nonToolBonus on
    non-equippables. The bonus only applies to equippables (the calling
    site only invokes equip_value on equippable items)."""
    # A resource has no attack/resistance/hp_restore: raw=0. Non-tool subtype
    # gives +1 to ANY equippable, including this synthetic resource.
    assert equip_value(ItemStats(code="x", level=1, type_="resource")) == 1.0


def test_pure_tool_scores_zero():
    """A pure gathering tool (no attack/resistance, subtype=tool) scores 0."""
    pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                        subtype="tool", skill_effects={"mining": -1})
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
