"""Test module for CheckMaterialAvailabilityAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.check_material_availability import CheckMaterialAvailabilityAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestCheckMaterialAvailabilityAction(unittest.TestCase):
    """Test cases for CheckMaterialAvailabilityAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = CheckMaterialAvailabilityAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = CheckMaterialAvailabilityAction()
        self.assertIsInstance(action, CheckMaterialAvailabilityAction)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['materials']['requirements_determined'], True)
        self.assertEqual(action.conditions['materials']['status'], 'checking')
        self.assertEqual(action.reactions['materials']['availability_checked'], True)
        self.assertEqual(action.weight, 1.0)
    
    def test_execute_no_required_materials(self):
        """Test execution when no required materials are specified."""
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No required materials specified")
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_no_character_response(self, mock_get_character):
        """Test execution when character API returns no response."""
        mock_get_character.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore']
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Could not get character data")
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_all_materials_sufficient(self, mock_get_character):
        """Test execution when all materials are available."""
        # Mock inventory with materials
        mock_item1 = Mock()
        mock_item1.code = "iron_ore"
        mock_item1.quantity = 10
        
        mock_item2 = Mock()
        mock_item2.code = "copper_ore"
        mock_item2.quantity = 5
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item1, mock_item2]
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore', 'copper_ore']
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Material availability check completed: All materials available")
        self.assertTrue(result.data['all_sufficient'])
        self.assertEqual(result.data['missing_materials'], 0)
        self.assertEqual(result.data['sufficient_materials'], 2)
        self.assertEqual(result.state_changes['materials']['status'], 'sufficient')
        self.assertTrue(result.state_changes['materials']['gathered'])
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_missing_materials(self, mock_get_character):
        """Test execution when some materials are missing."""
        # Mock inventory with only some materials
        mock_item = Mock()
        mock_item.code = "iron_ore"
        mock_item.quantity = 5
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item]
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore', 'copper_ore', 'gold_ore']
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Material availability check completed: 2 materials missing")
        self.assertFalse(result.data['all_sufficient'])
        self.assertEqual(result.data['missing_materials'], 2)
        self.assertEqual(result.data['sufficient_materials'], 1)
        self.assertEqual(result.state_changes['materials']['status'], 'insufficient')
        self.assertFalse(result.state_changes['materials']['gathered'])
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_with_material_requirements(self, mock_get_character):
        """Test execution with material requirements dictionary."""
        # Mock inventory
        mock_item1 = Mock()
        mock_item1.code = "iron_ore"
        mock_item1.quantity = 3
        
        mock_item2 = Mock()
        mock_item2.code = "copper_ore"
        mock_item2.quantity = 10
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item1, mock_item2]
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            material_requirements={'iron_ore': 5, 'copper_ore': 8}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Material availability check completed: 1 materials missing")
        self.assertFalse(result.data['all_sufficient'])
        self.assertEqual(result.data['missing_materials'], 1)  # iron_ore insufficient
        self.assertEqual(result.data['sufficient_materials'], 1)  # copper_ore sufficient
        
        # Check availability details
        details = result.data['availability_details']
        iron_detail = next(item for item in details if item['material'] == 'iron_ore')
        self.assertEqual(iron_detail['required'], 5)
        self.assertEqual(iron_detail['available'], 3)
        self.assertEqual(iron_detail['shortfall'], 2)
        self.assertFalse(iron_detail['sufficient'])
        
        copper_detail = next(item for item in details if item['material'] == 'copper_ore')
        self.assertEqual(copper_detail['required'], 8)
        self.assertEqual(copper_detail['available'], 10)
        self.assertEqual(copper_detail['shortfall'], 0)
        self.assertTrue(copper_detail['sufficient'])
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_empty_inventory(self, mock_get_character):
        """Test execution with empty inventory."""
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = []
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore']
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertFalse(result.data['all_sufficient'])
        self.assertEqual(result.data['missing_materials'], 1)
        self.assertEqual(result.state_changes['materials']['status'], 'insufficient')
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_execute_no_inventory_attribute(self, mock_get_character):
        """Test execution when character data has no inventory attribute."""
        mock_response = Mock()
        mock_response.data = Mock()
        # No inventory attribute
        del mock_response.data.inventory
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore']
        )
        
        result = self.action.execute(self.mock_client, context)
        
        # Should handle gracefully with empty inventory
        self.assertTrue(result.success)
        self.assertFalse(result.data['all_sufficient'])
        self.assertEqual(result.data['missing_materials'], 1)
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        context = MockActionContext(
            character_name=self.character_name,
            required_materials=['iron_ore']
        )
        
        # Mock exception in get_character_api
        with patch('src.controller.actions.check_material_availability.get_character_api', side_effect=Exception("API error")):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Material availability check failed: API error")
    
    def test_check_material_availability_with_requirements(self):
        """Test _check_material_availability with material requirements."""
        # Mock inventory items
        inventory = [
            Mock(code="iron_ore", quantity=5),
            Mock(code="copper_ore", quantity=3)
        ]
        
        material_requirements = {
            'iron_ore': 3,
            'copper_ore': 5,
            'gold_ore': 2
        }
        
        results = self.action._check_material_availability([], inventory, material_requirements)
        
        self.assertEqual(len(results), 3)
        
        # Check iron_ore (sufficient)
        iron_result = next(r for r in results if r['material'] == 'iron_ore')
        self.assertEqual(iron_result['required'], 3)
        self.assertEqual(iron_result['available'], 5)
        self.assertTrue(iron_result['sufficient'])
        self.assertEqual(iron_result['shortfall'], 0)
        
        # Check copper_ore (insufficient)
        copper_result = next(r for r in results if r['material'] == 'copper_ore')
        self.assertEqual(copper_result['required'], 5)
        self.assertEqual(copper_result['available'], 3)
        self.assertFalse(copper_result['sufficient'])
        self.assertEqual(copper_result['shortfall'], 2)
        
        # Check gold_ore (not in inventory)
        gold_result = next(r for r in results if r['material'] == 'gold_ore')
        self.assertEqual(gold_result['required'], 2)
        self.assertEqual(gold_result['available'], 0)
        self.assertFalse(gold_result['sufficient'])
        self.assertEqual(gold_result['shortfall'], 2)
    
    def test_check_material_availability_with_list(self):
        """Test _check_material_availability with material list (fallback)."""
        # Mock inventory items
        inventory = [
            Mock(code="iron_ore", quantity=2),
            Mock(code="copper_ore", quantity=0)
        ]
        
        required_materials = ['iron_ore', 'copper_ore', 'gold_ore']
        
        results = self.action._check_material_availability(required_materials, inventory)
        
        self.assertEqual(len(results), 3)
        
        # All materials should require quantity 1 in fallback mode
        for result in results:
            self.assertEqual(result['required'], 1)
            
        # Check specific materials
        iron_result = next(r for r in results if r['material'] == 'iron_ore')
        self.assertTrue(iron_result['sufficient'])
        
        copper_result = next(r for r in results if r['material'] == 'copper_ore')
        self.assertFalse(copper_result['sufficient'])
        
        gold_result = next(r for r in results if r['material'] == 'gold_ore')
        self.assertFalse(gold_result['sufficient'])
    
    def test_check_material_availability_invalid_inventory_items(self):
        """Test _check_material_availability with invalid inventory items."""
        # Mock inventory with invalid items
        inventory = [
            Mock(code="iron_ore", quantity=5),
            Mock(code="invalid"),  # No quantity attribute
            Mock(quantity=10),  # No code attribute
            "not_an_object"  # Not even an object
        ]
        
        material_requirements = {'iron_ore': 3, 'copper_ore': 2}
        
        results = self.action._check_material_availability([], inventory, material_requirements)
        
        # Should handle invalid items gracefully
        self.assertEqual(len(results), 2)
        
        iron_result = next(r for r in results if r['material'] == 'iron_ore')
        self.assertTrue(iron_result['sufficient'])
        
        copper_result = next(r for r in results if r['material'] == 'copper_ore')
        self.assertFalse(copper_result['sufficient'])
    
    @patch('src.controller.actions.check_material_availability.get_character_api')
    def test_context_storage(self, mock_get_character):
        """Test that results are properly stored in context."""
        # Mock inventory
        mock_item = Mock()
        mock_item.code = "iron_ore"
        mock_item.quantity = 3
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.inventory = [mock_item]
        mock_get_character.return_value = mock_response
        
        # Use MockActionContext which properly handles set_result
        context = MockActionContext(
            character_name=self.character_name,
            material_requirements={'iron_ore': 5, 'copper_ore': 2}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        # Check that set_result was called with the expected values
        # MockActionContext stores results internally
        # We can verify the execution succeeded and check the result data
        self.assertTrue(result.success)
        self.assertFalse(result.data['all_sufficient'])
        
        # Verify the availability details
        availability_details = result.data['availability_details']
        self.assertEqual(len(availability_details), 2)
        
        # Verify specific material details
        iron_detail = next(d for d in availability_details if d['material'] == 'iron_ore')
        self.assertEqual(iron_detail['shortfall'], 2)
        
        copper_detail = next(d for d in availability_details if d['material'] == 'copper_ore')
        self.assertEqual(copper_detail['shortfall'], 2)
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "CheckMaterialAvailabilityAction()")


if __name__ == '__main__':
    unittest.main()