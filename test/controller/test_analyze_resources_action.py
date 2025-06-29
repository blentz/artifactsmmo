"""Test module for AnalyzeResourcesAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.analyze_resources import AnalyzeResourcesAction


class TestAnalyzeResourcesAction(unittest.TestCase):
    """Test cases for AnalyzeResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.action = AnalyzeResourcesAction(
            character_x=10,
            character_y=15,
            character_level=5,
            analysis_radius=8,
            equipment_types=['weapon', 'armor']
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_resources_action_initialization(self):
        """Test AnalyzeResourcesAction initialization."""
        self.assertEqual(self.action.character_x, 10)
        self.assertEqual(self.action.character_y, 15)
        self.assertEqual(self.action.character_level, 5)
        self.assertEqual(self.action.analysis_radius, 8)
        self.assertEqual(self.action.equipment_types, ['weapon', 'armor'])

    def test_analyze_resources_action_initialization_defaults(self):
        """Test AnalyzeResourcesAction initialization with defaults."""
        action = AnalyzeResourcesAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.character_level, 1)
        self.assertEqual(action.analysis_radius, 10)
        self.assertIsNone(action.equipment_types)

    def test_analyze_resources_action_repr(self):
        """Test AnalyzeResourcesAction string representation."""
        expected = "AnalyzeResourcesAction(10, 15, lvl=5, radius=8, types=['weapon', 'armor'])"
        self.assertEqual(repr(self.action), expected)

    def test_analyze_resources_action_repr_no_types(self):
        """Test AnalyzeResourcesAction string representation without equipment types."""
        action = AnalyzeResourcesAction(character_x=5, character_y=3)
        expected = "AnalyzeResourcesAction(5, 3, lvl=1, radius=10, types=None)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.analyze_resources.MapState')
    def test_execute_map_state_fails(self, mock_map_state_class):
        """Test execute when MapState creation fails."""
        mock_map_state_class.side_effect = Exception("Map state error")
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Map state error', result['error'])

    @patch('src.controller.actions.analyze_resources.get_all_resources_api')
    @patch('src.controller.actions.analyze_resources.MapState')
    def test_execute_resource_api_fails(self, mock_map_state_class, mock_get_all_resources_api):
        """Test execute when resource API fails."""
        # Mock map state
        mock_map_state = Mock()
        mock_map_state_class.return_value = mock_map_state
        
        # Mock resource API failure
        mock_get_all_resources_api.return_value = None
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve resource information', result['error'])

    @patch('src.controller.actions.analyze_resources.get_all_resources_api')
    @patch('src.controller.actions.analyze_resources.MapState')
    def test_execute_no_resources_data(self, mock_map_state_class, mock_get_all_resources_api):
        """Test execute when resource API returns no data."""
        # Mock map state
        mock_map_state = Mock()
        mock_map_state_class.return_value = mock_map_state
        
        # Mock resource API with no data
        mock_response = Mock()
        mock_response.data = None
        mock_get_all_resources_api.return_value = mock_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve resource information', result['error'])

    @patch('src.controller.actions.analyze_resources.get_all_resources_api')
    @patch('src.controller.actions.analyze_resources.MapState')
    def test_execute_successful_analysis(self, mock_map_state_class, mock_get_all_resources_api):
        """Test successful resource analysis."""
        # Mock map state with resource data
        mock_map_state = Mock()
        mock_map_state.data = {
            '10,15': {'x': 10, 'y': 15, 'content': {'code': 'iron_rocks', 'type_': 'resource'}},
            '11,15': {'x': 11, 'y': 15, 'content': {'code': 'copper_rocks', 'type_': 'resource'}},
            '12,15': {'x': 12, 'y': 15, 'content': None}
        }
        mock_map_state_class.return_value = mock_map_state
        
        # Mock resource API response
        mock_resource1 = Mock()
        mock_resource1.code = 'iron_rocks'
        mock_resource1.skill = 'mining'
        mock_resource1.level = 10
        mock_resource1.drop = [{'code': 'iron_ore', 'quantity': 1}]
        
        mock_resource2 = Mock()
        mock_resource2.code = 'copper_rocks'
        mock_resource2.skill = 'mining'
        mock_resource2.level = 5
        mock_resource2.drop = [{'code': 'copper_ore', 'quantity': 1}]
        
        mock_response = Mock()
        mock_response.data = [mock_resource1, mock_resource2]
        mock_get_all_resources_api.return_value = mock_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertIn('resources_analyzed', result)
        self.assertIn('accessible_resources', result)
        self.assertIn('resource_analysis', result)

    def test_calculate_resource_accessibility_high_level(self):
        """Test resource accessibility calculation for high-level character."""
        resource_data = {'level': 5}
        character_level = 10
        
        accessibility = self.action._calculate_resource_accessibility(resource_data, character_level)
        self.assertEqual(accessibility, 'high')

    def test_calculate_resource_accessibility_medium_level(self):
        """Test resource accessibility calculation for medium-level character."""
        resource_data = {'level': 8}
        character_level = 10
        
        accessibility = self.action._calculate_resource_accessibility(resource_data, character_level)
        self.assertEqual(accessibility, 'medium')

    def test_calculate_resource_accessibility_low_level(self):
        """Test resource accessibility calculation for low-level character."""
        resource_data = {'level': 15}
        character_level = 10
        
        accessibility = self.action._calculate_resource_accessibility(resource_data, character_level)
        self.assertEqual(accessibility, 'low')

    def test_calculate_resource_accessibility_no_level(self):
        """Test resource accessibility calculation when resource has no level."""
        resource_data = {}
        character_level = 10
        
        accessibility = self.action._calculate_resource_accessibility(resource_data, character_level)
        self.assertEqual(accessibility, 'unknown')

    def test_calculate_distance(self):
        """Test distance calculation between two points."""
        distance = self.action._calculate_distance(10, 15, 13, 19)
        expected_distance = ((13-10)**2 + (19-15)**2) ** 0.5
        self.assertAlmostEqual(distance, expected_distance, places=2)

    def test_analyze_resource_drops_with_drops(self):
        """Test resource drop analysis when resource has drops."""
        resource_data = {
            'drop': [
                {'code': 'iron_ore', 'quantity': 1, 'rate': 0.8},
                {'code': 'rare_gem', 'quantity': 1, 'rate': 0.1}
            ]
        }
        
        drops = self.action._analyze_resource_drops(resource_data)
        self.assertEqual(len(drops), 2)
        self.assertEqual(drops[0]['code'], 'iron_ore')
        self.assertEqual(drops[1]['code'], 'rare_gem')

    def test_analyze_resource_drops_no_drops(self):
        """Test resource drop analysis when resource has no drops."""
        resource_data = {}
        
        drops = self.action._analyze_resource_drops(resource_data)
        self.assertEqual(drops, [])

    def test_filter_by_equipment_types_match(self):
        """Test filtering resources by equipment types when types match."""
        action = AnalyzeResourcesAction(equipment_types=['weapon'])
        resource_data = {'drop': [{'code': 'iron_ore', 'used_for': ['weapon', 'armor']}]}
        
        result = action._filter_by_equipment_types(resource_data)
        self.assertTrue(result)

    def test_filter_by_equipment_types_no_match(self):
        """Test filtering resources by equipment types when types don't match."""
        action = AnalyzeResourcesAction(equipment_types=['jewelry'])
        resource_data = {'drop': [{'code': 'iron_ore', 'used_for': ['weapon', 'armor']}]}
        
        result = action._filter_by_equipment_types(resource_data)
        self.assertFalse(result)

    def test_filter_by_equipment_types_no_filter(self):
        """Test filtering when no equipment types filter is set."""
        action = AnalyzeResourcesAction(equipment_types=None)
        resource_data = {'drop': [{'code': 'iron_ore'}]}
        
        result = action._filter_by_equipment_types(resource_data)
        self.assertTrue(result)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.analyze_resources.MapState', side_effect=Exception("Unexpected Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Resource analysis failed: Unexpected Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that AnalyzeResourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weights'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertIsInstance(AnalyzeResourcesAction.conditions, dict)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertIsInstance(AnalyzeResourcesAction.reactions, dict)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weights'))
        self.assertIsInstance(AnalyzeResourcesAction.weights, dict)


if __name__ == '__main__':
    unittest.main()