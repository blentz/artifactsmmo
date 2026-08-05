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

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import RULER_SCALE, armor_score
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.progression_tree import _structural_candidates
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
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


class _Objective:
    """The two `CharacterObjective` members `_structural_candidates` reads.

    A stub rather than the real objective because the tree's gear branch is
    exactly these two calls, and building a full objective would drag the whole
    attainability layer into a test about who owns a slot.
    """

    def __init__(self, targets: dict[str, str]) -> None:
        self._targets = targets

    def near_term_gear(self, state: WorldState) -> dict[str, str]:
        return dict(self._targets)

    def _item_value(self, code: str | None) -> int:
        if not code:
            return 0
        stats = _ALL.get(code)
        return pursuit_value(stats) if stats is not None else 0


_ALL = {it.code: it for it in
        (_LIFE_AMULET, _FIRE_AND_EARTH_AMULET, _MUSHMUSH_JACKET,
         _ADVENTURER_VEST, _PIGGY_ARMOR)}


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
    # Neither amulet carries an efficiency stat, so pursuit is exactly 1000x.
    assert pursuit_value(_LIFE_AMULET) == 1000 * RULER_SCALE * 6000
    assert pursuit_value(_FIRE_AND_EARTH_AMULET) == 1000 * RULER_SCALE * 70000
    assert pursuit_value(_FIRE_AND_EARTH_AMULET) > pursuit_value(_LIFE_AMULET)

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

    objective = _Objective({_AMULET: "life_amulet"})
    assert _structural_candidates(state, gd, objective) == []

    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment)
    assert goal.find_upgrade_target(state, gd) is None


# --- The loop, closed -------------------------------------------------------

def _alternate(state: WorldState, gd: GameData, objective: _Objective,
               monster_atk: dict[str, int], monster_res: dict[str, int],
               slot: str, legs: int = 8) -> list[str | None]:
    """Run the observed cycle: the acquisition authority equips its target,
    then the combat picker runs, repeatedly. Returns the slot's occupant after
    every leg — a LOOP shows as alternating entries, closure as a constant
    tail."""
    seen: list[str | None] = [state.equipment[slot]]
    for leg in range(legs):
        if leg % 2 == 0:
            candidates = _structural_candidates(state, gd, objective)
            for cand in candidates:
                state = replace(
                    state,
                    equipment={**state.equipment, cand.slot: cand.code})
        else:
            picked = pick_loadout(
                Combat(monster_atk, monster_res, state.attack), state, gd)
            state = replace(state, equipment=dict(picked))
        seen.append(state.equipment[slot])
    return seen


def test_amulet_slot_reaches_a_fixed_point_instead_of_alternating() -> None:
    """THE regression test for the observed loop. Pre-fix this sequence reads
    ``[f&e, life, f&e, life, ...]`` — the tree's gain of 10000 re-equipping
    `life_amulet` and `OptimizeLoadout(wolf)` reversing it. It must be constant
    now, and constant at the amulet the fight actually wants."""
    gd = _gd(_LIFE_AMULET, _FIRE_AND_EARTH_AMULET)
    state = _state(21, {"life_amulet": 1},
                   {_AMULET: "fire_and_earth_amulet"}, _BATTLEAXE_ATTACK)
    objective = _Objective({_AMULET: "life_amulet"})

    seen = _alternate(state, gd, objective, _WOLF_ATK, _WOLF_RES, _AMULET)
    assert set(seen) == {"fire_and_earth_amulet"}, seen


def test_the_loop_closes_from_the_other_starting_occupant_too() -> None:
    """Closure must not depend on where the cycle happens to start. Beginning
    with `life_amulet` worn, the picker moves the slot ONCE (to the amulet the
    monster makes better) and it never moves again — one swap that buys damage,
    not an unbounded alternation."""
    gd = _gd(_LIFE_AMULET, _FIRE_AND_EARTH_AMULET)
    state = _state(21, {"fire_and_earth_amulet": 1},
                   {_AMULET: "life_amulet"}, _BATTLEAXE_ATTACK)
    objective = _Objective({_AMULET: "life_amulet"})

    seen = _alternate(state, gd, objective, _WOLF_ATK, _WOLF_RES, _AMULET)
    assert seen[0] == "life_amulet", seen
    assert set(seen[2:]) == {"fire_and_earth_amulet"}, seen


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


def test_an_unowned_target_is_still_pursued() -> None:
    """The gate is scoped to items the character ALREADY HOLDS, where the only
    remaining work is the contested equip. Acquiring gear he does not own is
    real, terminating work and must stay proposed — otherwise closing the loop
    would close gear progression with it."""
    gd = _gd(_ADVENTURER_VEST, _MUSHMUSH_JACKET)
    state = _state(21, {}, {_BODY: "adventurer_vest"}, _FOREST_WHIP_ATTACK)
    objective = _Objective({_BODY: "mushmush_jacket"})
    candidates = _structural_candidates(state, gd, objective)
    assert [(c.slot, c.code) for c in candidates] == [(_BODY, "mushmush_jacket")]


def test_a_dominating_owned_item_is_still_proposed() -> None:
    """The gate admits what it can prove the picker agrees with. A strictly
    better copy of the same shape (every stat >=) is a fixed point for every
    monster, so the tree may still pre-empt the picker and equip it."""
    better = ItemStats(code="better_amulet", level=10, type_="amulet",
                       hp_bonus=40, dmg_elements={"fire": 5, "earth": 5})
    _ALL[better.code] = better
    try:
        gd = _gd(_FIRE_AND_EARTH_AMULET, better)
        state = _state(21, {"better_amulet": 1},
                       {_AMULET: "fire_and_earth_amulet"}, _BATTLEAXE_ATTACK)
        objective = _Objective({_AMULET: "better_amulet"})
        candidates = _structural_candidates(state, gd, objective)
        assert [(c.slot, c.code) for c in candidates] == [(_AMULET, "better_amulet")]

        seen = _alternate(state, gd, objective, _WOLF_ATK, _WOLF_RES, _AMULET)
        assert set(seen[1:]) == {"better_amulet"}, seen
    finally:
        del _ALL[better.code]


def test_an_unknown_incumbent_is_not_gated() -> None:
    """`game_data` with no stats for the worn code: `pick_loadout` displaces an
    unknown incumbent unconditionally, so there is no disagreement to defer to
    and the candidate stays. Mirrors the tree's own missing-stats handling
    rather than inventing a third policy."""
    gd = _gd(_LIFE_AMULET)          # nothing for the worn code
    state = _state(21, {"life_amulet": 1},
                   {_AMULET: "unknown_amulet"}, _BATTLEAXE_ATTACK)
    objective = _Objective({_AMULET: "life_amulet"})
    candidates = _structural_candidates(state, gd, objective)
    assert [(c.slot, c.code) for c in candidates] == [(_AMULET, "life_amulet")]


def test_a_banked_copy_counts_as_owned() -> None:
    """Ownership for this gate is bag OR bank: a banked copy is one Withdraw
    from the same contested equip, so it must be gated the same way."""
    gd = _gd(_MUSHMUSH_JACKET, _PIGGY_ARMOR)
    state = _state(25, {}, {_BODY: "mushmush_jacket"}, _FOREST_WHIP_ATTACK)
    state = replace(state, bank_items={"piggy_armor": 1})
    objective = _Objective({_BODY: "piggy_armor"})
    assert _structural_candidates(state, gd, objective) == []


def test_the_tree_leg_of_the_loop_closes_on_a_positive_gain_swap() -> None:
    """The deferral must hold where the monster-blind ruler genuinely PREFERS
    the candidate, not only where the two rulers happen to tie.

    Owned `mushmush_jacket` outranks the worn `piggy_armor` by 41_399_980 on
    `pursuit_value` — a huge positive gain the tree would chase every cycle —
    but it trades away 150 hp and all the fire resistance, so against a
    400-FIRE hitter `pick_loadout` puts piggy straight back. Without the
    deferral this alternates forever; with it, the tree proposes nothing and
    the slot never moves. (Against a monster where the jacket IS better, the
    picker equips it — see
    `test_deferring_loses_nothing_the_picker_equips_it_when_it_helps`.)

    The two items swapped ROLES here when Rank was unified onto `armor_score`
    and `pursuit_value` followed it: the monster-blind ruler now prefers the
    jacket's 10% GLOBAL damage over piggy's fire-and-earth-only resistance,
    because the catalog-median adversary attacks in every element equally. The
    LOOP being closed is identical — a monster-blind preference the
    monster-relative picker reverses — only its direction changed."""
    gd = _gd(_MUSHMUSH_JACKET, _PIGGY_ARMOR)
    state = _state(25, {"mushmush_jacket": 1}, {_BODY: "piggy_armor"},
                   _FOREST_WHIP_ATTACK)
    objective = _Objective({_BODY: "mushmush_jacket"})

    assert pursuit_value(_MUSHMUSH_JACKET) > pursuit_value(_PIGGY_ARMOR)
    assert _structural_candidates(state, gd, objective) == []

    seen = _alternate(state, gd, objective, _ROSENBLOOD_ATK, _ROSENBLOOD_RES, _BODY)
    assert set(seen) == {"piggy_armor"}, seen


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
    assert pursuit_value(_MUSHMUSH_JACKET) > pursuit_value(_ADVENTURER_VEST)
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
    assert pursuit_value(_MUSHMUSH_JACKET) > pursuit_value(_PIGGY_ARMOR)
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
