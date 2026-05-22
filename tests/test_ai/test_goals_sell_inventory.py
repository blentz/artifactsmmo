"""Tests for SellInventoryGoal."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from tests.test_ai.fixtures import make_state


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    return gd


class TestSellInventoryGoal:
    def test_value_zero_when_bank_accessible(self):
        goal = SellInventoryGoal(bank_accessible=True)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_no_sellable_items(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"useless_thing": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_already_satisfied(self):
        """Goal should return 0 when inventory_free >= MIN_FREE_SLOTS, even with sellables and bank locked."""
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 10}, inventory_max=20)  # 10 free, satisfied
        assert goal.value(state, gd) == 0.0

    def test_value_scales_with_inventory_fill_when_locked_and_has_sellable(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 18}, inventory_max=20)  # 2 free, NOT satisfied
        # used=18/max=20 = 0.9; * 100 = 90
        assert goal.value(state, gd) == 90.0

    def test_value_caps_at_100_at_full(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 20}, inventory_max=20)  # 0 free, NOT satisfied
        assert goal.value(state, gd) == 100.0

    def test_is_satisfied_when_min_free_slots_available(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 10}, inventory_max=20)  # 10 free
        assert goal.is_satisfied(state) is True

    def test_is_not_satisfied_when_inventory_nearly_full(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 18}, inventory_max=20)  # 2 free
        assert goal.is_satisfied(state) is False

    def test_relevant_actions_filters_to_rest_and_sells_for_inventory_items(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5, "bread": 2}})
        state = make_state(inventory={"chicken": 5, "bread": 3, "useless": 1})
        actions = [
            RestAction(),
            FightAction(monster_code="goblin", locations=frozenset({(1, 1)})),
            NpcSellAction(npc_code="cook", item_code="chicken", quantity=1, npc_location=(2, 1)),
            NpcSellAction(npc_code="cook", item_code="bread", quantity=1, npc_location=(2, 1)),
            NpcSellAction(npc_code="cook", item_code="not_in_inventory", quantity=1, npc_location=(2, 1)),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        # Rest stays; FightAction excluded; only sells for inventory items
        names = [repr(a) for a in relevant]
        assert "Rest" in names
        assert any("NpcSell(chicken" in n for n in names)
        assert any("NpcSell(bread" in n for n in names)
        assert not any("NpcSell(not_in_inventory" in n for n in names)
        assert not any("Fight" in n for n in names)

    def test_desired_state_targets_min_free_slots(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 18}, inventory_max=20)
        assert goal.desired_state(state, GameData()) == {"inventory_free": 5}

    def test_repr(self):
        assert repr(SellInventoryGoal(bank_accessible=False)) == "SellInventory"
