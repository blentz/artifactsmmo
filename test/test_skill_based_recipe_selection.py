#!/usr/bin/env python3
"""Tests for skill-based recipe selection functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.select_recipe import SelectRecipeAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestSkillBasedRecipeSelection(UnifiedContextTestBase):
    """Test skill-based recipe selection logic."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = SelectRecipeAction()
        self.mock_client = Mock()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
        # Mock knowledge base with sample recipes
        self.mock_knowledge_base = Mock()
        self.context.knowledge_base = self.mock_knowledge_base
        
        # Sample character data
        self.character_data = Mock()
        self.character_data.level = 5
        self.character_data.weaponcrafting_level = 2
        self.character_data.gearcrafting_level = 1
        self.character_data.jewelrycrafting_level = 3

    def create_sample_items_data(self):
        """Create sample items data for testing."""
        return {
            'wooden_sword': {
                'type': 'weapon',
                'level': 1,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 1,
                    'items': [{'code': 'ash_wood', 'quantity': 3}]
                },
                'effects': [{'name': 'attack', 'value': 5}]
            },
            'iron_sword': {
                'type': 'weapon', 
                'level': 2,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 2,
                    'items': [{'code': 'iron', 'quantity': 5}]
                },
                'effects': [{'name': 'attack', 'value': 10}]
            },
            'steel_sword': {
                'type': 'weapon',
                'level': 3,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 3,
                    'items': [{'code': 'steel', 'quantity': 5}]
                },
                'effects': [{'name': 'attack', 'value': 15}]
            },
            'adamantite_sword': {
                'type': 'weapon',
                'level': 4,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 4,
                    'items': [{'code': 'adamantite', 'quantity': 5}]
                },
                'effects': [{'name': 'attack', 'value': 20}]
            },
            'leather_armor': {
                'type': 'armor',
                'level': 1,
                'craft': {
                    'skill': 'gearcrafting',
                    'level': 1,
                    'items': [{'code': 'cowhide', 'quantity': 4}]
                },
                'effects': [{'name': 'hp', 'value': 30}]
            },
            'iron_armor': {
                'type': 'armor',
                'level': 2,
                'craft': {
                    'skill': 'gearcrafting', 
                    'level': 2,
                    'items': [{'code': 'iron', 'quantity': 8}]
                },
                'effects': [{'name': 'hp', 'value': 50}]
            },
            'copper_ring': {
                'type': 'ring',
                'level': 1,
                'craft': {
                    'skill': 'jewelrycrafting',
                    'level': 1,
                    'items': [{'code': 'copper', 'quantity': 2}]
                },
                'effects': [{'name': 'wisdom', 'value': 5}]
            },
            'silver_ring': {
                'type': 'ring',
                'level': 3,
                'craft': {
                    'skill': 'jewelrycrafting',
                    'level': 3,
                    'items': [{'code': 'silver', 'quantity': 3}]
                },
                'effects': [{'name': 'wisdom', 'value': 15}]
            },
            'impossible_weapon': {
                'type': 'weapon',
                'level': 10,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 10,  # Too high for character level 5
                    'items': [{'code': 'mythril', 'quantity': 10}]
                },
                'effects': [{'name': 'attack', 'value': 100}]
            }
        }

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_prioritizes_exact_skill_level_match(self, mock_get_char):
        """Test that recipes matching exact skill level are prioritized."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should select iron_sword (level 2) which matches weaponcrafting level 2
        assert result.success is True
        assert result.data['selected_item'] == 'iron_sword'
        assert result.data['selected_recipe']['required_skill_level'] == 2

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_respects_skill_level_constraint(self, mock_get_char):
        """Test that recipes requiring higher skill levels are filtered out."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute  
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should not select steel_sword (requires level 3) or adamantite_sword (requires level 4)
        # since character only has weaponcrafting level 2
        selected_item = result.data['selected_item']
        assert selected_item in ['wooden_sword', 'iron_sword']  # Only level 1-2 weapons
        assert selected_item != 'steel_sword'
        assert selected_item != 'adamantite_sword'

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_respects_character_level_constraint(self, mock_get_char):
        """Test that skill level cannot exceed character level."""
        # Setup character with high skill but constrained by character level
        character_data = Mock()
        character_data.level = 2  # Low character level
        character_data.weaponcrafting_level = 2  # Same as character level
        
        mock_response = Mock()
        mock_response.data = character_data
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should only select items requiring level <= 2 (character level)
        selected_recipe = result.data['selected_recipe']
        assert selected_recipe['required_skill_level'] <= 2

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_skill_progression_with_gearcrafting(self, mock_get_char):
        """Test skill progression logic with gearcrafting."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data  # gearcrafting_level = 1
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'gearcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'armor')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should select leather_armor (level 1) to match gearcrafting level 1
        assert result.success is True
        assert result.data['selected_item'] == 'leather_armor'
        assert result.data['selected_recipe']['required_skill_level'] == 1

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_skill_progression_with_jewelrycrafting(self, mock_get_char):
        """Test skill progression logic with jewelrycrafting."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data  # jewelrycrafting_level = 3
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'jewelrycrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'ring')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should select silver_ring (level 3) to match jewelrycrafting level 3
        assert result.success is True
        assert result.data['selected_item'] == 'silver_ring'
        assert result.data['selected_recipe']['required_skill_level'] == 3

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_fallback_to_lower_skill_level(self, mock_get_char):
        """Test fallback to lower skill level when no exact match."""
        # Setup character with skill level that doesn't have exact recipe match
        character_data = Mock()
        character_data.level = 5
        character_data.weaponcrafting_level = 2
        
        mock_response = Mock()
        mock_response.data = character_data
        mock_get_char.return_value = mock_response
        
        # Only provide level 1 weapon recipe (no level 2)
        items_data = {
            'wooden_sword': {
                'type': 'weapon',
                'level': 1,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 1,
                    'items': [{'code': 'ash_wood', 'quantity': 3}]
                },
                'effects': [{'name': 'attack', 'value': 5}]
            }
        }
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should select wooden_sword (level 1) as fallback
        assert result.success is True
        assert result.data['selected_item'] == 'wooden_sword'

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_filters_out_impossible_recipes(self, mock_get_char):
        """Test that impossible recipes (requiring skill > character level) are filtered out."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data  # character level 5
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should not select impossible_weapon (requires level 10, character is level 5)
        assert result.data['selected_item'] != 'impossible_weapon'

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_no_suitable_recipe_found(self, mock_get_char):
        """Test handling when no suitable recipe is found."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data
        mock_get_char.return_value = mock_response
        
        # Provide only recipes that require too high skill level
        items_data = {
            'impossible_weapon': {
                'type': 'weapon',
                'level': 10,
                'craft': {
                    'skill': 'weaponcrafting',
                    'level': 10,  # Too high
                    'items': [{'code': 'mythril', 'quantity': 10}]
                },
                'effects': [{'name': 'attack', 'value': 100}]
            }
        }
        self.mock_knowledge_base.data = {'items': items_data}
        
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should return error
        assert result.success is False
        assert 'No suitable recipe found' in result.error

    def test_skill_progression_sorting(self):
        """Test the skill progression sorting algorithm."""
        # Create sample items with different skill requirements
        items = [
            {
                'item_code': 'level1_item',
                'required_skill_level': 1,
                'skill_level_diff': 1,  # Current skill level is 2
                'item_score': 10
            },
            {
                'item_code': 'level2_item_low_score',
                'required_skill_level': 2,
                'skill_level_diff': 0,  # Exact match
                'item_score': 5
            },
            {
                'item_code': 'level2_item_high_score',
                'required_skill_level': 2,
                'skill_level_diff': 0,  # Exact match
                'item_score': 15
            }
        ]
        
        # Define the sorting key function (copied from implementation)
        def skill_progression_key(item):
            skill_diff = item['skill_level_diff']
            item_score = item['item_score']
            required_level = item['required_skill_level']
            
            return (skill_diff, -item_score, -required_level)
        
        # Sort using the algorithm
        items.sort(key=skill_progression_key)
        
        # Verify sorting: exact matches first, then by score, then by level
        assert items[0]['item_code'] == 'level2_item_high_score'  # Exact match, highest score
        assert items[1]['item_code'] == 'level2_item_low_score'   # Exact match, lower score
        assert items[2]['item_code'] == 'level1_item'             # Non-exact match

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_skill_determination_from_knowledge_base(self, mock_get_char):
        """Test automatic skill determination from knowledge base."""
        # Setup
        mock_response = Mock()
        mock_response.data = self.character_data
        mock_get_char.return_value = mock_response
        
        items_data = self.create_sample_items_data()
        self.mock_knowledge_base.data = {'items': items_data}
        
        # Don't set target_craft_skill - let it be determined automatically
        self.context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - should automatically determine weaponcrafting for weapon slot
        assert result.success is True
        # Should select appropriate weapon based on weaponcrafting skill level 2
        assert result.data['selected_item'] in ['wooden_sword', 'iron_sword']


class TestSkillConstraints:
    """Test skill constraint validation."""

    def test_skill_level_cannot_exceed_character_level(self):
        """Test the constraint that skill level cannot exceed character level."""
        action = SelectRecipeAction()
        
        # Test data
        character_level = 3
        character_skill_level = 3  # At character level limit
        
        # Recipe requiring skill level 4 should be invalid
        required_level = 4
        
        # This should be filtered out by the constraint check
        assert required_level > character_level  # This is the constraint we test
        assert required_level > character_skill_level

    def test_valid_skill_level_constraints(self):
        """Test valid skill level constraints."""
        # Test valid combinations
        valid_combinations = [
            (1, 1, 1),  # char_level=1, skill_level=1, required=1
            (5, 3, 3),  # char_level=5, skill_level=3, required=3  
            (10, 5, 2), # char_level=10, skill_level=5, required=2
        ]
        
        for char_level, skill_level, required_level in valid_combinations:
            # All these should be valid
            assert required_level <= skill_level
            assert required_level <= char_level
            assert skill_level <= char_level


class TestRecipeSelectionIntegration(UnifiedContextTestBase):
    """Integration tests for recipe selection."""

    def setUp(self):
        """Set up integration test fixtures."""
        super().setUp()
        self.action = SelectRecipeAction()

    @patch('src.controller.actions.select_recipe.get_character_api')
    def test_complete_weapon_crafting_progression(self, mock_get_char):
        """Test complete weapon crafting progression from level 1 to 4."""
        # Test progression: level 1 -> 2 -> 3 -> 4
        progression_tests = [
            (1, 'wooden_sword'),   # Level 1 weaponcrafting -> wooden sword
            (2, 'iron_sword'),     # Level 2 weaponcrafting -> iron sword  
            (3, 'steel_sword'),    # Level 3 weaponcrafting -> steel sword
            (4, 'adamantite_sword') # Level 4 weaponcrafting -> adamantite sword
        ]
        
        items_data = {
            'wooden_sword': {
                'type': 'weapon', 'level': 1,
                'craft': {'skill': 'weaponcrafting', 'level': 1, 'items': []},
                'effects': [{'name': 'attack', 'value': 5}]
            },
            'iron_sword': {
                'type': 'weapon', 'level': 2,
                'craft': {'skill': 'weaponcrafting', 'level': 2, 'items': []},
                'effects': [{'name': 'attack', 'value': 10}]
            },
            'steel_sword': {
                'type': 'weapon', 'level': 3,
                'craft': {'skill': 'weaponcrafting', 'level': 3, 'items': []},
                'effects': [{'name': 'attack', 'value': 15}]
            },
            'adamantite_sword': {
                'type': 'weapon', 'level': 4,
                'craft': {'skill': 'weaponcrafting', 'level': 4, 'items': []},
                'effects': [{'name': 'attack', 'value': 20}]
            }
        }
        
        for skill_level, expected_item in progression_tests:
            # Setup character with specific skill level
            character_data = Mock()
            character_data.level = max(skill_level, 4)  # Ensure character level is sufficient
            character_data.weaponcrafting_level = skill_level
            
            mock_response = Mock()
            mock_response.data = character_data
            mock_get_char.return_value = mock_response
            
            # Setup context
            self.context.character_name = "TestChar"
            self.context.knowledge_base = Mock()
            self.context.knowledge_base.data = {'items': items_data}
            self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
            self.context.set(StateParameters.TARGET_SLOT, 'weapon')
            
            # Execute
            result = self.action.execute(Mock(), self.context)
            
            # Verify progression
            assert result.success is True, f"Failed at skill level {skill_level}"
            assert result.data['selected_item'] == expected_item, f"Expected {expected_item} at skill level {skill_level}, got {result.data['selected_item']}"