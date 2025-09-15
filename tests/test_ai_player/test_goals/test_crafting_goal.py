"""
Comprehensive tests for CraftingGoal

This module tests the CraftingGoal class comprehensively to achieve 100% coverage,
including all edge cases, error conditions, and complex scenarios that arise when
crafting level-appropriate equipment for the level 5 progression goal.
"""

from unittest.mock import Mock, patch
import pytest

from src.ai_player.goals.crafting_goal import CraftingGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPTargetState
from src.ai_player.goals.sub_goal_request import SubGoalRequest
from src.game_data.game_data import GameData
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
from tests.fixtures.character_states import CharacterStateFixtures


def create_test_character_state():
    """Create a comprehensive test character state for crafting scenarios."""
    return CharacterGameState(
        name="test_crafter",
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


def create_craftable_item(code: str, name: str, level: int, item_type: str, skill: str, skill_level: int, materials: list):
    """Create a craftable test item."""
    item = Mock(spec=GameItem)
    item.code = code
    item.name = name
    item.level = level
    item.type = item_type
    item.craft = {
        'skill': skill,
        'level': skill_level,
        'materials': materials
    }
    return item


def create_non_craftable_item(code: str, name: str, level: int, item_type: str):
    """Create a non-craftable test item."""
    item = Mock(spec=GameItem)
    item.code = code
    item.name = name
    item.level = level
    item.type = item_type
    item.craft = None
    return item


def create_workshop_map(x: int, y: int, skill: str):
    """Create a workshop map location."""
    content = Mock()
    content.type = "workshop"
    content.code = skill
    
    workshop_map = Mock(spec=GameMap)
    workshop_map.x = x
    workshop_map.y = y
    workshop_map.content = content
    return workshop_map


def create_drop_object(code: str, quantity: int = 1):
    """Create a drop object with .code attribute."""
    drop = Mock()
    drop.code = code
    drop.quantity = quantity
    return drop


def create_resource_with_drops(code: str, skill: str, level: int, drops: list):
    """Create a resource that drops specified materials."""
    resource = Mock(spec=GameResource)
    resource.code = code
    resource.skill = skill
    resource.level = level
    # Create drop objects with .code attributes (not dictionaries)
    resource.drops = [create_drop_object(drop["code"], drop.get("quantity", 1)) for drop in drops]
    return resource


def create_resource_map(x: int, y: int, resource_code: str):
    """Create a map location with a resource."""
    content = Mock()
    content.type = "resource"
    content.code = resource_code
    
    resource_map = Mock(spec=GameMap)
    resource_map.x = x
    resource_map.y = y
    resource_map.content = content
    return resource_map


def create_comprehensive_game_data():
    """Create comprehensive game data for crafting tests."""
    # Craftable items of various levels and types
    items = [
        create_craftable_item("iron_sword", "Iron Sword", 3, "weapon", "weaponcrafting", 2, 
                             [{"code": "iron", "quantity": 3}, {"code": "coal", "quantity": 1}]),
        create_craftable_item("steel_helmet", "Steel Helmet", 4, "helmet", "gearcrafting", 3,
                             [{"code": "steel", "quantity": 2}, {"code": "iron", "quantity": 1}]),
        create_craftable_item("copper_ring", "Copper Ring", 1, "ring", "jewelrycrafting", 1,
                             [{"code": "copper", "quantity": 2}]),
        create_craftable_item("mithril_sword", "Mithril Sword", 5, "weapon", "weaponcrafting", 4,
                             [{"code": "mithril", "quantity": 4}, {"code": "coal", "quantity": 2}]),
        create_craftable_item("legendary_sword", "Legendary Sword", 10, "weapon", "weaponcrafting", 8,
                             [{"code": "adamantite", "quantity": 5}, {"code": "coal", "quantity": 3}]),
        create_non_craftable_item("health_potion", "Health Potion", 1, "consumable"),
        create_non_craftable_item("monster_drop", "Monster Drop", 2, "material"),
    ]
    
    # Resources that provide crafting materials
    resources = [
        create_resource_with_drops("iron_rock", "mining", 2, [{"code": "iron", "quantity": 1}]),
        create_resource_with_drops("coal_rock", "mining", 3, [{"code": "coal", "quantity": 1}]),
        create_resource_with_drops("copper_rock", "mining", 1, [{"code": "copper", "quantity": 1}]),
        create_resource_with_drops("steel_rock", "mining", 4, [{"code": "steel", "quantity": 1}]),
        create_resource_with_drops("mithril_rock", "mining", 5, [{"code": "mithril", "quantity": 1}]),
    ]
    
    # Maps with workshops and resource locations
    maps = [
        create_workshop_map(10, 10, "weaponcrafting"),
        create_workshop_map(15, 15, "gearcrafting"),
        create_workshop_map(20, 20, "jewelrycrafting"),
        create_resource_map(5, 5, "iron_rock"),
        create_resource_map(8, 8, "coal_rock"),
        create_resource_map(3, 3, "copper_rock"),
        create_resource_map(12, 12, "steel_rock"),
        create_resource_map(25, 25, "mithril_rock"),
    ]
    
    return GameData(
        items=items,
        resources=resources,
        maps=maps,
        monsters=[Mock(spec=GameMonster)],
        npcs=[Mock(spec=GameNPC)]
    )


class TestCraftingGoalInitialization:
    """Test CraftingGoal initialization and basic properties."""
    
    def test_default_initialization(self):
        """Test default CraftingGoal initialization."""
        goal = CraftingGoal()
        
        assert goal.target_item_code is None
        assert goal.max_result_level == 5
        assert goal.crafting_analysis is not None
        assert goal.map_analysis is not None
    
    def test_initialization_with_target_item(self):
        """Test CraftingGoal initialization with specific target item."""
        goal = CraftingGoal(target_item_code="iron_sword")
        
        assert goal.target_item_code == "iron_sword"
        assert goal.max_result_level == 5
    
    def test_initialization_with_custom_max_level(self):
        """Test CraftingGoal initialization with custom max level."""
        goal = CraftingGoal(max_result_level=3)
        
        assert goal.target_item_code is None
        assert goal.max_result_level == 3
    
    def test_initialization_with_all_parameters(self):
        """Test CraftingGoal initialization with all parameters."""
        goal = CraftingGoal(target_item_code="steel_helmet", max_result_level=4)
        
        assert goal.target_item_code == "steel_helmet"
        assert goal.max_result_level == 4


class TestCraftingGoalWeight:
    """Test CraftingGoal weight calculation using multi-factor scoring."""
    
    def test_calculate_weight_basic_scenario(self):
        """Test weight calculation for basic crafting scenario."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        weight = goal.calculate_weight(character_state, game_data)
        
        assert isinstance(weight, float)
        assert 0.0 <= weight <= 10.0
    
    def test_calculate_weight_empty_game_data(self):
        """Test weight calculation with empty game data."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        empty_game_data = GameData()
        
        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            goal.calculate_weight(character_state, empty_game_data)
    
    def test_calculate_weight_high_necessity_scenario(self):
        """Test weight calculation when crafting is highly necessary."""
        goal = CraftingGoal()
        
        # Create character with no equipment (high necessity)
        character_state = create_test_character_state()
        character_state.weapon_slot = ""
        character_state.helmet_slot = ""
        character_state.body_armor_slot = ""
        character_state.leg_armor_slot = ""
        character_state.boots_slot = ""
        character_state.ring1_slot = ""
        character_state.ring2_slot = ""
        character_state.amulet_slot = ""
        
        game_data = create_comprehensive_game_data()
        
        weight = goal.calculate_weight(character_state, game_data)
        
        # Should have higher weight due to high necessity
        assert weight > 5.0
    
    def test_calculate_weight_low_skills_scenario(self):
        """Test weight calculation with low crafting skills."""
        goal = CraftingGoal()
        
        # Create character with very low crafting skills
        character_state = create_test_character_state()
        character_state.weaponcrafting_level = 1
        character_state.gearcrafting_level = 1
        character_state.jewelrycrafting_level = 1
        
        game_data = create_comprehensive_game_data()
        
        weight = goal.calculate_weight(character_state, game_data)
        
        # Should still be positive but potentially lower due to feasibility
        assert weight > 0.0
    
    def test_calculate_weight_level_5_character(self):
        """Test weight calculation for level 5 character."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.level = 5
        
        game_data = create_comprehensive_game_data()
        
        weight = goal.calculate_weight(character_state, game_data)
        
        # Should still have value even at level 5 for appropriate gear
        assert weight > 0.0


class TestCraftingGoalFeasibility:
    """Test CraftingGoal feasibility checks."""
    
    def test_is_feasible_with_good_skills(self):
        """Test feasibility with adequate crafting skills."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        result = goal.is_feasible(character_state, game_data)
        
        assert isinstance(result, bool)
        # Should be feasible with good crafting skills and available materials
        assert result is True
    
    def test_is_feasible_empty_game_data(self):
        """Test feasibility with empty game data."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        empty_game_data = GameData()
        
        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            goal.is_feasible(character_state, empty_game_data)
    
    def test_is_feasible_no_craftable_recipes(self):
        """Test feasibility when no craftable recipes are available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Create game data with only non-craftable items
        game_data = GameData(
            items=[create_non_craftable_item("potion", "Potion", 1, "consumable")],
            resources=[Mock(spec=GameResource)],  # Need at least one resource for validation
            maps=[Mock(spec=GameMap)],  # Need at least one map for validation
            monsters=[Mock(spec=GameMonster)],
            npcs=[Mock(spec=GameNPC)]
        )
        
        result = goal.is_feasible(character_state, game_data)
        
        assert result is False
    
    def test_is_feasible_very_low_skills(self):
        """Test feasibility with very low crafting skills."""
        goal = CraftingGoal()
        
        # Create character with level 1 in all crafting skills
        character_state = create_test_character_state()
        character_state.weaponcrafting_level = 1
        character_state.gearcrafting_level = 1
        character_state.jewelrycrafting_level = 1
        
        game_data = create_comprehensive_game_data()
        
        result = goal.is_feasible(character_state, game_data)
        
        # Should still be feasible due to level 1 copper ring recipe
        assert result is True
    
    def test_is_feasible_borderline_skills(self):
        """Test feasibility with borderline skill levels."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        # Mock the analysis to return borderline feasible recipes
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes') as mock_find:
            mock_item = Mock()
            mock_item.name = "Test Item"
            mock_analysis = Mock()
            mock_analysis.feasible = False
            mock_analysis.recipe_structure.skill_required = "weaponcrafting"
            mock_analysis.recipe_structure.level_required = 3
            mock_analysis.recipe_structure.materials_needed = []  # Make it iterable
            
            character_state.weaponcrafting_level = 2  # One level below required
            
            mock_find.return_value = [(mock_item, mock_analysis)]
            
            result = goal.is_feasible(character_state, game_data)
            
            # Should be feasible if within 1 level of requirement
            assert result is True


class TestCraftingGoalTargetState:
    """Test CraftingGoal target state generation."""
    
    def test_get_target_state_basic_scenario(self):
        """Test target state generation for basic crafting scenario."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        target_state = goal.get_target_state(character_state, game_data)
        
        assert isinstance(target_state, GOAPTargetState)
        assert isinstance(target_state.target_states, dict)
        assert target_state.priority == 7
        assert target_state.timeout_seconds == 900
    
    def test_get_target_state_empty_game_data(self):
        """Test target state generation with empty game data."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        empty_game_data = GameData()
        
        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            goal.get_target_state(character_state, empty_game_data)
    
    def test_get_target_state_no_recipes(self):
        """Test target state when no recipes are available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        with patch.object(goal, '_select_optimal_recipe', return_value=None):
            game_data = create_comprehensive_game_data()
            
            target_state = goal.get_target_state(character_state, game_data)
            
            assert target_state.target_states == {}
            assert target_state.priority == 1
            assert target_state.timeout_seconds is None
    
    def test_get_target_state_no_workshop(self):
        """Test target state when no workshop is available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Create game data without workshops
        mock_map = Mock(spec=GameMap)
        mock_map.content = None  # No content to ensure no workshops
        
        game_data = GameData(
            items=[create_craftable_item("iron_sword", "Iron Sword", 3, "weapon", "weaponcrafting", 2, [])],
            resources=[Mock(spec=GameResource)],  # Need at least one resource for validation
            maps=[mock_map],  # Map with no content for validation
            monsters=[Mock(spec=GameMonster)],
            npcs=[Mock(spec=GameNPC)]
        )
        
        target_state = goal.get_target_state(character_state, game_data)
        
        # Should return empty target state if no workshop available
        assert target_state.target_states == {}
        assert target_state.priority == 1
    
    def test_get_target_state_with_specific_target(self):
        """Test target state generation with specific target item."""
        goal = CraftingGoal(target_item_code="iron_sword")
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        target_state = goal.get_target_state(character_state, game_data)
        
        assert isinstance(target_state, GOAPTargetState)
        # Should include workshop location and crafting materials states
        expected_states = [
            GameState.AT_WORKSHOP_LOCATION,
            GameState.HAS_CRAFTING_MATERIALS,
            GameState.HAS_REQUIRED_ITEMS,
            GameState.CAN_CRAFT,
            GameState.GAINED_XP,
            GameState.INVENTORY_SPACE_AVAILABLE,
            GameState.COOLDOWN_READY,
            GameState.CURRENT_X,
            GameState.CURRENT_Y
        ]
        
        for expected_state in expected_states:
            assert expected_state in target_state.target_states


class TestCraftingGoalProgression:
    """Test CraftingGoal progression value calculation."""
    
    def test_get_progression_value_level_3(self):
        """Test progression value for level 3 character."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        character_state.level = 3
        
        progression_value = goal.get_progression_value(character_state)
        
        assert isinstance(progression_value, float)
        assert 0.0 <= progression_value <= 1.0
        # Should have good progression value for character below level 5
        assert progression_value > 0.5
    
    def test_get_progression_value_level_5(self):
        """Test progression value for level 5 character."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        character_state.level = 5
        
        progression_value = goal.get_progression_value(character_state)
        
        assert isinstance(progression_value, float)
        assert 0.0 <= progression_value <= 1.0
        # Should still have some value for level-appropriate gear
        assert progression_value == 0.6
    
    def test_get_progression_value_high_equipment_need(self):
        """Test progression value with high equipment need."""
        goal = CraftingGoal()
        
        # Create character with no equipment
        character_state = create_test_character_state()
        character_state.level = 2
        character_state.weapon_slot = ""
        character_state.helmet_slot = ""
        character_state.body_armor_slot = ""
        character_state.leg_armor_slot = ""
        character_state.boots_slot = ""
        character_state.ring1_slot = ""
        character_state.ring2_slot = ""
        character_state.amulet_slot = ""
        
        progression_value = goal.get_progression_value(character_state)
        
        # Should have higher progression value due to equipment need
        assert progression_value > 0.7


class TestCraftingGoalErrorRisk:
    """Test CraftingGoal error risk estimation."""
    
    def test_estimate_error_risk_basic(self):
        """Test error risk estimation for basic scenario."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        error_risk = goal.estimate_error_risk(character_state)
        
        assert isinstance(error_risk, float)
        assert 0.0 <= error_risk <= 1.0
        # Crafting should have relatively low base risk
        assert error_risk <= 0.5
    
    def test_estimate_error_risk_low_skills(self):
        """Test error risk estimation with low crafting skills."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.weaponcrafting_level = 2  # Below threshold
        character_state.gearcrafting_level = 2    # Below threshold
        
        error_risk = goal.estimate_error_risk(character_state)
        
        # Should have higher risk due to low skills
        assert error_risk > 0.3
    
    def test_estimate_error_risk_good_skills(self):
        """Test error risk estimation with good crafting skills."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.weaponcrafting_level = 5
        character_state.gearcrafting_level = 4
        
        error_risk = goal.estimate_error_risk(character_state)
        
        # Should have base risk only
        assert error_risk == 0.2


class TestCraftingGoalSubGoals:
    """Test CraftingGoal sub-goal generation."""
    
    def test_generate_sub_goal_requests_basic(self):
        """Test basic sub-goal generation for crafting."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
        
        assert isinstance(sub_goals, list)
        # Should generate sub-goals for materials and workshop movement
        assert len(sub_goals) > 0
    
    def test_generate_sub_goal_requests_no_recipe(self):
        """Test sub-goal generation when no recipe is available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        with patch.object(goal, '_select_optimal_recipe', return_value=None):
            game_data = create_comprehensive_game_data()
            
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
            
            assert sub_goals == []
    
    def test_generate_sub_goal_requests_at_workshop(self):
        """Test sub-goal generation when already at workshop."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.at_workshop_location = True
        
        game_data = create_comprehensive_game_data()
        
        sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
        
        # Should not generate movement sub-goal if already at workshop
        movement_goals = [sg for sg in sub_goals if hasattr(sg, 'goal_type') and 'move' in sg.goal_type]
        assert len(movement_goals) == 0
    
    def test_generate_sub_goal_requests_material_requests(self):
        """Test that material gathering sub-goals are generated."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
        
        # Should include material requests
        obtain_item_goals = [sg for sg in sub_goals if isinstance(sg, SubGoalRequest) and hasattr(sg, 'parameters') and 'item_code' in sg.parameters]
        assert len(obtain_item_goals) > 0


class TestCraftingGoalPrivateMethods:
    """Test CraftingGoal private methods for complete coverage."""
    
    def test_select_optimal_recipe_with_target(self):
        """Test optimal recipe selection with specific target."""
        goal = CraftingGoal(target_item_code="iron_sword")
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        result = goal._select_optimal_recipe(character_state, game_data)
        
        assert result is not None
        item, analysis = result
        assert item.code == "iron_sword"
    
    def test_select_optimal_recipe_without_target(self):
        """Test optimal recipe selection without specific target."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        result = goal._select_optimal_recipe(character_state, game_data)
        
        assert result is not None
        item, analysis = result
        assert hasattr(item, 'code')
        assert hasattr(item, 'name')
    
    def test_select_optimal_recipe_no_feasible(self):
        """Test optimal recipe selection when no feasible recipes exist."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Mock to return no feasible recipes
        with patch.object(goal.crafting_analysis, 'find_level_appropriate_recipes', return_value=[]):
            game_data = create_comprehensive_game_data()
            
            result = goal._select_optimal_recipe(character_state, game_data)
            
            assert result is None
    
    def test_score_recipe_value_equipment_items(self):
        """Test recipe scoring for equipment items."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Create mock item and analysis
        item = Mock()
        item.type = "weapon"
        item.level = 3
        
        analysis = Mock()
        analysis.feasible = True
        analysis.recipe_structure.materials_needed = [{"code": "iron", "quantity": 2}]
        
        score = goal._score_recipe_value(item, analysis, character_state)
        
        assert isinstance(score, float)
        assert score > 0.0
        # Equipment items should get bonus points
        assert score >= 0.5
    
    def test_score_recipe_value_level_appropriate(self):
        """Test recipe scoring for level-appropriate items."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        character_state.level = 3
        
        item = Mock()
        item.type = "weapon"
        item.level = 3  # Same as character level
        
        analysis = Mock()
        analysis.feasible = True
        analysis.recipe_structure.materials_needed = []
        
        score = goal._score_recipe_value(item, analysis, character_state)
        
        # Should get high level appropriateness score
        assert score > 0.8
    
    def test_calculate_crafting_necessity(self):
        """Test crafting necessity calculation."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        necessity = goal._calculate_crafting_necessity(character_state, game_data)
        
        assert isinstance(necessity, float)
        assert 0.0 <= necessity <= 1.0
    
    def test_calculate_crafting_feasibility(self):
        """Test crafting feasibility calculation."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        feasibility = goal._calculate_crafting_feasibility(character_state, game_data)
        
        assert isinstance(feasibility, float)
        assert 0.0 <= feasibility <= 1.0
    
    def test_assess_equipment_need_empty_slots(self):
        """Test equipment need assessment with empty slots."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.weapon_slot = ""
        character_state.helmet_slot = ""
        character_state.body_armor_slot = ""
        character_state.leg_armor_slot = ""
        character_state.boots_slot = ""
        character_state.ring1_slot = ""
        character_state.ring2_slot = ""
        character_state.amulet_slot = ""
        
        equipment_need = goal._assess_equipment_need(character_state)
        
        # Should be 1.0 for completely empty equipment
        assert equipment_need == 1.0
    
    def test_assess_equipment_need_full_equipment(self):
        """Test equipment need assessment with full equipment."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.weapon_slot = "sword"
        character_state.helmet_slot = "helmet"
        character_state.body_armor_slot = "armor"
        character_state.leg_armor_slot = "pants"
        character_state.boots_slot = "boots"
        character_state.ring1_slot = "ring1"
        character_state.ring2_slot = "ring2"
        character_state.amulet_slot = "amulet"
        
        equipment_need = goal._assess_equipment_need(character_state)
        
        # Should be 0.0 for fully equipped character
        assert equipment_need == 0.0
    
    def test_get_character_skill_level_all_skills(self):
        """Test getting character skill levels for all crafting skills."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Test all skill mappings
        assert goal._get_character_skill_level(character_state, "mining") == 3
        assert goal._get_character_skill_level(character_state, "woodcutting") == 2
        assert goal._get_character_skill_level(character_state, "fishing") == 1
        assert goal._get_character_skill_level(character_state, "weaponcrafting") == 2
        assert goal._get_character_skill_level(character_state, "gearcrafting") == 2
        assert goal._get_character_skill_level(character_state, "jewelrycrafting") == 1
        assert goal._get_character_skill_level(character_state, "cooking") == 1
        assert goal._get_character_skill_level(character_state, "alchemy") == 1
        
        # Test unknown skill
        assert goal._get_character_skill_level(character_state, "unknown_skill") == 1
    
    def test_can_obtain_materials_all_available(self):
        """Test material obtainability when all materials are available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        # Mock analysis with materials that exist in game data
        analysis = Mock()
        analysis.recipe_structure.materials_needed = [
            {"code": "iron", "quantity": 2},
            {"code": "coal", "quantity": 1}
        ]
        
        result = goal._can_obtain_materials(character_state, analysis, game_data)
        
        assert result is True
    
    def test_can_obtain_materials_some_unavailable(self):
        """Test material obtainability when some materials are unavailable."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        # Mock analysis with materials that don't exist
        analysis = Mock()
        analysis.recipe_structure.materials_needed = [
            {"code": "iron", "quantity": 2},
            {"code": "unobtainium", "quantity": 1}  # Doesn't exist
        ]
        
        result = goal._can_obtain_materials(character_state, analysis, game_data)
        
        assert result is False
    
    def test_can_obtain_material_individual(self):
        """Test individual material obtainability."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        # Test obtainable material
        result = goal._can_obtain_material("iron", character_state, game_data)
        assert result is True
        
        # Test unobtainable material
        result = goal._can_obtain_material("nonexistent", character_state, game_data)
        assert result is False
    
    def test_can_obtain_material_insufficient_skill(self):
        """Test material obtainability with insufficient skill level."""
        goal = CraftingGoal()
        
        character_state = create_test_character_state()
        character_state.mining_level = 1  # Too low for steel
        
        game_data = create_comprehensive_game_data()
        
        result = goal._can_obtain_material("steel", character_state, game_data)
        
        # Should be False because character mining level (1) < steel resource level (4)
        assert result is False


class TestCraftingGoalIntegration:
    """Integration tests for CraftingGoal with real-world scenarios."""
    
    def test_full_crafting_workflow_iron_sword(self):
        """Test complete crafting workflow for iron sword."""
        goal = CraftingGoal(target_item_code="iron_sword")
        character_state = create_test_character_state()
        game_data = create_comprehensive_game_data()
        
        # Test feasibility
        assert goal.is_feasible(character_state, game_data) is True
        
        # Test weight calculation
        weight = goal.calculate_weight(character_state, game_data)
        assert weight > 0.0
        
        # Test target state generation
        target_state = goal.get_target_state(character_state, game_data)
        assert len(target_state.target_states) > 0
        
        # Test sub-goal generation
        sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
        assert len(sub_goals) > 0
    
    def test_progression_through_levels(self):
        """Test crafting goal behavior across different character levels."""
        goal = CraftingGoal()
        game_data = create_comprehensive_game_data()
        
        for level in [1, 2, 3, 4, 5]:
            character_state = create_test_character_state()
            character_state.level = level
            
            # Should remain feasible across progression
            feasible = goal.is_feasible(character_state, game_data)
            assert feasible is True
            
            # Weight should be reasonable
            weight = goal.calculate_weight(character_state, game_data)
            assert 0.0 < weight <= 10.0
            
            # Progression value should make sense
            progression = goal.get_progression_value(character_state)
            assert 0.0 <= progression <= 1.0
    
    def test_edge_case_no_workshops_available(self):
        """Test behavior when no workshops are available."""
        goal = CraftingGoal()
        character_state = create_test_character_state()
        
        # Create game data without workshop maps
        mock_map = Mock(spec=GameMap)
        mock_map.content = None  # No content - this is the edge case we're testing
        
        game_data = GameData(
            items=[create_craftable_item("iron_sword", "Iron Sword", 3, "weapon", "weaponcrafting", 2, [])],
            resources=[Mock(spec=GameResource)],  # Need at least one resource for validation
            maps=[mock_map],  # Map with no content for validation
            monsters=[Mock(spec=GameMonster)],
            npcs=[Mock(spec=GameNPC)]
        )
        
        target_state = goal.get_target_state(character_state, game_data)
        
        # Should return empty target state
        assert target_state.target_states == {}
        assert target_state.priority == 1
    
    def test_crafting_goal_with_character_fixtures(self):
        """Test CraftingGoal with various character state fixtures."""
        goal = CraftingGoal()
        game_data = create_comprehensive_game_data()
        
        # Test with different character scenarios
        test_scenarios = [
            CharacterStateFixtures.get_level_1_starter(),
            CharacterStateFixtures.get_level_10_experienced(),
            CharacterStateFixtures.get_level_25_advanced(),
        ]
        
        for game_state_dict in test_scenarios:
            # Convert GameState dict to CharacterGameState object
            character_state = create_test_character_state()
            character_state.level = game_state_dict[GameState.CHARACTER_LEVEL]
            character_state.gold = game_state_dict[GameState.CHARACTER_GOLD]
            character_state.weaponcrafting_level = game_state_dict.get(GameState.WEAPONCRAFTING_LEVEL, 1)
            character_state.gearcrafting_level = game_state_dict.get(GameState.GEARCRAFTING_LEVEL, 1)
            
            # Should work with all character scenarios
            weight = goal.calculate_weight(character_state, game_data)
            assert isinstance(weight, float)
            assert weight >= 0.0