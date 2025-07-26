"""
Tests for CLI commands __init__ module

These tests validate the proper exposure and import functionality
of the CLI commands module, ensuring DiagnosticCommands and other
command classes are properly accessible.
"""

from unittest.mock import patch

import pytest

import src.cli.commands as commands_module
from src.cli.commands import DiagnosticCommands


class TestModuleStructure:
    """Test CLI commands module structure and exports"""

    def test_module_has_diagnostic_commands(self):
        """Test that module exposes DiagnosticCommands"""
        assert hasattr(commands_module, "DiagnosticCommands")
        assert commands_module.DiagnosticCommands is DiagnosticCommands

    def test_module_has_all_exports(self):
        """Test that __all__ contains expected exports"""
        expected_exports = [
            "DiagnosticCommands",
        ]

        for export in expected_exports:
            assert export in commands_module.__all__

    def test_all_exports_are_importable(self):
        """Test that all exports in __all__ can be imported"""
        for export_name in commands_module.__all__:
            assert hasattr(commands_module, export_name)

    def test_diagnostic_commands_is_class(self):
        """Test that DiagnosticCommands is a class"""
        assert isinstance(DiagnosticCommands, type)

    def test_module_docstring_exists(self):
        """Test that module has a proper docstring"""
        assert commands_module.__doc__ is not None
        assert "CLI Commands Module" in commands_module.__doc__


class TestDiagnosticCommandsImport:
    """Test DiagnosticCommands import functionality"""

    def test_diagnostic_commands_can_be_instantiated(self):
        """Test that DiagnosticCommands can be instantiated"""
        # This tests that the import works and the class is accessible
        diagnostic_commands = DiagnosticCommands()
        assert diagnostic_commands is not None

    def test_diagnostic_commands_has_expected_methods(self):
        """Test that DiagnosticCommands has expected diagnostic methods"""
        diagnostic_commands = DiagnosticCommands()

        # Check for key diagnostic methods
        assert hasattr(diagnostic_commands, "diagnose_state")
        assert hasattr(diagnostic_commands, "diagnose_actions")
        assert hasattr(diagnostic_commands, "diagnose_plan")
        assert hasattr(diagnostic_commands, "test_planning")

        # Check for formatting methods
        assert hasattr(diagnostic_commands, "format_state_output")
        assert hasattr(diagnostic_commands, "format_action_output")
        assert hasattr(diagnostic_commands, "format_planning_output")

    def test_diagnostic_commands_methods_are_callable(self):
        """Test that DiagnosticCommands methods are callable"""
        diagnostic_commands = DiagnosticCommands()

        # Test that methods are callable (not just attributes)
        assert callable(diagnostic_commands.diagnose_state)
        assert callable(diagnostic_commands.diagnose_actions)
        assert callable(diagnostic_commands.diagnose_plan)
        assert callable(diagnostic_commands.test_planning)
        assert callable(diagnostic_commands.format_state_output)
        assert callable(diagnostic_commands.format_action_output)
        assert callable(diagnostic_commands.format_planning_output)


class TestImportPaths:
    """Test various import paths work correctly"""

    def test_direct_import_from_commands(self):
        """Test direct import from commands module"""
        from src.cli.commands import DiagnosticCommands as DirectDC
        assert DirectDC is DiagnosticCommands

    def test_import_from_commands_init(self):
        """Test import from commands.__init__"""
        import src.cli.commands
        assert src.cli.commands.DiagnosticCommands is DiagnosticCommands

    def test_relative_import_simulation(self):
        """Test that relative imports would work (simulated)"""
        # This simulates what main.py does with: from .commands.diagnostics import DiagnosticCommands
        # We can't test actual relative imports here, but we can test the end result
        from src.cli.commands.diagnostics import DiagnosticCommands as RelativeDC
        assert RelativeDC is DiagnosticCommands


class TestModuleReimport:
    """Test module re-import behavior"""

    def test_module_reimport_gives_same_objects(self):
        """Test that re-importing gives the same objects"""
        import src.cli.commands as commands1
        import src.cli.commands as commands2

        assert commands1.DiagnosticCommands is commands2.DiagnosticCommands

    def test_class_instances_from_reimport(self):
        """Test that class instances work correctly after reimport"""
        import src.cli.commands as commands1
        dc1 = commands1.DiagnosticCommands()

        import src.cli.commands as commands2
        dc2 = commands2.DiagnosticCommands()

        # Should be the same class but different instances
        assert type(dc1) is type(dc2)
        assert dc1 is not dc2


class TestErrorConditions:
    """Test error conditions and edge cases"""

    def test_invalid_attribute_access(self):
        """Test that accessing invalid attributes raises AttributeError"""
        with pytest.raises(AttributeError):
            _ = commands_module.NonExistentCommand

    def test_all_exports_are_valid(self):
        """Test that all items in __all__ actually exist"""
        for export_name in commands_module.__all__:
            assert hasattr(commands_module, export_name), f"Export {export_name} not found in module"


class TestDependencyIntegration:
    """Test integration with actual dependencies"""

    def test_diagnostic_commands_uses_real_imports(self):
        """Test that DiagnosticCommands correctly imports its dependencies"""
        # This verifies that the diagnostics.py module is properly structured
        # and that our __init__.py correctly exposes it

        diagnostic_commands = DiagnosticCommands()

        # The class should be initialized without errors
        # This indirectly tests that all imports in diagnostics.py work
        assert diagnostic_commands is not None

    @patch('src.cli.commands.diagnostics.StateDiagnostics')
    @patch('src.cli.commands.diagnostics.ActionDiagnostics')
    @patch('src.cli.commands.diagnostics.PlanningDiagnostics')
    def test_diagnostic_commands_with_mocked_dependencies(self, mock_planning, mock_action, mock_state):
        """Test DiagnosticCommands with mocked dependencies"""
        # This tests that our import structure allows for proper mocking
        diagnostic_commands = DiagnosticCommands()
        assert diagnostic_commands is not None


class TestPerformance:
    """Test performance characteristics of module imports"""

    def test_import_speed(self):
        """Test that imports happen quickly"""
        import time
        import sys

        # Clear any cached modules to ensure fresh import timing
        modules_to_clear = [
            'src.cli.commands',
            'src.cli.commands.diagnostics'
        ]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]

        start_time = time.time()
        # Perform the actual import we're timing
        import src.cli.commands
        end_time = time.time()

        # Import should complete in reasonable time (< 1 second)
        assert end_time - start_time < 1.0

    def test_multiple_imports_efficiency(self):
        """Test that multiple imports are efficient"""
        import time

        start_time = time.time()
        for _ in range(100):
            # Import the same module multiple times to test caching efficiency
            import src.cli.commands
            _ = src.cli.commands.DiagnosticCommands
        end_time = time.time()

        # Multiple imports should still be fast due to Python's import caching
        assert end_time - start_time < 1.0
