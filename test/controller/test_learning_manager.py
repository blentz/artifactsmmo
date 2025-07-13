"""
Test LearningManager - Architecture Compliant Version

This module tests the LearningManager class that provides simple learning
orchestration for API interactions, following architectural principles.

Architectural Principle: "Business logic goes in actions, NOT in managers"
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.learning_manager import LearningManager


class TestLearningManagerArchitectureCompliant(unittest.TestCase):
    """Test LearningManager functionality - architecture compliant methods only."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock knowledge base
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.get_knowledge_summary.return_value = {
            'monsters_discovered': 2,
            'total_locations_discovered': 15
        }
        self.mock_knowledge_base.get_learning_stats.return_value = {
            'total_combats': 10,
            'exploration_time': 300
        }
        
        # Create mock map state
        self.mock_map_state = Mock()
        self.mock_map_state.data = {'location1': {}, 'location2': {}}  # 2 locations
        
        # Create mock client
        self.mock_client = Mock()
        
        # Create test config file in temp directory
        self.config_file = os.path.join(self.temp_dir, 'goal_templates.yaml')
        with open(self.config_file, 'w') as f:
            f.write("""
thresholds:
  min_monsters_for_recommendations: 5
  min_locations_for_exploration: 25
  good_success_rate_threshold: 0.8
  dangerous_success_rate_threshold: 0.4
  optimization_distance_radius: 30
""")
        
        # Create learning manager with explicit config file path
        self.learning_manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            self.mock_client,
            config_file=self.config_file
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_learning_manager_initialization(self):
        """Test learning manager initializes correctly."""
        self.assertIsNotNone(self.learning_manager)
        self.assertEqual(self.learning_manager.knowledge_base, self.mock_knowledge_base)
        self.assertEqual(self.learning_manager.map_state, self.mock_map_state)
        
        # Check configuration was loaded from test config (min_monsters=5 is in test config)
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 5)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 25)
        self.assertEqual(self.learning_manager.good_success_rate_threshold, 0.8)
        self.assertEqual(self.learning_manager.dangerous_success_rate_threshold, 0.4)
        self.assertEqual(self.learning_manager.optimization_distance_radius, 30)
    
    def test_get_learning_insights(self):
        """Test getting learning insights - architecturally compliant data summarization."""
        insights = self.learning_manager.get_learning_insights()
        
        # Verify structure
        self.assertIn('knowledge_summary', insights)
        self.assertIn('learning_stats', insights)
        self.assertIn('recommendations', insights)
        
        # Verify data is passed through from knowledge base
        self.assertEqual(insights['knowledge_summary']['monsters_discovered'], 2)
        self.assertEqual(insights['learning_stats']['total_combats'], 10)
        
        # Verify simple recommendations based on thresholds
        self.assertTrue(len(insights['recommendations']) > 0)
        
        # Should have monster exploration recommendation (2 < 5)
        monster_recs = [r for r in insights['recommendations'] if 'monster' in r.lower()]
        self.assertTrue(len(monster_recs) > 0)
        
        # Should have location exploration recommendation (15 < 25)
        location_recs = [r for r in insights['recommendations'] if 'location' in r.lower()]
        self.assertTrue(len(location_recs) > 0)
    
    def test_learning_insights_error_handling(self):
        """Test error handling in learning insights."""
        # Mock knowledge base to raise exception
        self.mock_knowledge_base.get_knowledge_summary.side_effect = Exception("Test error")
        
        insights = self.learning_manager.get_learning_insights()
        
        # Should handle error gracefully
        self.assertIn('error', insights)
        self.assertIn('Test error', insights['error'])
    
    def test_configuration_reload(self):
        """Test configuration reload functionality."""
        # Verify initial values first
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 5)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 25)
        
        # Modify config file
        with open(self.config_file, 'w') as f:
            f.write("""
thresholds:
  min_monsters_for_recommendations: 10
  min_locations_for_exploration: 50
""")
        
        # Reload configuration
        self.learning_manager.reload_configuration()
        
        # Verify new values
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 10)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 50)
    
    def test_learn_from_capability_analysis_no_analyzer(self):
        """Test capability analysis learning with no analyzer."""
        # Create manager without client (no analyzer)
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=self.config_file
        )
        
        result = manager.learn_from_capability_analysis(resource_code="ash_tree")
        
        # Should handle gracefully
        self.assertIn('error', result)
        self.assertIn('analyzer not initialized', result['error'])
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_learn_from_capability_analysis_resource(self, mock_analyzer_class):
        """Test learning from capability analysis for resources."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            self.mock_client,
            config_file=self.config_file
        )
        
        # Mock analyzer response
        mock_drops = {'ash_wood': 1}
        mock_analyzer.analyze_resource_drops.return_value = mock_drops
        
        result = manager.learn_from_capability_analysis(resource_code="ash_tree")
        
        # Verify analyzer was called
        mock_analyzer.analyze_resource_drops.assert_called_once_with("ash_tree")
        
        # Verify knowledge base learning was called
        self.mock_knowledge_base.learn_resource_capabilities.assert_called_once_with("ash_tree", mock_drops)
        
        # Verify result structure
        self.assertIn('resource_analysis', result)
        self.assertEqual(result['resource_analysis']['resource_code'], "ash_tree")
        self.assertEqual(result['resource_analysis']['drops'], mock_drops)
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_learn_from_capability_analysis_item(self, mock_analyzer_class):
        """Test learning from capability analysis for items."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            self.mock_client,
            config_file=self.config_file
        )
        
        # Mock analyzer response
        mock_capabilities = {'attack': 10, 'defense': 5}
        mock_analyzer.analyze_item_capabilities.return_value = mock_capabilities
        
        result = manager.learn_from_capability_analysis(item_code="wooden_staff")
        
        # Verify analyzer was called
        mock_analyzer.analyze_item_capabilities.assert_called_once_with("wooden_staff")
        
        # Verify knowledge base learning was called
        self.mock_knowledge_base.learn_item_capabilities.assert_called_once_with("wooden_staff", mock_capabilities)
        
        # Verify result structure
        self.assertIn('item_analysis', result)
        self.assertEqual(result['item_analysis'], mock_capabilities)
    
    def test_learn_from_capability_analysis_exception(self):
        """Test exception handling in capability analysis."""
        # Mock analyzer to raise exception
        with patch('src.controller.learning_manager.CapabilityAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.analyze_resource_drops.side_effect = Exception("Analysis failed")
            
            with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
                manager = LearningManager(
                    self.mock_knowledge_base,
                    self.mock_map_state,
                    self.mock_client
                )
            
            result = manager.learn_from_capability_analysis(resource_code="ash_tree")
            
            # Should handle error gracefully
            self.assertIn('error', result)
            self.assertIn('Analysis failed', result['error'])


class TestLearningManagerBulkLearning(unittest.TestCase):
    """Test bulk learning functionality - architecturally compliant data collection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_knowledge_base = Mock()
        self.mock_map_state = Mock()
        self.mock_client = Mock()
        
        # Create test config
        self.config_file = os.path.join(self.temp_dir, 'goal_templates.yaml')
        with open(self.config_file, 'w') as f:
            f.write("thresholds: {}")
        
        self.learning_manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            self.mock_client,
            config_file=self.config_file
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk(self, mock_api):
        """Test bulk resource learning."""
        # Mock API response
        mock_resource1 = Mock()
        mock_resource1.to_dict.return_value = {'code': 'ash_tree', 'name': 'Ash Tree'}
        mock_resource2 = Mock()
        mock_resource2.to_dict.return_value = {'code': 'iron_rocks', 'name': 'Iron Rocks'}
        
        mock_response = Mock()
        mock_response.data = [mock_resource1, mock_resource2]
        mock_api.return_value = mock_response
        
        result = self.learning_manager.learn_all_resources_bulk(self.mock_client)
        
        # Verify API was called
        mock_api.assert_called_once()
        
        # Verify knowledge base learning
        self.assertEqual(self.mock_knowledge_base.learn_resource.call_count, 2)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 2)
        self.assertIn('ash_tree', result['resources_learned'])
        self.assertIn('iron_rocks', result['resources_learned'])
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_exception(self, mock_api):
        """Test bulk resource learning with exception."""
        mock_api.side_effect = Exception("API error")
        
        result = self.learning_manager.learn_all_resources_bulk(self.mock_client)
        
        # Should handle error gracefully
        self.assertFalse(result['success'])
        self.assertIn('API error', result['error'])
        self.assertEqual(result['total_resources_learned'], 0)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_no_response(self, mock_api):
        """Test bulk resource learning with no response."""
        mock_api.return_value = None
        
        result = self.learning_manager.learn_all_resources_bulk(self.mock_client)
        
        # Should handle gracefully
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 0)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_pagination(self, mock_api):
        """Test bulk resource learning with pagination."""
        # Mock paginated responses
        def side_effect(client, page, size):
            if page == 1:
                mock_resource = Mock()
                mock_resource.to_dict.return_value = {'code': 'ash_tree'}
                mock_response = Mock()
                mock_response.data = [mock_resource] * 100  # Full page
                return mock_response
            elif page == 2:
                mock_resource = Mock()
                mock_resource.to_dict.return_value = {'code': 'iron_rocks'}
                mock_response = Mock()
                mock_response.data = [mock_resource] * 50  # Partial page
                return mock_response
            else:
                return None
        
        mock_api.side_effect = side_effect
        
        result = self.learning_manager.learn_all_resources_bulk(self.mock_client)
        
        # Should handle pagination correctly
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 150)


if __name__ == '__main__':
    unittest.main()