"""Unit tests for AIPlayerController with full metaprogramming integration."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml
from src.controller.actions.base import ActionResult
from src.controller.ai_player_controller import AIPlayerController
from src.game.character.state import CharacterState

from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class TestAIPlayerControllerMetaprogramming(UnifiedContextTestBase):
    """Test cases for AIPlayerController with metaprogramming approach."""
    
    def setUp(self) -> None:
        """Set up test fixtures with proper metaprogramming configuration."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test action configuration
        self.action_config_file = os.path.join(self.temp_dir, 'action_configurations.yaml')
        action_config = {
            'action_configurations': {
                'move': {'type': 'builtin', 'description': 'Move character'},
                'attack': {'type': 'builtin', 'description': 'Attack monster'},
                'rest': {'type': 'builtin', 'description': 'Rest character'},
                'map_lookup': {'type': 'builtin', 'description': 'Lookup map location'},
                'find_monsters': {'type': 'builtin', 'description': 'Find monsters'}
            },
            'composite_actions': {}
        }
        
        with open(self.action_config_file, 'w') as f:
            yaml.dump(action_config, f)
        
        # Create test state configuration
        self.state_config_file = os.path.join(self.temp_dir, 'state_configurations.yaml')
        state_config = {
            'state_classes': {
                'world_state': {
                    'class_path': 'src.controller.world.state.WorldState',
                    'constructor_params': {'name': 'world'},
                    'singleton': True
                },
                'knowledge_base': {
                    'class_path': 'src.controller.knowledge.base.KnowledgeBase',
                    'constructor_params': {'filename': os.path.join(self.temp_dir, 'test_knowledge.yaml')},
                    'singleton': True
                }
            }
        }
        
        with open(self.state_config_file, 'w') as f:
            yaml.dump(state_config, f)
        
        # Set up mock client using fixtures
        self.mock_client = create_mock_client()
        
        # Mock character state
        self.mock_character_state = Mock(spec=CharacterState)
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'x': 5,
            'y': 10,
            'level': 1,
            'xp': 0,
            'hp': 100,
            'max_hp': 100
        }
    
    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_controller_initialization(self, mock_state_loader, mock_action_executor):
        """Test that controller initializes with metaprogramming components."""
        # Mock the components
        mock_executor_instance = Mock()
        mock_state_loader_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        mock_state_loader.return_value = mock_state_loader_instance
        
        # Mock state creation
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            
            # Verify metaprogramming components are initialized
            self.assertIsNotNone(controller.action_executor)
            self.assertEqual(controller.client, self.mock_client)
            self.assertEqual(controller.world_state, mock_world_state)
            self.assertEqual(controller.knowledge_base, mock_knowledge_base)
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_execute_action_through_metaprogramming(self, mock_action_executor_class):
        """Test that actions are executed through the metaprogramming system."""
        # Set up mocks
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Add empty data dict
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock successful action execution
                mock_result = ActionResult(
                    success=True,
                    data={'success': True, 'x': 15, 'y': 20},
                    action_name='move'
                )
                mock_executor_instance.execute_action.return_value = mock_result
                
                # Execute action - with unified context, set parameters on context
                controller.plan_action_context.x = 15
                controller.plan_action_context.y = 20
                result = controller._execute_action('move')
                
                # Verify execution through metaprogramming
                self.assertTrue(result)
                mock_executor_instance.execute_action.assert_called_once()
                
                # Verify context was built correctly
                call_args = mock_executor_instance.execute_action.call_args
                # With unified context, the signature is execute_action(action_name, client, context)
                # So context is the 3rd argument (index 2)
                context = call_args[0][2]
                
                # Context should be ActionContext instance with proper attributes
                self.assertEqual(context.character_name, 'test_character')
                self.assertEqual(context.character_x, 5)
                self.assertEqual(context.character_y, 10)
                # Verify action data was set
                self.assertEqual(context.x, 15)
                self.assertEqual(context.y, 20)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_execute_action_failure(self, mock_state_loader, mock_action_executor):
        """Test handling of action execution failure."""
        mock_executor_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            
            # Mock failed action execution
            mock_result = ActionResult(
                    success=False,
                    data=None,
                    action_name='move',
                    error='Action failed'
            
                )
            mock_executor_instance.execute_action.return_value = mock_result
            
            # Execute action - with unified context, set parameters on context
            controller.plan_action_context.x = 5
            controller.plan_action_context.y = 10
            success, result_data = controller._execute_action('move')
            
            # Verify failure handling
            self.assertFalse(success)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_context_building(self, mock_state_loader, mock_action_executor):
        """Test that execution context is built correctly."""
        mock_executor_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            controller.character_state = self.mock_character_state
            
            # Build context
            action_data = {'param': 'value'}
            context = controller._build_execution_context(action_data)
            
            # Verify context contents
            self.assertEqual(context.controller, controller)
            self.assertEqual(context.character_state, self.mock_character_state)
            self.assertEqual(context.world_state, mock_world_state)
            self.assertEqual(context.knowledge_base, mock_knowledge_base)
            self.assertEqual(context.character_name, 'test_character')
            self.assertEqual(context.character_x, 5)
            self.assertEqual(context.character_y, 10)
            self.assertEqual(context.character_level, 1)
            self.assertEqual(context.character_hp, 100)  # Changed from pre_combat_hp
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_get_available_actions(self, mock_action_executor_class):
        """Test getting available actions through metaprogramming."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        mock_executor_instance.get_available_actions.return_value = ['move', 'attack', 'rest', 'map_lookup', 'find_monsters', 'hunt']
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Add empty data dict
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                
                # Get available actions
                actions = controller.get_available_actions()
                
                # Verify delegation to action executor
                self.assertEqual(actions, ['move', 'attack', 'rest', 'map_lookup', 'find_monsters', 'hunt'])
                mock_executor_instance.get_available_actions.assert_called_once()
    
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_reload_configurations(self, mock_action_executor_class):
        """Test reloading configurations."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Add empty data dict
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                
                # Mock reload methods
                with patch.object(controller, 'reload_state_configurations') as mock_state_reload:
                    controller.reload_action_configurations()
                    
                    # Verify both reloads are called
                    mock_executor_instance.reload_configuration.assert_called_once()
                    mock_state_reload.assert_called_once()
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_character_state_management(self, mock_state_loader, mock_action_executor):
        """Test character state management methods."""
        mock_executor_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            
            # Test setting character state
            self.assertIsNone(controller.character_state)
            controller.set_character_state(self.mock_character_state)
            self.assertEqual(controller.character_state, self.mock_character_state)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_goap_integration_preserved(self, mock_state_loader, mock_action_executor):
        """Test that GOAP integration methods are preserved."""
        mock_executor_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            
            # Verify GOAP integration is now delegated to managers
            self.assertTrue(hasattr(controller, 'goap_execution_manager'))
            self.assertTrue(hasattr(controller, 'execute_plan'))
            # GOAP methods moved to GOAPExecutionManager
            self.assertTrue(hasattr(controller.goap_execution_manager, 'create_world_with_planner'))
            self.assertTrue(hasattr(controller.goap_execution_manager, 'create_plan'))
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.lib.state_loader.StateConfigLoader')
    def test_learning_method_preservation(self, mock_state_loader, mock_action_executor):
        """Test that learning methods are preserved for backward compatibility."""
        mock_executor_instance = Mock()
        mock_action_executor.return_value = mock_executor_instance
        
        mock_world_state = Mock()
        mock_world_state.data = {}  # Add empty data dict
        mock_knowledge_base = Mock()
        
        with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
            mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
            
            controller = AIPlayerController(self.mock_client)
            
            # Verify learning methods exist (even if they delegate to metaprogramming system)
            self.assertTrue(hasattr(controller, 'learn_from_map_exploration'))
            self.assertTrue(hasattr(controller, 'learn_from_combat'))
            self.assertTrue(hasattr(controller, 'intelligent_monster_search'))


if __name__ == '__main__':
    unittest.main()