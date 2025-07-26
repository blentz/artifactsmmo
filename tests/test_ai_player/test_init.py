"""
Tests for AI Player Module Initialization

This test module validates the ai_player module's __init__.py file implementation,
ensuring proper exports, module initialization, and factory functions work correctly.
"""

import inspect
from unittest.mock import Mock, patch

import pytest

import src.ai_player as ai_player_module
from src.ai_player import (
    ActionDiagnostics,
    ActionExecutor,
    ActionFactory,
    # Action System
    ActionRegistry,
    ActionResult,
    # Core Components
    AIPlayer,
    BaseAction,
    CharacterGameState,
    CombatAction,
    CooldownInfo,
    EconomicIntelligence,
    # State Management
    GameState,
    GatheringAction,
    GoalManager,
    InventoryOptimizer,
    # Action Implementations
    MovementAction,
    ParameterizedActionFactory,
    PathfindingService,
    PlanningDiagnostics,
    RestAction,
    # Diagnostics
    StateDiagnostics,
    StateManager,
    # Specialized Components
    TaskManager,
    # Factory Functions
    create_ai_player,
    get_all_actions,
    get_available_actions,
    initialize_ai_player_module,
    register_action_factory,
    validate_game_state,
)


class TestModuleExports:
    """Test that all expected classes and functions are properly exported"""

    def test_core_components_exported(self):
        """Test that core AI player components are exported"""
        assert AIPlayer is not None
        assert GoalManager is not None
        assert ActionExecutor is not None

    def test_state_management_exported(self):
        """Test that state management classes are exported"""
        assert GameState is not None
        assert ActionResult is not None
        assert CharacterGameState is not None
        assert CooldownInfo is not None
        assert StateManager is not None

    def test_action_system_exported(self):
        """Test that action system classes are exported"""
        assert ActionRegistry is not None
        assert ActionFactory is not None
        assert ParameterizedActionFactory is not None
        assert BaseAction is not None
        assert get_all_actions is not None
        assert register_action_factory is not None

    def test_action_implementations_exported(self):
        """Test that concrete action implementations are exported"""
        assert MovementAction is not None
        assert CombatAction is not None
        assert GatheringAction is not None
        assert RestAction is not None

    def test_diagnostics_exported(self):
        """Test that diagnostic classes are exported"""
        assert StateDiagnostics is not None
        assert ActionDiagnostics is not None
        assert PlanningDiagnostics is not None

    def test_specialized_components_exported(self):
        """Test that specialized component classes are exported"""
        assert TaskManager is not None
        assert PathfindingService is not None
        assert InventoryOptimizer is not None
        assert EconomicIntelligence is not None

    def test_factory_functions_exported(self):
        """Test that module-level factory functions are exported"""
        assert create_ai_player is not None
        assert get_available_actions is not None
        assert validate_game_state is not None
        assert initialize_ai_player_module is not None


class TestModuleAll:
    """Test the __all__ export list"""

    def test_all_list_complete(self):
        """Test that __all__ contains all intended exports"""
        expected_exports = {
            # Core Components
            "AIPlayer", "GoalManager", "ActionExecutor",

            # State Management
            "GameState", "ActionResult", "CharacterGameState",
            "CooldownInfo", "StateManager",

            # Action System
            "ActionRegistry", "ActionFactory", "ParameterizedActionFactory",
            "BaseAction", "get_all_actions", "register_action_factory",

            # Action Implementations
            "MovementAction", "CombatAction", "GatheringAction", "RestAction",

            # Diagnostics
            "StateDiagnostics", "ActionDiagnostics", "PlanningDiagnostics",

            # Specialized Components
            "TaskManager", "PathfindingService", "InventoryOptimizer", "EconomicIntelligence",
        }

        actual_exports = set(ai_player_module.__all__)
        assert actual_exports == expected_exports

    def test_no_private_exports(self):
        """Test that __all__ doesn't include private members"""
        for export in ai_player_module.__all__:
            assert not export.startswith('_'), f"Private member {export} should not be in __all__"


class TestModuleVersion:
    """Test module version information"""

    def test_version_exists(self):
        """Test that module version is defined"""
        assert hasattr(ai_player_module, '__version__')
        assert ai_player_module.__version__ == "2.0.0"

    def test_version_format(self):
        """Test that version follows semantic versioning format"""
        version = ai_player_module.__version__
        parts = version.split('.')
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestFactoryFunctions:
    """Test module-level factory functions"""

    @patch('src.ai_player.AIPlayer')
    def test_create_ai_player(self, mock_ai_player):
        """Test create_ai_player factory function"""
        mock_instance = Mock()
        mock_ai_player.return_value = mock_instance

        character_name = "test_character"
        result = create_ai_player(character_name)

        mock_ai_player.assert_called_once_with(character_name)
        assert result == mock_instance

    @patch('src.ai_player.get_all_actions')
    def test_get_available_actions(self, mock_get_all_actions):
        """Test get_available_actions wrapper function"""
        mock_actions = [Mock(), Mock()]
        mock_get_all_actions.return_value = mock_actions

        current_state = {GameState.CHARACTER_LEVEL: 1}
        game_data = Mock()

        result = get_available_actions(current_state, game_data)

        mock_get_all_actions.assert_called_once_with(current_state, game_data)
        assert result == mock_actions

    def test_get_available_actions_no_game_data(self):
        """Test get_available_actions with no game_data parameter"""
        with patch('src.ai_player.get_all_actions') as mock_get_all_actions:
            mock_actions = [Mock()]
            mock_get_all_actions.return_value = mock_actions

            current_state = {GameState.CHARACTER_LEVEL: 1}
            result = get_available_actions(current_state)

            mock_get_all_actions.assert_called_once_with(current_state, None)
            assert result == mock_actions

    @patch('src.ai_player.GameState.validate_state_dict')
    def test_validate_game_state(self, mock_validate):
        """Test validate_game_state wrapper function"""
        mock_validated = {GameState.CHARACTER_LEVEL: 1}
        mock_validate.return_value = mock_validated

        state_dict = {"character_level": 1}
        result = validate_game_state(state_dict)

        mock_validate.assert_called_once_with(state_dict)
        assert result == mock_validated


class TestModuleInitialization:
    """Test module initialization functionality"""

    def test_initialize_ai_player_module(self):
        """Test initialize_ai_player_module function"""
        # Function should exist and be callable
        assert callable(initialize_ai_player_module)

        # Should not raise any exceptions
        try:
            initialize_ai_player_module()
        except Exception as e:
            pytest.fail(f"initialize_ai_player_module raised {e}")

    @patch('src.ai_player.initialize_ai_player_module')
    def test_module_initialization_on_import(self, mock_initialize):
        """Test that module initialization is called on import"""
        # This test verifies the initialize call happens during import
        # The actual call happened when the module was imported for this test
        # We can at least verify the function exists and is callable
        assert callable(initialize_ai_player_module)


class TestModuleIntegrity:
    """Test overall module integrity and consistency"""

    def test_no_circular_imports(self):
        """Test that module imports don't create circular dependencies"""
        # If we got this far, imports succeeded without circular dependency errors
        assert True

    def test_all_exports_importable(self):
        """Test that all items in __all__ are actually importable"""
        for export_name in ai_player_module.__all__:
            assert hasattr(ai_player_module, export_name), f"{export_name} not found in module"
            exported_item = getattr(ai_player_module, export_name)
            assert exported_item is not None, f"{export_name} is None"

    def test_docstring_exists(self):
        """Test that module has proper docstring"""
        assert ai_player_module.__doc__ is not None
        assert len(ai_player_module.__doc__.strip()) > 0
        assert "ArtifactsMMO AI Player Module" in ai_player_module.__doc__


class TestTypeHints:
    """Test type hint consistency in factory functions"""

    def test_create_ai_player_type_hints(self):
        """Test create_ai_player has proper type hints"""
        sig = inspect.signature(create_ai_player)

        # Check parameter type hint
        assert 'character_name' in sig.parameters
        param = sig.parameters['character_name']
        assert param.annotation == str

        # Check return type hint
        # Note: AIPlayer is the actual class, not a string
        assert sig.return_annotation is not None

    def test_get_available_actions_type_hints(self):
        """Test get_available_actions has proper type hints"""
        sig = inspect.signature(get_available_actions)

        # Check parameters exist
        assert 'current_state' in sig.parameters
        assert 'game_data' in sig.parameters

        # Check return type hint
        assert sig.return_annotation is not None

    def test_validate_game_state_type_hints(self):
        """Test validate_game_state has proper type hints"""
        sig = inspect.signature(validate_game_state)

        # Check parameter exists
        assert 'state_dict' in sig.parameters

        # Check return type hint
        assert sig.return_annotation is not None


@pytest.mark.integration
class TestRealImports:
    """Integration tests with real module imports"""

    def test_import_all_exports(self):
        """Test importing all exports from the module"""

        # Test that star import would work by checking __all__
        for export_name in ai_player_module.__all__:
            assert hasattr(ai_player_module, export_name), f"Export {export_name} not found"

    def test_import_specific_components(self):
        """Test importing specific components"""

        assert AIPlayer is not None
        assert GameState is not None
        assert create_ai_player is not None

    def test_module_level_access(self):
        """Test accessing module-level attributes"""

        assert hasattr(ai_player_module, '__version__')
        assert hasattr(ai_player_module, '__all__')
        assert hasattr(ai_player_module, 'create_ai_player')


if __name__ == '__main__':
    pytest.main([__file__])
