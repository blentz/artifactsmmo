"""Tests for learning integration with metaprogramming approach."""

import unittest
from unittest.mock import Mock, patch
import tempfile
import os

from src.controller.ai_player_controller import AIPlayerController
from src.controller.action_executor import ActionResult
from src.game.character.state import CharacterState
from test.fixtures import create_mock_client


class TestLearningMetaprogramming(unittest.TestCase):
    """Test learning integration with metaprogramming action execution."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock client
        self.mock_client = create_mock_client()
        
        # Mock character state
        self.mock_character_state = Mock(spec=CharacterState)
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'x': 0,
            'y': 0,
            'level': 1,
            'hp': 100,
            'max_hp': 100
        }
    
    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_move_action_learning_callback(self, mock_action_executor_class):
        """Test that move actions trigger learning callbacks through metaprogramming."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock learning method
                controller.learn_from_map_exploration = Mock()
                
                # Mock response with exploration data
                mock_response = Mock()
                mock_response.data.character.x = 5
                mock_response.data.character.y = 10
                
                mock_result = ActionResult(
                    success=True,
                    response=mock_response,
                    action_name='move'
                )
                
                # Configure executor to call the learning callback
                def mock_execute_action(action_name, action_data, client, context):
                    # Simulate the action executor calling learning callbacks
                    if context and 'controller' in context:
                        controller = context['controller']
                        if hasattr(controller, 'learn_from_map_exploration'):
                            controller.learn_from_map_exploration(5, 10, mock_response)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute action
                action_data = {'x': 5, 'y': 10}
                result = controller._execute_action('move', action_data)
                
                # Verify learning was called
                self.assertTrue(result)
                controller.learn_from_map_exploration.assert_called_once_with(5, 10, mock_response)
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_attack_action_learning_callback(self, mock_action_executor_class):
        """Test that attack actions trigger combat learning callbacks."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock learning method
                controller.learn_from_combat = Mock()
                
                # Mock response with combat data
                mock_response = Mock()
                mock_response.data.fight.monster = {'code': 'test_monster'}
                mock_response.data.fight.result = 'win'
                
                mock_result = ActionResult(
                    success=True,
                    response=mock_response,
                    action_name='attack'
                )
                
                # Configure executor to call the learning callback
                def mock_execute_action(action_name, action_data, client, context):
                    # Simulate the action executor calling learning callbacks
                    if context and 'controller' in context and action_name == 'attack':
                        controller = context['controller']
                        pre_combat_hp = context.get('pre_combat_hp', 100)
                        if hasattr(controller, 'learn_from_combat'):
                            controller.learn_from_combat('test_monster', 'win', pre_combat_hp)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute action
                action_data = {}
                result = controller._execute_action('attack', action_data)
                
                # Verify learning was called
                self.assertTrue(result)
                controller.learn_from_combat.assert_called_once_with('test_monster', 'win', 100)
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_composite_action_learning_integration(self, mock_action_executor_class):
        """Test that composite actions can trigger multiple learning callbacks."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock learning methods
                controller.learn_from_map_exploration = Mock()
                controller.learn_from_combat = Mock()
                
                # Mock composite action response
                mock_result = ActionResult(
                    success=True,
                    response={'composite': True, 'steps': [
                        {'action': 'move', 'success': True},
                        {'action': 'attack', 'success': True}
                    ]},
                    action_name='hunt'
                )
                
                # Configure executor to simulate composite action learning
                def mock_execute_action(action_name, action_data, client, context):
                    # Simulate composite action triggering multiple callbacks
                    if action_name == 'hunt' and context and 'controller' in context:
                        controller = context['controller']
                        # Simulate move learning
                        if hasattr(controller, 'learn_from_map_exploration'):
                            controller.learn_from_map_exploration(15, 20, Mock())
                        # Simulate combat learning
                        if hasattr(controller, 'learn_from_combat'):
                            controller.learn_from_combat('hunted_monster', 'win', 80)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute composite action
                action_data = {'search_radius': 15}
                result = controller._execute_action('hunt', action_data)
                
                # Verify both learning methods were called
                self.assertTrue(result)
                controller.learn_from_map_exploration.assert_called_once()
                controller.learn_from_combat.assert_called_once()
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_learning_method_availability(self, mock_action_executor_class):
        """Test that learning methods are available on the controller."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                
                # Verify learning methods exist and are callable
                self.assertTrue(hasattr(controller, 'learn_from_map_exploration'))
                self.assertTrue(hasattr(controller, 'learn_from_combat'))
                self.assertTrue(hasattr(controller, 'intelligent_monster_search'))
                self.assertTrue(callable(controller.learn_from_map_exploration))
                self.assertTrue(callable(controller.learn_from_combat))
                self.assertTrue(callable(controller.intelligent_monster_search))


if __name__ == '__main__':
    unittest.main()