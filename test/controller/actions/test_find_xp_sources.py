"""Test module for FindXpSourcesAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_xp_sources import FindXpSourcesAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestFindXpSourcesAction(unittest.TestCase):
    """Test cases for FindXpSourcesAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindXpSourcesAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = FindXpSourcesAction()
        self.assertIsInstance(action, FindXpSourcesAction)
        self.assertIsNotNone(action.logger)
    
    def test_execute_no_skill_provided(self):
        """Test execution when no skill is provided."""
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No skill type provided")
    
    def test_execute_no_learning_manager(self):
        """Test execution when learning manager is not available."""
        context = MockActionContext(
            character_name=self.character_name,
            skill='mining',
            knowledge_base=Mock()
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Learning manager not available")
    
    def test_execute_no_knowledge_base(self):
        """Test execution when knowledge base is not available."""
        context = MockActionContext(
            character_name=self.character_name,
            skill='mining',
            learning_manager=Mock()
        )
        # Remove knowledge_base
        context.knowledge_base = None
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Knowledge base not available")
    
    def test_execute_effects_not_available_learning_fails(self):
        """Test execution when effects data is not available and learning fails."""
        mock_learning_manager = Mock()
        mock_learning_manager.learn_all_effects_bulk.return_value = {'success': False, 'error': 'API error'}
        
        mock_kb = Mock()
        mock_kb.data = {'effects': {}, 'xp_effects_analysis': {}}
        
        context = MockActionContext(
            character_name=self.character_name,
            skill='mining',
            learning_manager=mock_learning_manager,
            knowledge_base=mock_kb
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Failed to learn effects: API error")
    
    def test_execute_effects_available_found_sources(self):
        """Test execution when effects are available and XP sources found."""
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = [
            {'effect_name': 'mining_xp', 'effect_value': 10, 'effect_description': 'Mining XP gain'}
        ]
        
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {'mining_xp': {'name': 'mining_xp'}},
            'xp_effects_analysis': {'mining': ['mining_xp']},
            'items': {}
        }
        
        context = MockActionContext(
            character_name=self.character_name,
            skill='mining',
            learning_manager=mock_learning_manager,
            knowledge_base=mock_kb
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['skill'], 'mining')
        self.assertEqual(len(result.data['xp_sources']), 1)
        self.assertEqual(result.data['total_sources_found'], 1)
        self.assertEqual(result.message, "Found 1 XP sources for mining skill")
    
    def test_execute_no_sources_found_with_alternatives(self):
        """Test execution when no sources found initially but alternatives exist."""
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.side_effect = [
            [],  # First call returns empty
            [{'effect_name': 'weaponcrafting_xp', 'effect_value': 15}]  # Alternative skill returns sources
        ]
        
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {
                'weaponcrafting_xp': {'name': 'weaponcrafting_xp'}
            },
            'xp_effects_analysis': {},
            'items': {
                'sword': {'craft': {'skill': 'weaponcrafting'}}
            }
        }
        
        context = MockActionContext(
            character_name=self.character_name,
            skill='weapon',
            learning_manager=mock_learning_manager,
            knowledge_base=mock_kb
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.data['xp_sources']), 1)
        mock_learning_manager.find_xp_sources_for_skill.assert_any_call('weaponcrafting')
    
    def test_execute_no_sources_found_at_all(self):
        """Test execution when no XP sources found at all."""
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = []
        
        mock_kb = Mock()
        mock_kb.data = {'effects': {}, 'items': {}}
        
        context = MockActionContext(
            character_name=self.character_name,
            skill='unknown_skill',
            learning_manager=mock_learning_manager,
            knowledge_base=mock_kb
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No XP sources found for skill 'unknown_skill'")
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.side_effect = Exception("Search error")
        
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {'mining_xp': {}},
            'xp_effects_analysis': {'mining': ['mining_xp']}
        }
        
        context = MockActionContext(
            character_name=self.character_name,
            skill='mining',
            learning_manager=mock_learning_manager,
            knowledge_base=mock_kb
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "XP sources search failed: Search error")
    
    def test_check_effects_data_available_valid(self):
        """Test _check_effects_data_available with valid data."""
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {'effect1': {}},
            'xp_effects_analysis': {'mining': ['effect1']}
        }
        
        result = self.action._check_effects_data_available(mock_kb)
        self.assertTrue(result)
    
    def test_check_effects_data_available_missing_effects(self):
        """Test _check_effects_data_available with missing effects."""
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {},
            'xp_effects_analysis': {'mining': ['effect1']}
        }
        
        result = self.action._check_effects_data_available(mock_kb)
        self.assertFalse(result)
    
    def test_check_effects_data_available_missing_xp_analysis(self):
        """Test _check_effects_data_available with missing XP analysis."""
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {'effect1': {}},
            'xp_effects_analysis': {}
        }
        
        result = self.action._check_effects_data_available(mock_kb)
        self.assertFalse(result)
    
    def test_check_effects_data_available_no_kb(self):
        """Test _check_effects_data_available with no knowledge base."""
        result = self.action._check_effects_data_available(None)
        self.assertFalse(result)
    
    def test_check_effects_data_available_no_data_attr(self):
        """Test _check_effects_data_available when kb has no data attribute."""
        mock_kb = Mock()
        del mock_kb.data
        
        result = self.action._check_effects_data_available(mock_kb)
        self.assertFalse(result)
    
    def test_check_effects_data_available_exception(self):
        """Test _check_effects_data_available with exception."""
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        result = self.action._check_effects_data_available(mock_kb)
        self.assertFalse(result)
    
    def test_find_alternative_skill_names(self):
        """Test _find_alternative_skill_names."""
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {
                'woodcutting_xp': {},
                'mining_craft_bonus': {}
            },
            'items': {
                'sword': {'craft': {'skill': 'weaponcrafting'}},
                'pickaxe': {'craft': {'skill': 'mining_advanced'}}
            }
        }
        
        alternatives = self.action._find_alternative_skill_names('mining', mock_kb)
        self.assertIn('mining_advanced', alternatives)
    
    def test_find_alternative_skill_names_no_kb(self):
        """Test _find_alternative_skill_names with no knowledge base."""
        alternatives = self.action._find_alternative_skill_names('mining', None)
        self.assertEqual(alternatives, [])
    
    def test_find_alternative_skill_names_exception(self):
        """Test _find_alternative_skill_names with exception."""
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        alternatives = self.action._find_alternative_skill_names('mining', mock_kb)
        self.assertEqual(alternatives, [])
    
    def test_analyze_actionable_sources_crafting(self):
        """Test _analyze_actionable_sources for crafting effects."""
        xp_sources = [
            {'effect_name': 'weaponcraft_xp', 'effect_value': 10, 'effect_description': 'Crafting weapons gives XP'}
        ]
        
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'sword': {
                    'name': 'Iron Sword',
                    'craft': {'skill': 'weaponcrafting', 'level': 5}
                }
            }
        }
        
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'weaponcrafting')
        
        self.assertEqual(len(result), 1)
        self.assertIn('crafting_items', result[0]['suggested_actions'])
        self.assertTrue(len(result[0]['required_items']) > 0)
    
    def test_analyze_actionable_sources_gathering(self):
        """Test _analyze_actionable_sources for gathering effects."""
        xp_sources = [
            {'effect_name': 'mining_gather_xp', 'effect_value': 5, 'effect_description': 'Mining resources'}
        ]
        
        mock_kb = Mock()
        mock_kb.data = {
            'resources': {
                'iron_ore_deposit': {
                    'name': 'Iron Ore Deposit',
                    'skill': 'mining',
                    'drops': [{'code': 'iron_ore'}]
                }
            },
            'items': {}
        }
        
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'mining')
        
        self.assertEqual(len(result), 1)
        self.assertIn('gathering_resources', result[0]['suggested_actions'])
    
    def test_analyze_actionable_sources_consumables(self):
        """Test _analyze_actionable_sources for consumable effects."""
        xp_sources = [
            {'effect_name': 'potion_mining_xp', 'effect_value': 50, 'effect_description': 'Consume potion for XP'}
        ]
        
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'mining_potion': {
                    'name': 'Mining XP Potion',
                    'type': 'consumable',
                    'effects': [{'name': 'mining_xp', 'value': 50}]
                }
            }
        }
        
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'mining')
        
        self.assertEqual(len(result), 1)
        self.assertIn('consuming_items', result[0]['suggested_actions'])
    
    def test_analyze_actionable_sources_exception(self):
        """Test _analyze_actionable_sources with exception."""
        xp_sources = [{'effect_name': 'test'}]
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'mining')
        
        # Should handle exception gracefully
        self.assertEqual(result, [])
    
    def test_find_craftable_items_for_skill(self):
        """Test _find_craftable_items_for_skill."""
        actionable_info = {
            'required_items': []
        }
        
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'iron_sword': {
                    'name': 'Iron Sword',
                    'craft': {
                        'skill': 'Weaponcrafting',
                        'level': 5
                    }
                },
                'copper_sword': {
                    'name': 'Copper Sword',
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 1
                    }
                }
            }
        }
        
        self.action._find_craftable_items_for_skill(actionable_info, mock_kb, 'weaponcrafting')
        
        self.assertEqual(len(actionable_info['required_items']), 2)
        self.assertEqual(actionable_info['required_items'][0]['action_type'], 'craft')
    
    def test_find_gatherable_resources_for_skill(self):
        """Test _find_gatherable_resources_for_skill."""
        actionable_info = {
            'required_items': []
        }
        
        mock_kb = Mock()
        mock_kb.data = {
            'resources': {
                'iron_deposit': {
                    'name': 'Iron Deposit',
                    'skill': 'Mining',
                    'drops': [{'code': 'iron_ore'}]
                }
            },
            'items': {}
        }
        
        self.action._find_gatherable_resources_for_skill(actionable_info, mock_kb, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 1)
        self.assertEqual(actionable_info['required_items'][0]['action_type'], 'gather')
    
    def test_find_gatherable_resources_with_skill_materials(self):
        """Test _find_gatherable_resources_for_skill with materials for skill."""
        actionable_info = {
            'required_items': []
        }
        
        mock_kb = Mock()
        mock_kb.data = {
            'resources': {
                'tree': {
                    'name': 'Oak Tree',
                    'skill': 'woodcutting',
                    'drops': [{'code': 'oak_wood'}]
                }
            },
            'items': {
                'wooden_sword': {
                    'craft': {
                        'skill': 'weaponcrafting',
                        'items': [{'code': 'oak_wood'}]
                    }
                }
            }
        }
        
        self.action._find_gatherable_resources_for_skill(actionable_info, mock_kb, 'weaponcrafting')
        
        # Should find tree as it produces materials for weaponcrafting
        self.assertEqual(len(actionable_info['required_items']), 1)
        self.assertTrue(actionable_info['required_items'][0]['produces_skill_materials'])
    
    def test_is_item_used_for_skill_true(self):
        """Test _is_item_used_for_skill when item is used."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'sword': {
                    'craft': {
                        'skill': 'weaponcrafting',
                        'items': [{'code': 'iron_ingot'}, {'code': 'leather'}]
                    }
                }
            }
        }
        
        result = self.action._is_item_used_for_skill('iron_ingot', mock_kb, 'weaponcrafting')
        self.assertTrue(result)
    
    def test_is_item_used_for_skill_false(self):
        """Test _is_item_used_for_skill when item is not used."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'sword': {
                    'craft': {
                        'skill': 'weaponcrafting',
                        'items': [{'code': 'iron_ingot'}]
                    }
                }
            }
        }
        
        result = self.action._is_item_used_for_skill('copper_ingot', mock_kb, 'weaponcrafting')
        self.assertFalse(result)
    
    def test_is_item_used_for_skill_exception(self):
        """Test _is_item_used_for_skill with exception."""
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        result = self.action._is_item_used_for_skill('iron_ingot', mock_kb, 'weaponcrafting')
        self.assertFalse(result)
    
    def test_find_consumable_items_for_skill(self):
        """Test _find_consumable_items_for_skill."""
        actionable_info = {
            'required_items': []
        }
        
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'mining_potion': {
                    'name': 'Mining XP Potion',
                    'type': 'potion',
                    'effects': [{'name': 'mining_xp_boost', 'value': 100}]
                },
                'strength_potion': {
                    'name': 'Strength Potion',
                    'type': 'consumable',
                    'effects': [{'name': 'strength_boost', 'value': 5}]
                }
            }
        }
        
        self.action._find_consumable_items_for_skill(actionable_info, mock_kb, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 1)
        self.assertEqual(actionable_info['required_items'][0]['action_type'], 'consume')
        self.assertEqual(actionable_info['required_items'][0]['item_code'], 'mining_potion')
    
    def test_find_craftable_items_no_kb(self):
        """Test _find_craftable_items_for_skill with no knowledge base."""
        actionable_info = {'required_items': []}
        
        self.action._find_craftable_items_for_skill(actionable_info, None, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_find_craftable_items_exception(self):
        """Test _find_craftable_items_for_skill with exception."""
        actionable_info = {'required_items': []}
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        self.action._find_craftable_items_for_skill(actionable_info, mock_kb, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_find_gatherable_resources_no_kb(self):
        """Test _find_gatherable_resources_for_skill with no knowledge base."""
        actionable_info = {'required_items': []}
        
        self.action._find_gatherable_resources_for_skill(actionable_info, None, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_find_gatherable_resources_exception(self):
        """Test _find_gatherable_resources_for_skill with exception."""
        actionable_info = {'required_items': []}
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        self.action._find_gatherable_resources_for_skill(actionable_info, mock_kb, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_find_consumable_items_no_kb(self):
        """Test _find_consumable_items_for_skill with no knowledge base."""
        actionable_info = {'required_items': []}
        
        self.action._find_consumable_items_for_skill(actionable_info, None, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_find_consumable_items_exception(self):
        """Test _find_consumable_items_for_skill with exception."""
        actionable_info = {'required_items': []}
        mock_kb = Mock()
        mock_kb.data = Mock(side_effect=Exception("Data error"))
        
        self.action._find_consumable_items_for_skill(actionable_info, mock_kb, 'mining')
        
        self.assertEqual(len(actionable_info['required_items']), 0)
    
    def test_analyze_actionable_sources_no_actions_suggested(self):
        """Test _analyze_actionable_sources when no actions are suggested."""
        xp_sources = [
            {'effect_name': 'unknown_effect', 'effect_value': 10, 'effect_description': 'Unknown effect'}
        ]
        
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'mining')
        
        # Should not add to actionable_sources if no suggested_actions
        self.assertEqual(len(result), 0)
    
    def test_analyze_actionable_sources_exception_in_loop(self):
        """Test _analyze_actionable_sources when exception occurs during loop iteration."""
        # Create a source that will cause an exception when processing
        xp_sources = [
            {'effect_name': 'crafting_xp', 'effect_value': 10, 'effect_description': 'Crafting XP'},
            Mock()  # This will cause exception when accessing .get() method
        ]
        
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        
        # Should handle exception and return partial results
        result = self.action._analyze_actionable_sources(xp_sources, mock_kb, 'mining')
        
        # Should process the first source successfully and handle the exception for the second
        self.assertEqual(len(result), 1)
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "FindXpSourcesAction()")


if __name__ == '__main__':
    unittest.main()