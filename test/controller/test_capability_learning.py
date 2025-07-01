"""
Test capability learning system for ash_tree → ash_wood → wooden_staff analysis.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.capability_analyzer import CapabilityAnalyzer
from src.controller.knowledge.base import KnowledgeBase
from src.controller.learning_manager import LearningManager

from test.fixtures import create_mock_client


class TestCapabilityLearning(unittest.TestCase):
    """Test the capability learning system for upgrade chain analysis."""
    
    def setUp(self):
        """Set up test environment with mocked API client."""
        self.temp_dir = tempfile.mkdtemp()
        self.knowledge_file = os.path.join(self.temp_dir, 'test_knowledge.yaml')
        
        # Mock client for API calls
        self.mock_client = create_mock_client()
        
        # Initialize components
        self.knowledge_base = KnowledgeBase(filename=self.knowledge_file)
        self.map_state = Mock()
        self.learning_manager = LearningManager(
            knowledge_base=self.knowledge_base,
            map_state=self.map_state,
            client=self.mock_client
        )
        self.capability_analyzer = CapabilityAnalyzer(self.mock_client)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.capability_analyzer.get_resource_api')
    def test_analyze_ash_tree_drops(self, mock_get_resource):
        """Test analyzing ash_tree resource to discover ash_wood drops."""
        # Mock API response for ash_tree resource
        mock_response = Mock()
        mock_response.data.drops = [
            Mock(code='ash_wood', rate=1, min_quantity=1, max_quantity=3)
        ]
        mock_get_resource.return_value = mock_response
        
        # Analyze ash_tree drops
        drops = self.capability_analyzer.analyze_resource_drops('ash_tree')
        
        # Verify analysis results
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0]['item_code'], 'ash_wood')
        self.assertEqual(drops[0]['drop_rate'], 1)
        self.assertEqual(drops[0]['probability'], '1/1')
        
        # Verify API was called correctly
        mock_get_resource.assert_called_once_with(client=self.mock_client, code='ash_tree')
    
    @patch('src.controller.capability_analyzer.get_item_api')
    def test_analyze_wooden_staff_capabilities(self, mock_get_item):
        """Test analyzing wooden_staff item to discover attack effects and crafting requirements."""
        # Mock API response for wooden_staff item
        mock_response = Mock()
        mock_response.data.name = 'Wooden Staff'
        mock_response.data.code = 'wooden_staff'
        mock_response.data.level = 1
        mock_response.data.type_ = 'weapon'
        mock_response.data.subtype = 'staff'
        
        # Mock effects (attack power)
        mock_effect = Mock()
        mock_effect.code = 'attack'
        mock_effect.value = 6
        mock_response.data.effects = [mock_effect]
        
        # Mock crafting requirements
        mock_craft = Mock()
        mock_ingredient = Mock()
        mock_ingredient.code = 'ash_wood'
        mock_ingredient.quantity = 6
        mock_craft.items = [mock_ingredient]
        mock_response.data.craft = mock_craft
        
        mock_get_item.return_value = mock_response
        
        # Analyze wooden_staff capabilities
        capabilities = self.capability_analyzer.analyze_item_capabilities('wooden_staff')
        
        # Verify analysis results
        self.assertEqual(capabilities['name'], 'Wooden Staff')
        self.assertEqual(capabilities['code'], 'wooden_staff')
        self.assertEqual(capabilities['type'], 'weapon')
        self.assertTrue(capabilities['can_craft'])
        
        # Check effects
        self.assertEqual(len(capabilities['effects']), 1)
        self.assertEqual(capabilities['effects'][0]['name'], 'attack')
        self.assertEqual(capabilities['effects'][0]['value'], 6)
        
        # Check crafting requirements
        self.assertEqual(len(capabilities['craft_requirements']), 1)
        self.assertEqual(capabilities['craft_requirements'][0]['code'], 'ash_wood')
        self.assertEqual(capabilities['craft_requirements'][0]['quantity'], 6)
    
    @patch('src.controller.capability_analyzer.get_item_api')
    @patch('src.controller.capability_analyzer.get_resource_api')
    def test_ash_tree_to_wooden_staff_upgrade_chain(self, mock_get_resource, mock_get_item):
        """Test complete upgrade chain analysis: ash_tree → ash_wood → wooden_staff."""
        # Mock ash_tree resource response
        mock_resource_response = Mock()
        mock_resource_response.data.drops = [
            Mock(code='ash_wood', rate=1, min_quantity=1, max_quantity=3)
        ]
        mock_get_resource.return_value = mock_resource_response
        
        # Mock wooden_staff item response
        mock_item_response = Mock()
        mock_item_response.data.name = 'Wooden Staff'
        mock_item_response.data.code = 'wooden_staff'
        mock_item_response.data.level = 1
        mock_item_response.data.type_ = 'weapon'
        mock_item_response.data.subtype = 'staff'
        
        # Mock attack effect
        mock_effect = Mock()
        mock_effect.code = 'attack'
        mock_effect.value = 6
        mock_item_response.data.effects = [mock_effect]
        
        # Mock crafting requirements (ash_wood needed)
        mock_craft = Mock()
        mock_ingredient = Mock()
        mock_ingredient.code = 'ash_wood'
        mock_ingredient.quantity = 6
        mock_craft.items = [mock_ingredient]
        mock_item_response.data.craft = mock_craft
        
        mock_get_item.return_value = mock_item_response
        
        # Analyze complete upgrade chain
        chain_analysis = self.capability_analyzer.analyze_upgrade_chain('ash_tree', 'wooden_staff')
        
        # Verify chain is viable
        self.assertTrue(chain_analysis['viable'])
        self.assertEqual(len(chain_analysis['paths']), 1)
        
        # Check the viable path
        path = chain_analysis['paths'][0]
        self.assertEqual(path['resource'], 'ash_tree')
        self.assertEqual(path['intermediate'], 'ash_wood')
        self.assertEqual(path['target'], 'wooden_staff')
        self.assertEqual(path['drop_rate'], 1)
        self.assertEqual(path['required_quantity'], 6)
        
        # Check target capabilities
        target_caps = chain_analysis['target_capabilities']
        self.assertEqual(target_caps['name'], 'Wooden Staff')
        self.assertEqual(len(target_caps['effects']), 1)
        self.assertEqual(target_caps['effects'][0]['value'], 6)  # Attack power
    
    @patch('src.controller.capability_analyzer.get_item_api')
    def test_wooden_stick_vs_wooden_staff_comparison(self, mock_get_item):
        """Test weapon comparison: wooden_stick vs wooden_staff upgrade viability."""
        # Mock responses for both weapons
        def mock_item_response(code):
            response = Mock()
            if code == 'wooden_stick':
                response.data.name = 'Wooden Stick'
                response.data.code = 'wooden_stick'
                response.data.level = 1
                response.data.type_ = 'weapon'
                response.data.subtype = 'stick'
                # Mock lower attack effect
                mock_effect = Mock()
                mock_effect.code = 'attack'
                mock_effect.value = 2
                response.data.effects = [mock_effect]
                response.data.craft = None
            elif code == 'wooden_staff':
                response.data.name = 'Wooden Staff'
                response.data.code = 'wooden_staff'
                response.data.level = 1
                response.data.type_ = 'weapon'
                response.data.subtype = 'staff'
                # Mock higher attack effect
                mock_effect = Mock()
                mock_effect.code = 'attack'
                mock_effect.value = 6
                response.data.effects = [mock_effect]
                response.data.craft = None
            return response
        
        mock_get_item.side_effect = lambda client, code: mock_item_response(code)
        
        # Compare weapons
        comparison = self.capability_analyzer.compare_weapon_upgrades('wooden_stick', 'wooden_staff')
        
        # Verify upgrade is recommended
        self.assertTrue(comparison['recommendUpgrade'])
        self.assertEqual(comparison['current_attack'], 2)
        self.assertEqual(comparison['upgrade_attack'], 6)
        self.assertEqual(comparison['attack_improvement'], 4)
        self.assertIn('increases by 4', comparison['reason'])
    
    def test_learning_manager_integration(self):
        """Test learning manager integration with capability analysis."""
        # Test that learning manager can perform capability analysis
        with patch.object(self.learning_manager.capability_analyzer, 'analyze_resource_drops') as mock_analyze:
            mock_analyze.return_value = [{'item_code': 'ash_wood', 'drop_rate': 1}]
            
            # Perform learning
            result = self.learning_manager.learn_from_capability_analysis(resource_code='ash_tree')
            
            # Verify learning was performed
            self.assertIsNotNone(result['resource_analysis'])
            self.assertEqual(result['resource_analysis']['resource_code'], 'ash_tree')
            mock_analyze.assert_called_once_with('ash_tree')
    
    def test_knowledge_base_persistence(self):
        """Test that capability learning data is persisted to knowledge base."""
        # Test resource capability storage
        drops = [{'item_code': 'ash_wood', 'drop_rate': 1, 'min_quantity': 1, 'max_quantity': 3}]
        self.knowledge_base.learn_resource_capabilities('ash_tree', drops)
        
        # Verify data was stored
        self.assertIn('resource_capabilities', self.knowledge_base.data)
        self.assertIn('ash_tree', self.knowledge_base.data['resource_capabilities'])
        stored_data = self.knowledge_base.data['resource_capabilities']['ash_tree']
        self.assertEqual(stored_data['resource_code'], 'ash_tree')
        self.assertEqual(len(stored_data['drops']), 1)
        
        # Test upgrade chain storage
        chain_analysis = {
            'viable': True,
            'paths': [{'resource': 'ash_tree', 'intermediate': 'ash_wood', 'target': 'wooden_staff'}]
        }
        self.knowledge_base.learn_upgrade_chain('ash_tree', 'wooden_staff', chain_analysis)
        
        # Verify chain was stored
        self.assertIn('upgrade_chains', self.knowledge_base.data)
        chain_key = 'ash_tree→wooden_staff'
        self.assertIn(chain_key, self.knowledge_base.data['upgrade_chains'])
        stored_chain = self.knowledge_base.data['upgrade_chains'][chain_key]
        self.assertEqual(stored_chain['resource'], 'ash_tree')
        self.assertEqual(stored_chain['target'], 'wooden_staff')


if __name__ == '__main__':
    unittest.main()