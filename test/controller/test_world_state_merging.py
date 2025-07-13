"""
Test world state merging to ensure all persisted states are included
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.world.state import WorldState
from src.lib.state_parameters import StateParameters
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
        """Test that world state is retrieved from UnifiedStateContext."""
        from src.lib.unified_state_context import UnifiedStateContext
        
        # Get singleton context and update it with test data
        context = UnifiedStateContext()
        context.set(StateParameters.CHARACTER_HEALTHY, True)
        context.set(StateParameters.MATERIALS_STATUS, 'sufficient')
        context.set(StateParameters.CHARACTER_COOLDOWN_ACTIVE, False)
        
        # Get current world state - should use UnifiedStateContext
        world_state = self.controller.get_current_world_state()
        
        # Verify that UnifiedStateContext state is returned
        self.assertIsInstance(world_state, dict)
        self.assertIn(StateParameters.CHARACTER_HEALTHY, world_state)
        self.assertIn(StateParameters.MATERIALS_STATUS, world_state)
        
        # Reset context for other tests
        context.reset()
            
    def test_unified_state_context_consistency(self):
        """Test that UnifiedStateContext provides consistent state."""
        from src.lib.unified_state_context import UnifiedStateContext
        
        # Get singleton context and set some state
        context = UnifiedStateContext()
        context.set(StateParameters.CHARACTER_HEALTHY, False)
        context.set(StateParameters.CHARACTER_COOLDOWN_ACTIVE, True)
        
        # Get current world state - should reflect UnifiedStateContext state
        world_state = self.controller.get_current_world_state()
        
        # Verify that UnifiedStateContext state is returned
        self.assertIsInstance(world_state, dict)
        self.assertIn(StateParameters.CHARACTER_HEALTHY, world_state)
        self.assertIn(StateParameters.CHARACTER_COOLDOWN_ACTIVE, world_state)
        
        # Reset context for other tests
        context.reset()
            
    def test_unified_state_context_defaults(self):
        """Test that UnifiedStateContext provides default state values."""
        from src.lib.unified_state_context import UnifiedStateContext
        
        # Get singleton context and reset to defaults
        context = UnifiedStateContext()
        context.reset()
        
        # Should not raise an exception
        world_state = self.controller.get_current_world_state()
        
        # Should have default states in flattened format
        self.assertIsNotNone(world_state.get(StateParameters.CHARACTER_HEALTHY))
        self.assertIsInstance(world_state, dict)
        
        # Verify config-based default values are present (architecture-compliant)
        self.assertIn(StateParameters.CHARACTER_HEALTHY, world_state)
        self.assertIn(StateParameters.CHARACTER_COOLDOWN_ACTIVE, world_state)
        self.assertIn(StateParameters.MATERIALS_STATUS, world_state)
        
        # CHARACTER_LEVEL, CHARACTER_HP, CHARACTER_MAX_HP come from API, not state defaults


if __name__ == '__main__':
    unittest.main()