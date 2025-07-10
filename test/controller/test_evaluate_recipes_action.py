"""
Tests for the general-purpose EvaluateRecipesAction
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.evaluate_recipes import EvaluateRecipesAction
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestEvaluateRecipesAction(UnifiedContextTestBase):
    """Test suite for general-purpose recipe evaluation action"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create action instance
        self.action = EvaluateRecipesAction()
        
        # Create mock states
        self.character_state = Mock(spec=CharacterState)
        self.map_state = Mock(spec=MapState)
        self.context.character_state = self.character_state
        self.context.map_state = self.map_state
        self.mock_client = Mock()
        
        # Mock character data
        self.character_state.data = {
            'level': 5,
            'equipment': {
                'weapon': {
                    'code': 'wooden_stick',
                    'level': 1,
                    'effects': {'attack_fire': 10}
                }
            },
            'inventory': [
                {'code': 'ash_wood', 'quantity': 10},
                {'code': 'copper_ore', 'quantity': 5}
            ],
            'skills': {
                'weaponcrafting': 3,
                'gearcrafting': 2,
                'jewelrycrafting': 1
            }
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Base class handles context cleanup
        super().tearDown()
        
    def test_weapon_slot_evaluation(self):
        """Test evaluating recipes for weapon slot"""
        # Set target slot
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response
        mock_response = Mock()
        mock_response.data = [
            self._create_mock_item('wooden_staff', 3, 'weaponcrafting', 
                                 [{'code': 'wooden_stick', 'quantity': 1}, 
                                  {'code': 'ash_wood', 'quantity': 5}],
                                 {'attack_fire': 25})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertTrue(result.success)
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'wooden_staff')
            self.assertEqual(self.context.get(StateParameters.TARGET_SLOT), 'weapon')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_CRAFT_SKILL), 'weaponcrafting')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_WORKSHOP_TYPE), 'weaponcrafting_workshop')
            
    def test_armor_slot_evaluation(self):
        """Test evaluating recipes for armor slot"""
        # Set target slot
        self.context.set(StateParameters.TARGET_SLOT, 'body_armor')
        
        # Mock API response
        mock_response = Mock()
        mock_response.data = [
            self._create_mock_item('copper_armor', 2, 'gearcrafting',
                                 [{'code': 'copper_ore', 'quantity': 5}],
                                 {'hp': 50, 'res_fire': 10})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            if not result.success:
                print(f"Armor test failed with error: {result.error}")
            self.assertTrue(result.success)
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'copper_armor')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_CRAFT_SKILL), 'gearcrafting')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_WORKSHOP_TYPE), 'gearcrafting_workshop')
            
    def test_jewelry_slot_evaluation(self):
        """Test evaluating recipes for jewelry slot"""
        # Set target slot
        self.context.set(StateParameters.TARGET_SLOT, 'ring1')
        
        # Mock character with jewelry materials  
        self.character_state.data['inventory'].append({'code': 'copper_ore', 'quantity': 3})
        
        # Mock API response
        mock_response = Mock()
        mock_response.data = [
            self._create_mock_item('copper_ring', 1, 'jewelrycrafting',
                                 [{'code': 'copper_ore', 'quantity': 2}],
                                 {'critical_strike': 5})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            if not result.success:
                print(f"Jewelry test failed with error: {result.error}")
                print(f"Target slot: {self.context.get(StateParameters.TARGET_SLOT)}")
            self.assertTrue(result.success)
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'copper_ring')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_CRAFT_SKILL), 'jewelrycrafting')
            self.assertEqual(self.context.get(StateParameters.REQUIRED_WORKSHOP_TYPE), 'jewelrycrafting_workshop')
            
    def test_no_target_slot_fails(self):
        """Test that missing target slot causes failure"""
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        
    def test_unknown_slot_fails(self):
        """Test that unknown equipment slot causes failure"""
        self.context.set(StateParameters.TARGET_SLOT, 'unknown_slot')
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        
    def test_no_craftable_recipes_fails(self):
        """Test that no craftable recipes causes failure"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response with no recipes
        mock_response = Mock()
        mock_response.data = []
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result.success)
            
    def test_insufficient_skill_level_filters_out(self):
        """Test that recipes requiring too high skill level are filtered out"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response with high-level recipe
        mock_response = Mock()
        mock_response.data = [
            self._create_mock_item('iron_sword', 10, 'weaponcrafting',  # Requires level 10
                                 [{'code': 'iron', 'quantity': 5}],
                                 {'attack_fire': 100})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result.success)  # No craftable recipes after filtering
            
    def test_material_availability_scoring(self):
        """Test that recipes with available materials score higher"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response with two recipes
        mock_response = Mock()
        mock_response.data = [
            # Recipe with available materials
            self._create_mock_item('wooden_staff', 3, 'weaponcrafting',
                                 [{'code': 'ash_wood', 'quantity': 5}],  # We have 10
                                 {'attack_fire': 25}),
            # Recipe with unavailable materials  
            self._create_mock_item('copper_sword', 3, 'weaponcrafting',
                                 [{'code': 'copper', 'quantity': 10}],  # We don't have this
                                 {'attack_fire': 30})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertTrue(result.success)
            # Should select the one with available materials
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'wooden_staff')
            
    def test_stat_improvement_scoring(self):
        """Test that recipes with better stats score higher"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response with recipes having different stats
        mock_response = Mock()
        mock_response.data = [
            # Better stats
            self._create_mock_item('ash_staff', 3, 'weaponcrafting',
                                 [{'code': 'ash_wood', 'quantity': 3}],
                                 {'attack_fire': 30}),  # Better than current weapon
            # Same stats as current weapon
            self._create_mock_item('wooden_staff', 3, 'weaponcrafting',
                                 [{'code': 'ash_wood', 'quantity': 5}],
                                 {'attack_fire': 10})   # Same as current weapon
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertTrue(result.success)
            # Should select the one with better stats
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'ash_staff')
            
    def test_level_appropriateness_filtering(self):
        """Test that recipes too high level or too low level are filtered out"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Mock API response with inappropriate level recipes
        mock_response = Mock()
        mock_response.data = [
            # Too high level (character is level 5, level range is 3, so max is 8)
            self._create_mock_item('master_sword', 15, 'weaponcrafting',
                                 [{'code': 'ash_wood', 'quantity': 1}],
                                 {'attack_fire': 200}),
            # Too low level (min would be level 2, so level 1 is too low)
            self._create_mock_item('stick', 0, 'weaponcrafting',
                                 [{'code': 'ash_wood', 'quantity': 1}],
                                 {'attack_fire': 5})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result.success)  # All recipes filtered out
            
    def test_no_current_equipment_handles_gracefully(self):
        """Test that missing current equipment is handled gracefully"""
        self.context.set(StateParameters.TARGET_SLOT, 'helmet')
        
        # Remove current equipment
        self.character_state.data['equipment'] = {}
        
        # Mock API response
        mock_response = Mock()
        mock_response.data = [
            self._create_mock_item('copper_helmet', 2, 'gearcrafting',
                                 [{'code': 'copper_ore', 'quantity': 3}],
                                 {'hp': 20, 'res_fire': 5})
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertTrue(result.success)
            self.assertEqual(self.context.get(StateParameters.TARGET_ITEM), 'copper_helmet')
            
    def test_api_error_handling(self):
        """Test that API errors are handled gracefully"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
            mock_get_items.side_effect = Exception("API Error")
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result.success)
            
    def test_no_api_client_fails(self):
        """Test that missing API client causes failure"""
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        result = self.action.execute(None, self.context)
        
        self.assertFalse(result.success)
        
    def _create_mock_item(self, item_code: str, item_level: int, craft_skill: str, 
                         required_items: list, effects: dict, item_slot: str = None):
        """Helper method to create mock item with craft information"""
        # Infer slot from item name if not provided
        if item_slot is None:
            if 'sword' in item_code or 'staff' in item_code or 'stick' in item_code:
                item_slot = 'weapon'
            elif 'shield' in item_code:
                item_slot = 'shield'
            elif 'helmet' in item_code:
                item_slot = 'helmet'
            elif 'armor' in item_code:
                item_slot = 'body_armor'
            elif 'ring' in item_code:
                item_slot = 'ring'
            elif 'amulet' in item_code:
                item_slot = 'amulet'
            else:
                item_slot = 'weapon'  # Default fallback
        
        mock_item = Mock()
        mock_item.code = item_code
        mock_item.to_dict.return_value = {
            'code': item_code,
            'level': item_level,
            'slot': item_slot,
            'effects': effects
        }
        
        # Mock craft information
        mock_craft = Mock()
        mock_craft.level = item_level
        mock_craft.skill = craft_skill
        mock_craft.items = []
        
        for req_item in required_items:
            mock_craft_item = Mock()
            mock_craft_item.code = req_item['code']
            mock_craft_item.quantity = req_item['quantity']
            mock_craft.items.append(mock_craft_item)
            
        mock_item.craft = mock_craft
        
        return mock_item


if __name__ == '__main__':
    unittest.main()