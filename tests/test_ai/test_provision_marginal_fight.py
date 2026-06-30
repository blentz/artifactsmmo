"""Tests for ProvisionMarginalFightGoal."""

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.provision_marginal_fight import (
    PROVISION_MARGINAL_VALUE,
    ProvisionMarginalFightGoal,
)
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _goal() -> ProvisionMarginalFightGoal:
    return ProvisionMarginalFightGoal(target_monster="green_slime",
                                      heal_code="small_health_potion", quantity=40)


def _gd_with_consumable(code: str, hp_restore: int, level: int = 1) -> GameData:
    """Return a GameData containing a single utility-type heal item."""
    gd = GameData()
    gd._item_stats = {
        code: ItemStats(code=code, level=level, type_="utility", hp_restore=hp_restore),
    }
    return gd


def plan_for_goal(goal: ProvisionMarginalFightGoal, state: object,
                  gd: GameData) -> list[object]:
    """Drive the real planner for the given goal; mirrors existing test usage."""
    return GOAPPlanner().plan(state, goal, [], gd, budget_seconds=10.0)


def test_satisfied_when_a_utility_slot_holds_a_heal() -> None:
    state = make_state(equipment={"utility1_slot": "small_health_potion"})
    assert _goal().is_satisfied(state) is True


def test_unsatisfied_when_no_utility_heal() -> None:
    state = make_state(equipment={"utility1_slot": None, "utility2_slot": None})
    assert _goal().is_satisfied(state) is False


def test_value_is_zero_when_satisfied_else_constant() -> None:
    gd = _gd_with_consumable("small_health_potion", hp_restore=60)
    filled = make_state(equipment={"utility1_slot": "small_health_potion"})
    empty = make_state(equipment={"utility1_slot": None, "utility2_slot": None})
    assert _goal().value(filled, gd) == 0.0
    assert _goal().value(empty, gd) == PROVISION_MARGINAL_VALUE


def test_relevant_actions_constructs_the_scaled_equip() -> None:
    state = make_state(inventory={"small_health_potion": 100},
                       equipment={"utility1_slot": None})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60)
    # passed actions are ignored — the goal emits its own quantity-bearing equip
    out = _goal().relevant_actions([EquipAction("copper_helmet", "helmet_slot")], state, gd)
    assert len(out) == 1
    a = out[0]
    assert isinstance(a, EquipAction)
    assert (a.code, a.slot, a.quantity) == ("small_health_potion", "utility1_slot", 40)


def test_goal_plans_the_equip_end_to_end() -> None:
    """Integration: the goal must actually PLAN its equip (verifies desired_state /
    is_satisfied wiring against the real planner)."""
    state = make_state(level=5, inventory={"small_health_potion": 100},
                       equipment={"utility1_slot": None, "utility2_slot": None})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60, level=1)
    goal = _goal()
    plan = plan_for_goal(goal, state, gd)   # use the repo's planner entrypoint
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot"
               and a.quantity == 40 for a in plan)
