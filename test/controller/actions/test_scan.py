"""Test ScanAction"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.scan import ScanAction
from src.lib.action_context import ActionContext


class TestScanAction(unittest.TestCase):
    """Test cases for ScanAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = ScanAction()
        self.mock_client = Mock()
        
    @patch('src.controller.actions.scan.get_character_api')
    @patch('src.controller.actions.scan.get_map_api')
    def test_execute_successful_scan(self, mock_get_map, mock_get_char):
        """Test successful scan execution."""
        # Mock character API response
        mock_char_response = Mock()
        mock_char_data = Mock()
        mock_char_data.x = 0
        mock_char_data.y = 0
        mock_char_response.data = mock_char_data
        mock_get_char.return_value = mock_char_response
        
        # Mock map API responses for different locations
        # Location with monster
        mock_map_response1 = Mock()
        mock_map_data1 = Mock()
        type(mock_map_data1).content = {'code': 'chicken', 'type': 'monster', 'name': 'Chicken', 'level': 1}
        mock_map_response1.data = mock_map_data1
        
        # Location with resource
        mock_map_response2 = Mock()
        mock_map_data2 = Mock()
        type(mock_map_data2).content = {'code': 'ash_tree', 'type': 'resource', 'name': 'Ash Tree', 'level': 1}
        mock_map_response2.data = mock_map_data2
        
        # Empty location
        mock_map_response3 = Mock()
        mock_map_data3 = Mock()
        type(mock_map_data3).content = None
        mock_map_response3.data = mock_map_data3
        
        # Set up map API to return different responses based on location
        mock_get_map.side_effect = [mock_map_response1, mock_map_response2, mock_map_response3] * 10
        
        # Create context
        context = ActionContext(character_name="test_char")
        context['search_radius'] = 1
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertIn('discoveries', result.data)
        self.assertIn('scan_center', result.data)
        self.assertEqual(result.data['scan_center'], (0, 0))
    
    @patch('src.controller.actions.scan.get_character_api')
    def test_execute_no_character_data(self, mock_get_char):
        """Test execution when character data is not available."""
        # Mock character API to return None
        mock_get_char.return_value = None
        
        # Create context
        context = ActionContext(character_name="test_char")
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify error result
        self.assertFalse(result.success)
        self.assertIn("Could not get character data", result.error)
    
    @patch('src.controller.actions.scan.get_character_api')
    @patch('src.controller.actions.scan.get_map_api')
    def test_execute_api_exception(self, mock_get_map, mock_get_char):
        """Test execution with API exception."""
        # Mock character API response
        mock_char_response = Mock()
        mock_char_data = Mock()
        mock_char_data.x = 0
        mock_char_data.y = 0
        mock_char_response.data = mock_char_data
        mock_get_char.return_value = mock_char_response
        
        # Mock map API to raise exception
        mock_get_map.side_effect = Exception("API error")
        
        # Create context
        context = ActionContext(character_name="test_char")
        context['search_radius'] = 1
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Should still succeed but with empty discoveries
        self.assertTrue(result.success)
        self.assertEqual(len(result.data['discoveries']), 0)
    
    def test_categorize_content_workshop(self):
        """Test categorizing workshop content."""
        content_info = {
            'content_type': 'workshop',
            'content_code': 'weaponcrafting'
        }
        category = self.action._categorize_content(content_info)
        self.assertEqual(category, 'workshop')
    
    def test_categorize_content_resource(self):
        """Test categorizing resource content."""
        content_info = {
            'content_type': 'resource',
            'content_code': 'ash_tree'
        }
        category = self.action._categorize_content(content_info)
        self.assertEqual(category, 'resource')
        
        # Test with rocks
        content_info = {
            'content_type': 'resource',
            'content_code': 'copper_rocks'
        }
        category = self.action._categorize_content(content_info)
        self.assertEqual(category, 'resource')
    
    def test_categorize_content_monster(self):
        """Test categorizing monster content."""
        content_info = {
            'content_type': 'monster',
            'content_code': 'chicken'
        }
        category = self.action._categorize_content(content_info)
        self.assertEqual(category, 'monster')
    
    def test_categorize_content_unknown(self):
        """Test categorizing unknown content."""
        content_info = {
            'content_type': 'something_else',
            'content_code': 'unknown_thing'
        }
        category = self.action._categorize_content(content_info)
        self.assertEqual(category, 'unknown')
    
    def test_repr(self):
        """Test string representation."""
        expected = "ScanAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()