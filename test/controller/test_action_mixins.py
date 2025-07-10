import logging
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.mixins import KnowledgeBaseSearchMixin, MapStateAccessMixin


# CharacterDataMixin tests removed - component removed for architecture compliance
# Actions should read character data from UnifiedStateContext instead of making direct API calls


class TestKnowledgeBaseSearchMixin(unittest.TestCase):
    """Test KnowledgeBaseSearchMixin functionality."""
    
    def setUp(self):
        # Create a test class that uses the mixin
        class TestAction(KnowledgeBaseSearchMixin):
            def __init__(self):
                self.logger = logging.getLogger(__name__)
        
        self.action = TestAction()
        
        # Create mock knowledge base
        self.knowledge_base = Mock()
        self.knowledge_base.data = {
            'items': {
                'iron_sword': {
                    'item_type': 'weapon',
                    'level': 5,
                    'name': 'Iron Sword'
                },
                'copper_sword': {
                    'item_type': 'weapon',
                    'level': 3,
                    'name': 'Copper Sword'
                },
                'iron_helmet': {
                    'item_type': 'helmet',
                    'level': 5,
                    'name': 'Iron Helmet'
                }
            },
            'resources': {
                'iron_ore': {
                    'skill_required': 'mining',
                    'name': 'Iron Ore'
                },
                'ash_wood': {
                    'skill_required': 'woodcutting',
                    'name': 'Ash Wood'
                }
            },
            'workshops': {
                'weaponcrafting_workshop': {
                    'craft_skill': 'weaponcrafting',
                    'x': 10,
                    'y': 20,
                    'name': 'Weapon Workshop'
                },
                'mining_workshop': {
                    'craft_skill': 'mining',
                    'x': 5,
                    'y': 15,
                    'name': 'Mining Workshop'
                }
            }
        }

    def test_search_knowledge_base_items_by_type(self):
        results = self.action.search_knowledge_base_items(
            self.knowledge_base, 
            item_type='weapon'
        )
        
        self.assertEqual(len(results), 2)
        codes = [r['code'] for r in results]
        self.assertIn('iron_sword', codes)
        self.assertIn('copper_sword', codes)

    def test_search_knowledge_base_items_by_level_range(self):
        results = self.action.search_knowledge_base_items(
            self.knowledge_base,
            level_range=(4, 6)
        )
        
        self.assertEqual(len(results), 2)
        codes = [r['code'] for r in results]
        self.assertIn('iron_sword', codes)
        self.assertIn('iron_helmet', codes)

    def test_search_knowledge_base_resources_by_skill(self):
        results = self.action.search_knowledge_base_resources(
            self.knowledge_base,
            skill_type='mining'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'iron_ore')

    def test_search_knowledge_base_resources_by_code(self):
        results = self.action.search_knowledge_base_resources(
            self.knowledge_base,
            resource_code='ash_wood'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'ash_wood')

    def test_search_knowledge_base_workshops(self):
        results = self.action.search_knowledge_base_workshops(
            self.knowledge_base,
            workshop_type='weaponcrafting'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'weaponcrafting_workshop')
        self.assertEqual(results[0]['location'], (10, 20))

    def test_search_map_state_for_content(self):
        # Create mock map state
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {
                    'type': 'resource',
                    'code': 'iron_ore'
                }
            },
            '5,15': {
                'content': {
                    'type': 'resource',
                    'code': 'copper_ore'
                }
            },
            '0,0': {
                'content': {
                    'type': 'workshop',
                    'code': 'weaponcrafting'
                }
            }
        }
        
        # Search for resources
        results = self.action.search_map_state_for_content(
            map_state,
            content_type='resource'
        )
        
        self.assertEqual(len(results), 2)
        
        # Search for specific resource
        results = self.action.search_map_state_for_content(
            map_state,
            content_code='iron_ore'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['location'], (10, 20))
        
        # Search with radius
        results = self.action.search_map_state_for_content(
            map_state,
            center=(0, 0),
            radius=20
        )
        
        self.assertEqual(len(results), 2)  # Workshop is at 0,0, resources within radius


class TestMapStateAccessMixin(unittest.TestCase):
    """Test MapStateAccessMixin functionality."""
    
    def setUp(self):
        # Create a test class that uses the mixin
        class TestAction(MapStateAccessMixin):
            def __init__(self):
                self.logger = logging.getLogger(__name__)
        
        self.action = TestAction()

    def test_get_location_from_map_state_with_method(self):
        # Mock map state with get_location_info method
        map_state = Mock()
        location_data = {'content': {'type': 'resource'}}
        map_state.get_location_info.return_value = location_data
        
        result = self.action.get_location_from_map_state(map_state, 10, 20)
        
        self.assertEqual(result, location_data)
        map_state.get_location_info.assert_called_once_with(10, 20)

    def test_get_location_from_map_state_fallback_to_data(self):
        # Mock map state without methods but with data
        map_state = Mock(spec=['data'])
        map_state.data = {
            '10,20': {'content': {'type': 'resource'}}
        }
        
        result = self.action.get_location_from_map_state(map_state, 10, 20)
        
        self.assertEqual(result, {'content': {'type': 'resource'}})

    def test_extract_map_state(self):
        map_state = Mock()
        kwargs = {'map_state': map_state, 'other': 'data'}
        
        result = self.action.extract_map_state(kwargs)
        
        self.assertEqual(result, map_state)

    def test_extract_knowledge_base(self):
        knowledge_base = Mock()
        kwargs = {'knowledge_base': knowledge_base, 'other': 'data'}
        
        result = self.action.extract_knowledge_base(kwargs)
        
        self.assertEqual(result, knowledge_base)


if __name__ == '__main__':
    unittest.main()