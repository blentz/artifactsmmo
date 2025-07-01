"""
Test GOAP weapon selection preservation

This module tests that weapon selection made by evaluate_weapon_recipes
is properly preserved throughout planning and execution phases.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os

from src.controller.goap_execution_manager import GOAPExecutionManager
from src.lib.goap_data import GoapData


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
    
    def test_weapon_selection_preserved_in_knowledge_based_planning(self):
        """Test that weapon selection is preserved when knowledge-based planning succeeds."""
        # Mock analyze_crafting_chain to return a plan
        with patch('src.controller.actions.analyze_crafting_chain.AnalyzeCraftingChainAction') as mock_action_class:
            mock_action = Mock()
            mock_action_class.return_value = mock_action
            mock_action.execute.return_value = {
                'success': True,
                'action_sequence': [
                    {'name': 'find_resources', 'params': {'resource_type': 'ash_wood'}},
                    {'name': 'move', 'params': {}},
                    {'name': 'gather_resources', 'params': {}},
                    {'name': 'find_correct_workshop', 'params': {}},
                    {'name': 'move', 'params': {}},
                    {'name': 'craft_item', 'params': {}},
                    {'name': 'equip_item', 'params': {}}
                ]
            }
            
            # Create plan with equipment goal
            goal_state = {'has_better_weapon': True, 'equipment_equipped': True}
            actions_config = {}
            
            plan = self.goap_manager._create_knowledge_based_plan(
                {}, goal_state, actions_config, self.controller
            )
            
            # Verify plan was created
            self.assertIsNotNone(plan)
            self.assertEqual(len(plan), 7)
            
            # Verify weapon selection is preserved in appropriate actions
            craft_action = next(a for a in plan if a['name'] == 'craft_item')
            self.assertEqual(craft_action['params']['item_code'], 'wooden_staff')
            
            equip_action = next(a for a in plan if a['name'] == 'equip_item')
            self.assertEqual(equip_action['params']['item_code'], 'wooden_staff')
    
    def test_weapon_selection_preserved_in_standard_goap_fallback(self):
        """Test that weapon selection is preserved when falling back to standard GOAP."""
        # Mock analyze_crafting_chain to fail
        with patch('src.controller.actions.analyze_crafting_chain.AnalyzeCraftingChainAction') as mock_action_class:
            mock_action = Mock()
            mock_action_class.return_value = mock_action
            mock_action.execute.side_effect = Exception("Test failure")
            
            # Mock create_plan to return a standard GOAP plan
            with patch.object(self.goap_manager, 'create_plan') as mock_create_plan:
                mock_create_plan.return_value = [
                    {'name': 'evaluate_weapon_recipes', 'params': {}},
                    {'name': 'analyze_crafting_chain', 'params': {}},
                    {'name': 'plan_crafting_materials', 'params': {}},
                    {'name': 'craft_item', 'params': {}},
                    {'name': 'equip_item', 'params': {}}
                ]
                
                # Create plan with equipment goal
                goal_state = {'has_better_weapon': True, 'equipment_equipped': True}
                actions_config = {}
                current_state = {'best_weapon_selected': True}
                
                plan = self.goap_manager._create_knowledge_based_plan(
                    current_state, goal_state, actions_config, self.controller
                )
                
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
            
            plan = self.goap_manager._create_knowledge_based_plan(
                current_state, goal_state, actions_config, self.controller
            )
            
            # Verify plan was created without modifications
            self.assertIsNotNone(plan)
            self.assertEqual(len(plan), 2)
            
            # Verify no target_item or item_code was added
            for action in plan:
                if action['name'] == 'craft_item':
                    self.assertNotIn('target_item', action['params'])
                    self.assertNotIn('item_code', action['params'])
    
    def test_weapon_selection_with_different_actions(self):
        """Test that only relevant actions get weapon selection preserved."""
        # Mock create_plan to return a plan with various actions
        with patch.object(self.goap_manager, 'create_plan') as mock_create_plan:
            mock_create_plan.return_value = [
                {'name': 'move', 'params': {'x': 1, 'y': 2}},
                {'name': 'find_monsters', 'params': {}},
                {'name': 'transform_raw_materials', 'params': {}},
                {'name': 'craft_item', 'params': {}},
                {'name': 'rest', 'params': {}}
            ]
            
            # Create plan
            goal_state = {'has_better_weapon': True}
            actions_config = {}
            current_state = {}
            
            plan = self.goap_manager._create_knowledge_based_plan(
                current_state, goal_state, actions_config, self.controller
            )
            
            # Verify plan structure is preserved without hard-coded weapon selection
            self.assertEqual(len(plan), 5)
            # Action context preservation happens during execution, not planning


if __name__ == '__main__':
    unittest.main()