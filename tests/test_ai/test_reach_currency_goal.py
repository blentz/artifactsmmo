"""Tests for ReachCurrencyGoal (C3 Task 4)."""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
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
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    gd = GameData()
    acts = [
        AcceptTaskAction(taskmaster_location=(0, 0)),
        CompleteTaskAction(taskmaster_location=(0, 0)),
        FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
    ]
    kept = g.relevant_actions(acts, make_state(), gd)
    assert any(isinstance(a, AcceptTaskAction) for a in kept)
    assert any(isinstance(a, CompleteTaskAction) for a in kept)
    assert any(isinstance(a, FightAction) for a in kept)


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
