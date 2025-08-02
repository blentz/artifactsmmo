"""
State management tests

This package contains comprehensive tests for the AI player's state management
system, including:

- GameState enum functionality and type safety
- State validation and model integrity
- Character state models and Pydantic validation
- State synchronization with ArtifactsMMO API
- StateManager functionality and caching
- State transitions and action results
- API integration and error handling

Test modules:
- test_init.py: Tests for state module exports and imports
- test_game_state.py: Tests for GameState enum and state models
- test_state_manager.py: Tests for StateManager class functionality
- test_state_manager_impl.py: Implementation-specific StateManager tests

The tests ensure type safety, proper validation, and correct integration
with the game API while maintaining high code coverage and test reliability.
"""

from typing import Any, Dict

from src.ai_player.state.action_result import ActionResult
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import CooldownInfo, GameState


def create_mock_character_state(**overrides: Any) -> dict[GameState, Any]:
    """
    Create a mock character state with default values for testing.
    
    Args:
        **overrides: Any state values to override from defaults
        
    Returns:
        Dict[GameState, Any]: Complete character state dictionary
        
    Usage:
        # Create default state
        state = create_mock_character_state()
        
        # Override specific values
        state = create_mock_character_state(
            character_level=5,
            current_x=10,
            current_y=10
        )
    """
    default_state = {
        # Character progression
        GameState.CHARACTER_LEVEL: 1,
        GameState.CHARACTER_XP: 0,
        GameState.CHARACTER_GOLD: 0,
        GameState.HP_CURRENT: 100,
        GameState.HP_MAX: 100,

        # Position
        GameState.CURRENT_X: 0,
        GameState.CURRENT_Y: 0,

        # Skills
        GameState.MINING_LEVEL: 1,
        GameState.MINING_XP: 0,
        GameState.WOODCUTTING_LEVEL: 1,
        GameState.WOODCUTTING_XP: 0,
        GameState.FISHING_LEVEL: 1,
        GameState.FISHING_XP: 0,
        GameState.WEAPONCRAFTING_LEVEL: 1,
        GameState.WEAPONCRAFTING_XP: 0,
        GameState.GEARCRAFTING_LEVEL: 1,
        GameState.GEARCRAFTING_XP: 0,
        GameState.JEWELRYCRAFTING_LEVEL: 1,
        GameState.JEWELRYCRAFTING_XP: 0,
        GameState.COOKING_LEVEL: 1,
        GameState.COOKING_XP: 0,
        GameState.ALCHEMY_LEVEL: 1,
        GameState.ALCHEMY_XP: 0,

        # Equipment
        GameState.WEAPON_EQUIPPED: None,
        GameState.TOOL_EQUIPPED: None,
        GameState.HELMET_EQUIPPED: None,
        GameState.BODY_ARMOR_EQUIPPED: None,
        GameState.LEG_ARMOR_EQUIPPED: None,
        GameState.BOOTS_EQUIPPED: None,
        GameState.RING1_EQUIPPED: None,
        GameState.RING2_EQUIPPED: None,
        GameState.AMULET_EQUIPPED: None,

        # Calculated states
        GameState.INVENTORY_SPACE_AVAILABLE: 20,
        GameState.INVENTORY_FULL: False,
        GameState.COOLDOWN_READY: True,
        GameState.CAN_FIGHT: True,
        GameState.CAN_GATHER: True,
        GameState.CAN_CRAFT: True,
        GameState.AT_TARGET_LOCATION: False,
        GameState.AT_MONSTER_LOCATION: False,
        GameState.HAS_REQUIRED_ITEMS: False,
    }

    # Apply overrides
    for state_key, value in overrides.items():
        if isinstance(state_key, str):
            # Convert string keys to GameState enum
            for enum_key in GameState:
                if enum_key.value == state_key:
                    default_state[enum_key] = value
                    break
        else:
            default_state[state_key] = value

    return default_state


def create_mock_action_result(
    success: bool = True,
    message: str = "Action completed successfully",
    state_changes: dict[GameState, Any] | None = None,
    cooldown_seconds: int = 0
) -> ActionResult:
    """
    Create a mock ActionResult for testing.
    
    Args:
        success: Whether the action was successful
        message: Action result message
        state_changes: Dictionary of state changes from the action
        cooldown_seconds: Cooldown duration in seconds
        
    Returns:
        ActionResult: Mock action result instance
    """
    if state_changes is None:
        state_changes = {}

    return ActionResult(
        success=success,
        message=message,
        state_changes=state_changes,
        cooldown_seconds=cooldown_seconds
    )


def create_mock_cooldown_info(
    character_name: str = "test_character",
    expiration: str = "2024-01-01T00:00:00Z",
    total_seconds: int = 60,
    remaining_seconds: int = 0,
    reason: str = "Test cooldown"
) -> CooldownInfo:
    """
    Create a mock CooldownInfo for testing.
    
    Args:
        character_name: Name of the character
        expiration: ISO format expiration time
        total_seconds: Total cooldown duration
        remaining_seconds: Remaining cooldown time
        reason: Reason for the cooldown
        
    Returns:
        CooldownInfo: Mock cooldown info instance
    """
    return CooldownInfo(
        character_name=character_name,
        expiration=expiration,
        total_seconds=total_seconds,
        remaining_seconds=remaining_seconds,
        reason=reason
    )


__all__ = [
    "create_mock_character_state",
    "create_mock_action_result",
    "create_mock_cooldown_info",
]
