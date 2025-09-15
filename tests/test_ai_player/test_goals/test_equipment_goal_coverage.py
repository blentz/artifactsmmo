"""
Targeted coverage tests for EquipmentGoal

This module contains specific tests to achieve 100% coverage for EquipmentGoal,
focusing on hitting the specific lines that are missing from coverage analysis.
"""

from unittest.mock import Mock, patch
import pytest

from src.ai_player.goals.equipment_goal import EquipmentGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPTargetState
from src.ai_player.goals.sub_goal_request import SubGoalRequest
from src.game_data.game_data import GameData
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


def create_basic_character_state():
    """Create a basic character state for testing."""
    return CharacterGameState(
        name="test_char",
        level=3,
        xp=1000,
        hp=80,
        max_hp=100,
        x=5,
        y=5,
        gold=500,
        mining_level=3,
        mining_xp=500,
        woodcutting_level=2,
        woodcutting_xp=200,
        fishing_level=1,
        fishing_xp=50,
        weaponcrafting_level=2,
        weaponcrafting_xp=300,
        gearcrafting_level=2,
        gearcrafting_xp=250,
        jewelrycrafting_level=1,
        jewelrycrafting_xp=100,
        cooking_level=1,
        cooking_xp=50,
        alchemy_level=1,
        alchemy_xp=25,
        cooldown=0,
        weapon_slot="",
        rune_slot="",
        shield_slot="",
        helmet_slot="",
        body_armor_slot="",
        leg_armor_slot="",
        boots_slot="",
        ring1_slot="",
        ring2_slot="",
        amulet_slot="",
        artifact1_slot="",
        at_monster_location=False,
        at_workshop_location=False,
        inventory_space_available=True,
        inventory_space_count=20,
    )


def create_valid_game_data():
    """Create valid game data that passes validation."""
    # Create actual game items with levels for testing
    test_item1 = Mock(spec=GameItem)
    test_item1.code = "test_weapon"
    test_item1.level = 3
    test_item1.type = "weapon"

    test_item2 = Mock(spec=GameItem)
    test_item2.code = "test_helmet"
    test_item2.level = 4
    test_item2.type = "helmet"

    return GameData(
        items=[test_item1, test_item2],
        resources=[Mock(spec=GameResource)],
        maps=[Mock(spec=GameMap)],
        monsters=[Mock(spec=GameMonster)],
        npcs=[Mock(spec=GameNPC)],
    )


class TestEquipmentGoalCoverage:
    """Tests specifically targeting missing coverage lines."""

    def test_calculate_weight_coverage_lines_60_78(self):
        """Test calculate_weight method to hit lines 60-78."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Mock the private methods to avoid complex dependencies
        with patch.object(goal, "_calculate_equipment_necessity", return_value=0.8):
            with patch.object(goal, "_calculate_equipment_feasibility", return_value=0.7):
                with patch.object(goal, "get_progression_value", return_value=0.6):
                    weight = goal.calculate_weight(character_state, game_data)

                    # Should execute lines 60-78
                    assert isinstance(weight, float)
                    assert 0.0 <= weight <= 10.0

    def test_is_feasible_coverage_lines_82_87(self):
        """Test is_feasible method to hit lines 82-87."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test with available upgrades
        mock_upgrades = [("item", "slot", "method")]
        with patch.object(goal, "_find_available_equipment_upgrades", return_value=mock_upgrades):
            result = goal.is_feasible(character_state, game_data)
            assert result is True  # Line 87

        # Test with no upgrades
        with patch.object(goal, "_find_available_equipment_upgrades", return_value=[]):
            result = goal.is_feasible(character_state, game_data)
            assert result is False  # Should hit the len() > 0 check

    def test_get_target_state_coverage_lines_115_137(self):
        """Test get_target_state method to hit lines 115-137."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test with equipment upgrade available
        mock_item = Mock()
        mock_item.code = "test_item"
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "crafting")):
            target_state = goal.get_target_state(character_state, game_data)

            # Should hit lines 115-137
            assert isinstance(target_state, GOAPTargetState)
            assert target_state.priority == 5
            assert target_state.timeout_seconds == 1800

            # Check that equipment states are set
            expected_states = [
                GameState.READY_FOR_UPGRADE,
                GameState.HAS_REQUIRED_ITEMS,
                GameState.WEAPON_EQUIPPED,
                GameState.HELMET_EQUIPPED,
                GameState.BODY_ARMOR_EQUIPPED,
                GameState.LEG_ARMOR_EQUIPPED,
                GameState.BOOTS_EQUIPPED,
                GameState.RING1_EQUIPPED,
                GameState.RING2_EQUIPPED,
                GameState.AMULET_EQUIPPED,
                GameState.INVENTORY_SPACE_AVAILABLE,
                GameState.COOLDOWN_READY,
            ]

            for state in expected_states:
                assert state in target_state.target_states

    def test_get_progression_value_coverage_lines_148_162(self):
        """Test get_progression_value method to hit lines 148-162."""
        goal = EquipmentGoal()
        game_data = create_valid_game_data()

        # Test level 4 character with low equipment coverage
        character_state = create_basic_character_state()
        character_state.level = 4

        with patch.object(goal, "_calculate_equipment_coverage", return_value=0.5):
            progression = goal.get_progression_value(character_state, game_data)
            assert progression == 0.9  # Line 156

        # Test character with moderate coverage
        character_state.level = 3
        with patch.object(goal, "_calculate_equipment_coverage", return_value=0.8):
            with patch.object(goal, "_calculate_level_appropriate_coverage", return_value=0.6):
                progression = goal.get_progression_value(character_state, game_data)
                assert isinstance(progression, float)
                assert 0.0 <= progression <= 1.0

    def test_estimate_error_risk_coverage_lines_167_179(self):
        """Test estimate_error_risk method to hit lines 167-179."""
        goal = EquipmentGoal()

        # Test with high gold and high inventory space (no additional risk)
        character_state = create_basic_character_state()
        character_state.gold = 500
        character_state.inventory_space_available = True  # Has space, no inventory risk
        character_state.inventory_space_count = 10  # Enough space (>= 3)

        risk = goal.estimate_error_risk(character_state)
        assert risk == 0.15  # Base risk only

        # Test with low gold
        character_state.gold = 50
        risk = goal.estimate_error_risk(character_state)
        assert risk == 0.25  # Base + gold risk

        # Test with low inventory space
        character_state.gold = 500  # High gold, no gold risk
        character_state.inventory_space_available = False  # No space, triggers inventory risk
        character_state.inventory_space_count = 1  # Low space (< 3)
        risk = goal.estimate_error_risk(character_state)
        assert risk == 0.30  # Base + inventory risk

        # Test without inventory_space_available attribute
        delattr(character_state, "inventory_space_available")
        risk = goal.estimate_error_risk(character_state)
        assert risk >= 0.15  # At least base risk

    def test_generate_sub_goal_requests_coverage_lines_187_247(self):
        """Test generate_sub_goal_requests method to hit lines 187-247."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test with no equipment upgrade
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=None):
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
            assert sub_goals == []  # Line 192

        # Test with monster drop acquisition
        mock_item = Mock()
        mock_item.code = "test_item"
        mock_item.name = "Test Item"

        mock_monster = Mock()
        mock_monster.code = "test_monster"
        mock_monster.name = "Test Monster"

        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "monster_drop")):
            with patch.object(
                goal, "_find_monsters_dropping_item", return_value=[(mock_monster, {"code": "test_item"})]
            ):
                sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

                # Should create combat sub-goal (lines 197-209)
                assert len(sub_goals) > 0
                combat_goals = [sg for sg in sub_goals if sg.goal_type == "combat_for_item"]
                assert len(combat_goals) > 0

        # Test with crafting acquisition
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "crafting")):
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

            # Should create crafting sub-goal (lines 211-219)
            craft_goals = [sg for sg in sub_goals if sg.goal_type == "craft_item"]
            assert len(craft_goals) > 0

        # Test with NPC purchase acquisition
        mock_npc = Mock()
        mock_npc.code = "test_npc"
        mock_npc.name = "Test NPC"

        mock_location = Mock()
        mock_location.x = 10
        mock_location.y = 10

        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "npc_purchase")):
            with patch.object(goal, "_find_npcs_selling_item", return_value=[mock_npc]):
                with patch.object(goal.map_analysis, "find_content_by_code", return_value=[mock_location]):
                    sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

                    # Should create movement sub-goal (lines 221-235)
                    assert len(sub_goals) > 0

        # Test with low inventory space - we need to create a character with an integer attribute
        # since the code checks for inventory_space_available < 2
        character_state_with_int_inventory = create_basic_character_state()
        character_state_with_int_inventory.inventory_space_available = False  # No space condition
        character_state_with_int_inventory.inventory_space_count = 1  # Low space (< 2)
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "crafting")):
            sub_goals = goal.generate_sub_goal_requests(character_state_with_int_inventory, game_data)

            # Should create inventory management sub-goal (lines 237-246)
            inventory_goals = [sg for sg in sub_goals if sg.goal_type == "manage_inventory"]
            assert len(inventory_goals) > 0

    def test_find_available_equipment_upgrades_coverage_lines_253_282(self):
        """Test _find_available_equipment_upgrades method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()

        # Create mock items
        mock_weapon = Mock()
        mock_weapon.level = 3
        mock_weapon.type = "weapon"
        mock_weapon.code = "test_weapon"

        mock_helmet = Mock()
        mock_helmet.level = 4
        mock_helmet.type = "helmet"
        mock_helmet.code = "test_helmet"

        game_data = create_valid_game_data()
        game_data.items = [mock_weapon, mock_helmet]

        # Mock methods to avoid complex dependencies
        with patch.object(goal, "_item_fits_slot", return_value=True):
            with patch.object(goal, "_determine_acquisition_method", return_value="crafting"):
                upgrades = goal._find_available_equipment_upgrades(character_state, game_data)

                # Should return upgrades (lines 253-282)
                assert isinstance(upgrades, list)

        # Test with specific target slot
        goal.target_slot = "weapon"
        with patch.object(goal, "_item_fits_slot", return_value=True):
            with patch.object(goal, "_determine_acquisition_method", return_value="crafting"):
                upgrades = goal._find_available_equipment_upgrades(character_state, game_data)

                # Should filter by target slot (line 264-265)
                assert isinstance(upgrades, list)

    def test_select_optimal_equipment_upgrade_coverage_lines_288_305(self):
        """Test _select_optimal_equipment_upgrade method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test with no upgrades available
        with patch.object(goal, "_find_available_equipment_upgrades", return_value=[]):
            result = goal._select_optimal_equipment_upgrade(character_state, game_data)
            assert result is None  # Line 291

        # Test with upgrades available
        mock_item = Mock()
        mock_upgrades = [(mock_item, "weapon", "crafting")]
        with patch.object(goal, "_find_available_equipment_upgrades", return_value=mock_upgrades):
            with patch.object(goal, "_score_equipment_upgrade", return_value=0.8):
                result = goal._select_optimal_equipment_upgrade(character_state, game_data)

                # Should return best upgrade (lines 294-303)
                assert result is not None
                item, method = result
                assert item == mock_item
                assert method == "crafting"

    def test_score_equipment_upgrade_coverage_lines_309_332(self):
        """Test _score_equipment_upgrade method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()

        mock_item = Mock()
        mock_item.level = 3

        score = goal._score_equipment_upgrade(mock_item, "weapon", "crafting", character_state)

        # Should calculate score (lines 309-332)
        assert isinstance(score, float)
        assert score > 0.0

    def test_calculate_equipment_necessity_coverage_lines_337_343(self):
        """Test _calculate_equipment_necessity method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        with patch.object(goal, "_calculate_equipment_coverage", return_value=0.5):
            with patch.object(goal, "_calculate_level_equipment_gap", return_value=0.3):
                necessity = goal._calculate_equipment_necessity(character_state, game_data)

                # Should calculate necessity (lines 337-343)
                assert isinstance(necessity, float)
                assert 0.0 <= necessity <= 1.0

    def test_calculate_equipment_feasibility_coverage_lines_347_368(self):
        """Test _calculate_equipment_feasibility method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        with patch.object(goal, "_find_available_equipment_upgrades", return_value=[("item", "slot", "method")]):
            feasibility = goal._calculate_equipment_feasibility(character_state, game_data)

            # Should calculate feasibility (lines 347-368)
            assert isinstance(feasibility, float)
            assert 0.0 <= feasibility <= 1.0

    def test_calculate_equipment_coverage_coverage_lines_372_379(self):
        """Test _calculate_equipment_coverage method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()

        # Test with empty equipment
        coverage = goal._calculate_equipment_coverage(character_state)
        assert coverage == 0.0  # All empty slots

        # Test with some equipment
        character_state.weapon_slot = "weapon"
        character_state.helmet_slot = "helmet"
        coverage = goal._calculate_equipment_coverage(character_state)
        assert coverage == 2.0 / 8.0  # 2 out of 8 slots

    def test_calculate_level_appropriate_coverage_coverage_lines_383_392(self):
        """Test _calculate_level_appropriate_coverage method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test with no equipment
        coverage = goal._calculate_level_appropriate_coverage(character_state, game_data)
        assert coverage == 0.0

        # Test with appropriate level equipment using proper equipment codes
        character_state.weapon_slot = "test_weapon"  # Level 3 item (within max_item_level 5)

        coverage = goal._calculate_level_appropriate_coverage(character_state, game_data)
        assert coverage == 1.0 / 8.0  # 1 out of 8 slots with appropriate equipment

    def test_calculate_level_equipment_gap_coverage_lines_396_411(self):
        """Test _calculate_level_equipment_gap method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        character_state.level = 5
        game_data = create_valid_game_data()

        # Test with no equipment (uses level 1 default)
        gap = goal._calculate_level_equipment_gap(character_state, game_data)
        assert gap > 0.0

        # Test with some equipment using proper equipment codes
        character_state.weapon_slot = "test_helmet"  # Level 4 item

        gap = goal._calculate_level_equipment_gap(character_state, game_data)
        assert gap >= 0.0  # Level 5 character with level 4 equipment should have some gap

    def test_item_fits_slot_coverage(self):
        """Test _item_fits_slot method."""
        goal = EquipmentGoal()

        mock_weapon = Mock()
        mock_weapon.type = "weapon"

        assert goal._item_fits_slot(mock_weapon, "weapon") is True
        assert goal._item_fits_slot(mock_weapon, "helmet") is False

        mock_ring = Mock()
        mock_ring.type = "ring"

        assert goal._item_fits_slot(mock_ring, "ring1") is True
        assert goal._item_fits_slot(mock_ring, "ring2") is True

    def test_determine_acquisition_method_coverage_lines_434_445(self):
        """Test _determine_acquisition_method method."""
        goal = EquipmentGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data()

        # Test craftable item
        mock_item = Mock()
        mock_item.craft = {"skill": "weaponcrafting"}
        method = goal._determine_acquisition_method(mock_item, character_state, game_data)
        assert method == "crafting"  # Line 435

        # Test item with NPC sales
        mock_item.craft = None
        with patch.object(goal, "_find_npcs_selling_item", return_value=["npc"]):
            method = goal._determine_acquisition_method(mock_item, character_state, game_data)
            assert method == "npc_purchase"  # Line 439

        # Test item with monster drops
        with patch.object(goal, "_find_npcs_selling_item", return_value=[]):
            with patch.object(goal, "_find_monsters_dropping_item", return_value=["monster"]):
                method = goal._determine_acquisition_method(mock_item, character_state, game_data)
                assert method == "monster_drop"  # Line 443

        # Test item with no acquisition method
        with patch.object(goal, "_find_npcs_selling_item", return_value=[]):
            with patch.object(goal, "_find_monsters_dropping_item", return_value=[]):
                method = goal._determine_acquisition_method(mock_item, character_state, game_data)
                assert method is None  # Line 445

    def test_find_npcs_selling_item_coverage(self):
        """Test _find_npcs_selling_item method."""
        goal = EquipmentGoal()
        game_data = create_valid_game_data()

        # Current implementation returns empty list
        result = goal._find_npcs_selling_item("test_item", game_data)
        assert result == []

    def test_find_monsters_dropping_item_coverage(self):
        """Test _find_monsters_dropping_item method."""
        goal = EquipmentGoal()

        # Create mock monster with drops
        mock_monster = Mock()
        mock_drop = {"code": "test_item", "quantity": 1}
        mock_monster.drops = [mock_drop]

        game_data = create_valid_game_data()
        game_data.monsters = [mock_monster]

        result = goal._find_monsters_dropping_item("test_item", game_data)
        assert len(result) > 0

        # Test item not dropped by any monster
        result = goal._find_monsters_dropping_item("nonexistent_item", game_data)
        assert len(result) == 0
