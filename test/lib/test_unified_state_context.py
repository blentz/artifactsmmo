"""
Test Suite for UnifiedStateContext - QA Engineer Implementation

Comprehensive validation of unified state management functionality.
Focuses on singleton behavior, parameter validation, and data integrity.

QA Focus Areas:
- Singleton pattern integrity
- Parameter validation enforcement
- State persistence and loading
- Error handling and edge cases
"""

import pytest
import tempfile
import os
from unittest.mock import patch
from src.lib.unified_state_context import UnifiedStateContext, get_unified_context
from src.lib.state_parameters import StateParameters


class TestUnifiedStateContext:
    """Validate UnifiedStateContext functionality."""
    
    def setup_method(self):
        """Reset singleton for each test."""
        # Reset the singleton instance
        import src.lib.unified_state_context
        src.lib.unified_state_context._unified_instance = None
    
    def test_singleton_pattern_enforcement(self):
        """Validate singleton behavior."""
        context1 = UnifiedStateContext()
        context2 = UnifiedStateContext()
        context3 = get_unified_context()
        
        # All instances should be the same object
        assert context1 is context2
        assert context1 is context3
        assert context2 is context3
    
    def test_parameter_validation_on_get(self):
        """Test parameter validation during get operations."""
        context = UnifiedStateContext()
        
        # Valid parameter should work - TARGET_ITEM is in config as null
        result = context.get(StateParameters.TARGET_ITEM, "default")
        assert result is None  # Returns config value (null) instead of default
        
        # Test with a parameter that's not in defaults
        result = context.get(StateParameters.TARGET_ITEM)
        assert result is None  # Should return None since TARGET_ITEM is None
        
        # Invalid parameter should raise ValueError
        with pytest.raises(ValueError, match="not registered in StateParameters"):
            context.get("invalid.parameter")
    
    def test_parameter_validation_on_set(self):
        """Test parameter validation during set operations."""
        context = UnifiedStateContext()
        
        # Valid parameter should work
        context.set(StateParameters.TARGET_ITEM, "test_item")
        assert context.get(StateParameters.TARGET_ITEM) == "test_item"
        
        # Invalid parameter should raise ValueError
        with pytest.raises(ValueError, match="not registered in StateParameters"):
            context.set("invalid.parameter", "value")
    
    def test_parameter_validation_on_update(self):
        """Test parameter validation during bulk updates."""
        context = UnifiedStateContext()
        
        # Valid parameters should work
        valid_updates = {
            StateParameters.TARGET_ITEM: "copper_dagger",
            StateParameters.CHARACTER_LEVEL: 5
        }
        context.update(valid_updates)
        
        assert context.get(StateParameters.TARGET_ITEM) == "copper_dagger"
        assert context.get(StateParameters.CHARACTER_LEVEL) == 5
        
        # Invalid parameter should raise ValueError
        invalid_updates = {
            StateParameters.TARGET_ITEM: "valid_item",
            "invalid.parameter": "invalid_value"
        }
        
        with pytest.raises(ValueError, match="not registered in StateParameters"):
            context.update(invalid_updates)
        
        # Ensure no partial updates occurred
        assert context.get(StateParameters.TARGET_ITEM) == "copper_dagger"  # Unchanged
    
    def test_flat_data_loading_with_validation(self):
        """Test loading flat data with parameter validation."""
        context = UnifiedStateContext()
        
        # Mix of valid and invalid parameters
        flat_data = {
            StateParameters.TARGET_ITEM: "test_sword",
            StateParameters.CHARACTER_LEVEL: 10,
            "invalid.parameter": "should_be_ignored",
            "another.invalid": "also_ignored"
        }
        
        with patch.object(context._logger, 'warning') as mock_warning:
            context.load_from_flat_dict(flat_data)
            
            # Should log warnings for invalid parameters
            assert mock_warning.call_count == 1
            warning_args = mock_warning.call_args[0][0]
            assert "invalid.parameter" in warning_args
            assert "another.invalid" in warning_args
        
        # Valid parameters should be loaded
        assert context.get(StateParameters.TARGET_ITEM) == "test_sword"
        assert context.get(StateParameters.CHARACTER_LEVEL) == 10
    
    def test_default_values_initialization(self):
        """Validate default values are properly set."""
        context = UnifiedStateContext()
        
        # Test config-based default values (only those that can't be obtained from API)
        assert context.get(StateParameters.CHARACTER_HEALTHY) is True
        assert context.get(StateParameters.CHARACTER_COOLDOWN_ACTIVE) is False
        assert context.get(StateParameters.MATERIALS_STATUS) == "unknown"
    
    def test_state_persistence_methods(self):
        """Test state export and import functionality."""
        context = UnifiedStateContext()
        
        # Set test values
        test_data = {
            StateParameters.TARGET_ITEM: "iron_sword",
            StateParameters.CHARACTER_LEVEL: 15,
            StateParameters.CHARACTER_X: 100,
            StateParameters.CHARACTER_Y: 200
        }
        context.update(test_data)
        
        # Export to flat dict
        exported = context.to_flat_dict()
        
        # Verify exported data contains our test values
        for param, value in test_data.items():
            assert exported[param] == value
        
        # Create new context and import data
        context.reset()  # Reset to defaults
        context.load_from_flat_dict(exported)
        
        # Verify data was imported correctly
        for param, value in test_data.items():
            assert context.get(param) == value
    
    def test_reset_functionality(self):
        """Test state reset to defaults."""
        context = UnifiedStateContext()
        
        # Modify some values
        context.set(StateParameters.TARGET_ITEM, "modified_item")
        context.set(StateParameters.CHARACTER_HEALTHY, False)
        
        # Verify values changed
        assert context.get(StateParameters.TARGET_ITEM) == "modified_item"
        assert context.get(StateParameters.CHARACTER_HEALTHY) is False
        
        # Reset state
        context.reset()
        
        # Verify values returned to config defaults
        assert context.get(StateParameters.CHARACTER_HEALTHY) is True
        assert context.get(StateParameters.TARGET_ITEM) is None  # Not in config defaults
    
    def test_category_filtering(self):
        """Test category-based parameter retrieval."""
        context = UnifiedStateContext()
        
        # Set some equipment parameters
        context.set(StateParameters.EQUIPMENT_UPGRADE_STATUS, "ready")
        context.set(StateParameters.EQUIPMENT_GAPS_ANALYZED, True)
        
        # Get equipment category parameters
        equipment_params = context.get_parameters_by_category("equipment_status")
        
        # Should contain our set parameters
        assert StateParameters.EQUIPMENT_UPGRADE_STATUS in equipment_params
        assert equipment_params[StateParameters.EQUIPMENT_UPGRADE_STATUS] == "ready"
        assert equipment_params[StateParameters.EQUIPMENT_GAPS_ANALYZED] is True
        
        # Should not contain parameters from other categories
        for param_name in equipment_params.keys():
            assert param_name.startswith("equipment_status.")
    
    def test_dictionary_interface(self):
        """Test dictionary-style access methods."""
        context = UnifiedStateContext()
        
        # Test __getitem__ and __setitem__
        context[StateParameters.TARGET_ITEM] = "dict_access_item"
        assert context[StateParameters.TARGET_ITEM] == "dict_access_item"
        
        # Test __contains__
        assert StateParameters.TARGET_ITEM in context
        
        # Test keys(), values(), items()
        keys = list(context.keys())
        values = list(context.values())
        items = list(context.items())
        
        assert len(keys) > 0
        assert len(values) == len(keys)
        assert len(items) == len(keys)
        
        # Verify items integrity
        for key, value in items:
            assert context[key] == value
    
    def test_has_parameter_method(self):
        """Test parameter existence checking."""
        context = UnifiedStateContext()
        
        # Set a parameter
        context.set(StateParameters.TARGET_ITEM, "test_value")
        
        # Should exist after setting
        assert context.has_parameter(StateParameters.TARGET_ITEM)
        
        # Parameter with config default value should exist
        assert context.has_parameter(StateParameters.CHARACTER_HEALTHY)
        
        # Unset parameter should not exist if it doesn't have a config default
        param_without_default = StateParameters.CHARACTER_LEVEL  # Not in config defaults
        assert not context.has_parameter(param_without_default)