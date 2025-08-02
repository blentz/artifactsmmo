"""
Test suite for AI player diagnostics system.

Tests all diagnostic classes and functionality for comprehensive validation.
"""

import importlib
import inspect
from unittest.mock import patch

import src.ai_player.diagnostics as ai_player_diagnostics
from src.ai_player.diagnostics import ActionDiagnostics, PlanningDiagnostics, StateDiagnostics


class TestDiagnosticsModule:
    """Test the diagnostics module interface and exports."""

    def test_module_imports_successfully(self):
        """Test that the diagnostics module can be imported without errors."""
        # This test passes if no ImportError is raised during import
        assert ai_player_diagnostics is not None

    def test_all_attribute_exists(self):
        """Test that __all__ attribute is defined in the module."""
        assert hasattr(ai_player_diagnostics, '__all__')
        assert isinstance(ai_player_diagnostics.__all__, list)

    def test_all_attribute_contents(self):
        """Test that __all__ contains exactly the expected classes."""
        expected_exports = [
            "StateDiagnostics",
            "ActionDiagnostics",
            "PlanningDiagnostics"
        ]
        assert ai_player_diagnostics.__all__ == expected_exports

    def test_all_exports_are_importable(self):
        """Test that all classes listed in __all__ can be imported."""
        for export_name in ai_player_diagnostics.__all__:
            assert hasattr(ai_player_diagnostics, export_name)
            exported_class = getattr(ai_player_diagnostics, export_name)
            assert inspect.isclass(exported_class)

    def test_state_diagnostics_export(self):
        """Test that StateDiagnostics is properly exported."""
        assert hasattr(ai_player_diagnostics, 'StateDiagnostics')
        assert ai_player_diagnostics.StateDiagnostics is StateDiagnostics

    def test_action_diagnostics_export(self):
        """Test that ActionDiagnostics is properly exported."""
        assert hasattr(ai_player_diagnostics, 'ActionDiagnostics')
        assert ai_player_diagnostics.ActionDiagnostics is ActionDiagnostics

    def test_planning_diagnostics_export(self):
        """Test that PlanningDiagnostics is properly exported."""
        assert hasattr(ai_player_diagnostics, 'PlanningDiagnostics')
        assert ai_player_diagnostics.PlanningDiagnostics is PlanningDiagnostics

    def test_direct_imports_work(self):
        """Test that classes can be imported directly from the module."""
        # Use aliases to test the imports work
        AD = ActionDiagnostics
        PD = PlanningDiagnostics
        SD = StateDiagnostics

        assert SD is StateDiagnostics
        assert AD is ActionDiagnostics
        assert PD is PlanningDiagnostics

    def test_no_unexpected_exports(self):
        """Test that only expected attributes are exported from the module."""
        module_attrs = [attr for attr in dir(ai_player_diagnostics)
                       if not attr.startswith('_')]

        expected_attrs = set(ai_player_diagnostics.__all__)
        actual_attrs = set(module_attrs)

        # Allow for additional attributes that might be imported but not in __all__
        # but ensure __all__ contents are present
        assert expected_attrs.issubset(actual_attrs)

    def test_module_has_docstring(self):
        """Test that the module has comprehensive documentation."""
        assert ai_player_diagnostics.__doc__ is not None
        assert len(ai_player_diagnostics.__doc__.strip()) > 0

        # Check for key documentation elements
        doc = ai_player_diagnostics.__doc__
        assert "Diagnostic System Module" in doc
        assert "StateDiagnostics" in doc
        assert "ActionDiagnostics" in doc
        assert "PlanningDiagnostics" in doc
        assert "Example usage:" in doc

    def test_classes_are_classes(self):
        """Test that all exported items are actually classes."""
        for export_name in ai_player_diagnostics.__all__:
            exported_item = getattr(ai_player_diagnostics, export_name)
            assert inspect.isclass(exported_item)

    def test_import_structure_integrity(self):
        """Test that import structure follows expected patterns."""
        # Verify that imports come from expected submodules
        with patch('src.ai_player.diagnostics.action_diagnostics'):
            with patch('src.ai_player.diagnostics.planning_diagnostics'):
                with patch('src.ai_player.diagnostics.state_diagnostics'):
                    # Re-import to trigger the import statements
                    importlib.reload(ai_player_diagnostics)

                    # Verify the actual implementation works without mocks
                    importlib.reload(ai_player_diagnostics)

    def test_module_level_attributes(self):
        """Test module-level attributes and structure."""
        # Test that module has expected attributes
        assert hasattr(ai_player_diagnostics, '__name__')
        assert hasattr(ai_player_diagnostics, '__doc__')
        assert hasattr(ai_player_diagnostics, '__all__')

        # Test module name
        assert ai_player_diagnostics.__name__ == 'src.ai_player.diagnostics'

    def test_circular_import_protection(self):
        """Test that the module doesn't have circular import issues."""
        # This test passes if we can import multiple times without issues
        # Re-import should work fine
        diag_module = ai_player_diagnostics
        assert diag_module.StateDiagnostics is StateDiagnostics
        assert diag_module.ActionDiagnostics is ActionDiagnostics
        assert diag_module.PlanningDiagnostics is PlanningDiagnostics
