"""
Test Complete Crafting Sequence

This module tests the complete crafting sequence using the new hierarchical sub-goal
architecture, verifying proper material gathering, workshop movement, and crafting
execution for the Copper Legs Armor example.
"""

import pytest
from unittest.mock import Mock, patch

from src.ai_player.goals.crafting_goal import CraftingGoal
from src.ai_player.goals.material_gathering_goal import MaterialGatheringGoal
from src.ai_player.goals.workshop_movement_goal import WorkshopMovementGoal
from src.ai_player.goals.craft_execution_goal import CraftExecutionGoal
from src.ai_player.state.game_state import GameState
from src.ai_player.state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData


@pytest.fixture
def mock_game_data():
    """Create mock game data with required recipes and resources."""
    game_data = Mock(spec=GameData)

    # Mock items including Copper Legs Armor recipe
    copper_legs = Mock()
    copper_legs.code = "copper_legs_armor"
    copper_legs.name = "Copper Legs Armor"
    copper_legs.level = 5
    copper_legs.type = "leg_armor"
    copper_legs.level_required = 5
    copper_legs.craft = {
        "skill": "gearcrafting",
        "level": 5,
        "materials": [{"code": "copper_ore", "quantity": 10}, {"code": "feather", "quantity": 2}],
    }

    # Mock intermediate items
    copper_bar = Mock()
    copper_bar.code = "copper_bar"
    copper_bar.name = "Copper Bar"
    copper_bar.level = 3
    copper_bar.type = "material"
    copper_bar.level_required = 3
    copper_bar.craft = {"skill": "mining", "level": 3, "materials": [{"code": "copper_ore", "quantity": 2}]}

    # Mock intermediate items
    copper_bar = Mock()
    copper_bar.code = "copper_bar"
    copper_bar.name = "Copper Bar"
    copper_bar.level = 3
    copper_bar.type = "material"
    copper_bar.level_required = 3
    copper_bar.craft = {"skill": "mining", "level": 3, "materials": [{"code": "copper_ore", "quantity": 2}]}

    # Mock intermediate items
    copper_bar = Mock()
    copper_bar.code = "copper_bar"
    copper_bar.name = "Copper Bar"
    copper_bar.level = 3
    copper_bar.type = "material"
    copper_bar.craft = {"skill": "mining", "level": 3, "materials": [{"code": "copper_ore", "quantity": 2}]}

    # Mock resources
    copper_ore = Mock()
    copper_ore.code = "copper_ore"
    copper_ore.skill = "mining"
    copper_ore.level = 1
    copper_ore.drops = [Mock(code="copper_ore", quantity=1)]

    feather = Mock()
    feather.code = "feather"
    feather.skill = "combat"
    feather.level = 1
    feather.drops = [Mock(code="feather", quantity=1)]

    game_data.items = [copper_legs, copper_bar]
    game_data.resources = [copper_ore, feather]

    # Mock maps with resource and workshop locations
    copper_map = Mock()
    copper_map.content = Mock(type="resource", code="copper_ore")
    copper_map.x = 2
    copper_map.y = 0

    chicken_map = Mock()
    chicken_map.content = Mock(type="monster", code="chicken")
    chicken_map.x = 0
    chicken_map.y = 1

    workshop_map = Mock()
    workshop_map.content = Mock(type="workshop", code="gearcrafting")
    workshop_map.x = 3
    workshop_map.y = 1

    game_data.maps = [copper_map, chicken_map, workshop_map]

    # Add validate_required_data method
    def validate_required_data():
        return True

    game_data.validate_required_data = validate_required_data

    return game_data


@pytest.fixture
def character_state():
    """Create character state with required skills and inventory."""
    return CharacterGameState(
        name="TestCharacter",
        x=0,
        y=0,
        level=5,
        xp=1000,
        gold=100,
        hp=100,
        max_hp=100,
        mining_level=5,
        mining_xp=1000,
        woodcutting_level=1,
        woodcutting_xp=0,
        fishing_level=1,
        fishing_xp=0,
        weaponcrafting_level=1,
        weaponcrafting_xp=0,
        gearcrafting_level=5,
        gearcrafting_xp=1000,
        jewelrycrafting_level=1,
        jewelrycrafting_xp=0,
        cooking_level=1,
        cooking_xp=0,
        alchemy_level=1,
        alchemy_xp=0,
        cooldown=0,
        cooldown_ready=True,
        can_fight=True,
        can_gather=True,
        can_craft=True,
        can_trade=True,
        can_move=True,
        can_rest=True,
        can_use_item=True,
        can_bank=True,
        can_gain_xp=True,
        xp_source_available=True,
        at_monster_location=False,
        at_resource_location=False,
        at_safe_location=True,
        safe_to_fight=True,
        hp_low=False,
        hp_critical=False,
        inventory_space_available=True,
        inventory_space_used=0,
        gained_xp=False,
        enemy_nearby=False,
        resource_available=False,
        at_workshop_location=False,
    )


def test_crafting_goal_generates_correct_sub_goals(mock_game_data, character_state):
    """Test that CraftingGoal generates the correct sequence of sub-goals."""
    # Create crafting goal for Copper Legs Armor
    goal = CraftingGoal(target_item_code="copper_legs_armor")

    # Get sub-goal requests
    sub_goals = goal.generate_sub_goal_requests(character_state, mock_game_data)

    # Verify correct number of sub-goals
    assert len(sub_goals) == 4  # 2 material gathering + 1 movement + 1 crafting

    # Verify material gathering sub-goals
    material_goals = [g for g in sub_goals if g.goal_type == "gather_material"]
    assert len(material_goals) == 2
    copper_goal = next(g for g in material_goals if g.parameters["material_code"] == "copper_ore")
    feather_goal = next(g for g in material_goals if g.parameters["material_code"] == "feather")
    assert copper_goal.parameters["quantity"] == 10
    assert feather_goal.parameters["quantity"] == 2

    # Verify workshop movement sub-goal
    movement_goals = [g for g in sub_goals if g.goal_type == "move_to_workshop"]
    assert len(movement_goals) == 1
    assert movement_goals[0].parameters["workshop_type"] == "gearcrafting"
    assert movement_goals[0].parameters["workshop_x"] == 3
    assert movement_goals[0].parameters["workshop_y"] == 1

    # Verify crafting execution sub-goal
    craft_goals = [g for g in sub_goals if g.goal_type == "execute_craft"]
    assert len(craft_goals) == 1
    assert craft_goals[0].parameters["recipe_code"] == "copper_legs_armor"
    assert craft_goals[0].parameters["workshop_type"] == "gearcrafting"


def test_material_gathering_goal_target_state(mock_game_data, character_state):
    """Test that MaterialGatheringGoal produces correct target state."""
    goal = MaterialGatheringGoal(material_code="copper_ore", quantity=10)
    target_state = goal.get_target_state(character_state, mock_game_data)

    assert target_state.target_states[GameState.AT_RESOURCE_LOCATION] is True
    assert target_state.target_states[GameState.RESOURCE_AVAILABLE] is True
    assert target_state.target_states[GameState.CAN_GATHER] is True
    assert target_state.target_states[GameState.COOLDOWN_READY] is True
    assert target_state.target_states[GameState.INVENTORY_SPACE_AVAILABLE] is True
    assert target_state.target_states[GameState.HAS_MATERIAL_COPPER_ORE] is True
    assert target_state.target_states[GameState.INVENTORY_CONTAINS_COPPER_ORE] == 10
    assert target_state.target_states[GameState.MATERIAL_GATHERING_IN_PROGRESS] is True


def test_workshop_movement_goal_target_state(mock_game_data, character_state):
    """Test that WorkshopMovementGoal produces correct target state."""
    goal = WorkshopMovementGoal(workshop_x=3, workshop_y=1, workshop_type="gearcrafting")
    target_state = goal.get_target_state(character_state, mock_game_data)

    assert target_state.target_states[GameState.AT_WORKSHOP_LOCATION] is True
    assert target_state.target_states[GameState.CURRENT_X] == 3
    assert target_state.target_states[GameState.CURRENT_Y] == 1
    assert target_state.target_states[GameState.CAN_CRAFT] is True
    assert target_state.target_states[GameState.PATH_CLEAR] is True


def test_craft_execution_goal_target_state(mock_game_data, character_state):
    """Test that CraftExecutionGoal produces correct target state."""
    goal = CraftExecutionGoal(recipe_code="copper_legs_armor", workshop_type="gearcrafting")
    target_state = goal.get_target_state(character_state, mock_game_data)

    assert target_state.target_states[GameState.AT_WORKSHOP_LOCATION] is True
    assert target_state.target_states[GameState.HAS_CRAFTING_MATERIALS] is True
    assert target_state.target_states[GameState.CRAFTING_MATERIALS_READY] is True
    assert target_state.target_states[GameState.CAN_CRAFT] is True
    assert target_state.target_states[GameState.COOLDOWN_READY] is True
    assert target_state.target_states[GameState.GAINED_XP] is True
    assert target_state.target_states[GameState.HAS_CRAFTED_ITEM] is True
    assert target_state.target_states[GameState.CRAFTING_COMPLETED] is True
    assert target_state.target_states[GameState.INVENTORY_SPACE_AVAILABLE] is True


def test_crafting_goal_minimal_target_state(mock_game_data, character_state):
    """Test that CraftingGoal's target state is minimal for recipe selection."""
    goal = CraftingGoal(target_item_code="copper_legs_armor")
    target_state = goal.get_target_state(character_state, mock_game_data)

    # Should only include states needed for recipe selection
    assert len(target_state.target_states) == 2
    assert target_state.target_states[GameState.HAS_SELECTED_RECIPE] is True
    assert target_state.target_states[GameState.RECIPE_ANALYZED] is True


@pytest.mark.parametrize(
    "current_x,current_y,expected_weight",
    [
        (0, 0, 8.0),  # Far from resources
        (2, 0, 10.0),  # At copper location
        (0, 1, 9.0),  # At chicken location
    ],
)
def test_material_gathering_goal_weight_calculation(
    mock_game_data, character_state, current_x, current_y, expected_weight
):
    """Test that MaterialGatheringGoal calculates appropriate weights based on location."""
    character_state.x = current_x
    character_state.y = current_y

    goal = MaterialGatheringGoal(material_code="copper_ore", quantity=10)
    weight = goal.calculate_weight(character_state, mock_game_data)

    assert abs(weight - expected_weight) <= 0.1


@pytest.mark.parametrize(
    "current_x,current_y,expected_weight",
    [
        (0, 0, 7.0),  # Far from workshop
        (3, 1, 10.0),  # At workshop
        (3, 0, 8.5),  # Near workshop
    ],
)
def test_workshop_movement_goal_weight_calculation(
    mock_game_data, character_state, current_x, current_y, expected_weight
):
    """Test that WorkshopMovementGoal calculates appropriate weights based on location."""
    character_state.x = current_x
    character_state.y = current_y

    goal = WorkshopMovementGoal(workshop_x=3, workshop_y=1, workshop_type="gearcrafting")
    weight = goal.calculate_weight(character_state, mock_game_data)

    assert abs(weight - expected_weight) <= 0.1


@pytest.mark.parametrize(
    "has_materials,at_workshop,expected_weight",
    [
        (True, True, 10.0),  # Perfect conditions
        (True, False, 5.0),  # Has materials but wrong location
        (False, True, 3.0),  # Right location but no materials
        (False, False, 2.7),  # Neither condition met
    ],
)
def test_craft_execution_goal_weight_calculation(
    mock_game_data, character_state, has_materials, at_workshop, expected_weight
):
    """Test that CraftExecutionGoal calculates appropriate weights based on conditions."""
    character_state.has_crafting_materials = has_materials
    character_state.at_workshop_location = at_workshop

    goal = CraftExecutionGoal(recipe_code="copper_legs_armor", workshop_type="gearcrafting")
    weight = goal.calculate_weight(character_state, mock_game_data)

    assert abs(weight - expected_weight) <= 0.1
