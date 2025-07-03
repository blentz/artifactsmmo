"""Comprehensive unit tests for CoordinateStandardizationMixin"""

import unittest

from src.controller.actions.coordinate_mixin import CoordinateStandardizationMixin


class TestCoordinateStandardizationMixin(unittest.TestCase):
    """Test cases for CoordinateStandardizationMixin class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mixin = CoordinateStandardizationMixin()
    
    def test_standardize_coordinate_input_target_x_y_priority(self):
        """Test that target_x, target_y have highest priority."""
        result = self.mixin.standardize_coordinate_input(
            target_x=10, target_y=20,
            x=30, y=40,  # Should be ignored
            location=(50, 60)  # Should be ignored
        )
        self.assertEqual(result, (10, 20))
    
    def test_standardize_coordinate_input_location_tuple(self):
        """Test location tuple format."""
        result = self.mixin.standardize_coordinate_input(location=(15, 25))
        self.assertEqual(result, (15, 25))
        
        # Test with list
        result = self.mixin.standardize_coordinate_input(location=[33, 44])
        self.assertEqual(result, (33, 44))
    
    def test_standardize_coordinate_input_legacy_x_y(self):
        """Test legacy x, y parameters."""
        result = self.mixin.standardize_coordinate_input(x=100, y=200)
        self.assertEqual(result, (100, 200))
    
    def test_standardize_coordinate_input_with_extra_params(self):
        """Test that extra parameters are ignored."""
        result = self.mixin.standardize_coordinate_input(target_x=7, target_y=8)
        self.assertEqual(result, (7, 8))
    
    
    def test_standardize_coordinate_input_no_coordinates(self):
        """Test when no coordinates are provided."""
        result = self.mixin.standardize_coordinate_input()
        self.assertEqual(result, (None, None))
    
    def test_standardize_coordinate_input_partial_coordinates(self):
        """Test with partial coordinate data."""
        # Only target_x provided
        result = self.mixin.standardize_coordinate_input(target_x=10)
        self.assertEqual(result, (None, None))
        
        # Only x provided
        result = self.mixin.standardize_coordinate_input(x=20)
        self.assertEqual(result, (None, None))
        
        # Invalid location tuple (too short)
        result = self.mixin.standardize_coordinate_input(location=(5,))
        self.assertEqual(result, (None, None))
    
    def test_standardize_coordinate_input_type_conversion(self):
        """Test that coordinates are converted to integers."""
        result = self.mixin.standardize_coordinate_input(target_x='10', target_y='20')
        self.assertEqual(result, (10, 20))
        
        result = self.mixin.standardize_coordinate_input(target_x=10.5, target_y=20.8)
        self.assertEqual(result, (10, 20))
    
    def test_standardize_coordinate_input_priority_order(self):
        """Test that coordinate input follows correct priority order."""
        # target_x/target_y should override everything else
        result = self.mixin.standardize_coordinate_input(
            target_x=1, target_y=2,
            location=(3, 4),
            x=5, y=6
        )
        self.assertEqual(result, (1, 2))
        
        # location should override x/y
        result = self.mixin.standardize_coordinate_input(
            location=(7, 8),
            x=9, y=10
        )
        self.assertEqual(result, (7, 8))
    
    def test_standardize_coordinate_output(self):
        """Test standardized coordinate output."""
        result = self.mixin.standardize_coordinate_output(15, 25)
        expected = {'target_x': 15, 'target_y': 25}
        self.assertEqual(result, expected)
    
    
    def test_get_standardized_coordinates(self):
        """Test instance method for getting standardized coordinates."""
        context = {'target_x': 30, 'target_y': 40}
        result = self.mixin.get_standardized_coordinates(context)
        self.assertEqual(result, (30, 40))
        
        context = {'location': (50, 60)}
        result = self.mixin.get_standardized_coordinates(context)
        self.assertEqual(result, (50, 60))
    
    def test_create_coordinate_response(self):
        """Test creating coordinate response with additional data."""
        result = self.mixin.create_coordinate_response(
            10, 20,
            distance=5,
            resource_code='iron_ore',
            success=True
        )
        
        expected = {
            'target_x': 10,
            'target_y': 20,
            'distance': 5,
            'resource_code': 'iron_ore',
            'success': True
        }
        self.assertEqual(result, expected)
    
    def test_create_coordinate_response_no_additional_data(self):
        """Test creating coordinate response without additional data."""
        result = self.mixin.create_coordinate_response(5, 15)
        expected = {'target_x': 5, 'target_y': 15}
        self.assertEqual(result, expected)




class TestInvalidLocationFormats(unittest.TestCase):
    """Test cases for invalid location formats."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mixin = CoordinateStandardizationMixin()
    
    def test_invalid_location_none(self):
        """Test with None location."""
        result = self.mixin.standardize_coordinate_input(location=None)
        self.assertEqual(result, (None, None))
    
    def test_invalid_location_string(self):
        """Test with string location."""
        result = self.mixin.standardize_coordinate_input(location="10,20")
        self.assertEqual(result, (None, None))
    
    def test_invalid_location_empty_tuple(self):
        """Test with empty tuple location."""
        result = self.mixin.standardize_coordinate_input(location=())
        self.assertEqual(result, (None, None))
    
    def test_invalid_location_single_element(self):
        """Test with single element location."""
        result = self.mixin.standardize_coordinate_input(location=(10,))
        self.assertEqual(result, (None, None))
    


if __name__ == '__main__':
    unittest.main()