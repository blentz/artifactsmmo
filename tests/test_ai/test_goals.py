"""Tests for GOAP goals — pure value() and is_satisfied() functions."""

import os
import tempfile

from artifactsmmo_cli.ai.actions.bank import DepositAllAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal, FarmMonsterGoal
from artifactsmmo_cli.ai.goals.farm_items import FarmItemsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
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

    def test_value_zero_hp_is_critical_floor(self):
        """Below CRITICAL_HP_FRACTION, value jumps to CRITICAL_HP_VALUE so the
        goal dominates UnlockBank(90) etc and preempts combat."""
        goal = RestoreHPGoal()
        state = make_state(hp=0, max_hp=150)
        assert goal.value(state, make_game_data()) == RestoreHPGoal.CRITICAL_HP_VALUE

    def test_satisfied_at_full_hp(self):
        goal = RestoreHPGoal()
        state = make_state(hp=150, max_hp=150)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_below_max(self):
        goal = RestoreHPGoal()
        state = make_state(hp=149, max_hp=150)
        assert goal.is_satisfied(state) is False


class TestDepositInventoryGoal:
    # Bankable generic items: a game_data with no recipes/consumables/weapons so
    # every "item_N" is bankable (not in the keep-set), letting the fill-driven
    # value ramp be exercised directly.
    def _gd(self):
        return make_game_data()

    def test_value_empty_inventory_is_zero(self):
        goal = DepositInventoryGoal(game_data=self._gd())
        state = make_state(inventory={}, inventory_max=20)
        assert goal.value(state, self._gd()) == 0.0

    def test_value_full_inventory_is_80(self):
        goal = DepositInventoryGoal(game_data=self._gd())
        inventory = {f"item_{i}": 1 for i in range(20)}
        state = make_state(inventory=inventory, inventory_max=20)
        assert abs(goal.value(state, self._gd()) - 80.0) < 0.1

    def test_satisfied_when_nothing_bankable(self):
        # Only kept items (task coins) remain → nothing to bank → satisfied.
        goal = DepositInventoryGoal(game_data=self._gd())
        state = make_state(inventory={"tasks_coin": 3}, inventory_max=20)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_bankable_items_present(self):
        goal = DepositInventoryGoal(game_data=self._gd())
        inventory = {f"item_{i}": 1 for i in range(17)}
        state = make_state(inventory=inventory, inventory_max=20)
        assert goal.is_satisfied(state) is False

    def test_value_returns_zero_when_below_ramp_start(self):
        """No urgency to deposit while inventory is below 50% used."""
        goal = DepositInventoryGoal(game_data=self._gd())
        # 8/20 used = 40% — below 50% ramp start. value should be 0.
        inventory = {f"item_{i}": 1 for i in range(8)}
        state = make_state(inventory=inventory, inventory_max=20)
        assert goal.value(state, self._gd()) == 0.0

    def test_value_ramps_from_50_to_100_percent_used(self):
        """At 75% used the value should sit between 0 and the max (80)."""
        goal = DepositInventoryGoal(game_data=self._gd())
        inventory = {f"item_{i}": 1 for i in range(15)}  # 15/20 = 75%
        state = make_state(inventory=inventory, inventory_max=20)
        v = goal.value(state, self._gd())
        assert 35.0 < v < 50.0  # halfway up the ramp ≈ 40

    def test_satisfied_when_only_kept_items_remain(self):
        """No fixed-fraction rule: satisfaction is purely 'nothing bankable'."""
        goal = DepositInventoryGoal(game_data=self._gd())
        state = make_state(inventory={"tasks_coin": 1}, inventory_max=20,
                           task_code="copper_ore")  # copper_ore not in bag → no bankable
        assert goal.is_satisfied(state) is True


class TestCompleteTaskGoal:
    def test_no_task_value_is_zero(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code=None, task_total=0, task_progress=0)
        assert goal.value(state, make_game_data()) == 0.0

    def test_task_at_zero_progress_value(self):
        # An in-flight task with no progress yet is not yet turn-in-able,
        # so CompleteTaskGoal should stay out of the way (value 0). Other
        # goals (FarmItems/FarmMonster) drive progress.
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=0)
        assert goal.value(state, make_game_data()) == 0.0

    def test_task_at_full_progress_value(self):
        goal = CompleteTaskGoal()
        state = make_state(task_code="chicken", task_total=10, task_progress=10)
        assert abs(goal.value(state, make_game_data()) - 90.0) < 0.1

    def test_satisfied_when_task_already_turned_in(self):
        # Goal models "no task held". The full-progress state still HAS
        # a task — turn-in hasn't happened yet — so not satisfied.
        goal = CompleteTaskGoal()
        full_state = make_state(task_code="chicken", task_total=10, task_progress=10)
        assert goal.is_satisfied(full_state) is False
        cleared_state = make_state(task_code=None, task_total=0, task_progress=0)
        assert goal.is_satisfied(cleared_state) is True

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

    def test_relevant_actions_filters_fights_by_monster_code(self):
        """FarmMonster(chicken) must NOT expose Fight(yellow_slime) to the planner.

        Regression: prior behaviour returned every FightAction, letting the
        planner pick a cheaper-cost different monster and walk Robby into
        a one-shot loss loop.
        """
        from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
        from artifactsmmo_cli.ai.actions.gathering import GatherAction

        goal = FarmMonsterGoal(monster_code="chicken")
        state = make_state()
        gd = make_game_data()
        actions = [
            FightAction(monster_code="chicken", locations=frozenset({(0, 1)})),
            FightAction(monster_code="yellow_slime", locations=frozenset({(4, -1)})),
            RestAction(),
            UseConsumableAction(_item_stats={}),
            GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 2)})),
        ]
        kept = goal.relevant_actions(actions, state, gd)
        names = [repr(a) for a in kept]
        assert any("Fight(chicken)" in n for n in names)
        assert not any("Fight(yellow_slime)" in n for n in names)
        assert any(isinstance(a, RestAction) for a in kept)
        assert any(isinstance(a, UseConsumableAction) for a in kept)
        assert not any(isinstance(a, GatherAction) for a in kept)


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


class TestUpgradeEquipmentGoalToolBias:
    """A craftable upgrade whose stats bonus an active gathering skill must
    outrank generic gear and bump value() above FarmItems (35)."""

    def test_value_50_when_craftable_tool_matches_active_skill(self):
        # Active task = ash_plank → walks recipe ash_plank ← ash_wood ← ash_tree
        # → woodcutting is active.
        axe = ItemStats(
            code="copper_axe", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
            skill_effects={"woodcutting": -1},
        )
        gd = make_game_data(item_stats={"copper_axe": axe})
        gd._crafting_recipes = {
            "copper_axe": {"copper_ore": 6},
            "ash_plank": {"ash_wood": 1},
        }
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
        state = make_state(
            inventory={}, level=5, skills={"weaponcrafting": 1},
            bank_items={"copper_ore": 6},
            task_code="ash_plank", task_type="items", task_total=10, task_progress=0,
        )
        goal = UpgradeEquipmentGoal()
        assert goal.value(state, gd) == 51.0

    def test_crafting_target_makes_mining_tool_relevant(self):
        """Self-directed copper-gear crafting (no mining task) marks mining
        active via crafting_target, so the pickaxe is picked over a higher-value
        generic weapon. Without the target it is not — proving the new signal."""
        dagger = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
            attack={"fire": 10},  # higher raw value → wins when mining inactive
        )
        pickaxe = ItemStats(
            code="copper_pickaxe", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
            skill_effects={"mining": -1},
        )
        gd = make_game_data(item_stats={"copper_dagger": dagger, "copper_pickaxe": pickaxe})
        gd._crafting_recipes = {
            "copper_dagger": {"copper_ore": 6},
            "copper_pickaxe": {"copper_ore": 6},
            "copper_bar": {"copper_ore": 10},  # the crafting target's chain → mining
        }
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        base = dict(
            inventory={}, level=5, skills={"weaponcrafting": 1},
            bank_items={"copper_ore": 12},  # both craftable; empty weapon slot
        )
        goal = UpgradeEquipmentGoal()

        # No task, no crafting target → mining inactive → higher-value dagger wins.
        no_target = make_state(task_code=None, crafting_target=None, **base)
        assert goal._find_craftable_upgrade_target(no_target, gd)[0] == "copper_dagger"

        # Crafting copper gear (copper_bar chain → mining) → pickaxe wins.
        mining = make_state(task_code=None, crafting_target="copper_bar", **base)
        assert goal._find_craftable_upgrade_target(mining, gd)[0] == "copper_pickaxe"

    def test_relevant_tool_beats_lower_level_generic_craftable(self):
        # Lower craft_level (dagger=1) would normally win; the axe (level 2) has
        # the relevant skill bonus and should still be picked.
        dagger = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        axe = ItemStats(
            code="copper_axe", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=2,
            skill_effects={"woodcutting": -1},
        )
        gd = make_game_data(item_stats={"copper_dagger": dagger, "copper_axe": axe})
        gd._crafting_recipes = {
            "copper_dagger": {"copper_ore": 6},
            "copper_axe": {"copper_ore": 6},
            "ash_plank": {"ash_wood": 1},
        }
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
        state = make_state(
            inventory={}, level=5, skills={"weaponcrafting": 2},
            bank_items={"copper_ore": 12},
            task_code="ash_plank", task_type="items", task_total=10, task_progress=0,
        )
        goal = UpgradeEquipmentGoal()
        upgrade = goal._find_craftable_upgrade(state, make_game_data_with(gd))
        assert upgrade is not None
        assert upgrade[0] == "copper_axe"


def make_game_data_with(gd):
    """Pass-through so we don't accidentally re-create gd."""
    return gd


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

    def test_relevant_actions_excludes_unequip_and_downgrade_equips(self):
        """Regression: is_satisfied fires when any slot differs from the initial
        snapshot, so the planner could 'upgrade' by equipping a worse item
        (copper_axe → fishing_net, both owned) since that also makes the slot
        differ. relevant_actions must drop UnequipActions and every EquipAction
        except the one for the current upgrade target."""
        from artifactsmmo_cli.ai.actions.equipment import EquipAction, UnequipAction
        gd = make_game_data(item_stats={
            "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon"),
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon"),
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                        crafting_skill="gearcrafting", crafting_level=1),
        })
        gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}}
        equipment = _make_equipment(weapon_slot="copper_axe")
        state = make_state(inventory={"fishing_net": 1, "ash_plank": 6}, level=5,
                           equipment=equipment, skills={"gearcrafting": 5})
        # Committed target = wooden_shield (the intended upgrade).
        goal = UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))
        actions = [
            UnequipAction(slot="weapon_slot"),
            EquipAction(code="fishing_net", slot="weapon_slot"),   # downgrade — must be dropped
            EquipAction(code="wooden_shield", slot="shield_slot"), # the target — must be kept
            CraftAction(code="wooden_shield"),
        ]
        result = goal.relevant_actions(actions, state, gd)
        assert not any(isinstance(a, UnequipAction) for a in result)
        equips = [a for a in result if isinstance(a, EquipAction)]
        assert {a.code for a in equips} == {"wooden_shield"}

    def test_committed_target_locks_craft_to_one_item(self):
        """Regression: ash_planks gathered for a wooden_shield got spent on a
        fishing_net because the per-cycle target picker flipped. A committed
        target locks UpgradeEquipment to exactly that item — even when a
        different equippable is also craftable from the same materials."""
        gd = make_game_data(item_stats={
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon",
                                      crafting_skill="weaponcrafting", crafting_level=1),
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                        crafting_skill="gearcrafting", crafting_level=1),
        })
        gd._crafting_recipes = {
            "fishing_net": {"ash_plank": 6},
            "wooden_shield": {"ash_plank": 6},
        }
        # 6 planks: enough for EITHER. Both slots empty. Committed to shield.
        state = make_state(inventory={"ash_plank": 6}, level=5,
                           skills={"weaponcrafting": 5, "gearcrafting": 5})
        goal = UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))
        assert goal.find_upgrade_target(state, gd) == ("wooden_shield", "shield_slot")
        assert goal._find_upgrade(state, gd) == ("wooden_shield", "shield_slot")
        assert goal.desired_state(state, gd) == {"equipment": {"shield_slot": "wooden_shield"}}

    def test_committed_target_waits_without_materials(self):
        """Committed target with no materials → _find_upgrade returns None
        (don't craft a different item, just wait for GatherMaterials)."""
        gd = make_game_data(item_stats={
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                        crafting_skill="gearcrafting", crafting_level=1),
        })
        gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}}
        state = make_state(inventory={"ash_plank": 2}, level=5, skills={"gearcrafting": 5})
        goal = UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))
        assert goal._find_upgrade(state, gd) is None

    def test_junk_inventory_weapon_does_not_beat_better_craftable(self):
        """Regression: a junk weapon already in the bag (wooden_stick / fishing_net)
        with an empty weapon slot used to win the upgrade target because
        find_upgrade_target checked inventory FIRST and the inventory picker
        maximized level, not value. Now the best-VALUE candidate across
        inventory and craftable wins, so junk loses to real craftable gear."""
        gd = make_game_data(item_stats={
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={"air": 1}),
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon",
                                      attack={"water": 5}, skill_effects={"fishing": -10}),
            "wooden_staff": ItemStats(code="wooden_staff", level=1, type_="weapon",
                                       crafting_skill="weaponcrafting", crafting_level=1,
                                       attack={"air": 8}),
        })
        gd._crafting_recipes = {"wooden_staff": {"ash_plank": 6}}
        equipment = _make_equipment()  # weapon slot empty
        state = make_state(inventory={"wooden_stick": 1, "fishing_net": 1}, level=5,
                           equipment=equipment, skills={"weaponcrafting": 5})
        goal = UpgradeEquipmentGoal()
        # staff (value 8, craftable) beats stick (1) and net (5) in inventory.
        assert goal.find_upgrade_target(state, gd) == ("wooden_staff", "weapon_slot")

    def test_value_ranking_prefers_shield_over_fishing_net(self):
        """Regression: with an empty weapon slot the picker chose fishing_net
        (attack 5, fishing penalty) over a wooden_shield (resist 2/2/2/2 = 8)
        because the tiebreak was alphabetical. Rank by stat value so the
        better gear is the committed target."""
        gd = make_game_data(item_stats={
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon",
                                      crafting_skill="weaponcrafting", crafting_level=1,
                                      attack={"water": 5}, skill_effects={"fishing": -10}),
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                        crafting_skill="gearcrafting", crafting_level=1,
                                        resistance={"fire": 2, "earth": 2, "water": 2, "air": 2}),
        })
        gd._crafting_recipes = {
            "fishing_net": {"ash_plank": 6},
            "wooden_shield": {"ash_plank": 6},
        }
        # Both slots empty, both craftable. Shield must win on value.
        state = make_state(inventory={}, level=5,
                           skills={"weaponcrafting": 5, "gearcrafting": 5})
        goal = UpgradeEquipmentGoal()
        target = goal._find_craftable_upgrade_target(state, gd)
        assert target == ("wooden_shield", "shield_slot")

    def test_craftable_tiebreak_prefers_ring_over_dagger_deterministically(self):
        """Regression: copper_dagger and copper_ring are both L1, craft_level 1.
        With the weapon slot filled (copper_axe), only the ring is a valid
        upgrade. Even when both slots are empty, the tiebreak must be
        deterministic (not dict-order) so the bot never crafts a redundant
        dagger when a ring is the intended target."""
        gd = make_game_data(item_stats={
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                        crafting_skill="weaponcrafting", crafting_level=1),
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                      crafting_skill="jewelrycrafting", crafting_level=1),
            "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon"),
        })
        gd._crafting_recipes = {
            "copper_dagger": {"copper_bar": 6},
            "copper_ring": {"copper_bar": 6},
        }
        equipment = _make_equipment(weapon_slot="copper_axe")  # weapon filled
        state = make_state(inventory={}, level=5, equipment=equipment,
                           skills={"weaponcrafting": 5, "jewelrycrafting": 5})
        goal = UpgradeEquipmentGoal()
        # Weapon occupied by axe (dagger not an upgrade); ring slots empty.
        assert goal._find_craftable_upgrade_target(state, gd) == ("copper_ring", "ring1_slot")

    def test_inventory_ready_active_tool_preempts_farm_items(self):
        """Regression: copper_axe sat in inventory while Robby gathered ash
        with fishing_net, because FarmItems' runaway dynamic bonus (377)
        crushed the equip. An inventory-ready tool that boosts the active
        task skill must now preempt a capped FarmItems (max 75)."""
        gd = make_game_data(item_stats={
            "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                     skill_effects=frozenset({"woodcutting"})),
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon",
                                      skill_effects=frozenset({"fishing"})),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        })
        gd._crafting_recipes = {"copper_axe": {}, "fishing_net": {}, "ash_plank": {"ash_wood": 1}}
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
        equipment = _make_equipment(weapon_slot="fishing_net")
        state = make_state(inventory={"copper_axe": 1}, level=3, equipment=equipment,
                           task_code="ash_plank", task_type="items",
                           task_total=10, task_progress=0)
        goal = UpgradeEquipmentGoal()
        prio = goal.priority(state, gd)
        assert prio == 88.0  # UPGRADE_EQUIPMENT_ACTIVE_TOOL_READY
        assert prio > 75.0   # above capped FarmItems max

    def test_active_skill_tool_beats_equipped_unrelated_tool(self):
        """Regression: Robby gathered ash_wood with fishing_net equipped
        because _is_upgrade_over treated same-level both-craftable items
        as 'not an upgrade' — ignoring that copper_axe boosts the active
        gather skill (woodcutting) while fishing_net does not."""
        gd = make_game_data(item_stats={
            "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                     skill_effects=frozenset({"woodcutting"})),
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon",
                                      skill_effects=frozenset({"fishing"})),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        })
        gd._crafting_recipes = {"copper_axe": {}, "fishing_net": {}, "ash_plank": {"ash_wood": 1}}
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
        equipment = {k: None for k in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                        "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                                        "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                                        "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]}
        equipment["weapon_slot"] = "fishing_net"
        state = make_state(inventory={"copper_axe": 1}, level=3, equipment=equipment,
                            task_code="ash_plank", task_type="items", task_total=10, task_progress=0)
        goal = UpgradeEquipmentGoal()
        target = goal._find_inventory_only_upgrade(state, gd)
        assert target == ("copper_axe", "weapon_slot")

    def test_does_not_steal_materials_meant_for_better_upgrade(self):
        """Regression: GatherMaterials targets the ideal upgrade
        (find_upgrade_target — ignores material availability), so
        UpgradeEquipment must not race it by crafting a cheaper item
        with the bars meant for the ideal target. If the ideal target's
        materials are not yet in hand, UpgradeEquipment must wait."""
        ring_stats = ItemStats(code="copper_ring", level=1, type_="ring",
                               crafting_skill="jewelrycrafting", crafting_level=1)
        dagger_stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=1)
        gd = make_game_data(item_stats={
            "copper_ring": ring_stats, "copper_dagger": dagger_stats,
        })
        # Both recipes need copper_bar; ring needs 6, dagger needs 2.
        gd._crafting_recipes = {
            "copper_ring": {"copper_bar": 6},
            "copper_dagger": {"copper_bar": 2},
        }
        # Dagger already in bank — Bug 2 fix excludes it → target = ring.
        # Bot has 3 bars: enough for dagger, NOT enough for ring.
        state = make_state(inventory={"copper_bar": 3}, bank_items={"copper_dagger": 1},
                            level=5,
                            skills={"jewelrycrafting": 1, "weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        # Target picker should pick ring (dagger already owned via bank).
        target = goal._find_craftable_upgrade_target(state, gd)
        assert target == ("copper_ring", "ring1_slot")
        # Materials picker should NOT fall back to a non-target item.
        upgrade = goal._find_craftable_upgrade(state, gd)
        assert upgrade is None, "must wait for ring's materials, not craft a different item"

    def test_no_recraft_when_copy_already_in_bank(self):
        """Regression: UpgradeEquipment kept crafting fresh copper_dagger
        copies each cycle because _find_craftable_upgrade_target only
        skipped items already in inventory, not in bank. After equipping
        and depositing, the next cycle saw 'no copy in inventory' and
        re-triggered the craft."""
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        state = make_state(inventory={"copper_ore": 6}, bank_items={"copper_dagger": 1},
                           level=5, skills={"weaponcrafting": 1})
        goal = UpgradeEquipmentGoal()
        # Copy in bank — bot should withdraw, not re-craft. find_upgrade_target
        # must return the bank item (not None, not a fresh craft target).
        target = goal.find_upgrade_target(state, gd)
        assert target == ("copper_dagger", "weapon_slot")


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

    def test_priority_zero_when_target_craft_skill_gated(self):
        """Regression: copper_ring needs jewelrycrafting; if Robby's skill is
        too low, the final Craft is infeasible and gathering can never
        satisfy the goal. Priority must drop to 0 so lower-priority goals
        (e.g. DiscardOverstock) can run instead of being starved forever."""
        stats = ItemStats(code="copper_ring", level=1, type_="ring",
                          crafting_skill="jewelrycrafting", crafting_level=5)
        gd = make_game_data(item_stats={"copper_ring": stats})
        goal = GatherMaterialsGoal(target_item="copper_ring", needed={"copper_bar": 6})
        state = make_state(inventory={}, bank_items={}, skills={"jewelrycrafting": 1})
        assert goal.priority(state, gd) == 0.0

    def test_priority_high_when_target_craft_skill_met(self):
        stats = ItemStats(code="copper_ring", level=1, type_="ring",
                          crafting_skill="jewelrycrafting", crafting_level=5)
        gd = make_game_data(item_stats={"copper_ring": stats})
        goal = GatherMaterialsGoal(target_item="copper_ring", needed={"copper_bar": 6})
        state = make_state(inventory={}, bank_items={}, skills={"jewelrycrafting": 5})
        assert goal.priority(state, gd) == 50.0


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
        # Per-cycle horizon: still unsatisfied when no submission has occurred
        # since goal construction (initial_progress=4, current progress=4).
        goal = FarmItemsGoal(initial_progress=4)
        state = make_state(task_total=5, task_progress=4)
        assert goal.is_satisfied(state) is False

    def test_satisfied_when_progress_advances_one_submission(self):
        # Per-cycle horizon: one TaskTrade past initial counts as done.
        goal = FarmItemsGoal(initial_progress=4)
        state = make_state(task_total=10, task_progress=5)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_no_task(self):
        goal = FarmItemsGoal()
        state = make_state(task_total=0, task_progress=0)
        assert goal.is_satisfied(state) is False

    def test_desired_state_targets_one_more_submission(self):
        goal = FarmItemsGoal(initial_progress=3)
        state = make_state(task_total=10, task_progress=3)
        assert goal.desired_state(state, make_game_data()) == {"task_progress": 4}

    def test_priority_outranks_farm_monster_when_not_satisfied(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=0)
        assert goal.priority(state, make_game_data()) == 35.0

    def test_priority_zero_when_satisfied(self):
        goal = FarmItemsGoal()
        state = make_state(task_type="items", task_code="ash_wood", task_total=10, task_progress=10)
        assert goal.priority(state, make_game_data()) == 0.0

    def test_plan_delivers_via_task_trade_not_gather_only(self):
        """Regression: gathering no longer fakes items-task progress, so the
        planner must reach progress via a TaskTrade delivery. Bot holds the
        items; the plan delivers them."""
        gd = make_game_data()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_locations = {"copper_rocks": [(2, 0)]}
        state = make_state(
            x=1, y=2, task_type="items", task_code="copper_ore",
            task_total=5, task_progress=0, inventory={"copper_ore": 5},
        )
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])),
            TaskTradeAction(code="copper_ore", taskmaster_location=(1, 2)),
        ]
        goal = FarmItemsGoal(initial_progress=0)
        plan = GOAPPlanner().plan(state, goal, actions, gd)
        assert plan, "expected a delivery plan, got none"
        assert any(isinstance(a, TaskTradeAction) for a in plan)

    def test_no_plan_when_only_gather_available(self):
        """Without a delivery action, gathering can't advance an items-task —
        the planner finds no plan (proving gather alone doesn't fake progress)."""
        gd = make_game_data()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_locations = {"copper_rocks": [(2, 0)]}
        state = make_state(
            x=1, y=2, task_type="items", task_code="copper_ore",
            task_total=5, task_progress=0, inventory={"copper_ore": 5},
        )
        actions = [GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))]
        goal = FarmItemsGoal(initial_progress=0)
        assert GOAPPlanner().plan(state, goal, actions, gd) == []

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
    def test_value_22_when_coins_meet_learned_minimum(self):
        # min_coins is injected (learned empirically), not a hardcoded cost.
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={"tasks_coin": 6})
        assert goal.value(state, make_game_data()) == 22.0

    def test_value_22_when_coins_in_bank_meet_minimum(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(bank_items={"tasks_coin": 6})
        assert goal.value(state, make_game_data()) == 22.0

    def test_value_zero_when_no_coins(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={}, bank_items={})
        assert goal.value(state, make_game_data()) == 0.0

    def test_value_zero_when_below_minimum(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={"tasks_coin": 5})
        assert goal.value(state, make_game_data()) == 0.0

    def test_satisfied_when_no_coins(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={}, bank_items={})
        assert goal.is_satisfied(state) is True

    def test_satisfied_when_below_minimum(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={"tasks_coin": 5})
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_coins_meet_minimum(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={"tasks_coin": 6})
        assert goal.is_satisfied(state) is False

    def test_not_satisfied_when_coins_in_bank_meet_minimum(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(bank_items={"tasks_coin": 6})
        assert goal.is_satisfied(state) is False

    def test_default_minimum_is_one(self):
        goal = TaskExchangeGoal()
        assert goal.is_satisfied(make_state(inventory={"tasks_coin": 1})) is False
        assert goal.is_satisfied(make_state(inventory={}, bank_items={})) is True

    def test_desired_state_drops_below_batch(self):
        goal = TaskExchangeGoal(min_coins=6)
        state = make_state(inventory={"tasks_coin": 8})
        assert goal.desired_state(state, make_game_data()) == {"inventory": {"tasks_coin": 2}}

    def test_repr(self):
        assert repr(TaskExchangeGoal()) == "TaskExchange"


class TestUnlockBankGoal:
    def _make_gd_with_sellables(self) -> GameData:
        gd = GameData()
        gd._npc_sell_prices = {"cook": {"chicken": 5}}
        return gd

    def _make_gd_no_sellables(self) -> GameData:
        gd = GameData()
        gd._npc_sell_prices = {}
        return gd

    def test_value_90_when_bank_locked_no_inventory_pressure(self):
        """Bank locked + low inventory → stay focused on unlock."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=100, inventory={}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 90.0

    def test_value_90_when_bank_locked_below_threshold_with_sellables(self):
        """Bank locked + inventory < 85% full + sellables → still 90, not deferred."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        # 5/20 = 25% full — well below 85%
        state = make_state(xp=100, inventory={"chicken": 5}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 90.0

    def test_value_30_when_bank_locked_inventory_critical_and_sellables_exist(self):
        """Bank locked + inventory ≥ 85% full + sellables → defer to SellInventory."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        # 17/20 = 85% full
        state = make_state(xp=100, inventory={"chicken": 17}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 30.0

    def test_value_30_at_exactly_85_percent(self):
        """Edge: exactly at 85% threshold triggers deferral."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=100, inventory={"chicken": 17}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 30.0

    def test_value_90_when_bank_locked_inventory_critical_but_no_sellables(self):
        """Bank locked + inventory ≥ 85% full + NO sellables → can't sell, stay at 90."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=100, inventory={"useless_thing": 20}, inventory_max=20)
        assert goal.value(state, self._make_gd_no_sellables()) == 90.0

    def test_value_0_when_bank_not_locked(self):
        """Bank already unlocked → value 0."""
        goal = UnlockBankGoal(bank_locked=False, initial_xp=100)
        state = make_state(xp=100, inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 0.0

    def test_value_0_when_xp_advanced(self):
        """XP past initial → achievement done → value 0."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=101, inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, self._make_gd_with_sellables()) == 0.0

    def test_is_satisfied_when_bank_unlocked_or_target_fight_landed(self):
        """is_satisfied is planner-reachable via xp>initial. The chicken-massacre
        loop is now prevented by relevant_actions restricting combat to the
        TARGET monster, so a generic XP bump can't come from the wrong fight.
        `not bank_locked` still short-circuits to satisfied."""
        # Locked, no XP gained yet → not satisfied (planner must fight target).
        locked = UnlockBankGoal(bank_locked=True, initial_xp=100)
        assert locked.is_satisfied(make_state(xp=100)) is False
        # Locked, XP advanced (a target-monster fight was simulated) → satisfied.
        assert locked.is_satisfied(make_state(xp=101)) is True
        # Already unlocked → satisfied regardless of XP.
        unlocked = UnlockBankGoal(bank_locked=False, initial_xp=100)
        assert unlocked.is_satisfied(make_state(xp=100)) is True

    def test_desired_state_returns_empty_dict(self):
        """desired_state returns {} — satisfaction is driven by the constructor's
        bank_locked flag, not by reaching a specific WorldState attribute."""
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=100)
        gd = self._make_gd_with_sellables()
        assert goal.desired_state(state, gd) == {}

    def test_relevant_actions_returns_fight_actions(self):
        """relevant_actions includes FightAction instances."""
        from artifactsmmo_cli.ai.actions.combat import FightAction
        from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
        from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
        from artifactsmmo_cli.ai.actions.rest import RestAction
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        state = make_state(xp=100)
        gd = self._make_gd_with_sellables()
        actions = [
            FightAction(monster_code="chicken"),
            FightAction(monster_code="wolf"),
            RestAction(),
            DeleteItemAction(code="iron_ore"),
            UseConsumableAction(_item_stats={}),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        relevant_reprs = [repr(a) for a in relevant]
        assert "Fight(chicken)" in relevant_reprs
        assert "Fight(wolf)" in relevant_reprs
        # R-1.3: now allows Rest (any "recovery"-tagged action) — combat
        # against the unlock monster benefits from healing between fights.
        # Previous behavior excluded Rest by isinstance; the new tag-based
        # filter includes it intentionally.
        assert "Rest" in relevant_reprs
        assert "Delete(iron_ore×1)" in relevant_reprs
        assert "UseConsumable" in relevant_reprs

    def test_relevant_actions_filters_by_target_monster(self):
        """When target_monster is set, only that monster's fight action is returned."""
        from artifactsmmo_cli.ai.actions.combat import FightAction
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100, target_monster="chicken")
        state = make_state(xp=100)
        gd = self._make_gd_with_sellables()
        actions = [
            FightAction(monster_code="chicken"),
            FightAction(monster_code="wolf"),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        relevant_reprs = [repr(a) for a in relevant]
        assert "Fight(chicken)" in relevant_reprs
        assert "Fight(wolf)" not in relevant_reprs

    def test_relevant_actions_excludes_all_fights_when_target_unavailable(self):
        """When target_monster is set but no FightAction for it exists, return
        NO fight actions. The previous fallback to all-fights let the bot
        grind chickens forever while the actual achievement stayed unmet
        and the bank stayed locked."""
        from artifactsmmo_cli.ai.actions.combat import FightAction
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100, target_monster="dragon")
        state = make_state(xp=100)
        gd = self._make_gd_with_sellables()
        actions = [
            FightAction(monster_code="chicken"),
            FightAction(monster_code="wolf"),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        relevant_reprs = [repr(a) for a in relevant]
        assert "Fight(chicken)" not in relevant_reprs
        assert "Fight(wolf)" not in relevant_reprs

    def test_repr_with_no_target_monster(self):
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100)
        assert repr(goal) == "UnlockBank(?)"

    def test_repr_with_target_monster(self):
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100, target_monster="skeleton")
        assert repr(goal) == "UnlockBank(skeleton)"


def test_farm_items_goal_includes_task_trade_in_relevant_actions():
    """When task_type==items, FarmItemsGoal.relevant_actions must include TaskTradeAction."""
    gd = GameData()
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._crafting_recipes = {}

    actions = [
        RestAction(),
        GatherAction(resource_code="iron_rocks", locations=frozenset({(2, 3)})),
        TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2)),
        TaskTradeAction(code="other_item", quantity=1, taskmaster_location=(1, 2)),
    ]
    state = make_state(task_code="iron_ore", task_type="items", task_total=20, task_progress=5)
    goal = FarmItemsGoal()
    relevant = goal.relevant_actions(actions, state, gd)
    names = [repr(a) for a in relevant]
    assert any("TaskTrade(iron_ore" in n for n in names)


class TestFarmItemsBatching:
    def test_relevant_actions_emits_batched_task_trade(self):
        """qty=1 prebuilt must be substituted with batch-sized variant so
        planner gathers many items before the round-trip to the taskmaster."""
        gd = GameData()
        gd._resource_drops = {"gudgeon_spot": "gudgeon"}
        gd._crafting_recipes = {}
        actions = [TaskTradeAction(code="gudgeon", quantity=1, taskmaster_location=(1, 2))]
        # task_remaining=232, inventory empty, free_slots=104 → batch capped at BATCH_SIZE(30)
        state = make_state(task_code="gudgeon", task_type="items",
                            task_total=353, task_progress=121,
                            inventory={}, inventory_max=104)
        goal = FarmItemsGoal()
        relevant = goal.relevant_actions(actions, state, gd)
        trades = [a for a in relevant if isinstance(a, TaskTradeAction)]
        assert len(trades) == 1
        assert trades[0].quantity == 30

    def test_batch_capped_by_task_remaining(self):
        """Endgame: task_remaining < BATCH_SIZE → trade only what's left."""
        gd = GameData()
        actions = [TaskTradeAction(code="gudgeon", quantity=1, taskmaster_location=(1, 2))]
        # 5 items left in task
        state = make_state(task_code="gudgeon", task_type="items",
                            task_total=353, task_progress=348,
                            inventory={}, inventory_max=104)
        goal = FarmItemsGoal()
        trades = [a for a in goal.relevant_actions(actions, state, gd) if isinstance(a, TaskTradeAction)]
        assert trades[0].quantity == 5

    def test_crafted_task_uses_smaller_batch(self):
        """Crafted-item tasks (ash_plank: gather wood + craft plank) inflate
        plan depth ~3x. Smaller batch keeps plans inside the 2s budget.
        Without this, FarmItems timed_out=True → plan_len=0 → no_plan."""
        gd = GameData()
        gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
        actions = [TaskTradeAction(code="ash_plank", quantity=1, taskmaster_location=(1, 2))]
        state = make_state(task_code="ash_plank", task_type="items",
                            task_total=26, task_progress=0,
                            inventory={}, inventory_max=104)
        goal = FarmItemsGoal()
        trades = [a for a in goal.relevant_actions(actions, state, gd) if isinstance(a, TaskTradeAction)]
        assert trades[0].quantity == 8  # BATCH_SIZE_CRAFTED, not 30

    def test_batch_capped_by_bag_headroom(self):
        """Bag-near-full: batch = current task-item count + the slots gathering
        can still fill (free_slots minus the gather min-free reserve), NOT the
        full free_slots — otherwise the trade demands more than is obtainable."""
        gd = GameData()
        actions = [TaskTradeAction(code="gudgeon", quantity=1, taskmaster_location=(1, 2))]
        # 10 gudgeon, 5 free slots; gather stops at 2 free (MIN_FREE_SLOTS=3) so
        # only 3 more obtainable → achievable = 13, batch = min(30, 232, 13) = 13.
        state = make_state(task_code="gudgeon", task_type="items",
                            task_total=353, task_progress=121,
                            inventory={"gudgeon": 10, "other": 89}, inventory_max=104)
        goal = FarmItemsGoal()
        trades = [a for a in goal.relevant_actions(actions, state, gd) if isinstance(a, TaskTradeAction)]
        assert trades[0].quantity == 13

    def test_full_bag_delivers_what_it_holds_no_deadlock(self):
        """Regression (Robby stuck): near-full bag (free < MIN_FREE_SLOTS) can't
        gather more, so the batch must equal what's already held — a deliverable
        TaskTrade — not current+free which overshoots and yields no plan."""
        gd = GameData()
        actions = [TaskTradeAction(code="copper_ore", quantity=1, taskmaster_location=(1, 2))]
        # 15 copper_ore, bag 102/104 → free 2 (< MIN_FREE_SLOTS): 0 gatherable.
        state = make_state(task_code="copper_ore", task_type="items",
                           task_total=255, task_progress=0,
                           inventory={"copper_ore": 15, "junk": 87}, inventory_max=104)
        goal = FarmItemsGoal()
        trade = [a for a in goal.relevant_actions(actions, state, gd)
                 if isinstance(a, TaskTradeAction)][0]
        assert trade.quantity == 15
        assert trade.is_applicable(state, gd)  # deliverable now → breaks the deadlock


def test_farm_monster_goal_value_amplifies_on_high_xp_yield():
    """G-F: goal.value is base + scalar-yield bonus from cycles where the
    goal itself was selected (not just from observed Fight outcomes — the
    selected_goal column is the attribution key)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(30):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="testchar", outcome="ok",
                selected_goal="FarmMonster(yellow_slime)",
                action_repr="Fight(yellow_slime)", delta_xp=20,
            ))
        goal = FarmMonsterGoal(monster_code="yellow_slime", initial_xp=0)
        gd = make_game_data()
        gd._monster_level = {"yellow_slime": 1}
        state = make_state(xp=50, max_xp=100, level=5)
        base = goal.value(state, gd, history=None)
        with_hist = goal.value(state, gd, history=store)
        # base = 30 + (50/100)*20 = 40. Bonus > 0 since we seeded the goal's
        # cycles with positive delta_xp at full warmup (30 = CONFIDENCE_CAP).
        assert base == 40.0
        assert with_hist > base
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_farm_monster_goal_value_unchanged_when_history_none():
    gd = make_game_data()
    gd._monster_level = {"x": 1}
    state = make_state(xp=50, max_xp=100, level=5)
    goal = FarmMonsterGoal(monster_code="x", initial_xp=0)
    assert goal.value(state, gd) == goal.value(state, gd, history=None)


def test_gather_materials_goal_unchanged_when_history_none():
    """history=None preserves v1 behaviour."""
    goal = GatherMaterialsGoal(target_item="copper_boots", needed={"copper_ore": 60})
    state = make_state(inventory={}, inventory_max=104, bank_items={})
    gd = make_game_data()
    assert goal.value(state, gd) == goal.value(state, gd, history=None)


def test_gather_materials_goal_value_penalty_when_slow_to_satisfy():
    """When goal historically takes many cycles to satisfy, value is scaled down."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                selected_goal="GatherMaterials(copper_boots)",
                cycles_to_satisfy=50,
            ))
        goal = GatherMaterialsGoal(target_item="copper_boots", needed={"copper_ore": 60})
        state = make_state(inventory={}, inventory_max=104, bank_items={})
        gd = make_game_data()
        base = goal.value(state, gd, history=None)
        with_hist = goal.value(state, gd, history=store)
        assert with_hist < base
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_task_cancel_fires_for_infeasible_items_task():
    gd = make_game_data()
    gd._item_stats["small_health_potion"] = ItemStats(
        code="small_health_potion", level=1, type_="utility",
        crafting_skill="alchemy", crafting_level=5)
    gd._crafting_recipes["small_health_potion"] = {"sunflower": 3}
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, task_progress=0, skills={"alchemy": 1})
    assert TaskCancelGoal().value(state, gd) > 0.0


def test_task_cancel_zero_for_feasible_items_task():
    gd = make_game_data()
    gd._item_stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=1)
    gd._crafting_recipes["copper_dagger"] = {"copper_bar": 6}
    state = make_state(task_code="copper_dagger", task_type="items",
                       task_total=5, skills={"weaponcrafting": 6})
    assert TaskCancelGoal().value(state, gd) == 0.0


def test_task_cancel_still_fires_for_too_hard_monster():
    gd = make_game_data()
    gd._monster_level = {"dragon": 40}
    state = make_state(task_code="dragon", task_type="monsters", task_total=1, level=3)
    assert TaskCancelGoal().value(state, gd) > 0.0


class TestDepositInventorySelective:
    def _gd(self):
        gd = make_game_data()
        gd._npc_sell_prices = {"m": {"sap": 3}}
        gd._item_stats = {
            "sap": ItemStats(code="sap", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        return gd

    def test_satisfied_when_no_bankable_items(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=True, game_data=gd)
        state = make_state(inventory={"copper_ore": 100}, inventory_max=104,
                           task_code="copper_ore")
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_not_satisfied_when_bankable_present(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=True, game_data=gd)
        state = make_state(inventory={"sap": 60}, inventory_max=104)
        assert goal.is_satisfied(state) is False

    def test_value_zero_when_bank_inaccessible(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=False, game_data=gd)
        state = make_state(inventory={"sap": 100}, inventory_max=104)
        assert goal.value(state, gd) == 0.0
