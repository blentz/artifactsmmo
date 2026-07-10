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
    # inventory_max=100 (the fixture default of 20 would leave this 100-qty
    # single-stack state over the total-quantity cap — invisible before the
    # EquipAction net-slot room guard, which now correctly reads inventory_free
    # off inventory_max and would reject the quantity-neutral equip on a
    # negative headroom that predates this test's guard-relevant assertion).
    state = make_state(level=5, inventory={"small_health_potion": 100},
                       inventory_max=100,
                       equipment={"utility1_slot": None, "utility2_slot": None})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60, level=1)
    goal = _goal()
    plan = plan_for_goal(goal, state, gd)   # use the repo's planner entrypoint
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot"
               and a.quantity == 40 for a in plan)


def test_consumable_type_heal_yields_no_plan() -> None:
    """Seam lock: a goal built with a type=consumable heal_code cannot plan — its
    EquipAction targets a utility slot but a consumable item is not utility-slot
    equippable, so EquipAction.is_applicable rejects it and the planner returns
    no equip. This is why best_held_heal must pre-filter to utility heals."""
    state = make_state(level=5, inventory={"cooked_fish": 100},
                       equipment={"utility1_slot": None, "utility2_slot": None})
    gd = GameData()
    gd._item_stats = {
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=60),
    }
    goal = ProvisionMarginalFightGoal(target_monster="green_slime",
                                      heal_code="cooked_fish", quantity=40)
    plan = plan_for_goal(goal, state, gd)
    assert plan == []


def test_desired_state_returns_empty_dict() -> None:
    state = make_state()
    gd = GameData()
    assert _goal().desired_state(state, gd) == {}


def test_serialize_returns_expected_dict() -> None:
    assert _goal().serialize() == {
        "type": "ProvisionMarginalFightGoal",
        "target_monster": "green_slime",
        "heal_code": "small_health_potion",
        "quantity": 40,
    }


def test_repr_format() -> None:
    assert repr(_goal()) == "ProvisionMarginalFight(green_slime,small_health_potionx40)"
