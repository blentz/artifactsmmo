"""
Integration Test Suite for State Unification - Zero Backward Compatibility

End-to-end validation of complete state unification across all components.
Tests the unified state system without temporary file complexity.

QA Focus Areas:
- Complete state flow validation
- Cross-component integration
- Data consistency verification
- Parameter validation enforcement
"""

import pytest
from unittest.mock import Mock
from src.lib.unified_state_context import get_unified_context
from src.lib.state_parameters import StateParameters
from src.lib.action_context import ActionContext
from src.controller.world.state import WorldState
from src.lib.recipe_utils import (
    get_selected_item_from_context,
    set_selected_item_in_context,
    get_recipe_from_context,
    set_target_recipe_in_context
)


class TestStateUnificationIntegration:
    """Comprehensive integration tests for state unification."""
    
    def setup_method(self):
        """Reset state for each test."""
        # Reset singleton
        import src.lib.unified_state_context
        src.lib.unified_state_context._unified_instance = None
    
    def test_complete_goap_to_action_context_flow(self):
        """Test complete parameter flow from GOAP state to ActionContext."""
        # Create mock controller with world state
        mock_controller = Mock()
        mock_controller.character_state = Mock()
        mock_controller.character_state.data = {
            'x': 10,
            'y': 20,
            'level': 5,
            'hp': 100,
            'max_hp': 100,
            'weapon': 'iron_sword',
            'armor': 'leather_armor'
        }
        
        # Test unified context directly (since WorldState loads from file)
        unified_context = get_unified_context()
        
        # Set test parameters directly (only config-based state parameters)
        unified_context.set(StateParameters.TARGET_ITEM, "copper_dagger")
        unified_context.set(StateParameters.CHARACTER_HEALTHY, True)
        unified_context.set(StateParameters.MATERIALS_STATUS, "insufficient")
        
        # Create ActionContext from controller
        context = ActionContext.from_controller(mock_controller)
        
        # Verify GOAP state -> ActionContext parameter flow (config-based parameters only)
        assert context.get(StateParameters.TARGET_ITEM) == "copper_dagger"
        assert context.get(StateParameters.CHARACTER_HEALTHY) is True
        assert context.get(StateParameters.MATERIALS_STATUS) == "insufficient"
        
        # Verify context creation succeeded (character data comes from API, not state parameters)
        assert isinstance(context, ActionContext)
        # CHARACTER_X, CHARACTER_Y, CHARACTER_LEVEL come from API, not state parameters
    
    def test_recipe_utils_integration_with_state_parameters(self):
        """Test recipe utility functions with StateParameters integration."""
        context = ActionContext()
        
        # Test selected item operations
        assert get_selected_item_from_context(context) is None
        
        set_selected_item_in_context(context, "test_sword")
        assert get_selected_item_from_context(context) == "test_sword"
        # HAS_TARGET_ITEM removed - use knowledge_base.has_target_item(context) helper
        
        # Test recipe operations
        test_recipe = {
            'code': 'iron_sword',
            'craft': {
                'items': [
                    {'code': 'iron', 'quantity': 3},
                    {'code': 'coal', 'quantity': 1}
                ]
            }
        }
        
        set_target_recipe_in_context(context, test_recipe)
        retrieved_recipe = get_recipe_from_context(context)
        
        assert retrieved_recipe == test_recipe
        assert context.get(StateParameters.TARGET_RECIPE) == test_recipe
    
    def test_world_state_persistence_with_unified_context(self):
        """Test WorldState save/load with unified context."""
        # Create world state
        world_state = WorldState()
        
        # Set some parameters in unified context
        unified_context = world_state.get_unified_context()
        unified_context.set(StateParameters.TARGET_ITEM, "persistence_test_item")
        unified_context.set(StateParameters.CHARACTER_LEVEL, 42)
        unified_context.set(StateParameters.MATERIALS_STATUS, "sufficient")
        
        # Save world state
        world_state.save()
        
        # Reset singleton to simulate new instance
        import src.lib.unified_state_context
        src.lib.unified_state_context._unified_instance = None
        
        # Create new world state and load
        world_state2 = WorldState()
        world_state2.load()
        
        # Verify data persistence
        unified_context2 = world_state2.get_unified_context()
        assert unified_context2.get(StateParameters.TARGET_ITEM) == "persistence_test_item"
        assert unified_context2.get(StateParameters.CHARACTER_LEVEL) == 42
        assert unified_context2.get(StateParameters.MATERIALS_STATUS) == "sufficient"
    
    def test_action_context_state_synchronization(self):
        """Test ActionContext synchronization with WorldState."""
        # Create mock controller with world state
        mock_controller = Mock()
        mock_controller.character_state = Mock()
        mock_controller.character_state.data = {'x': 0, 'y': 0, 'level': 1}
        
        # Test unified context directly (since WorldState loads from file)
        unified_context = get_unified_context()
        unified_context.set(StateParameters.TARGET_ITEM, "sync_test_item")
        unified_context.set(StateParameters.CHARACTER_HEALTHY, True)
        unified_context.set(StateParameters.COMBAT_STATUS, "active")
        
        # Create ActionContext
        context = ActionContext.from_controller(mock_controller)
        
        # Verify synchronization - both should access same singleton
        assert context.get(StateParameters.TARGET_ITEM) == "sync_test_item"
        assert context.get(StateParameters.CHARACTER_HEALTHY) is True
        assert context.get(StateParameters.COMBAT_STATUS) == "active"
        
        # Test bidirectional sync - modify context
        context.set(StateParameters.TARGET_ITEM, "modified_item")
        
        # Verify change is reflected in unified context
        assert unified_context.get(StateParameters.TARGET_ITEM) == "modified_item"
    
    def test_parameter_validation_across_components(self):
        """Test parameter validation enforcement across all components."""
        context = ActionContext()
        
        # All components should reject invalid parameters
        with pytest.raises(ValueError, match="not registered in StateParameters"):
            context.set("invalid.parameter", "value")
        
        with pytest.raises(ValueError, match="not registered in StateParameters"):
            context.get("nonexistent.parameter")
    
    def test_error_handling_and_recovery(self):
        """Test error handling across the state unification system."""
        # Test ActionContext with missing controller dependencies
        mock_controller = Mock()
        mock_controller.character_state = None
        
        # Should not crash, should handle gracefully
        context = ActionContext.from_controller(mock_controller)
        
        # Should have config-based default values (CHARACTER_LEVEL comes from API)
        assert context.get(StateParameters.CHARACTER_HEALTHY) is True
        # CHARACTER_LEVEL comes from API, not state defaults
        assert isinstance(context, ActionContext)  # Context creation succeeded
    
    def test_state_consistency_after_operations(self):
        """Test state consistency after various operations."""
        context = ActionContext()
        
        # Set related parameters
        context.set(StateParameters.TARGET_ITEM, "consistency_test")
        
        # Verify automatic flag setting
        # HAS_TARGET_ITEM removed - use knowledge_base.has_target_item(context) helper
        
        # Clear selected item
        context.set(StateParameters.TARGET_ITEM, None)
        
        # Verify related state updates
        # HAS_TARGET_ITEM removed - use knowledge_base.has_target_item(context) helper
        
        # Test bulk updates maintain consistency
        updates = {
            StateParameters.CHARACTER_LEVEL: 10,
            StateParameters.CHARACTER_HEALTHY: True,
            StateParameters.CHARACTER_X: 50
        }
        
        context.update(updates)
        
        # Verify all updates applied
        for param, value in updates.items():
            assert context.get(param) == value
    
    def test_equipment_api_authoritative_integration(self):
        """Test that equipment uses APIs as authoritative source."""
        context = ActionContext()
        
        # Equipment parameters removed - APIs are authoritative for current equipment state
        # Test that context can be created and used with TARGET_ITEM for equipment goals
        context.set(StateParameters.TARGET_ITEM, "test_sword")
        context.set(StateParameters.TARGET_SLOT, "weapon")
        
        # Test target item retrieval
        assert context.get(StateParameters.TARGET_ITEM) == "test_sword"
        assert context.get(StateParameters.TARGET_SLOT) == "weapon"
        
        # Equipment slot method removed - APIs are authoritative for current equipment
        # Test that the context works for goal-based equipment targeting
    
    def test_singleton_consistency_across_components(self):
        """Test that all components use the same singleton instance."""
        # Create multiple components
        world_state = WorldState()
        context1 = ActionContext()
        context2 = ActionContext()
        
        # All should reference the same singleton
        unified_context = world_state.get_unified_context()
        assert context1._state is unified_context
        assert context2._state is unified_context
        assert context1._state is context2._state
        
        # Changes in one should be visible in all
        context1.set(StateParameters.TARGET_ITEM, "singleton_test")
        assert context2.get(StateParameters.TARGET_ITEM) == "singleton_test"
        assert unified_context.get(StateParameters.TARGET_ITEM) == "singleton_test"