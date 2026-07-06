"""Tests for ReachCurrencyGoal (C3 Task 4)."""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def test_satisfied_when_currency_at_target():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 8})) is True
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 5})) is False


def test_satisfied_counts_bank_items():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    # 3 in inventory + 5 in bank = 8 total → satisfied
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 3},
                                     bank_items={TASKS_COIN_CODE: 5})) is True
    # 3 in inventory + 4 in bank = 7 → not satisfied
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 3},
                                     bank_items={TASKS_COIN_CODE: 4})) is False


def test_max_depth_is_property_sufficient_for_worst_case():
    # worst case on_hand=0, floor=1 -> 8 cycles * 3 actions = 24
    # `max_depth` is a PROPERTY (no args), matching Goal.max_depth.
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    assert g.max_depth == 8 * 3


def test_max_depth_at_least_actions_per_cycle():
    # target=0 → funding_cycles_pure(0,0,1)=0; max still ≥ ACTIONS_PER_CYCLE=3
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 0)
    assert g.max_depth >= 3


def test_relevant_actions_keeps_task_lifecycle_and_progress():
    """Accept/Complete/Fight only. Crafts CANNOT progress the monsters-typed
    in-model pending task, so keeping the ~320 CraftActions only floods the
    h=0 search (live probe 2026-07-06: 24K nodes / 10s timeout with crafts,
    plannable in milliseconds without)."""
    from artifactsmmo_cli.ai.actions.crafting import CraftAction

    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    gd = GameData()
    acts = [
        AcceptTaskAction(taskmaster_location=(0, 0)),
        CompleteTaskAction(taskmaster_location=(0, 0)),
        FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
        CraftAction(code="wooden_shield", quantity=1, workshop_location=(2, 2)),
    ]
    kept = g.relevant_actions(acts, make_state(), gd)
    assert any(isinstance(a, AcceptTaskAction) for a in kept)
    assert any(isinstance(a, CompleteTaskAction) for a in kept)
    assert any(isinstance(a, FightAction) for a in kept)
    assert not any(isinstance(a, CraftAction) for a in kept)


def test_value_nonzero_when_unsatisfied():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    state = make_state(inventory={TASKS_COIN_CODE: 2})
    gd = GameData()
    assert g.value(state, gd) > 0.0


def test_value_zero_when_satisfied():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    state = make_state(inventory={TASKS_COIN_CODE: 8})
    gd = GameData()
    assert g.value(state, gd) == 0.0


def test_desired_state_targets_currency_inventory():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    gd = GameData()
    state = make_state()
    ds = g.desired_state(state, gd)
    assert ds == {"inventory": {TASKS_COIN_CODE: 8}}


def test_repr():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    assert repr(g) == f"ReachCurrency({TASKS_COIN_CODE}, 8)"


def _funding_fixture() -> tuple[GameData, object]:
    """A minimal world where one funding cycle is plannable: a taskmaster, a
    beatable monster, and a known coin reward."""
    gd = GameData()
    gd._taskmaster_location = (1, 2)
    gd._monster_locations = {"chicken": (1, 0)}
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": []}
    gd._task_coin_rewards = {"chickens": 2}
    gd._xp_per_kill = {"chicken": 10}
    fill_monster_stat_defaults(gd)
    state = make_state(level=5, x=0, y=0, task_code=None, task_type=None,
                       inventory={}, bank_items={})
    return gd, state


def test_accept_apply_produces_progressable_task():
    """The in-model pending task must be PROGRESSABLE: AcceptTask.apply sets
    task_type so a subsequent Fight.apply can raise task_progress. Live bug
    2026-07-06: apply left task_type=None and no monster matches
    '__pending__', so CompleteTask was never applicable in ANY projection and
    ReachCurrencyGoal (the whole C4 funding pipeline) was unplannable —
    satchel/jasper_crystal acquisition stalled forever."""
    gd, state = _funding_fixture()
    accept = AcceptTaskAction(taskmaster_location=(1, 2))
    after_accept = accept.apply(state, gd)
    assert after_accept.task_type == "monsters"
    fight = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
    after_fight = fight.apply(after_accept, gd)
    assert after_fight.task_progress == 1
    complete = CompleteTaskAction(taskmaster_location=(1, 2))
    assert complete.is_applicable(after_fight, gd)


def test_fight_does_not_progress_real_task_of_other_monster():
    """The pending-task progress rule must NOT leak into real tasks: a live
    'wolves' task does not advance by fighting chickens."""
    gd, state = _funding_fixture()
    import dataclasses
    tasked = dataclasses.replace(state, task_code="wolf", task_type="monsters",
                                 task_progress=0, task_total=10)
    fight = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
    assert fight.apply(tasked, gd).task_progress == 0


def test_goal_plans_one_funding_cycle_end_to_end():
    """The planner must FIND accept->fight->complete from a no-task state.
    This is the integration the unit tests above exist to enable; it was
    never asserted before, which is how the feature shipped inert."""
    from artifactsmmo_cli.ai.planner import GOAPPlanner

    gd, state = _funding_fixture()
    goal = ReachCurrencyGoal(TASKS_COIN_CODE, 2)  # one cycle at reward 2
    actions = [
        AcceptTaskAction(taskmaster_location=(1, 2)),
        CompleteTaskAction(taskmaster_location=(1, 2)),
        FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
    ]
    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd, budget_seconds=10.0)
    names = [type(a).__name__ for a in plan]
    assert names == ["AcceptTaskAction", "FightAction", "CompleteTaskAction"], (
        f"one funding cycle must be plannable, got {names} "
        f"(explored={planner.last_stats.nodes_explored})"
    )
