"""Test unified state management through post-execution handler."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_executor import ActionExecutor
from src.controller.ai_player_controller import AIPlayerController
from src.lib.action_context import ActionContext


class TestUnifiedStateManagement(unittest.TestCase):
    """Test that unified state management works correctly."""
    
    @patch('src.controller.ai_player_controller.StateManagerMixin.__init__', return_value=None)
    @patch('src.controller.ai_player_controller.GOAPGoalManager')
    @patch('src.controller.ai_player_controller.ActionExecutor')
    @patch('src.controller.ai_player_controller.CooldownManager')
    @patch('src.controller.ai_player_controller.MissionExecutor')
    @patch('src.controller.ai_player_controller.SkillGoalManager')
    @patch('src.controller.ai_player_controller.GOAPExecutionManager')
    @patch('src.controller.ai_player_controller.LearningManager')
    def setUp(self, mock_learning, mock_goap, mock_skill, mock_mission, 
              mock_cooldown, mock_executor, mock_goal, mock_init):
        """Set up test fixtures."""
        self.mock_client = Mock()
        
        # Create a minimal controller without full initialization
        self.controller = AIPlayerController.__new__(AIPlayerController)
        self.controller.logger = Mock()
        self.controller.client = self.mock_client
        self.controller.action_context = {}
        
        # Mock the world state properly
        mock_world_state = Mock()
        mock_world_state.data = {}
        mock_world_state.save = Mock()
        self.controller.world_state = mock_world_state
        
        # Mock character state
        self.controller.character_state = Mock()
        self.controller.character_state.name = "test_character"
        self.controller.character_state.data = {
            'x': 0, 'y': 0, 'level': 1, 'hp': 100, 'max_hp': 100
        }
        
    def test_action_with_reactions_updates_state(self):
        """Test that action reactions update world state through unified handler."""
        # Create action executor
        executor = ActionExecutor()
        
        # Mock the action factory to return a mock action with reactions
        mock_action = Mock()
        mock_action.execute.return_value = {
            'success': True,
            'equipment_status': {
                'upgrade_status': 'analyzing',
                'target_slot': 'weapon'
            }
        }
        
        # Set up reactions on the mock action class
        mock_action.__class__.reactions = {
            'equipment_status': {
                'upgrade_status': 'analyzing',
                'target_slot': 'weapon'
            }
        }
        
        # Add required methods to controller
        self.controller.update_world_state = Mock()
        self.controller.get_current_world_state = Mock(return_value={'equipment_status': {}})
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            # Build context
            context = ActionContext.from_controller(self.controller, {})
            
            # Execute action
            result = executor.execute_action('analyze_equipment', {}, self.mock_client, context)
            
            # Verify action was executed
            self.assertTrue(result.success)
            
            # Verify world state was updated through unified API
            # The update_world_state method should be called with the full world state including reactions
            self.controller.update_world_state.assert_called()
            
            # Check that the call included the equipment_status updates
            call_args = self.controller.update_world_state.call_args[0][0]
            self.assertIn('equipment_status', call_args)
            self.assertEqual(call_args['equipment_status']['upgrade_status'], 'analyzing')
            self.assertEqual(call_args['equipment_status']['target_slot'], 'weapon')
    
    def test_template_resolution_in_reactions(self):
        """Test that template variables in reactions are resolved correctly."""
        executor = ActionExecutor()
        
        # Mock action that returns a value used in template
        mock_action = Mock()
        mock_action.execute.return_value = {
            'success': True,
            'selected_item': 'wooden_staff',
            'target_slot': 'weapon'
        }
        
        # Set up reactions with template variables
        mock_action.__class__.reactions = {
            'equipment_status': {
                'selected_item': '${selected_item}',
                'target_slot': '${target_slot}'
            }
        }
        
        # Add required methods to controller
        self.controller.update_world_state = Mock()
        self.controller.get_current_world_state = Mock(return_value={'equipment_status': {}})
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            context = ActionContext.from_controller(self.controller, {})
            result = executor.execute_action('select_recipe', {}, self.mock_client, context)
            
            self.assertTrue(result.success)
            
            # Verify update_world_state was called
            self.controller.update_world_state.assert_called()
            
            # Check that templates were resolved in the call
            call_args = self.controller.update_world_state.call_args[0][0]
            self.assertIn('equipment_status', call_args)
            self.assertEqual(call_args['equipment_status']['selected_item'], 'wooden_staff')
            self.assertEqual(call_args['equipment_status']['target_slot'], 'weapon')
    
    def test_action_context_preserved_between_actions(self):
        """Test that action context is preserved for inter-action data flow."""
        executor = ActionExecutor()
        
        # First action sets some data
        mock_action1 = Mock()
        mock_action1.execute.return_value = {
            'success': True,
            'selected_item': 'copper_sword',
            'target_slot': 'weapon'
        }
        mock_action1.__class__.reactions = {}
        
        # Add required methods to controller
        self.controller.update_world_state = Mock()
        self.controller.get_current_world_state = Mock(return_value={})
        
        # Execute first action
        with patch.object(executor.factory, 'create_action', return_value=mock_action1):
            context = ActionContext.from_controller(self.controller, {})
            executor.execute_action('select_recipe', {}, self.mock_client, context)
        
        # Verify action context was updated
        self.assertIn('select_recipe', self.controller.action_context)
        self.assertIn('selected_item', self.controller.action_context)
        self.assertEqual(self.controller.action_context['selected_item'], 'copper_sword')
        self.assertEqual(self.controller.action_context['target_slot'], 'weapon')
        
        # Second action should have access to this data
        context2 = ActionContext.from_controller(self.controller, {})
        # ActionContext stores previous results in controller.action_context
        self.assertEqual(self.controller.action_context['selected_item'], 'copper_sword')
        self.assertEqual(self.controller.action_context['target_slot'], 'weapon')
    
    def test_no_state_updates_on_failed_action(self):
        """Test that state is not updated when action fails."""
        executor = ActionExecutor()
        
        # Mock a failing action
        mock_action = Mock()
        mock_action.execute.return_value = {
            'success': False,
            'error': 'Action failed'
        }
        mock_action.__class__.reactions = {
            'equipment_status': {
                'upgrade_status': 'failed'
            }
        }
        
        # Add required methods to controller
        self.controller.update_world_state = Mock()
        self.controller.get_current_world_state = Mock(return_value={'equipment_status': {}})
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            context = ActionContext.from_controller(self.controller, {})
            result = executor.execute_action('test_action', {}, self.mock_client, context)
            
            # Verify action failed
            self.assertFalse(result.success)
            
            # Verify world state was NOT updated (due to failed action)
            self.controller.update_world_state.assert_not_called()


if __name__ == '__main__':
    unittest.main()