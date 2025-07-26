"""
Tests for the diagnostics module as a whole.

Tests module exports, integration, and overall functionality.
"""


# Test that all classes can be imported from the module
from src.ai_player.diagnostics import ActionDiagnostics, PlanningDiagnostics, StateDiagnostics
from src.ai_player.state.game_state import GameState


class TestDiagnosticsModule:
    """Test suite for the diagnostics module as a whole"""

    def test_module_exports(self):
        """Test that all expected classes are exported"""
        # Test that classes can be imported
        assert StateDiagnostics is not None
        assert ActionDiagnostics is not None
        assert PlanningDiagnostics is not None

        # Test that classes can be instantiated
        state_diag = StateDiagnostics()
        assert state_diag is not None

        # ActionDiagnostics and PlanningDiagnostics require dependencies
        # so we'll test them with mocks

    def test_module_docstring(self):
        """Test that module has proper documentation"""
        import src.ai_player.diagnostics as diagnostics_module

        assert diagnostics_module.__doc__ is not None
        assert "Diagnostic System Module" in diagnostics_module.__doc__
        assert len(diagnostics_module.__all__) == 3

    def test_class_inheritance(self):
        """Test that diagnostic classes have proper structure"""
        # StateDiagnostics should be a regular class
        assert hasattr(StateDiagnostics, '__init__')
        assert hasattr(StateDiagnostics, 'validate_state_enum_usage')
        assert hasattr(StateDiagnostics, 'check_state_consistency')
        assert hasattr(StateDiagnostics, 'format_state_for_display')

        # ActionDiagnostics should require action registry
        assert hasattr(ActionDiagnostics, '__init__')
        assert hasattr(ActionDiagnostics, 'validate_action_registry')
        assert hasattr(ActionDiagnostics, 'analyze_action_preconditions')
        assert hasattr(ActionDiagnostics, 'format_action_info')

        # PlanningDiagnostics should require goal manager
        assert hasattr(PlanningDiagnostics, '__init__')
        assert hasattr(PlanningDiagnostics, 'analyze_planning_steps')
        assert hasattr(PlanningDiagnostics, 'test_goal_reachability')
        assert hasattr(PlanningDiagnostics, 'visualize_plan')

    def test_integration_example(self):
        """Test basic integration of diagnostic classes"""
        # Create sample state for testing
        sample_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.COOLDOWN_READY: True
        }

        # Test StateDiagnostics
        state_diag = StateDiagnostics()

        # Should be able to validate state
        invalid_keys = state_diag.validate_state_enum_usage({
            "character_level": 10,
            "invalid_key": 100
        })
        assert "invalid_key" in invalid_keys
        assert "character_level" not in invalid_keys

        # Should be able to format state
        formatted = state_diag.format_state_for_display(sample_state)
        assert "CHARACTER PROGRESSION" in formatted
        assert "character_level: 10" in formatted

        # Should be able to detect invalid values
        invalid_state = {GameState.CHARACTER_LEVEL: -1}
        errors = state_diag.detect_invalid_state_values(invalid_state)
        assert len(errors) > 0
        assert "Invalid character level" in errors[0]

        # Should be able to generate statistics
        stats = state_diag.get_state_statistics(sample_state)
        assert stats["character_level"] == 10
        assert stats["hp_percentage"] == 80.0

    def test_gamestate_enum_integration(self):
        """Test that diagnostics properly integrate with GameState enum"""
        state_diag = StateDiagnostics()

        # Test with enum keys
        enum_state = {
            GameState.CHARACTER_LEVEL: 15,
            GameState.HP_CURRENT: 90,
            GameState.HP_MAX: 100
        }

        # Should handle enum keys properly
        stats = state_diag.get_state_statistics(enum_state)
        assert stats["character_level"] == 15
        assert stats["hp_percentage"] == 90.0

        # Test state change analysis with enum keys
        old_state = {GameState.CHARACTER_LEVEL: 10}
        new_state = {GameState.CHARACTER_LEVEL: 11}

        changes = state_diag.analyze_state_changes(old_state, new_state)
        assert changes["has_changes"] is True
        assert len(changes["positive_changes"]) == 1

    def test_error_handling(self):
        """Test that diagnostic classes handle errors gracefully"""
        state_diag = StateDiagnostics()

        # Test with malformed input
        try:
            # Should not crash with None input
            result = state_diag.validate_state_enum_usage(None)
            # If it doesn't crash, it should return empty list or handle gracefully
        except (TypeError, AttributeError):
            # Expected behavior for None input
            pass

        # Test with mixed key types
        mixed_state = {
            GameState.CHARACTER_LEVEL: 10,
            "string_key": 20,
            123: "number_key"
        }

        # Should handle mixed keys without crashing
        invalid_keys = state_diag.validate_state_enum_usage(mixed_state)
        assert isinstance(invalid_keys, list)

    def test_comprehensive_workflow(self):
        """Test a comprehensive diagnostic workflow"""
        # Create a complete diagnostic workflow example
        state_diag = StateDiagnostics()

        # Step 1: Validate raw API response
        api_response = {
            "character_level": 12,
            "character_xp": 1500,
            "hp_current": 85,
            "hp_max": 100,
            "current_x": 10,
            "current_y": 20,
            "cooldown_ready": True
        }

        # Check for invalid keys
        invalid_keys = state_diag.validate_state_enum_usage(api_response)

        # Step 2: Convert to proper GameState format
        game_state = {
            GameState.CHARACTER_LEVEL: api_response["character_level"],
            GameState.CHARACTER_XP: api_response["character_xp"],
            GameState.HP_CURRENT: api_response["hp_current"],
            GameState.HP_MAX: api_response["hp_max"],
            GameState.CURRENT_X: api_response["current_x"],
            GameState.CURRENT_Y: api_response["current_y"],
            GameState.COOLDOWN_READY: api_response["cooldown_ready"]
        }

        # Step 3: Validate completeness
        missing_keys = state_diag.validate_state_completeness(game_state)

        # Step 4: Detect invalid values
        validation_errors = state_diag.detect_invalid_state_values(game_state)

        # Step 5: Generate comprehensive report
        stats = state_diag.get_state_statistics(game_state)
        formatted_display = state_diag.format_state_for_display(game_state)

        # Verify workflow results
        assert len(invalid_keys) == 0  # All keys should be valid
        assert GameState.CHARACTER_GOLD in missing_keys  # Gold not provided
        assert len(validation_errors) == 0  # All values should be valid
        assert stats["character_level"] == 12
        assert "character_level: 12" in formatted_display

        # Step 6: Test state change tracking
        updated_state = game_state.copy()
        updated_state[GameState.CHARACTER_LEVEL] = 13
        updated_state[GameState.CHARACTER_XP] = 2000
        updated_state[GameState.HP_CURRENT] = 70  # Took damage

        change_analysis = state_diag.analyze_state_changes(game_state, updated_state)

        assert change_analysis["has_changes"] is True
        assert len(change_analysis["positive_changes"]) == 2  # Level and XP
        assert len(change_analysis["concerning_changes"]) == 1  # HP decrease

        # Verify progression metrics
        progression = change_analysis["progression_metrics"]
        assert progression["level_gained"] == 1
        assert progression["xp_gained"] == 500
        assert progression["hp_change"] == -15


class TestDiagnosticsModuleDocumentation:
    """Test documentation and usage examples"""

    def test_module_usage_example(self):
        """Test the usage example from module docstring"""
        # This should match the example in the module docstring
        from unittest.mock import Mock

        # Mock dependencies
        action_registry = Mock()
        goal_manager = Mock()

        # Create diagnostic instances as shown in docstring
        state_diag = StateDiagnostics()
        action_diag = ActionDiagnostics(action_registry)
        planning_diag = PlanningDiagnostics(goal_manager)

        # Test basic functionality
        assert state_diag is not None
        assert action_diag is not None
        assert planning_diag is not None

        # Test that dependencies are stored
        assert action_diag.action_registry == action_registry
        assert planning_diag.goal_manager == goal_manager

    def test_class_docstrings(self):
        """Test that all classes have proper documentation"""
        assert StateDiagnostics.__doc__ is not None
        assert "State management diagnostic utilities" in StateDiagnostics.__doc__

        assert ActionDiagnostics.__doc__ is not None
        assert "Action system diagnostic utilities" in ActionDiagnostics.__doc__

        assert PlanningDiagnostics.__doc__ is not None
        assert "GOAP planning diagnostic utilities" in PlanningDiagnostics.__doc__

    def test_method_signatures(self):
        """Test that key methods have expected signatures"""
        import inspect

        # Test StateDiagnostics key methods
        sig = inspect.signature(StateDiagnostics.validate_state_enum_usage)
        assert 'state_dict' in sig.parameters

        sig = inspect.signature(StateDiagnostics.format_state_for_display)
        assert 'state' in sig.parameters

        # Test ActionDiagnostics key methods
        sig = inspect.signature(ActionDiagnostics.check_action_executability)
        assert 'action' in sig.parameters
        assert 'current_state' in sig.parameters

        # Test PlanningDiagnostics key methods
        sig = inspect.signature(PlanningDiagnostics.test_goal_reachability)
        assert 'start_state' in sig.parameters
        assert 'goal_state' in sig.parameters
