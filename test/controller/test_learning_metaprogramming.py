"""Tests for learning integration with metaprogramming approach."""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.base import ActionResult
from src.controller.ai_player_controller import AIPlayerController
from src.game.character.state import CharacterState

from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class TestLearningMetaprogramming(UnifiedContextTestBase):
    """Test learning integration with metaprogramming action execution."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
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
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_move_action_learning_callback(self, mock_action_executor_class, mock_get_character):
        """Test that move actions can be executed through metaprogramming system."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        # Mock get_character to prevent API calls during refresh
        mock_get_character.return_value = None
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Ensure data is a dict, not Mock
                mock_knowledge_base = Mock()
                mock_knowledge_base.data = {}  # Ensure data is a dict, not Mock
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock successful action execution
                mock_result = ActionResult(
                    success=True,
                    message="Moved successfully",
                    action_name='move',
                    data={'response': Mock()}
                )
                mock_executor_instance.execute_action.return_value = mock_result
                
                # Execute action using unified context
                controller.plan_action_context.x = 5
                controller.plan_action_context.y = 10
                success, result_data = controller._execute_action('move')
                
                # Architecture compliance - verify action execution through metaprogramming
                self.assertTrue(success)
                mock_executor_instance.execute_action.assert_called_once()
                
                # Verify learning functionality is available through LearningManager
                self.assertTrue(hasattr(controller, 'learning_manager'))
                self.assertIsNotNone(controller.learning_manager)
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_attack_action_learning_callback(self, mock_action_executor_class, mock_get_character):
        """Test that attack actions can be executed through metaprogramming system."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        # Mock get_character to prevent API calls during refresh
        mock_get_character.return_value = None
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Ensure data is a dict, not Mock
                mock_knowledge_base = Mock()
                mock_knowledge_base.data = {}  # Ensure data is a dict, not Mock
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock successful attack execution
                mock_result = ActionResult(
                    success=True,
                    message="Attack successful",
                    action_name='attack',
                    data={'response': Mock()}
                )
                mock_executor_instance.execute_action.return_value = mock_result
                
                # Execute action using unified context
                success, result_data = controller._execute_action('attack')
                
                # Architecture compliance - verify action execution through metaprogramming
                self.assertTrue(success)
                mock_executor_instance.execute_action.assert_called_once()
                
                # Verify learning functionality is available through LearningManager
                self.assertTrue(hasattr(controller, 'learning_manager'))
                self.assertIsNotNone(controller.learning_manager)
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_composite_action_learning_integration(self, mock_action_executor_class, mock_get_character):
        """Test that composite actions can be executed through metaprogramming system."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        # Mock get_character to prevent API calls during refresh
        mock_get_character.return_value = None
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Ensure data is a dict, not Mock
                mock_knowledge_base = Mock()
                mock_knowledge_base.data = {}  # Ensure data is a dict, not Mock
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                controller.character_state = self.mock_character_state
                
                # Mock composite action response
                mock_result = ActionResult(
                    success=True,
                    message="Hunt successful",
                    action_name='hunt',
                    data={'composite': True}
                )
                mock_executor_instance.execute_action.return_value = mock_result
                
                # Execute composite action using unified context
                controller.plan_action_context.search_radius = 15
                success, result_data = controller._execute_action('hunt')
                
                # Architecture compliance - verify composite action execution
                self.assertTrue(success)
                mock_executor_instance.execute_action.assert_called_once()
                
                # Verify learning functionality is available through LearningManager
                self.assertTrue(hasattr(controller, 'learning_manager'))
                self.assertIsNotNone(controller.learning_manager)
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_learning_method_availability(self, mock_action_executor_class, mock_get_character):
        """Test that learning methods are available on the controller."""
        mock_executor_instance = Mock()
        mock_action_executor_class.return_value = mock_executor_instance
        
        # Mock get_character to prevent API calls during refresh
        mock_get_character.return_value = None
        
        with patch.object(AIPlayerController, 'initialize_state_management'):
            with patch.object(AIPlayerController, 'create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_world_state.data = {}  # Ensure data is a dict, not Mock
                mock_knowledge_base = Mock()
                mock_knowledge_base.data = {}  # Ensure data is a dict, not Mock
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                
                # Verify learning functionality is available through LearningManager
                self.assertTrue(hasattr(controller, 'learning_manager'))
                self.assertIsNotNone(controller.learning_manager)
                # Verify find_known_monsters_nearby method still exists
                self.assertTrue(hasattr(controller, 'find_known_monsters_nearby'))
                self.assertTrue(callable(controller.find_known_monsters_nearby))


if __name__ == '__main__':
    unittest.main()