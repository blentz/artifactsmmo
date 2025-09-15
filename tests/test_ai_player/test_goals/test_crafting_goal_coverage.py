"""
Additional tests to achieve 100% coverage for CraftingGoal

This module contains targeted tests to cover the specific lines that are missing
from the existing test suite, focusing on edge cases and error conditions.
"""

from unittest.mock import Mock, patch
import pytest

from src.ai_player.goals.crafting_goal import CraftingGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPTargetState
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
        weapon_slot="iron_sword",
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
        at_workshop_location=False
    )


def create_valid_game_data_with_maps():
    """Create valid game data that passes validation."""
    return GameData(
        items=[Mock(spec=GameItem)],
        resources=[Mock(spec=GameResource)],
        maps=[Mock(spec=GameMap)],  # Need at least one map for validation
        monsters=[Mock(spec=GameMonster)],
        npcs=[Mock(spec=GameNPC)]
    )


class TestCraftingGoalCoverageGaps:
    """Tests specifically targeting missing coverage lines."""

    def test_is_feasible_no_craftable_recipes_coverage_line_80(self):
        """Test line 80: return False when no craftable recipes exist."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Mock to return empty list of craftable recipes
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', return_value=[]):
            result = goal.is_feasible(character_state, game_data)
            assert result is False  # This should hit line 80

    def test_is_feasible_with_obtainable_materials_coverage_line_87(self):
        """Test line 87: return True when feasible recipes with obtainable materials exist."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Create mock recipe analysis
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.feasible = True
        
        # Mock the material obtainability check to return True
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', 
                         return_value=[(mock_item, mock_analysis)]):
            with patch.object(goal, '_can_obtain_materials', return_value=True):
                result = goal.is_feasible(character_state, game_data)
                assert result is True  # This should hit line 87

    def test_is_feasible_borderline_skills_with_materials_coverage_line_95(self):
        """Test line 95: return True for borderline feasible recipes with obtainable materials."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        character_state.weaponcrafting_level = 2  # Will be borderline for level 3 requirement
        game_data = create_valid_game_data_with_maps()
        
        # Create mock recipe that's not quite feasible but close
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.feasible = False  # Not immediately feasible
        mock_analysis.recipe_structure.skill_required = "weaponcrafting"
        mock_analysis.recipe_structure.level_required = 3  # One level above character
        
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', 
                         return_value=[(mock_item, mock_analysis)]):
            with patch.object(goal, '_can_obtain_materials', return_value=True):
                result = goal.is_feasible(character_state, game_data)
                assert result is True  # This should hit line 95

    def test_get_target_state_no_workshop_coverage_line_133(self):
        """Test line 133: return empty GOAPTargetState when no workshop is found."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Mock to return a valid recipe but no workshop locations
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.recipe_structure.skill_required = "weaponcrafting"
        
        with patch.object(goal, '_select_optimal_recipe', return_value=(mock_item, mock_analysis)):
            with patch.object(goal.map_analysis, 'find_content_by_code', return_value=[]):
                target_state = goal.get_target_state(character_state, game_data)
                
                # Should return empty target state - hitting line 133
                assert target_state.target_states == {}
                assert target_state.priority == 1
                assert target_state.timeout_seconds is None

    def test_get_target_state_fallback_workshop_coverage_line_149(self):
        """Test line 149: fallback to first workshop when distance calculation fails."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Create mock workshop location
        mock_workshop = Mock()
        mock_workshop.x = 10
        mock_workshop.y = 10
        
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.recipe_structure.skill_required = "weaponcrafting"
        
        with patch.object(goal, '_select_optimal_recipe', return_value=(mock_item, mock_analysis)):
            with patch.object(goal.map_analysis, 'find_content_by_code', return_value=[mock_workshop]):
                with patch.object(goal.map_analysis, 'calculate_travel_efficiency', return_value={}):
                    # Empty distances dict should trigger fallback to workshop_locations[0]
                    target_state = goal.get_target_state(character_state, game_data)
                    
                    # Should use fallback workshop - hitting line 149
                    assert target_state.target_states[GameState.CURRENT_X] == 10
                    assert target_state.target_states[GameState.CURRENT_Y] == 10

    def test_select_optimal_recipe_no_scored_recipes_coverage_line_300(self):
        """Test line 300: return None when no scored recipes exist."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Mock to return empty craftable recipes after filtering
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', return_value=[]):
            result = goal._select_optimal_recipe(character_state, game_data)
            assert result is None  # This should hit line 300


    def test_can_obtain_materials_all_available_coverage_line_413(self):
        """Test line 413: return True when all materials can be obtained."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Create mock analysis with materials
        mock_analysis = Mock()
        mock_analysis.recipe_structure.materials_needed = [
            {"code": "iron", "quantity": 2},
            {"code": "coal", "quantity": 1}
        ]
        
        # Mock individual material checks to return True
        with patch.object(goal, '_can_obtain_material', return_value=True):
            result = goal._can_obtain_materials(character_state, mock_analysis, game_data)
            assert result is True  # This should hit line 413

    def test_can_obtain_material_with_locations_coverage_line_426(self):
        """Test line 426: return True when resource locations are found."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Create mock resource with drop
        mock_drop = Mock()
        mock_drop.code = "iron"
        
        mock_resource = Mock()
        mock_resource.skill = "mining"
        mock_resource.level = 2  # Character can access (level 3 mining)
        mock_resource.drops = [mock_drop]
        
        game_data.resources = [mock_resource]
        
        # Mock map analysis to return locations
        with patch.object(goal.map_analysis, 'find_content_by_code', return_value=["some_location"]):
            result = goal._can_obtain_material("iron", character_state, game_data)
            assert result is True  # This should hit line 426


class TestCraftingGoalEdgeCaseIntegration:
    """Integration tests for edge cases to ensure complete coverage."""

    def test_complete_workflow_with_all_edge_cases(self):
        """Test complete workflow hitting multiple edge case paths."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Test sequence that should hit multiple coverage lines
        
        # 1. Test with no craftable recipes first
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', return_value=[]):
            assert goal.is_feasible(character_state, game_data) is False
        
        # 2. Test with feasible recipe but no workshop
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.feasible = True
        
        with patch.object(goal, '_select_optimal_recipe', return_value=(mock_item, mock_analysis)):
            with patch.object(goal.map_analysis, 'find_content_by_code', return_value=[]):
                target_state = goal.get_target_state(character_state, game_data)
                assert target_state.target_states == {}
        
        # 3. Test material obtainability
        with patch.object(goal, '_can_obtain_materials', return_value=True):
            with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', 
                             return_value=[(mock_item, mock_analysis)]):
                assert goal.is_feasible(character_state, game_data) is True

    def test_workshop_distance_calculation_edge_cases(self):
        """Test workshop selection with various distance calculation scenarios."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Create multiple workshop locations
        workshop1 = Mock()
        workshop1.x = 10
        workshop1.y = 10
        
        workshop2 = Mock()
        workshop2.x = 20
        workshop2.y = 20
        
        mock_item = Mock()
        mock_analysis = Mock()
        mock_analysis.recipe_structure.skill_required = "weaponcrafting"
        
        with patch.object(goal, '_select_optimal_recipe', return_value=(mock_item, mock_analysis)):
            with patch.object(goal.map_analysis, 'find_content_by_code', 
                             return_value=[workshop1, workshop2]):
                
                # Test empty distances (should use fallback)
                with patch.object(goal.map_analysis, 'calculate_travel_efficiency', return_value={}):
                    target_state = goal.get_target_state(character_state, game_data)
                    # Should use first workshop as fallback
                    assert target_state.target_states[GameState.CURRENT_X] == 10
                
                # Test with valid distances  
                distances = {(10, 10): 0.8, (20, 20): 0.5}
                with patch.object(goal.map_analysis, 'calculate_travel_efficiency', 
                                 return_value=distances):
                    target_state = goal.get_target_state(character_state, game_data)
                    # Should use best efficiency workshop (10, 10)
                    assert target_state.target_states[GameState.CURRENT_X] == 10

    def test_material_obtainability_complex_scenarios(self):
        """Test complex material obtainability scenarios."""
        goal = CraftingGoal()
        character_state = create_basic_character_state()
        game_data = create_valid_game_data_with_maps()
        
        # Test with multiple resources and drops
        iron_drop = Mock()
        iron_drop.code = "iron"
        
        coal_drop = Mock()
        coal_drop.code = "coal"
        
        # Resource with iron drops
        iron_resource = Mock()
        iron_resource.skill = "mining"
        iron_resource.level = 2
        iron_resource.drops = [iron_drop]
        iron_resource.code = "iron_rock"
        
        # Resource with coal drops  
        coal_resource = Mock()
        coal_resource.skill = "mining"
        coal_resource.level = 3
        coal_resource.drops = [coal_drop]
        coal_resource.code = "coal_rock"
        
        game_data.resources = [iron_resource, coal_resource]
        
        # Test successful material obtainability
        locations = ["location1"]
        with patch.object(goal.map_analysis, 'find_content_by_code', return_value=locations):
            assert goal._can_obtain_material("iron", character_state, game_data) is True
            assert goal._can_obtain_material("coal", character_state, game_data) is True
        
        # Test with no locations available
        with patch.object(goal.map_analysis, 'find_content_by_code', return_value=[]):
            assert goal._can_obtain_material("iron", character_state, game_data) is False
        
        # Test with insufficient skill level
        character_state.mining_level = 1  # Too low for coal (level 3)
        with patch.object(goal.map_analysis, 'find_content_by_code', return_value=locations):
            assert goal._can_obtain_material("coal", character_state, game_data) is False