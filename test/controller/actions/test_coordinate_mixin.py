"""Comprehensive unit tests for CoordinateStandardizationMixin"""

import unittest

from src.controller.actions.coordinate_mixin import (
    CoordinateStandardizationMixin,
    extract_target_coordinates,
    standardize_coordinates,
)


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
    
    def test_standardize_coordinate_input_kwargs_target(self):
        """Test target coordinates from kwargs."""
        result = self.mixin.standardize_coordinate_input(target_x=7, target_y=8, other_param='test')
        self.assertEqual(result, (7, 8))
    
    def test_standardize_coordinate_input_kwargs_x_y(self):
        """Test x, y coordinates from kwargs."""
        kwargs = {'x': 50, 'y': 75, 'some_other_key': 'value'}
        result = self.mixin.standardize_coordinate_input(**kwargs)
        self.assertEqual(result, (50, 75))
    
    def test_standardize_coordinate_input_kwargs_location(self):
        """Test location from kwargs."""
        kwargs = {'location': (88, 99), 'data': 'test'}
        result = self.mixin.standardize_coordinate_input(**kwargs)
        self.assertEqual(result, (88, 99))
    
    def test_standardize_coordinate_input_no_coordinates(self):
        """Test when no coordinates are provided."""
        result = self.mixin.standardize_coordinate_input()
        self.assertEqual(result, (None, None))
        
        result = self.mixin.standardize_coordinate_input(other_data='test')
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
    
    def test_validate_coordinates_valid(self):
        """Test coordinate validation with valid coordinates."""
        self.assertTrue(self.mixin.validate_coordinates(10, 20))
        self.assertTrue(self.mixin.validate_coordinates(0, 0))
        self.assertTrue(self.mixin.validate_coordinates(-5, -10))
    
    def test_validate_coordinates_invalid(self):
        """Test coordinate validation with invalid coordinates."""
        self.assertFalse(self.mixin.validate_coordinates(None, 20))
        self.assertFalse(self.mixin.validate_coordinates(10, None))
        self.assertFalse(self.mixin.validate_coordinates(None, None))
        self.assertFalse(self.mixin.validate_coordinates('10', 20))
        self.assertFalse(self.mixin.validate_coordinates(10, '20'))
        self.assertFalse(self.mixin.validate_coordinates(10.5, 20))
    
    def test_get_standardized_coordinates(self):
        """Test instance method for getting standardized coordinates."""
        result = self.mixin.get_standardized_coordinates(target_x=30, target_y=40)
        self.assertEqual(result, (30, 40))
        
        result = self.mixin.get_standardized_coordinates(location=(50, 60))
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


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions."""
    
    def test_standardize_coordinates_with_target_coordinates(self):
        """Test standardizing data with target coordinates."""
        input_data = {
            'target_x': 10,
            'target_y': 20,
            'resource_code': 'iron_ore',
            'distance': 5
        }
        
        result = standardize_coordinates(input_data)
        
        expected = {
            'target_x': 10,
            'target_y': 20,
            'resource_code': 'iron_ore',
            'distance': 5
        }
        self.assertEqual(result, expected)
    
    def test_standardize_coordinates_with_legacy_format(self):
        """Test standardizing data with legacy x, y format."""
        input_data = {
            'x': 30,
            'y': 40,
            'resource_code': 'copper_ore',
            'distance': 3
        }
        
        result = standardize_coordinates(input_data)
        
        expected = {
            'target_x': 30,
            'target_y': 40,
            'resource_code': 'copper_ore',
            'distance': 3
        }
        self.assertEqual(result, expected)
    
    def test_standardize_coordinates_with_location_format(self):
        """Test standardizing data with location tuple format."""
        input_data = {
            'location': (50, 60),
            'workshop_type': 'weaponcrafting',
            'x': 100,  # Should be removed
            'y': 200   # Should be removed
        }
        
        result = standardize_coordinates(input_data)
        
        expected = {
            'target_x': 50,
            'target_y': 60,
            'workshop_type': 'weaponcrafting'
        }
        self.assertEqual(result, expected)
    
    def test_standardize_coordinates_no_coordinates(self):
        """Test standardizing data with no coordinates."""
        input_data = {
            'resource_code': 'gold_ore',
            'distance': 10
        }
        
        result = standardize_coordinates(input_data)
        
        # Should return original data unchanged
        self.assertEqual(result, input_data)
    
    def test_standardize_coordinates_removes_legacy_formats(self):
        """Test that legacy coordinate formats are removed."""
        input_data = {
            'target_x': 5,
            'target_y': 10,
            'x': 15,        # Should be removed
            'y': 20,        # Should be removed
            'location': (25, 30),  # Should be removed
            'other_data': 'preserved'
        }
        
        result = standardize_coordinates(input_data)
        
        expected = {
            'target_x': 5,
            'target_y': 10,
            'other_data': 'preserved'
        }
        self.assertEqual(result, expected)
    
    def test_extract_target_coordinates_various_formats(self):
        """Test extracting coordinates from various data formats."""
        # Test with target coordinates
        data = {'target_x': 10, 'target_y': 20}
        result = extract_target_coordinates(data)
        self.assertEqual(result, (10, 20))
        
        # Test with legacy format
        data = {'x': 30, 'y': 40}
        result = extract_target_coordinates(data)
        self.assertEqual(result, (30, 40))
        
        # Test with location
        data = {'location': (50, 60)}
        result = extract_target_coordinates(data)
        self.assertEqual(result, (50, 60))
        
        # Test with no coordinates
        data = {'resource_code': 'iron_ore'}
        result = extract_target_coordinates(data)
        self.assertEqual(result, (None, None))
    
    def test_extract_target_coordinates_priority(self):
        """Test extraction follows correct priority order."""
        data = {
            'target_x': 1,
            'target_y': 2,
            'x': 3,
            'y': 4,
            'location': (5, 6)
        }
        
        result = extract_target_coordinates(data)
        self.assertEqual(result, (1, 2))  # target_x/target_y have highest priority
    
    def test_extract_target_coordinates_empty_data(self):
        """Test extraction from empty data."""
        result = extract_target_coordinates({})
        self.assertEqual(result, (None, None))


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
    
    def test_kwargs_location_invalid(self):
        """Test invalid location in kwargs."""
        kwargs = {'location': 'invalid'}
        result = self.mixin.standardize_coordinate_input(**kwargs)
        self.assertEqual(result, (None, None))


if __name__ == '__main__':
    unittest.main()