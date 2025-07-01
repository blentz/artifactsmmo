"""
Tests for the CharacterState class with dynamic API data handling.
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.game.character.state import CharacterState


class TestCharacterState(unittest.TestCase):
    """Test cases for CharacterState class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.test_name = 'test_character'
        
        # Mock API response data
        self.mock_api_data = Mock()
        self.mock_api_data.level = 10
        self.mock_api_data.xp = 5000
        self.mock_api_data.hp = 80
        self.mock_api_data.max_hp = 100
        self.mock_api_data.x = 15
        self.mock_api_data.y = 25
        self.mock_api_data.gold = 1000
        self.mock_api_data.weapon = 'iron_sword'
        self.mock_api_data.shield = 'wooden_shield'
        self.mock_api_data.helmet = ''
        self.mock_api_data.custom_field = 'custom_value'
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_character_state_initialization(self):
        """Test CharacterState initialization."""
        initial_data = {
            'level': 1,
            'hp': 100,
            'weapon': 'wooden_sword'
        }
        
        with patch('src.game.character.state.YamlData.__init__') as mock_init:
            with patch.object(CharacterState, 'save') as mock_save:
                state = CharacterState(initial_data, self.test_name)
                
                self.assertEqual(state.name, self.test_name)
                self.assertEqual(state.data, initial_data)
                mock_save.assert_called_once()
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_character_state_initialization_empty(self):
        """Test CharacterState initialization with empty data."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState(None, self.test_name)
                self.assertEqual(state.data, {})
                
                state2 = CharacterState("not a dict", self.test_name)
                self.assertEqual(state2.data, {})
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_update_from_api_response(self):
        """Test updating character state from API response."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({}, self.test_name)
            
            # Update from API response
            state.update_from_api_response(self.mock_api_data)
            
            # All attributes should be copied dynamically
            self.assertEqual(state.data['level'], 10)
            self.assertEqual(state.data['xp'], 5000)
            self.assertEqual(state.data['hp'], 80)
            self.assertEqual(state.data['max_hp'], 100)
            self.assertEqual(state.data['x'], 15)
            self.assertEqual(state.data['y'], 25)
            self.assertEqual(state.data['gold'], 1000)
            self.assertEqual(state.data['weapon'], 'iron_sword')
            self.assertEqual(state.data['shield'], 'wooden_shield')
            self.assertEqual(state.data['helmet'], '')
            self.assertEqual(state.data['custom_field'], 'custom_value')
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_update_from_api_response_none(self):
        """Test updating character state with None response."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({'level': 5}, self.test_name)
            
            # Should not crash with None
            state.update_from_api_response(None)
            
            # Original data should remain
            self.assertEqual(state.data['level'], 5)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_update_from_api_response_preserves_none_values(self):
        """Test that None values from API are not included."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({}, self.test_name)
            
            # Add None attribute to mock
            self.mock_api_data.null_field = None
            # Also test to_ methods are skipped
            self.mock_api_data.to_dict = Mock()
            self.mock_api_data.to_json = Mock()
            
            state.update_from_api_response(self.mock_api_data)
            
            # None values should not be included
            self.assertNotIn('null_field', state.data)
            # to_ methods should not be included
            self.assertNotIn('to_dict', state.data)
            self.assertNotIn('to_json', state.data)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_update_from_api_response_skips_private_attributes(self):
        """Test that private attributes are not copied."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({}, self.test_name)
            
            # Add private attributes to mock
            self.mock_api_data._private = 'should_not_copy'
            self.mock_api_data.__dunder__ = 'should_not_copy'
            
            state.update_from_api_response(self.mock_api_data)
            
            # Private attributes should not be copied
            self.assertNotIn('_private', state.data)
            self.assertNotIn('__dunder__', state.data)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_dynamic_slot_discovery(self):
        """Test that equipment slots are discovered dynamically."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({}, self.test_name)
            
            # Create API response with non-standard slots
            api_data = Mock()
            api_data.level = 10
            api_data.custom_equipment_slot = 'custom_item'
            api_data.another_slot = 'another_item'
            api_data.future_slot = 'future_item'
            
            state.update_from_api_response(api_data)
            
            # All slots should be captured dynamically
            self.assertEqual(state.data['custom_equipment_slot'], 'custom_item')
            self.assertEqual(state.data['another_slot'], 'another_item')
            self.assertEqual(state.data['future_slot'], 'future_item')
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_repr(self):
        """Test string representation."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({'level': 5, 'hp': 100}, self.test_name)
            
            repr_str = repr(state)
            self.assertIn('CharacterState', repr_str)
            self.assertIn(self.test_name, repr_str)
            self.assertIn('level', repr_str)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_no_hardcoded_slots(self):
        """Test that there are no hardcoded equipment slot lists."""
        # This test verifies the implementation doesn't contain hardcoded slot lists
        import inspect

        import src.game.character.state
        
        source = inspect.getsource(src.game.character.state.CharacterState)
        
        # Should not contain hardcoded slot lists
        self.assertNotIn("['weapon', 'shield'", source)
        self.assertNotIn('["weapon", "shield"', source)
        self.assertNotIn("equipment_slots = [", source)
        self.assertNotIn("slot_mapping = {", source)
    
    @patch('src.game.character.state.DATA_PREFIX', '')
    def test_handles_complex_api_attributes(self):
        """Test handling of complex API attributes."""
        with patch('src.game.character.state.YamlData.__init__'):
            with patch.object(CharacterState, 'save'):
                state = CharacterState({}, self.test_name)
            
            # API response with complex attributes
            api_data = Mock()
            # Create proper inventory item mock without to_dict
            inventory_item = Mock(spec=['code', 'quantity'])
            inventory_item.code = 'item1'
            inventory_item.quantity = 5
            api_data.inventory = [inventory_item]
            api_data.skills = {'mining': 10, 'woodcutting': 5}
            api_data.simple_value = 'test'
            
            state.update_from_api_response(api_data)
            
            # All types of attributes should be stored
            self.assertEqual(state.data['inventory'], [{'code': 'item1', 'quantity': 5}])
            self.assertEqual(state.data['skills'], {'mining': 10, 'woodcutting': 5})
            self.assertEqual(state.data['simple_value'], 'test')


if __name__ == '__main__':
    unittest.main()