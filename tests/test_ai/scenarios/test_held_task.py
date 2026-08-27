"""The HELD TASK dimension of the scenario set.

`ScenarioCharacter.task` has existed since the harness was built and, until this
file, no scenario set it: 30 of 30 carried `task_code=None`, so
`combat_deficit.blocked_task_monster` returned `None` in every offline test and
everything downstream of it — `has_combat_deficit`, `deficit_upgrade_target`,
`RegearEdge`, the `GEAR_REVIEW` guard — was reachable only through hand-built
states. Live, 21.1 % of cycles hold a task, and every one of them is a
`monsters` task.

Three scenarios now hold one, chosen to give the dimension three DISTINCT
values rather than three copies of one:

* `l12_gearcrafting_gap` — a task it can win (deficit False),
* `l13_drop_recipe_grind` — a task it cannot win, with gear that closes the gap,
* `l10_copper_adequate` — a task it cannot win, with NO gear that closes it.

Those three populate the dimension. They do not CONTROL it: they are three
different characters at three levels with three loadouts, so nothing measured
across them can be attributed to the task rather than to everything else that
also differs. Coverage-matrix cells 1-3 (design 2026-08-24 §5.3) add the
controlled form — ONE character in three task states, every other field
identical:

* `l32_held_task_workable` — pig, winnable,
* `l32_held_task_closable` — ogre, unwinnable, a chain closes it,
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
   two of them ever collapse onto the same `(deficit, closable)` pair — which is
   how a dimension quietly stops discriminating.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat_deficit import deficit_upgrade_target, has_combat_deficit
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.decisions.root import (
    IsAFightBlockingMe,
    RootWalk,
    WhichSlotClosesTheFight,
    resolve_root,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.inventory_keep import keep_in_bag
from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    HORIZON_LEVEL_UP,
    HORIZON_OUT_OF_REACH,
    resolve_task_horizon,
)
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE

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
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _obj(game_data: GameData) -> CharacterObjective:
    return CharacterObjective(target_char_level=50, target_skill_levels={},
                              target_gear={}, _game_data=game_data)


def _state(name: str, game_data: GameData):
    return scenario_state(SCENARIOS[name], game_data)


def test_the_held_task_dimension_has_a_populated_side(gd: GameData) -> None:
    """The dimension is populated at all — and the fields are wired end to end."""
    holders = [n for n in SCENARIOS if SCENARIOS[n].task is not None]
    assert sorted(holders) == sorted(TASK_SCENARIOS)
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
               deficit_upgrade_target(_state(name, gd), gd) is not None)
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
    assert deficit_upgrade_target(state, gd) is None


def test_unwinnable_task_names_the_gear_that_closes_it(gd: GameData) -> None:
    """The "I lost, so get gear" link, with an offline witness at last.

    Before this the ONLY route from a lost fight to a gear upgrade was a
    countdown timer, and the walk that replaced it had no scenario exercising
    its positive arm."""
    state = _state(UNWINNABLE_CLOSABLE, gd)
    assert has_combat_deficit(state, gd) is True
    target = deficit_upgrade_target(state, gd)
    assert target is not None
    item, slot = target
    assert slot == "weapon_slot"
    assert gd.item_stats(item) is not None


def test_unwinnable_task_with_no_closing_chain_names_nothing(gd: GameData) -> None:
    """The FALL-THROUGH arm: a deficit no gear in the catalogue closes.

    Paired with the test above on purpose — `None` here is only meaningful next
    to a case where the same call returns a target, otherwise it is
    indistinguishable from the function never running."""
    state = _state(UNWINNABLE_OPEN, gd)
    assert has_combat_deficit(state, gd) is True
    assert deficit_upgrade_target(state, gd) is None


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


def test_the_task_triple_splits_the_deficit_three_ways(gd: GameData) -> None:
    """One character, three tasks, three answers at the branch D2 names.

    `blocked_task_monster` is reached in all three (a task is held); what
    differs is only which arm of `has_combat_deficit` / `deficit_upgrade_target`
    the monster lands on. Measured over all 58 catalogue monsters at this
    loadout: 12 are workable, 8 closable, 38 open — so none of the three values
    is a lucky single.

    That split was 12 / 37 / 9 while `deficit_upgrade_target` branched on
    `deficit.chain` instead of `deficit.closes`. Twenty-nine of those thirty-
    seven "closable" monsters were nothing of the kind: the walk named an item
    that moved the margin and never reached zero, and the guard committed to it
    anyway. The middle value is now the monsters a chain really does close, and
    it is still populated eight times over."""
    workable = _state(TRIPLE_WORKABLE, gd)
    closable = _state(TRIPLE_CLOSABLE, gd)
    open_ = _state(TRIPLE_OPEN, gd)

    assert has_combat_deficit(workable, gd) is False
    assert deficit_upgrade_target(workable, gd) is None

    assert has_combat_deficit(closable, gd) is True
    target = deficit_upgrade_target(closable, gd)
    assert target == ("perfect_bow", "weapon_slot")

    assert has_combat_deficit(open_, gd) is True
    assert deficit_upgrade_target(open_, gd) is None
    # ...and the lich really is IN BAND, so the fall-through is a gear fact and
    # not the artefact of naming a monster twenty levels out of reach.
    assert gd.monster_level("lich") <= SCENARIOS[TRIPLE_OPEN].level


def test_the_task_triple_flips_the_regear_edge(gd: GameData) -> None:
    """`regear_edge.py:79`, the STANDING arm, with the task as the only input moving.

    The latch's standing arm is a three-way conjunction: a craftable upgrade
    exists, the cascade found nothing else worth fighting, and a combat deficit
    exists. The first is identical across the triple (asserted here so a
    failure cannot be blamed on it) and the second is supplied explicitly —
    see `test_no_offline_scenario_can_starve_the_winnable_cascade` for why it
    has to be. So the latch's answer moves with the deficit, i.e. with the
    task, which is exactly the claim cell 2 makes.

    THE OPEN CELL FLIPPED ON 2026-08-25, and it is the point of the one-level
    horizon rather than a regression. The third conjunct was `has_combat_deficit`
    — the bare fact "this fight is lost" — so cells 2 and 3 armed the latch
    IDENTICALLY even though only cell 2 has gear that wins the fight. GEAR_REVIEW
    is a guard, so for cell 3 that meant preempting the objective step to build
    gear the walk had just proved cannot close the gap, and falling through to
    the monster-blind value scan to pick it (measured: the SAME goal cell 1
    produces — see `test_the_task_triple_moves_the_gear_review_target`). Live
    R2D2 did that for 981 consecutive cycles with character XP frozen 31.6 h.
    The conjunct is now `task_horizon` == HORIZON_GEAR, so the latch arms where
    gear really is what stands in the way and nowhere else — which is what the
    class docstring said all along.

    Cell 2 still arms it. A fix that quieted cell 3 by deleting the standing arm
    would have deleted the loss->upgrade link with it, and this line is what
    says so."""
    def _arm(name: str, *, winnable_alternative: bool) -> bool:
        """Does the WALK take the fight arm? (wave 4: this was the latch.)

        The standing arm is now `decisions/root.IsAFightBlockingMe`, so the
        question "does this cell arm the gear review" is asked of the node. The
        rows below are unchanged from the latch era — the behaviour moved, it
        did not change."""
        state = _state(name, gd)
        assert has_craftable_upgrade_any_slot(state, gd) is True
        monster = "chicken" if winnable_alternative else None
        child = IsAFightBlockingMe(
            _obj(gd), RootWalk()).resolve(
                state, gd,
                dataclasses.replace(NO_PROFILE_CONTEXT, combat_monster=monster),
                None)
        return isinstance(child, WhichSlotClosesTheFight)

    assert _arm(TRIPLE_WORKABLE, winnable_alternative=False) is False
    assert _arm(TRIPLE_CLOSABLE, winnable_alternative=False) is True
    assert _arm(TRIPLE_OPEN, winnable_alternative=False) is False
    # The other conjunct still binds: an alternative to fight releases all three.
    for name in TRIPLE:
        assert _arm(name, winnable_alternative=True) is False


def test_the_triple_cannot_starve_the_winnable_cascade(gd: GameData) -> None:
    """Why the test above passes `winnable_alternative` instead of measuring it.

    `RegearEdge`'s standing arm needs the cascade to find NOTHING worth fighting,
    and for THESE THREE cells it always finds something: `_path_aligned_monster`
    returns a winnable low-level slime for each of them, so `winnable_alternative`
    is True and the standing arm cannot fire from the triple alone.

    THE SCOPE OF THAT CLAIM WAS WRONG AND IS NOW MEASURED. This test used to be
    called `test_no_offline_scenario_can_starve_the_winnable_cascade` and its
    docstring generalised to "every derived-stats character measured" — but it
    only ever asserted over `TRIPLE`, three of forty-two. Swept over all of them
    (2026-08-25), **11 of 42 scenarios DO starve the cascade**: `l1_fresh`,
    `l3_low_hp`, `l8_overstocked`, `l10_gearcrafting_gap_combat_blocked`,
    `l15_midband`, `l20_band_entry`, `l30_band_entry`, `l40_band_entry`,
    `l48_capstone_approach`, `l48_band_adequate`, `l48_raid_active`. None of them
    holds a task, which is the real and much narrower reason the standing arm was
    unreachable — and giving one a task is all it took to reach it. That witness
    is `test_a_starved_cascade_witnesses_the_standing_arm_end_to_end` below."""
    for name in TRIPLE:
        player = GamePlayer(character=name, history=None)
        player.seed_offline(_state(name, gd), gd)
        assert player._winnable_farm_target() is not None
        player.plan_from_state()
        assert player._last_ctx is not None
        assert player._last_ctx.regear_level_up is False


def test_the_task_triple_moves_the_gear_review_target(gd: GameData) -> None:
    """`WhichSlotClosesTheFight` — both arms, reached from the triple.

    This is where D2 stops being a predicate and becomes a DECISION. The node
    asks `deficit_upgrade_target` and hands its answer to `IsThisTargetBlocked`;
    when it names nothing the walk falls through to the tier arm. Cell 2 takes
    the first arm; cells 1 and 3 take the fall-through, and they take it for
    different reasons (no deficit at all vs a deficit no gear closes) — which
    is why the triple needs all three rows and not two.

    Measured: the node prices its candidates through `route_price`, so the
    deficit target it lands on (`earth_boost_potion`) is the priced answer, not
    the unpriced `perfect_bow` of `test_the_task_triple_splits_the_deficit_three_ways`.
    Both are `deficit_upgrade_target`; only the `actions_of` differs.

    WAS `map_guard(GEAR_REVIEW)` until wave 4. The assertions are unchanged: the
    same cell still names the same priced item, one layer down."""
    roots = {name: repr(resolve_root(_state(name, gd), gd, _obj(gd),
                                     NO_PROFILE_CONTEXT, None).root)
             for name in TRIPLE}
    assert "earth_boost_potion" in roots[TRIPLE_CLOSABLE]
    # The two fall-through rows agree with each other and DISAGREE with the
    # deficit-driven one. They now fall through to the TIER arm rather than to a
    # monster-blind value scan — that scan was deleted with the guard branch, so
    # what they agree on is the objective's own next step.
    assert roots[TRIPLE_WORKABLE] == roots[TRIPLE_OPEN]
    assert roots[TRIPLE_CLOSABLE] != roots[TRIPLE_WORKABLE]


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
# distinction, taken at the three places the fact is consumed.


def test_the_gear_review_guard_takes_the_level_when_gear_cannot(gd: GameData) -> None:
    """The middle clause, at the one place it becomes an action.

    `l13_drop_recipe_grind` against `mushmush`: no chain closes the fight at 13,
    `iron_dagger` closes it at 14, and the catalogue pool is identical at both
    levels — so the level, not the pool, is what buys the fight. The guard maps to
    `ReachUnlockLevelGoal(14)` instead of falling through to the monster-blind
    value scan, which is what it did for every such state before."""
    state = dataclasses.replace(
        _state(UNWINNABLE_CLOSABLE, gd), task_code="mushmush", task_type="monsters",
        task_progress=0, task_total=10,
        task_lifecycle_phase=TaskLifecyclePhase.IN_PROGRESS)
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, regear_level_up=True)

    assert resolve_task_horizon(state, gd).verdict == HORIZON_LEVEL_UP
    assert repr(map_guard(GuardKind.GEAR_REVIEW, gd, ctx, state=state)) == (
        f"ReachUnlockLevel({state.level + 1})")


def test_the_open_task_is_cancelled_end_to_end_with_a_coin(gd: GameData) -> None:
    """The whole ladder, from a held task to a first action.

    Measured on this exact cell at HEAD~ (a `tasks_coin` added to the pocket so
    the rung's S-052 gate is satisfied): the bot planned
    `GatherMaterials(flying_wing, {flying_wing:6})` with a first action of
    `Fight(flying_snake)` — it kept the dead lich task and went and did something
    else, forever, because `task_feasibility`'s level proxy reported a level-30
    monster feasible for a level-32 character. Cell 2 already cancelled before
    this change and still does, but for S-048's reason (an ogre pays a level-32
    character no XP), which is why it cannot stand in for cell 3."""
    state = _state(TRIPLE_OPEN, gd)
    state = dataclasses.replace(
        state, inventory={**state.inventory, TASKS_COIN_CODE: 1})
    player = GamePlayer(character=TRIPLE_OPEN, history=None)
    player.seed_offline(state, gd)
    report = player.plan_from_state()

    assert repr(report.selected_goal) == "TaskCancel"
    assert repr(report.plan[0]) == "TaskCancel"


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
# of the forty-two scenarios starve the cascade (see
# `test_the_triple_cannot_starve_the_winnable_cascade`); none of them holds a
# task. Giving one a task closes the last conjunct and the arm becomes reachable
# from `plan_from_state` — the same entry point production uses.

STARVED = "l48_capstone_approach"
STARVED_GEAR = "corrupted_ogre"
STARVED_LEVEL_UP = "dryad"
STARVED_OUT_OF_REACH = "baby_red_dragon"


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
    player.seed_offline(state, game_data)
    report = player.plan_from_state()
    assert player._last_ctx is not None
    return state, player, report


def test_a_starved_cascade_witnesses_the_standing_arm_end_to_end(gd: GameData) -> None:
    """The `GEAR_REVIEW` guard, fired and NOT fired, through `plan_from_state`.

    All three rows share `has_combat_deficit is True` — the bare fact the arm
    used to test — so before `63533b82` all three armed the latch and all three
    handed the character to the guard. The horizon splits them: only the row a
    gear chain closes is entitled to preempt the objective.

    The EDGE arm is provably not what fires here: `plan_from_state` passes
    `self._last_outcome` (None on a seeded player) and `prev_level == state.level`,
    so `self._active` cannot be set. What is measured is `_blocked` alone."""
    for monster in (STARVED_GEAR, STARVED_LEVEL_UP, STARVED_OUT_OF_REACH):
        state, player, _ = _starved_run(monster, gd)
        # The three conjuncts of the standing arm, measured rather than passed in.
        assert player._winnable_farm_target() is None
        assert has_craftable_upgrade_any_slot(state, gd) is True
        # ...and the fact the OLD arm read, identical across all three rows.
        assert has_combat_deficit(state, gd) is True

    verdicts = {m: resolve_task_horizon(_starved_state(m, gd), gd).verdict
                for m in (STARVED_GEAR, STARVED_LEVEL_UP, STARVED_OUT_OF_REACH)}
    assert verdicts == {STARVED_GEAR: HORIZON_GEAR,
                        STARVED_LEVEL_UP: HORIZON_LEVEL_UP,
                        STARVED_OUT_OF_REACH: HORIZON_OUT_OF_REACH}

    # WHERE EACH VERDICT IS SERVED, after wave 4 split the two arms.
    #
    # The guard flag is now `level_up_pending`, which needs an EDGE. A seeded
    # player has none (`_last_outcome` is None and `prev_level == state.level`),
    # so it is False on all three rows — including the gear row, which used to
    # be True here. That is the split, not a regression: the gear verdict is
    # served by the graph now, and the assertion below is what says so.
    active = {m: _starved_run(m, gd)[1]._last_ctx.regear_level_up
              for m in (STARVED_GEAR, STARVED_LEVEL_UP, STARVED_OUT_OF_REACH)}
    assert active == {STARVED_GEAR: False,
                      STARVED_LEVEL_UP: False,
                      STARVED_OUT_OF_REACH: False}

    armed = {m: isinstance(
                 IsAFightBlockingMe(_obj(gd), RootWalk()).resolve(
                     _starved_state(m, gd), gd, NO_PROFILE_CONTEXT, None),
                 WhichSlotClosesTheFight)
             for m in (STARVED_GEAR, STARVED_LEVEL_UP, STARVED_OUT_OF_REACH)}
    assert armed == {STARVED_GEAR: True,
                     STARVED_LEVEL_UP: False,
                     STARVED_OUT_OF_REACH: False}


def test_an_out_of_horizon_task_leaves_the_character_doing_its_own_work(
        gd: GameData) -> None:
    """INERT means INDISTINGUISHABLE FROM NOT HOLDING THE TASK — measured.

    This is the freeze the latch caused, stated as an outcome instead of a flag.
    The control is the SAME character with no task at all: a task the horizon
    cannot reach must not change what it does, and a task gear closes must.

    `HORIZON_LEVEL_UP` lands with the out-of-reach row deliberately, and the
    reason is in `regear_edge.py`: the standing arm's other conjunct is
    `not winnable_alternative`, so a level-up verdict reached HERE has no monster
    to fight for the level. Letting the objective's own XP grind run IS the
    level-up being pursued."""
    _, _, control = _starved_run(None, gd)
    control_goal, control_first = repr(control.selected_goal), repr(control.plan[0])

    for monster in (STARVED_LEVEL_UP, STARVED_OUT_OF_REACH):
        _, _, report = _starved_run(monster, gd)
        assert repr(report.selected_goal) == control_goal
        assert repr(report.plan[0]) == control_first

    # ...and the closable row is the one that DOES divert the character.
    _, _, gear = _starved_run(STARVED_GEAR, gd)
    assert repr(gear.selected_goal) != control_goal


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
    assert keep_in_bag("apprentice_gloves", state, gd, NO_PROFILE_CONTEXT) \
        > keep_in_bag("apprentice_gloves", _no_task(state), gd, NO_PROFILE_CONTEXT)
    assert keep_in_bag("apprentice_gloves", state, gd, NO_PROFILE_CONTEXT) \
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


def test_a_long_haul_grind_stands_down_for_the_items_task(gd: GameData) -> None:
    """`objective_step_fight_core.py:61` — a bootstrap gap of more than four
    levels DEFERS to an in-progress items task rather than grinding past it.

    Both arms are exercised: the same gap with no task does NOT stand down."""
    args = dict(is_reach_char_level=True, target=40, level=32,
                has_combat_monster=True, task_progress=2, task_total=10)
    assert objective_step_is_fight_pure(
        task_type="items", task_code="apprentice_gloves", **args) is False
    assert objective_step_is_fight_pure(
        task_type="monsters", task_code="cow", **args) is True
