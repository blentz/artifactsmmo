"""Tests for EvaluateRecipesAction."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.controller.actions.evaluate_recipes import EvaluateRecipesAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.character.state import CharacterState
from test.test_base import UnifiedContextTestBase


class TestEvaluateRecipesAction(UnifiedContextTestBase):
    """Test the EvaluateRecipesAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = EvaluateRecipesAction()
        self.mock_client = Mock()
        
        # Create mock character state
        self.mock_character_state = Mock(spec=CharacterState)
        self.mock_character_state.data = {
            'level': 5,
            'skills': {'weaponcrafting': 3, 'gearcrafting': 2},
            'inventory': [
                {'code': 'copper', 'quantity': 10},
                {'code': 'ash_wood', 'quantity': 5}
            ],
            'equipment': {
                'weapon': {'code': 'stick', 'level': 1}
            }
        }
        
        # Use unified context and set character name
        self.mock_context = self.context  # Use the unified context
        self.mock_context.set(StateParameters.CHARACTER_NAME, "test_character")
        self.mock_context.character_state = self.mock_character_state
        
    def test_init(self):
        """Test action initialization."""
        action = EvaluateRecipesAction()
        self.assertIsInstance(action, EvaluateRecipesAction)
        self.assertIsNotNone(action.logger)
        
    def test_goap_parameters(self):
        """Test GOAP conditions and reactions."""
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('equipment_status', self.action.conditions)
        self.assertEqual(self.action.conditions['character_status']['alive'], True)
        self.assertEqual(self.action.conditions['equipment_status']['target_slot'], '!null')
        
        self.assertIn('equipment_status', self.action.reactions)
        self.assertEqual(self.action.reactions['equipment_status']['recipe_evaluated'], True)
        self.assertEqual(self.action.weight, 2.0)
        
    def test_slot_to_skill_mapping(self):
        """Test slot to skill mapping constants."""
        expected_mappings = {
            'weapon': 'weaponcrafting',
            'shield': 'weaponcrafting',
            'helmet': 'gearcrafting',
            'body_armor': 'gearcrafting',
            'leg_armor': 'gearcrafting',
            'boots': 'gearcrafting',
            'amulet': 'jewelrycrafting',
            'ring1': 'jewelrycrafting',
            'ring2': 'jewelrycrafting',
            'consumable': 'cooking',
            'potion': 'alchemy'
        }
        self.assertEqual(self.action.SLOT_TO_SKILL, expected_mappings)
        
    def test_slot_stat_priorities(self):
        """Test slot stat priorities constants."""
        # Check weapon priorities
        weapon_priorities = self.action.SLOT_STAT_PRIORITIES['weapon']
        self.assertEqual(weapon_priorities['attack_fire'], 3.0)
        self.assertEqual(weapon_priorities['dmg_fire'], 2.0)
        
        # Check helmet priorities
        helmet_priorities = self.action.SLOT_STAT_PRIORITIES['helmet']
        self.assertEqual(helmet_priorities['hp'], 3.0)
        self.assertEqual(helmet_priorities['res_fire'], 2.0)
        
    def test_validate_slot_skill_compatibility_exact_match(self):
        """Test slot-skill compatibility validation with exact match."""
        result = self.action._validate_slot_skill_compatibility('weapon', 'weaponcrafting')
        self.assertTrue(result)
        
    def test_validate_slot_skill_compatibility_cross_compatible(self):
        """Test slot-skill compatibility with cross-compatible skills."""
        result = self.action._validate_slot_skill_compatibility('shield', 'weaponcrafting')
        self.assertTrue(result)
        
        result = self.action._validate_slot_skill_compatibility('helmet', 'gearcrafting')
        self.assertTrue(result)
        
    def test_validate_slot_skill_compatibility_incompatible(self):
        """Test slot-skill compatibility with incompatible combination."""
        result = self.action._validate_slot_skill_compatibility('weapon', 'cooking')
        self.assertFalse(result)
        
    def test_get_current_equipment_no_data(self):
        """Test getting current equipment when no character data."""
        self.mock_character_state.data = None
        result = self.action._get_current_equipment(self.mock_character_state, 'weapon')
        self.assertIsNone(result)
        
    def test_get_current_equipment_no_equipment(self):
        """Test getting current equipment when no equipment data."""
        self.mock_character_state.data = {'level': 5}
        result = self.action._get_current_equipment(self.mock_character_state, 'weapon')
        self.assertIsNone(result)
        
    def test_get_current_equipment_normal_slot(self):
        """Test getting current equipment for normal slot."""
        result = self.action._get_current_equipment(self.mock_character_state, 'weapon')
        self.assertEqual(result, {'code': 'stick', 'level': 1})
        
    def test_get_current_equipment_ring_slot(self):
        """Test getting current equipment for ring slots."""
        self.mock_character_state.data['equipment']['ring'] = {'code': 'silver_ring', 'level': 2}
        
        result = self.action._get_current_equipment(self.mock_character_state, 'ring1')
        self.assertEqual(result, {'code': 'silver_ring', 'level': 2})
        
        result = self.action._get_current_equipment(self.mock_character_state, 'ring2')
        self.assertEqual(result, {'code': 'silver_ring', 'level': 2})
        
    def test_item_fits_slot_direct_match(self):
        """Test item slot fitting with direct match."""
        result = self.action._item_fits_slot('weapon', 'weapon')
        self.assertTrue(result)
        
    def test_item_fits_slot_ring_compatibility(self):
        """Test item slot fitting with ring compatibility."""
        result = self.action._item_fits_slot('ring', 'ring1')
        self.assertTrue(result)
        
        result = self.action._item_fits_slot('ring', 'ring2')
        self.assertTrue(result)
        
    def test_item_fits_slot_no_match(self):
        """Test item slot fitting with no match."""
        result = self.action._item_fits_slot('weapon', 'helmet')
        self.assertFalse(result)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_fetch_recipes_success(self, mock_get_items):
        """Test successful recipe fetching."""
        mock_response = Mock()
        mock_item = Mock()
        mock_item.craft = Mock()
        mock_item.craft.level = 2
        mock_material = Mock()
        mock_material.code = 'copper'
        mock_material.quantity = 5
        mock_item.craft.items = [mock_material]
        mock_item.to_dict.return_value = {'code': 'copper_dagger'}
        mock_response.data = [mock_item]
        mock_get_items.return_value = mock_response
        
        recipes = self.action._fetch_recipes('weaponcrafting', self.mock_character_state, self.mock_client)
        
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['item']['code'], 'copper_dagger')
        self.assertEqual(recipes[0]['level'], 2)
        self.assertEqual(len(recipes[0]['items']), 1)
        self.assertEqual(recipes[0]['items'][0]['code'], 'copper')
        self.assertEqual(recipes[0]['items'][0]['quantity'], 5)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_fetch_recipes_no_response(self, mock_get_items):
        """Test recipe fetching with no response."""
        mock_get_items.return_value = None
        
        recipes = self.action._fetch_recipes('weaponcrafting', self.mock_character_state, self.mock_client)
        
        self.assertEqual(len(recipes), 0)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_fetch_recipes_exception(self, mock_get_items):
        """Test recipe fetching with exception."""
        mock_get_items.side_effect = Exception("API error")
        
        recipes = self.action._fetch_recipes('weaponcrafting', self.mock_character_state, self.mock_client)
        
        self.assertEqual(len(recipes), 0)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_fetch_recipes_no_craft_items(self, mock_get_items):
        """Test recipe fetching with items that have no craft data."""
        mock_response = Mock()
        mock_item = Mock()
        mock_item.craft = None  # No crafting data
        mock_response.data = [mock_item]
        mock_get_items.return_value = mock_response
        
        recipes = self.action._fetch_recipes('weaponcrafting', self.mock_character_state, self.mock_client)
        
        self.assertEqual(len(recipes), 0)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_fetch_recipes_no_craft_level(self, mock_get_items):
        """Test recipe fetching with craft data but no level."""
        mock_response = Mock()
        mock_item = Mock()
        mock_item.craft = Mock()
        # Don't set level attribute
        del mock_item.craft.level
        mock_item.craft.items = []
        mock_item.to_dict.return_value = {'code': 'basic_item'}
        mock_response.data = [mock_item]
        mock_get_items.return_value = mock_response
        
        recipes = self.action._fetch_recipes('weaponcrafting', self.mock_character_state, self.mock_client)
        
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['level'], 1)  # Default level
        
    def test_evaluate_recipe_wrong_slot(self):
        """Test recipe evaluation with wrong item slot."""
        recipe = {
            'item': {'code': 'helmet', 'slot': 'helmet', 'level': 2},
            'level': 2,
            'items': []
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertEqual(score, 0)
        self.assertIn("doesn't match target slot", reasoning)
        
    def test_evaluate_recipe_starter_item_downgrade(self):
        """Test recipe evaluation rejecting starter items as downgrades."""
        recipe = {
            'item': {'code': 'stick', 'slot': 'weapon', 'level': 1},
            'level': 1,
            'items': []
        }
        current_item = {'code': 'copper_dagger', 'level': 3}
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, current_item, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertEqual(score, 0)
        self.assertIn("Starter item, not an upgrade", reasoning)
        
    def test_evaluate_recipe_too_high_level(self):
        """Test recipe evaluation with too high level item."""
        recipe = {
            'item': {'code': 'epic_sword', 'slot': 'weapon', 'level': 15},
            'level': 15,
            'items': []
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertEqual(score, 0)
        self.assertIn("Too high level", reasoning)
        
    def test_evaluate_recipe_too_low_level(self):
        """Test recipe evaluation with too low level item for high-level character."""
        # Set character to high level
        self.mock_character_state.data['level'] = 15
        
        recipe = {
            'item': {'code': 'stick', 'slot': 'weapon', 'level': 1},
            'level': 1,
            'items': []
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertEqual(score, 0)
        self.assertIn("Too low level", reasoning)
        
    def test_evaluate_recipe_low_level_character_exception(self):
        """Test recipe evaluation allows low level items for low level characters."""
        # Set character to low level
        self.mock_character_state.data['level'] = 3
        
        recipe = {
            'item': {'code': 'copper_dagger', 'slot': 'weapon', 'level': 2, 'effects': {'attack_fire': 10}},
            'level': 2,
            'items': [{'code': 'copper', 'quantity': 5}]
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertGreater(score, 0)  # Should be allowed
        
    def test_evaluate_recipe_insufficient_skill(self):
        """Test recipe evaluation with insufficient skill level."""
        recipe = {
            'item': {'code': 'iron_sword', 'slot': 'weapon', 'level': 3},
            'level': 10,  # Higher than character skill level (3)
            'items': []
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertEqual(score, 0)
        self.assertIn("Insufficient weaponcrafting level", reasoning)
        
    def test_evaluate_recipe_with_materials_available(self):
        """Test recipe evaluation with all materials available."""
        recipe = {
            'item': {'code': 'copper_dagger', 'slot': 'weapon', 'level': 2, 'effects': {'attack_fire': 10}},
            'level': 2,
            'items': [{'code': 'copper', 'quantity': 5}]
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertGreater(score, 0)
        self.assertIn("materials ready", reasoning)
        self.assertIn("100% materials in inventory", reasoning)
        
    def test_evaluate_recipe_with_missing_materials(self):
        """Test recipe evaluation with missing materials."""
        recipe = {
            'item': {'code': 'iron_sword', 'slot': 'weapon', 'level': 3, 'effects': {'attack_fire': 15}},
            'level': 3,
            'items': [{'code': 'iron', 'quantity': 10}]  # Character doesn't have iron
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertGreater(score, 0)  # Should still have some score but reduced
        self.assertIn("missing: iron", reasoning)
        self.assertIn("0% materials in inventory", reasoning)
        
    def test_evaluate_recipe_partial_materials(self):
        """Test recipe evaluation with partial materials available."""
        # Add some iron to inventory but not enough
        self.mock_character_state.data['inventory'].append({'code': 'iron', 'quantity': 3})
        
        recipe = {
            'item': {'code': 'iron_sword', 'slot': 'weapon', 'level': 3, 'effects': {'attack_fire': 15}},
            'level': 3,
            'items': [{'code': 'iron', 'quantity': 10}]
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertGreater(score, 0)
        self.assertIn("missing: iron (3/10)", reasoning)
        self.assertIn("30% materials in inventory", reasoning)
        
    def test_evaluate_recipe_no_materials_needed(self):
        """Test recipe evaluation with no materials needed."""
        recipe = {
            'item': {'code': 'magic_sword', 'slot': 'weapon', 'level': 3, 'effects': {'attack_fire': 20}},
            'level': 3,
            'items': []  # No materials needed
        }
        
        score, reasoning = self.action._evaluate_recipe(
            recipe, None, self.mock_character_state, 'weaponcrafting', 'weapon', self.mock_client
        )
        
        self.assertGreater(score, 0)
        
    def test_calculate_stat_improvement_no_current_item(self):
        """Test stat improvement calculation with no current item."""
        new_item = {'effects': {'attack_fire': 10}}
        stat_priorities = {'attack_fire': 3.0, 'dmg_fire': 2.0}
        
        improvement = self.action._calculate_stat_improvement(new_item, None, stat_priorities)
        
        self.assertEqual(improvement, 1.0)  # 100% improvement from nothing
        
    def test_calculate_stat_improvement_no_new_stats(self):
        """Test stat improvement calculation with no new stats."""
        new_item = {}
        current_item = {'effects': {'attack_fire': 5}}
        stat_priorities = {'attack_fire': 3.0}
        
        improvement = self.action._calculate_stat_improvement(new_item, current_item, stat_priorities)
        
        self.assertEqual(improvement, 0.0)
        
    def test_calculate_stat_improvement_upgrade(self):
        """Test stat improvement calculation with actual upgrade."""
        new_item = {'effects': {'attack_fire': 15, 'dmg_fire': 8}}
        current_item = {'effects': {'attack_fire': 10, 'dmg_fire': 5}}
        stat_priorities = {'attack_fire': 3.0, 'dmg_fire': 2.0}
        
        improvement = self.action._calculate_stat_improvement(new_item, current_item, stat_priorities)
        
        self.assertGreater(improvement, 0.0)
        # Should weight attack_fire improvements more than dmg_fire
        
    def test_calculate_stat_improvement_from_zero(self):
        """Test stat improvement calculation from zero stats."""
        new_item = {'effects': {'attack_fire': 10}}
        current_item = {'effects': {'dmg_fire': 5}}  # No attack_fire
        stat_priorities = {'attack_fire': 3.0}
        
        improvement = self.action._calculate_stat_improvement(new_item, current_item, stat_priorities)
        
        self.assertEqual(improvement, 1.0)  # 100% improvement from 0
        
    def test_calculate_stat_improvement_no_priority_stats(self):
        """Test stat improvement calculation with no priority stat improvements."""
        new_item = {'effects': {'wisdom': 5}}
        current_item = {'effects': {'attack_fire': 10}}
        stat_priorities = {'attack_fire': 3.0, 'dmg_fire': 2.0}
        
        improvement = self.action._calculate_stat_improvement(new_item, current_item, stat_priorities)
        
        self.assertEqual(improvement, 0.0)
        
    def test_execute_integration_no_target_slot(self):
        """Test execute integration with no target slot."""
        # Don't set EQUIPMENT_TARGET_SLOT parameter - should be None by default
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('No target equipment slot specified', result.error)
        
    def test_execute_integration_no_character_state(self):
        """Test execute integration with no character state."""
        self.mock_context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        self.mock_context.character_state = None
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('No character state available', result.error)
        
    def test_execute_integration_unknown_slot(self):
        """Test execute integration with unknown equipment slot."""
        self.mock_context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'unknown_slot')
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('Unknown equipment slot: unknown_slot', result.error)
        
    def test_execute_integration_incompatible_slot_skill(self):
        """Test execute integration with incompatible slot and skill."""
        self.mock_context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        self.mock_context.set(StateParameters.TARGET_CRAFT_SKILL, 'cooking')
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn("not compatible with skill 'cooking'", result.error)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_execute_integration_no_recipes(self, mock_get_items):
        """Test execute integration when no recipes available."""
        self.mock_context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        mock_get_items.return_value = None
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('No weaponcrafting recipes available', result.error)
        
    @patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync')
    def test_execute_integration_successful_selection(self, mock_get_items):
        """Test execute integration with successful recipe selection."""
        self.mock_context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        
        # Mock API response with craftable recipe
        mock_response = Mock()
        mock_item = Mock()
        mock_item.craft = Mock()
        mock_item.craft.level = 2
        mock_material = Mock()
        mock_material.code = 'copper'
        mock_material.quantity = 5
        mock_item.craft.items = [mock_material]
        mock_item.to_dict.return_value = {
            'code': 'copper_dagger',
            'level': 2,
            'slot': 'weapon',
            'effects': {'attack_fire': 10}
        }
        mock_response.data = [mock_item]
        mock_get_items.return_value = mock_response
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['selected_item'], 'copper_dagger')
        self.assertEqual(result.data['target_slot'], 'weapon')
        self.assertEqual(result.data['craft_skill'], 'weaponcrafting')
        
        # Verify context updates
        self.assertTrue(result.success)
        self.assertEqual(result.data['selected_item'], 'copper_dagger')
        self.assertEqual(result.data['target_slot'], 'weapon')
        self.assertEqual(result.data['craft_skill'], 'weaponcrafting')
        
    def test_repr_method(self):
        """Test string representation of the action."""
        result = repr(self.action)
        self.assertIn('EvaluateRecipesAction', result)


if __name__ == '__main__':
    unittest.main()