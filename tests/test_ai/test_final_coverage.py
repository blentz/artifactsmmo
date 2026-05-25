"""Tests for final coverage gaps."""

from unittest.mock import MagicMock, patch

import pytest
from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._monster_locations = kwargs.get("monster_locs", {})
    gd._resource_locations = kwargs.get("resource_locs", {})
    gd._workshop_locations = kwargs.get("workshop_locs", {})
    gd._bank_location = kwargs.get("bank_loc", (4, 0))
    gd._taskmaster_location = kwargs.get("taskmaster_loc", (1, 2))
    gd._item_stats = kwargs.get("item_stats", {})
    gd._crafting_recipes = kwargs.get("recipes", {})
    gd._resource_skill = kwargs.get("resource_skills", {})
    gd._monster_level = {}
    return gd


class TestProgressionGoalEdgeCases:
    def test_is_satisfied_always_false(self):
        goal = UpgradeEquipmentGoal()
        state = make_state(inventory={"sword": 1})
        assert goal.is_satisfied(state) is False

    def test_find_upgrade_skips_unknown_type(self):
        goal = UpgradeEquipmentGoal()
        # type_ "consumable" not in ITEM_TYPE_TO_SLOT → slot is None → continue
        stats = ItemStats(code="healing_potion", level=1, type_="consumable")
        state = make_state(inventory={"healing_potion": 1}, level=5)
        gd = make_gd(item_stats={"healing_potion": stats})
        assert goal.value(state, gd) == 0.0

    def test_find_upgrade_when_current_stats_none(self):
        """Regression: missing stats for an equipped item must NOT auto-trigger
        an upgrade. The bot used to recraft duplicates every cycle whenever
        the game_data DB lacked entries for starter gear (fishing_net)."""
        goal = UpgradeEquipmentGoal()
        new_stats = ItemStats(code="copper_dagger", level=2, type_="weapon")
        equipment = {k: None for k in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                        "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                                        "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                                        "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]}
        equipment["weapon_slot"] = "ghost_sword"
        state = make_state(inventory={"copper_dagger": 1}, level=5, equipment=equipment)
        gd = make_gd(item_stats={"copper_dagger": new_stats})  # ghost_sword has no stats
        # Conservative: current_stats None → refuse upgrade (don't recraft).
        assert goal.value(state, gd) == 0.0

    def test_find_upgrade_higher_level_upgrade(self):
        goal = UpgradeEquipmentGoal()
        old_stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        new_stats = ItemStats(code="iron_sword", level=5, type_="weapon")
        equipment = {k: None for k in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                        "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                                        "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                                        "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]}
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(inventory={"iron_sword": 1}, level=10, equipment=equipment)
        gd = make_gd(item_stats={"copper_dagger": old_stats, "iron_sword": new_stats})
        assert goal.value(state, gd) == 35.0


class TestPlannerFindsAndReturns:
    def test_continues_searching_after_first_plan_found(self):
        """The planner continues after finding a plan to look for cheaper ones."""
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = RestoreHPGoal()
        actions = [RestAction()]
        gd = make_gd()
        plan = planner.plan(state, goal, actions, gd)
        assert len(plan) == 1  # RestAction directly satisfies RestoreHPGoal


class TestWithdrawIsApplicableNoBank:
    def test_not_applicable_when_bank_items_none(self):
        action = WithdrawItemAction(code="copper", quantity=1, bank_location=(4, 0))
        state = make_state(x=0, y=0, bank_items=None)
        gd = make_gd(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is False


class TestGatherIsApplicableEmptyLocations:
    def test_not_applicable_when_no_locations(self):
        # GatherAction with empty locations is never applicable (no destination)
        action = GatherAction(resource_code="copper", locations=frozenset())
        state = make_state(x=0, y=0)
        gd = make_gd(resource_locs={"copper": [(3, 0)]})
        assert action.is_applicable(state, gd) is False


class TestEquipApplyWithExistingItem:
    def test_apply_puts_old_item_back_in_inventory(self):
        action = EquipAction(code="iron_sword", slot="weapon_slot")
        stats = ItemStats(code="iron_sword", level=1, type_="weapon")
        equipment = {k: None for k in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                        "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                                        "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                                        "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]}
        equipment["weapon_slot"] = "copper_dagger"  # existing item
        state = make_state(inventory={"iron_sword": 1}, level=5, equipment=equipment)
        gd = make_gd(item_stats={"iron_sword": stats})
        new_state = action.apply(state, gd)
        assert new_state.equipment["weapon_slot"] == "iron_sword"
        assert new_state.inventory.get("copper_dagger", 0) == 1

    def test_equip_repr_with_slot(self):
        action = EquipAction(code="iron_sword", slot="weapon_slot")
        stats = ItemStats(code="iron_sword", level=1, type_="weapon")
        state = make_state(inventory={"iron_sword": 1}, level=5)
        gd = make_gd(item_stats={"iron_sword": stats})
        assert action.is_applicable(state, gd) is True


class TestGameDataPaginationContinues:
    def test_items_paginates_second_page(self):
        gd = GameData()
        from artifactsmmo_api_client.types import UNSET

        item = MagicMock()
        item.code = "sword"
        item.level = 5
        item.type_ = "weapon"
        item.craft = UNSET

        full_page = MagicMock()
        full_page.data = [item] * 100

        item2 = MagicMock()
        item2.code = "shield"
        item2.level = 5
        item2.type_ = "shield"
        item2.craft = UNSET
        partial_page = MagicMock()
        partial_page.data = [item2]

        with patch("artifactsmmo_cli.ai.game_data.get_all_items", side_effect=[full_page, partial_page]):
            gd._load_items(MagicMock())

        assert "sword" in gd._item_stats
        assert "shield" in gd._item_stats

    def test_resources_paginates_second_page(self):
        gd = GameData()
        res = MagicMock()
        res.code = "copper"
        res.skill = MagicMock()
        res.skill.value = "mining"
        res.level = 1
        res.drops = []
        res2 = MagicMock()
        res2.code = "gold"
        res2.skill = MagicMock()
        res2.skill.value = "mining"
        res2.level = 5
        res2.drops = []

        full_page = MagicMock()
        full_page.data = [res] * 100
        partial_page = MagicMock()
        partial_page.data = [res2]

        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", side_effect=[full_page, partial_page]):
            gd._load_resources(MagicMock())

        assert "copper" in gd._resource_skill
        assert "gold" in gd._resource_skill

    def test_monsters_paginates_second_page(self):
        gd = GameData()
        mon = MagicMock()
        mon.code = "chicken"
        mon.level = 1
        mon2 = MagicMock()
        mon2.code = "cow"
        mon2.level = 2

        full_page = MagicMock()
        full_page.data = [mon] * 100
        partial_page = MagicMock()
        partial_page.data = [mon2]

        with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", side_effect=[full_page, partial_page]):
            gd._load_monsters(MagicMock())

        assert "chicken" in gd._monster_level
        assert "cow" in gd._monster_level


class TestPlayerRunVerboseAndExecute:
    def test_run_finds_plan_and_executes(self):
        """Test run() when a plan is found and executed (non-dry-run)."""
        player = GamePlayer(character="hero", verbose=True)
        char_after_rest = make_char_schema(hp=150, max_hp=150)
        client = MagicMock()

        # Below the 25% critical-HP guard threshold so RestoreHP fires as a guard.
        initial_state = make_state(hp=20, max_hp=150)
        wait_calls = [0]

        def fake_wait():
            wait_calls[0] += 1
            if wait_calls[0] > 1:
                raise KeyboardInterrupt

        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=MagicMock(data=[])):
                    with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=MagicMock(data=[])):
                        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=MagicMock(data=[])):
                            with patch("artifactsmmo_cli.ai.game_data.get_all_monsters",
                                       return_value=MagicMock(data=[])):
                                with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items",
                                           return_value=MagicMock(data=[])):
                                    with patch("artifactsmmo_cli.ai.game_data.get_all_events",
                                               return_value=MagicMock(data=[])):
                                        with patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None):
                                            with patch.object(player, "_fetch_world_state", return_value=initial_state):
                                                with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                                                    with patch.object(player, "_maybe_periodic_refresh"):
                                                        with patch.object(player, "_build_actions",
                                                                   return_value=[RestAction()]):
                                                            with patch("artifactsmmo_cli.ai.actions.rest.action_rest",
                                                                       return_value=make_api_result(char_after_rest)):
                                                                with pytest.raises(KeyboardInterrupt):
                                                                    player.run()

        assert player.state is not None
        assert player.state.hp == 150  # Rest was executed

    def test_run_dry_run_finds_plan_and_applies(self):
        """Test run() dry_run path when a plan is found."""
        player = GamePlayer(character="hero", dry_run=True)
        client = MagicMock()

        # Below the 25% critical-HP guard threshold so RestoreHP fires as a guard.
        initial_state = make_state(hp=20, max_hp=150)
        wait_calls = [0]

        def fake_wait():
            wait_calls[0] += 1
            if wait_calls[0] > 1:
                raise KeyboardInterrupt

        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=MagicMock(data=[])):
                    with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=MagicMock(data=[])):
                        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=MagicMock(data=[])):
                            with patch("artifactsmmo_cli.ai.game_data.get_all_monsters",
                                       return_value=MagicMock(data=[])):
                                with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items",
                                           return_value=MagicMock(data=[])):
                                    with patch("artifactsmmo_cli.ai.game_data.get_all_events",
                                               return_value=MagicMock(data=[])):
                                        with patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None):
                                            with patch.object(player, "_fetch_world_state", return_value=initial_state):
                                                with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                                                    with patch.object(player, "_maybe_periodic_refresh"):
                                                        with patch.object(player, "_build_actions",
                                                                   return_value=[RestAction()]):
                                                            with pytest.raises(KeyboardInterrupt):
                                                                player.run()

        # dry_run: apply() was called, not execute()
        assert player.state is not None
        assert player.state.hp == 150  # RestAction.apply sets hp to max_hp


class TestActionCostMethods:
    def test_craft_action_cost(self):
        action = CraftAction(code="sword", quantity=3)
        state = make_state()
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(15.0)

    def test_equip_action_cost(self):
        action = EquipAction(code="sword", slot="weapon_slot")
        state = make_state()
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(1.0)

    def test_gather_action_cost_includes_distance(self):
        # At (0,0), nearest copper at (2,0): distance=2, total cost=6+2=8
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0)
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(8.0)


class TestGameDataUnsetContent:
    def test_skips_unset_content(self):
        gd = GameData()
        tile = MagicMock()
        tile.interactions.content = UNSET
        tile.x = 1
        tile.y = 0
        page = MagicMock()
        page.data = [tile]
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=page):
            gd._load_maps(MagicMock())
        assert gd._monster_locations == {}


class TestProgressionLevelTooLow:
    def test_find_upgrade_skips_item_above_character_level(self):
        goal = UpgradeEquipmentGoal()
        stats = ItemStats(code="legendary_sword", level=100, type_="weapon")
        state = make_state(inventory={"legendary_sword": 1}, level=1)
        gd = make_gd(item_stats={"legendary_sword": stats})
        assert goal.value(state, gd) == 0.0


class TestBuildActionsWithCraftingRecipes:
    def test_adds_craft_equip_withdraw_for_gear_items(self):
        """_build_actions() adds CraftAction for all craftable items; EquipAction/WithdrawItemAction only for gear."""
        weapon_stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        consumable_stats = ItemStats(code="potion", level=1, type_="consumable")

        gd = make_gd(
            item_stats={"copper_dagger": weapon_stats, "potion": consumable_stats},
            recipes={
                "copper_dagger": {"copper_ore": 6},
                "potion": {"herb": 2},
            },
            workshop_locs={"weaponcrafting": (3, 0)},
        )
        player = GamePlayer(character="hero")
        player.game_data = gd
        player.state = make_state()

        actions = player._build_actions()

        craft_codes = {a.code for a in actions if isinstance(a, CraftAction)}
        equip_codes = {a.code for a in actions if isinstance(a, EquipAction)}
        withdraw_codes = {a.code for a in actions if isinstance(a, WithdrawItemAction)}

        # CraftAction added for all craftable items (gear AND non-gear like potions)
        assert "copper_dagger" in craft_codes
        assert "potion" in craft_codes
        # EquipAction only for gear items
        assert "copper_dagger" in equip_codes
        assert "potion" not in equip_codes
        # WithdrawItemAction only for gear recipe materials
        assert "copper_ore" in withdraw_codes
        assert "herb" not in withdraw_codes

    def test_skips_item_with_no_stats(self):
        """Items in _crafting_recipes without stats are skipped."""
        gd = make_gd(
            item_stats={},  # no stats for mystery_item
            recipes={"mystery_item": {"copper_ore": 6}},
        )
        player = GamePlayer(character="hero")
        player.game_data = gd
        player.state = make_state()

        actions = player._build_actions()
        craft_codes = {a.code for a in actions if isinstance(a, CraftAction)}
        assert "mystery_item" not in craft_codes


class TestPlannerVisitedSet:
    def test_skips_revisited_states(self):
        planner = GOAPPlanner()
        # hp=50 < max_hp=150 → RestoreHPGoal not satisfied; only MoveActions can't heal
        state = make_state(x=1, y=0, hp=50, max_hp=150)
        goal = RestoreHPGoal()
        # Move between two points creates a cycle; planner should skip the revisit
        actions = [MoveAction(2, 0), MoveAction(1, 0)]
        gd = make_gd()
        plan = planner.plan(state, goal, actions, gd)
        assert plan == []
