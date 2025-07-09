"""Test module for GatherResourceQuantityAction."""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.gather_resource_quantity import GatherResourceQuantityAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestGatherResourceQuantityAction(unittest.TestCase):
    """Test cases for GatherResourceQuantityAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = GatherResourceQuantityAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = GatherResourceQuantityAction()
        self.assertIsInstance(action, GatherResourceQuantityAction)
        self.assertEqual(action.max_attempts, 20)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['location_context']['at_resource'], True)
        self.assertEqual(action.conditions['materials']['status'], 'insufficient')
        self.assertEqual(action.reactions['materials']['status'], 'sufficient')
        self.assertEqual(action.weight, 2.5)
    
    def test_execute_no_gathering_goal(self):
        """Test execution when no gathering goal is set."""
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No gathering goal set")
    
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_already_have_sufficient(self, mock_get_character):
        """Test execution when already have sufficient materials."""
        # Mock inventory response
        mock_item = Mock()
        mock_item.code = "iron_ore"
        mock_item.quantity = 10
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item]
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'iron_ore', 'quantity': 5}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Successfully gathered iron_ore to meet goal")
        self.assertTrue(result.data['goal_met'])
        self.assertEqual(result.data['final_quantity'], 10)
        self.assertEqual(result.state_changes['materials']['status'], 'sufficient')
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_successful_gathering(self, mock_get_character, mock_executor_class):
        """Test successful gathering over multiple attempts."""
        # Mock inventory responses - start with 0, then 3, then 7, then final check 7
        mock_responses = []
        for quantity in [0, 3, 7, 7]:  # Added final check
            mock_item = Mock()
            mock_item.code = "copper_ore"
            mock_item.quantity = quantity
            mock_response = Mock()
            mock_response.data = Mock()
            mock_response.data.inventory = [mock_item]
            mock_responses.append(mock_response)
        
        mock_get_character.side_effect = mock_responses
        
        # Mock action executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        # Mock gather results as ActionResult objects
        gather_results = [
            ActionResult(success=True, data={'items_obtained': [{'code': 'copper_ore', 'quantity': 3}], 'cooldown_seconds': 0}),
            ActionResult(success=True, data={'items_obtained': [{'code': 'copper_ore', 'quantity': 4}], 'cooldown_seconds': 0})
        ]
        mock_executor.execute_action.side_effect = gather_results
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'copper_ore', 'quantity': 7}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Successfully gathered copper_ore to meet goal")
        self.assertTrue(result.data['goal_met'])
        self.assertEqual(result.data['final_quantity'], 7)
        self.assertEqual(mock_executor.execute_action.call_count, 2)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_gathering_with_failures(self, mock_get_character, mock_executor_class):
        """Test gathering with some failed attempts."""
        # Mock inventory responses - always returns 0 to simulate not reaching goal
        mock_item = Mock()
        mock_item.code = "ash_wood"
        mock_item.quantity = 0
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item]
        mock_get_character.return_value = mock_response
        
        # Mock action executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        # Mix of successful and failed gather attempts
        gather_results = [
            ActionResult(success=False, data={}),  # Failed attempt
            ActionResult(success=True, data={'items_obtained': [{'code': 'ash_wood', 'quantity': 2}]}),
            ActionResult(success=False, data={}),  # Failed attempt (was None)
            ActionResult(success=True, data={'items_obtained': []})  # No items obtained
        ]
        mock_executor.execute_action.side_effect = gather_results
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'ash_wood', 'quantity': 10}
        )
        
        # Set max attempts to match the number of mock results
        self.action.max_attempts = 4
        
        result = self.action.execute(self.mock_client, context)
        
        # Should still succeed but mark as partial
        if not result.success:
            print(f"Test failed with error: {result.error}")
            print(f"Result data: {result.data}")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Partially gathered ash_wood")
        self.assertFalse(result.data['goal_met'])
        self.assertEqual(result.data['attempts'], 4)
        self.assertEqual(result.state_changes['materials']['status'], 'partial')
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_max_attempts_reached(self, mock_get_character, mock_executor_class):
        """Test when max attempts is reached."""
        # Mock inventory always returns 0
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = []
        mock_get_character.return_value = mock_response
        
        # Mock action executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        mock_executor.execute_action.return_value = ActionResult(success=True, data={'items_obtained': []})
        
        # Set max attempts to small number for testing
        self.action.max_attempts = 3
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'gold_ore', 'quantity': 5}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Partially gathered gold_ore")
        self.assertEqual(result.data['attempts'], 3)
        self.assertEqual(mock_executor.execute_action.call_count, 3)
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_with_cooldown(self, mock_get_character, mock_executor_class):
        """Test execution when cooldown is encountered."""
        # Mock inventory
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = []
        mock_get_character.return_value = mock_response
        
        # Mock action executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        # Return result with cooldown
        mock_executor.execute_action.return_value = ActionResult(
            success=True, 
            data={
                'items_obtained': [{'code': 'diamond', 'quantity': 1}],
                'cooldown_seconds': 10
            }
        )
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'diamond', 'quantity': 5}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        # Should stop on cooldown
        self.assertTrue(result.success)
        self.assertEqual(mock_executor.execute_action.call_count, 1)
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'iron_ore', 'quantity': 5}
        )
        
        # Mock exception in _get_current_quantity
        with patch.object(self.action, '_get_current_quantity', side_effect=Exception("API error")):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Failed to gather resource quantity: API error")
    
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_get_current_quantity_success(self, mock_get_character):
        """Test _get_current_quantity with successful response."""
        mock_item1 = Mock()
        mock_item1.code = "copper_ore"
        mock_item1.quantity = 5
        
        mock_item2 = Mock()
        mock_item2.code = "iron_ore"
        mock_item2.quantity = 10
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item1, mock_item2]
        mock_get_character.return_value = mock_response
        
        quantity = self.action._get_current_quantity(self.mock_client, self.character_name, "iron_ore")
        self.assertEqual(quantity, 10)
        
        quantity = self.action._get_current_quantity(self.mock_client, self.character_name, "gold_ore")
        self.assertEqual(quantity, 0)
    
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_get_current_quantity_no_response(self, mock_get_character):
        """Test _get_current_quantity with no response."""
        mock_get_character.return_value = None
        
        quantity = self.action._get_current_quantity(self.mock_client, self.character_name, "iron_ore")
        self.assertEqual(quantity, 0)
    
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_get_current_quantity_exception(self, mock_get_character):
        """Test _get_current_quantity with exception."""
        mock_get_character.side_effect = Exception("Network error")
        
        quantity = self.action._get_current_quantity(self.mock_client, self.character_name, "iron_ore")
        self.assertEqual(quantity, 0)
    
    def test_create_success_result(self):
        """Test _create_success_result method."""
        result = self.action._create_success_result("iron_ore", 10, 15)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Successfully gathered iron_ore to meet goal")
        self.assertEqual(result.data['material'], "iron_ore")
        self.assertEqual(result.data['quantity_needed'], 10)
        self.assertEqual(result.data['final_quantity'], 15)
        self.assertTrue(result.data['goal_met'])
        self.assertEqual(result.state_changes['materials']['status'], 'sufficient')
        self.assertTrue(result.state_changes['materials']['gathered'])
        self.assertTrue(result.state_changes['inventory']['updated'])
    
    def test_create_partial_success_result(self):
        """Test _create_partial_success_result method."""
        result = self.action._create_partial_success_result("copper_ore", 20, 12, 5)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Partially gathered copper_ore")
        self.assertEqual(result.data['material'], "copper_ore")
        self.assertEqual(result.data['quantity_needed'], 20)
        self.assertEqual(result.data['final_quantity'], 12)
        self.assertEqual(result.data['attempts'], 5)
        self.assertFalse(result.data['goal_met'])
        self.assertEqual(result.state_changes['materials']['status'], 'partial')
        self.assertTrue(result.state_changes['materials']['gathered'])
        self.assertTrue(result.state_changes['inventory']['updated'])
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "GatherResourceQuantityAction()")
    
    @patch('src.controller.action_executor.ActionExecutor')
    @patch('src.controller.actions.gather_resource_quantity.get_character_api')
    def test_execute_with_different_material_in_gather_result(self, mock_get_character, mock_executor_class):
        """Test when gather result contains different materials."""
        # Mock inventory
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = []
        mock_get_character.return_value = mock_response
        
        # Mock action executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        
        # Return items but not the material we want
        mock_executor.execute_action.return_value = ActionResult(
            success=True,
            data={
                'items_obtained': [
                    {'code': 'stone', 'quantity': 3},
                    {'code': 'dirt', 'quantity': 2}
                ]
            }
        )
        
        context = MockActionContext(
            character_name=self.character_name,
            current_gathering_goal={'material': 'iron_ore', 'quantity': 5}
        )
        
        # Set max attempts low for test
        self.action.max_attempts = 2
        
        result = self.action.execute(self.mock_client, context)
        
        # Should handle not finding the material in results
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Partially gathered iron_ore")


if __name__ == '__main__':
    unittest.main()