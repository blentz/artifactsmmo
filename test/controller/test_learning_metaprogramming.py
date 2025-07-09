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
        """Test that move actions trigger learning callbacks through metaprogramming."""
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
                
                # Initialize current_plan to avoid iteration errors
                controller.current_plan = []
                controller.current_action_index = 0
                
                # Mock learning method
                controller.learn_from_map_exploration = Mock()
                
                # Mock response with exploration data
                mock_response = Mock()
                mock_response.data.character.x = 5
                mock_response.data.character.y = 10
                
                mock_result = ActionResult(
                    success=True,
                    message="Moved successfully",
                    action_name='move',
                    data={'response': mock_response}
                )
                
                # Configure executor to call the learning callback
                def mock_execute_action(action_name, client, context):
                    # Simulate the action executor calling learning callbacks
                    if context and hasattr(context, 'controller'):
                        controller_from_context = context.controller
                        if hasattr(controller_from_context, 'learn_from_map_exploration'):
                            controller_from_context.learn_from_map_exploration(5, 10, mock_response)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute action using unified context
                # Set parameters on the action context
                controller.plan_action_context.x = 5
                controller.plan_action_context.y = 10
                result = controller._execute_action('move')
                
                # Verify learning was called
                self.assertTrue(result)
                controller.learn_from_map_exploration.assert_called_once_with(5, 10, mock_response)
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_attack_action_learning_callback(self, mock_action_executor_class, mock_get_character):
        """Test that attack actions trigger combat learning callbacks."""
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
                
                # Initialize current_plan to avoid iteration errors
                controller.current_plan = []
                controller.current_action_index = 0
                
                # Mock learning method
                controller.learn_from_combat = Mock()
                
                # Mock response with combat data
                mock_response = Mock()
                mock_response.data.fight.monster = {'code': 'test_monster'}
                mock_response.data.fight.result = 'win'
                
                mock_result = ActionResult(
                    success=True,
                    message="Attack successful",
                    action_name='attack',
                    data={'response': mock_response}
                )
                
                # Configure executor to call the learning callback
                def mock_execute_action(action_name, client, context):
                    # Simulate the action executor calling learning callbacks
                    if context and hasattr(context, 'controller') and action_name == 'attack':
                        from src.lib.state_parameters import StateParameters
                        controller_from_context = context.controller
                        # Use StateParameters for pre_combat_hp
                        pre_combat_hp = context.get(StateParameters.COMBAT_PRE_COMBAT_HP)
                        if pre_combat_hp == 0:
                            pre_combat_hp = 100  # Default test value
                        if hasattr(controller_from_context, 'learn_from_combat'):
                            controller_from_context.learn_from_combat('test_monster', 'win', pre_combat_hp)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute action using unified context
                result = controller._execute_action('attack')
                
                # Verify learning was called
                self.assertTrue(result)
                # The pre_combat_hp uses 100 when the default 0 is found
                controller.learn_from_combat.assert_called_once_with('test_monster', 'win', 100)
    
    @patch('src.controller.ai_player_controller.get_character')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    def test_composite_action_learning_integration(self, mock_action_executor_class, mock_get_character):
        """Test that composite actions can trigger multiple learning callbacks."""
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
                
                # Initialize current_plan to avoid iteration errors
                controller.current_plan = []
                controller.current_action_index = 0
                
                # Mock learning methods
                controller.learn_from_map_exploration = Mock()
                controller.learn_from_combat = Mock()
                
                # Mock composite action response
                mock_result = ActionResult(
                    success=True,
                    message="Hunt successful",
                    action_name='hunt',
                    data={'composite': True, 'steps': [
                        {'action': 'move', 'success': True},
                        {'action': 'attack', 'success': True}
                    ]}
                )
                
                # Configure executor to simulate composite action learning
                def mock_execute_action(action_name, client, context):
                    # Simulate composite action triggering multiple callbacks
                    if action_name == 'hunt' and context and hasattr(context, 'controller'):
                        controller_from_context = context.controller
                        # Simulate move learning
                        if hasattr(controller_from_context, 'learn_from_map_exploration'):
                            controller_from_context.learn_from_map_exploration(15, 20, Mock())
                        # Simulate combat learning
                        if hasattr(controller_from_context, 'learn_from_combat'):
                            controller_from_context.learn_from_combat('hunted_monster', 'win', 80)
                    return mock_result
                
                mock_executor_instance.execute_action.side_effect = mock_execute_action
                
                # Execute composite action using unified context
                controller.plan_action_context.search_radius = 15
                result = controller._execute_action('hunt')
                
                # Verify both learning methods were called
                self.assertTrue(result)
                controller.learn_from_map_exploration.assert_called_once()
                controller.learn_from_combat.assert_called_once()
    
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
                
                # Verify learning methods exist and are callable
                self.assertTrue(hasattr(controller, 'learn_from_map_exploration'))
                self.assertTrue(hasattr(controller, 'learn_from_combat'))
                self.assertTrue(hasattr(controller, 'intelligent_monster_search'))
                self.assertTrue(callable(controller.learn_from_map_exploration))
                self.assertTrue(callable(controller.learn_from_combat))
                self.assertTrue(callable(controller.intelligent_monster_search))


if __name__ == '__main__':
    unittest.main()