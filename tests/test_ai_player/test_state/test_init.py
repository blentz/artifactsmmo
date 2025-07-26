"""
Tests for state module __init__.py

Tests that the state module properly exports its public API components
and that imports work correctly for all exported classes and enums.
"""


import src.ai_player.state as state_module
from src.ai_player import state
from src.ai_player.state import (
    ActionResult,
    CharacterGameState,
    CooldownInfo,
    GameState,
    StateManager,
)


def test_state_module_imports() -> None:
    """Test that all expected components can be imported from state module."""
    # Verify all components are importable and have expected types
    assert GameState is not None
    assert ActionResult is not None
    assert CharacterGameState is not None
    assert CooldownInfo is not None
    assert StateManager is not None


def test_gamestate_enum_available() -> None:
    """Test that GameState enum is properly exposed and functional."""

    # Test that GameState is an enum with expected properties
    assert hasattr(GameState, 'CHARACTER_LEVEL')
    assert hasattr(GameState, 'CURRENT_X')
    assert hasattr(GameState, 'MINING_LEVEL')
    assert hasattr(GameState, 'INVENTORY_FULL')

    # Test enum value access
    assert GameState.CHARACTER_LEVEL.value == "character_level"
    assert GameState.CURRENT_X.value == "current_x"
    assert GameState.MINING_LEVEL.value == "mining_level"
    assert GameState.INVENTORY_FULL.value == "inventory_full"


def test_actionresult_model_available() -> None:
    """Test that ActionResult Pydantic model is properly exposed."""

    # Test that ActionResult can be instantiated
    result = ActionResult(
        success=True,
        message="Test action completed",
        state_changes={GameState.CHARACTER_LEVEL: 5},
        cooldown_seconds=0
    )

    assert result.success is True
    assert result.message == "Test action completed"
    assert result.state_changes[GameState.CHARACTER_LEVEL] == 5
    assert result.cooldown_seconds == 0


def test_charactergamestate_model_available() -> None:
    """Test that CharacterGameState Pydantic model is properly exposed."""

    # Test that CharacterGameState class is available
    assert hasattr(CharacterGameState, 'to_goap_state')
    assert hasattr(CharacterGameState, 'from_api_character')

    # Test that it's a Pydantic model
    assert hasattr(CharacterGameState, 'model_config')


def test_cooldowninfo_model_available() -> None:
    """Test that CooldownInfo Pydantic model is properly exposed."""

    # Test that CooldownInfo can be instantiated with required fields
    cooldown = CooldownInfo(
        character_name="test_char",
        expiration="2024-01-01T00:00:00Z",
        total_seconds=60,
        remaining_seconds=30,
        reason="Combat cooldown"
    )

    assert cooldown.character_name == "test_char"
    assert cooldown.expiration == "2024-01-01T00:00:00Z"
    assert cooldown.total_seconds == 60
    assert cooldown.remaining_seconds == 30
    assert cooldown.reason == "Combat cooldown"

    # Test that properties are available
    assert hasattr(cooldown, 'is_ready')
    assert hasattr(cooldown, 'time_remaining')


def test_statemanager_class_available() -> None:
    """Test that StateManager class is properly exposed."""

    # Test that StateManager class is available with expected methods
    assert hasattr(StateManager, '__init__')
    assert hasattr(StateManager, 'get_current_state')
    assert hasattr(StateManager, 'update_state_from_api')
    assert hasattr(StateManager, 'update_state_from_result')
    assert hasattr(StateManager, 'get_cached_state')
    assert hasattr(StateManager, 'validate_state_consistency')
    assert hasattr(StateManager, 'force_refresh')
    assert hasattr(StateManager, 'save_state_to_cache')
    assert hasattr(StateManager, 'load_state_from_cache')
    assert hasattr(StateManager, 'convert_api_to_goap_state')
    assert hasattr(StateManager, 'get_state_value')
    assert hasattr(StateManager, 'set_state_value')
    assert hasattr(StateManager, 'get_state_diff')


def test_module_all_attribute() -> None:
    """Test that __all__ is properly defined with all expected exports."""

    expected_exports = [
        "GameState",
        "ActionResult",
        "CharacterGameState",
        "CooldownInfo",
        "StateManager",
    ]

    assert hasattr(state, '__all__')
    assert set(state.__all__) == set(expected_exports)

    # Test that all items in __all__ are actually available
    for export_name in state.__all__:
        assert hasattr(state, export_name)


def test_import_from_state_module() -> None:
    """Test importing components directly from state module."""
    # This tests the import pattern used throughout the codebase

    # All imports should succeed without errors
    assert GameState is not None
    assert StateManager is not None
    assert CharacterGameState is not None
    assert CooldownInfo is not None
    assert ActionResult is not None


def test_no_unexpected_exports() -> None:
    """Test that only expected components are exported from module."""

    # Test using __all__ to ensure only intended exports are public
    expected_exports = [
        "GameState",
        "ActionResult",
        "CharacterGameState",
        "CooldownInfo",
        "StateManager",
    ]

    # __all__ should contain exactly the expected exports
    assert hasattr(state_module, '__all__')
    assert set(state_module.__all__) == set(expected_exports)

    # All items in __all__ should be available
    for export_name in state_module.__all__:
        assert hasattr(state_module, export_name)


def test_module_docstring() -> None:
    """Test that module has proper docstring."""

    assert state_module.__doc__ is not None
    assert "State Management Module" in state_module.__doc__
    assert "type-safe state management" in state_module.__doc__
    assert "enum-based" in state_module.__doc__
    assert "Pydantic models" in state_module.__doc__
