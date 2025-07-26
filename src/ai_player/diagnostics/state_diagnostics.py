"""
State Diagnostics Module

Provides diagnostic functions for state management validation and troubleshooting.
Includes GameState enum validation, state consistency checking, and state
inspection utilities for CLI diagnostic commands.
"""

from typing import Any

from ..state.game_state import GameState


class StateDiagnostics:
    """State management diagnostic utilities"""

    def __init__(self) -> None:
        """Initialize StateDiagnostics for state validation and analysis.

        Parameters:
            None

        Return values:
            None (constructor)

        This constructor initializes the state diagnostics system for
        comprehensive state validation, consistency checking, and analysis
        utilities essential for AI player troubleshooting.
        """
        # Track known required state keys for completeness validation
        self.required_state_keys = {
            GameState.CHARACTER_LEVEL,
            GameState.CHARACTER_XP,
            GameState.CHARACTER_GOLD,
            GameState.HP_CURRENT,
            GameState.HP_MAX,
            GameState.CURRENT_X,
            GameState.CURRENT_Y,
            GameState.COOLDOWN_READY,
        }

        # Track numeric state keys for range validation
        self.numeric_state_keys = {
            GameState.CHARACTER_LEVEL,
            GameState.CHARACTER_XP,
            GameState.CHARACTER_GOLD,
            GameState.HP_CURRENT,
            GameState.HP_MAX,
            GameState.CURRENT_X,
            GameState.CURRENT_Y,
            GameState.MINING_LEVEL,
            GameState.MINING_XP,
            GameState.WOODCUTTING_LEVEL,
            GameState.WOODCUTTING_XP,
            GameState.FISHING_LEVEL,
            GameState.FISHING_XP,
            GameState.WEAPONCRAFTING_LEVEL,
            GameState.WEAPONCRAFTING_XP,
            GameState.GEARCRAFTING_LEVEL,
            GameState.GEARCRAFTING_XP,
            GameState.JEWELRYCRAFTING_LEVEL,
            GameState.JEWELRYCRAFTING_XP,
            GameState.COOKING_LEVEL,
            GameState.COOKING_XP,
            GameState.ALCHEMY_LEVEL,
            GameState.ALCHEMY_XP,
        }

    def validate_state_enum_usage(self, state_dict: dict[str, Any]) -> list[str]:
        """Validate that all state keys exist in GameState enum.

        Parameters:
            state_dict: Dictionary with string keys to validate against GameState enum

        Return values:
            List of invalid state keys that don't exist in GameState enum

        This method validates that all state keys in the provided dictionary
        correspond to valid GameState enum values, identifying type safety
        violations and potential runtime errors in the AI player system.
        """
        invalid_keys = []
        valid_enum_values = {state.value for state in GameState}

        for key in state_dict.keys():
            if isinstance(key, str) and key not in valid_enum_values:
                invalid_keys.append(key)
            elif not isinstance(key, str | GameState):
                invalid_keys.append(str(key))

        return invalid_keys

    def check_state_consistency(self, api_state: dict[str, Any], local_state: dict[GameState, Any]) -> dict[str, Any]:
        """Compare API state with local state for consistency.

        Parameters:
            api_state: Fresh state data from API response
            local_state: Cached state with GameState enum keys

        Return values:
            Dictionary containing consistency analysis and discrepancies

        This method compares fresh API state data with locally cached state
        to identify inconsistencies, cache staleness, or synchronization
        issues that may affect AI player decision making.
        """
        analysis: dict[str, Any] = {
            "consistent": True,
            "discrepancies": [],
            "missing_in_local": [],
            "missing_in_api": [],
            "value_differences": []
        }

        # Convert local state to string keys for comparison
        local_str_state = {key.value if isinstance(key, GameState) else key: value
                           for key, value in local_state.items()}

        # Check for missing keys in local state
        for api_key in api_state.keys():
            if api_key not in local_str_state:
                analysis["missing_in_local"].append(api_key)
                analysis["consistent"] = False

        # Check for missing keys in API state
        for local_key in local_str_state.keys():
            if local_key not in api_state:
                analysis["missing_in_api"].append(local_key)
                analysis["consistent"] = False

        # Check for value differences
        for key in api_state.keys():
            if key in local_str_state:
                api_value = api_state[key]
                local_value = local_str_state[key]

                if api_value != local_value:
                    analysis["value_differences"].append({
                        "key": key,
                        "api_value": api_value,
                        "local_value": local_value,
                        "difference": (
                            abs(api_value - local_value)
                            if isinstance(api_value, int | float) and isinstance(local_value, int | float)
                            else "non_numeric"
                        )
                    })
                    analysis["consistent"] = False

        return analysis

    def analyze_state_changes(self, old_state: dict[GameState, Any], new_state: dict[GameState, Any]) -> dict[str, Any]:
        """Analyze differences between state snapshots.

        Parameters:
            old_state: Previous state snapshot with GameState enum keys
            new_state: Current state snapshot with GameState enum keys

        Return values:
            Dictionary containing change analysis, modified values, and trends

        This method analyzes changes between state snapshots to identify
        progression patterns, unexpected modifications, and state evolution
        for troubleshooting and monitoring AI player development.
        """
        analysis: dict[str, Any] = {
            "has_changes": False,
            "changes": [],
            "progression_metrics": {},
            "concerning_changes": [],
            "positive_changes": []
        }

        # Find all state keys across both snapshots
        all_keys = set(old_state.keys()) | set(new_state.keys())

        for key in all_keys:
            old_value = old_state.get(key)
            new_value = new_state.get(key)

            if old_value != new_value:
                analysis["has_changes"] = True

                change_info = {
                    "key": key.value if isinstance(key, GameState) else str(key),
                    "old_value": old_value,
                    "new_value": new_value,
                    "change_type": self._classify_change(key, old_value, new_value)
                }

                # Calculate numeric difference if applicable
                if isinstance(old_value, int | float) and isinstance(new_value, int | float):
                    change_info["difference"] = new_value - old_value
                    change_info["percent_change"] = ((new_value - old_value) / old_value * 100) if old_value != 0 else 0

                analysis["changes"].append(change_info)

                # Classify as positive or concerning
                if self._is_positive_change(key, old_value, new_value):
                    analysis["positive_changes"].append(change_info)
                elif self._is_concerning_change(key, old_value, new_value):
                    analysis["concerning_changes"].append(change_info)

        # Calculate progression metrics
        analysis["progression_metrics"] = self._calculate_progression_metrics(old_state, new_state)

        return analysis

    def validate_state_completeness(self, state: dict[GameState, Any]) -> list[GameState]:
        """Check for missing required state keys.

        Parameters:
            state: State dictionary with GameState enum keys to validate

        Return values:
            List of GameState enum keys that are missing from the state

        This method validates that all essential state keys are present
        in the character state, identifying missing data that could affect
        AI player decision making and action planning.
        """
        missing_keys = []

        for required_key in self.required_state_keys:
            if required_key not in state:
                missing_keys.append(required_key)

        return missing_keys

    def format_state_for_display(self, state: dict[GameState, Any]) -> str:
        """Format state data for CLI display.

        Parameters:
            state: State dictionary with GameState enum keys to format

        Return values:
            Formatted string representation suitable for CLI diagnostic output

        This method formats character state data into a readable format
        for CLI diagnostic display, organizing values by category and
        highlighting important information for debugging.
        """
        lines = []

        # Character progression section
        lines.append("=== CHARACTER PROGRESSION ===")
        for key in [GameState.CHARACTER_LEVEL, GameState.CHARACTER_XP, GameState.CHARACTER_GOLD]:
            if key in state:
                lines.append(f"{key.value}: {state[key]}")

        # Health section
        lines.append("\n=== HEALTH STATUS ===")
        for key in [GameState.HP_CURRENT, GameState.HP_MAX]:
            if key in state:
                lines.append(f"{key.value}: {state[key]}")
        if GameState.HP_CURRENT in state and GameState.HP_MAX in state:
            hp_percent = (state[GameState.HP_CURRENT] / state[GameState.HP_MAX]) * 100
            lines.append(f"hp_percentage: {hp_percent:.1f}%")

        # Position section
        lines.append("\n=== POSITION ===")
        for key in [GameState.CURRENT_X, GameState.CURRENT_Y]:
            if key in state:
                lines.append(f"{key.value}: {state[key]}")

        # Skills section
        lines.append("\n=== SKILLS ===")
        skill_keys = [k for k in state.keys() if k.value.endswith('_level')]
        for key in sorted(skill_keys, key=lambda x: x.value):
            lines.append(f"{key.value}: {state[key]}")

        # Action status section
        lines.append("\n=== ACTION STATUS ===")
        if GameState.COOLDOWN_READY in state:
            lines.append(f"{GameState.COOLDOWN_READY.value}: {state[GameState.COOLDOWN_READY]}")

        # Additional states
        other_keys = [k for k in state.keys() if k not in self.required_state_keys and not k.value.endswith('_level')]
        if other_keys:
            lines.append("\n=== OTHER STATES ===")
            for key in sorted(other_keys, key=lambda x: x.value):
                lines.append(f"{key.value}: {state[key]}")

        return "\n".join(lines)

    def detect_invalid_state_values(self, state: dict[GameState, Any]) -> list[str]:
        """Detect state values that may be invalid or corrupted.

        Parameters:
            state: State dictionary with GameState enum keys to validate

        Return values:
            List of error messages describing invalid state values found

        This method validates state values for correctness including range
        checks, type validation, and logical consistency to identify data
        corruption or invalid state conditions in the AI player system.
        """
        errors = []

        # Validate character level range
        if GameState.CHARACTER_LEVEL in state:
            level = state[GameState.CHARACTER_LEVEL]
            if not isinstance(level, int) or level < 1 or level > 45:
                errors.append(f"Invalid character level: {level} (must be 1-45)")

        # Validate HP values
        if GameState.HP_CURRENT in state:
            hp = state[GameState.HP_CURRENT]
            if not isinstance(hp, int) or hp < 0:
                errors.append(f"Invalid current HP: {hp} (must be >= 0)")

        if GameState.HP_MAX in state:
            max_hp = state[GameState.HP_MAX]
            if not isinstance(max_hp, int) or max_hp <= 0:
                errors.append(f"Invalid max HP: {max_hp} (must be > 0)")

        # Check HP consistency
        if (GameState.HP_CURRENT in state and GameState.HP_MAX in state):
            current_hp = state[GameState.HP_CURRENT]
            max_hp = state[GameState.HP_MAX]
            if isinstance(current_hp, int) and isinstance(max_hp, int):
                if current_hp > max_hp:
                    errors.append(f"Current HP ({current_hp}) exceeds max HP ({max_hp})")

        # Validate skill levels
        skill_keys = [k for k in state.keys() if k.value.endswith('_level')]
        for key in skill_keys:
            level = state[key]
            if not isinstance(level, int) or level < 1 or level > 45:
                errors.append(f"Invalid {key.value}: {level} (must be 1-45)")

        # Validate XP values (should be non-negative)
        xp_keys = [k for k in state.keys() if k.value.endswith('_xp')]
        for key in xp_keys:
            xp = state[key]
            if not isinstance(xp, int) or xp < 0:
                errors.append(f"Invalid {key.value}: {xp} (must be >= 0)")

        # Validate gold
        if GameState.CHARACTER_GOLD in state:
            gold = state[GameState.CHARACTER_GOLD]
            if not isinstance(gold, int) or gold < 0:
                errors.append(f"Invalid gold: {gold} (must be >= 0)")

        # Validate boolean states
        if GameState.COOLDOWN_READY in state:
            cooldown_ready = state[GameState.COOLDOWN_READY]
            if not isinstance(cooldown_ready, bool):
                errors.append(f"Invalid cooldown_ready: {cooldown_ready} (must be boolean)")

        return errors

    def get_state_statistics(self, state: dict[GameState, Any]) -> dict[str, Any]:
        """Generate statistics about current state.

        Parameters:
            state: State dictionary with GameState enum keys to analyze

        Return values:
            Dictionary containing statistical analysis of state data

        This method generates comprehensive statistics about character state
        including progression metrics, efficiency indicators, and trend analysis
        for monitoring AI player performance and optimization.
        """
        stats = {
            "character_level": state.get(GameState.CHARACTER_LEVEL, 0),
            "total_xp": state.get(GameState.CHARACTER_XP, 0),
            "gold": state.get(GameState.CHARACTER_GOLD, 0),
            "hp_percentage": 0.0,
            "skills": {},
            "total_skill_levels": 0,
            "average_skill_level": 0.0,
            "progress_to_max": 0.0
        }

        # Calculate HP percentage
        if GameState.HP_CURRENT in state and GameState.HP_MAX in state:
            current_hp = state[GameState.HP_CURRENT]
            max_hp = state[GameState.HP_MAX]
            if max_hp > 0:
                stats["hp_percentage"] = (current_hp / max_hp) * 100

        # Analyze skill progression
        skill_keys = [k for k in state.keys() if k.value.endswith('_level')]
        total_skill_levels = 0
        skill_count = 0

        for key in skill_keys:
            skill_name = key.value.replace('_level', '')
            skill_level = state[key]
            stats["skills"][skill_name] = {
                "level": skill_level,
                "xp": (
                    state.get(GameState(f"{skill_name}_xp"), 0)
                    if f"{skill_name}_xp" in [gs.value for gs in GameState]
                    else 0
                )
            }
            total_skill_levels += skill_level
            skill_count += 1

        if skill_count > 0:
            stats["total_skill_levels"] = total_skill_levels
            stats["average_skill_level"] = total_skill_levels / skill_count

        # Calculate progress to maximum level
        character_level = stats["character_level"]
        if character_level > 0:
            stats["progress_to_max"] = (character_level / 45) * 100

        return stats

    def _classify_change(self, key: GameState, old_value: Any, new_value: Any) -> str:
        """Classify the type of change for a state key."""
        if old_value is None and new_value is not None:
            return "added"
        elif old_value is not None and new_value is None:
            return "removed"
        elif isinstance(old_value, int | float) and isinstance(new_value, int | float):
            if new_value > old_value:
                return "increased"
            elif new_value < old_value:
                return "decreased"
            else:
                return "unchanged"
        else:
            return "modified"

    def _is_positive_change(self, key: GameState, old_value: Any, new_value: Any) -> bool:
        """Determine if a change is positive/beneficial."""
        # Increases in these values are generally positive
        positive_increase_keys = {
            GameState.CHARACTER_LEVEL, GameState.CHARACTER_XP, GameState.CHARACTER_GOLD,
            GameState.HP_CURRENT, GameState.MINING_LEVEL, GameState.MINING_XP,
            GameState.WOODCUTTING_LEVEL, GameState.WOODCUTTING_XP, GameState.FISHING_LEVEL,
            GameState.FISHING_XP, GameState.WEAPONCRAFTING_LEVEL, GameState.WEAPONCRAFTING_XP,
            GameState.GEARCRAFTING_LEVEL, GameState.GEARCRAFTING_XP, GameState.JEWELRYCRAFTING_LEVEL,
            GameState.JEWELRYCRAFTING_XP, GameState.COOKING_LEVEL, GameState.COOKING_XP,
            GameState.ALCHEMY_LEVEL, GameState.ALCHEMY_XP
        }

        if key in positive_increase_keys:
            if isinstance(old_value, int | float) and isinstance(new_value, int | float):
                return new_value > old_value

        # Becoming ready for action is positive
        if key == GameState.COOLDOWN_READY:
            return new_value is True and old_value is False

        return False

    def _is_concerning_change(self, key: GameState, old_value: Any, new_value: Any) -> bool:
        """Determine if a change is concerning/problematic."""
        # HP decreases are concerning
        if key == GameState.HP_CURRENT:
            if isinstance(old_value, int | float) and isinstance(new_value, int | float):
                return new_value < old_value

        # Going on cooldown might be concerning in some contexts
        if key == GameState.COOLDOWN_READY:
            return new_value is False and old_value is True

        # Large decreases in gold could be concerning
        if key == GameState.CHARACTER_GOLD:
            if isinstance(old_value, int | float) and isinstance(new_value, int | float):
                decrease = old_value - new_value
                return decrease > old_value * 0.5  # More than 50% decrease

        return False

    def _calculate_progression_metrics(
        self,
        old_state: dict[GameState, Any],
        new_state: dict[GameState, Any]
    ) -> dict[str, Any]:
        """Calculate progression metrics between state snapshots."""
        metrics: dict[str, Any] = {
            "level_gained": 0,
            "xp_gained": 0,
            "gold_gained": 0,
            "skills_improved": [],
            "hp_change": 0
        }

        # Calculate level and XP progression
        old_level = old_state.get(GameState.CHARACTER_LEVEL, 0)
        new_level = new_state.get(GameState.CHARACTER_LEVEL, 0)
        metrics["level_gained"] = new_level - old_level

        old_xp = old_state.get(GameState.CHARACTER_XP, 0)
        new_xp = new_state.get(GameState.CHARACTER_XP, 0)
        metrics["xp_gained"] = new_xp - old_xp

        # Calculate gold change
        old_gold = old_state.get(GameState.CHARACTER_GOLD, 0)
        new_gold = new_state.get(GameState.CHARACTER_GOLD, 0)
        metrics["gold_gained"] = new_gold - old_gold

        # Calculate HP change
        old_hp = old_state.get(GameState.HP_CURRENT, 0)
        new_hp = new_state.get(GameState.HP_CURRENT, 0)
        metrics["hp_change"] = new_hp - old_hp

        # Check skill improvements
        skill_keys = [k for k in new_state.keys() if k.value.endswith('_level')]
        for key in skill_keys:
            old_skill = old_state.get(key, 1)
            new_skill = new_state.get(key, 1)
            if new_skill > old_skill:
                metrics["skills_improved"].append({
                    "skill": key.value,
                    "old_level": old_skill,
                    "new_level": new_skill,
                    "levels_gained": new_skill - old_skill
                })

        return metrics
