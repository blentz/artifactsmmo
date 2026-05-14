"""Tests to cover remaining uncovered lines: repr, cost, desired_state, edge cases."""

import pytest

from artifactsmmo_cli.ai.actions.bank import DepositAllAction, WithdrawItemAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOT, EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.combat import CompleteTaskGoal, FarmMonsterGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from tests.test_ai.fixtures import make_state


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._monster_locations = kwargs.get("monster_locs", {})
    gd._resource_locations = kwargs.get("resource_locs", {})
    gd._workshop_locations = kwargs.get("workshop_locs", {})
    gd._bank_location = kwargs.get("bank_loc", (4, 0))
    gd._item_stats = kwargs.get("item_stats", {})
    gd._crafting_recipes = kwargs.get("recipes", {})
    gd._resource_skill = kwargs.get("resource_skills", {})
    gd._monster_level = {}
    return gd


class TestReprMethods:
    def test_action_base_repr(self):
        class ConcreteAction(Action):
            def is_applicable(self, s, gd): return True
            def apply(self, s, gd): return s
            def cost(self, s, gd): return 1.0
            def execute(self, s, c): return s
        assert repr(ConcreteAction()) == "ConcreteAction"

    def test_goal_base_repr(self):
        class ConcreteGoal(Goal):
            def value(self, s, gd): return 1.0
            def is_satisfied(self, s): return False
            def desired_state(self, s, gd): return {}
        assert repr(ConcreteGoal()) == "ConcreteGoal"

    def test_restore_hp_repr(self):
        g = RestoreHPGoal()
        assert "RestoreHP" in repr(g)

    def test_deposit_inventory_repr(self):
        assert repr(DepositInventoryGoal()) == "DepositInventory"

    def test_farm_monster_repr(self):
        assert repr(FarmMonsterGoal(monster_code="chicken")) == "FarmMonster(chicken)"

    def test_complete_task_repr(self):
        assert repr(CompleteTaskGoal()) == "CompleteTask"

    def test_upgrade_equipment_repr(self):
        assert repr(UpgradeEquipmentGoal()) == "UpgradeEquipment"

    def test_deposit_all_repr(self):
        assert repr(DepositAllAction()) == "DepositAll"

    def test_withdraw_repr(self):
        assert repr(WithdrawItemAction(code="iron", quantity=3)) == "Withdraw(iron×3)"

    def test_fight_repr(self):
        assert repr(FightAction(monster_code="wolf")) == "Fight(wolf)"

    def test_gather_repr(self):
        assert repr(GatherAction(resource_code="copper")) == "Gather(copper)"

    def test_rest_repr(self):
        assert repr(RestAction()) == "Rest"

    def test_craft_repr(self):
        assert repr(CraftAction(code="sword", quantity=2)) == "Craft(sword×2)"

    def test_equip_repr(self):
        assert repr(EquipAction(code="sword", slot="weapon_slot")) == "Equip(sword->weapon_slot)"


class TestCostMethods:
    def test_deposit_all_cost_scales_with_inventory(self):
        action = DepositAllAction()
        state = make_state(inventory={"a": 1, "b": 2, "c": 3})
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(6.0)

    def test_withdraw_cost(self):
        action = WithdrawItemAction(code="copper", quantity=5)
        state = make_state()
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(2.0)


class TestDesiredStateMethods:
    def test_restore_hp_desired_state(self):
        goal = RestoreHPGoal()
        state = make_state(hp=50, max_hp=150)
        gd = make_gd()
        ds = goal.desired_state(state, gd)
        assert ds == {"hp": 150}

    def test_deposit_inventory_desired_state(self):
        goal = DepositInventoryGoal()
        state = make_state()
        gd = make_gd()
        ds = goal.desired_state(state, gd)
        assert "inventory_free" in ds

    def test_farm_monster_desired_state(self):
        goal = FarmMonsterGoal(monster_code="chicken", initial_xp=50)
        state = make_state(xp=50)
        gd = make_gd()
        ds = goal.desired_state(state, gd)
        assert ds["xp"] > 50

    def test_complete_task_desired_state(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=3)
        gd = make_gd()
        ds = goal.desired_state(state, gd)
        assert ds == {"task_progress": 10}

    def test_upgrade_equipment_desired_state_with_upgrade(self):
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="sword", level=1, type_="weapon")
        state = make_state(inventory={"sword": 1}, level=5)
        gd = make_gd(item_stats={"sword": stats})
        ds = goal.desired_state(state, gd)
        assert "equipment" in ds

    def test_upgrade_equipment_desired_state_no_upgrade(self):
        goal = UpgradeEquipmentGoal()
        state = make_state(inventory={})
        gd = make_gd()
        ds = goal.desired_state(state, gd)
        assert ds == {}

    def test_find_upgrade_target_skips_craftable_item_already_in_inventory(self):
        # Item in inventory AND level too high → _find_inventory_upgrade skips it
        # → _find_craftable_upgrade_target hits line 78 (item in inventory → continue)
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="sword", level=100, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(inventory={"sword": 1}, level=1, skills={"weaponcrafting": 1})
        gd = make_gd(item_stats={"sword": stats}, recipes={"sword": {"copper": 1}})
        assert goal.find_upgrade_target(state, gd) is None

    def test_find_upgrade_target_skips_item_level_too_high(self):
        # stats.level > state.level → skip (line 82)
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="legendary", level=100, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(inventory={}, level=1, skills={"weaponcrafting": 1})
        gd = make_gd(item_stats={"legendary": stats}, recipes={"legendary": {"copper": 1}})
        assert goal.find_upgrade_target(state, gd) is None

    def test_find_upgrade_target_skips_non_equippable_type(self):
        # type_ not in ITEM_TYPE_TO_SLOT → slot is None → skip (line 86)
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="potion", level=1, type_="consumable",
                          crafting_skill="cooking", crafting_level=1)
        state = make_state(inventory={}, level=5, skills={"cooking": 5})
        gd = make_gd(item_stats={"potion": stats}, recipes={"potion": {"herb": 1}})
        assert goal.find_upgrade_target(state, gd) is None

    def test_find_upgrade_target_skips_when_skill_too_low(self):
        # skill level too low → skip (line 89)
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="sword", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=10)
        state = make_state(inventory={}, level=5, skills={"weaponcrafting": 1})
        gd = make_gd(item_stats={"sword": stats}, recipes={"sword": {"copper": 1}})
        assert goal.find_upgrade_target(state, gd) is None

    def test_find_upgrade_target_upgrades_equipped_slot(self):
        # current slot occupied, new item has higher level → return it (lines 95-97)
        goal = UpgradeEquipmentGoal()
        old_stats = ItemStats(code="stick", level=1, type_="weapon")
        new_stats = ItemStats(code="sword", level=5, type_="weapon",
                              crafting_skill="weaponcrafting", crafting_level=1)
        equipment = {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}
        equipment["weapon_slot"] = "stick"
        state = make_state(inventory={}, level=10, equipment=equipment,
                           skills={"weaponcrafting": 5})
        gd = make_gd(item_stats={"stick": old_stats, "sword": new_stats},
                     recipes={"sword": {"copper": 1}})
        result = goal.find_upgrade_target(state, gd)
        assert result == ("sword", "weapon_slot")

    def test_find_upgrade_finds_item_in_bank(self):
        """Regression: item deposited to bank before equip must still trigger UpgradeEquipment."""
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={}, bank_items={"copper_dagger": 1}, level=5)
        gd = make_gd(item_stats={"copper_dagger": stats})
        # Item is in bank — should still be found as an upgrade
        result = goal._find_inventory_upgrade(state, gd)
        assert result == ("copper_dagger", "weapon_slot")

    def test_find_upgrade_target_picks_lowest_crafting_level_not_dict_order(self):
        """Crafting progression must be linear: pick the upgrade with the lowest
        crafting_level so we level the relevant skill before accessing harder recipes.

        copper_boots (crafting_level 5) listed first in dict;
        copper_dagger (crafting_level 1) listed second — dagger must win.
        """
        goal = UpgradeEquipmentGoal()
        boots_stats = ItemStats(code="copper_boots", level=5, type_="boots",
                                crafting_skill="gearcrafting", crafting_level=5)
        dagger_stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(inventory={}, level=10,
                           skills={"weaponcrafting": 5, "gearcrafting": 5})
        gd = make_gd(
            item_stats={"copper_boots": boots_stats, "copper_dagger": dagger_stats},
            recipes={"copper_boots": {"copper_bar": 4}, "copper_dagger": {"copper_ore": 2}},
        )
        result = goal.find_upgrade_target(state, gd)
        assert result is not None
        assert result[0] == "copper_dagger"


class TestIsUpgradeOver:
    """Regression tests for the same-level craftable-beats-starter logic."""

    def _make_goal_and_gd(self, craftable_items: list[str]) -> tuple:
        goal = UpgradeEquipmentGoal()
        stick_stats = ItemStats(code="wooden_stick", level=1, type_="weapon")
        dagger_stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        gd = make_gd(
            item_stats={"wooden_stick": stick_stats, "copper_dagger": dagger_stats},
            recipes={c: {"copper_ore": 6} for c in craftable_items},
        )
        return goal, gd

    def test_craftable_beats_same_level_non_craftable_in_inventory(self):
        """copper_dagger (craftable, level 1) in inventory should upgrade wooden_stick (starter, level 1)."""
        goal, gd = self._make_goal_and_gd(["copper_dagger"])
        equipment = {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}
        equipment["weapon_slot"] = "wooden_stick"
        state = make_state(inventory={"copper_dagger": 1}, level=5, equipment=equipment)
        result = goal._find_inventory_only_upgrade(state, gd)
        assert result == ("copper_dagger", "weapon_slot")

    def test_upgrade_equipment_value_nonzero_with_starter_gear(self):
        """UpgradeEquipment.value() must be >0 when copper_dagger is in inventory vs wooden_stick."""
        goal, gd = self._make_goal_and_gd(["copper_dagger"])
        equipment = {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}
        equipment["weapon_slot"] = "wooden_stick"
        state = make_state(inventory={"copper_dagger": 1}, level=5, equipment=equipment)
        assert goal.value(state, gd) > 0.0

    def test_upgrade_equipment_priority_60_with_inventory_starter_upgrade(self):
        """Priority must be 60 (immediate equip) when craftable replaces starter gear in inventory."""
        goal, gd = self._make_goal_and_gd(["copper_dagger"])
        equipment = {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}
        equipment["weapon_slot"] = "wooden_stick"
        state = make_state(inventory={"copper_dagger": 1}, level=5, equipment=equipment)
        assert goal.priority(state, gd) == 60.0

    def test_non_craftable_does_not_beat_same_level_non_craftable(self):
        """Two non-craftable items at same level: no upgrade."""
        goal = UpgradeEquipmentGoal()
        stick_stats = ItemStats(code="wooden_stick", level=1, type_="weapon")
        stick2_stats = ItemStats(code="other_stick", level=1, type_="weapon")
        gd = make_gd(item_stats={"wooden_stick": stick_stats, "other_stick": stick2_stats}, recipes={})
        equipment = {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}
        equipment["weapon_slot"] = "wooden_stick"
        state = make_state(inventory={"other_stick": 1}, level=5, equipment=equipment)
        assert goal._find_inventory_only_upgrade(state, gd) is None

    def test_is_upgrade_over_higher_level_wins_regardless(self):
        """Higher level always beats lower level (basic sanity check)."""
        goal = UpgradeEquipmentGoal()
        new_stats = ItemStats(code="iron_sword", level=5, type_="weapon")
        old_stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        gd = make_gd(item_stats={"iron_sword": new_stats, "copper_dagger": old_stats}, recipes={})
        assert goal._is_upgrade_over("iron_sword", new_stats, "copper_dagger", old_stats, gd) is True

    def test_is_upgrade_over_empty_slot(self):
        """Any item upgrades an empty slot."""
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        gd = make_gd(item_stats={"copper_dagger": stats})
        assert goal._is_upgrade_over("copper_dagger", stats, None, None, gd) is True


class TestEdgeCases:
    def test_farm_monster_goal_value_zero_max_xp(self):
        goal = FarmMonsterGoal(monster_code="chicken")
        state = make_state(xp=0, max_xp=0)
        gd = make_gd()
        val = goal.value(state, gd)
        assert val == pytest.approx(30.0)

    def test_withdraw_not_applicable_when_bank_items_none(self):
        action = WithdrawItemAction(code="copper", quantity=1)
        state = make_state(x=4, y=0, bank_items=None)
        gd = make_gd(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is False

    def test_withdraw_apply_removes_item_when_quantity_exact(self):
        action = WithdrawItemAction(code="copper", quantity=5)
        state = make_state(x=4, y=0, inventory={}, bank_items={"copper": 5})
        gd = make_gd(bank_loc=(4, 0))
        new_state = action.apply(state, gd)
        assert "copper" not in (new_state.bank_items or {})

    def test_craft_not_applicable_when_no_workshop_location(self):
        # workshop_location=None is caught before checking stats
        action = CraftAction(code="unknown_item", workshop_location=None)
        state = make_state(x=5, y=0)
        gd = make_gd()
        assert action.is_applicable(state, gd) is False

    def test_craft_not_applicable_when_no_stats(self):
        # Has workshop location but item stats missing
        action = CraftAction(code="unknown_item", workshop_location=(5, 0))
        state = make_state(x=5, y=0)
        gd = make_gd()
        assert action.is_applicable(state, gd) is False

    def test_craft_not_applicable_when_no_recipe(self):
        action = CraftAction(code="sword", workshop_location=(5, 0))
        stats = ItemStats(code="sword", level=1, type_="weapon", crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(x=5, y=0, skills={"weaponcrafting": 5}, inventory={"copper": 6})
        gd = make_gd(
            workshop_locs={"weaponcrafting": (5, 0)},
            item_stats={"sword": stats},
            recipes={},  # no recipe
        )
        assert action.is_applicable(state, gd) is False

    def test_equip_not_applicable_when_item_not_in_inventory(self):
        action = EquipAction(code="sword", slot="weapon_slot")
        stats = ItemStats(code="sword", level=1, type_="weapon")
        state = make_state(inventory={}, level=5)
        gd = make_gd(item_stats={"sword": stats})
        assert action.is_applicable(state, gd) is False

    def test_equip_not_applicable_when_no_stats(self):
        action = EquipAction(code="unknown", slot="weapon_slot")
        state = make_state(inventory={"unknown": 1}, level=5)
        gd = make_gd()
        assert action.is_applicable(state, gd) is False

    def test_gather_applicable_when_no_skill_required(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(3, 0)]))
        state = make_state(x=0, y=0, inventory={}, inventory_max=10)
        gd = make_gd(resource_locs={"copper": [(3, 0)]})  # no skill req
        assert action.is_applicable(state, gd) is True

    def test_deposit_inventory_zero_max_returns_zero(self):
        goal = DepositInventoryGoal()
        state = make_state(inventory_max=0)
        gd = make_gd()
        assert goal.value(state, gd) == 0.0
