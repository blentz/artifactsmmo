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


def test_values_utility_stats_wisdom_prospecting_hp_bonus():
    """Utility gear/artifacts: wisdom + prospecting + hp_bonus count toward value.
    novice_guide (hp 25, wisdom 25, prospecting 25, non-tool): raw=75 → 2*75+1=151.
    Before, valued 0 (wisdom/prospecting dropped) → discarded; now a high-value
    non-tool the ranker pursues and the discard logic protects."""
    art = ItemStats(code="novice_guide", level=10, type_="artifact",
                    hp_bonus=25, wisdom=25, prospecting=25)
    assert equip_value(art) == 151


def test_values_inventory_space_so_bags_are_pursued():
    """A bag's only stat is inventory_space (backpack=+35) → raw 35 → 2*35+1 = 71.
    Was valued 0 (inventory_space dropped) → never equipped; now a valued upgrade."""
    bag = ItemStats(code="backpack", level=10, type_="bag", inventory_space=35)
    assert equip_value(bag) == 71


def test_values_haste_efficiency():
    """Haste (cooldown reduction) is valued like any utility: raw 8 → 2*8+1 = 17.
    Was dropped by the parser; now haste gear is pursued."""
    legs = ItemStats(code="haste_legs", level=1, type_="leg_armor", haste=8)
    assert equip_value(legs) == 17


def test_values_lifesteal_combat_sustain():
    """Lifesteal (heal-on-crit) is valued as a combat stat: raw 15 → 2*15+1 = 31."""
    ring = ItemStats(code="vampiric_ring", level=1, type_="ring", lifesteal=15)
    assert equip_value(ring) == 31


def test_values_combat_buff_potion():
    """Combat-buff potions (boost_dmg/res/hp + antipoison, summed into combat_buff)
    are valued as utility so the bot equips them: raw 20 → 2*20+1 = 41 (PLAN #3a)."""
    pot = ItemStats(code="enchanted_boost_potion", level=1, type_="utility", combat_buff=20)
    assert equip_value(pot) == 41


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
