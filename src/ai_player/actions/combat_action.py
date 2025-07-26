"""
Combat Action Implementation

This module implements the combat action for fighting monsters in the game.
It handles monster engagement, HP requirements, and combat result processing
while integrating with the GOAP system through the BaseAction interface.

The CombatAction demonstrates proper handling of combat mechanics and
state management for monster fighting scenarios.
"""

from typing import Any, Optional

from ...game_data.api_client import APIClientWrapper
from ..state.game_state import ActionResult, GameState
from .base_action import BaseAction


class CombatAction(BaseAction):
    """Combat action for fighting monsters using GameState enum.
    
    Handles monster fighting with proper HP and location preconditions,
    integrating with the API for actual combat execution.
    """

    def __init__(self, target_monster: str | None = None, api_client: Optional['APIClientWrapper'] = None):
        """Initialize CombatAction with optional target monster.
        
        Parameters:
            target_monster: Specific monster code to target, or None for any monster
            api_client: API client wrapper for combat execution
            
        Return values:
            None (constructor)
            
        This constructor creates a combat action instance for fighting monsters,
        optionally targeting a specific monster type for strategic combat
        planning within the AI player system.
        """
        self.target_monster = target_monster
        self.api_client = api_client

    @property
    def name(self) -> str:
        """Unique combat action identifier.
        
        Parameters:
            None (property)
            
        Return values:
            String identifier for the combat action in GOAP planning
            
        This property provides the unique action name used by the GOAP planner
        to identify and reference the combat action in planning sequences,
        including target monster information when specified.
        """
        if self.target_monster:
            return f"combat_{self.target_monster}"
        return "combat"

    @property
    def cost(self) -> int:
        """GOAP cost for combat action.
        
        Parameters:
            None (property)
            
        Return values:
            Integer cost value for GOAP planning optimization
            
        This property returns the planning cost for combat actions, enabling
        the GOAP planner to balance combat against other actions based on
        risk, reward, and strategic priorities.
        """
        return 10

    def get_preconditions(self) -> dict[GameState, Any]:
        """Combat preconditions including HP and location using GameState enum.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys defining combat requirements
            
        This method returns the preconditions for combat including sufficient HP,
        monster location, equipment requirements, and cooldown readiness using
        GameState enum keys for type-safe condition checking.
        """
        preconditions = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.SAFE_TO_FIGHT: True,
            GameState.AT_MONSTER_LOCATION: True,
        }

        if self.target_monster:
            preconditions[GameState.ENEMY_NEARBY] = True

        return preconditions

    def get_effects(self) -> dict[GameState, Any]:
        """Combat effects including XP and HP changes using GameState enum.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys defining combat outcomes
            
        This method returns the expected effects of combat including character
        XP gains, potential HP loss, item drops, and cooldown activation using
        GameState enum keys for type-safe effect specification.
        """
        return {
            GameState.CHARACTER_XP: "+combat_xp_gain",
            GameState.CHARACTER_GOLD: "+combat_gold_gain",
            GameState.COOLDOWN_READY: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
        }

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        """Execute combat via API client.
        
        Parameters:
            character_name: Name of the character to engage in combat
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            ActionResult with success status, message, and combat outcome changes
            
        This method executes the combat action through the API client, handling
        safety validation, combat mechanics, HP management, and result processing
        for monster fighting in the AI player system.
        """
        if self.api_client is None:
            return ActionResult(
                success=False,
                message="API client not available for combat execution",
                state_changes={},
                cooldown_seconds=0
            )

        # Safety check before engaging in combat
        if not self.is_safe_to_fight(current_state):
            return ActionResult(
                success=False,
                message="Combat conditions unsafe - insufficient HP or high risk",
                state_changes={},
                cooldown_seconds=0
            )

        try:
            # Execute combat via API
            fight_result = await self.api_client.fight_monster(character_name)

            # Extract state changes from combat result
            state_changes = {
                GameState.CHARACTER_XP: fight_result.data.character.xp,
                GameState.CHARACTER_GOLD: fight_result.data.character.gold,
                GameState.HP_CURRENT: fight_result.data.character.hp,
                GameState.COOLDOWN_READY: False,
                GameState.CAN_FIGHT: False,
                GameState.CAN_GATHER: False,
                GameState.CAN_CRAFT: False,
                GameState.CAN_TRADE: False,
                GameState.CAN_MOVE: False,
                GameState.CAN_REST: False,
                GameState.CAN_USE_ITEM: False,
                GameState.CAN_BANK: False,
            }

            # Update safety states based on new HP
            hp_percentage = fight_result.data.character.hp / fight_result.data.character.max_hp
            state_changes[GameState.HP_LOW] = hp_percentage < 0.3
            state_changes[GameState.HP_CRITICAL] = hp_percentage < 0.1
            state_changes[GameState.SAFE_TO_FIGHT] = hp_percentage > 0.5

            return ActionResult(
                success=True,
                message=f"Combat successful: {fight_result.data.fight.result}",
                state_changes=state_changes,
                cooldown_seconds=fight_result.data.cooldown.total_seconds
            )

        except Exception as error:
            return ActionResult(
                success=False,
                message=f"Combat failed: {str(error)}",
                state_changes={},
                cooldown_seconds=0
            )

    def is_safe_to_fight(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character has sufficient HP for combat.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Boolean indicating whether character can safely engage in combat
            
        This method evaluates the character's current HP against safety
        thresholds to determine if combat engagement is safe, preventing
        character death and ensuring sustainable gameplay.
        """
        # Check if already marked as safe to fight
        if GameState.SAFE_TO_FIGHT in current_state:
            safe_value = current_state[GameState.SAFE_TO_FIGHT]
            if safe_value is not None:
                return bool(safe_value)
            return False

        # Calculate from current HP values
        current_hp = current_state.get(GameState.HP_CURRENT, 0)
        max_hp = current_state.get(GameState.HP_MAX, 1)

        if current_hp <= 0 or max_hp <= 0:
            return False

        # Ensure character has at least 50% HP for safe combat
        hp_percentage = current_hp / max_hp
        return bool(hp_percentage >= 0.5)

    def calculate_combat_risk(self, current_state: dict[GameState, Any]) -> float:
        """Calculate risk level for current combat scenario.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Float representing combat risk level (0.0 = safe, 1.0 = extremely risky)
            
        This method analyzes character stats, equipment, HP percentage, and
        monster level to calculate combat risk, enabling strategic combat
        planning and retreat decision making.
        """
        risk_factors = []

        # HP-based risk - only add if HP data is available
        current_hp = current_state.get(GameState.HP_CURRENT)
        max_hp = current_state.get(GameState.HP_MAX)

        if current_hp is not None and max_hp is not None and max_hp > 0:
            hp_percentage = current_hp / max_hp
            # Risk increases exponentially as HP decreases
            hp_risk = max(0.0, (1.0 - hp_percentage) ** 2)
            risk_factors.append(hp_risk)
        elif max_hp is not None and max_hp <= 0:
            risk_factors.append(1.0)  # Maximum risk if invalid HP data

        # Location-based risk
        if not current_state.get(GameState.AT_SAFE_LOCATION, True):
            risk_factors.append(0.3)  # Moderate risk in unsafe areas

        # Equipment-based risk (basic check)
        weapon_equipped = current_state.get(GameState.WEAPON_EQUIPPED)
        if not weapon_equipped:
            risk_factors.append(0.4)  # Higher risk without weapon

        # Character level consideration (lower level = higher risk)
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level < 5:
            risk_factors.append(0.2)  # Additional risk for low-level characters

        # Calculate weighted risk (use max to be more conservative)
        if risk_factors:
            # Use the highest risk factor as the primary risk
            total_risk = max(risk_factors)
            # Add a small contribution from average to account for multiple factors
            average_risk = sum(risk_factors) / len(risk_factors)
            combined_risk = total_risk * 0.8 + average_risk * 0.2
            return float(min(1.0, combined_risk))  # Cap at 1.0

        return 0.5  # Default moderate risk if no factors available

    def should_retreat(self, current_state: dict[GameState, Any]) -> bool:
        """Determine if character should retreat from combat.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Boolean indicating whether character should disengage from combat
            
        This method evaluates current combat conditions including HP level,
        enemy strength, and escape routes to determine if tactical retreat
        is necessary for character survival.
        """
        # Check critical HP states
        if current_state.get(GameState.HP_CRITICAL, False):
            return True  # Always retreat if HP is critical

        # Calculate current risk level
        risk_level = self.calculate_combat_risk(current_state)

        # Retreat if risk is too high (above 70%)
        if risk_level > 0.7:
            return True

        # Check if character is no longer safe to fight
        if not self.is_safe_to_fight(current_state):
            return True

        # Check if character has low HP
        if current_state.get(GameState.HP_LOW, False):
            return True

        # Check if in combat and taking too much damage
        # (This would require tracking damage over time in a real implementation)
        if current_state.get(GameState.IN_COMBAT, False):
            current_hp = current_state.get(GameState.HP_CURRENT, 0)
            max_hp = current_state.get(GameState.HP_MAX, 1)

            if max_hp > 0:
                hp_percentage = current_hp / max_hp
                # Retreat if HP drops below 30% during combat
                if hp_percentage < 0.3:
                    return True

        return False  # Safe to continue combat

    def can_execute(self, current_state: dict[GameState, Any]) -> bool:
        """Check if action preconditions are met in current state.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Boolean indicating whether all preconditions are satisfied
        """
        preconditions = self.get_preconditions()
        return all(
            current_state.get(key) == value for key, value in preconditions.items()
        )

    def validate_preconditions(self) -> bool:
        """Validate that all preconditions use valid GameState enum keys.
        
        Parameters:
            None (operates on self)
            
        Return values:
            Boolean indicating whether all precondition keys are valid GameState enums
        """
        try:
            preconditions = self.get_preconditions()
            return all(isinstance(key, GameState) for key in preconditions.keys())
        except Exception:
            return False

    def validate_effects(self) -> bool:
        """Validate that all effects use valid GameState enum keys.
        
        Parameters:
            None (operates on self)
            
        Return values:
            Boolean indicating whether all effect keys are valid GameState enums
        """
        try:
            effects = self.get_effects()
            return all(isinstance(key, GameState) for key in effects.keys())
        except Exception:
            return False
