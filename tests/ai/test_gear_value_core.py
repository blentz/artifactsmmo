"""Tests for the ONE gear ruler: `gear_value` over the Rank / Combat / Gather
purposes, and the canonical adversary that makes Rank an instance of Combat
rather than a second formula. Mirrors Formal/GearValue.lean."""

import json
import statistics
from pathlib import Path

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import (
    RANK_MONSTER_RESISTANCE,
    RANK_MONSTER_TOTAL_ATTACK,
    RANK_REFERENCE_ATTACK,
    Combat,
    Gather,
    Rank,
    combat_raw,
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
    assert gear_value(potion, Rank) == 200 * 60
    adversary = rank_adversary()
    assert armor_score(potion, dict(adversary.monster_attack),
                       dict(adversary.monster_resistance),
                       dict(adversary.player_attack)) == 200 * 60


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


# --- the untouched economics atom --------------------------------------------

def test_combat_raw_sums_eight_stats() -> None:
    """`combat_raw` is NOT a gear ruler — it is `strategic_value`'s single
    "how much combat is in this item" scalar. It keeps its own tests because it
    keeps its own job."""
    assert combat_raw(attack=3, resistance=2, hp_restore=1, hp_bonus=4, dmg=5,
                      critical_strike=6, lifesteal=7, combat_buff=8) == 36


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
