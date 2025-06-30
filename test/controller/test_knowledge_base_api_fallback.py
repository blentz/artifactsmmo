"""Test module for KnowledgeBase API fallback functionality."""

import unittest
from unittest.mock import Mock, patch
import tempfile
import os
from src.controller.knowledge.base import KnowledgeBase


class TestKnowledgeBaseAPIFallback(unittest.TestCase):
    """Test cases for KnowledgeBase API fallback methods."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_file.close()
        
        # Create knowledge base with temporary file
        self.knowledge_base = KnowledgeBase(filename=self.temp_file.name)
        
        # Mock client
        self.mock_client = Mock()

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    @patch('src.controller.knowledge.base.get_monster_api')
    def test_get_monster_data_with_fallback(self, mock_get_monster):
        """Test get_monster_data uses API fallback when not in knowledge base."""
        # Setup mock response
        mock_monster = Mock()
        mock_monster.code = 'dragon'
        mock_monster.name = 'Dragon'
        mock_monster.level = 10
        mock_monster.hp = 100
        mock_monster.attack_fire = 20
        mock_monster.attack_earth = 0
        mock_monster.attack_water = 0
        mock_monster.attack_air = 0
        mock_monster.res_fire = 10
        mock_monster.res_earth = 5
        mock_monster.res_water = 5
        mock_monster.res_air = 5
        mock_monster.drops = []
        
        mock_response = Mock()
        mock_response.data = mock_monster
        mock_get_monster.return_value = mock_response
        
        # Test API fallback
        result = self.knowledge_base.get_monster_data('dragon', client=self.mock_client)
        
        # Verify API was called
        mock_get_monster.assert_called_once_with(code='dragon', client=self.mock_client)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'dragon')
        self.assertEqual(result['name'], 'Dragon')
        self.assertEqual(result['level'], 10)
        self.assertEqual(result['hp'], 100)
        
        # Verify data was stored
        self.assertIn('dragon', self.knowledge_base.data['monsters'])
        
        # Test subsequent call doesn't use API
        mock_get_monster.reset_mock()
        result2 = self.knowledge_base.get_monster_data('dragon', client=self.mock_client)
        mock_get_monster.assert_not_called()
        self.assertEqual(result2['code'], 'dragon')

    @patch('src.controller.knowledge.base.get_resource_api')
    def test_get_resource_data_with_fallback(self, mock_get_resource):
        """Test get_resource_data uses API fallback when not in knowledge base."""
        # Setup mock response
        mock_resource = Mock()
        mock_resource.code = 'iron_ore'
        mock_resource.name = 'Iron Ore'
        mock_resource.skill = 'mining'
        mock_resource.level = 5
        mock_resource.drops = [{'code': 'iron', 'quantity': 1}]
        
        mock_response = Mock()
        mock_response.data = mock_resource
        mock_get_resource.return_value = mock_response
        
        # Test API fallback
        result = self.knowledge_base.get_resource_data('iron_ore', client=self.mock_client)
        
        # Verify API was called
        mock_get_resource.assert_called_once_with(code='iron_ore', client=self.mock_client)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'iron_ore')
        self.assertEqual(result['name'], 'Iron Ore')
        self.assertEqual(result['skill'], 'mining')
        self.assertEqual(result['level'], 5)
        
        # Verify data was stored
        self.assertIn('iron_ore', self.knowledge_base.data['resources'])

    @patch('src.controller.knowledge.base.get_item_api')
    def test_get_item_data_with_fallback(self, mock_get_item):
        """Test get_item_data uses API fallback when not in knowledge base."""
        # Setup mock response
        mock_item = Mock()
        mock_item.code = 'iron_sword'
        mock_item.name = 'Iron Sword'
        mock_item.type = 'weapon'
        mock_item.subtype = 'sword'
        mock_item.level = 10
        mock_item.effects = []
        mock_item.description = 'A basic iron sword'
        mock_item.tradeable = True
        
        mock_response = Mock()
        mock_response.data = mock_item
        mock_get_item.return_value = mock_response
        
        # Test API fallback
        result = self.knowledge_base.get_item_data('iron_sword', client=self.mock_client)
        
        # Verify API was called
        mock_get_item.assert_called_once_with(code='iron_sword', client=self.mock_client)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'iron_sword')
        self.assertEqual(result['name'], 'Iron Sword')
        self.assertEqual(result['type'], 'weapon')
        self.assertEqual(result['subtype'], 'sword')
        self.assertEqual(result['level'], 10)
        
        # Verify data was stored
        self.assertIn('iron_sword', self.knowledge_base.data['items'])

    @patch('src.controller.knowledge.base.get_npc_api')
    def test_get_npc_data_with_fallback(self, mock_get_npc):
        """Test get_npc_data uses API fallback when not in knowledge base."""
        # Setup mock response
        mock_npc = Mock()
        mock_npc.code = 'merchant_john'
        mock_npc.name = 'Merchant John'
        mock_npc.type = 'merchant'
        mock_npc.subtype = 'general'
        mock_npc.description = 'A friendly merchant'
        mock_npc.services = ['buy', 'sell']
        
        mock_response = Mock()
        mock_response.data = mock_npc
        mock_get_npc.return_value = mock_response
        
        # Test API fallback
        result = self.knowledge_base.get_npc_data('merchant_john', client=self.mock_client)
        
        # Verify API was called
        mock_get_npc.assert_called_once_with(code='merchant_john', client=self.mock_client)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'merchant_john')
        self.assertEqual(result['name'], 'Merchant John')
        self.assertEqual(result['type'], 'merchant')
        self.assertEqual(result['description'], 'A friendly merchant')
        
        # Verify data was stored
        self.assertIn('merchant_john', self.knowledge_base.data['npcs'])

    def test_fallback_methods_without_client(self):
        """Test fallback methods return None when no client provided."""
        # Test without client
        self.assertIsNone(self.knowledge_base.get_monster_data('unknown_monster'))
        self.assertIsNone(self.knowledge_base.get_resource_data('unknown_resource'))
        self.assertIsNone(self.knowledge_base.get_item_data('unknown_item'))
        self.assertIsNone(self.knowledge_base.get_npc_data('unknown_npc'))

    @patch('src.controller.knowledge.base.get_monster_api')
    def test_fallback_handles_api_errors(self, mock_get_monster):
        """Test fallback handles API errors gracefully."""
        # Setup mock to raise exception
        mock_get_monster.side_effect = Exception("API Error")
        
        # Test API fallback with error
        result = self.knowledge_base.get_monster_data('error_monster', client=self.mock_client)
        
        # Should return None on error
        self.assertIsNone(result)
        
        # Verify data was not stored
        self.assertNotIn('error_monster', self.knowledge_base.data['monsters'])

    @patch('src.controller.knowledge.base.get_monster_api')
    def test_fallback_handles_not_found(self, mock_get_monster):
        """Test fallback handles 404 not found responses."""
        # Setup mock to return None (404)
        mock_get_monster.return_value = None
        
        # Test API fallback with not found
        result = self.knowledge_base.get_monster_data('nonexistent', client=self.mock_client)
        
        # Should return None
        self.assertIsNone(result)
        
        # Verify data was not stored
        self.assertNotIn('nonexistent', self.knowledge_base.data['monsters'])


if __name__ == '__main__':
    unittest.main()