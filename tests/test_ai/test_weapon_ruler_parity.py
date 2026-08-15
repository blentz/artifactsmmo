"""The weapon slot's two asymmetries against the rest of the gear ruler, closed.

Until this change the weapon slot sat outside two properties every other slot
had:

1. **Scale.** ``weapon_score`` was ``2 * raw + nonToolBonus`` while
   ``armor_score`` was ``1 *`` its terms, so a weapon's number was twice an
   armor's for the same real effect. ``pursuit_value`` and the progression tree
   compare the two CROSS-SLOT by design, so that factor was a thumb on the
   weapon's side of every such ranking. The ``2`` is not arbitrary — it is what
   keeps the ``+1`` non-tool tie-break from flipping a genuine ordering — so it
   was moved onto EVERY term (``scoring.RULER_SCALE``) rather than deleted.
2. **Efficiency.** ``weapon_score`` had no flat-utility block at all, so a
   weapon's wisdom / prospecting / inventory_space / haste contributed nothing
   to any purpose. Five live items carry those stats.

Both are asserted here against the pinned catalog bundle, together with the
invariants that had to survive: the fishing_net tie-break, cross-slot combat
dominance, and no double-counting of utility.

Mirrors `Formal.PurposeRouting.ruler_commensurate`,
`weaponScore_efficiency_eq_AEfficiency`, `weaponScore_tiebreaks_nontool_over_tool`
and `nonToolBonus_lt_rulerScale`.
"""
import dataclasses
import json
from pathlib import Path

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.scoring import (
    RULER_SCALE,
    armor_score,
    gear_score_efficiency,
    weapon_score,
    weapon_score_combat,
    weapon_score_raw,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_components, gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank, rank_adversary
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value

BUNDLE = (Path(__file__).resolve().parents[1] / "test_ai" / "scenarios"
          / "fixtures" / "gamedata_bundle.json")

# The four live tools the prior report named: 100 prospecting each, and the
# ruler could not see a point of it.
VOIDSTONE_TOOLS = ("voidstone_pickaxe", "voidstone_axe", "voidstone_gloves",
                   "voidstone_fishing_rod")

_NO_RES: dict[str, int] = {}


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


# --- Defect 2: a weapon's efficiency stats reach the ruler ---------------------

def test_the_four_voidstone_tools_efficiency_stats_now_score() -> None:
    """Each voidstone tool carries 100 prospecting. The ruler used to price it
    at 0; it now prices it at exactly what an artifact's 100 prospecting costs."""
    gd = _bundle()
    for code in VOIDSTONE_TOOLS:
        stats = gd.item_stats(code)
        assert stats is not None, code
        assert stats.type_ == "weapon" and stats.prospecting == 100, code

        stripped = dataclasses.replace(stats, prospecting=0)
        gain = gear_value(stats, Rank) - gear_value(stripped, Rank)
        assert gain == RULER_SCALE * 200 * 100, code

        # It lands in the EFFICIENCY term, never in the combat term — the
        # structural no-double-count property `pursuit_value` rides.
        combat, efficiency = gear_components(stats, Rank)
        assert efficiency == RULER_SCALE * 200 * 100, code
        assert combat == gear_components(stripped, Rank)[0], code
        assert combat + efficiency == gear_value(stats, Rank), code


def test_obsidian_battleaxe_now_pays_its_inventory_penalty() -> None:
    """The fifth affected item, and the one that shows the term is SIGNED:
    obsidian_battleaxe carries `inventory_space = -25`, a penalty the ruler used
    to hand it for free."""
    gd = _bundle()
    axe = gd.item_stats("obsidian_battleaxe")
    assert axe is not None and axe.inventory_space == -25
    neutral = dataclasses.replace(axe, inventory_space=0)
    assert gear_value(axe, Rank) - gear_value(neutral, Rank) == RULER_SCALE * 200 * -25
    assert gear_score_efficiency(axe) < 0


def test_a_stat_prices_identically_on_a_weapon_and_on_armor() -> None:
    """NO SLOT PREMIUM. The two branches call the SAME `gear_score_efficiency`,
    so the ruler cannot charge for a stat by which slot happens to carry it."""
    for stat in ("wisdom", "prospecting", "inventory_space", "haste"):
        for magnitude in (-25, 1, 100):
            weapon = ItemStats(code="w", level=1, type_="weapon", **{stat: magnitude})
            armour = ItemStats(code="a", level=1, type_="helmet", **{stat: magnitude})
            assert gear_score_efficiency(weapon) == gear_score_efficiency(armour)
            assert (gear_components(weapon, Rank)[1]
                    == gear_components(armour, Rank)[1]
                    == RULER_SCALE * 200 * magnitude), (stat, magnitude)


def test_utility_is_not_counted_twice_on_the_weapon_branch() -> None:
    """The weapon COMBAT term takes no efficiency stat as a parameter, so adding
    one moves the efficiency half and NOTHING else — the same guarantee
    `armor_score_combat_pure` gives on the armor branches."""
    bare = ItemStats(code="w", level=1, type_="weapon", attack={"earth": 20})
    rich = dataclasses.replace(bare, wisdom=40, prospecting=40, haste=5)
    assert weapon_score_combat(rich, _NO_RES) == weapon_score_combat(bare, _NO_RES)
    assert (weapon_score(rich, _NO_RES) - weapon_score(bare, _NO_RES)
            == RULER_SCALE * 200 * (40 + 40 + 5))


# --- Defect 1: one scale across the slots -------------------------------------

def test_a_weapon_and_an_armor_of_equal_swing_score_equally() -> None:
    """COMMENSURABILITY, stated in HP of damage swing per turn.

    At the canonical adversary (33 attack per element, 0 resistance) a weapon
    with `a` attack in one element adds `a` HP of swing per turn, and a piece of
    armour with `r`% resistance in one element stops `33*r/100`. Choose the two
    so the swings are EQUAL and the ruler must return the same number (bar the
    non-tool tie-break, which is not a swing).

    Before `RULER_SCALE` moved onto the armor terms the armor scored HALF."""
    unit = RULER_SCALE * 20000  # ruler units per HP of swing per turn
    for attack, resistance in ((33, 100), (66, 200), (99, 300)):
        weapon = ItemStats(code="w", level=1, type_="weapon",
                           attack={"earth": attack})
        armour = ItemStats(code="a", level=1, type_="body_armor",
                           resistance={"earth": resistance})
        swing = attack  # HP per turn, unresisted
        assert 33 * resistance == 100 * swing, (attack, resistance)
        assert (gear_value(weapon, Rank) - 1) == gear_value(armour, Rank)
        assert (gear_value(armour, Rank)) / unit == float(swing)


def test_the_live_witness_that_used_to_tie() -> None:
    """The pair the prior report's "unearned thumb on the scale" produced:
    level-1 `copper_dagger` scored 282_001 and level-20 `steel_armor` 282_000 —
    a dead heat — while the armor delivers exactly twice the swing."""
    gd = _bundle()
    dagger = gd.item_stats("copper_dagger")
    armour = gd.item_stats("steel_armor")
    assert dagger is not None and armour is not None
    unit = RULER_SCALE * 20000
    assert (gear_value(dagger, Rank) - 1) / unit == 7.05
    assert gear_value(armour, Rank) / unit == 14.1
    assert gear_value(armour, Rank) == 2 * (gear_value(dagger, Rank) - 1)


def test_every_ruler_term_is_a_multiple_of_the_quantum() -> None:
    """What makes the tie-break safe: the ONLY thing in the ruler that is not a
    multiple of `RULER_SCALE` is the non-tool bonus itself, and it is strictly
    smaller than `RULER_SCALE`. Checked over the whole live catalog."""
    gd = _bundle()
    adversary = rank_adversary()
    for stats in gd.all_item_stats.values():
        combat, efficiency = (gear_components(stats, Rank)
                              if stats.type_ != "" else (0, 0))
        assert efficiency % RULER_SCALE == 0, stats.code
        bonus = 0 if stats.type_ != "weapon" else (0 if stats.subtype == "tool" else 1)
        assert (combat - bonus) % RULER_SCALE == 0, stats.code
        if stats.type_ != "weapon":
            assert armor_score(stats, dict(adversary.monster_attack),
                               dict(adversary.monster_resistance),
                               dict(adversary.player_attack)) % RULER_SCALE == 0


# --- The invariants that had to survive ---------------------------------------

def test_fishing_net_invariant_non_tool_beats_attack_equivalent_tool() -> None:
    """THE 2026-06-06 TRACE, asserted directly. `fishing_net` (5 water, subtype
    tool) and an attack-equivalent real weapon tie on RAW score; the ruler must
    strictly prefer the real weapon, or the left-fold argmax picks on iteration
    order and the character grinds slimes with a net."""
    gd = _bundle()
    net = gd.item_stats("fishing_net")
    assert net is not None and net.subtype == "tool"
    twin = dataclasses.replace(net, code="net_but_a_weapon", subtype="")

    assert weapon_score_raw(net, _NO_RES) == weapon_score_raw(twin, _NO_RES)
    assert weapon_score(twin, _NO_RES) > weapon_score(net, _NO_RES)
    assert weapon_score(twin, _NO_RES) - weapon_score(net, _NO_RES) == 1


def test_the_non_tool_bonus_never_flips_a_strict_raw_inequality() -> None:
    """The other half of the invariant: a tool that is even ONE raw unit better
    still wins, because every ruler term is a multiple of `RULER_SCALE` and the
    bonus is strictly smaller than it. Swept over the smallest possible gaps."""
    for better_raw, worse_raw in ((1, 0), (2, 1), (7, 6), (100, 99)):
        tool = ItemStats(code="t", level=1, type_="weapon", subtype="tool",
                         attack={"earth": better_raw})
        real = ItemStats(code="r", level=1, type_="weapon", subtype="",
                         attack={"earth": worse_raw})
        assert weapon_score_raw(tool, _NO_RES) > weapon_score_raw(real, _NO_RES)
        assert weapon_score(tool, _NO_RES) > weapon_score(real, _NO_RES)
        # ... and the combat term alone, which is what the economics layer reads.
        assert weapon_score_combat(tool, _NO_RES) > weapon_score_combat(real, _NO_RES)


def test_cross_slot_combat_dominance_survives_the_rescale() -> None:
    """`Formal.StrategicValue.pursuit_combat_dominates`, on the historical
    witness: a prospecting-201 artifact must not outrank a modest combat weapon
    cross-slot. Doubling the armor terms cannot break this — the property is an
    order-embedding over the COMBAT term, which the efficiency block spans less
    than one unit of."""
    weapon = ItemStats(code="wpn", level=2, type_="weapon", attack={"earth": 30})
    artifact = ItemStats(code="art", level=2, type_="artifact", prospecting=201)
    assert pursuit_value(weapon) > pursuit_value(artifact)
    # And now that a WEAPON can carry efficiency too, the same holds with the
    # roles reversed: a prospecting tool cannot outrank a better fighter.
    tool = ItemStats(code="tool", level=2, type_="weapon", subtype="tool",
                     attack={"earth": 29}, prospecting=201)
    assert pursuit_value(weapon) > pursuit_value(tool)


def test_the_two_pinned_orderings_still_hold() -> None:
    """`mushmush_jacket` > `adventurer_vest` and `fire_and_earth_amulet` >
    `life_amulet` — the two live orderings pinned in `Contracts.lean`. A uniform
    rescale cannot reorder anything, and this says so on the live ruler."""
    jacket = ItemStats(code="mushmush_jacket", level=10, type_="body_armor",
                       hp_bonus=60, wisdom=10, dmg=10, critical_strike=3)
    vest = ItemStats(code="adventurer_vest", level=10, type_="body_armor",
                     hp_bonus=60, wisdom=20, dmg=6)
    assert gear_value(jacket, Rank) > gear_value(vest, Rank)

    life = ItemStats(code="life_amulet", level=15, type_="amulet", hp_bonus=30)
    fae = ItemStats(code="fire_and_earth_amulet", level=20, type_="amulet",
                    hp_bonus=20, dmg_elements={"fire": 5, "earth": 5})
    assert gear_value(fae, Rank) > gear_value(life, Rank)


def test_the_ruler_is_a_uniform_rescale_of_its_predecessor() -> None:
    """No item is REORDERED against another by this change on the armor side:
    every armor value is exactly twice what it was, so every armor-vs-armor
    verdict is preserved. Weapon combat terms are untouched. Checked by
    recomputing the pre-change armor value as `gear_value // RULER_SCALE`."""
    gd = _bundle()
    equippables = [s for s in gd.all_item_stats.values()
                   if s.type_ != "weapon" and gear_value(s, Rank) != 0]
    assert len(equippables) > 100
    for stats in equippables:
        assert gear_value(stats, Rank) % RULER_SCALE == 0, stats.code
    ranked_now = sorted(equippables, key=lambda s: (gear_value(s, Rank), s.code))
    ranked_before = sorted(equippables,
                           key=lambda s: (gear_value(s, Rank) // RULER_SCALE, s.code))
    assert [s.code for s in ranked_now] == [s.code for s in ranked_before]


def test_elements_are_the_four_the_ruler_prices() -> None:
    """Guard for the witnesses above: they assume the canonical adversary spreads
    its attack over exactly these four elements."""
    assert set(ELEMENTS) == {"fire", "earth", "water", "air"}
