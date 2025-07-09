"""Test unified state management through post-execution handler."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_executor import ActionExecutor
from src.controller.ai_player_controller import AIPlayerController
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


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
        
        # Mock additional required attributes
        self.controller.cooldown_manager = Mock()
        self.controller.update_world_state = Mock()
        self.controller.get_current_world_state = Mock(return_value={})
        
    def test_action_with_reactions_updates_state(self):
        """Test that action reactions update state using StateParameters."""
        # Create action executor
        executor = ActionExecutor()
        
        # Mock the action factory to return a mock action with reactions
        from src.controller.actions.base import ActionResult
        mock_action = Mock()
        mock_action.execute.return_value = ActionResult(
            success=True,
            data={}
        )
        
        # Set up reactions using flat StateParameters (no nested dictionaries)
        mock_action.__class__.reactions = {
            StateParameters.EQUIPMENT_UPGRADE_STATUS: 'analyzing',
            StateParameters.EQUIPMENT_TARGET_SLOT: 'weapon'
        }
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor.factory, '_load_action_parameters', return_value=None), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            # Build context
            context = ActionContext.from_controller(self.controller, {})
            context.controller = self.controller
            
            # Execute action
            result = executor.execute_action('analyze_equipment', self.mock_client, context)
            
            # Verify action was executed
            self.assertTrue(result.success)
            
            # Verify state was updated in context using StateParameters
            self.assertEqual(context.get(StateParameters.EQUIPMENT_UPGRADE_STATUS), 'analyzing')
            self.assertEqual(context.get(StateParameters.EQUIPMENT_TARGET_SLOT), 'weapon')
            
            # Verify boolean flags were recalculated
            self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_TARGET_SLOT))
    
    def test_direct_value_assignment_in_reactions(self):
        """Test that actions use direct value assignment in reactions (no templates)."""
        executor = ActionExecutor()
        
        # Mock action that sets explicit values
        from src.controller.actions.base import ActionResult
        mock_action = Mock()
        mock_action.execute.return_value = ActionResult(
            success=True,
            data={}
        )
        
        # Set up reactions with direct values (no template variables)
        mock_action.__class__.reactions = {
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'wooden_staff',
            StateParameters.EQUIPMENT_TARGET_SLOT: 'weapon'
        }
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor.factory, '_load_action_parameters', return_value=None), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            context = ActionContext.from_controller(self.controller, {})
            context.controller = self.controller
            result = executor.execute_action('select_recipe', self.mock_client, context)
            
            self.assertTrue(result.success)
            
            # Verify direct value assignment worked
            self.assertEqual(context.get(StateParameters.EQUIPMENT_SELECTED_ITEM), 'wooden_staff')
            self.assertEqual(context.get(StateParameters.EQUIPMENT_TARGET_SLOT), 'weapon')
            
            # Verify boolean flags were recalculated
            self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_TARGET_SLOT))
            self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
    
    def test_action_context_preserved_between_actions(self):
        """Test that StateParameters persist correctly across action executions."""
        context = ActionContext()
        
        # First action sets data using StateParameters
        context.set_result(StateParameters.SELECTED_ITEM, 'copper_sword')
        context.set_result(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        
        # Verify data persists (simulating between-action state)
        self.assertEqual(context.get(StateParameters.SELECTED_ITEM), 'copper_sword')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_TARGET_SLOT), 'weapon')
        
        # Second action can access the data and add more
        context.set_result(StateParameters.WORKFLOW_STEP, 'crafting_ready')
        
        # All data should still be accessible through unified context
        self.assertEqual(context.get(StateParameters.SELECTED_ITEM), 'copper_sword')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_TARGET_SLOT), 'weapon')
        self.assertEqual(context.get(StateParameters.WORKFLOW_STEP), 'crafting_ready')
    
    def test_no_state_updates_on_failed_action(self):
        """Test that state is not updated when action fails."""
        executor = ActionExecutor()
        
        # Mock a failing action
        from src.controller.actions.base import ActionResult
        mock_action = Mock()
        mock_action.execute.return_value = ActionResult(
            success=False,
            error='Action failed'
        )
        mock_action.__class__.reactions = {
            StateParameters.EQUIPMENT_UPGRADE_STATUS: 'failed'
        }
        
        with patch.object(executor.factory, 'create_action', return_value=mock_action), \
             patch.object(executor.factory, '_load_action_parameters', return_value=None), \
             patch.object(executor, '_get_action_class', return_value=mock_action.__class__):
            context = ActionContext.from_controller(self.controller, {})
            context.controller = self.controller
            
            # Store initial state
            initial_upgrade_status = context.get(StateParameters.EQUIPMENT_UPGRADE_STATUS)
            
            result = executor.execute_action('analyze_equipment', self.mock_client, context)
            
            # Verify action failed
            self.assertFalse(result.success)
            
            # Verify state was NOT updated (should remain the same)
            self.assertEqual(context.get(StateParameters.EQUIPMENT_UPGRADE_STATUS), initial_upgrade_status)


if __name__ == '__main__':
    unittest.main()