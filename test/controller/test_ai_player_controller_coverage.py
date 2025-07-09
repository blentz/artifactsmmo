"""Comprehensive tests for AIPlayerController to achieve high coverage."""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, call
import logging

from src.controller.ai_player_controller import AIPlayerController
from src.controller.actions.base import ActionResult
from src.controller.skill_goal_manager import SkillType
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.lib.action_context import ActionContext
from test.test_base import UnifiedContextTestBase


class TestAIPlayerControllerCoverage(UnifiedContextTestBase):
    """Comprehensive test cases for AIPlayerController."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Mock dependencies
        self.mock_client = Mock()
        self.mock_goal_manager = Mock()
        
        # Mock character state
        self.mock_character_state = Mock(spec=CharacterState)
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'x': 5,
            'y': 10,
            'level': 10,
            'xp': 1000,
            'hp': 80,
            'max_hp': 100,
            'cooldown': 0,
            'cooldown_expiration': None
        }
        
        # Mock map state
        self.mock_map_state = Mock(spec=MapState)
        self.mock_map_state.get_location_info = Mock(return_value={'content': None})
        
        # Create controller with mocked dependencies
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create:
                self.mock_world_state = Mock()
                self.mock_world_state.data = {}
                self.mock_knowledge_base = Mock()
                self.mock_knowledge_base.data = {}
                mock_create.side_effect = [self.mock_world_state, self.mock_knowledge_base]
                
                # Mock goal_manager to return proper dict from calculate_world_state
                self.mock_goal_manager.calculate_world_state.return_value = {
                    'character_level': 10,
                    'character_status': {
                        'level': 10,
                        'xp': 1000,
                        'hp': 80,
                        'max_hp': 100
                    }
                }
                
                self.controller = AIPlayerController(self.mock_client, self.mock_goal_manager)
                
        # Set character and map states
        self.controller.character_state = self.mock_character_state
        self.controller.map_state = self.mock_map_state
        
        # Mock the manager objects that are created in __init__
        self.controller.action_executor = Mock()
        self.controller.cooldown_manager = Mock()
        self.controller.mission_executor = Mock()
        self.controller.skill_goal_manager = Mock()
        self.controller.goap_execution_manager = Mock()
        self.controller.learning_manager = Mock()
    
    def test_set_client(self):
        """Test setting the client."""
        new_client = Mock()
        self.controller.set_client(new_client)
        self.assertEqual(self.controller.client, new_client)
    
    def test_set_character_state(self):
        """Test setting character state."""
        # Create new character state
        new_char_state = Mock(spec=CharacterState)
        new_char_state.name = "new_character"
        new_char_state.data = {'x': 15, 'y': 20}
        
        # Mock _invalidate_location_states
        with patch.object(self.controller, '_invalidate_location_states') as mock_invalidate:
            self.controller.set_character_state(new_char_state)
            
            # Verify character state is set
            self.assertEqual(self.controller.character_state, new_char_state)
            mock_invalidate.assert_called_once()
    
    @patch('src.controller.ai_player_controller.YamlData')
    def test_invalidate_location_states_with_config(self, mock_yaml_data):
        """Test location state invalidation with config."""
        # Mock YAML config
        mock_config = Mock()
        mock_config.data = {
            'location_based_states': ['at_bank', 'at_workshop', 'at_resource_location']
        }
        mock_yaml_data.return_value = mock_config
        
        # Set up world state with location data
        self.mock_world_state.data = {
            'at_bank': True,
            'at_workshop': 'weaponcrafting',
            'at_resource_location': True
        }
        
        # Mock update_world_state
        with patch.object(self.controller, 'update_world_state') as mock_update:
            self.controller._invalidate_location_states()
            
            # Verify update was called with False values
            expected_updates = {
                'at_bank': False,
                'at_workshop': False,
                'at_resource_location': False
            }
            mock_update.assert_called_once_with(expected_updates)
    
    @patch('src.controller.ai_player_controller.YamlData')
    def test_invalidate_location_states_config_error(self, mock_yaml_data):
        """Test location state invalidation with config error."""
        # Mock YAML config to raise exception
        mock_yaml_data.side_effect = Exception("Config error")
        
        # Set up world state with location data
        self.mock_world_state.data = {
            'at_correct_workshop': True,
            'at_target_location': True,
            'at_resource_location': True
        }
        
        # Mock update_world_state
        with patch.object(self.controller, 'update_world_state') as mock_update:
            self.controller._invalidate_location_states()
            
            # Should fall back to hardcoded states
            expected_updates = {
                'at_correct_workshop': False,
                'at_target_location': False,
                'at_resource_location': False
            }
            mock_update.assert_called_once_with(expected_updates)
    
    def test_invalidate_location_states_no_world_state(self):
        """Test location state invalidation with no world state."""
        self.controller.world_state = None
        # Should not raise exception
        self.controller._invalidate_location_states()
    
    def test_set_map_state(self):
        """Test setting map state."""
        new_map_state = Mock(spec=MapState)
        self.controller.set_map_state(new_map_state)
        self.assertEqual(self.controller.map_state, new_map_state)
    
    def test_check_and_handle_cooldown_no_character_state(self):
        """Test cooldown handling with no character state."""
        self.controller.character_state = None
        result = self.controller.check_and_handle_cooldown()
        self.assertTrue(result)
    
    def test_check_and_handle_cooldown_no_expiration(self):
        """Test cooldown handling with no expiration."""
        self.mock_character_state.data['cooldown_expiration'] = None
        result = self.controller.check_and_handle_cooldown()
        self.assertTrue(result)
    
    def test_check_and_handle_cooldown_active(self):
        """Test cooldown handling when character is on cooldown."""
        # Set future expiration time
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        self.controller.cooldown_manager.calculate_wait_duration.return_value = 5
        
        # Mock _execute_action and _refresh_character_state
        with patch.object(self.controller, '_execute_action') as mock_execute:
            with patch.object(self.controller, '_refresh_character_state') as mock_refresh:
                mock_execute.return_value = (True, {})
                
                result = self.controller.check_and_handle_cooldown()
                
                self.assertTrue(result)
                mock_execute.assert_called_once_with('wait')
                mock_refresh.assert_called_once()
    
    def test_check_and_handle_cooldown_wait_failed(self):
        """Test cooldown handling when wait action fails."""
        # Set future expiration time
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        self.controller.cooldown_manager.calculate_wait_duration.return_value = 5
        
        # Mock _execute_action to fail
        with patch.object(self.controller, '_execute_action') as mock_execute:
            mock_execute.return_value = (False, {})
            
            result = self.controller.check_and_handle_cooldown()
            
            self.assertFalse(result)
    
    def test_check_and_handle_cooldown_expired(self):
        """Test cooldown handling when cooldown is expired."""
        # Set past expiration time
        past_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        self.mock_character_state.data['cooldown_expiration'] = past_time.isoformat()
        
        result = self.controller.check_and_handle_cooldown()
        self.assertTrue(result)
    
    def test_check_and_handle_cooldown_exception(self):
        """Test cooldown handling with exception."""
        # Set invalid expiration time
        self.mock_character_state.data['cooldown_expiration'] = "invalid"
        
        # The actual logger is already created, so we need to patch the logger instance
        with patch.object(self.controller.logger, 'warning') as mock_warning:
            result = self.controller.check_and_handle_cooldown()
            self.assertTrue(result)
            # Should log warning
            mock_warning.assert_called()
    
    def test_execute_next_action_empty_plan(self):
        """Test execute_next_action with empty plan."""
        self.controller.current_plan = []
        self.controller.current_action_index = 0
        
        result = self.controller.execute_next_action()
        
        self.assertFalse(result)
        self.assertFalse(self.controller.is_executing)
    
    def test_execute_next_action_no_client(self):
        """Test execute_next_action with no client."""
        self.controller.client = None
        self.controller.current_plan = [{'name': 'move', 'x': 10}]
        self.controller.current_action_index = 0
        
        result = self.controller.execute_next_action()
        
        self.assertFalse(result)
    
    def test_execute_next_action_success(self):
        """Test successful execution of next action."""
        # Set up plan
        self.controller.current_plan = [
            {'name': 'move', 'x': 10, 'y': 15}
        ]
        self.controller.current_action_index = 0
        
        # Mock check_and_handle_cooldown and _execute_action
        with patch.object(self.controller, 'check_and_handle_cooldown') as mock_cooldown:
            with patch.object(self.controller, '_execute_action') as mock_execute:
                mock_cooldown.return_value = True
                mock_execute.return_value = (True, {'moved': True})
                
                result = self.controller.execute_next_action()
                
                self.assertTrue(result)
                self.assertEqual(self.controller.current_action_index, 1)
                # With unified context, no manual context update occurs
                mock_execute.assert_called_once_with('move')
    
    def test_execute_next_action_failure(self):
        """Test failed execution of next action."""
        # Set up plan
        self.controller.current_plan = [
            {'name': 'attack', 'target': 'monster'}
        ]
        self.controller.current_action_index = 0
        
        # Mock check_and_handle_cooldown and _execute_action
        with patch.object(self.controller, 'check_and_handle_cooldown') as mock_cooldown:
            with patch.object(self.controller, '_execute_action') as mock_execute:
                mock_cooldown.return_value = True
                mock_execute.return_value = (False, {})
                
                result = self.controller.execute_next_action()
                
                self.assertFalse(result)
                self.assertFalse(self.controller.is_executing)
    
    def test_execute_next_action_cooldown_fail(self):
        """Test execute_next_action when cooldown handling fails."""
        self.controller.current_plan = [{'name': 'move'}]
        self.controller.current_action_index = 0
        
        with patch.object(self.controller, 'check_and_handle_cooldown') as mock_cooldown:
            mock_cooldown.return_value = False
            
            result = self.controller.execute_next_action()
            
            self.assertFalse(result)
            self.assertFalse(self.controller.is_executing)
    
    def test_execute_next_action_exception(self):
        """Test execute_next_action with exception during action execution."""
        self.controller.current_plan = [{'name': 'move'}]
        self.controller.current_action_index = 0
        
        # Mock check_and_handle_cooldown to succeed
        with patch.object(self.controller, 'check_and_handle_cooldown') as mock_cooldown:
            mock_cooldown.return_value = True
            
            # Mock _execute_action to raise exception (this is inside try-except)
            with patch.object(self.controller, '_execute_action') as mock_execute:
                mock_execute.side_effect = Exception("Test error")
                
                result = self.controller.execute_next_action()
                
                self.assertFalse(result)
                self.assertFalse(self.controller.is_executing)
    
    def test_execute_action_refresh_state(self):
        """Test _execute_action refreshes state for non-wait actions."""
        with patch.object(self.controller, '_refresh_character_state') as mock_refresh:
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_build_execution_context') as mock_context:
                    mock_cooldown.return_value = False
                    mock_context.return_value = Mock()
                    self.controller.action_executor.execute_action.return_value = ActionResult(
                        success=True, data={}, action_name='move'
                    )
                    
                    self.controller._execute_action('move')
                    
                    mock_refresh.assert_called_once()
    
    def test_execute_action_cooldown_detected(self):
        """Test _execute_action when cooldown is detected."""
        with patch.object(self.controller, '_refresh_character_state'):
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_execute_cooldown_wait') as mock_wait:
                    mock_cooldown.side_effect = [True, False]  # First True, then False after wait
                    mock_wait.return_value = True
                    
                    with patch.object(self.controller, '_build_execution_context'):
                        self.controller.action_executor.execute_action.return_value = ActionResult(
                            success=True, data={}, action_name='move'
                        )
                        
                        success, result = self.controller._execute_action('move')
                        
                        self.assertTrue(success)
                        mock_wait.assert_called_once()
    
    def test_execute_action_with_response_data(self):
        """Test _execute_action with various response data types."""
        # Test find_monsters response
        with patch.object(self.controller, '_refresh_character_state'):
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_build_execution_context') as mock_context:
                    mock_cooldown.return_value = False
                    mock_context.return_value = Mock()
                    
                    response = {'target_x': 15, 'target_y': 20}
                    self.controller.action_executor.execute_action.return_value = ActionResult(
                        success=True, data=response, action_name='find_monsters'
                    )
                    
                    success, result_data = self.controller._execute_action('find_monsters')
                    
                    self.assertTrue(success)
                    self.assertEqual(result_data['x'], 15)
                    self.assertEqual(result_data['y'], 20)
                    self.assertEqual(result_data['target_x'], 15)
                    self.assertEqual(result_data['target_y'], 20)
    
    def test_execute_action_lookup_item_info(self):
        """Test _execute_action with lookup_item_info response."""
        with patch.object(self.controller, '_refresh_character_state'):
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_build_execution_context') as mock_context:
                    mock_cooldown.return_value = False
                    mock_context.return_value = Mock()
                    
                    response = {
                        'success': True,
                        'recipe_found': True,
                        'item_code': 'copper_sword',
                        'item_name': 'Copper Sword',
                        'craft_skill': 'weaponcrafting',
                        'materials_needed': [
                            {'code': 'copper', 'is_resource': True, 'resource_source': 'copper_ore'}
                        ],
                        'crafting_chain': [
                            {'step_type': 'craft_intermediate', 'item_code': 'copper', 'item_name': 'Copper', 'craft_skill': 'mining'}
                        ]
                    }
                    self.controller.action_executor.execute_action.return_value = ActionResult(
                        success=True, data=response, action_name='lookup_item_info'
                    )
                    
                    success, result_data = self.controller._execute_action('lookup_item_info')
                    
                    self.assertTrue(success)
                    self.assertEqual(result_data['recipe_item_code'], 'copper_sword')
                    self.assertEqual(result_data['resource_types'], ['copper_ore'])
                    self.assertTrue(result_data['smelting_required'])
                    self.assertEqual(result_data['smelt_item_code'], 'copper')
    
    def test_execute_action_attack_response(self):
        """Test _execute_action with attack response."""
        # Initialize world state
        self.controller.world_state.data = {'goal_progress': {'monsters_hunted': 5}}
        
        with patch.object(self.controller, '_refresh_character_state'):
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_build_execution_context') as mock_context:
                    with patch.object(self.controller, 'get_current_world_state') as mock_get_state:
                        with patch.object(self.controller, 'update_world_state') as mock_update:
                            mock_cooldown.return_value = False
                            mock_context.return_value = Mock()
                            mock_get_state.return_value = {'goal_progress': {'monsters_hunted': 5}}
                            
                            response = {'success': True, 'monster_defeated': True}
                            self.controller.action_executor.execute_action.return_value = ActionResult(
                                success=True, data=response, action_name='attack'
                            )
                            
                            success, result_data = self.controller._execute_action('attack')
                            
                            self.assertTrue(success)
                            mock_update.assert_called_once_with({'goal_progress': {'monsters_hunted': 6}})
    
    def test_execute_action_cooldown_error(self):
        """Test _execute_action with cooldown error in response."""
        with patch.object(self.controller, '_refresh_character_state') as mock_refresh:
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                with patch.object(self.controller, '_build_execution_context') as mock_context:
                    mock_cooldown.return_value = False
                    mock_context.return_value = Mock()
                    
                    self.controller.action_executor.execute_action.return_value = ActionResult(
                    success=False,
                    data={},
                    action_name='move',
                    error='Character is on cooldown'
                    
                )
                    
                    success, result = self.controller._execute_action('move')
                    
                    self.assertFalse(success)
                    # Should refresh state when cooldown error detected
                    self.assertEqual(mock_refresh.call_count, 2)  # Once at start, once for cooldown error
    
    def test_execute_action_exception(self):
        """Test _execute_action with exception."""
        with patch.object(self.controller, '_refresh_character_state'):
            with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                mock_cooldown.side_effect = Exception("Test error")
                
                success, result = self.controller._execute_action('move')
                
                self.assertFalse(success)
                self.assertEqual(result, {})
    
    def test_execute_cooldown_wait(self):
        """Test _execute_cooldown_wait method."""
        self.controller.cooldown_manager.handle_cooldown_with_wait.return_value = True
        
        result = self.controller._execute_cooldown_wait()
        
        self.assertTrue(result)
        self.controller.cooldown_manager.handle_cooldown_with_wait.assert_called_once_with(
            self.mock_character_state, self.controller.action_executor, self.controller
        )
    
    def test_is_character_on_cooldown(self):
        """Test _is_character_on_cooldown method."""
        self.controller.cooldown_manager.is_character_on_cooldown.return_value = True
        
        result = self.controller._is_character_on_cooldown()
        
        self.assertTrue(result)
        self.controller.cooldown_manager.is_character_on_cooldown.assert_called_once_with(
            self.mock_character_state
        )
    
    def test_should_refresh_character_state_no_state(self):
        """Test _should_refresh_character_state with no character state."""
        self.controller.character_state = None
        self.assertTrue(self.controller._should_refresh_character_state())
    
    def test_should_refresh_character_state_with_state(self):
        """Test _should_refresh_character_state with character state."""
        self.controller.cooldown_manager.should_refresh_character_state.return_value = False
        
        result = self.controller._should_refresh_character_state()
        
        self.assertFalse(result)
        self.controller.cooldown_manager.should_refresh_character_state.assert_called_once()
    
    @patch('src.controller.ai_player_controller.get_character')
    def test_refresh_character_state(self, mock_get_character):
        """Test _refresh_character_state method."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_get_character.return_value = mock_response
        
        # Mock update and save methods
        self.mock_character_state.update_from_api_response = Mock()
        self.mock_character_state.save = Mock()
        
        self.controller._refresh_character_state()
        
        # Verify API was called
        mock_get_character.assert_called_once_with(
            name='test_character',
            client=self.mock_client
        )
        
        # Verify character state was updated
        self.mock_character_state.update_from_api_response.assert_called_once_with(mock_response.data)
        self.mock_character_state.save.assert_called_once()
        self.controller.cooldown_manager.mark_character_state_refreshed.assert_called_once()
    
    @patch('src.controller.ai_player_controller.get_character')
    def test_refresh_character_state_no_client(self, mock_get_character):
        """Test _refresh_character_state with no client."""
        self.controller.client = None
        
        self.controller._refresh_character_state()
        
        mock_get_character.assert_not_called()
    
    @patch('src.controller.ai_player_controller.get_character')
    def test_refresh_character_state_exception(self, mock_get_character):
        """Test _refresh_character_state with exception."""
        mock_get_character.side_effect = Exception("API error")
        
        # Should not raise exception
        self.controller._refresh_character_state()
    
    def test_build_execution_context(self):
        """Test _build_execution_context method."""
        action_data = {'target': 'monster', 'distance': 5}
        self.controller.current_goal_parameters = {'search.radius': 5}
        
        # Ensure plan_action_context exists (it should be created in __init__)
        if not hasattr(self.controller, 'plan_action_context') or self.controller.plan_action_context is None:
            self.controller.plan_action_context = ActionContext()
        
        # Set action data on the plan context
        self.controller.plan_action_context.target = 'monster'
        self.controller.plan_action_context.distance = 5
        
        # Test context building
        context = self.controller._build_execution_context('attack')
        
        # Verify it returns the singleton plan_action_context
        self.assertIs(context, self.controller.plan_action_context)
        
        # Verify action data is preserved on context
        self.assertEqual(context.target, 'monster')
        self.assertEqual(context.distance, 5)
        
        # Verify goal parameters were added
        self.assertEqual(context.get('search.radius'), 5)
        
        # Test with params in context
        self.controller.plan_action_context.x = 10
        self.controller.plan_action_context.y = 20
        
        context = self.controller._build_execution_context('move')
        
        # Verify params are preserved
        self.assertEqual(context.x, 10)
        self.assertEqual(context.y, 20)
    
    def test_build_execution_context_wait_action(self):
        """Test _build_execution_context for wait action."""
        # Mock the cooldown manager to return a specific wait duration
        self.controller.cooldown_manager = Mock()
        self.controller.cooldown_manager.calculate_wait_duration.return_value = 10
        
        # Ensure plan_action_context exists
        if not hasattr(self.controller, 'plan_action_context') or self.controller.plan_action_context is None:
            self.controller.plan_action_context = ActionContext()
        
        # Ensure wait_duration is cleaned up (base class will handle this)
        
        with patch.object(self.controller, '_refresh_character_state'):
            # Pass action_name to match how wait duration is detected
            context = self.controller._build_execution_context('wait')
            
            # Verify wait duration was added to context
            self.assertEqual(context.wait_duration, 10)
            
            # Verify it's the same plan context
            self.assertIs(context, self.controller.plan_action_context)
            
            # Verify cooldown manager was called
            self.controller.cooldown_manager.calculate_wait_duration.assert_called_once_with(self.mock_character_state)
    
    def test_reset_failed_goal(self):
        """Test reset_failed_goal method."""
        self.controller.mission_executor.reset_failed_goal = Mock()
        
        self.controller.reset_failed_goal('test_goal')
        
        self.controller.mission_executor.reset_failed_goal.assert_called_once_with('test_goal')
    
    def test_get_available_actions(self):
        """Test get_available_actions method."""
        self.controller.action_executor.get_available_actions.return_value = ['move', 'attack']
        
        actions = self.controller.get_available_actions()
        
        self.assertEqual(actions, ['move', 'attack'])
    
    def test_reload_action_configurations(self):
        """Test reload_action_configurations method."""
        # Mock reload methods
        self.controller.action_executor.reload_configuration = Mock()
        self.controller.reload_state_configurations = Mock()
        self.controller.mission_executor._load_configuration = Mock()
        self.controller.learning_manager.reload_configuration = Mock()
        self.controller.skill_goal_manager.reload_configuration = Mock()
        
        self.controller.reload_action_configurations()
        
        # Verify all reloads were called
        self.controller.action_executor.reload_configuration.assert_called_once()
        self.controller.reload_state_configurations.assert_called_once()
        self.controller.mission_executor._load_configuration.assert_called_once()
        self.controller.learning_manager.reload_configuration.assert_called_once()
        self.controller.skill_goal_manager.reload_configuration.assert_called_once()
    
    def test_execute_plan_no_plan(self):
        """Test execute_plan with no plan."""
        self.controller.current_plan = []
        
        result = self.controller.execute_plan()
        
        self.assertFalse(result)
    
    def test_execute_plan_success(self):
        """Test successful plan execution."""
        # Set up plan
        self.controller.current_plan = [
            {'name': 'move', 'x': 10, 'y': 15},
            {'name': 'rest'}
        ]
        self.controller.current_action_index = 0
        
        # Mock execute_next_action
        with patch.object(self.controller, 'execute_next_action') as mock_execute:
            # Simulate successful execution of both actions
            # After 2 actions, current_action_index will be 2 (>= len(plan))
            def mock_execute_side_effect():
                if self.controller.current_action_index < len(self.controller.current_plan):
                    self.controller.current_action_index += 1
                    return True
                return False
            
            mock_execute.side_effect = mock_execute_side_effect
            
            result = self.controller.execute_plan()
            
            self.assertTrue(result)
            self.assertFalse(self.controller.is_executing)
            self.assertEqual(mock_execute.call_count, 2)  # Only 2 actions in plan
    
    def test_execute_plan_failure(self):
        """Test failed plan execution."""
        self.controller.current_plan = [{'name': 'move'}]
        self.controller.current_action_index = 0
        
        with patch.object(self.controller, 'execute_next_action') as mock_execute:
            mock_execute.return_value = False
            
            result = self.controller.execute_plan()
            
            self.assertFalse(result)
    
    def test_execute_single_action_success(self):
        """Test _execute_single_action success."""
        action_data = {'x': 10, 'y': 15}
        
        # Mock dependencies
        mock_context = Mock()
        mock_context.action_results = {'result_key': 'result_value'}
        
        with patch.object(self.controller, '_build_execution_context') as mock_build:
            mock_build.return_value = mock_context
            
            mock_result = ActionResult(
                success=True,
                data={'moved': True},
                action_name='move'
            )
            self.controller.action_executor.execute_action.return_value = mock_result
            
            result = self.controller._execute_single_action('move', action_data)
            
            self.assertTrue(result)
            # Verify action was executed with correct parameters
            self.controller.action_executor.execute_action.assert_called_once_with(
                'move', self.mock_client, mock_context
            )
    
    def test_execute_single_action_failure(self):
        """Test _execute_single_action failure."""
        with patch.object(self.controller, '_build_execution_context') as mock_build:
            mock_build.return_value = Mock()
            
            mock_result = Mock()
            mock_result.success = False
            self.controller.action_executor.execute_action.return_value = mock_result
            
            result = self.controller._execute_single_action('move', {})
            
            self.assertFalse(result)
            # The actual implementation sets last_action_result to the mock result directly
            self.assertEqual(self.controller.last_action_result, mock_result)
    
    def test_execute_single_action_exception(self):
        """Test _execute_single_action with exception."""
        with patch.object(self.controller, '_build_execution_context') as mock_build:
            mock_build.side_effect = Exception("Test error")
            
            result = self.controller._execute_single_action('move', {})
            
            self.assertFalse(result)
    
    
    def test_is_plan_complete(self):
        """Test is_plan_complete method."""
        # Test with empty plan
        self.controller.current_plan = []
        self.assertTrue(self.controller.is_plan_complete())
        
        # Test with plan in progress
        self.controller.current_plan = ['action1', 'action2']
        self.controller.current_action_index = 1
        self.assertFalse(self.controller.is_plan_complete())
        
        # Test with plan complete
        self.controller.current_action_index = 2
        self.assertTrue(self.controller.is_plan_complete())
    
    def test_cancel_plan(self):
        """Test cancel_plan method."""
        self.controller.current_plan = ['action1', 'action2']
        self.controller.current_action_index = 1
        self.controller.is_executing = True
        
        self.controller.cancel_plan()
        
        self.assertEqual(self.controller.current_plan, [])
        self.assertEqual(self.controller.current_action_index, 0)
        self.assertFalse(self.controller.is_executing)
    
    def test_get_plan_status(self):
        """Test get_plan_status method."""
        self.controller.current_plan = [
            {'name': 'move'},
            {'name': 'attack'},
            {'name': 'rest'}
        ]
        self.controller.current_action_index = 1
        self.controller.is_executing = True
        
        status = self.controller.get_plan_status()
        
        self.assertTrue(status['has_plan'])
        self.assertEqual(status['plan_length'], 3)
        self.assertEqual(status['current_action_index'], 1)
        self.assertTrue(status['is_executing'])
        self.assertFalse(status['is_complete'])
        self.assertEqual(status['current_action'], 'attack')
    
    def test_get_current_world_state(self):
        """Test get_current_world_state method."""
        # Mock goal manager calculate_world_state
        calculated_state = {
            'character_level': 10,
            'location_status': {'at_bank': False}
        }
        self.controller.goal_manager.calculate_world_state.return_value = calculated_state
        
        # Set up persisted world state
        self.controller.world_state.data = {
            'inventory_updated': True,
            'location_status': {'at_workshop': True},  # Nested dict
            'custom_state': 'value'
        }
        
        with patch.object(self.controller, '_should_refresh_character_state') as mock_should:
            mock_should.return_value = False
            
            state = self.controller.get_current_world_state(force_refresh=False)
            
            # Verify calculated state
            self.assertEqual(state['character_level'], 10)
            
            # Verify nested state merging
            self.assertEqual(state['location_status']['at_bank'], False)  # From calculated
            self.assertEqual(state['location_status']['at_workshop'], True)  # From persisted
            
            # Verify non-calculated states are preserved
            self.assertEqual(state['inventory_updated'], True)
            self.assertEqual(state['custom_state'], 'value')
    
    def test_get_current_world_state_force_refresh(self):
        """Test get_current_world_state with force refresh."""
        self.controller.goal_manager.calculate_world_state.return_value = {}
        
        with patch.object(self.controller, '_refresh_character_state') as mock_refresh:
            self.controller.get_current_world_state(force_refresh=True)
            
            mock_refresh.assert_called_once()
    
    def test_update_world_state(self):
        """Test update_world_state method."""
        # Initial state
        self.controller.world_state.data = {
            'character_status': {'level': 10, 'hp': 80},
            'location_status': {'at_bank': False}
        }
        
        # Update state
        updates = {
            'character_status': {'hp': 90, 'xp': 1500},
            'new_category': {'new_data': True}
        }
        
        self.controller.update_world_state(updates)
        
        # Verify updates - note that update_world_state uses dict.update() 
        # which replaces entire values, not merging nested dicts
        self.assertEqual(self.controller.world_state.data['character_status'], {'hp': 90, 'xp': 1500})
        self.assertTrue(self.controller.world_state.data['new_category']['new_data'])
        self.controller.world_state.save.assert_called_once()
    
    def test_update_world_state_no_world_state(self):
        """Test update_world_state with no world state."""
        self.controller.world_state = None
        
        # Should not raise exception
        self.controller.update_world_state({'test': 'value'})
    
    def test_execute_autonomous_mission(self):
        """Test execute_autonomous_mission method."""
        mission_params = {'target_level': 15}
        self.controller.mission_executor.execute_progression_mission.return_value = True
        
        result = self.controller.execute_autonomous_mission(mission_params)
        
        self.assertTrue(result)
        self.controller.mission_executor.execute_progression_mission.assert_called_once_with(mission_params)
    
    def test_level_up_goal(self):
        """Test level_up_goal method."""
        self.controller.mission_executor.execute_level_progression.return_value = True
        
        result = self.controller.level_up_goal(target_level=15)
        
        self.assertTrue(result)
        self.controller.mission_executor.execute_level_progression.assert_called_once_with(15)
    
    def test_skill_up_goal(self):
        """Test skill_up_goal method."""
        self.controller.skill_goal_manager.achieve_skill_goal_with_goap.return_value = True
        
        # Mock get_current_world_state
        with patch.object(self.controller, 'get_current_world_state') as mock_get_state:
            mock_get_state.return_value = {'weaponcrafting_level': 5}
            
            result = self.controller.skill_up_goal(SkillType.WEAPONCRAFTING, 10)
            
            self.assertTrue(result)
            self.controller.skill_goal_manager.achieve_skill_goal_with_goap.assert_called_once_with(
                SkillType.WEAPONCRAFTING,
                10,
                {'weaponcrafting_level': 5},
                self.controller
            )
    
    def test_get_skill_progression_strategy(self):
        """Test get_skill_progression_strategy method."""
        expected_strategy = {'action': 'craft_items', 'priority': 1}
        self.controller.skill_goal_manager.get_skill_progression_strategy.return_value = expected_strategy
        
        strategy = self.controller.get_skill_progression_strategy(SkillType.WEAPONCRAFTING, 5)
        
        self.assertEqual(strategy, expected_strategy)
        self.controller.skill_goal_manager.get_skill_progression_strategy.assert_called_once_with(
            SkillType.WEAPONCRAFTING, 5
        )
    
    def test_get_available_skills(self):
        """Test get_available_skills method."""
        expected_skills = [SkillType.WEAPONCRAFTING, SkillType.COMBAT]
        self.controller.skill_goal_manager.get_available_skills.return_value = expected_skills
        
        skills = self.controller.get_available_skills()
        
        self.assertEqual(skills, expected_skills)
    
    def test_find_and_move_to_level_appropriate_monster(self):
        """Test find_and_move_to_level_appropriate_monster method."""
        # Mock action executor
        mock_result = Mock()
        mock_result.success = True
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            mock_context = Mock()
            mock_build_context.return_value = mock_context
            
            result = self.controller.find_and_move_to_level_appropriate_monster()
            
            self.assertTrue(result)
            self.controller.action_executor.execute_action.assert_called_once_with(
                'find_and_move_to_monster',
                self.mock_client,
                mock_context
            )
    
    def test_find_and_move_to_level_appropriate_monster_no_monsters(self):
        """Test find_and_move_to_level_appropriate_monster with no monsters found."""
        # Mock action executor to return failure (no monsters found)
        mock_result = Mock()
        mock_result.success = False
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            mock_context = Mock()
            mock_build_context.return_value = mock_context
            
            result = self.controller.find_and_move_to_level_appropriate_monster()
            
            self.assertFalse(result)
            self.controller.action_executor.execute_action.assert_called_once()
    
    def test_learn_from_map_exploration(self):
        """Test learn_from_map_exploration method."""
        # Mock knowledge base with proper data attribute
        self.controller.knowledge_base = Mock()
        self.controller.knowledge_base.data = {}  # Initialize as empty dict to avoid iteration issues
        
        # Mock map state - ensure it exists
        if not self.controller.map_state:
            self.controller.map_state = Mock()
        
        # Mock map response with proper data structure
        map_response = Mock()
        # Create data as a plain dict (not Mock with to_dict)
        map_response.data = {
            'x': 10,
            'y': 15,
            'content': {
                'type': 'monster',
                'code': 'goblin'
            }
        }
        
        self.controller.learn_from_map_exploration(10, 15, map_response)
        
        # Verify knowledge base learning was called with correct parameters
        self.controller.knowledge_base.learn_from_content_discovery.assert_called_once_with(
            'monster', 'goblin', 10, 15, {'type': 'monster', 'code': 'goblin'}
        )
        
        # Verify save was called
        self.controller.knowledge_base.save.assert_called_once()
    
    def test_learn_from_combat(self):
        """Test learn_from_combat method."""
        # Mock knowledge base with proper methods
        self.controller.knowledge_base = Mock()
        self.controller.knowledge_base.get_monster_combat_success_rate.return_value = 0.75  # 75% success rate
        
        # Ensure character_state has proper numeric hp and max_hp values
        self.mock_character_state.data['hp'] = 80
        self.mock_character_state.data['max_hp'] = 100
        self.mock_character_state.data['level'] = 10
        
        fight_data = {
            'turns': 3,
            'damage_dealt': 50,
            'damage_taken': 20,
            'xp': 100,
            'gold': 50
        }
        
        combat_context = {
            'post_combat_hp': 60
        }
        
        self.controller.learn_from_combat('goblin', 'win', 80, fight_data, combat_context)
        
        # Verify knowledge base recording was called
        self.controller.knowledge_base.record_combat_result.assert_called_once()
        
        # Verify save was called
        self.controller.knowledge_base.save.assert_called_once()
    
    def test_find_known_monsters_nearby(self):
        """Test find_known_monsters_nearby method."""
        # Mock learning manager
        expected_monsters = [
            {'code': 'goblin', 'x': 8, 'y': 12, 'level': 8}
        ]
        self.controller.learning_manager.find_known_monsters_nearby.return_value = expected_monsters
        
        # Character at position (5, 10) level 10
        monsters = self.controller.find_known_monsters_nearby(
            max_distance=15,
            character_level=10,
            level_range=3
        )
        
        # Verify delegation to learning manager
        self.controller.learning_manager.find_known_monsters_nearby.assert_called_once_with(
            self.mock_character_state, 15, 10, 3
        )
        
        # Verify result
        self.assertEqual(monsters, expected_monsters)
    
    def test_intelligent_monster_search(self):
        """Test intelligent_monster_search method."""
        # Mock action executor
        mock_result = Mock()
        mock_result.success = True
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            mock_context = Mock()
            mock_build_context.return_value = mock_context
            
            result = self.controller.intelligent_monster_search(search_radius=5)
            
            self.assertTrue(result)
            self.controller.action_executor.execute_action.assert_called_once_with(
                'intelligent_monster_search',
                self.mock_client,
                mock_context
            )
    
    def test_get_learning_insights(self):
        """Test get_learning_insights method."""
        expected_insights = {
            'monsters_known': 10,
            'locations_explored': 50
        }
        self.controller.learning_manager.get_learning_insights.return_value = expected_insights
        
        insights = self.controller.get_learning_insights()
        
        self.assertEqual(insights, expected_insights)
        self.controller.learning_manager.get_learning_insights.assert_called_once()
    
    def test_optimize_with_knowledge(self):
        """Test optimize_with_knowledge method."""
        expected_optimization = {
            'recommended_action': 'hunt',
            'target': 'goblin'
        }
        self.controller.learning_manager.optimize_with_knowledge.return_value = expected_optimization
        
        optimization = self.controller.optimize_with_knowledge('combat')
        
        self.assertEqual(optimization, expected_optimization)
        self.controller.learning_manager.optimize_with_knowledge.assert_called_once_with(
            self.mock_character_state, 'combat'
        )
    
    def test_learn_all_game_data_efficiently(self):
        """Test learn_all_game_data_efficiently method."""
        # Mock learning manager
        mock_result = {
            'success': True,
            'stats': {
                'resources': 10,
                'monsters': 15,
                'items': 20,
                'total': 45
            },
            'details': {},
            'errors': []
        }
        self.controller.learning_manager.learn_all_game_data_bulk.return_value = mock_result
        
        result = self.controller.learn_all_game_data_efficiently()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['success'], True)
        self.assertEqual(result['stats']['total'], 45)
        
        # Verify delegation to learning manager
        self.controller.learning_manager.learn_all_game_data_bulk.assert_called_once_with(self.mock_client)


if __name__ == '__main__':
    unittest.main()