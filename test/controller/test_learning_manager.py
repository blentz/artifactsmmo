"""
Test LearningManager integration and functionality.

This module tests the LearningManager class that provides YAML-configurable
learning and optimization services extracted from the AI controller.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

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
        
        # Patch config directory to use temp directory
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
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
        initial_monsters = self.learning_manager.min_monsters_for_recommendations
        initial_locations = self.learning_manager.min_locations_for_exploration
        self.assertIsNotNone(initial_monsters)
        self.assertIsNotNone(initial_locations)
        
        # Test that reload_configuration method exists and can be called
        # We can't easily test the file reload in isolation because it uses
        # the global CONFIG_PREFIX which points to the real config file
        self.learning_manager.reload_configuration()
        
        # Verify configuration is still loaded after reload
        self.assertIsNotNone(self.learning_manager.min_monsters_for_recommendations)
        self.assertIsNotNone(self.learning_manager.min_locations_for_exploration)
    
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


class TestLearningManagerCapabilityAnalysis(unittest.TestCase):
    """Test capability analysis methods in LearningManager."""
    
    def setUp(self):
        """Set up test fixtures for capability analysis tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_knowledge_base = Mock()
        self.mock_map_state = Mock()
        self.mock_client = Mock()
        
        # Create test config file
        config_content = """
thresholds:
  min_monsters_for_recommendations: 3
  min_locations_for_exploration: 20
"""
        with open(os.path.join(self.temp_dir, 'goal_templates.yaml'), 'w') as f:
            f.write(config_content)
        
        # Patch config directory
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            self.learning_manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client  # Pass client to enable capability analyzer
            )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_learn_from_capability_analysis_no_analyzer(self):
        """Test capability analysis learning with no analyzer."""
        # Create manager without client (no capability analyzer)
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state
            )
        
        result = manager.learn_from_capability_analysis("ash_tree")
        
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Capability analyzer not initialized')
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_learn_from_capability_analysis_resource(self, mock_analyzer_class):
        """Test capability analysis learning for resource."""
        # Mock capability analyzer
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        # Recreate manager to get mocked analyzer
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Mock analyzer response
        mock_drops = [{'code': 'ash_wood', 'quantity': 1}]
        mock_analyzer.analyze_resource_drops.return_value = mock_drops
        
        result = manager.learn_from_capability_analysis(resource_code="ash_tree")
        
        # Verify structure
        self.assertIn('resource_analysis', result)
        self.assertEqual(result['resource_analysis']['resource_code'], 'ash_tree')
        self.assertEqual(result['resource_analysis']['drops'], mock_drops)
        
        # Verify calls
        mock_analyzer.analyze_resource_drops.assert_called_once_with("ash_tree")
        self.mock_knowledge_base.learn_resource_capabilities.assert_called_once_with("ash_tree", mock_drops)
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_learn_from_capability_analysis_item(self, mock_analyzer_class):
        """Test capability analysis learning for item."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Mock analyzer response
        mock_capabilities = {'craftable': True, 'equippable': True}
        mock_analyzer.analyze_item_capabilities.return_value = mock_capabilities
        
        result = manager.learn_from_capability_analysis(item_code="wooden_staff")
        
        # Verify structure
        self.assertIn('item_analysis', result)
        self.assertEqual(result['item_analysis'], mock_capabilities)
        
        # Verify calls
        mock_analyzer.analyze_item_capabilities.assert_called_once_with("wooden_staff")
        self.mock_knowledge_base.learn_item_capabilities.assert_called_once_with("wooden_staff", mock_capabilities)
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_learn_from_capability_analysis_exception(self, mock_analyzer_class):
        """Test capability analysis learning with exception."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Make analyzer raise exception
        mock_analyzer.analyze_resource_drops.side_effect = Exception("Analysis failed")
        
        result = manager.learn_from_capability_analysis(resource_code="ash_tree")
        
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Analysis failed')
    
    def test_analyze_upgrade_chain_no_analyzer(self):
        """Test upgrade chain analysis with no analyzer."""
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state
            )
        
        result = manager.analyze_upgrade_chain("ash_tree", "wooden_staff")
        
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Capability analyzer not initialized')
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_analyze_upgrade_chain_success(self, mock_analyzer_class):
        """Test successful upgrade chain analysis."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Mock analyzer response
        mock_chain = {
            'viable': True,
            'paths': [
                {'resource': 'ash_tree', 'intermediate': 'ash_wood', 'target': 'wooden_staff'}
            ]
        }
        mock_analyzer.analyze_upgrade_chain.return_value = mock_chain
        
        result = manager.analyze_upgrade_chain("ash_tree", "wooden_staff")
        
        # Verify result
        self.assertEqual(result, mock_chain)
        
        # Verify calls
        mock_analyzer.analyze_upgrade_chain.assert_called_once_with("ash_tree", "wooden_staff")
        self.mock_knowledge_base.learn_upgrade_chain.assert_called_once_with("ash_tree", "wooden_staff", mock_chain)
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_analyze_upgrade_chain_not_viable(self, mock_analyzer_class):
        """Test upgrade chain analysis when not viable."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Mock non-viable chain
        mock_chain = {'viable': False, 'reason': 'Missing intermediate item'}
        mock_analyzer.analyze_upgrade_chain.return_value = mock_chain
        
        result = manager.analyze_upgrade_chain("copper_ore", "iron_sword")
        
        # Should return result but not learn (not viable)
        self.assertEqual(result, mock_chain)
        self.mock_knowledge_base.learn_upgrade_chain.assert_not_called()
    
    def test_evaluate_weapon_upgrade_no_analyzer(self):
        """Test weapon upgrade evaluation with no analyzer."""
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state
            )
        
        result = manager.evaluate_weapon_upgrade("wooden_staff", "iron_sword")
        
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Capability analyzer not initialized')
    
    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_evaluate_weapon_upgrade_success(self, mock_analyzer_class):
        """Test successful weapon upgrade evaluation."""
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
        
        # Mock comparison response
        mock_comparison = {
            'recommended': True,
            'attack_improvement': 5,
            'defense_improvement': 2
        }
        mock_analyzer.compare_weapon_upgrades.return_value = mock_comparison
        
        result = manager.evaluate_weapon_upgrade("wooden_staff", "iron_sword")
        
        # Verify result
        self.assertEqual(result, mock_comparison)
        
        # Verify calls
        mock_analyzer.compare_weapon_upgrades.assert_called_once_with("wooden_staff", "iron_sword")
        self.mock_knowledge_base.learn_weapon_comparison.assert_called_once_with("wooden_staff", "iron_sword", mock_comparison)


class TestLearningManagerBulkLearning(unittest.TestCase):
    """Test bulk learning methods in LearningManager."""
    
    def setUp(self):
        """Set up test fixtures for bulk learning tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_knowledge_base = Mock()
        self.mock_map_state = Mock()
        self.mock_map_state.data = {}  # Initialize as empty dict for map storage
        self.mock_client = Mock()
        
        # Create test config file
        config_content = "thresholds: {}"
        with open(os.path.join(self.temp_dir, 'goal_templates.yaml'), 'w') as f:
            f.write(config_content)
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            self.manager = LearningManager(
                self.mock_knowledge_base,
                self.mock_map_state,
                self.mock_client
            )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_success(self, mock_api):
        """Test successful bulk resource learning."""
        # Mock API responses
        mock_resource1 = Mock()
        mock_resource1.to_dict.return_value = {'code': 'ash_tree', 'skill': 'woodcutting'}
        mock_resource2 = Mock()
        mock_resource2.to_dict.return_value = {'code': 'copper_ore', 'skill': 'mining'}
        
        mock_response = Mock()
        mock_response.data = [mock_resource1, mock_resource2]
        mock_api.return_value = mock_response
        
        result = self.manager.learn_all_resources_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 2)
        self.assertEqual(result['resources_learned'], ['ash_tree', 'copper_ore'])
        
        # Verify knowledge base calls
        self.assertEqual(self.mock_knowledge_base.learn_resource.call_count, 2)
        self.mock_knowledge_base.save.assert_called_once()
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_pagination(self, mock_api):
        """Test bulk resource learning with pagination."""
        # Mock two pages of results
        mock_resource1 = Mock()
        mock_resource1.to_dict.return_value = {'code': 'resource1'}
        mock_resource2 = Mock()
        mock_resource2.to_dict.return_value = {'code': 'resource2'}
        
        # First page - full page
        mock_response1 = Mock()
        mock_response1.data = [mock_resource1] * 100  # Full page
        
        # Second page - partial page (indicates end)
        mock_response2 = Mock()
        mock_response2.data = [mock_resource2]  # Only 1 item, less than page_size
        
        mock_api.side_effect = [mock_response1, mock_response2]
        
        result = self.manager.learn_all_resources_bulk(self.mock_client)
        
        # Should have made 2 API calls
        self.assertEqual(mock_api.call_count, 2)
        
        # Should have learned 101 resources (100 + 1)
        self.assertEqual(result['total_resources_learned'], 101)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_exception(self, mock_api):
        """Test bulk resource learning with exception."""
        mock_api.side_effect = Exception("API connection failed")
        
        result = self.manager.learn_all_resources_bulk(self.mock_client)
        
        # Verify failure response
        self.assertFalse(result['success'])
        self.assertIn('API connection failed', result['error'])
        self.assertEqual(result['total_resources_learned'], 0)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_no_response(self, mock_api):
        """Test bulk resource learning with no API response."""
        mock_api.return_value = None
        
        result = self.manager.learn_all_resources_bulk(self.mock_client)
        
        # Should handle gracefully
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 0)
    
    @patch('src.controller.learning_manager.get_all_resources_api')
    def test_learn_all_resources_bulk_resource_processing_error(self, mock_api):
        """Test bulk resource learning with individual resource processing errors."""
        # Mock one good resource and one bad one
        mock_resource_good = Mock()
        mock_resource_good.to_dict.return_value = {'code': 'ash_tree'}
        
        mock_resource_bad = Mock()
        mock_resource_bad.to_dict.side_effect = Exception("Bad resource data")
        
        mock_response = Mock()
        mock_response.data = [mock_resource_good, mock_resource_bad]
        mock_api.return_value = mock_response
        
        result = self.manager.learn_all_resources_bulk(self.mock_client)
        
        # Should still succeed, just learning fewer resources
        self.assertTrue(result['success'])
        self.assertEqual(result['total_resources_learned'], 1)  # Only the good one
        self.assertEqual(result['resources_learned'], ['ash_tree'])
    
    def test_learn_all_game_data_bulk_success(self):
        """Test successful comprehensive bulk learning."""
        # Mock all individual learning methods
        with patch.object(self.manager, 'learn_all_resources_bulk') as mock_resources:
            with patch.object(self.manager, '_learn_all_monsters_bulk') as mock_monsters:
                with patch.object(self.manager, '_learn_all_items_bulk') as mock_items:
                    with patch.object(self.manager, '_learn_all_npcs_bulk') as mock_npcs:
                        with patch.object(self.manager, '_learn_all_maps_bulk') as mock_maps:
                            with patch.object(self.manager, 'learn_all_effects_bulk') as mock_effects:
                                # Set up mock responses
                                mock_resources.return_value = {'success': True, 'total_resources_learned': 10}
                                mock_monsters.return_value = {'success': True, 'total_monsters_learned': 5}
                                mock_items.return_value = {'success': True, 'total_items_learned': 20}
                                mock_npcs.return_value = {'success': True, 'total_npcs_learned': 3}
                                mock_maps.return_value = {'success': True, 'total_maps_learned': 100}
                                mock_effects.return_value = {'success': True, 'total_effects_learned': 15}
                                
                                result = self.manager.learn_all_game_data_bulk(self.mock_client)
                                
                                # Verify overall success
                                self.assertTrue(result['success'])
                                
                                # Verify all methods called
                                mock_resources.assert_called_once_with(self.mock_client)
                                mock_monsters.assert_called_once_with(self.mock_client)
                                mock_items.assert_called_once_with(self.mock_client)
                                mock_npcs.assert_called_once_with(self.mock_client)
                                mock_maps.assert_called_once_with(self.mock_client)
                                mock_effects.assert_called_once_with(self.mock_client)
                                
                                # Verify stats
                                expected_total = 10 + 5 + 20 + 3 + 100 + 15  # 153
                                self.assertEqual(result['stats']['total'], expected_total)
                                self.assertEqual(result['stats']['resources'], 10)
                                self.assertEqual(result['stats']['monsters'], 5)
    
    def test_learn_all_game_data_bulk_with_errors(self):
        """Test comprehensive bulk learning with some errors."""
        with patch.object(self.manager, 'learn_all_resources_bulk') as mock_resources:
            with patch.object(self.manager, '_learn_all_monsters_bulk') as mock_monsters:
                with patch.object(self.manager, '_learn_all_items_bulk') as mock_items:
                    with patch.object(self.manager, '_learn_all_npcs_bulk') as mock_npcs:
                        with patch.object(self.manager, '_learn_all_maps_bulk') as mock_maps:
                            with patch.object(self.manager, 'learn_all_effects_bulk') as mock_effects:
                                # Some succeed, some fail
                                mock_resources.return_value = {'success': True, 'total_resources_learned': 10}
                                mock_monsters.return_value = {'success': False, 'error': 'Monster API failed', 'total_monsters_learned': 0}
                                mock_items.return_value = {'success': True, 'total_items_learned': 20}
                                mock_npcs.return_value = {'success': False, 'error': 'NPC API failed', 'total_npcs_learned': 0}
                                mock_maps.return_value = {'success': True, 'total_maps_learned': 100}
                                mock_effects.return_value = {'success': True, 'total_effects_learned': 15}
                                
                                result = self.manager.learn_all_game_data_bulk(self.mock_client)
                                
                                # Should mark overall as failed due to errors
                                self.assertFalse(result['success'])
                                
                                # Should have error messages
                                self.assertIn('Monsters: Monster API failed', result['errors'])
                                self.assertIn('NPCs: NPC API failed', result['errors'])
                                
                                # Should still have partial stats
                                self.assertEqual(result['stats']['resources'], 10)
                                self.assertEqual(result['stats']['monsters'], 0)
                                self.assertEqual(result['stats']['items'], 20)
    
    def test_learn_all_game_data_bulk_exception(self):
        """Test comprehensive bulk learning with overall exception."""
        with patch.object(self.manager, 'learn_all_resources_bulk') as mock_resources:
            # Make first method raise exception
            mock_resources.side_effect = Exception("Overall failure")
            
            result = self.manager.learn_all_game_data_bulk(self.mock_client)
            
            # Should return error response
            self.assertFalse(result['success'])
            self.assertIn('Overall failure', result['error'])
    
    @patch('src.controller.learning_manager.get_all_monsters_api')
    def test_learn_all_monsters_bulk(self, mock_api):
        """Test bulk monster learning."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.to_dict.return_value = {'code': 'chicken', 'level': 1}
        
        mock_response = Mock()
        mock_response.data = [mock_monster]
        mock_api.return_value = mock_response
        
        result = self.manager._learn_all_monsters_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_monsters_learned'], 1)
        self.assertEqual(result['monsters_learned'], ['chicken'])
        
        # Verify knowledge base call
        self.mock_knowledge_base._learn_monster_discovery.assert_called_once_with('chicken', 0, 0, {'code': 'chicken', 'level': 1})
    
    @patch('src.controller.learning_manager.get_all_items_api')
    def test_learn_all_items_bulk(self, mock_api):
        """Test bulk item learning."""
        # Mock API response
        mock_item = Mock()
        mock_item.to_dict.return_value = {'code': 'wooden_staff', 'type': 'weapon'}
        
        mock_response = Mock()
        mock_response.data = [mock_item]
        mock_api.return_value = mock_response
        
        result = self.manager._learn_all_items_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_items_learned'], 1)
        self.assertEqual(result['items_learned'], ['wooden_staff'])
        
        # Verify knowledge base call
        self.mock_knowledge_base._learn_item_discovery.assert_called_once_with('wooden_staff', 0, 0, {'code': 'wooden_staff', 'type': 'weapon'})
    
    @patch('src.controller.learning_manager.get_all_npcs_api')
    def test_learn_all_npcs_bulk(self, mock_api):
        """Test bulk NPC learning."""
        # Mock API response
        mock_npc = Mock()
        mock_npc.to_dict.return_value = {'code': 'mining_master', 'skill': 'mining'}
        
        mock_response = Mock()
        mock_response.data = [mock_npc]
        mock_api.return_value = mock_response
        
        result = self.manager._learn_all_npcs_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_npcs_learned'], 1)
        self.assertEqual(result['npcs_learned'], ['mining_master'])
        
        # Verify knowledge base call
        self.mock_knowledge_base._learn_npc_discovery.assert_called_once_with('mining_master', 0, 0, {'code': 'mining_master', 'skill': 'mining'})
    
    @patch('src.controller.learning_manager.get_all_maps_api')
    def test_learn_all_maps_bulk(self, mock_api):
        """Test bulk map learning."""
        # Mock API response
        mock_map = Mock()
        mock_map.to_dict.return_value = {
            'x': 5,
            'y': 10,
            'content': {
                'type': 'monster',
                'code': 'chicken'
            }
        }
        
        mock_response = Mock()
        mock_response.data = [mock_map]
        mock_api.return_value = mock_response
        
        result = self.manager._learn_all_maps_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_maps_learned'], 1)
        self.assertEqual(result['maps_learned'], ['5,10'])
        
        # Verify map state and knowledge base calls
        self.assertIn('5,10', self.mock_map_state.data)
        self.mock_knowledge_base.learn_from_content_discovery.assert_called_once()
    
    @patch('src.controller.learning_manager.get_all_effects_api')
    def test_learn_all_effects_bulk(self, mock_api):
        """Test bulk effects learning."""
        # Mock API response
        mock_effect = Mock()
        mock_effect.to_dict.return_value = {
            'name': 'Mining XP',
            'description': 'Grants mining experience',
            'value': 10
        }
        
        mock_response = Mock()
        mock_response.data = [mock_effect]
        mock_api.return_value = mock_response
        
        # Mock _analyze_xp_effect method
        with patch.object(self.manager, '_analyze_xp_effect') as mock_analyze_xp:
            result = self.manager.learn_all_effects_bulk(self.mock_client)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['total_effects_learned'], 1)
        self.assertEqual(result['effects_learned'], ['Mining XP'])
        
        # Verify knowledge base calls
        self.mock_knowledge_base.learn_effect.assert_called_once_with('Mining XP', {'name': 'Mining XP', 'description': 'Grants mining experience', 'value': 10})
        mock_analyze_xp.assert_called_once()
    
    def test_analyze_xp_effect(self):
        """Test XP effect analysis."""
        # Mock knowledge base to return known skills
        with patch.object(self.manager, '_get_known_skills_from_knowledge_base') as mock_get_skills:
            mock_get_skills.return_value = ['mining', 'woodcutting', 'combat']
            
            xp_effects = {}
            
            # Test mining XP effect
            effect_data = {
                'name': 'Mining XP Boost',
                'description': 'Increases mining experience gain',
                'value': 15
            }
            
            self.manager._analyze_xp_effect(effect_data, xp_effects)
            
            # Should have identified mining skill
            self.assertIn('mining', xp_effects)
            self.assertEqual(len(xp_effects['mining']), 1)
            self.assertEqual(xp_effects['mining'][0]['effect_name'], 'Mining XP Boost')
    
    def test_analyze_xp_effect_no_xp_keyword(self):
        """Test XP effect analysis with effect that doesn't grant XP."""
        with patch.object(self.manager, '_get_known_skills_from_knowledge_base') as mock_get_skills:
            mock_get_skills.return_value = ['mining', 'woodcutting']
            
            xp_effects = {}
            
            # Effect without 'xp' in name
            effect_data = {
                'name': 'Speed Boost',
                'description': 'Increases movement speed',
                'value': 10
            }
            
            self.manager._analyze_xp_effect(effect_data, xp_effects)
            
            # Should not add any XP effects
            self.assertEqual(len(xp_effects), 0)
    
    def test_find_xp_sources_for_skill(self):
        """Test finding XP sources for a specific skill."""
        # Mock knowledge base data
        self.mock_knowledge_base.data = {
            'xp_effects_analysis': {
                'mining': [
                    {
                        'effect_name': 'Mining XP Boost',
                        'effect_description': 'Increases mining XP',
                        'effect_value': 10
                    }
                ]
            }
        }
        
        sources = self.manager.find_xp_sources_for_skill('mining')
        
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['effect_name'], 'Mining XP Boost')
    
    def test_find_xp_sources_for_skill_no_knowledge_base(self):
        """Test finding XP sources with no knowledge base."""
        # Set knowledge base to None
        self.manager.knowledge_base = None
        
        sources = self.manager.find_xp_sources_for_skill('mining')
        
        self.assertEqual(len(sources), 0)
    
    def test_get_known_skills_from_knowledge_base(self):
        """Test getting known skills from knowledge base."""
        # Mock knowledge base data
        self.mock_knowledge_base.data = {
            'items': {
                'wooden_staff': {
                    'craft_data': {'skill': 'weaponcrafting'}
                },
                'iron_sword': {
                    'craft': {'skill': 'weaponcrafting'}
                }
            },
            'resources': {
                'ash_tree': {'skill': 'woodcutting'},
                'copper_ore': {'skill': 'mining'}
            },
            'monsters': {
                'chicken': {'level': 1}
            },
            'workshops': {
                'weaponcrafting_workshop': {'craft_skill': 'weaponcrafting'}
            }
        }
        
        skills = self.manager._get_known_skills_from_knowledge_base()
        
        # Should find all skills from different sources
        expected_skills = ['combat', 'mining', 'weaponcrafting', 'woodcutting']
        self.assertEqual(sorted(skills), expected_skills)
    
    def test_get_known_skills_from_knowledge_base_no_data(self):
        """Test getting known skills with no knowledge base data."""
        self.manager.knowledge_base = None
        
        skills = self.manager._get_known_skills_from_knowledge_base()
        
        self.assertEqual(len(skills), 0)


if __name__ == '__main__':
    unittest.main()