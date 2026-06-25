"""Tests for SellInventoryGoal."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.sell_inventory import ACCUM_BASE, ACCUM_STEP, SellInventoryGoal
from tests.test_ai.fixtures import make_state


def _gd_with_buyer() -> GameData:
    """GameData with a permanent NPC buyer for wooden_shield (tradeable, level 1 shield)."""
    gd = GameData()
    gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
    gd._npc_locations = {"vendor": (1, 1)}
    gd._item_stats = {
        "wooden_shield": ItemStats(
            code="wooden_shield", level=1, type_="shield",
            crafting_skill="gearcrafting", crafting_level=1, tradeable=True,
        )
    }
    gd._crafting_recipes = {}
    return gd


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    return gd


class TestSellInventoryGoal:
    def test_value_zero_when_bank_accessible_and_no_accumulation(self):
        """Bank accessible and item count below accumulation threshold -> value 0."""
        goal = SellInventoryGoal(bank_accessible=True)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        # 4 chickens: below ACCUM_MULT * eff_cap (5*1=5); satisfied (16 free)
        state = make_state(inventory={"chicken": 4}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_no_sellable_items(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"useless_thing": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_satisfied_and_no_accumulation(self):
        """Goal returns 0 when satisfied AND item count is below accumulation threshold."""
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        # 4 chickens: below ACCUM_MULT * eff_cap (5*1=5); satisfied (16 free)
        state = make_state(inventory={"chicken": 4}, inventory_max=20)
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


class TestSellInventoryAccumulation:
    """Task-3: moderate idle-sell when accumulated multiples exceed the ratio cap."""

    def test_value_positive_unpressured_when_accumulated(self):
        """14 wooden_shields → steps=3 → min(18+9, 48) = 27.0 regardless of bank access."""
        gd = _gd_with_buyer()
        # 14 shields; cap=1 (equippable, not dominated); 14 >= 5*1 → accumulates
        # inventory_free = 50 - 14 = 36 >= 5 → is_satisfied = True
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        assert goal.is_satisfied(state) is True
        expected = min(ACCUM_BASE + 3 * ACCUM_STEP, 48.0)  # min(27.0, 48.0) = 27.0
        assert goal.value(state, gd) == expected

    def test_value_zero_when_below_accum_threshold(self):
        """Item count below ACCUM_MULT * cap → no accumulation value (steps=0)."""
        gd = _gd_with_buyer()
        # 4 shields < 5 * 1 = 5 → accumulation_excess returns 0
        state = make_state(level=1, inventory={"wooden_shield": 4}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_satisfied_when_no_accumulation_and_space_free(self):
        """1 shield (at cap) → satisfied and value 0.0."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 1}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_relevant_actions_sell_down_to_cap(self):
        """14 shields → one NpcSellAction for wooden_shield with quantity 13 (sell down to cap=1)."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        acts = goal.relevant_actions([], state, gd)
        sells = [a for a in acts if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
        assert len(sells) == 1
        assert sells[0].quantity == 13

    def test_relevant_actions_no_sell_when_below_threshold(self):
        """4 shields (below threshold) → no accumulation NpcSellAction emitted."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 4}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        acts = goal.relevant_actions([], state, gd)
        sells = [a for a in acts if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
        assert len(sells) == 0

    def test_relevant_actions_no_sell_when_no_location(self):
        """If NPC has no location, no NpcSellAction emitted for that item."""
        gd = GameData()
        gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
        # no _npc_locations entry for "vendor" → npc_location returns None
        gd._item_stats = {
            "wooden_shield": ItemStats(
                code="wooden_shield", level=1, type_="shield",
                crafting_skill="gearcrafting", crafting_level=1, tradeable=True,
            )
        }
        gd._crafting_recipes = {}
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        goal = SellInventoryGoal(bank_accessible=True)
        acts = goal.relevant_actions([], state, gd)
        sells = [a for a in acts if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
        assert len(sells) == 0

    def test_value_zero_when_inventory_max_zero(self):
        """inventory_max == 0 edge case -> value 0.0 (no division by zero)."""
        gd = _gd_with_buyer()
        state = make_state(inventory={}, inventory_max=0)
        goal = SellInventoryGoal(bank_accessible=False)
        assert goal.value(state, gd) == 0.0
