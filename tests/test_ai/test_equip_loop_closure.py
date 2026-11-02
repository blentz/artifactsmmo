"""The equip LOOP: two authorities alternating over one slot, and its closure.

Live 2026-08-04, character Robby (level 21). He wore `fire_and_earth_amulet`
and carried one `life_amulet`, and every cycle looked like this::

    c3  Equip(life_amulet->amulet_slot)   goal=UpgradeEquipment(life_amulet)
    c4  OptimizeLoadout(wolf)             goal=GrindCharacterXP(wolf)
    ...
    c9  Equip(life_amulet->amulet_slot)   goal=UpgradeEquipment(life_amulet)

Two rulers disagreed about who owns `amulet_slot`, and neither yielded — one
API request and one cooldown per leg, forever. The four numbers, all computed
below from live `/v3/items` + `/v3/monsters` stats:

    equip_value   life_amulet 61      fire_and_earth_amulet 41   (life wins)
    armor_score   life_amulet 6000    fire_and_earth_amulet 48000 (f&e wins)

`armor_score` prices `dmg_elements` (170ed8d8); the flat 8-stat `combat_raw`
sum — under `equip_value`, `strategic_value` and the progression tree's
`pursuit_value` — did not, and `fire_and_earth_amulet`'s ENTIRE offensive value
lives there.

The fix has two halves and this file pins both:

1. ARITHMETIC. There is now ONE ruler and the acquisition path reads its own
   COMBAT term (`gear_value.gear_components`), so "which stats exist" is not a
   question the two layers can answer differently. `combat_raw` — the flat sum
   that could not see per-element damage % — is deleted, along with the
   `dmg_elements` hoist that had been patching it.
2. STRUCTURE. No monster-blind total order can agree with a monster-relative
   one on every monster, so ties are not enough. `equipment/slot_occupancy`
   makes the acquisition path DEFER: it may pre-empt `pick_loadout` for an item
   it already owns only when that item dominates the incumbent stat-wise, which
   the scorers' monotonicity turns into "the picker never swaps it back".
"""

from dataclasses import replace

from artifactsmmo_cli.ai.equip_value import equip_value
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import RULER_SCALE, armor_score
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.world_state import WorldState

# --- API items (effects verbatim from /v3/items) ---------------------------

_LIFE_AMULET = ItemStats(code="life_amulet", level=5, type_="amulet", hp_bonus=30)
_FIRE_AND_EARTH_AMULET = ItemStats(
    code="fire_and_earth_amulet", level=10, type_="amulet",
    hp_bonus=20, dmg_elements={"fire": 5, "earth": 5},
)
_MUSHMUSH_JACKET = ItemStats(
    code="mushmush_jacket", level=15, type_="body_armor",
    hp_bonus=60, dmg=10, critical_strike=3, wisdom=10,
)
_ADVENTURER_VEST = ItemStats(
    code="adventurer_vest", level=10, type_="body_armor",
    hp_bonus=60, dmg=6, wisdom=20,
)
_PIGGY_ARMOR = ItemStats(
    code="piggy_armor", level=25, type_="body_armor",
    hp_bonus=150, dmg_elements={"fire": 22},
    resistance={"fire": 10, "earth": 5}, wisdom=30,
)

# --- API monsters (verbatim from /v3/monsters) -----------------------------

# wolf (level 15): what Robby was grinding. Weak to fire/earth (res -10).
_WOLF_ATK = {"fire": 0, "earth": 0, "water": 12, "air": 12}
_WOLF_RES = {"fire": -10, "earth": -10, "water": 10, "air": 10}
# rosenblood (level 40): 400 fire attack — where resistance is worth more than
# any damage percentage.
_ROSENBLOOD_ATK = {"fire": 400, "earth": 0, "water": 0, "air": 0}
_ROSENBLOOD_RES = {"fire": 10, "earth": 10, "water": 10, "air": 10}
# steel_battleaxe (level 20 weapon): attack_earth 40 — the picker-optimal
# level-<=21 weapon against a wolf, whose res_earth is -10.
_BATTLEAXE_ATTACK = {"earth": 40}
_FOREST_WHIP_ATTACK = {"air": 40}

_HARD_LEATHER_PANTS = ItemStats(
    code="hard_leather_pants", level=20, type_="leg_armor",
    hp_bonus=80, haste=2, dmg_elements={"air": 10, "earth": 10},
    resistance={"air": 6},
)
_ADVENTURER_PANTS = ItemStats(
    code="adventurer_pants", level=15, type_="leg_armor",
    hp_bonus=60, dmg=5, wisdom=20,
)
# A strictly worse leg piece: `hard_leather_pants` dominates it on every stat
# the scorers read, so the picker can never swap it back.
_OLD_PANTS = ItemStats(
    code="old_pants", level=1, type_="leg_armor", hp_bonus=5,
)

# battlestaff (level 20 weapon): attack_water 40 — HAL's weapon, and the reason
# `adventurer_pants`' GLOBAL 5% damage outscores `hard_leather_pants`' air/earth
# 10%: none of the latter applies to a water hit.
_BATTLESTAFF_ATTACK = {"water": 40}
# sheep (level 1): what HAL was actually fighting.
_SHEEP_ATK = {"air": 0, "earth": 14, "fire": 0, "water": 0}
_SHEEP_RES = {"air": 10, "earth": 10, "fire": 10, "water": 10}

_AMULET = "amulet_slot"
_BODY = "body_armor_slot"


def _gd(*items: ItemStats) -> GameData:
    gd = GameData()
    gd._item_stats = {it.code: it for it in items}
    return gd


def _state(level: int, inventory: dict[str, int],
           equipment: dict[str, str | None],
           attack: dict[str, int]) -> WorldState:
    return WorldState(
        character="robby", level=level, xp=0, max_xp=100, hp=200, max_hp=200,
        gold=0, skills={}, x=0, y=0, inventory=dict(inventory), inventory_max=100,
        inventory_slots_max=100, equipment=dict(equipment), cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack=dict(attack), dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0,
    )




# --- The four numbers -------------------------------------------------------

def test_the_two_amulets_now_score_the_same_way_on_both_rulers() -> None:
    """`fire_and_earth_amulet`'s whole offence is `dmg_elements`. Before the
    hoist the monster-blind ruler scored it 41 / 20000 against `life_amulet`'s
    61 / 30000 — a 10000 gain the progression tree chased every cycle — while
    the monster-relative scorer had it 48000 to 6000 the other way.

    Three fixes landed on top of each other and this pins the state after all:

    1. the `dmg_elements` hoist made the acquisition path stop disagreeing about
       which stats EXIST;
    2. unifying Rank onto `armor_score` made `equip_value` stop being a separate
       formula at all. It now prefers the element amulet 70000 to 6000, the same
       DIRECTION the monster-relative scorer does, because it is the same
       function evaluated against the catalog-median monster instead of a wolf;
    3. `pursuit_value`'s combat term became that same ruler's own combat term,
       so it stopped merely TYING the pair (30000 each, on a flat sum that could
       not see per-element damage) and now prefers the element amulet by the
       same ratio the ruler does. A tie was enough to stop the loop; agreement
       is what stops the two layers holding different opinions at all.
    """
    assert equip_value(_LIFE_AMULET) == RULER_SCALE * 6000
    assert equip_value(_FIRE_AND_EARTH_AMULET) == RULER_SCALE * 70000
    assert equip_value(_FIRE_AND_EARTH_AMULET) > equip_value(_LIFE_AMULET)

    # The monster-relative half is untouched and still prefers the element
    # amulet by the damage it adds to a 40-earth output vs res_earth -10.
    life = armor_score(_LIFE_AMULET, _WOLF_ATK, _WOLF_RES, _BATTLEAXE_ATTACK)
    fae = armor_score(_FIRE_AND_EARTH_AMULET, _WOLF_ATK, _WOLF_RES,
                      _BATTLEAXE_ATTACK)
    assert life == RULER_SCALE * 6000, life   # RULER_SCALE * (0 + 0 + 200*30)
    assert fae == RULER_SCALE * 48000, fae    # RULER_SCALE * (40*110*(2*5) + 200*20)
    assert fae > life


def test_both_authorities_put_the_same_amulet_in_robbys_slot() -> None:
    """The specific pair, both authorities, Robby's real state: he WEARS
    `fire_and_earth_amulet` and CARRIES `life_amulet`. The combat picker keeps
    what he wears, and the acquisition path proposes nothing — no swap, no
    cooldown, no request."""
    gd = _gd(_LIFE_AMULET, _FIRE_AND_EARTH_AMULET)
    state = _state(21, {"life_amulet": 1},
                   {_AMULET: "fire_and_earth_amulet"}, _BATTLEAXE_ATTACK)

    picked = pick_loadout(Combat(_WOLF_ATK, _WOLF_RES, _BATTLEAXE_ATTACK),
                          state, gd)
    assert picked[_AMULET] == "fire_and_earth_amulet", picked

    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment)
    assert goal.find_upgrade_target(state, gd) is None


# --- The loop, closed -------------------------------------------------------

def test_the_upgrade_goal_leg_of_the_loop_also_closes() -> None:
    """The OTHER producer of a displacing equip: `UpgradeEquipmentGoal`'s
    inventory path. `piggy_armor` (level 25) passes `_is_upgrade_over` against
    the worn `mushmush_jacket` (level 15) on level alone, but it trades away 3
    crit, so `pick_loadout` against a light hitter puts the jacket straight
    back. The goal defers instead, and the slot never moves."""
    gd = _gd(_MUSHMUSH_JACKET, _PIGGY_ARMOR)
    state = _state(25, {"piggy_armor": 1}, {_BODY: "mushmush_jacket"},
                   _FOREST_WHIP_ATTACK)
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment)
    assert goal.find_upgrade_target(state, gd) is None

    for _ in range(4):
        target = goal.find_upgrade_target(state, gd)
        if target is not None:
            code, slot = target
            state = replace(state, equipment={**state.equipment, slot: code})
        picked = pick_loadout(
            Combat(_WOLF_ATK, _WOLF_RES, state.attack), state, gd)
        state = replace(state, equipment=dict(picked))
        assert state.equipment[_BODY] == "mushmush_jacket", state.equipment


def test_deferring_loses_nothing_the_picker_equips_it_when_it_helps() -> None:
    """Deferral is not rejection. The SAME `piggy_armor` the upgrade goal
    declines to force is equipped by the one authority that can price it — against
    rosenblood's 400 fire attack, where 10% fire resistance is worth far more
    than the jacket's damage percentage."""
    gd = _gd(_MUSHMUSH_JACKET, _PIGGY_ARMOR)
    state = _state(25, {"piggy_armor": 1}, {_BODY: "mushmush_jacket"},
                   _FOREST_WHIP_ATTACK)
    picked = pick_loadout(
        Combat(_ROSENBLOOD_ATK, _ROSENBLOOD_RES, _FOREST_WHIP_ATTACK), state, gd)
    assert picked[_BODY] == "piggy_armor", picked


# --- 170ed8d8's win, on BOTH rulers now -------------------------------------

def test_mushmush_jacket_beats_adventurer_vest_on_both_rulers() -> None:
    """The armor fix that started this: the vest's 10 extra wisdom must not buy
    a 4-damage, 3-crit downgrade. `armor_score` has said so since 170ed8d8, and
    the tree's `pursuit_value` — whose efficiency budget is what keeps wisdom
    sub-dominant — agrees.

    `equip_value` now agrees too (317600 vs 174400). It used to get this
    BACKWARDS, 167 to 173, because the flat sum weighted 10 extra wisdom the same
    as 4 points of global damage plus 3 points of crit; unifying Rank onto
    `armor_score` removed the separate formula that could hold the wrong opinion.
    `may_displace` still refuses the vest over the jacket outright, so the loop
    was closed structurally even while the flat ruler disagreed."""
    assert equip_value(_MUSHMUSH_JACKET) > equip_value(_ADVENTURER_VEST)
    assert may_displace(_ADVENTURER_VEST, _MUSHMUSH_JACKET) is False

    gd = _gd(_MUSHMUSH_JACKET, _ADVENTURER_VEST)
    state = _state(21, {"mushmush_jacket": 1}, {_BODY: "adventurer_vest"},
                   _FOREST_WHIP_ATTACK)
    mushmush_atk = {"fire": 16, "earth": 0, "water": 16, "air": 0}
    mushmush_res = {"fire": 20, "earth": 20, "water": 0, "air": -30}
    picked = pick_loadout(Combat(mushmush_atk, mushmush_res, _FOREST_WHIP_ATTACK),
                          state, gd)
    assert picked[_BODY] == "mushmush_jacket", picked


def test_a_purely_defensive_item_still_wins_where_defence_matters() -> None:
    """`piggy_armor` carries 150 hp and 15 points of resistance, all of it in
    fire and earth. Against a 400-FIRE hitter it must beat the pure-offence
    jacket on the monster-relative ruler — a damage-only valuation would invert
    that, and `pursuit_value` (the acquisition economics) agrees.

    VERDICT CHANGE, and an honest one: both MONSTER-BLIND rulers now put the
    jacket AHEAD (`equip_value` 317600 to 280200), because Rank IS `armor_score`
    and the adversary it scores against is the catalog MEDIAN — which attacks in
    every element equally. A monster-blind ruler cannot know you will meet
    rosenblood, so it dilutes piggy's fire-and-earth-only resistance across four
    elements while the jacket's 10% GLOBAL damage applies whatever shows up.
    That is the same number `armor_score` itself returns for the median monster,
    so the authorities are not disagreeing — they are ONE function asked about
    different adversaries, and `may_displace` (below) is what keeps them from
    fighting over the slot.

    `pursuit_value` used to side with piggy here, on a flat sum that added
    piggy's 15 resistance points and 30 wisdom to its 150 hp 1:1. It now follows
    the ruler, which is the whole point of the economics layer reading the
    ruler's own combat term: the acquisition path can no longer hold an opinion
    the picker's own formula does not."""
    piggy = armor_score(_PIGGY_ARMOR, _ROSENBLOOD_ATK, _ROSENBLOOD_RES,
                        _FOREST_WHIP_ATTACK)
    jacket = armor_score(_MUSHMUSH_JACKET, _ROSENBLOOD_ATK, _ROSENBLOOD_RES,
                         _FOREST_WHIP_ATTACK)
    assert piggy > jacket
    assert equip_value(_MUSHMUSH_JACKET) > equip_value(_PIGGY_ARMOR)
    assert not may_displace(_PIGGY_ARMOR, _MUSHMUSH_JACKET)
    assert not may_displace(_MUSHMUSH_JACKET, _PIGGY_ARMOR)


# --- may_displace, branch by branch -----------------------------------------

def test_may_displace_accepts_a_stat_wise_dominating_candidate() -> None:
    better = ItemStats(code="b", level=1, type_="amulet", hp_bonus=40,
                       dmg_elements={"fire": 5, "earth": 5})
    assert may_displace(better, _FIRE_AND_EARTH_AMULET) is True


def test_may_displace_allows_an_exact_tie() -> None:
    """`pick_loadout` keeps the incumbent on a tie, so a tying candidate is
    never swapped back either — equality is a fixed point."""
    assert may_displace(_FIRE_AND_EARTH_AMULET, _FIRE_AND_EARTH_AMULET) is True


def test_may_displace_rejects_less_flat_utility() -> None:
    assert may_displace(_FIRE_AND_EARTH_AMULET, _LIFE_AMULET) is False


def test_may_displace_rejects_less_crit() -> None:
    less_crit = replace(_MUSHMUSH_JACKET, code="lc", critical_strike=0,
                        hp_bonus=600)
    assert may_displace(less_crit, _MUSHMUSH_JACKET) is False


def test_may_displace_rejects_a_tool_over_a_non_tool() -> None:
    """`weapon_score`'s `nonToolBonus` breaks a raw tie for the non-tool, so a
    tool can never be proved to hold the slot."""
    tool = ItemStats(code="steel_pickaxe", level=20, type_="weapon",
                     subtype="tool", attack={"earth": 5})
    weapon = ItemStats(code="steel_battleaxe", level=20, type_="weapon",
                       attack={"earth": 5})
    assert may_displace(tool, weapon) is False
    assert may_displace(weapon, tool) is True


def test_may_displace_rejects_less_attack_in_any_element() -> None:
    a = ItemStats(code="a", level=1, type_="weapon", attack={"earth": 40})
    b = ItemStats(code="b", level=1, type_="weapon", attack={"earth": 30, "air": 40})
    assert may_displace(b, a) is False


def test_may_displace_rejects_less_resistance_in_any_element() -> None:
    a = ItemStats(code="a", level=1, type_="body_armor", resistance={"fire": 10})
    b = ItemStats(code="b", level=1, type_="body_armor",
                  resistance={"fire": 5, "air": 40})
    assert may_displace(b, a) is False


def test_may_displace_rejects_less_damage_in_any_element() -> None:
    """The combined `dmg + dmg_elements[e]` is what `armor_score` reads, so a
    global `dmg` may compensate a missing per-element bonus — but only when it
    covers EVERY element the incumbent specializes in."""
    a = ItemStats(code="a", level=1, type_="amulet",
                  dmg_elements={"fire": 5, "earth": 5})
    short = ItemStats(code="b", level=1, type_="amulet", dmg=4)
    assert may_displace(short, a) is False
    assert may_displace(replace(short, code="c", dmg=5), a) is True


def test_the_committed_upgrade_leg_of_the_loop_also_closes() -> None:
    """The THIRD producer of a displacing equip, and the one the 2026-08-04 fix
    missed: a COMMITTED `UpgradeEquipmentGoal`.

    Live 2026-09-09, character HAL (level 20). He wore `adventurer_pants`,
    carried one `hard_leather_pants`, and ran this pair 203 times over 13.5
    hours — 0 character XP for the whole run:

        Equip(hard_leather_pants->leg_armor_slot)  goal=UpgradeEquipment(...)
        (LevelSkill expansion -> OptimizeLoadout)  unequip, adventurer_pants back

    `_find_inventory_upgrade` defers to `pick_loadout` through `may_displace`,
    but `_committed_upgrade_if_ready` — the path a target committed by
    `obtain_item_routing._equippable_goal` / `map_guard(GEAR_REVIEW)` takes —
    did not consult it at all, so a committed target walked straight past the
    one authority on slot occupancy.

    Neither piece dominates (checked below), so this slot belongs to the picker.
    """
    gd = _gd(_HARD_LEATHER_PANTS, _ADVENTURER_PANTS)
    leg = "leg_armor_slot"
    state = _state(20, {"hard_leather_pants": 1},
                   {leg: "adventurer_pants"}, _BATTLESTAFF_ATTACK)
    goal = UpgradeEquipmentGoal(
        initial_equipment=state.equipment,
        committed_target=("hard_leather_pants", leg),
    )

    # Vacuity guards: the loop is real in BOTH directions, so the assertion
    # below can only come from the occupancy gate.
    assert may_displace(_HARD_LEATHER_PANTS, _ADVENTURER_PANTS) is False
    assert may_displace(_ADVENTURER_PANTS, _HARD_LEATHER_PANTS) is False
    assert pick_loadout(Combat(_SHEEP_ATK, _SHEEP_RES, _BATTLESTAFF_ATTACK),
                        _state(20, {"adventurer_pants": 1},
                               {leg: "hard_leather_pants"},
                               _BATTLESTAFF_ATTACK), gd)[leg] == "adventurer_pants", (
        "fixture drift: the picker no longer reverses this equip, so there is "
        "no loop left for the gate to close"
    )

    # The committed goal must not name an equip the picker will undo.
    assert goal.desired_state(state, gd) == {}

    for _ in range(4):
        desired = goal.desired_state(state, gd)
        equipment = desired.get("equipment")
        if equipment:
            state = replace(state, equipment={**state.equipment, **equipment})
        picked = pick_loadout(
            Combat(_SHEEP_ATK, _SHEEP_RES, state.attack), state, gd)
        state = replace(state, equipment=dict(picked))
        assert state.equipment[leg] == "adventurer_pants", state.equipment
