"""
Action Diagnostics Module

Provides diagnostic functions for action registry inspection and validation.
Includes action precondition/effect analysis, registry validation, and action
troubleshooting utilities for CLI diagnostic commands.
"""

from typing import Any

from ..actions import ActionRegistry
from ..actions.base_action import BaseAction
from ..state.game_state import GameState


class ActionDiagnostics:
    """Action system diagnostic utilities"""

    def __init__(self, action_registry: ActionRegistry):
        """Initialize ActionDiagnostics with action registry reference.

        Parameters:
            action_registry: ActionRegistry instance for action inspection

        Return values:
            None (constructor)

        This constructor initializes the action diagnostics system with
        access to the action registry for comprehensive analysis and
        validation of all registered actions and their implementations.
        """
        self.action_registry = action_registry

    def validate_action_registry(self) -> list[str]:
        """Validate all actions in registry use valid GameState enum keys.

        Parameters:
            None

        Return values:
            List of validation errors found in action implementations

        This method validates that all registered actions properly use
        GameState enum keys in their preconditions and effects, identifying
        type safety violations that could cause runtime errors.
        """
        errors = []

        # Get all action types from the registry
        action_types = self.action_registry.get_all_action_types()

        for action_class in action_types:
            try:
                # Try to create an instance to test validation
                try:
                    action_instance = action_class()

                    # Validate preconditions
                    if not action_instance.validate_preconditions():
                        errors.append(f"Action {action_class.__name__} has invalid preconditions (non-GameState keys)")

                    # Validate effects
                    if not action_instance.validate_effects():
                        errors.append(f"Action {action_class.__name__} has invalid effects (non-GameState keys)")

                except TypeError:
                    # Action requires parameters - can't validate instance without params
                    # This is expected for parameterized actions
                    continue
                except Exception as e:
                    errors.append(f"Action {action_class.__name__} validation failed: {str(e)}")

            except Exception as e:
                errors.append(f"Failed to validate action class {action_class.__name__}: {str(e)}")

        return errors

    def analyze_action_preconditions(self, action: BaseAction) -> dict[str, Any]:
        """Analyze action preconditions for validity and completeness.

        Parameters:
            action: BaseAction instance to analyze preconditions for

        Return values:
            Dictionary containing precondition analysis and validation results

        This method examines an action's preconditions for proper GameState
        enum usage, logical consistency, and completeness for effective
        GOAP planning and action execution validation.
        """
        analysis: dict[str, Any] = {
            "valid": True,
            "preconditions": {},
            "issues": [],
            "recommendations": []
        }

        try:
            preconditions = action.get_preconditions()
            analysis["preconditions"] = {key.value if isinstance(key, GameState) else str(key): value
                                        for key, value in preconditions.items()}

            # Check for proper GameState enum usage
            for key, value in preconditions.items():
                if not isinstance(key, GameState):
                    analysis["valid"] = False
                    analysis["issues"].append(f"Precondition key '{key}' is not a GameState enum")

                # Check for logical precondition values
                if key == GameState.CHARACTER_LEVEL and isinstance(value, int):
                    if value < 1 or value > 45:
                        analysis["issues"].append(f"Character level precondition {value} is out of range (1-45)")

                # Check for boolean preconditions that should use appropriate values
                boolean_keys = {GameState.COOLDOWN_READY, GameState.CAN_FIGHT, GameState.CAN_GATHER}
                if key in boolean_keys and not isinstance(value, bool):
                    analysis["issues"].append(
                        f"Boolean state '{key.value}' should have boolean value, got {type(value)}"
                    )

            # Check for common missing preconditions
            if GameState.COOLDOWN_READY not in preconditions:
                analysis["recommendations"].append("Consider adding COOLDOWN_READY precondition for API actions")

        except Exception as e:
            analysis["valid"] = False
            analysis["issues"].append(f"Failed to analyze preconditions: {str(e)}")

        return analysis

    def analyze_action_effects(self, action: BaseAction) -> dict[str, Any]:
        """Analyze action effects for validity and completeness.

        Parameters:
            action: BaseAction instance to analyze effects for

        Return values:
            Dictionary containing effect analysis and validation results

        This method examines an action's effects for proper GameState enum
        usage, realistic state changes, and completeness for accurate GOAP
        planning and state prediction in the AI player system.
        """
        analysis: dict[str, Any] = {
            "valid": True,
            "effects": {},
            "issues": [],
            "recommendations": []
        }

        try:
            effects = action.get_effects()
            analysis["effects"] = {key.value if isinstance(key, GameState) else str(key): value
                                  for key, value in effects.items()}

            # Check for proper GameState enum usage
            for key, value in effects.items():
                if not isinstance(key, GameState):
                    analysis["valid"] = False
                    analysis["issues"].append(f"Effect key '{key}' is not a GameState enum")

                # Check for realistic effect values
                if key == GameState.CHARACTER_LEVEL and isinstance(value, int):
                    if value < 1 or value > 45:
                        analysis["issues"].append(f"Character level effect {value} is out of range (1-45)")

                # Check for boolean effects
                boolean_keys = {GameState.COOLDOWN_READY, GameState.CAN_FIGHT, GameState.CAN_GATHER}
                if key in boolean_keys and not isinstance(value, bool):
                    analysis["issues"].append(
                        f"Boolean state '{key.value}' should have boolean value, got {type(value)}"
                    )

            # Check for expected effects based on action name
            action_name = action.name.lower()
            if "move" in action_name:
                if GameState.CURRENT_X not in effects and GameState.CURRENT_Y not in effects:
                    analysis["recommendations"].append("Movement action should update position (CURRENT_X, CURRENT_Y)")

            if "fight" in action_name or "combat" in action_name:
                if GameState.CHARACTER_XP not in effects:
                    analysis["recommendations"].append("Combat action should provide XP gain")

            # Most actions should set cooldown
            if GameState.COOLDOWN_READY not in effects:
                analysis["recommendations"].append("Consider setting COOLDOWN_READY to False after action execution")

        except Exception as e:
            analysis["valid"] = False
            analysis["issues"].append(f"Failed to analyze effects: {str(e)}")

        return analysis

    def check_action_executability(self, action: BaseAction, current_state: dict[GameState, Any]) -> dict[str, Any]:
        """Check if action can be executed in current state.

        Parameters:
            action: BaseAction instance to check executability for
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Dictionary containing executability analysis and blocking conditions

        This method validates whether an action can be executed in the current
        state by checking all preconditions and identifying any blocking
        factors that prevent immediate execution.
        """
        analysis: dict[str, Any] = {
            "executable": False,
            "blocking_conditions": [],
            "satisfied_conditions": [],
            "missing_state_keys": []
        }

        try:
            # Use the action's built-in can_execute method
            analysis["executable"] = action.can_execute(current_state)

            # Detailed analysis of preconditions
            preconditions = action.get_preconditions()
            for state_key, required_value in preconditions.items():
                if state_key not in current_state:
                    analysis["missing_state_keys"].append(state_key.value)
                    analysis["blocking_conditions"].append(f"Missing state key: {state_key.value}")
                else:
                    current_value = current_state[state_key]
                    if action._satisfies_precondition(state_key, current_value, required_value):
                        analysis["satisfied_conditions"].append(
                            f"{state_key.value}: {current_value} meets {required_value}"
                        )
                    else:
                        analysis["blocking_conditions"].append(
                            f"{state_key.value}: {current_value} does not meet {required_value}"
                        )

        except Exception as e:
            analysis["blocking_conditions"].append(f"Error checking executability: {str(e)}")

        return analysis

    def get_available_actions(self, current_state: dict[GameState, Any]) -> list[BaseAction]:
        """Get all actions that can be executed in current state.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of BaseAction instances that can be executed immediately

        This method filters all registered actions to identify which ones
        have their preconditions satisfied in the current state, providing
        the available action set for GOAP planning and diagnostic analysis.
        """
        available_actions = []

        try:
            # Generate actions using the registry with dummy game data
            # In a real implementation, we'd need actual game data
            game_data: dict[str, Any] = {}  # Placeholder
            all_actions = self.action_registry.generate_actions_for_state(current_state, game_data)

            for action in all_actions:
                try:
                    if action.can_execute(current_state):
                        available_actions.append(action)
                except Exception:
                    # Skip actions that fail executability check
                    continue

        except Exception:
            # If dynamic generation fails, try simple action types
            action_types = self.action_registry.get_all_action_types()
            for action_class in action_types:
                try:
                    action_instance = action_class()
                    if action_instance.can_execute(current_state):
                        available_actions.append(action_instance)
                except TypeError:
                    # Action requires parameters, skip
                    continue
                except Exception:
                    # Other errors, skip
                    continue

        return available_actions

    def format_action_info(self, action: BaseAction) -> str:
        """Format action information for CLI display.

        Parameters:
            action: BaseAction instance to format information for

        Return values:
            Formatted string representation suitable for CLI diagnostic output

        This method formats comprehensive action information including name,
        cost, preconditions, and effects in a readable format for CLI
        diagnostic display and troubleshooting analysis.
        """
        lines = []

        # Action header
        lines.append(f"=== ACTION: {action.name} ===")
        lines.append(f"Cost: {action.cost}")

        # Preconditions section
        try:
            preconditions = action.get_preconditions()
            lines.append("\nPreconditions:")
            if preconditions:
                for key, value in preconditions.items():
                    lines.append(f"  {key.value}: {value}")
            else:
                lines.append("  None")
        except Exception as e:
            lines.append(f"  Error getting preconditions: {e}")

        # Effects section
        try:
            effects = action.get_effects()
            lines.append("\nEffects:")
            if effects:
                for key, value in effects.items():
                    lines.append(f"  {key.value}: {value}")
            else:
                lines.append("  None")
        except Exception as e:
            lines.append(f"  Error getting effects: {e}")

        # Validation status
        lines.append("\nValidation:")
        try:
            precond_valid = action.validate_preconditions()
            effects_valid = action.validate_effects()
            lines.append(f"  Preconditions valid: {precond_valid}")
            lines.append(f"  Effects valid: {effects_valid}")
        except Exception as e:
            lines.append(f"  Validation error: {e}")

        return "\n".join(lines)

    def validate_action_costs(self) -> list[str]:
        """Validate action costs are reasonable and consistent.

        Parameters:
            None

        Return values:
            List of validation warnings about potentially problematic action costs

        This method analyzes action costs across the registry to identify
        unrealistic values, inconsistencies, or potential optimization
        opportunities in GOAP planning cost assignments.
        """
        warnings = []
        action_costs = []

        # Collect costs from all action types
        action_types = self.action_registry.get_all_action_types()
        for action_class in action_types:
            try:
                action_instance = action_class()
                cost = action_instance.cost
                action_costs.append((action_class.__name__, cost))

                # Check for unrealistic costs
                if cost <= 0:
                    warnings.append(f"Action {action_class.__name__} has non-positive cost: {cost}")
                elif cost > 1000:
                    warnings.append(f"Action {action_class.__name__} has very high cost: {cost}")

            except TypeError:
                # Action requires parameters, skip cost validation
                continue
            except Exception as e:
                warnings.append(f"Failed to get cost for {action_class.__name__}: {e}")

        # Check for cost distribution
        if action_costs:
            costs = [cost for _, cost in action_costs]
            min_cost = min(costs)
            max_cost = max(costs)

            if max_cost > min_cost * 100:
                warnings.append(f"Large cost variance: min={min_cost}, max={max_cost}")

        return warnings

    def detect_action_conflicts(self) -> list[str]:
        """Detect potential conflicts between action effects.

        Parameters:
            None

        Return values:
            List of detected conflicts between action implementations

        This method analyzes all registered actions to identify potential
        conflicts between action effects, contradictory state changes, or
        logical inconsistencies that could cause planning problems.
        """
        conflicts = []
        action_effects_map = {}

        # Collect effects from all actions
        action_types = self.action_registry.get_all_action_types()
        for action_class in action_types:
            try:
                action_instance = action_class()
                effects = action_instance.get_effects()
                action_effects_map[action_class.__name__] = effects
            except TypeError:
                # Action requires parameters, skip
                continue
            except Exception:
                # Other errors, skip
                continue

        # Look for conflicting effects on the same state keys
        state_key_effects: dict[Any, list[Any]] = {}
        for action_name, effects in action_effects_map.items():
            for state_key, value in effects.items():
                if state_key not in state_key_effects:
                    state_key_effects[state_key] = []
                state_key_effects[state_key].append((action_name, value))

        # Check for contradictory effects
        for state_key, effect_list in state_key_effects.items():
            if len(effect_list) > 1:
                values = [value for _, value in effect_list]
                unique_values = set(values)

                # If multiple actions set different values for the same state
                if len(unique_values) > 1:
                    # This might be normal (e.g., different move actions set different positions)
                    # But flag boolean conflicts
                    if all(isinstance(v, bool) for v in values):
                        if len(unique_values) > 1:
                            conflicts.append(f"Boolean conflict on {state_key.value}: {dict(effect_list)}")

        # Check for logical conflicts in preconditions vs effects
        for action_name, effects in action_effects_map.items():
            for other_name, other_effects in action_effects_map.items():
                if action_name != other_name:
                    # Look for actions that undo each other
                    for key, value in effects.items():
                        if key in other_effects and other_effects[key] != value:
                            if isinstance(value, bool) and isinstance(other_effects[key], bool):
                                conflicts.append(
                                    f"Actions {action_name} and {other_name} have opposite effects on {key.value}"
                                )

        return conflicts
