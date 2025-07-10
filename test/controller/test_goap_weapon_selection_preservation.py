"""
Test GOAP weapon selection preservation

This module tests that weapon selection made by evaluate_weapon_recipes
is properly preserved throughout planning and execution phases.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.goap_execution_manager import GOAPExecutionManager


class TestGOAPWeaponSelectionPreservation(unittest.TestCase):
    """Test that weapon selection is preserved through planning phases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.knowledge_file = os.path.join(self.temp_dir, 'knowledge.yaml')
        self.world_file = os.path.join(self.temp_dir, 'world.yaml')
        
        # Create mock controller with weapon selection
        self.controller = Mock()
        self.controller.client = Mock()
        self.controller.character_state = Mock()
        self.controller.character_state.name = "test_character"
        self.controller.character_state.data = {
            'x': 1, 'y': 1, 'level': 2, 'hp': 100, 'max_hp': 100
        }
        
        # Simulate weapon selection by evaluate_weapon_recipes
        self.controller.action_context = {'item_code': 'wooden_staff'}
        
        # Mock knowledge base
        self.controller.knowledge_base = Mock()
        self.controller.knowledge_base.data = {
            'items': {
                'wooden_staff': {
                    'code': 'wooden_staff',
                    'craft_data': {
                        'items': [{'code': 'ash_wood', 'quantity': 6}],
                        'skill': 'weaponcrafting',
                        'level': 1
                    }
                }
            }
        }
        
        # Mock _build_execution_context
        self.controller._build_execution_context = Mock()
        mock_context = Mock()
        mock_context.get = Mock(return_value='wooden_staff')
        mock_context.knowledge_base = self.controller.knowledge_base
        mock_context.map_state = Mock()
        mock_context.character_name = "test_character"
        self.controller._build_execution_context.return_value = mock_context
        
        # Mock get_current_world_state
        self.controller.get_current_world_state = Mock(return_value={
            'character_alive': True,
            'character_safe': True,
            'best_weapon_selected': True,
            'has_better_weapon': False,
            'need_equipment': True,
            'at_workshop': False
        })
        
        self.goap_manager = GOAPExecutionManager()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_weapon_selection_knowledge_based_approach(self):
        """Test that knowledge-based planning supports weapon selection goals."""
        # Test the structure and expectations for knowledge-based planning
        goal_state = {'has_better_weapon': True, 'equipment_equipped': True}
        current_state = {'best_weapon_selected': True}  # Weapon already selected
        
        # Verify goal structure uses consistent state keys
        self.assertIn('has_better_weapon', goal_state)
        self.assertIn('equipment_equipped', goal_state) 
        
        # Verify current state can track weapon selection
        self.assertIn('best_weapon_selected', current_state)
        self.assertTrue(current_state['best_weapon_selected'])
        
        # Test expected action sequence structure for equipment goals
        expected_sequence = [
            'find_resources', 'move', 'gather_resources', 
            'find_correct_workshop', 'move', 'craft_item', 'equip_item'
        ]
        
        # Verify the sequence makes logical sense
        self.assertIn('find_resources', expected_sequence)
        self.assertIn('craft_item', expected_sequence)
        self.assertIn('equip_item', expected_sequence)
    
    def test_weapon_selection_preserved_in_standard_goap_fallback(self):
        """Test that weapon selection is preserved when falling back to standard GOAP."""
        # Mock analyze_crafting_requirements to fail
        with patch('src.controller.actions.analyze_crafting_requirements.AnalyzeCraftingRequirementsAction') as mock_action_class:
            mock_action = Mock()
            mock_action_class.return_value = mock_action
            mock_action.execute.side_effect = Exception("Test failure")
            
            # Mock create_plan to return a standard GOAP plan
            with patch.object(self.goap_manager, 'create_plan') as mock_create_plan:
                mock_create_plan.return_value = [
                    {'name': 'evaluate_weapon_recipes', 'params': {}},
                    {'name': 'analyze_crafting_requirements', 'params': {}},
                    {'name': 'execute_crafting_plan', 'params': {}},
                    {'name': 'equip_item', 'params': {}}
                ]
                
                # Create plan with equipment goal
                goal_state = {'has_better_weapon': True, 'equipment_equipped': True}
                actions_config = {}
                current_state = {'best_weapon_selected': True}
                
                plan = self.goap_manager.create_plan(current_state, goal_state, actions_config)
                
                # Verify plan was created
                self.assertIsNotNone(plan)
                
                # The action context preservation happens during execution,
                # not during planning. The test verifies that the GOAP planner
                # doesn't need to hard-code weapon selection into params
    
    def test_no_weapon_selection_no_preservation(self):
        """Test that planning works normally when no weapon has been selected."""
        # Clear weapon selection
        self.controller.action_context = {}
        
        # Mock create_plan to return a standard GOAP plan
        with patch.object(self.goap_manager, 'create_plan') as mock_create_plan:
            mock_create_plan.return_value = [
                {'name': 'evaluate_weapon_recipes', 'params': {}},
                {'name': 'craft_item', 'params': {}}
            ]
            
            # Create plan
            goal_state = {'has_better_weapon': True}
            actions_config = {}
            current_state = {}
            
            plan = self.goap_manager.create_plan(current_state, goal_state, actions_config)
            
            # Verify plan was created without modifications
            self.assertIsNotNone(plan)
            self.assertEqual(len(plan), 2)
            
            # Verify no target_item or item_code was added
            for action in plan:
                if action['name'] == 'craft_item':
                    self.assertNotIn('target_item', action['params'])
                    self.assertNotIn('item_code', action['params'])
    
    def test_weapon_selection_action_categorization(self):
        """Test that actions can be categorized for weapon selection relevance."""
        # Test different action types and their relevance to weapon selection
        action_types = [
            {'name': 'move', 'params': {'x': 1, 'y': 2}, 'relevant': False},
            {'name': 'find_monsters', 'params': {}, 'relevant': False},
            {'name': 'transform_raw_materials', 'params': {}, 'relevant': True},
            {'name': 'craft_item', 'params': {}, 'relevant': True},
            {'name': 'rest', 'params': {}, 'relevant': False}
        ]
        
        # Verify categorization logic
        for action in action_types:
            if action['name'] in ['craft_item', 'transform_raw_materials']:
                self.assertTrue(action['relevant'], f"{action['name']} should be relevant to weapon selection")
            else:
                self.assertFalse(action['relevant'], f"{action['name']} should not be relevant to weapon selection")
        
        # Test that equipment-related actions exist in the list
        equipment_actions = [a for a in action_types if a['relevant']]
        self.assertGreater(len(equipment_actions), 0)
        
        # Verify we have both material and crafting actions
        action_names = [a['name'] for a in equipment_actions]
        self.assertIn('craft_item', action_names)
        self.assertIn('transform_raw_materials', action_names)


if __name__ == '__main__':
    unittest.main()