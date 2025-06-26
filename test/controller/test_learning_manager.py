"""
Test LearningManager integration and functionality.

This module tests the LearningManager class that provides YAML-configurable
learning and optimization services extracted from the AI controller.
"""

import unittest
from unittest.mock import Mock, patch
import tempfile
import os

from src.controller.learning_manager import LearningManager


class TestLearningManager(unittest.TestCase):
    """Test LearningManager functionality."""
    
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
        self.mock_knowledge_base.find_suitable_monsters.return_value = [
            {
                'monster_code': 'goblin',
                'location': (10, 10),
                'success_rate': 0.8
            },
            {
                'monster_code': 'orc',
                'location': (12, 12),
                'success_rate': 0.2
            }
        ]
        
        # Create mock map state
        self.mock_map_state = Mock()
        self.mock_map_state.data = {'location1': {}, 'location2': {}}  # 2 locations
        
        # Patch data directory to use temp directory
        with patch('src.controller.learning_manager.DATA_PREFIX', self.temp_dir):
            # Create required configuration file
            self._create_test_config_file()
            
            # Initialize learning manager
            self.learning_manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state
            )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config_file(self):
        """Create minimal test configuration file."""
        config_content = """
thresholds:
  min_monsters_for_recommendations: 3
  min_locations_for_exploration: 20
  good_success_rate_threshold: 0.7
  dangerous_success_rate_threshold: 0.3
  optimization_distance_radius: 20
"""
        
        with open(os.path.join(self.temp_dir, 'goal_templates.yaml'), 'w') as f:
            f.write(config_content)
    
    def test_learning_manager_initialization(self):
        """Test that LearningManager initializes correctly."""
        self.assertIsNotNone(self.learning_manager.knowledge_base)
        self.assertIsNotNone(self.learning_manager.map_state)
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 3)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 20)
        self.assertEqual(self.learning_manager.good_success_rate_threshold, 0.7)
        self.assertEqual(self.learning_manager.dangerous_success_rate_threshold, 0.3)
        self.assertEqual(self.learning_manager.optimization_distance_radius, 20)
    
    def test_get_learning_insights(self):
        """Test learning insights generation."""
        insights = self.learning_manager.get_learning_insights()
        
        # Verify insights structure
        self.assertIn('knowledge_summary', insights)
        self.assertIn('learning_stats', insights)
        self.assertIn('recommendations', insights)
        
        # Verify recommendations based on mock data
        recommendations = insights['recommendations']
        # Should recommend more exploration (2 < 3 monsters, 15 < 20 locations)
        self.assertTrue(any('more monster varieties' in rec for rec in recommendations))
        self.assertTrue(any('more locations' in rec for rec in recommendations))
    
    def test_optimize_with_knowledge_combat(self):
        """Test combat optimization suggestions."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {
            'level': 5,
            'x': 10,
            'y': 10
        }
        
        optimizations = self.learning_manager.optimize_with_knowledge(
            mock_character_state, goal_type='combat'
        )
        
        # Verify optimization structure
        self.assertEqual(optimizations['goal_type'], 'combat')
        self.assertEqual(optimizations['character_level'], 5)
        self.assertEqual(optimizations['current_position'], (10, 10))
        
        # Verify suggestions
        suggestions = optimizations['suggestions']
        self.assertTrue(len(suggestions) > 0)
        
        # Should have high success rate target (goblin with 0.8 > 0.7)
        combat_targets = [s for s in suggestions if s['type'] == 'combat_target']
        self.assertEqual(len(combat_targets), 1)
        self.assertIn('goblin', combat_targets[0]['description'])
        
        # Should have warning about dangerous monster (orc with 0.2 < 0.3)
        combat_warnings = [s for s in suggestions if s['type'] == 'combat_warning']
        self.assertEqual(len(combat_warnings), 1)
        self.assertIn('orc', str(combat_warnings[0]['dangerous_monsters']))
    
    def test_optimize_with_knowledge_exploration(self):
        """Test exploration optimization suggestions."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {
            'level': 5,
            'x': 10,
            'y': 10
        }
        
        optimizations = self.learning_manager.optimize_with_knowledge(
            mock_character_state, goal_type='exploration'
        )
        
        # Verify suggestions for exploration
        suggestions = optimizations['suggestions']
        exploration_suggestions = [s for s in suggestions if s['type'] == 'exploration']
        
        # Should suggest more exploration (2 locations < 20 threshold)
        self.assertEqual(len(exploration_suggestions), 1)
        self.assertIn('visited 2 locations', exploration_suggestions[0]['description'])
    
    def test_find_known_monsters_nearby(self):
        """Test finding known monsters nearby."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {
            'x': 10,
            'y': 10,
            'level': 5
        }
        
        monsters = self.learning_manager.find_known_monsters_nearby(
            mock_character_state,
            max_distance=15,
            character_level=5,
            level_range=2
        )
        
        # Verify delegation to knowledge base
        self.mock_knowledge_base.find_suitable_monsters.assert_called_once_with(
            map_state=self.mock_map_state,
            character_level=5,
            level_range=2,
            max_distance=15,
            current_x=10,
            current_y=10
        )
        
        # Verify return value
        self.assertEqual(len(monsters), 2)
        self.assertEqual(monsters[0]['monster_code'], 'goblin')
        self.assertEqual(monsters[1]['monster_code'], 'orc')
    
    def test_find_known_monsters_nearby_no_character_state(self):
        """Test finding monsters with no character state."""
        result = self.learning_manager.find_known_monsters_nearby(None)
        self.assertIsNone(result)
    
    def test_optimize_with_knowledge_no_character_state(self):
        """Test optimization with no character state."""
        result = self.learning_manager.optimize_with_knowledge(None)
        self.assertEqual(result['error'], 'No character state available')
    
    def test_configuration_reload(self):
        """Test configuration reloading."""
        # Verify initial values
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 3)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 20)
        
        # Modify config file
        config_content = """
thresholds:
  min_monsters_for_recommendations: 5
  min_locations_for_exploration: 30
  good_success_rate_threshold: 0.7
  dangerous_success_rate_threshold: 0.3
  optimization_distance_radius: 20
"""
        
        with open(os.path.join(self.temp_dir, 'goal_templates.yaml'), 'w') as f:
            f.write(config_content)
        
        # Reload configuration
        self.learning_manager.reload_configuration()
        
        # Verify new values
        self.assertEqual(self.learning_manager.min_monsters_for_recommendations, 5)
        self.assertEqual(self.learning_manager.min_locations_for_exploration, 30)
    
    def test_learning_insights_error_handling(self):
        """Test error handling in learning insights."""
        # Mock knowledge base to raise exception
        self.mock_knowledge_base.get_knowledge_summary.side_effect = Exception("Test error")
        
        insights = self.learning_manager.get_learning_insights()
        
        # Should return error information
        self.assertIn('error', insights)
        self.assertEqual(insights['error'], 'Test error')
    
    def test_optimize_with_knowledge_error_handling(self):
        """Test error handling in optimization."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {'level': 5, 'x': 10, 'y': 10}
        
        # Mock knowledge base to raise exception
        self.mock_knowledge_base.find_suitable_monsters.side_effect = Exception("Test error")
        
        result = self.learning_manager.optimize_with_knowledge(mock_character_state, 'combat')
        
        # Should still return structure with empty suggestions
        self.assertEqual(result['goal_type'], 'combat')
        self.assertIsInstance(result['suggestions'], list)


if __name__ == '__main__':
    unittest.main()