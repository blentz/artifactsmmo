"""
Test Suite for StateParameters Registry - QA Engineer Implementation

Comprehensive validation of parameter registry integrity and naming conventions.
Zero tolerance for parameter conflicts or naming violations.

QA Focus Areas:
- Parameter uniqueness and consistency
- Naming convention compliance 
- Registry completeness
- Integration validation
"""

import pytest
from src.lib.state_parameters import StateParameters


class TestStateParametersRegistry:
    """Validate StateParameters registry integrity."""
    
    def test_no_duplicate_parameter_values(self):
        """Ensure no duplicate parameter names exist."""
        all_params = StateParameters.get_all_parameters()
        param_list = list(all_params)
        
        assert len(param_list) == len(set(param_list)), \
            f"Duplicate parameter values found: {[p for p in param_list if param_list.count(p) > 1]}"
    
    def test_all_parameters_follow_naming_convention(self):
        """Validate dotted naming convention compliance."""
        all_params = StateParameters.get_all_parameters()
        
        for param in all_params:
            # Must contain at least one dot
            assert '.' in param, f"Parameter '{param}' missing category separator"
            assert not param.startswith('.'), f"Parameter '{param}' starts with dot"
            assert not param.endswith('.'), f"Parameter '{param}' ends with dot"
            
            # Must have at least two parts (category.name)
            parts = param.split('.')
            assert len(parts) >= 2, f"Parameter '{param}' must have at least category.name"
            
            # All parts must be non-empty
            for i, part in enumerate(parts):
                assert part, f"Parameter '{param}' has empty part at position {i}"
            
            # Must use lowercase with underscores
            for part in parts:
                assert part.islower() or '_' in part, f"Part '{part}' in parameter '{param}' not lowercase"
    
    def test_parameter_validation_method(self):
        """Test parameter validation functionality."""
        # Valid parameters should pass
        assert StateParameters.validate_parameter(StateParameters.TARGET_ITEM)
        assert StateParameters.validate_parameter(StateParameters.CHARACTER_LEVEL)
        
        # Invalid parameters should fail
        assert not StateParameters.validate_parameter("invalid.parameter")
        assert not StateParameters.validate_parameter("equipment_status.nonexistent")
        assert not StateParameters.validate_parameter("")
    
    def test_category_grouping_functionality(self):
        """Validate category-based parameter grouping."""
        equipment_params = StateParameters.get_parameters_by_category("equipment_status")
        character_params = StateParameters.get_parameters_by_category("character_status")
        
        # Should have parameters in each category
        assert len(equipment_params) > 0, "No equipment_status parameters found"
        assert len(character_params) > 0, "No character_status parameters found"
        
        # All parameters should belong to correct category
        for param in equipment_params:
            assert param.startswith("equipment_status."), f"Wrong category for {param}"
        
        for param in character_params:
            assert param.startswith("character_status."), f"Wrong category for {param}"
    
    def test_required_parameters_exist(self):
        """Ensure critical parameters are defined."""
        required_params = [
            StateParameters.TARGET_ITEM,
            StateParameters.CHARACTER_LEVEL,
            StateParameters.CHARACTER_X,
            StateParameters.CHARACTER_Y,
            StateParameters.TARGET_X,
            StateParameters.TARGET_Y,
            StateParameters.MATERIALS_STATUS,
            StateParameters.COMBAT_STATUS,
        ]
        
        all_params = StateParameters.get_all_parameters()
        
        for param in required_params:
            assert param in all_params, f"Required parameter '{param}' not in registry"
    
    def test_parameter_constants_are_strings(self):
        """Validate all parameter constants are strings."""
        for attr_name in dir(StateParameters):
            if not attr_name.startswith('_') and attr_name.isupper():
                attr_value = getattr(StateParameters, attr_name)
                assert isinstance(attr_value, str), f"Parameter '{attr_name}' is not a string: {type(attr_value)}"
    
    def test_registry_completeness(self):
        """Ensure registry covers all expected categories."""
        expected_categories = [
            "equipment_status",
            "character_status", 
            "materials",
            "combat_context",
            "goal_progress",
            "resource_availability",
            "skill_requirements",
            "skill_status",
            "skills",
            "workshop_status",
            "inventory",
            "healing_context"
        ]
        
        all_params = StateParameters.get_all_parameters()
        found_categories = set()
        
        for param in all_params:
            category = param.split('.')[0]
            found_categories.add(category)
        
        for expected_category in expected_categories:
            assert expected_category in found_categories, \
                f"Expected category '{expected_category}' not found in registry"