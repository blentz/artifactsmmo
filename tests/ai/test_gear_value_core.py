"""Tests for the ONE gear ruler: `gear_value` over the Rank / Combat / Gather
purposes, and the canonical adversary that makes Rank an instance of Combat
rather than a second formula. Mirrors Formal/GearValue.lean."""

import json
import statistics
from pathlib import Path

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.scoring import (
    RULER_SCALE,
    armor_score,
    gather_score,
    weapon_score,
)
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.gear_value import gear_components, gear_value
from artifactsmmo_cli.ai.gear_value_core import (
    RANK_MONSTER_RESISTANCE,
    RANK_MONSTER_TOTAL_ATTACK,
    RANK_REFERENCE_ATTACK,
    Combat,
    Gather,
    Rank,
    rank_adversary,
)
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value

_SNAPSHOT = Path(__file__).resolve().parents[2] / "formal" / "sim" / "game_data_snapshot.json"

# The four live items from the two bug reports this unification closes.
MUSHMUSH_JACKET = ItemStats(code="mushmush_jacket", level=10, type_="body_armor",
                            hp_bonus=60, dmg=10, critical_strike=3, wisdom=10)
ADVENTURER_VEST = ItemStats(code="adventurer_vest", level=10, type_="body_armor",
                            hp_bonus=60, dmg=6, wisdom=20)
LIFE_AMULET = ItemStats(code="life_amulet", level=15, type_="amulet", hp_bonus=30)
FIRE_AND_EARTH_AMULET = ItemStats(code="fire_and_earth_amulet", level=20, type_="amulet",
                                  hp_bonus=20, dmg_elements={"fire": 5, "earth": 5})


def _snapshot() -> dict[str, dict[str, dict[str, int]]]:
    with _SNAPSHOT.open() as fh:
        data: dict[str, dict[str, dict[str, int]]] = json.load(fh)
    return data


# --- the canonical adversary is DERIVED, not chosen ---------------------------

def test_reference_attack_is_the_catalog_median_monster_total_attack() -> None:
    """`RANK_MONSTER_TOTAL_ATTACK` must stay the median total attack over EVERY
    monster in the pinned live catalog. If the game's monster roster shifts, this
    fails rather than leaving Rank calibrated against a game that no longer
    exists — the "API data or fail" rule applied to a derived constant."""
    totals = [sum(atk.values()) for atk in _snapshot()["monster_attack"].values()]
    assert len(totals) > 1
    assert statistics.median(totals) == RANK_MONSTER_TOTAL_ATTACK
    assert RANK_MONSTER_TOTAL_ATTACK // len(ELEMENTS) == RANK_REFERENCE_ATTACK


def test_reference_resistance_is_the_catalog_median_monster_resistance() -> None:
    values = [v for res in _snapshot()["monster_resistance"].values() for v in res.values()]
    assert len(values) > 1
    assert statistics.median(values) == RANK_MONSTER_RESISTANCE


def test_rank_adversary_is_uniform_and_symmetric() -> None:
    """Uniform over elements (a monster-independent ruler has no evidence for
    preferring one element) and symmetric between the two sides (a
    level-appropriate fight is one where both sides' output is comparable —
    that is what fixes the defense-vs-offense exchange rate)."""
    adversary = rank_adversary()
    assert adversary.monster_attack == {e: RANK_REFERENCE_ATTACK for e in ELEMENTS}
    assert adversary.player_attack == adversary.monster_attack
    assert adversary.monster_resistance == {e: RANK_MONSTER_RESISTANCE for e in ELEMENTS}


def test_symmetric_duel_prices_resistance_and_damage_equally() -> None:
    """The calibration claim in `RANK_REFERENCE_ATTACK`'s docstring, checked:
    with both sides at `m` per element, `r`% resistance in every element and
    `r`% global damage are worth exactly the same."""
    r = 5
    all_resist = ItemStats(code="r", level=1, type_="body_armor",
                           resistance={e: r for e in ELEMENTS})
    all_damage = ItemStats(code="d", level=1, type_="body_armor", dmg=r)
    assert gear_value(all_resist, Rank) == gear_value(all_damage, Rank)


# --- Rank IS Combat -----------------------------------------------------------

def test_rank_is_combat_against_the_canonical_adversary() -> None:
    """The whole of the difference between the two purposes: one algorithm,
    parameterised by what the caller knows."""
    for stats in (MUSHMUSH_JACKET, LIFE_AMULET, FIRE_AND_EARTH_AMULET,
                  ItemStats(code="w", level=1, type_="weapon", attack={"fire": 6},
                            critical_strike=35)):
        assert gear_value(stats, Rank) == gear_value(stats, rank_adversary())


def test_rank_weapon_branch_is_weapon_score_against_the_canonical_monster() -> None:
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"fire": 6},
                       critical_strike=35)
    assert gear_value(weapon, Rank) == weapon_score(
        weapon, dict(rank_adversary().monster_resistance))


def test_rank_armor_branch_is_armor_score_against_the_canonical_monster() -> None:
    adversary = rank_adversary()
    assert gear_value(MUSHMUSH_JACKET, Rank) == armor_score(
        MUSHMUSH_JACKET, dict(adversary.monster_attack),
        dict(adversary.monster_resistance), dict(adversary.player_attack))


def test_gear_value_accepts_rank_class_or_instance() -> None:
    assert gear_value(LIFE_AMULET, Rank) == gear_value(LIFE_AMULET, Rank())


def test_gear_value_rejects_unsupported_purpose() -> None:
    s = ItemStats(code="x", level=1, type_="weapon")
    try:
        gear_value(s, object())
    except ValueError as exc:
        assert "unsupported purpose" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unsupported purpose")


# --- the two orderings this unification was required to fix -------------------

def test_mushmush_jacket_outranks_adventurer_vest_under_rank() -> None:
    """The owner's original complaint, closed on the PURSUIT side.

    `adventurer_vest` (hp 60, dmg 6, wisdom 20) beat `mushmush_jacket` (hp 60,
    dmg 10, crit 3, wisdom 10) under the retired flat Rank sum, 173 to 167,
    purely because that sum weighted 10 extra wisdom the same as 4 points of
    global damage plus 3 points of crit. `armor_score` had already been fixed;
    Rank had not."""
    assert gear_value(MUSHMUSH_JACKET, Rank) > gear_value(ADVENTURER_VEST, Rank)
    assert equip_value(MUSHMUSH_JACKET) > equip_value(ADVENTURER_VEST)


def test_amulet_pair_ordered_the_same_way_by_rank_and_by_combat() -> None:
    """The 2026-08-04 equip loop: the tree equipped `life_amulet` by Rank and the
    picker equipped `fire_and_earth_amulet` back by Combat, forever.

    Rank now orders the pair the way Combat does — strictly, and for 57 of the
    58 monsters in the pinned catalog (the retired flat sum ordered them the
    OPPOSITE way, `life_amulet` 30000 to 20000, which is what drove the loop)."""
    assert gear_value(FIRE_AND_EARTH_AMULET, Rank) > gear_value(LIFE_AMULET, Rank)
    snap = _snapshot()
    disagreeing = [
        monster for monster, attack in snap["monster_attack"].items()
        if gear_value(FIRE_AND_EARTH_AMULET,
                      Combat(attack, snap["monster_resistance"][monster],
                             {"earth": 44}))
        < gear_value(LIFE_AMULET,
                     Combat(attack, snap["monster_resistance"][monster],
                            {"earth": 44}))
    ]
    assert disagreeing == ["corrupted_ogre"]


def test_no_monster_blind_ruler_agrees_with_combat_everywhere() -> None:
    """The honest limit of the unification, and why the loop is closed by
    DOMINANCE rather than by agreement.

    `corrupted_ogre` resists earth 100%, so an earth-armed wearer's damage
    percentages are clamped to nothing and `life_amulet`'s extra 10 max HP wins
    there. No monster-BLIND total order can agree with a monster-RELATIVE one on
    every monster (`equipment/slot_occupancy` says exactly this), so agreement is
    not what stops the loop: `may_displace` does. Neither amulet stat-wise
    dominates the other, so the acquisition path may not pre-empt the picker for
    this pair in EITHER direction, and there is no swap to alternate."""
    snap = _snapshot()
    ogre = Combat(snap["monster_attack"]["corrupted_ogre"],
                  snap["monster_resistance"]["corrupted_ogre"], {"earth": 44})
    assert gear_value(LIFE_AMULET, ogre) > gear_value(FIRE_AND_EARTH_AMULET, ogre)
    assert gear_value(FIRE_AND_EARTH_AMULET, Rank) > gear_value(LIFE_AMULET, Rank)
    assert not may_displace(FIRE_AND_EARTH_AMULET, LIFE_AMULET)
    assert not may_displace(LIFE_AMULET, FIRE_AND_EARTH_AMULET)


def test_wisdom_is_no_longer_weighted_one_to_one_against_combat_stats() -> None:
    """One point of per-element resistance must outweigh one point of wisdom —
    wisdom is an XP rate, not damage, and `armor_score` keeps flat utility on
    its own footing."""
    one_wisdom = ItemStats(code="w", level=1, type_="body_armor", wisdom=1)
    one_resist = ItemStats(code="r", level=1, type_="body_armor", resistance={"fire": 1})
    assert gear_value(one_resist, Rank) > gear_value(one_wisdom, Rank)
    assert gear_value(one_resist, Rank) == RANK_REFERENCE_ATTACK * gear_value(one_wisdom, Rank)


def test_hp_restore_is_priced_by_the_one_ruler() -> None:
    """`hp_restore` joined `armor_score`'s flat-utility block when Rank moved
    onto it: a healing potion must not score 0, or the progression tree's
    `gain > 0` utility-slot gate empties out."""
    potion = ItemStats(code="small_health_potion", level=5, type_="utility",
                       hp_restore=60)
    assert gear_value(potion, Rank) == RULER_SCALE * 200 * 60
    adversary = rank_adversary()
    assert armor_score(potion, dict(adversary.monster_attack),
                       dict(adversary.monster_resistance),
                       dict(adversary.player_attack)) == RULER_SCALE * 200 * 60


# --- the non-tool tiebreak survives the move ----------------------------------

def test_rank_keeps_the_non_tool_tiebreak() -> None:
    """`weapon_score`'s `nonToolBonus`: on a raw-attack tie the non-tool weapon
    strictly wins (the fishing_net invariant)."""
    net = ItemStats(code="fishing_net", level=1, type_="weapon",
                    attack={"water": 5}, subtype="tool",
                    skill_effects={"fishing": -10})
    dagger = ItemStats(code="copper_dagger", level=1, type_="weapon",
                       attack={"earth": 5}, subtype="dagger")
    assert gear_value(dagger, Rank) == gear_value(net, Rank) + 1


# --- the ruler's own (COMBAT, EFFICIENCY) partition, which the ECONOMICS layer
# --- reads instead of a flat sum of its own ----------------------------------

def test_gear_components_partition_the_ruler() -> None:
    """`combat + efficiency == gear_value` on BOTH branches, for every item.
    This identity is what makes `tiers/pursuit_value` a re-reading of the one
    ruler rather than a second scorer. Mirrors `GearValue.rankValue_decomp`."""
    for stats in (MUSHMUSH_JACKET, ADVENTURER_VEST, LIFE_AMULET,
                  FIRE_AND_EARTH_AMULET,
                  ItemStats(code="w", level=1, type_="weapon",
                            attack={"fire": 6}, wisdom=100)):
        combat, efficiency = gear_components(stats, Rank)
        assert combat + efficiency == gear_value(stats, Rank)


def test_efficiency_term_is_the_four_time_buying_stats() -> None:
    """200 per point (the scale `armor_score` has always carried flat utility
    at), all four weighted alike, and NOTHING else in it."""
    stats = ItemStats(code="u", level=1, type_="artifact", hp_bonus=99,
                      wisdom=1, prospecting=2, inventory_space=3, haste=4)
    assert gear_components(stats, Rank)[1] == RULER_SCALE * 200 * (1 + 2 + 3 + 4)


def test_weapon_efficiency_term_prices_the_same_stats_as_armors() -> None:
    """A WEAPON's efficiency stats reach the ruler, at the SAME price armor pays.

    The four live voidstone tools carry 100 prospecting each and the ruler used
    to see none of it: `weapon_score` had no flat-utility block, so
    `gear_components` reported efficiency 0 on the weapon branch and a weapon's
    wisdom / prospecting / inventory_space / haste contributed to no purpose at
    all. Both branches now read `scoring.gear_score_efficiency`."""
    tool = ItemStats(code="voidstone_pickaxe", level=1, type_="weapon",
                     subtype="tool", attack={"earth": 5}, prospecting=100)
    combat, efficiency = gear_components(tool, Rank)
    assert efficiency == RULER_SCALE * 200 * 100
    assert combat + efficiency == gear_value(tool, Rank)
    # The combat term still takes no efficiency stat: dropping the prospecting
    # moves ONLY the efficiency half.
    bare = ItemStats(code="bare_pickaxe", level=1, type_="weapon",
                     subtype="tool", attack={"earth": 5})
    assert gear_components(bare, Rank) == (combat, 0)


def test_a_stat_costs_the_same_on_a_weapon_as_on_armor() -> None:
    """NO DOUBLE COUNT, NO SLOT PREMIUM: 100 prospecting is worth exactly the
    same number of ruler units whether an artifact or a weapon carries it, and
    it lands in the EFFICIENCY term on both."""
    for stat in ("wisdom", "prospecting", "inventory_space", "haste"):
        weapon = ItemStats(code="w", level=1, type_="weapon", **{stat: 100})
        artifact = ItemStats(code="a", level=1, type_="artifact", **{stat: 100})
        bare_w = ItemStats(code="w0", level=1, type_="weapon")
        bare_a = ItemStats(code="a0", level=1, type_="artifact")
        assert (gear_value(weapon, Rank) - gear_value(bare_w, Rank)
                == gear_value(artifact, Rank) - gear_value(bare_a, Rank)
                == RULER_SCALE * 200 * 100), stat
        assert gear_components(weapon, Rank)[1] == gear_components(artifact, Rank)[1]


def test_weapons_and_armor_are_on_one_scale_cross_slot() -> None:
    """THE COMMENSURABILITY FIX, on live catalog witnesses.

    `RULER_SCALE` used to multiply only the weapon term, so a weapon's number was
    twice an armor's for the same real effect. At the canonical adversary
    `copper_dagger` (level 1) and `steel_armor` (level 20) both scored 282_00x —
    a tie — while the dagger contributes 7.05 HP of swing per turn and the armor
    14.10. Cross-slot rankings (`pursuit_value`, the progression tree) compare
    exactly these numbers, so the tie was a 2x thumb on the weapon's side.

    The unit is `1/(RULER_SCALE * 20000)` of one HP of damage swing per turn on
    BOTH slots; the assertions below are stated in HP/turn to say so."""
    # Stats verbatim from /v3/items (the pinned bundle).
    dagger = ItemStats(code="copper_dagger", level=1, type_="weapon",
                       attack={"air": 6}, critical_strike=35)
    armor = ItemStats(code="steel_armor", level=20, type_="body_armor",
                      resistance={"earth": 5, "water": 5}, hp_bonus=90,
                      dmg_elements={"earth": 15, "water": 15})
    unit = RULER_SCALE * 20000  # ruler units per HP of swing per turn
    # copper_dagger: 6 attack, unresisted, x the (200+35)/200 crit multiplier
    # (the `- 1` strips the non-tool tie-break, which is not a swing).
    assert gear_value(dagger, Rank) - 1 == RULER_SCALE * 6 * 100 * 235
    assert (gear_value(dagger, Rank) - 1) / unit == 7.05
    # steel_armor: 2 elements x 33 reference attack x 5% resistance (defense),
    # + 2 elements x 33 attack x 15% element damage (offense), + 90 hp.
    assert gear_value(armor, Rank) == RULER_SCALE * (66_000 + 198_000 + 18_000)
    assert gear_value(armor, Rank) / unit == 14.1
    # The armor delivers twice the dagger's swing, and now scores twice as much.
    # Before the quantum moved onto the armor terms these two TIED at 282_00x.
    assert gear_value(armor, Rank) == 2 * (gear_value(dagger, Rank) - 1)


def test_combat_term_prices_resistance_far_above_hp_restore() -> None:
    """The category error this replaced: the retired flat `combat_raw` weighted
    a resistance PERCENTAGE 1:1 against an HP amount. On the ruler's own term
    one point of per-element resistance is worth `RANK_REFERENCE_ATTACK` (33)
    points of hp_restore — the canonical duel's exchange rate, not a constant
    anyone chose here."""
    one_resist = ItemStats(code="r", level=1, type_="amulet",
                           resistance={"fire": 1})
    one_heal = ItemStats(code="h", level=1, type_="amulet", hp_restore=1)
    assert (gear_components(one_resist, Rank)[0]
            == RANK_REFERENCE_ATTACK * gear_components(one_heal, Rank)[0])


def test_combat_purpose_matches_weapon_and_armor_score() -> None:
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"fire": 6},
                       critical_strike=20)
    armor = ItemStats(code="a", level=1, type_="body_armor", resistance={"fire": 30},
                      hp_bonus=15)
    m_res = {"fire": 25}
    m_atk = {"fire": 40}
    p_atk = {"fire": 30}
    assert gear_value(weapon, Combat(m_atk, m_res, p_atk)) == weapon_score(weapon, m_res)
    assert (gear_value(armor, Combat(m_atk, m_res, p_atk))
            == armor_score(armor, m_atk, m_res, p_atk))


def test_gather_purpose_matches_gather_score() -> None:
    tool = ItemStats(code="axe", level=1, type_="weapon",
                     skill_effects={"woodcutting": -10})
    assert gear_value(tool, Gather("woodcutting")) == gather_score(tool, "woodcutting")
