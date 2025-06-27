"""
Regression tests for knowledge base DropSchema serialization bug.

This module tests the fix for the YAML serialization issue where DropSchema objects
from the API client were causing 'cannot represent an object' errors during save.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock

from src.controller.knowledge.base import KnowledgeBase


class MockDropSchema:
    """Mock DropSchema object to simulate API client objects."""
    
    def __init__(self, code: str, quantity: int):
        self.code = code
        self.quantity = quantity
        self.additional_properties = {}
    
    def __repr__(self):
        return f"DropSchema(code='{self.code}', quantity={self.quantity}, additional_properties={{}})"


class TestKnowledgeBaseSerializationRegression(unittest.TestCase):
    """Test that DropSchema objects are properly serialized to YAML."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.knowledge_file = os.path.join(self.temp_dir, 'test_knowledge.yaml')
        self.knowledge_base = KnowledgeBase(filename=self.knowledge_file)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_combat_record_with_dropschema_drops(self):
        """Test that combat records with DropSchema drops can be saved without error."""
        # Create mock fight data with DropSchema objects (simulating API response)
        mock_drop1 = MockDropSchema('raw_chicken', 1)
        mock_drop2 = MockDropSchema('feather', 2)
        
        fight_data = {
            'xp': 12,
            'gold': 5,
            'turns': 3,
            'drops': [mock_drop1, mock_drop2]
        }
        
        character_data = {
            'level': 2,
            'hp': 69,
            'hp_before': 125
        }
        
        # This should not raise a YAML serialization error
        try:
            self.knowledge_base.record_combat_result(
                'chicken', 'win', character_data, fight_data
            )
            # Verify the save worked and data is correct
            self.assertIn('chicken', self.knowledge_base.data['monsters'])
            combat_results = self.knowledge_base.data['monsters']['chicken']['combat_results']
            self.assertEqual(len(combat_results), 1)
            
            # Verify drops were converted to dictionaries
            drops = combat_results[0]['drops']
            self.assertEqual(len(drops), 2)
            self.assertEqual(drops[0]['code'], 'raw_chicken')
            self.assertEqual(drops[0]['quantity'], 1)
            self.assertEqual(drops[1]['code'], 'feather')
            self.assertEqual(drops[1]['quantity'], 2)
            
        except Exception as e:
            self.fail(f"Combat record with DropSchema objects should not fail: {e}")
    
    def test_knowledge_base_save_with_dropschema_objects(self):
        """Test that knowledge base can save even with DropSchema objects in data."""
        # Manually inject DropSchema objects into the data structure
        mock_drop = MockDropSchema('raw_chicken', 1)
        
        # Add DropSchema object directly to monster data (simulating contaminated data)
        self.knowledge_base.data['monsters']['test_monster'] = {
            'code': 'test_monster',
            'combat_results': [{
                'result': 'win',
                'drops': [mock_drop],  # DropSchema object
                'xp_gained': 10
            }]
        }
        
        # This should not raise a YAML serialization error due to sanitization
        try:
            self.knowledge_base.save()
            
            # Reload and verify data was sanitized
            reloaded_kb = KnowledgeBase(filename=self.knowledge_file)
            monster_data = reloaded_kb.data['monsters']['test_monster']
            drops = monster_data['combat_results'][0]['drops']
            
            # Should be converted to dict
            self.assertIsInstance(drops[0], dict)
            self.assertEqual(drops[0]['code'], 'raw_chicken')
            self.assertEqual(drops[0]['quantity'], 1)
            
        except Exception as e:
            self.fail(f"Knowledge base save with DropSchema should not fail: {e}")
    
    def test_sanitize_nested_dropschema_objects(self):
        """Test that nested DropSchema objects are properly sanitized."""
        mock_drop = MockDropSchema('iron_ore', 3)
        
        # Create nested data structure with DropSchema
        nested_data = {
            'level1': {
                'level2': {
                    'drops': [mock_drop],
                    'other_data': 'normal'
                }
            },
            'list_with_drops': [
                {'drops': [mock_drop]},
                'normal_string'
            ]
        }
        
        # Test sanitization
        sanitized = self.knowledge_base._sanitize_object(nested_data)
        
        # Verify DropSchema was converted to dict at all levels
        drops1 = sanitized['level1']['level2']['drops'][0]
        self.assertIsInstance(drops1, dict)
        self.assertEqual(drops1['code'], 'iron_ore')
        self.assertEqual(drops1['quantity'], 3)
        
        drops2 = sanitized['list_with_drops'][0]['drops'][0]
        self.assertIsInstance(drops2, dict)
        self.assertEqual(drops2['code'], 'iron_ore')
        self.assertEqual(drops2['quantity'], 3)
        
        # Normal data should be unchanged
        self.assertEqual(sanitized['level1']['level2']['other_data'], 'normal')
        self.assertEqual(sanitized['list_with_drops'][1], 'normal_string')
    
    def test_empty_and_none_drops_handling(self):
        """Test handling of empty and None drops."""
        fight_data_cases = [
            {'drops': []},                # Empty list
            {'drops': None},              # None drops
            {'drops': [None]},            # List with None
            {},                           # No drops field
        ]
        
        character_data = {'level': 2, 'hp': 50}
        
        for i, fight_data in enumerate(fight_data_cases):
            monster_code = f'test_monster_{i}'
            
            # Should not raise errors
            try:
                self.knowledge_base.record_combat_result(
                    monster_code, 'win', character_data, fight_data
                )
            except Exception as e:
                self.fail(f"Case {i} should not fail: {e}")
    
    def test_mixed_drop_types(self):
        """Test handling of mixed drop types (DropSchema and dict)."""
        mock_drop = MockDropSchema('raw_chicken', 1)
        dict_drop = {'code': 'feather', 'quantity': 2}
        
        fight_data = {
            'drops': [mock_drop, dict_drop, None]  # Mixed types including None
        }
        
        character_data = {'level': 2, 'hp': 50}
        
        try:
            self.knowledge_base.record_combat_result(
                'mixed_monster', 'win', character_data, fight_data
            )
            
            # Verify both types were handled correctly
            combat_results = self.knowledge_base.data['monsters']['mixed_monster']['combat_results']
            drops = combat_results[0]['drops']
            
            # Should have 2 drops (None should be filtered out)
            self.assertEqual(len(drops), 2)
            
            # First drop (converted from DropSchema)
            self.assertEqual(drops[0]['code'], 'raw_chicken')
            self.assertEqual(drops[0]['quantity'], 1)
            
            # Second drop (already dict)
            self.assertEqual(drops[1]['code'], 'feather')
            self.assertEqual(drops[1]['quantity'], 2)
            
        except Exception as e:
            self.fail(f"Mixed drop types should not fail: {e}")


if __name__ == '__main__':
    unittest.main()