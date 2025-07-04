"""Comprehensive tests for AIPlayerController to achieve high coverage."""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, call

from src.controller.ai_player_controller import AIPlayerController
from src.controller.actions.base import ActionResult
from src.controller.skill_goal_manager import SkillType
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.lib.action_context import ActionContext


class TestAIPlayerControllerComprehensive(unittest.TestCase):
    """Comprehensive test cases for AIPlayerController."""
    
    def setUp(self):
        """Set up test fixtures."""
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
            'cooldown_expires_at': None
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
                
                self.controller = AIPlayerController(self.mock_client, self.mock_goal_manager)
                
        # Set character and map states
        self.controller.character_state = self.mock_character_state
        self.controller.map_state = self.mock_map_state
    
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
        new_char_state.data = {
            'x': 15,
            'y': 20,
            'level': 5,
            'hp': 50,
            'max_hp': 60
        }
        
        # Mock _invalidate_location_states
        with patch.object(self.controller, '_invalidate_location_states') as mock_invalidate:
            # Set character state
            self.controller.set_character_state(new_char_state)
            
            # Verify character state is set
            self.assertEqual(self.controller.character_state, new_char_state)
            
            # Verify location states were invalidated
            mock_invalidate.assert_called_once()
    
    @patch('src.controller.ai_player_controller.YamlData')
    def test_invalidate_location_states(self, mock_yaml_data):
        """Test location state invalidation."""
        # Mock YAML config
        mock_config = Mock()
        mock_config.data = {
            'location_based_states': ['at_bank', 'at_workshop', 'at_resource_location', 'at_location']
        }
        mock_yaml_data.return_value = mock_config
        
        # Set up world state with location data (flat structure as implementation expects)
        self.mock_world_state.data = {
            'at_bank': True,
            'at_workshop': 'weaponcrafting',
            'at_resource_location': True,
            'at_location': True,
            'resource_location_known': True,
            'workshop_location_known': True
        }
        
        # Mock update_world_state to capture the updates
        update_calls = []
        def capture_update(updates):
            update_calls.append(updates)
        
        with patch.object(self.controller, 'update_world_state', side_effect=capture_update):
            # Call invalidate
            self.controller._invalidate_location_states()
            
            # Verify update_world_state was called with correct values
            self.assertEqual(len(update_calls), 1)
            expected_updates = {
                'at_bank': False,
                'at_workshop': False,
                'at_resource_location': False,
                'at_location': False
            }
            self.assertEqual(update_calls[0], expected_updates)
    
    def test_set_map_state(self):
        """Test setting map state."""
        new_map_state = Mock(spec=MapState)
        
        self.controller.set_map_state(new_map_state)
        
        # Verify map state is set
        self.assertEqual(self.controller.map_state, new_map_state)
    
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
                mock_execute.assert_called_once_with('wait', {'wait_duration': 5})
                mock_refresh.assert_called_once()
    
    def test_check_and_handle_cooldown_inactive(self):
        """Test cooldown handling when character is not on cooldown."""
        # Set no cooldown expiration
        self.mock_character_state.data['cooldown_expiration'] = None
        
        result = self.controller.check_and_handle_cooldown()
        
        # Verify returns True (ready to act) when no cooldown
        self.assertTrue(result)
    
    def test_execute_next_action_empty_plan(self):
        """Test execute_next_action with empty plan."""
        self.controller.current_plan = []
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
        
        # Mock execute_action
        with patch.object(self.controller, '_execute_action') as mock_execute:
            mock_execute.return_value = (True, {'success': True})
            
            result = self.controller.execute_next_action()
            
            self.assertTrue(result)
            self.assertEqual(self.controller.current_action_index, 1)
            mock_execute.assert_called_once_with('move', {'name': 'move', 'x': 10, 'y': 15})
    
    def test_execute_next_action_failure(self):
        """Test failed execution of next action."""
        # Set up plan
        self.controller.current_plan = [
            {'name': 'attack', 'target': 'monster'}
        ]
        self.controller.current_action_index = 0
        
        # Mock execute_action
        with patch.object(self.controller, '_execute_action') as mock_execute:
            mock_execute.return_value = (False, {'success': False, 'error': 'No monster found'})
            
            result = self.controller.execute_next_action()
            
            self.assertFalse(result)
            # Index should not advance on failure
            self.assertEqual(self.controller.current_action_index, 0)
    
    
    def test_execute_action_regular(self):
        """Test _execute_action with regular action."""
        # Mock action executor
        self.controller.action_executor = Mock()
        mock_result = ActionResult(
            success=True,
            data={'moved': True, 'x': 10, 'y': 15},
            action_name='move'
        )
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building and refresh
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            with patch.object(self.controller, '_refresh_character_state'):
                with patch.object(self.controller, '_is_character_on_cooldown') as mock_cooldown:
                    mock_context = Mock()
                    mock_build_context.return_value = mock_context
                    mock_cooldown.return_value = False
                    
                    # Mock action context update
                    with patch.object(self.controller, '_update_action_context_from_response'):
                        success, result = self.controller._execute_action('move', {'x': 10, 'y': 15})
                        
                        self.assertTrue(success)
                        self.assertEqual(result, {})
    
    def test_execute_cooldown_wait(self):
        """Test _execute_cooldown_wait method."""
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        self.controller.cooldown_manager.handle_cooldown_with_wait.return_value = True
        
        result = self.controller._execute_cooldown_wait()
        
        self.assertTrue(result)
        self.controller.cooldown_manager.handle_cooldown_with_wait.assert_called_once_with(
            self.mock_character_state, self.controller.action_executor, self.controller
        )
    
    def test_is_character_on_cooldown(self):
        """Test _is_character_on_cooldown method."""
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        
        # Test with cooldown active
        self.controller.cooldown_manager.is_character_on_cooldown.return_value = True
        self.assertTrue(self.controller._is_character_on_cooldown())
        
        # Test with no cooldown
        self.controller.cooldown_manager.is_character_on_cooldown.return_value = False
        self.assertFalse(self.controller._is_character_on_cooldown())
        
        # Verify cooldown manager was called with character state
        self.controller.cooldown_manager.is_character_on_cooldown.assert_called_with(self.mock_character_state)
    
    def test_should_refresh_character_state(self):
        """Test _should_refresh_character_state method."""
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        
        # Test with no character state
        self.controller.character_state = None
        self.assertTrue(self.controller._should_refresh_character_state())
        
        # Test with valid character state - delegates to cooldown manager
        self.controller.character_state = self.mock_character_state
        self.controller.cooldown_manager.should_refresh_character_state.return_value = False
        self.assertFalse(self.controller._should_refresh_character_state())
        
        # Verify cooldown manager was called
        self.controller.cooldown_manager.should_refresh_character_state.assert_called_once()
    
    @patch('src.controller.ai_player_controller.get_character')
    def test_refresh_character_state(self, mock_get_character):
        """Test _refresh_character_state method."""
        # Mock API response
        mock_response = Mock()
        mock_char_data = Mock()
        mock_get_character.return_value = mock_response
        mock_response.data = mock_char_data
        
        # Mock cooldown manager
        self.controller.cooldown_manager = Mock()
        
        # Call refresh
        self.controller._refresh_character_state()
        
        # Verify API was called
        mock_get_character.assert_called_once_with(
            name='test_character',
            client=self.mock_client
        )
        
        # Verify character state update was called
        self.mock_character_state.update_from_api_response.assert_called_once_with(mock_char_data)
        self.mock_character_state.save.assert_called_once()
        
        # Verify cooldown manager was notified
        self.controller.cooldown_manager.mark_character_state_refreshed.assert_called_once()
    
    def test_build_execution_context(self):
        """Test _build_execution_context method."""
        action_data = {
            'target': 'monster',
            'distance': 5
        }
        
        context = self.controller._build_execution_context(action_data, 'attack')
        
        # Verify context attributes
        self.assertIsInstance(context, ActionContext)
        self.assertEqual(context.controller, self.controller)
        self.assertEqual(context.character_state, self.mock_character_state)
        self.assertEqual(context.world_state, self.mock_world_state)
        self.assertEqual(context.get('target'), 'monster')
        self.assertEqual(context.get('distance'), 5)
        self.assertEqual(context.character_name, 'test_character')
        self.assertEqual(context.character_x, 5)
        self.assertEqual(context.character_y, 10)
    
    def test_reset_failed_goal(self):
        """Test reset_failed_goal method."""
        # This is currently a no-op but test it exists
        self.controller.reset_failed_goal('test_goal')
        # Should not raise any exceptions
    
    def test_get_available_actions(self):
        """Test get_available_actions method."""
        # Mock action executor
        self.controller.action_executor = Mock()
        self.controller.action_executor.get_available_actions.return_value = [
            'move', 'attack', 'rest', 'craft'
        ]
        
        actions = self.controller.get_available_actions()
        
        self.assertEqual(actions, ['move', 'attack', 'rest', 'craft'])
        self.controller.action_executor.get_available_actions.assert_called_once()
    
    def test_reload_action_configurations(self):
        """Test reload_action_configurations method."""
        # Mock action executor and reload method
        self.controller.action_executor = Mock()
        
        with patch.object(self.controller, 'reload_state_configurations') as mock_reload_state:
            self.controller.reload_action_configurations()
            
            # Verify both reloads were called
            self.controller.action_executor.reload_configuration.assert_called_once()
            mock_reload_state.assert_called_once()
    
    def test_execute_plan_empty(self):
        """Test execute_plan with empty plan."""
        self.controller.current_plan = []
        
        result = self.controller.execute_plan()
        
        self.assertFalse(result)  # Empty plan returns False
    
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
            self.assertEqual(mock_execute.call_count, 2)  # Only 2 actions in plan
    
    def test_execute_single_action(self):
        """Test _execute_single_action method."""
        action_data = {'x': 10, 'y': 15}
        
        # Mock action executor
        self.controller.action_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.response = {'moved': True, 'x': 10, 'y': 15}
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            mock_context = Mock()
            mock_context.action_results = {'test': 'result'}
            mock_build_context.return_value = mock_context
            
            with patch.object(self.controller, '_update_action_context_from_response'):
                with patch.object(self.controller, '_update_action_context_from_results'):
                    result = self.controller._execute_single_action('move', action_data)
                    
                    self.assertTrue(result)
                    self.controller.action_executor.execute_action.assert_called_once_with(
                        'move', action_data, self.mock_client, mock_context
                    )
    
    def test_update_action_context_from_response(self):
        """Test _update_action_context_from_response method."""
        # Initialize action_context
        self.controller.action_context = {}
        
        # Test with dict response
        mock_response = {
            'x': 10,
            'y': 15,
            'cooldown': 5,
            'moved': True
        }
        
        self.controller._update_action_context_from_response('move', mock_response)
        
        # Verify context was updated with the response data
        self.assertEqual(self.controller.action_context['x'], 10)
        self.assertEqual(self.controller.action_context['y'], 15)
        self.assertEqual(self.controller.action_context['cooldown'], 5)
        self.assertEqual(self.controller.action_context['moved'], True)
    
    def test_update_action_context_from_results(self):
        """Test _update_action_context_from_results method."""
        # Initialize action_context
        self.controller.action_context = {}
        
        action_results = {
            'moved': True,
            'new_x': 20,
            'new_y': 25,
            'monster_found': 'goblin'
        }
        
        self.controller._update_action_context_from_results('find_monsters', action_results)
        
        # Verify context was updated with action results
        self.assertEqual(self.controller.action_context['moved'], True)
        self.assertEqual(self.controller.action_context['new_x'], 20)
        self.assertEqual(self.controller.action_context['new_y'], 25)
        self.assertEqual(self.controller.action_context['monster_found'], 'goblin')
    
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
        
        self.assertTrue(status['is_executing'])
        self.assertTrue(status['has_plan'])
        self.assertEqual(status['plan_length'], 3)
        self.assertEqual(status['current_action_index'], 1)
        self.assertEqual(status['current_action'], 'attack')
        self.assertFalse(status['is_complete'])
    
    def test_get_current_world_state(self):
        """Test get_current_world_state method."""
        # Set up world state
        self.mock_world_state.data = {
            'character_status': {'level': 10},
            'location_status': {'at_bank': False}
        }
        
        # Mock goal manager calculate_world_state
        self.controller.goal_manager = Mock()
        expected_state = {
            'character_status': {'level': 10, 'hp': 100},
            'location_status': {'at_bank': False}
        }
        self.controller.goal_manager.calculate_world_state.return_value = expected_state
        
        # Mock should refresh
        with patch.object(self.controller, '_should_refresh_character_state') as mock_should_refresh:
            mock_should_refresh.return_value = False
            
            # Test without force refresh
            state = self.controller.get_current_world_state(force_refresh=False)
            
            self.assertIn('character_status', state)
            self.assertIn('location_status', state)
            self.assertEqual(state['character_status']['level'], 10)
    
    def test_update_world_state(self):
        """Test update_world_state method."""
        # Initial state
        self.mock_world_state.data = {
            'character_status': {'level': 10, 'hp': 80},
            'location_status': {'at_bank': False}
        }
        
        # Update state (note: update() replaces entire keys)
        updates = {
            'character_status': {'level': 10, 'hp': 90, 'xp': 1500},
            'new_category': {'new_data': True}
        }
        
        self.controller.update_world_state(updates)
        
        # Verify updates (entire character_status is replaced)
        self.assertEqual(self.mock_world_state.data['character_status']['hp'], 90)
        self.assertEqual(self.mock_world_state.data['character_status']['xp'], 1500)
        self.assertEqual(self.mock_world_state.data['character_status']['level'], 10)
        self.assertTrue(self.mock_world_state.data['new_category']['new_data'])
    
    def test_execute_autonomous_mission(self):
        """Test execute_autonomous_mission method."""
        mission_params = {'target_level': 15}
        
        # Mock mission executor
        self.controller.mission_executor = Mock()
        self.controller.mission_executor.execute_progression_mission.return_value = True
        
        result = self.controller.execute_autonomous_mission(mission_params)
        
        self.assertTrue(result)
        self.controller.mission_executor.execute_progression_mission.assert_called_once_with(mission_params)
    
    def test_level_up_goal(self):
        """Test level_up_goal method."""
        # Mock mission executor
        self.controller.mission_executor = Mock()
        self.controller.mission_executor.execute_level_progression.return_value = True
        
        result = self.controller.level_up_goal(target_level=15)
        
        self.assertTrue(result)
        self.controller.mission_executor.execute_level_progression.assert_called_once_with(15)
    
    def test_skill_up_goal(self):
        """Test skill_up_goal method."""
        # Mock skill goal manager
        self.controller.skill_goal_manager = Mock()
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
        # Mock skill goal manager
        self.controller.skill_goal_manager = Mock()
        expected_strategy = {'action': 'craft_items', 'priority': 1}
        self.controller.skill_goal_manager.get_skill_progression_strategy.return_value = expected_strategy
        
        strategy = self.controller.get_skill_progression_strategy(SkillType.WEAPONCRAFTING, 5)
        
        self.assertEqual(strategy, expected_strategy)
        self.controller.skill_goal_manager.get_skill_progression_strategy.assert_called_once_with(
            SkillType.WEAPONCRAFTING, 5
        )
    
    def test_get_available_skills(self):
        """Test get_available_skills method."""
        # Mock skill goal manager
        self.controller.skill_goal_manager = Mock()
        expected_skills = [SkillType.WEAPONCRAFTING, SkillType.COMBAT]
        self.controller.skill_goal_manager.get_available_skills.return_value = expected_skills
        
        skills = self.controller.get_available_skills()
        
        self.assertEqual(skills, expected_skills)
    
    def test_find_and_move_to_level_appropriate_monster(self):
        """Test find_and_move_to_level_appropriate_monster method."""
        # Mock action executor
        self.controller.action_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        self.controller.action_executor.execute_action.return_value = mock_result
        
        # Mock context building
        with patch.object(self.controller, '_build_execution_context') as mock_build_context:
            mock_context = Mock()
            mock_build_context.return_value = mock_context
            
            result = self.controller.find_and_move_to_level_appropriate_monster(search_radius=5, level_range=2)
            
            self.assertTrue(result)
            self.controller.action_executor.execute_action.assert_called_once_with(
                'find_and_move_to_monster', 
                {'search_radius': 5, 'level_range': 2}, 
                self.mock_client, 
                mock_context
            )
    
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
        
        # Get the actual call arguments
        call_args = self.controller.knowledge_base.record_combat_result.call_args[0]
        self.assertEqual(call_args[0], 'goblin')  # monster_code
        self.assertEqual(call_args[1], 'win')     # result
        # Character data should have post-combat HP from context
        self.assertEqual(call_args[2]['hp'], 60)  # Updated HP from combat_context
        self.assertEqual(call_args[2]['hp_before'], 80)  # pre_combat_hp
        self.assertEqual(call_args[3], fight_data)  # fight_data
        
        # Verify save was called
        self.controller.knowledge_base.save.assert_called_once()
        
        # Verify success rate was queried
        self.controller.knowledge_base.get_monster_combat_success_rate.assert_called_once_with('goblin', 10)
    
    def test_find_known_monsters_nearby(self):
        """Test find_known_monsters_nearby method."""
        # Mock learning manager
        self.controller.learning_manager = Mock()
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
        self.controller.action_executor = Mock()
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
                {'search_radius': 5},
                self.mock_client,
                mock_context
            )
    
    def test_get_learning_insights(self):
        """Test get_learning_insights method."""
        # Mock learning manager
        self.controller.learning_manager = Mock()
        expected_insights = {
            'monsters_known': 10,
            'locations_explored': 50,
            'combat_wins': 25
        }
        self.controller.learning_manager.get_learning_insights.return_value = expected_insights
        
        insights = self.controller.get_learning_insights()
        
        self.assertEqual(insights, expected_insights)
        self.controller.learning_manager.get_learning_insights.assert_called_once()
    
    def test_optimize_with_knowledge(self):
        """Test optimize_with_knowledge method."""
        # Mock learning manager
        self.controller.learning_manager = Mock()
        expected_optimization = {
            'recommended_action': 'hunt',
            'target': 'goblin',
            'reason': 'optimal_xp'
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
        self.controller.learning_manager = Mock()
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