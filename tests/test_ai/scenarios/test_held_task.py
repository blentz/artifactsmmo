"""The HELD TASK dimension of the scenario set.

`ScenarioCharacter.task` has existed since the harness was built and, until this
file, no scenario set it: 30 of 30 carried `task_code=None`, so
`combat_deficit.blocked_task_monster` returned `None` in every offline test and
everything downstream of it — `has_combat_deficit`, `deficit_upgrade_target`,
`GearLatch`, the `GEAR_REVIEW` guard — was reachable only through hand-built
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
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.task_horizon import HORIZON_LEVEL_UP, resolve_task_horizon
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

WORKABLE = "l12_gearcrafting_gap"
UNWINNABLE_CLOSABLE = "l13_drop_recipe_grind"
UNWINNABLE_OPEN = "l10_copper_adequate"

TRIPLE_WORKABLE = "l32_held_task_workable"
TRIPLE_CLOSABLE = "l32_held_task_closable"
TRIPLE_OPEN = "l32_held_task_open"
TRIPLE = (TRIPLE_WORKABLE, TRIPLE_CLOSABLE, TRIPLE_OPEN)

TASK_SCENARIOS = (WORKABLE, UNWINNABLE_CLOSABLE, UNWINNABLE_OPEN, *TRIPLE)


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


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
        assert state.task_type == kind == "monsters"
        assert (state.task_progress, state.task_total) == (progress, total)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.IN_PROGRESS
        assert gd.monster_level(code) is not None, "the task monster must be real"


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


def test_the_task_triple_flips_the_gear_latch(gd: GameData) -> None:
    """`gear_latch.py:79`, the STANDING arm, with the task as the only input moving.

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
    def _latch(name: str, *, winnable_alternative: bool) -> bool:
        state = _state(name, gd)
        assert has_craftable_upgrade_any_slot(state, gd) is True
        latch = GearLatch()
        latch.update(state.level, state, None, gd,
                     winnable_alternative=winnable_alternative)
        return latch.active

    assert _latch(TRIPLE_WORKABLE, winnable_alternative=False) is False
    assert _latch(TRIPLE_CLOSABLE, winnable_alternative=False) is True
    assert _latch(TRIPLE_OPEN, winnable_alternative=False) is False
    # The other conjunct still binds: an alternative to fight releases all three.
    for name in TRIPLE:
        assert _latch(name, winnable_alternative=True) is False


def test_no_offline_scenario_can_starve_the_winnable_cascade(gd: GameData) -> None:
    """Why the test above passes `winnable_alternative` instead of measuring it.

    `GearLatch`'s standing arm needs the cascade to find NOTHING worth
    fighting. Offline it always finds something: `_path_aligned_monster` returns
    a winnable low-level slime for every derived-stats character measured
    (levels 20-45, copper and iron loadouts alike), so `winnable_alternative`
    is True and the standing arm cannot fire from a scenario alone. The EDGE
    arm needs `last_outcome == "error:fight_lost"` or a level-up, and
    `ScenarioCharacter` can declare neither.

    Recorded as an assertion rather than a comment so that the day the cascade
    CAN come up empty offline, this fails and cell 2 gets promoted from
    "the latch's state conjuncts hold" to "the guard fires end to end"."""
    for name in TRIPLE:
        player = GamePlayer(character=name, history=None)
        player.seed_offline(_state(name, gd), gd)
        assert player._winnable_farm_target() is not None
        player.plan_from_state()
        assert player._last_ctx is not None
        assert player._last_ctx.gear_review_active is False


def test_the_task_triple_moves_the_gear_review_target(gd: GameData) -> None:
    """`strategy_driver.py:381` — both arms, reached from the triple.

    This is where D2 stops being a predicate and becomes a DECISION. The
    GEAR_REVIEW guard asks `deficit_upgrade_target` FIRST and only falls
    through to the monster-blind value scan when it names nothing. Cell 2 takes
    the first arm; cells 1 and 3 take the fall-through, and they take it for
    different reasons (no deficit at all vs a deficit no gear closes) — which
    is why the triple needs all three rows and not two.

    Measured: the guard prices its candidates with `acquisition_actions`, so the
    deficit target it lands on (`earth_boost_potion`) is the priced answer, not
    the unpriced `perfect_bow` of `test_the_task_triple_splits_the_deficit_three_ways`.
    Both are `deficit_upgrade_target`; only the `cost_of` differs."""
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, gear_review_active=True)
    goals = {name: repr(map_guard(GuardKind.GEAR_REVIEW, gd, ctx,
                                  state=_state(name, gd)))
             for name in TRIPLE}
    assert "earth_boost_potion" in goals[TRIPLE_CLOSABLE]
    # The two fall-through rows agree with each other and DISAGREE with the
    # deficit-driven one — the generic scan is monster-blind, which is the
    # whole reason the monster-aware arm was added.
    assert goals[TRIPLE_WORKABLE] == goals[TRIPLE_OPEN]
    assert goals[TRIPLE_CLOSABLE] != goals[TRIPLE_WORKABLE]


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
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, gear_review_active=True)

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
