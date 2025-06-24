"""Unit tests for AIPlayerController class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

from src.controller.ai_player_controller import AIPlayerController
from src.controller.world.state import WorldState
from src.game.character.state import CharacterState
from src.game.map.state import MapState


class TestAIPlayerController(unittest.TestCase):
    """Test cases for AIPlayerController class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        # Create controller instance
        self.controller = AIPlayerController()
        
        # Mock the client
        self.mock_client = Mock()
        self.controller.set_client(self.mock_client)
        
        # Mock character and map states
        self.mock_character_state = Mock(spec=CharacterState)
        self.mock_character_state.name = "test_character"
        
        self.mock_map_state = Mock(spec=MapState)

    def test_init(self) -> None:
        """Test AIPlayerController initialization."""
        controller = AIPlayerController()
        
        # Verify initial state
        self.assertIsNotNone(controller.world_state)
        self.assertIsNone(controller.client)
        self.assertIsNone(controller.character_state)
        self.assertIsNone(controller.map_state)
        self.assertEqual(controller.current_plan, [])
        self.assertEqual(controller.current_action_index, 0)
        self.assertFalse(controller.is_executing)

    def test_init_with_client(self) -> None:
        """Test AIPlayerController initialization with client."""
        mock_client = Mock()
        controller = AIPlayerController(client=mock_client)
        
        self.assertEqual(controller.client, mock_client)

    def test_set_client(self) -> None:
        """Test setting the API client."""
        new_client = Mock()
        
        self.controller.set_client(new_client)
        
        self.assertEqual(self.controller.client, new_client)

    def test_set_character_state(self) -> None:
        """Test setting character state."""
        self.controller.set_character_state(self.mock_character_state)
        
        self.assertEqual(self.controller.character_state, self.mock_character_state)

    def test_set_map_state(self) -> None:
        """Test setting map state."""
        self.controller.set_map_state(self.mock_map_state)
        
        self.assertEqual(self.controller.map_state, self.mock_map_state)

    @patch('src.controller.ai_player_controller.Planner')
    @patch('src.controller.ai_player_controller.Action_List')
    def test_create_planner(self, mock_action_list_class, mock_planner_class):
        """Test creating a GOAP planner."""
        # Setup
        mock_planner = Mock()
        mock_action_list = Mock()
        mock_planner_class.return_value = mock_planner
        mock_action_list_class.return_value = mock_action_list
        
        start_state = {"location": "town", "health": 100}
        goal_state = {"location": "forest", "has_weapon": True}
        actions_config = {
            "move": {
                "conditions": {"health": True},
                "reactions": {"location": "forest"},
                "weight": 1.0
            }
        }
        
        # Execute
        result = self.controller.create_planner(start_state, goal_state, actions_config)
        
        # Verify
        self.assertEqual(result, mock_planner)
        mock_planner_class.assert_called_once()
        mock_planner.set_start_state.assert_called_once_with(**start_state)
        mock_planner.set_goal_state.assert_called_once_with(**goal_state)
        mock_planner.set_action_list.assert_called_once_with(mock_action_list)

    @patch('src.controller.ai_player_controller.AIPlayerController.create_planner')
    def test_plan_goal_success(self, mock_create_planner):
        """Test successful goal planning."""
        # Setup
        mock_planner = Mock()
        mock_plan = [{"name": "move", "cost": 1.0}]
        mock_planner.calculate.return_value = mock_plan
        mock_create_planner.return_value = mock_planner
        
        start_state = {"location": "town"}
        goal_state = {"location": "forest"}
        actions_config = {"move": {}}
        
        # Execute
        result = self.controller.plan_goal(start_state, goal_state, actions_config)
        
        # Verify
        self.assertTrue(result)
        self.assertEqual(self.controller.current_plan, mock_plan)
        self.assertEqual(self.controller.current_action_index, 0)
        mock_create_planner.assert_called_once_with(start_state, goal_state, actions_config)

    @patch('src.controller.ai_player_controller.AIPlayerController.create_planner')
    def test_plan_goal_no_plan_found(self, mock_create_planner):
        """Test goal planning when no plan is found."""
        # Setup
        mock_planner = Mock()
        mock_planner.calculate.return_value = []
        mock_create_planner.return_value = mock_planner
        
        start_state = {"location": "town"}
        goal_state = {"location": "forest"}
        actions_config = {"move": {}}
        
        # Execute
        result = self.controller.plan_goal(start_state, goal_state, actions_config)
        
        # Verify
        self.assertFalse(result)

    def test_plan_goal_no_client(self):
        """Test goal planning without client."""
        controller = AIPlayerController()  # No client set
        
        result = controller.plan_goal({}, {}, {})
        
        self.assertFalse(result)

    @patch('src.controller.ai_player_controller.AIPlayerController._execute_action')
    def test_execute_next_action_success(self, mock_execute_action):
        """Test successful execution of next action."""
        # Setup
        self.controller.current_plan = [
            {"name": "move", "cost": 1.0},
            {"name": "attack", "cost": 2.0}
        ]
        self.controller.current_action_index = 0
        mock_execute_action.return_value = True
        
        # Execute
        result = self.controller.execute_next_action()
        
        # Verify
        self.assertTrue(result)
        self.assertEqual(self.controller.current_action_index, 1)
        mock_execute_action.assert_called_once_with("move", {"name": "move", "cost": 1.0})

    def test_execute_next_action_no_plan(self):
        """Test executing next action when no plan exists."""
        self.controller.current_plan = []
        
        result = self.controller.execute_next_action()
        
        self.assertFalse(result)
        self.assertFalse(self.controller.is_executing)

    def test_execute_next_action_plan_complete(self):
        """Test executing next action when plan is complete."""
        self.controller.current_plan = [{"name": "move"}]
        self.controller.current_action_index = 1  # Beyond plan length
        
        result = self.controller.execute_next_action()
        
        self.assertFalse(result)
        self.assertFalse(self.controller.is_executing)

    def test_execute_next_action_no_client(self):
        """Test executing next action without client."""
        controller = AIPlayerController()  # No client
        controller.current_plan = [{"name": "move"}]
        
        result = controller.execute_next_action()
        
        self.assertFalse(result)

    @patch('src.controller.ai_player_controller.MoveAction')
    def test_execute_action_move(self, mock_move_action_class):
        """Test executing a move action."""
        # Setup
        mock_move_action = Mock()
        mock_move_action.execute.return_value = {"success": True}
        mock_move_action_class.return_value = mock_move_action
        
        self.controller.set_character_state(self.mock_character_state)
        
        # Execute
        result = self.controller._execute_action("move", {"name": "move"})
        
        # Verify
        self.assertTrue(result)
        mock_move_action_class.assert_called_once_with("test_character", 0, 1)
        mock_move_action.execute.assert_called_once_with(self.mock_client)

    @patch('src.controller.ai_player_controller.MapLookupAction')
    def test_execute_action_map_lookup(self, mock_map_lookup_action_class):
        """Test executing a map lookup action."""
        # Setup
        mock_map_lookup_action = Mock()
        mock_map_lookup_action.execute.return_value = {"success": True}
        mock_map_lookup_action_class.return_value = mock_map_lookup_action
        
        # Execute
        result = self.controller._execute_action("map_lookup", {"name": "map_lookup"})
        
        # Verify
        self.assertTrue(result)
        mock_map_lookup_action_class.assert_called_once_with(0, 0)
        mock_map_lookup_action.execute.assert_called_once_with(self.mock_client)

    def test_execute_action_unknown(self):
        """Test executing an unknown action."""
        result = self.controller._execute_action("unknown_action", {"name": "unknown"})
        
        self.assertFalse(result)

    def test_execute_action_move_no_character(self):
        """Test executing move action without character state."""
        result = self.controller._execute_action("move", {"name": "move"})
        
        self.assertFalse(result)

    @patch('src.controller.ai_player_controller.AIPlayerController.execute_next_action')
    def test_execute_plan_success(self, mock_execute_next):
        """Test successful plan execution."""
        # Setup
        self.controller.current_plan = [{"name": "move"}]
        
        # Mock execute_next_action to simulate successful execution followed by completion
        # We need to manually update the action index to simulate progress
        def mock_execute_side_effect():
            if self.controller.current_action_index < len(self.controller.current_plan):
                self.controller.current_action_index += 1
                return True
            else:
                self.controller.is_executing = False
                return False
        
        mock_execute_next.side_effect = mock_execute_side_effect
        
        # Execute
        result = self.controller.execute_plan()
        
        # Verify - Plan should return True when successfully completed
        self.assertTrue(result)  # Fixed: should return True for successful execution
        self.assertFalse(self.controller.is_executing)  # Should be False when complete

    def test_execute_plan_no_plan(self):
        """Test executing plan when no plan exists."""
        self.controller.current_plan = []
        
        result = self.controller.execute_plan()
        
        self.assertFalse(result)

    @patch('src.controller.ai_player_controller.AIPlayerController.execute_next_action')
    def test_execute_plan_action_fails(self, mock_execute_next):
        """Test plan execution when an action fails."""
        # Setup
        self.controller.current_plan = [{"name": "move"}]
        mock_execute_next.return_value = False
        
        # Execute
        result = self.controller.execute_plan()
        
        # Verify
        self.assertFalse(result)

    def test_is_plan_complete_no_plan(self):
        """Test checking plan completion when no plan exists."""
        self.controller.current_plan = []
        
        result = self.controller.is_plan_complete()
        
        self.assertTrue(result)

    def test_is_plan_complete_plan_finished(self):
        """Test checking plan completion when plan is finished."""
        self.controller.current_plan = [{"name": "move"}]
        self.controller.current_action_index = 1
        
        result = self.controller.is_plan_complete()
        
        self.assertTrue(result)

    def test_is_plan_complete_plan_in_progress(self):
        """Test checking plan completion when plan is still in progress."""
        self.controller.current_plan = [{"name": "move"}, {"name": "attack"}]
        self.controller.current_action_index = 0
        
        result = self.controller.is_plan_complete()
        
        self.assertFalse(result)

    def test_cancel_plan(self):
        """Test cancelling the current plan."""
        # Setup
        self.controller.current_plan = [{"name": "move"}]
        self.controller.current_action_index = 1
        self.controller.is_executing = True
        
        # Execute
        self.controller.cancel_plan()
        
        # Verify
        self.assertEqual(self.controller.current_plan, [])
        self.assertEqual(self.controller.current_action_index, 0)
        self.assertFalse(self.controller.is_executing)

    def test_get_plan_status_with_plan(self):
        """Test getting plan status when plan exists."""
        # Setup
        self.controller.current_plan = [{"name": "move"}, {"name": "attack"}]
        self.controller.current_action_index = 1
        self.controller.is_executing = True
        
        # Execute
        status = self.controller.get_plan_status()
        
        # Verify
        expected_status = {
            'has_plan': True,
            'plan_length': 2,
            'current_action_index': 1,
            'is_executing': True,
            'is_complete': False,
            'current_action': 'attack'
        }
        self.assertEqual(status, expected_status)

    def test_get_plan_status_no_plan(self):
        """Test getting plan status when no plan exists."""
        # Execute
        status = self.controller.get_plan_status()
        
        # Verify
        expected_status = {
            'has_plan': False,
            'plan_length': 0,
            'current_action_index': 0,
            'is_executing': False,
            'is_complete': True,
            'current_action': None
        }
        self.assertEqual(status, expected_status)

    @patch('src.controller.ai_player_controller.World')
    @patch('src.controller.ai_player_controller.AIPlayerController.create_planner')
    def test_create_world_with_planner(self, mock_create_planner, mock_world_class):
        """Test creating a world with planner."""
        # Setup
        mock_world = Mock()
        mock_planner = Mock()
        mock_world_class.return_value = mock_world
        mock_create_planner.return_value = mock_planner
        
        start_state = {"location": "town"}
        goal_state = {"location": "forest"}
        actions_config = {"move": {}}
        
        # Execute
        result = self.controller.create_world_with_planner(start_state, goal_state, actions_config)
        
        # Verify
        self.assertEqual(result, mock_world)
        mock_world.add_planner.assert_called_once_with(mock_planner)

    @patch('src.controller.ai_player_controller.AIPlayerController.create_world_with_planner')
    def test_calculate_best_plan_success(self, mock_create_world):
        """Test calculating best plan successfully."""
        # Setup
        mock_world = Mock()
        mock_plans = [
            [{"name": "move", "cost": 1.0}],
            [{"name": "move", "cost": 2.0}]
        ]
        mock_world.get_plan.return_value = mock_plans
        mock_create_world.return_value = mock_world
        
        start_state = {"location": "town"}
        goal_state = {"location": "forest"}
        actions_config = {"move": {}}
        
        # Execute
        result = self.controller.calculate_best_plan(start_state, goal_state, actions_config)
        
        # Verify
        self.assertEqual(result, mock_plans[0])  # Should return the first (best) plan
        mock_world.calculate.assert_called_once()

    @patch('src.controller.ai_player_controller.AIPlayerController.create_world_with_planner')
    def test_calculate_best_plan_no_plans(self, mock_create_world):
        """Test calculating best plan when no plans are found."""
        # Setup
        mock_world = Mock()
        mock_world.get_plan.return_value = []
        mock_create_world.return_value = mock_world
        
        start_state = {"location": "town"}
        goal_state = {"location": "forest"}
        actions_config = {"move": {}}
        
        # Execute
        result = self.controller.calculate_best_plan(start_state, goal_state, actions_config)
        
        # Verify
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
