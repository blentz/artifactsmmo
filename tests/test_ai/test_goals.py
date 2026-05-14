"""Tests for GOAP goals — pure value() and is_satisfied() functions."""

from artifactsmmo_cli.ai.actions.bank import DepositAllAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal, FarmMonsterGoal
from artifactsmmo_cli.ai.goals.farm_items import FarmItemsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from tests.test_ai.fixtures import make_state


def make_game_data(item_stats=None) -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = item_stats or {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {}
    return gd


class TestRestoreHPGoal:
    def test_value_full_hp_is_zero(self):
        goal = RestoreHPGoal()
        state = make_state(hp=150, max_hp=150)
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_half_hp_is_50(self):
        goal = RestoreHPGoal()
        state = make_state(hp=75, max_hp=150)
        assert abs(goal.value(state, make_game_data()) - 50.0) < 0.1

    def test_value_zero_hp_is_100(self):
        goal = RestoreHPGoal()
        state = make_state(hp=0, max_hp=150)
        assert abs(goal.value(state, make_game_data()) - 100.0) < 0.1

    def test_satisfied_at_full_hp(self):
        goal = RestoreHPGoal()
        state = make_state(hp=150, max_hp=150)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_below_max(self):
        goal = RestoreHPGoal()
        state = make_state(hp=149, max_hp=150)
        assert goal.is_satisfied(state) is False


class TestDepositInventoryGoal:
    def test_value_empty_inventory_is_zero(self):
        goal = DepositInventoryGoal()
        state = make_state(inventory={}, inventory_max=20)
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_full_inventory_is_80(self):
        goal = DepositInventoryGoal()
        inventory = {f"item_{i}": 1 for i in range(20)}
        state = make_state(inventory=inventory, inventory_max=20)
        assert abs(goal.value(state, make_game_data()) - 80.0) < 0.1

    def test_satisfied_with_enough_free_slots(self):
        goal = DepositInventoryGoal()
        state = make_state(inventory={"item1": 1}, inventory_max=20)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_nearly_full(self):
        goal = DepositInventoryGoal()
        inventory = {f"item_{i}": 1 for i in range(17)}
        state = make_state(inventory=inventory, inventory_max=20)
        assert goal.is_satisfied(state) is False


class TestCompleteTaskGoal:
    def test_no_task_value_is_zero(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code=None, task_total=0, task_progress=0)
        assert goal.value(state, make_game_data()) == 0.0

    def test_task_at_zero_progress_value(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=0)
        assert abs(goal.value(state, make_game_data()) - 50.0) < 0.1

    def test_task_at_full_progress_value(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=10)
        assert abs(goal.value(state, make_game_data()) - 90.0) < 0.1

    def test_satisfied_when_complete(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=10)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_in_progress(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=5)
        assert goal.is_satisfied(state) is False


class TestFarmMonsterGoal:
    def test_not_satisfied_at_initial_xp(self):
        goal = FarmMonsterGoal(monster_code="chicken", initial_xp=100)
        state = make_state(xp=100, max_xp=1000)
        assert goal.is_satisfied(state) is False

    def test_satisfied_when_xp_increases(self):
        goal = FarmMonsterGoal(monster_code="chicken", initial_xp=100)
        state = make_state(xp=101, max_xp=1000)
        assert goal.is_satisfied(state) is True

    def test_default_initial_xp_zero(self):
        goal = FarmMonsterGoal(monster_code="chicken")
        state = make_state(xp=0, max_xp=1000)
        assert goal.is_satisfied(state) is False

    def test_value_increases_with_xp(self):
        goal = FarmMonsterGoal(monster_code="chicken")
        state_low = make_state(xp=0, max_xp=100)
        state_high = make_state(xp=99, max_xp=100)
        assert goal.value(state_high, make_game_data()) > goal.value(state_low, make_game_data())

    def test_priority_defaults_to_value(self):
        goal = FarmMonsterGoal(monster_code="chicken")
        state = make_state(xp=50, max_xp=100, level=1)
        gd = make_game_data()
        gd._monster_level = {"chicken": 1}
        assert goal.priority(state, gd) == goal.value(state, gd)


def _make_equipment(**overrides):
    slots = {k: None for k in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                                "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                                "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]}
    slots.update(overrides)
    return slots


class TestUpgradeEquipmentGoal:
    def test_value_35_when_upgrade_available(self):
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        assert goal.value(state, gd) == 35.0

    def test_value_zero_when_no_upgrade(self):
        goal = UpgradeEquipmentGoal()
        state = make_state(inventory={})
        gd = make_game_data()
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_item_better_already_equipped(self):
        goal = UpgradeEquipmentGoal()
        old_stats = ItemStats(code="iron_sword", level=10, type_="weapon")
        new_stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        equipment = _make_equipment(weapon_slot="iron_sword")
        state = make_state(inventory={"copper_dagger": 1}, level=10, equipment=equipment)
        gd = make_game_data(item_stats={"iron_sword": old_stats, "copper_dagger": new_stats})
        assert goal.value(state, gd) == 0.0

    def test_not_satisfied_when_no_equipment_change(self):
        equipment = _make_equipment(weapon_slot="copper_dagger")
        goal = UpgradeEquipmentGoal(initial_equipment=equipment)
        state = make_state(equipment=equipment)
        assert goal.is_satisfied(state) is False

    def test_satisfied_when_new_item_equipped(self):
        initial = _make_equipment()
        goal = UpgradeEquipmentGoal(initial_equipment=initial)
        new_equipment = _make_equipment(weapon_slot="copper_dagger")
        state = make_state(equipment=new_equipment)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_with_no_initial_equipment(self):
        goal = UpgradeEquipmentGoal()
        state = make_state(equipment=_make_equipment())
        assert goal.is_satisfied(state) is False

    def test_value_35_when_craftable_upgrade_available(self):
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        state = make_state(inventory={}, level=5, skills={"weaponcrafting": 1},
                           bank_items={"copper_ore": 6})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 35.0

    def test_value_zero_when_materials_unavailable(self):
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        # No copper_ore → upgrade not immediately possible → GatherMaterials drives this
        state = make_state(inventory={}, level=5, skills={"weaponcrafting": 1}, bank_items={})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 0.0

    def test_craftable_upgrade_uses_inventory_materials(self):
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        # Materials in inventory (not bank)
        state = make_state(inventory={"copper_ore": 6}, level=5, skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 35.0

    def test_craftable_upgrade_skipped_when_skill_too_low(self):
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=10,
        )
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        state = make_state(inventory={}, level=5, skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 0.0

    def test_craftable_upgrade_skipped_when_in_inventory_but_not_better(self):
        # copper_dagger (level 1) is in inventory AND recipes, but iron_sword (level 5) is equipped.
        # _find_inventory_upgrade returns None (copper_dagger is inferior to iron_sword).
        # _find_craftable_upgrade then sees copper_dagger in recipes → item is in inventory → continue.
        dagger_stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1)
        sword_stats = ItemStats(code="iron_sword", level=5, type_="weapon")
        equipment = _make_equipment(weapon_slot="iron_sword")
        gd = make_game_data(item_stats={"copper_dagger": dagger_stats, "iron_sword": sword_stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        state = make_state(inventory={"copper_dagger": 1}, level=5, equipment=equipment,
                           skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 0.0

    def test_craftable_upgrade_skipped_when_level_too_high(self):
        stats = ItemStats(
            code="legendary_sword", level=50, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd = make_game_data(item_stats={"legendary_sword": stats})
        gd._crafting_recipes = {"legendary_sword": {"iron_ore": 10}}
        state = make_state(inventory={}, level=5, skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 0.0

    def test_craftable_upgrade_skipped_when_non_gear_type(self):
        stats = ItemStats(
            code="potion", level=1, type_="consumable",
            crafting_skill="cooking", crafting_level=1,
        )
        gd = make_game_data(item_stats={"potion": stats})
        gd._crafting_recipes = {"potion": {"fish": 2}}
        state = make_state(inventory={}, level=5, skills={"cooking": 5})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 0.0

    def test_craftable_upgrade_beats_equipped_item(self):
        old_stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        new_stats = ItemStats(
            code="iron_sword", level=5, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        equipment = _make_equipment(weapon_slot="copper_dagger")
        gd = make_game_data(item_stats={"copper_dagger": old_stats, "iron_sword": new_stats})
        gd._crafting_recipes = {"iron_sword": {"iron_ore": 6}}
        state = make_state(inventory={}, level=5, equipment=equipment, skills={"weaponcrafting": 5},
                           bank_items={"iron_ore": 6})
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 35.0


class TestUpgradeEquipmentGoalPriority:
    def test_priority_60_when_upgrade_in_inventory(self):
        """Regression: upgrade in inventory must have priority > GatherMaterials (50)
        so the bot equips before resuming gathering."""
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        assert goal.priority(state, gd) == 60.0

    def test_priority_35_when_upgrade_only_in_bank(self):
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={}, bank_items={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        assert goal.priority(state, gd) == 35.0

    def test_priority_35_for_craftable_upgrade_with_materials(self):
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        state = make_state(inventory={}, bank_items={"copper_ore": 6}, level=5,
                           skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        assert goal.priority(state, gd) == 35.0

    def test_priority_zero_when_no_upgrade(self):
        goal = UpgradeEquipmentGoal()
        state = make_state(inventory={}, bank_items={})
        gd = make_game_data()
        assert goal.priority(state, gd) == 0.0


class TestFarmMonsterGoalEquipmentGate:
    def test_value_zero_when_under_equipped(self):
        gd = make_game_data()
        gd._monster_level = {"green_slime": 5}
        # No equipment → best_equipped_level = 0, monster_level = 5, 0 < 5-1 → blocked
        state = make_state(xp=0, max_xp=1000)
        goal = FarmMonsterGoal(monster_code="green_slime")
        assert goal.value(state, gd) == 0.0

    def test_value_nonzero_when_equipped_enough(self):
        sword_stats = ItemStats(code="iron_sword", level=4, type_="weapon")
        gd = make_game_data(item_stats={"iron_sword": sword_stats})
        gd._monster_level = {"green_slime": 5}
        equipment = _make_equipment(weapon_slot="iron_sword")
        # best_equipped_level = 4, monster_level = 5, 4 >= 5-1 → allowed
        state = make_state(xp=0, max_xp=1000, equipment=equipment)
        goal = FarmMonsterGoal(monster_code="green_slime")
        assert goal.value(state, gd) > 0.0


class TestGatherMaterialsGoal:
    def test_value_40_when_materials_needed(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={}, bank_items={})
        assert goal.value(state, make_game_data()) == 40.0

    def test_value_zero_when_satisfied(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 6}, bank_items={})
        assert goal.value(state, make_game_data()) == 0.0

    def test_satisfied_with_bank_materials(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={}, bank_items={"copper_ore": 6})
        assert goal.is_satisfied(state) is True

    def test_satisfied_with_mixed_inventory_and_bank(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 3}, bank_items={"copper_ore": 3})
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_short(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 5}, bank_items={})
        assert goal.is_satisfied(state) is False

    def test_desired_state_returns_needed(self):
        needed = {"copper_ore": 6}
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed=needed)
        state = make_state()
        assert goal.desired_state(state, make_game_data()) == {"inventory": needed}

    def test_repr(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        assert repr(goal) == "GatherMaterials(copper_dagger)"

    def test_value_gradient_with_partial_collection(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 3}, bank_items={})
        value = goal.value(state, make_game_data())
        assert 1.0 <= value < 40.0

    def test_value_counts_intermediate_materials(self):
        # If copper_bar needs 2 copper_ore and we have 4 copper_ore, 2 bars are craftable
        gd = make_game_data()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 2}}
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 2})
        state = make_state(inventory={"copper_ore": 4}, bank_items={})
        value = goal.value(state, gd)
        assert value == 1.0  # fully covered by intermediates → min value 1.0

    def test_relevant_actions_includes_direct_gather(self):
        gd = make_game_data()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        goal = GatherMaterialsGoal(target_item="sword", needed={"copper_ore": 6})
        state = make_state()
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])),
            GatherAction(resource_code="ash_tree", locations=frozenset([(5, 0)])),
            FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(4, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Gather(copper_rocks)" in repr_set
        assert "Rest" in repr_set
        assert "DepositAll" in repr_set
        assert "Gather(ash_tree)" not in repr_set
        assert "Fight(chicken)" not in repr_set

    def test_relevant_actions_includes_intermediate_craft_and_gather(self):
        # copper_boots needs copper (bars); copper needs copper_ore; copper_rocks drops copper_ore
        gd = make_game_data()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._crafting_recipes = {"copper": {"copper_ore": 8}}
        gd._workshop_locations = {"mining": (3, 0)}
        stats = ItemStats(code="copper", level=1, type_="resource",
                          crafting_skill="mining", crafting_level=1)
        gd._item_stats = {"copper": stats}
        goal = GatherMaterialsGoal(target_item="copper_boots", needed={"copper": 4})
        state = make_state()
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])),
            GatherAction(resource_code="ash_tree", locations=frozenset([(5, 0)])),
            CraftAction(code="copper", quantity=1, workshop_location=(3, 0)),
            CraftAction(code="iron_bar", quantity=1, workshop_location=(3, 0)),
            FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(4, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Gather(copper_rocks)" in repr_set
        assert "Craft(copper×1)" in repr_set
        assert "Rest" in repr_set
        assert "DepositAll" in repr_set
        assert "Gather(ash_tree)" not in repr_set
        assert "Craft(iron_bar×1)" not in repr_set
        assert "Fight(chicken)" not in repr_set

    def test_relevant_actions_handles_three_level_chain(self):
        # Mirrors the real game pattern: greater_X -> X -> plank -> raw_wood
        # staff needs plank (crafted from wood); wood is a resource drop.
        gd = make_game_data()
        gd._resource_drops = {"wood_grove": "raw_wood"}
        gd._crafting_recipes = {
            "plank": {"raw_wood": 4},
            "staff": {"plank": 6, "gem": 1},
        }
        gd._workshop_locations = {"woodcutting": (3, 0), "weaponcrafting": (4, 0)}
        gd._item_stats = {
            "plank": ItemStats(code="plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
            "staff": ItemStats(code="staff", level=5, type_="weapon",
                               crafting_skill="weaponcrafting", crafting_level=1),
        }
        goal = GatherMaterialsGoal(target_item="greater_staff", needed={"staff": 1})
        state = make_state()
        actions = [
            GatherAction(resource_code="wood_grove", locations=frozenset([(1, 0)])),
            GatherAction(resource_code="gem_mine", locations=frozenset([(2, 0)])),
            CraftAction(code="plank", quantity=1, workshop_location=(3, 0)),
            CraftAction(code="staff", quantity=1, workshop_location=(4, 0)),
            CraftAction(code="iron_bar", quantity=1, workshop_location=(4, 0)),
            FightAction(monster_code="chicken", locations=frozenset([(5, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(6, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Gather(wood_grove)" in repr_set      # 3 levels deep: staff->plank->raw_wood
        assert "Craft(plank×1)" in repr_set           # intermediate craft
        assert "Craft(staff×1)" in repr_set           # top-level craft
        assert "Rest" in repr_set
        assert "DepositAll" in repr_set
        assert "Craft(iron_bar×1)" not in repr_set    # unrelated craft excluded
        assert "Fight(chicken)" not in repr_set

    def test_relevant_actions_when_no_resource_drops_mapped(self):
        gd = make_game_data()
        # No _resource_drops, no recipes → only Rest and Deposit kept
        goal = GatherMaterialsGoal(target_item="sword", needed={"copper_ore": 6})
        state = make_state()
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])),
            FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(4, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Rest" in repr_set
        assert "DepositAll" in repr_set
        assert "Gather(copper_rocks)" not in repr_set
        assert "Fight(chicken)" not in repr_set

    def test_max_depth_scales_with_needed_quantity(self):
        assert GatherMaterialsGoal(target_item="x", needed={"copper_bar": 6}).max_depth == 600
        assert GatherMaterialsGoal(target_item="x", needed={"a": 1}).max_depth == 100
        assert GatherMaterialsGoal(target_item="x", needed={"a": 2, "b": 3}).max_depth == 500

    def test_priority_is_fixed_50_when_not_satisfied(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={}, bank_items={})
        assert goal.priority(state, make_game_data()) == 50.0

    def test_priority_is_50_regardless_of_partial_progress(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 5}, bank_items={})
        assert goal.priority(state, make_game_data()) == 50.0

    def test_priority_is_zero_when_satisfied(self):
        goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_ore": 6})
        state = make_state(inventory={"copper_ore": 6}, bank_items={})
        assert goal.priority(state, make_game_data()) == 0.0

    def test_priority_exceeds_farm_monster_max(self):
        # FarmMonsterGoal max value is 30 + 20 = 50.0; GatherMaterials must stay above that
        goal = GatherMaterialsGoal(target_item="x", needed={"copper_ore": 1})
        state = make_state(inventory={}, bank_items={})
        farm_monster_max = 50.0
        assert goal.priority(state, make_game_data()) >= farm_monster_max


class TestAcceptTaskGoal:
    def test_value_20_when_no_task(self):
        goal = AcceptTaskGoal()
        state = make_state(task_code="", task_total=0)
        assert goal.value(state, make_game_data()) == 20.0

    def test_value_zero_when_task_active(self):
        goal = AcceptTaskGoal()
        state = make_state(task_code="chicken", task_total=10)
        assert goal.value(state, make_game_data()) == 0.0

    def test_satisfied_when_task_code_set(self):
        goal = AcceptTaskGoal()
        state = make_state(task_code="chicken")
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_empty(self):
        goal = AcceptTaskGoal()
        state = make_state(task_code="")
        assert goal.is_satisfied(state) is False

    def test_desired_state_is_pending(self):
        goal = AcceptTaskGoal()
        state = make_state()
        assert goal.desired_state(state, make_game_data()) == {"task_code": "__pending__"}

    def test_repr(self):
        assert repr(AcceptTaskGoal()) == "AcceptTask"


class TestFarmItemsGoal:
    def test_value_nonzero_when_items_task_active(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=0)
        assert goal.value(state, make_game_data()) > 0.0

    def test_value_zero_when_no_task(self):
        goal = FarmItemsGoal()
        state = make_state(task_code="", task_total=0)
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_zero_for_monsters_task(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="monsters", task_code="chicken", task_total=10, task_progress=0)
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_zero_when_satisfied(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=10)
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_scales_with_remaining_fraction(self):
        goal = FarmItemsGoal()
        state_half = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=5)
        state_full = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=0)
        assert goal.value(state_half, make_game_data()) < goal.value(state_full, make_game_data())

    def test_is_satisfied_when_progress_equals_total(self):
        goal = FarmItemsGoal()
        state = make_state(task_total=5, task_progress=5)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_progress_below_total(self):
        goal = FarmItemsGoal()
        state = make_state(task_total=5, task_progress=4)
        assert goal.is_satisfied(state) is False

    def test_not_satisfied_when_no_task(self):
        goal = FarmItemsGoal()
        state = make_state(task_total=0, task_progress=0)
        assert goal.is_satisfied(state) is False

    def test_desired_state_returns_task_total(self):
        goal = FarmItemsGoal()
        state = make_state(task_total=10, task_progress=3)
        assert goal.desired_state(state, make_game_data()) == {"task_progress": 10}

    def test_priority_fixed_28_when_not_satisfied(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=0)
        assert goal.priority(state, make_game_data()) == 28.0

    def test_priority_zero_when_satisfied(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=10)
        assert goal.priority(state, make_game_data()) == 0.0

    def test_relevant_actions_includes_task_item_gather(self):
        gd = make_game_data()
        gd._resource_drops = {"ash_tree": "ash_wood"}
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=5, task_progress=0)
        actions = [
            GatherAction(resource_code="ash_tree", locations=frozenset([(2, 0)])),
            GatherAction(resource_code="copper_rocks", locations=frozenset([(3, 0)])),
            FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(4, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Gather(ash_tree)" in repr_set
        assert "Rest" in repr_set
        assert "DepositAll" in repr_set
        assert "Gather(copper_rocks)" not in repr_set
        assert "Fight(chicken)" not in repr_set

    def test_relevant_actions_includes_craft_chain_for_crafted_task_item(self):
        gd = make_game_data()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 8}}
        gd._workshop_locations = {"mining": (3, 0)}
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="mining", crafting_level=1),
        }
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="copper_bar", task_total=3, task_progress=0)
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])),
            CraftAction(code="copper_bar", quantity=1, workshop_location=(3, 0)),
            CraftAction(code="iron_bar", quantity=1, workshop_location=(3, 0)),
            FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
            RestAction(),
            DepositAllAction(bank_location=(4, 0)),
        ]
        result = goal.relevant_actions(actions, state, gd)
        repr_set = {repr(a) for a in result}
        assert "Gather(copper_rocks)" in repr_set
        assert "Craft(copper_bar×1)" in repr_set
        assert "Craft(iron_bar×1)" not in repr_set
        assert "Fight(chicken)" not in repr_set

    def test_relevant_actions_empty_when_no_task_code(self):
        goal = FarmItemsGoal()
        state = make_state(task_code="", task_total=5, task_progress=0)
        actions = [RestAction(), GatherAction(resource_code="ash_tree", locations=frozenset([(2, 0)]))]
        result = goal.relevant_actions(actions, state, make_game_data())
        assert result == []

    def test_repr(self):
        assert repr(FarmItemsGoal()) == "FarmItems"


class TestTaskExchangeGoal:
    def test_value_22_when_coins_in_inventory(self):
        goal = TaskExchangeGoal()
        state = make_state(inventory={"tasks_coin": 3})
        assert goal.value(state, make_game_data()) == 22.0

    def test_value_22_when_coins_in_bank(self):
        goal = TaskExchangeGoal()
        state = make_state(bank_items={"tasks_coin": 1})
        assert goal.value(state, make_game_data()) == 22.0

    def test_value_zero_when_no_coins(self):
        goal = TaskExchangeGoal()
        state = make_state(inventory={}, bank_items={})
        assert goal.value(state, make_game_data()) == 0.0

    def test_satisfied_when_no_coins(self):
        goal = TaskExchangeGoal()
        state = make_state(inventory={}, bank_items={})
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_coins_in_inventory(self):
        goal = TaskExchangeGoal()
        state = make_state(inventory={"tasks_coin": 1})
        assert goal.is_satisfied(state) is False

    def test_not_satisfied_when_coins_in_bank(self):
        goal = TaskExchangeGoal()
        state = make_state(bank_items={"tasks_coin": 5})
        assert goal.is_satisfied(state) is False

    def test_desired_state(self):
        goal = TaskExchangeGoal()
        state = make_state()
        assert goal.desired_state(state, make_game_data()) == {"inventory": {"tasks_coin": 0}}

    def test_repr(self):
        assert repr(TaskExchangeGoal()) == "TaskExchange"
