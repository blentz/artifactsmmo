"""
Test unified ActionContext implementation in AI Player Controller.

This test module verifies that ActionContext properly persists data between
actions in a plan, fixing the issue where data stored with set_result()
was not available to subsequent actions.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.ai_player_controller import AIPlayerController
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestUnifiedActionContext(unittest.TestCase):
    """Test cases for unified ActionContext persistence across actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.controller = AIPlayerController(client=self.mock_client)
        
        # Mock the action executor
        self.mock_action_executor = Mock()
        self.controller.action_executor = self.mock_action_executor
        
        # Mock character state
        self.mock_char_state = Mock()
        self.mock_char_state.data = {
            'name': 'test_character',
            'level': 1,
            'hp': 100,
            'max_hp': 100
        }
        self.controller.character_state = self.mock_char_state
        
    def test_unified_context_created_on_plan_execution(self):
        """Test that a unified ActionContext is created when executing a plan."""
        # Set up a test plan
        self.controller.current_plan = [
            {'name': 'action1', 'params': {}},
            {'name': 'action2', 'params': {}}
        ]
        self.controller.current_action_index = 0
        
        # Mock successful action execution
        self.mock_action_executor.execute_action.return_value = ActionResult(
            success=True,
            data={'result': 'success'}
        )
        
        # Execute the plan
        result = self.controller.execute_plan()
        
        # Verify unified context was created
        self.assertIsNotNone(self.controller.plan_action_context)
        self.assertIsInstance(self.controller.plan_action_context, ActionContext)
        self.assertTrue(result)
        
    def test_context_persists_between_actions(self):
        """Test that ActionContext data persists between actions in a plan."""
        # Set up a test plan
        self.controller.current_plan = [
            {'name': 'analyze_equipment_gaps', 'params': {}},
            {'name': 'select_optimal_slot', 'params': {}}
        ]
        self.controller.current_action_index = 0
        
        # Track the contexts passed to each action
        contexts_seen = []
        
        def capture_context(action_name, client, context):
            contexts_seen.append((action_name, context))
            
            # Simulate first action storing data
            if action_name == 'analyze_equipment_gaps':
                context.set_result(StateParameters.EQUIPMENT_GAP_ANALYSIS, {
                    'weapon': {'missing': True, 'urgency_score': 100}
                })
            
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = capture_context
        
        # Execute the plan
        result = self.controller.execute_plan()
        
        # Verify both actions received the same context instance
        self.assertEqual(len(contexts_seen), 2)
        self.assertIs(contexts_seen[0][1], contexts_seen[1][1])
        
        # Verify data persisted from first to second action
        second_action_context = contexts_seen[1][1]
        gap_analysis = second_action_context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS)
        self.assertIsNotNone(gap_analysis)
        self.assertEqual(gap_analysis['weapon']['urgency_score'], 100)
        
    def test_action_data_updated_per_action(self):
        """Test that parameters are preserved in unified context while preserving results."""
        # With unified context, plans only contain action names
        self.controller.current_plan = [
            {'name': 'action1'},
            {'name': 'action2'}
        ]
        self.controller.current_action_index = 0
        
        # Set initial parameters on unified context using StateParameters
        self.controller.plan_action_context.set(StateParameters.CHARACTER_LEVEL, 5)
        self.controller.plan_action_context.set(StateParameters.GOAL_CURRENT_GOAL, 'combat')
        
        action_params_seen = []
        
        def capture_action_params(action_name, client, context):
            # Capture parameters set on context for this action
            params_dict = {
                'character_level': context.get(StateParameters.CHARACTER_LEVEL),
                'current_goal': context.get(StateParameters.GOAL_CURRENT_GOAL)
            }
            
            action_params_seen.append({
                'action': action_name,
                'params': params_dict,
                'has_shared_data': context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS) is not None
            })
            
            # First action stores a result
            if action_name == 'action1':
                context.set_result(StateParameters.EQUIPMENT_GAP_ANALYSIS, 'from_action1')
            
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = capture_action_params
        
        # Execute the plan
        self.controller.execute_plan()
        
        # Verify parameters were set for each action
        self.assertEqual(len(action_params_seen), 2)
        
        # With unified context, both actions see all parameters
        self.assertEqual(action_params_seen[0]['action'], 'action1')
        self.assertEqual(action_params_seen[0]['params']['character_level'], 5)
        self.assertEqual(action_params_seen[0]['params']['current_goal'], 'combat')
        self.assertFalse(action_params_seen[0]['has_shared_data'])
        
        # Second action should still have both params and access to shared data from action1
        self.assertEqual(action_params_seen[1]['action'], 'action2')
        self.assertEqual(action_params_seen[1]['params']['character_level'], 5)
        self.assertEqual(action_params_seen[1]['params']['current_goal'], 'combat')
        self.assertTrue(action_params_seen[1]['has_shared_data'])
        
    def test_singleton_context_always_exists(self):
        """Test that singleton context always exists and is used."""
        # The plan_action_context should always exist after initialization
        self.assertIsNotNone(self.controller.plan_action_context)
        self.assertIsInstance(self.controller.plan_action_context, ActionContext)
        
        # Set up single action plan
        self.controller.current_plan = [{'name': 'test_action', 'params': {'test': 'value'}}]
        self.controller.current_action_index = 0
        
        captured_context = None
        
        def capture_context(action_name, client, context):
            nonlocal captured_context
            captured_context = context
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = capture_context
        
        # Set parameters on unified context before execution
        self.controller.plan_action_context.test = 'value'
        
        # Execute using _execute_action directly
        success, _ = self.controller._execute_action('test_action')
        
        # Verify singleton context was used
        self.assertTrue(success)
        self.assertIsNotNone(captured_context)
        self.assertIs(captured_context, self.controller.plan_action_context)
        # Check that the parameter was set as a flattened property
        self.assertEqual(captured_context.test, 'value')
        
    def test_goal_parameters_included_in_context(self):
        """Test that goal parameters are included in the action context."""
        # Set goal parameters
        self.controller.current_goal_parameters = {
            'target_level': 5,
            'goal_type': 'combat'
        }
        
        # Set up a test plan
        self.controller.current_plan = [{'name': 'test_action', 'params': {}}]
        self.controller.current_action_index = 0
        
        captured_context = None
        
        def capture_context(action_name, client, context):
            nonlocal captured_context
            captured_context = context
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = capture_context
        
        # Execute the plan
        self.controller.execute_plan()
        
        # Verify goal parameters are accessible
        self.assertEqual(captured_context.get(StateParameters.CHARACTER_LEVEL), 5)
        self.assertEqual(captured_context.get(StateParameters.GOAL_CURRENT_GOAL), 'combat')
        
    def test_context_preserves_complex_data_structures(self):
        """Test that complex data structures are preserved across actions."""
        # Set up a test plan
        self.controller.current_plan = [
            {'name': 'action1', 'params': {}},
            {'name': 'action2', 'params': {}},
            {'name': 'action3', 'params': {}}
        ]
        self.controller.current_action_index = 0
        
        complex_data = {
            'nested': {
                'deep': {
                    'value': 42,
                    'list': [1, 2, 3]
                }
            },
            'items': [
                {'id': 1, 'name': 'item1'},
                {'id': 2, 'name': 'item2'}
            ]
        }
        
        results_by_action = {}
        
        def execute_action(action_name, client, context):
            if action_name == 'action1':
                # First action stores complex data
                context.set_result(StateParameters.EQUIPMENT_GAP_ANALYSIS, complex_data)
                context.set_result(StateParameters.TARGET_ITEM, 'value1')
            elif action_name == 'action2':
                # Second action reads and modifies
                data = context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS)
                results_by_action['action2_read'] = data
                context.set_result(StateParameters.SELECTED_RECIPE, 'value2')
                # Add to the complex data
                if data:
                    data['nested']['action2_added'] = True
            elif action_name == 'action3':
                # Third action verifies all data is available
                results_by_action['action3_complex'] = context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS)
                results_by_action['action3_data1'] = context.get(StateParameters.TARGET_ITEM)
                results_by_action['action3_data2'] = context.get(StateParameters.SELECTED_RECIPE)
            
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = execute_action
        
        # Execute the plan
        self.controller.execute_plan()
        
        # Verify complex data was preserved and modifications were visible
        self.assertIsNotNone(results_by_action['action2_read'])
        self.assertEqual(results_by_action['action2_read']['nested']['deep']['value'], 42)
        
        self.assertIsNotNone(results_by_action['action3_complex'])
        self.assertEqual(results_by_action['action3_complex']['nested']['deep']['value'], 42)
        self.assertTrue(results_by_action['action3_complex']['nested']['action2_added'])
        
        self.assertEqual(results_by_action['action3_data1'], 'value1')
        self.assertEqual(results_by_action['action3_data2'], 'value2')
        
    def test_equipment_upgrade_flow_with_unified_context(self):
        """Test the specific equipment upgrade flow that was failing."""
        # Set up the equipment upgrade plan
        self.controller.current_plan = [
            {'name': 'analyze_equipment_gaps', 'params': {}},
            {'name': 'select_optimal_slot', 'params': {}},
            {'name': 'select_recipe', 'params': {}}
        ]
        self.controller.current_action_index = 0
        
        execution_log = []
        
        def execute_equipment_action(action_name, client, context):
            if action_name == 'analyze_equipment_gaps':
                # Simulate equipment gap analysis
                gap_analysis = {
                    'weapon': {
                        'slot_name': 'weapon',
                        'missing': True,
                        'current_item': None,
                        'urgency_score': 100,
                        'reason': 'no equipment'
                    },
                    'helmet': {
                        'slot_name': 'helmet',
                        'missing': True,
                        'current_item': None,
                        'urgency_score': 80,
                        'reason': 'no equipment'
                    }
                }
                context.set_result(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
                execution_log.append(f"{action_name}: stored gap analysis")
                
            elif action_name == 'select_optimal_slot':
                # This action should find the gap analysis
                gap_analysis = context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS)
                if gap_analysis:
                    # Select weapon slot as highest priority
                    context.set_result(StateParameters.TARGET_SLOT, 'weapon')
                    context.set_result(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
                    execution_log.append(f"{action_name}: found gap analysis, selected weapon")
                else:
                    execution_log.append(f"{action_name}: ERROR - no gap analysis found!")
                    return ActionResult(success=False, error="No gap analysis found")
                    
            elif action_name == 'select_recipe':
                # This action should find the selected slot
                slot = context.get(StateParameters.TARGET_SLOT)
                skill = context.get(StateParameters.TARGET_CRAFT_SKILL)
                if slot and skill:
                    context.set_result(StateParameters.TARGET_ITEM, 'copper_dagger')
                    execution_log.append(f"{action_name}: found slot={slot}, skill={skill}, selected copper_dagger")
                else:
                    execution_log.append(f"{action_name}: ERROR - no slot/skill found!")
                    return ActionResult(success=False, error="No slot/skill found")
            
            return ActionResult(success=True, data={})
        
        self.mock_action_executor.execute_action.side_effect = execute_equipment_action
        
        # Execute the plan
        result = self.controller.execute_plan()
        
        # Verify the flow completed successfully
        self.assertTrue(result)
        self.assertEqual(len(execution_log), 3)
        self.assertIn("stored gap analysis", execution_log[0])
        self.assertIn("found gap analysis", execution_log[1])
        self.assertIn("selected copper_dagger", execution_log[2])
        
        # Verify final context has all the data
        final_context = self.controller.plan_action_context
        self.assertIsNotNone(final_context.get(StateParameters.EQUIPMENT_GAP_ANALYSIS))
        self.assertEqual(final_context.get(StateParameters.TARGET_SLOT), 'weapon')
        self.assertEqual(final_context.get(StateParameters.TARGET_ITEM), 'copper_dagger')


if __name__ == '__main__':
    unittest.main()