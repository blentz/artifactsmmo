"""
Test world state merging to ensure all persisted states are included
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.world.state import WorldState
from test.test_base import UnifiedContextTestBase


class TestWorldStateMerging(UnifiedContextTestBase):
    """Test that world state merging includes all persisted states"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch the DATA_PREFIX to use temp directory
        self.data_prefix_patcher = patch('src.controller.world.state.DATA_PREFIX', self.temp_dir)
        self.data_prefix_patcher.start()
        
        # Create controller instance
        self.controller = AIPlayerController()
        
        # Create mock character state
        self.mock_char_state = Mock()
        self.mock_char_state.data = {
            'level': 1,
            'hp': 100,
            'max_hp': 100
        }
        
        # Create mock map state
        self.mock_map_state = Mock()
        
        # Create mock knowledge base
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {}
        
        # Set states
        self.controller.character_state = self.mock_char_state
        self.controller.map_state = self.mock_map_state
        self.controller.knowledge_base = self.mock_knowledge_base
        
        # Create world state with various persisted data
        self.controller.world_state = WorldState('test_world')
        self.controller.world_state.data = {
            # Critical states that were being missed
            'inventory_updated': True,
            'materials_sufficient': True,
            'craft_plan_available': True,
            'has_equipment': False,
            'need_specific_workshop': True,
            'workshop_location_known': True,
            'at_correct_workshop': False,
            
            # Other persisted states
            'best_weapon_selected': True,
            'equipment_info_known': True,
            'recipe_known': True,
            'craftable_weapon_identified': True,
            'resource_availability': {'monsters': False},
            'location_context': {'at_target': False},
            'monster_present': False,
            'goal_progress': {'monsters_hunted': 5},
        }
        
    def tearDown(self):
        """Clean up after tests"""
        self.data_prefix_patcher.stop()
        
    def test_all_persisted_states_are_merged(self):
        """Test that all persisted world states are included in get_current_world_state"""
        # Mock the goal manager's calculate_world_state to return minimal state
        with patch.object(self.controller.goal_manager, 'calculate_world_state') as mock_calc:
            mock_calc.return_value = {
                'character_status': {
                    'alive': True,
                    'safe': True,
                    'cooldown_active': False
                },
                'combat_context': {'status': 'ready'}
            }
            
            # Get current world state
            world_state = self.controller.get_current_world_state()
            
            # Verify all persisted states are present
            self.assertTrue(world_state.get('inventory_updated'))
            self.assertTrue(world_state.get('materials_sufficient'))
            self.assertTrue(world_state.get('craft_plan_available'))
            self.assertFalse(world_state.get('has_equipment'))
            self.assertTrue(world_state.get('need_specific_workshop'))
            self.assertTrue(world_state.get('workshop_location_known'))
            self.assertFalse(world_state.get('at_correct_workshop'))
            
            # Verify other states
            self.assertTrue(world_state.get('best_weapon_selected'))
            self.assertTrue(world_state.get('equipment_info_known'))
            self.assertTrue(world_state.get('recipe_known'))
            self.assertTrue(world_state.get('craftable_weapon_identified'))
            
            # Verify calculated states are present in consolidated format
            self.assertIn('character_status', world_state)
            self.assertTrue(world_state['character_status'].get('alive'))
            self.assertTrue(world_state['character_status'].get('safe'))
            self.assertFalse(world_state['character_status'].get('cooldown_active'))
            
    def test_persisted_states_override_calculated_states(self):
        """Test that persisted states take precedence over calculated states for nested dicts"""
        # Add conflicting state to persisted data
        self.controller.world_state.data['character_status'] = {
            'alive': False,
            'safe': False,
            'cooldown_active': True
        }
        
        # Mock the goal manager to return conflicting values
        with patch.object(self.controller.goal_manager, 'calculate_world_state') as mock_calc:
            mock_calc.return_value = {
                'character_status': {
                    'alive': True,  # Will be overridden by persisted False
                    'safe': True,   # Will be overridden by persisted False
                    'cooldown_active': False  # Will be overridden by persisted True
                }
            }
            
            # Get current world state
            world_state = self.controller.get_current_world_state()
            
            # Verify persisted states override calculated ones for nested dicts
            self.assertFalse(world_state.get('character_status', {}).get('alive'))
            self.assertTrue(world_state.get('character_status', {}).get('cooldown_active'))
            
            # Verify persisted states are still included for non-conflicting keys
            self.assertTrue(world_state.get('inventory_updated'))
            self.assertTrue(world_state.get('materials_sufficient'))
            
    def test_empty_persisted_state_handling(self):
        """Test that empty or missing persisted state is handled gracefully"""
        # Test with empty data
        self.controller.world_state.data = {}
        
        with patch.object(self.controller.goal_manager, 'calculate_world_state') as mock_calc:
            mock_calc.return_value = {
                'character_status': {
                    'alive': True,
                    'safe': True
                }
            }
            
            # Should not raise an exception
            world_state = self.controller.get_current_world_state()
            
            # Should have calculated states in consolidated format
            self.assertTrue(world_state.get('character_status', {}).get('alive'))
            self.assertTrue(world_state.get('character_status', {}).get('safe'))
            # Check that we have the expected consolidated state groups
            self.assertIn('character_status', world_state)
            
        # Test with None world_state
        self.controller.world_state = None
        
        # Should not raise an exception
        world_state = self.controller.get_current_world_state()
        
        # Should only have calculated states (now in consolidated format)
        self.assertTrue(world_state['character_status']['alive'])
        self.assertTrue(world_state['character_status']['safe'])


if __name__ == '__main__':
    unittest.main()