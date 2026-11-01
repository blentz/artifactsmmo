"""The HELD TASK dimension of the scenario set.

`ScenarioCharacter.task` has existed since the harness was built and, until this
file, no scenario set it: 30 of 30 carried `task_code=None`, so
`combat_deficit.blocked_task_monster` returned `None` in every offline test and
everything downstream of it — `has_combat_deficit`, the task horizon, the task
root, `RegearEdge`, the `GEAR_REVIEW` guard (both deleted in Phase 4-3b) — was
reachable only through hand-built states. Live, 21.1 % of cycles hold a task, and every one of them is a
`monsters` task.

Three scenarios now hold one, chosen to give the dimension three DISTINCT
values rather than three copies of one:

* `l12_gearcrafting_gap` — a task it can win (deficit False),
* `l13_drop_recipe_grind` — a task it cannot win, whose `L*` closes the gap,
* `l10_copper_adequate` — a task it cannot win, with NO gear that closes it.

Those three populate the dimension. They do not CONTROL it: they are three
different characters at three levels with three loadouts, so nothing measured
across them can be attributed to the task rather than to everything else that
also differs. Coverage-matrix cells 1-3 (design 2026-08-24 §5.3) add the
controlled form — ONE character in three task states, every other field
identical:

* `l32_held_task_workable` — wolf, winnable,
* `l32_held_task_closable` — ogre, unwinnable; a catalogue chain closed it, but
  no ACHIEVABLE gear does: `L*(ogre)` is held and loses, one level closes it,
* `l32_held_task_open` — lich, unwinnable, nothing closes it.

`test_the_held_task_triple_varies_only_the_task` is what keeps them a control;
`test_the_task_triple_moves_the_gear_review_target` is what shows the flip
reaches a decision rather than stopping at a predicate.

Two properties this file is built to keep, both of them measured rather than
assumed:

1. **Not vacuous on the combat-stats axis.** At zero total attack every monster
   is unwinnable, so the deficit arm fires for reasons that have nothing to do
   with the task — measured, a `cow` task gives deficit in 30/30 scenarios with
   stats off and 9/30 with them on. All three scenarios therefore carry derived,
   non-zero attack, and `test_task_scenarios_are_not_vacuous_on_combat_stats`
   asserts it. A future edit that drops the flag turns these cells into noise,
   and that test is what says so.
2. **Three values, not one.** `test_the_three_task_values_are_distinct` fails if
   two of them ever collapse onto the same `(deficit, gear verdict)` pair — which
   is how a dimension quietly stops discriminating.
"""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_deficit import has_combat_deficit
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.decisions.root import _task_root, resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective_for, task_rate
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.inventory_keep import keep_in_bag
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    HORIZON_OUT_OF_REACH,
    TaskHorizon,
    resolve_task_horizon,
)
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.progression.meta_goal import ObtainItem, ReachTaskOutcome
from artifactsmmo_cli.ai.progression.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import shared_world

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

WORKABLE = "l12_gearcrafting_gap"
UNWINNABLE_CLOSABLE = "l13_drop_recipe_grind"
UNWINNABLE_OPEN = "l10_copper_adequate"

TRIPLE_WORKABLE = "l32_held_task_workable"
TRIPLE_CLOSABLE = "l32_held_task_closable"
TRIPLE_OPEN = "l32_held_task_open"
TRIPLE = (TRIPLE_WORKABLE, TRIPLE_CLOSABLE, TRIPLE_OPEN)

ITEMS_CELL = "l32_items_task"
"""The one ITEMS-type task. Everything else in the set is `monsters`,
which mirrors production (0 items tasks in 15,240 live task-cycles)."""

TASK_SCENARIOS = (WORKABLE, UNWINNABLE_CLOSABLE, UNWINNABLE_OPEN,
                  ITEMS_CELL, *TRIPLE)


@pytest.fixture(scope="module")
def gd() -> GameData:
    return shared_world(BUNDLE)


def _obj(game_data: GameData) -> CharacterObjective:
    return CharacterObjective.from_game_data(game_data)


def _state(name: str, game_data: GameData):
    return scenario_state(SCENARIOS[name], game_data)


def _horizon(state, game_data: GameData) -> TaskHorizon | None:  # type: ignore[no-untyped-def]
    """The task horizon on the offline context, store-less."""
    return resolve_task_horizon(state, game_data, TIMED_NO_PROFILE_CONTEXT, None)


def _gear(state, game_data: GameData) -> tuple[str, str] | None:  # type: ignore[no-untyped-def]
    """`(code, slot)` of the first missing piece of `L*` of the task monster on
    the horizon's gear verdict (what the task root asks), or None."""
    horizon = _horizon(state, game_data)
    if horizon is None or horizon.verdict != HORIZON_GEAR:
        return None
    first = gear_objective_for(horizon.monster, state, game_data, TIMED_NO_PROFILE_CONTEXT,
                               None, task_rate).missing[0]
    return first.code, first.slot


def test_the_held_task_dimension_has_a_populated_side(gd: GameData) -> None:
    """The dimension is populated at all — and the fields are wired end to end."""
    holders = [n for n in SCENARIOS if SCENARIOS[n].task is not None]
    # `l22_rest_for_combat` holds a monsters task too (2026-10-18): it is the
    # REST_FOR_COMBAT cell, whose grind target is the task's monster since the
    # gear objective names no XP fight while `L*` is missing. It is not a cell
    # of this dimension.
    assert sorted(holders) == sorted((*TASK_SCENARIOS, "l22_rest_for_combat"))
    for name in TASK_SCENARIOS:
        code, kind, progress, total = SCENARIOS[name].task
        state = _state(name, gd)
        assert state.task_code == code
        assert state.task_type == kind
        assert (state.task_progress, state.task_total) == (progress, total)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.IN_PROGRESS
        # The referent must be REAL on both arms — a task naming something the
        # catalogue does not have would make every consumer downstream vacuous.
        # This loop asserted `kind == "monsters"` until the items cell landed;
        # that was true of the whole set and is exactly what the cell widens.
        if kind == "monsters":
            assert gd.monster_level(code) is not None, "the task monster must be real"
        else:
            assert kind == "items"
            assert gd.item_stats(code) is not None, "the task item must be real"


def test_task_scenarios_are_not_vacuous_on_combat_stats(gd: GameData) -> None:
    """Zero attack would make the deficit fire for a reason that is not the task.

    Measured: with `derive_combat_stats` off, a cow task gives
    `has_combat_deficit` in 30/30 scenarios; with it on, 9/30. A task cell on the
    zero-attack side therefore measures the harness, not the bot."""
    for name in TASK_SCENARIOS:
        assert SCENARIOS[name].derive_combat_stats
        state = _state(name, gd)
        assert any(state.attack.values()), f"{name} has no attack — cell is vacuous"


def test_the_three_task_values_are_distinct(gd: GameData) -> None:
    """Three cells, three answers. Collapse two and the dimension stops splitting."""
    seen = {
        name: (has_combat_deficit(_state(name, gd), gd),
               _gear(_state(name, gd), gd) is not None)
        for name in TASK_SCENARIOS
    }
    assert len(set(seen.values())) == 3, seen


def test_workable_task_reaches_the_negative_deficit_arm(gd: GameData) -> None:
    """`blocked_task_monster` names a monster AND `predict_win` says yes.

    The negative arm is only reachable with a task in hand: no task at all
    short-circuits before `predict_win` is ever called, which is why 30/30
    task-free scenarios proved nothing about it."""
    state = _state(WORKABLE, gd)
    assert state.task_code == "cow"
    assert has_combat_deficit(state, gd) is False
    assert _horizon(state, gd) is None


def test_unwinnable_task_names_the_gear_that_closes_it(gd: GameData) -> None:
    """The "I lost, so get gear" link, with an offline witness at last.

    Before this the ONLY route from a lost fight to a gear upgrade was a
    countdown timer, and the walk that replaced it had no scenario exercising
    its positive arm. The gear is the first missing piece of `L*(cow)` (plan C
    Task 2); the deleted deficit walk named a weapon here."""
    state = _state(UNWINNABLE_CLOSABLE, gd)
    assert has_combat_deficit(state, gd) is True
    assert _gear(state, gd) == ("iron_legs_armor", "leg_armor_slot")


def test_unwinnable_task_with_no_closing_chain_names_nothing(gd: GameData) -> None:
    """The FALL-THROUGH arm: a deficit no gear in the catalogue closes.

    Paired with the test above on purpose — `None` here is only meaningful next
    to a case where the same call returns a target, otherwise it is
    indistinguishable from the function never running."""
    state = _state(UNWINNABLE_OPEN, gd)
    assert has_combat_deficit(state, gd) is True
    horizon = _horizon(state, gd)
    assert horizon is not None
    assert horizon.verdict == HORIZON_OUT_OF_REACH


# --- coverage-matrix cells 1-3: the same character, three task states --------

def test_the_held_task_triple_varies_only_the_task() -> None:
    """The control property, asserted rather than trusted.

    Cells 1-3 exist to attribute an effect to the HELD TASK. That attribution
    is only valid while `task` is the sole difference between them, so this
    compares every other field of the three `ScenarioCharacter`s and fails on
    any drift — including a well-meaning edit that tunes one cell's gold or
    bank and quietly turns the triple into three unrelated characters."""
    def _rest(name: str) -> dict[str, object]:
        return {k: v for k, v in dataclasses.asdict(SCENARIOS[name]).items()
                if k not in ("name", "task", "description")}

    reference = _rest(TRIPLE_WORKABLE)
    for name in TRIPLE[1:]:
        assert _rest(name) == reference, f"{name} differs from the triple by more than its task"
    assert len({SCENARIOS[n].task for n in TRIPLE}) == 3


def test_the_task_triple_splits_the_horizon_three_ways(gd: GameData) -> None:
    """One character, three tasks, three answers at the branch D2 names.

    `blocked_task_monster` is reached in all three (a task is held); what
    differs is only which horizon verdict the monster lands on.

    RE-DERIVED plan C Task 2: the gear verdict is `L*` of the task monster, the
    ACHIEVABLE loadout, its `R` read in task progress a second (ruling
    C2-grey: the ogre pays this character no XP). The closable cell's
    `L*(ogre)` secures the fight with its first missing piece the
    `lifesteal_rune` (the deleted deficit walk named the unobtainable
    `perfect_bow`), so the three cells still split three ways."""
    workable = _state(TRIPLE_WORKABLE, gd)
    closable = _state(TRIPLE_CLOSABLE, gd)
    open_ = _state(TRIPLE_OPEN, gd)

    assert has_combat_deficit(workable, gd) is False
    assert _horizon(workable, gd) is None

    assert has_combat_deficit(closable, gd) is True
    assert _gear(closable, gd) == ("lifesteal_rune", "rune_slot")

    assert has_combat_deficit(open_, gd) is True
    horizon = _horizon(open_, gd)
    assert horizon is not None
    assert horizon.verdict == HORIZON_OUT_OF_REACH
    # ...and the lich really is IN BAND, so the fall-through is a gear fact and
    # not the artefact of naming a monster twenty levels out of reach.
    assert gd.monster_level("lich") <= SCENARIOS[TRIPLE_OPEN].level


def test_the_triple_starves_the_winnable_cascade(gd: GameData) -> None:
    """The triple's cascade finds nothing to fight: the measured fact behind
    the deleted fight-arm test's `winnable_alternative=False` rows.

    REVERSED 2026-10-03. This test was `..._cannot_starve_...` and asserted a
    non-None farm target for all three cells: `_path_aligned_monster` returned
    a winnable low-level slime. At L32 every slime pays 0 XP, and `FightAction`
    refuses an XP fight that pays nothing, so that target was one the executor
    never fights (live, the same shape failed `GrindCharacterXP` 561 of 561
    times in three hours). `band_combat_target` now enforces the executor's
    XP floor, so the cascade returns None for all three cells: an honest gear
    wall, and the input the standing arm reads."""
    for name in TRIPLE:
        state = _state(name, gd)
        assert all(gd.xp_per_kill(slime, state.level) == 0
                   for slime in ("green_slime", "blue_slime", "red_slime", "yellow_slime"))
        player = GamePlayer(character=name, history=None)
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        player.seed_offline(state, gd)
        player.plan_from_state()
        assert player._last_ctx is not None
        assert player._last_ctx.combat_monster is None


def test_the_task_triple_moves_the_task_root(gd: GameData) -> None:
    """The triple's verdicts reach a DECISION: the task root (`_task_root`),
    offered in the alternatives.

    The root walk enters at `WhichPieceIsNext` (global gear objective Task 5),
    so a held task does not move the ROOT: all three cells head the walk with
    their own `L*`'s first piece. Spec §2.8: `L*`'s `fire_and_earth_amulet`
    adds nothing to `R` on `rat` over the `life_amulet` the triple owns, so it
    is not missing, and the walk heads with the rune.

    RE-DERIVED plan C Task 2: the task root of an unwinnable task is the first
    missing piece of `L*` of its monster, and only on the gear verdict. The
    closable cell's task asks `L*(ogre)`'s `lifesteal_rune`, which is also the
    head of the cell's own `L*`, so it adds no alternative (the deleted deficit
    walk asked for the priced `earth_boost_potion`); the open cell asks for
    nothing (no gear closes it, no coin cancels it); the workable cell's task
    is worked. The gear arm's
    witness is `test_an_unwinnable_task_monster_roots_its_first_missing_piece`."""
    resolutions = {}
    for name in TRIPLE:
        state = _state(name, gd)
        resolutions[name] = resolve_root(
            state, gd, _obj(gd), attach_gear_objective(state, gd, TIMED_NO_PROFILE_CONTEXT, None),
            None)
    first_piece = ObtainItem(code="lifesteal_rune", quantity=1, slot="rune_slot")
    assert {r.root for r in resolutions.values()} == {first_piece}
    task = ReachTaskOutcome(task_code="wolf")
    assert task in resolutions[TRIPLE_WORKABLE].alternatives
    # The closable and open cells offer exactly the workable cell's alternatives
    # less its task: the open cell's task asks nothing, the closable cell's
    # asks the piece its own walk already heads with.
    own = tuple(alt for alt in resolutions[TRIPLE_WORKABLE].alternatives if alt != task)
    assert resolutions[TRIPLE_CLOSABLE].alternatives == own
    assert resolutions[TRIPLE_OPEN].alternatives == own
    closable = _state(TRIPLE_CLOSABLE, gd)
    assert _task_root(closable, gd, attach_gear_objective(closable, gd, TIMED_NO_PROFILE_CONTEXT,
                                                          None), None) == first_piece


def test_an_unwinnable_task_monster_roots_its_first_missing_piece(gd: GameData) -> None:
    """Plan C Review Focus 1: a held monsters task whose monster is not
    winnable roots the first missing piece of `L*` of THAT monster, in its
    slot — never `Wait`, never the deleted deficit walk (which named a weapon
    for this cow).

    `l13_drop_recipe_grind` holds a cow task it loses. The cycle's own gear
    objective `(L*, m*)` is for another monster and heads with another piece,
    so the task root is read from `L*(cow)` and not from the cycle's `L*`."""
    state = _state(UNWINNABLE_CLOSABLE, gd)
    assert state.task_code == "cow"
    assert not is_winnable(dataclasses.replace(state, hp=state.max_hp), gd, "cow", None)
    ctx = attach_gear_objective(state, gd, TIMED_NO_PROFILE_CONTEXT, None)
    root = ObtainItem(code="iron_legs_armor", quantity=1, slot="leg_armor_slot")
    assert _task_root(state, gd, ctx, None) == root
    first = gear_objective_for("cow", state, gd, ctx, None, task_rate).missing[0]
    assert (first.code, first.slot) == ("iron_legs_armor", "leg_armor_slot")
    assert ctx.gear_objective is not None
    assert ctx.gear_objective.monster != "cow"
    assert ctx.gear_objective.missing[0].code != "iron_legs_armor"
    resolution = resolve_root(state, gd, _obj(gd), ctx, None)
    assert root in (resolution.root, *resolution.alternatives)


# --- the ONE-LEVEL PLANNING HORIZON over the same three cells ---------------
#
# USER (2026-08-25): "cancel tasks that we can't meet through gear upgrade, or
# (level-up by exactly 1 level and gear upgrade). anything beyond a 1-level
# horizon is too far out to be a reasonable near-term planning target."
#
# `test_the_task_triple_moves_the_gear_review_target` above records what the guard
# DOES with each cell, and the flat fact that cells 1 and 3 land on the same
# monster-blind goal. What it could not say is that landing there is WRONG for
# cell 3 and right for cell 1: the workable cell has no fight to lose, the open
# cell has one it will never win with gear. The three tests below are that
# distinction, taken at the places the fact is consumed (the GEAR_REVIEW
# guard's LEVEL_UP arm was one until Phase 4-3b deleted it: it never fired).


def test_the_open_task_is_offered_for_its_cancel_with_a_coin(gd: GameData) -> None:
    """The whole walk, from a held task to the cancel step.

    Measured on this exact cell at HEAD~ of the horizon change (a `tasks_coin`
    added to the pocket so S-052 is satisfied): the bot planned
    `GatherMaterials(flying_wing, {flying_wing:6})` with a first action of
    `Fight(flying_snake)` — it kept the dead lich task and went and did something
    else, forever, because `task_feasibility`'s level proxy reported a level-30
    monster feasible for a level-32 character.

    Until Phase 5-2c-iii-c-2 #5 the TASK_CANCEL collect rung fired here above
    every root, so `plan_from_state` selected `TaskCancel` outright. The rung is
    retired: an out-of-reach task is worthless (`task_worth`), so the walk OFFERS
    the task objective and its step is the cancel — taken on the task's turn,
    not ahead of the trunk."""
    state = _state(TRIPLE_OPEN, gd)
    state = dataclasses.replace(
        state, inventory={**state.inventory, TASKS_COIN_CODE: 1})
    assert state.task_code is not None
    task = ReachTaskOutcome(state.task_code)
    res = resolve_root(state, gd, _obj(gd), TIMED_NO_PROFILE_CONTEXT, None)
    assert task in [res.root, *res.alternatives]
    goal = objective_step_goal(task, state, gd, TIMED_NO_PROFILE_CONTEXT, history=None)
    assert repr(goal) == "TaskCancel"
    assert goal.value(state, gd, None) > 0.0


# --- the STANDING ARM, end to end -------------------------------------------
#
# `RegearEdge` has a 981-cycle / 31.6-hour character-XP freeze in its history, and
# it was caused by exactly the class of edit `63533b82` made to it: the standing
# arm armed on a STANDING FACT ("this fight is lost"), so `GEAR_REVIEW` — a GUARD,
# which preempts the objective step outright — held the character for 981
# consecutive cycles with no level-up and no `error:fight_lost` to release it.
# The rule that came out of that is "a standing condition must not drive a sticky
# latch", and the arm is not sticky. But narrowing WHEN it arms is a change to
# the same machinery, and it shipped with component-level evidence only.
#
# It does not have to. The arm needs three things at once: a craftable upgrade,
# a held monsters task whose fight is lost, and NO winnable alternative. Eleven
# of the forty-two scenarios starved the cascade when this was written
# (2026-08-25), none of them holding a task; since the cascade's XP floor
# (2026-10-03) the held-task triple starves it too (see
# `test_the_triple_starves_the_winnable_cascade`). Giving a starved cell a task
# closes the last conjunct and the arm becomes reachable from `plan_from_state`
# — the same entry point production uses.

STARVED = "l48_capstone_approach"
STARVED_GEAR = "dryad"
STARVED_OUT_OF_REACH = "red_dragon"
# RE-DERIVED 2026-10-18 (ruling R): the cell's hand stats lacked its loadout's.
# On the loadout's own totals the old gear row `corrupted_ogre` (L20) is
# winnable and holds no deficit, and the old out-of-reach row `baby_red_dragon`
# is gear-closable (hell_staff); both rows were stat artefacts. The rows are now
# `dryad` (L40, gear: `L*(dryad)`'s first missing piece is goblin_guard_shield,
# plan C Task 2; the deleted deficit walk named slime_shield) and `red_dragon`
# (L51, out of reach, and no spawn tile the fight pool reaches, so no `L*`),
# both lost on the derived sheet.
# There was a level-up row, dryad. Since the level-up arm reads `L*` (plan C
# Task 2) this cell's level-up monsters are echoless_bat and goblin_guard; the
# arm's witnesses are in `test_task_horizon` (ogre, pig, skeleton).


def _starved_state(monster: str, game_data: GameData):
    """`l48_capstone_approach` holding a monsters task, and nothing else changed.

    A CONTROL, in the same sense the l32 triple is one: one character, one
    loadout, one level, three tasks. Everything that differs between the three
    rows below is the monster code."""
    return dataclasses.replace(
        _state(STARVED, game_data), task_code=monster, task_type="monsters",
        task_progress=0, task_total=10,
        task_lifecycle_phase=TaskLifecyclePhase.IN_PROGRESS)


def _starved_run(monster: str | None, game_data: GameData):
    state = (_state(STARVED, game_data) if monster is None
             else _starved_state(monster, game_data))
    player = GamePlayer(character=STARVED, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, game_data)
    report = player.plan_from_state()
    assert player._last_ctx is not None
    return state, player, report


def test_a_starved_cascade_witnesses_the_standing_arm_end_to_end(gd: GameData) -> None:
    """The standing arm, taken and NOT taken, through `plan_from_state`. It was
    the latch, then the walk's `IsAFightBlockingMe` (wave 4); since plan C Task
    2 it is the task root's gear arm (`_task_root`).

    Both rows share `has_combat_deficit is True` — the bare fact the arm used
    to test — so before `63533b82` both armed the latch and both handed the
    character to the guard. The horizon splits them: only the row gear closes
    asks for gear.

    The EDGE arm is provably not what fires here: `plan_from_state` passes
    `self._last_outcome` (None on a seeded player) and `prev_level == state.level`,
    so `self._active` cannot be set. What is measured is `_blocked` alone."""
    for monster in (STARVED_GEAR, STARVED_OUT_OF_REACH):
        state, player, _ = _starved_run(monster, gd)
        # The three conjuncts of the standing arm, measured rather than passed in.
        assert player._last_ctx.combat_monster is None
        # ...and the fact the OLD arm read, identical across all three rows.
        assert has_combat_deficit(state, gd) is True

    horizons = {m: _horizon(_starved_state(m, gd), gd) for m in (STARVED_GEAR, STARVED_OUT_OF_REACH)}
    assert {m: None if h is None else h.verdict for m, h in horizons.items()} == {
        STARVED_GEAR: HORIZON_GEAR, STARVED_OUT_OF_REACH: HORIZON_OUT_OF_REACH}

    # WHERE EACH VERDICT IS SERVED: the gear verdict by the task root.
    roots = {m: _task_root(_starved_state(m, gd), gd, TIMED_NO_PROFILE_CONTEXT, None)
             for m in (STARVED_GEAR, STARVED_OUT_OF_REACH)}
    assert roots == {
        STARVED_GEAR: ObtainItem(code="goblin_guard_shield", quantity=1, slot="shield_slot"),
        STARVED_OUT_OF_REACH: None}


def test_an_out_of_horizon_task_leaves_the_character_doing_its_own_work(
        gd: GameData) -> None:
    """INERT means INDISTINGUISHABLE FROM NOT HOLDING THE TASK — measured.

    This is the freeze the latch caused, stated as an outcome instead of a flag.
    The control is the SAME character with no task at all: a task the horizon
    cannot reach must not change what it does, and a task gear closes asks for
    that gear through the task root, an alternative the rotation serves, never
    a diversion of the head (Phase 3-2, global gear objective Task 5).

    `HORIZON_LEVEL_UP` would land with the out-of-reach row deliberately, and
    the reason is in `regear_edge.py`: the standing arm's other conjunct is
    `not winnable_alternative`, so a level-up verdict reached HERE has no monster
    to fight for the level. Letting the objective's own XP grind run IS the
    level-up being pursued. (This cell has no level-up row under the odds; see
    the note at `STARVED`.)"""
    _, _, control = _starved_run(None, gd)
    control_goal, control_first = repr(control.selected_goal), repr(control.plan[0])

    for monster in (STARVED_OUT_OF_REACH,):
        _, _, report = _starved_run(monster, gd)
        assert repr(report.selected_goal) == control_goal
        assert repr(report.plan[0]) == control_first

    # ...and the closable row is the one whose fight arm FIRES. Until Phase 3-2
    # it diverted the character: the walk resolved the gear's skill gate,
    # `ReachSkillLevel(weaponcrafting, 43)`, and the arbiter fell through to
    # gathering 11 mithril bars for a weapon that gate keeps it from crafting.
    # The walk now asks that step first; it declines (no recipe grinds
    # weaponcrafting from here), so the arm names the blocker and the walk
    # continues to the character's own work.
    #
    # RE-DERIVED 2026-10-18 (ruling R): on the derived sheet the gear row is
    # `dryad` and its arm names `slime_shield`, whose cloth (wool) has no route
    # this cycle; the arm declines it FIRST, ahead of the control's own
    # declines, and the walk continues to the character's own work. The old
    # weaponcrafting-43 decline was the old row's (`corrupted_ogre`), a stat
    # artefact (see `STARVED_GEAR`).
    #
    # RE-DERIVED Task 5 (global gear objective): the fight arm is no longer the
    # walk's entry. The gear row's task asks for its gear through the TASK
    # root instead (`_task_root`), offered after the character's own `L*`
    # pieces; the head is the control's own first piece, nothing is declined,
    # and the character does exactly the control's work.
    #
    # RE-DERIVED plan C Task 2: the task root is `L*(dryad)`'s first missing
    # piece, `goblin_guard_shield`, which is also the head of the character's
    # own `L*`: the task asks for the piece the character already pursues, so it
    # adds no alternative (the deleted deficit walk appended `slime_shield`).
    _, _, gear = _starved_run(STARVED_GEAR, gd)
    shield = ObtainItem(code="goblin_guard_shield", quantity=1, slot="shield_slot")
    assert gear.decision.ranking[0].category == "WhichPieceIsNext → IsThisTargetBlocked"
    assert gear.decision.chosen_root == control.decision.chosen_root == shield
    assert gear.decision.declined == control.decision.declined == ()
    assert gear.decision.fallback_roots == control.decision.fallback_roots
    assert repr(gear.selected_goal) == control_goal


# ---------------------------------------------------------------------------
# THE ITEMS-TASK CELL (wave 6, increment 5.0)
#
# `ScenarioCharacter.task` had SIX holders before this, every one a `monsters`
# task — which mirrors production exactly (0 items tasks in 15,240 live
# task-cycles) and is precisely why the items-task economy was modelled but
# never exercised end to end.
#
# Each test below asserts the consumer DISCRIMINATES: its answer under the
# items task differs from the same character with no task at all. A test that
# only asserted "the consumer runs" would pass against a consumer that ignores
# the task entirely, which is the failure this cell exists to rule out.
# ---------------------------------------------------------------------------

def _no_task(state):
    return dataclasses.replace(
        state, task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=TaskLifecyclePhase.NONE)


def test_the_items_cell_is_the_only_items_task_in_the_set(gd: GameData) -> None:
    """One cell, and it is the ONLY one — so a future edit that turns it into a
    monsters task silently removes the whole dimension, and this says so."""
    kinds = {n: sc.task[1] for n, sc in SCENARIOS.items() if sc.task}
    assert kinds[ITEMS_CELL] == "items"
    assert [n for n, k in kinds.items() if k == "items"] == [ITEMS_CELL]
    # ...and it differs from its monsters sibling ONLY in the task.
    items, monsters = SCENARIOS[ITEMS_CELL], SCENARIOS[TRIPLE_WORKABLE]
    assert dataclasses.replace(items, name="x", task=None, description="") \
        == dataclasses.replace(monsters, name="x", task=None, description="")


def test_inventory_keep_holds_the_task_item(gd: GameData) -> None:
    """`inventory_keep.py:301` — the task item is kept for the REMAINING units.

    Measured 0 -> 8 (10 total, 2 done). Asserted against the no-task control so
    a consumer that ignored the task would fail here."""
    state = _state(ITEMS_CELL, gd)
    assert keep_in_bag("apprentice_gloves", state, gd, TIMED_NO_PROFILE_CONTEXT) \
        > keep_in_bag("apprentice_gloves", _no_task(state), gd, TIMED_NO_PROFILE_CONTEXT)
    assert keep_in_bag("apprentice_gloves", state, gd, TIMED_NO_PROFILE_CONTEXT) \
        == state.task_total - state.task_progress


def test_craft_relief_caps_by_the_remaining_task_units(gd: GameData) -> None:
    """`craft_relief.py:196` — an active items task caps the craft at the units
    still owed, so the bot does not over-craft a task item.

    The cap is the DISCRIMINATOR: without the task the code is not considered at
    all, so the two answers must differ."""
    state = _state(ITEMS_CELL, gd)
    with_task = craft_relief_candidates(state, gd)
    without = craft_relief_candidates(_no_task(state), gd)
    assert with_task != without
    assert any(c.item_code == "apprentice_gloves" for c in with_task)


def test_a_paying_items_task_stands_down_the_grind(gd: GameData) -> None:
    """`objective_step_fight_core.py` — the level step defers to an in-progress
    items task only while it PAYS (spec 2026-10-14); the gap plays no part.

    Every arm is exercised: unpaid fights, and a non-items task never defers."""
    args = dict(is_reach_char_level=True, has_combat_monster=True,
                task_progress=2, task_total=10)
    assert objective_step_is_fight_pure(
        task_type="items", task_code="apprentice_gloves", task_pays=True, **args) is False
    assert objective_step_is_fight_pure(
        task_type="items", task_code="apprentice_gloves", task_pays=False, **args) is True
    assert objective_step_is_fight_pure(
        task_type="monsters", task_code="cow", task_pays=True, **args) is True
