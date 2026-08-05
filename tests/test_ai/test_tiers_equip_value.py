"""`equip_value` = `gear_value(stats, Rank)` = the ONE gear ruler, evaluated
against the catalog-median canonical adversary.

SCALE NOTE. These pins moved from the retired flat sum (`2 * raw + nonToolBonus`,
~10^2) to `weapon_score`/`armor_score`'s own scale (~10^3-10^6). The unit is
1/20000 of one HP of damage swing per combat turn for the monster-relative terms
and 200x per stat point for the flat-utility block — see
`equipment/scoring.armor_score_pure`. Every stat that mattered before still
matters; what changed is that they are now weighed against each other in a real
unit instead of summed 1:1.

The canonical adversary is 33 attack per element, 0 resistance, mirrored on the
wearer (`ai/gear_value_core`), so:

  * one point of per-element resistance   = 200 * 33            =  6600
  * one point of any flat-utility stat    = 200                 =   200
  * one point of global `dmg`             = 4 * 33 * 100 * 2    = 26400
  * one point of `critical_strike` (armor)= 4 * 33 * 100        = 13200
  * one point of weapon attack (no crit)  = 2 * 100 * 200       = 40000
"""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_value_core import RANK_REFERENCE_ATTACK
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value


def test_weapon_ranks_on_attack_through_the_non_tool_augmented_weapon_score():
    """A weapon's Rank is `weapon_score` against the canonical monster's zero
    resistance: `2 * (Σ atk * 100) * (200 + crit) + nonToolBonus`. Closes the
    trace 2026-06-06 09:59 case where copper_dagger and fishing_net tied on the
    raw score and copper_dagger went invisible to the ranker."""
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 10, "air": 2})
    assert equip_value(s) == 2 * (12 * 100) * 200 + 1


def test_weapon_crit_is_priced_by_the_same_expected_hit_multiplier():
    """`(200 + crit)` — the exact-integer form of `predict_win`'s expected
    critical multiplier. The retired flat sum added crit as one raw point."""
    plain = ItemStats(code="a", level=1, type_="weapon", attack={"fire": 10})
    crit = ItemStats(code="b", level=1, type_="weapon", attack={"fire": 10},
                     critical_strike=35)
    assert equip_value(crit) == 2 * (10 * 100) * 235 + 1
    assert equip_value(crit) > equip_value(plain)


def test_values_utility_stats_wisdom_prospecting_hp_bonus():
    """Utility gear/artifacts: wisdom + prospecting + hp_bonus all count, on the
    flat-utility block's shared 200x scale. novice_guide (hp 25, wisdom 25,
    prospecting 25) → 200 * 75. Before the flat-utility term existed these were
    valued 0 and the item was discarded."""
    art = ItemStats(code="novice_guide", level=10, type_="artifact",
                    hp_bonus=25, wisdom=25, prospecting=25)
    assert equip_value(art) == 200 * 75


def test_values_inventory_space_so_bags_are_pursued():
    """A bag's only stat is inventory_space (backpack=+35) → 200 * 35."""
    bag = ItemStats(code="backpack", level=10, type_="bag", inventory_space=35)
    assert equip_value(bag) == 200 * 35


def test_values_haste_efficiency():
    """Haste (cooldown reduction) is flat utility → 200 * 8."""
    legs = ItemStats(code="haste_legs", level=1, type_="leg_armor", haste=8)
    assert equip_value(legs) == 200 * 8


def test_values_lifesteal_combat_sustain():
    """Lifesteal (heal-on-crit) is flat utility → 200 * 15."""
    ring = ItemStats(code="vampiric_ring", level=1, type_="ring", lifesteal=15)
    assert equip_value(ring) == 200 * 15


def test_values_combat_buff_potion():
    """Combat-buff potions (boost_dmg/res/hp + antipoison, summed into
    combat_buff) → 200 * 20, so the bot equips them (PLAN #3a)."""
    pot = ItemStats(code="enchanted_boost_potion", level=1, type_="utility", combat_buff=20)
    assert equip_value(pot) == 200 * 20


def test_values_hp_restore_so_healing_potions_are_pursued():
    """`hp_restore` joined the flat-utility block when Rank moved onto
    `armor_score`. Without it every healing potion would rank 0 and the
    progression tree's `gain > 0` utility gate would empty out."""
    pot = ItemStats(code="small_health_potion", level=1, type_="utility", hp_restore=60)
    assert equip_value(pot) == 200 * 60


def test_resistance_outweighs_flat_utility_by_the_reference_attack():
    """The one exchange rate the unification changed on purpose: a point of
    resistance is worth `RANK_REFERENCE_ATTACK` points of wisdom, not one."""
    resist = ItemStats(code="r", level=1, type_="body_armor", resistance={"fire": 1})
    wise = ItemStats(code="w", level=1, type_="body_armor", wisdom=1)
    assert equip_value(resist) == RANK_REFERENCE_ATTACK * equip_value(wise)


def test_nontool_strictly_beats_tool_on_raw_tie():
    """Spec mirror of PurposeRouting.combatScore_tiebreaks_nontool_over_tool —
    carried through the unification unchanged, since Rank's weapon branch IS
    `weapon_score`."""
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"earth": 5})
    tool   = ItemStats(code="t", level=1, type_="weapon", subtype="tool",
                       attack={"earth": 5}, skill_effects={"mining": -10})
    assert equip_value(weapon) > equip_value(tool)
    # Exact difference is the nonToolBonus.
    assert equip_value(weapon) - equip_value(tool) == 1


def test_zero_when_no_stats_for_resource():
    """A stat-less item scores exactly 0.

    VERDICT CHANGE (was 1): the retired flat sum handed every non-tool a
    `nonToolBonus` of +1 whatever its stats, so a stat-less item was worth
    strictly more than nothing. The nonToolBonus is a WEAPON-branch tiebreaker
    (`weapon_score`) and non-weapons never had one, so a stat-less non-weapon is
    now worth what it is worth. This is what `pick_loadout`'s empty-slot gate
    (`best_score <= 0` → leave empty) always meant: do not spend a request
    equipping something with no stats."""
    assert equip_value(ItemStats(code="x", level=1, type_="resource")) == 0


def test_pure_tool_scores_zero():
    """A pure gathering tool (no attack, subtype=tool) scores 0 on the gear
    ruler — it is valued on the separate `tool_value` axis."""
    pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                        subtype="tool", skill_effects={"mining": -1})
    assert equip_value(pickaxe) == 0


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
