"""
Diagnostic Commands Module

This module provides comprehensive diagnostic and troubleshooting commands
for the AI player system. Essential for debugging GOAP planning, state management,
and action execution issues.

The diagnostic commands enable deep introspection into the GOAP planning process,
state validation, action analysis, and system configuration troubleshooting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ...ai_player.actions import ActionRegistry
from ...ai_player.diagnostics.action_diagnostics import ActionDiagnostics
from ...ai_player.diagnostics.planning_diagnostics import PlanningDiagnostics
from ...ai_player.diagnostics.state_diagnostics import StateDiagnostics
from ...ai_player.goal_manager import GoalManager
from ...ai_player.state.character_game_state import CharacterGameState
from ...ai_player.state.game_state import GameState
from ...game_data.api_client import APIClientWrapper, CooldownManager


class DiagnosticCommands:
    """CLI diagnostic command implementations"""

    def __init__(self, action_registry: ActionRegistry | None = None,
                 goal_manager: GoalManager | None = None,
                 api_client: APIClientWrapper | None = None):
        """Initialize diagnostic commands with utility instances.

        Parameters:
            action_registry: Optional ActionRegistry instance for action diagnostics
            goal_manager: Optional GoalManager instance for planning diagnostics
            api_client: Optional APIClientWrapper instance for real character data

        Return values:
            None (constructor)

        This constructor initializes the diagnostic command system with
        instances of state, action, and planning diagnostic utilities for
        comprehensive AI player troubleshooting and analysis.
        """
        self.state_diagnostics = StateDiagnostics()

        if action_registry is not None:
            self.action_diagnostics = ActionDiagnostics(action_registry)
            self.action_registry = action_registry
        else:
            self.action_diagnostics = None
            self.action_registry = None

        if goal_manager is not None:
            self.planning_diagnostics = PlanningDiagnostics(goal_manager)
            self.goal_manager = goal_manager
        else:
            self.planning_diagnostics = None
            self.goal_manager = None

        self.api_client = api_client
        self.cooldown_manager = CooldownManager() if api_client else None


    async def diagnose_state(self, character_name: str, validate_enum: bool = False) -> dict[str, Any]:
        """Diagnose current character state and validation.

        Parameters:
            character_name: Name of the character to diagnose
            validate_enum: Whether to perform GameState enum validation

        Return values:
            Dictionary containing state analysis, validation results, and diagnostics

        This method provides comprehensive character state analysis including
        current values, GameState enum validation, and consistency checking
        for troubleshooting AI player state management issues.
        """
        diagnosis = {
            "character_name": character_name,
            "diagnostic_time": "",
            "api_available": self.api_client is not None,
            "state_validation": {
                "valid": True,
                "issues": [],
                "invalid_keys": [],
                "missing_required_keys": [],
                "invalid_values": []
            },
            "state_statistics": {},
            "consistency_check": {},
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        if not self.api_client:
            diagnosis["recommendations"].append(
                "API client not available - initialize DiagnosticCommands with APIClientWrapper for real character data"
            )
            return diagnosis

        try:
            # Get real character data from API
            character_data = await self.api_client.get_character(character_name)

            # Get map content for location-aware state
            game_map = await self.api_client.get_map(character_data.x, character_data.y)

            # Extract character game state with location context
            character_game_state = CharacterGameState.from_api_character(character_data, game_map.content)

            # Convert to GOAP state format and run diagnosis
            goap_state = character_game_state.to_goap_state()
            # Convert string keys back to GameState enum for diagnosis
            enum_state = {GameState(key): value for key, value in goap_state.items()}
            state_diagnosis = self.diagnose_state_data(enum_state, validate_enum)

            # Merge the API-sourced diagnosis with our structure
            diagnosis.update(state_diagnosis)
            diagnosis["character_name"] = character_name
            diagnosis["api_available"] = True
            diagnosis["character_found"] = True

            # Add API-specific information
            diagnosis["api_character_data"] = {
                "level": character_data.level,
                "xp": character_data.xp,
                "gold": character_data.gold,
                "hp": character_data.hp,
                "max_hp": character_data.max_hp,
                "position": {"x": character_data.x, "y": character_data.y}
            }

            # Add cooldown information if available
            if self.cooldown_manager:
                cooldown_info = self.cooldown_manager.get_cooldown_info(character_name)
                if cooldown_info:
                    diagnosis["cooldown_status"] = {
                        "on_cooldown": not cooldown_info.is_ready,
                        "remaining_seconds": cooldown_info.remaining_seconds,
                        "reason": cooldown_info.reason
                    }
                else:
                    diagnosis["cooldown_status"] = {
                        "on_cooldown": False,
                        "remaining_seconds": 0,
                        "reason": None
                    }

        except (ConnectionError, TimeoutError) as e:
            diagnosis["state_validation"]["valid"] = False
            diagnosis["state_validation"]["issues"].append(f"Network error fetching character data: {type(e).__name__}: {str(e)}")
            diagnosis["character_found"] = False
            diagnosis["recommendations"].append(f"Network connectivity issue: Cannot retrieve character '{character_name}' - check internet connection")
        except ValueError as e:
            diagnosis["state_validation"]["valid"] = False
            diagnosis["state_validation"]["issues"].append(f"Data validation error: {str(e)}")
            diagnosis["character_found"] = False
            diagnosis["recommendations"].append(f"Invalid character data received for '{character_name}' - this may indicate API changes")

        return diagnosis

    def diagnose_state_data(self, state_data: dict[GameState, Any], validate_enum: bool = False) -> dict[str, Any]:
        """Diagnose provided character state data.

        Parameters:
            state_data: Dictionary with GameState enum keys and current values
            validate_enum: Whether to perform GameState enum validation

        Return values:
            Dictionary containing state analysis, validation results, and diagnostics

        This method provides comprehensive character state analysis using
        provided state data, performing validation, consistency checks,
        and generating diagnostic recommendations.
        """
        diagnosis = {
            "diagnostic_time": "",
            "state_validation": {
                "valid": True,
                "issues": [],
                "invalid_keys": [],
                "missing_required_keys": [],
                "invalid_values": []
            },
            "state_statistics": {},
            "consistency_check": {},
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        try:
            # Validate state completeness
            missing_keys = self.state_diagnostics.validate_state_completeness(state_data)
            diagnosis["state_validation"]["missing_required_keys"] = [key.value for key in missing_keys]
            if missing_keys:
                diagnosis["state_validation"]["valid"] = False
                diagnosis["state_validation"]["issues"].append(f"Missing {len(missing_keys)} required state keys")

            # Detect invalid state values
            invalid_values = self.state_diagnostics.detect_invalid_state_values(state_data)
            diagnosis["state_validation"]["invalid_values"] = invalid_values
            if invalid_values:
                diagnosis["state_validation"]["valid"] = False
                diagnosis["state_validation"]["issues"].extend(invalid_values)

            # Generate state statistics
            diagnosis["state_statistics"] = self.state_diagnostics.get_state_statistics(state_data)

            # Enum validation if requested
            if validate_enum:
                # Convert to string keys for enum validation
                str_state = {key.value if isinstance(key, GameState) else str(key): value
                           for key, value in state_data.items()}
                invalid_keys = self.state_diagnostics.validate_state_enum_usage(str_state)
                diagnosis["state_validation"]["invalid_keys"] = invalid_keys
                if invalid_keys:
                    diagnosis["state_validation"]["valid"] = False
                    diagnosis["state_validation"]["issues"].append(f"Found {len(invalid_keys)} invalid enum keys")

            # Generate recommendations
            if diagnosis["state_statistics"].get("hp_percentage", 100) < 50:
                diagnosis["recommendations"].append("Character health is low - consider rest action")

            if diagnosis["state_statistics"].get("character_level", 1) < 5:
                diagnosis["recommendations"].append("Low character level - focus on XP-gaining activities")

            if not diagnosis["state_validation"]["valid"]:
                diagnosis["recommendations"].append("State validation failed - review and fix identified issues")

        except (AttributeError, TypeError) as e:
            diagnosis["state_validation"]["valid"] = False
            diagnosis["state_validation"]["issues"].append(f"Component error during state analysis: {type(e).__name__}: {str(e)}")
            diagnosis["recommendations"].append("System component issue detected - this may indicate a configuration problem")
        except ValueError as e:
            diagnosis["state_validation"]["valid"] = False
            diagnosis["state_validation"]["issues"].append(f"Data validation error during analysis: {str(e)}")
            diagnosis["recommendations"].append("Invalid data encountered during state analysis")

        return diagnosis

    async def diagnose_actions(self, character_name: str | None = None,
                             show_costs: bool = False,
                             list_all: bool = False,
                             show_preconditions: bool = False) -> dict[str, Any]:
        """Diagnose available actions and their properties.

        Parameters:
            character_name: Optional character name for state-specific action analysis
            show_costs: Whether to include GOAP action costs in output
            list_all: Whether to list all actions regardless of character state
            show_preconditions: Whether to display action preconditions and effects

        Return values:
            Dictionary containing action analysis, availability, and property details

        This method provides comprehensive analysis of available actions including
        their preconditions, effects, costs, and executability for troubleshooting
        GOAP planning and action availability issues.
        """
        diagnosis = {
            "character_name": character_name,
            "diagnostic_time": "",
            "registry_available": self.action_diagnostics is not None,
            "actions_analyzed": [],
            "registry_validation": {
                "valid": True,
                "errors": [],
                "warnings": []
            },
            "summary": {
                "total_actions": 0,
                "executable_actions": 0,
                "cost_range": {"min": 0, "max": 0},
                "action_types": {}
            },
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        if not self.action_diagnostics:
            diagnosis["registry_validation"]["valid"] = False
            diagnosis["registry_validation"]["errors"].append("ActionRegistry not available")
            diagnosis["recommendations"].append(
                "Action diagnostics unavailable - ActionRegistry required for full analysis"
            )
            return diagnosis

        try:
            # Validate action registry
            registry_errors = self.action_diagnostics.validate_action_registry()
            diagnosis["registry_validation"]["errors"] = registry_errors
            if registry_errors:
                diagnosis["registry_validation"]["valid"] = False

            # Validate action costs
            cost_warnings = self.action_diagnostics.validate_action_costs()
            diagnosis["registry_validation"]["warnings"] = cost_warnings

            # Get current character state using the proper application components
            current_state = {}
            if character_name and self.goal_manager and hasattr(self.goal_manager, 'state_manager'):
                try:
                    # Use the state manager that was properly initialized by CLI
                    current_state = await self.goal_manager.state_manager.get_current_state()
                except (AttributeError, TypeError) as e:
                    diagnosis["recommendations"].append(f"Component error getting character state: {type(e).__name__}: {e}")
                except ValueError as e:
                    diagnosis["recommendations"].append(f"Invalid character state data: {e}")

            # Use the same action generation path as the AI player
            if current_state and self.goal_manager:
                # Get game data from goal manager for parameterized action generation
                game_data = await self.goal_manager.get_game_data()
                all_actions = self.action_registry.generate_actions_for_state(current_state, game_data)
                diagnosis["summary"]["total_actions"] = len(all_actions)

                costs = []
                for action_instance in all_actions:
                    try:
                        action_info = {
                            "name": action_instance.name,
                            "class": action_instance.__class__.__name__,
                            "cost": action_instance.cost,
                            "executable": False,
                            "preconditions": {},
                            "effects": {},
                            "validation": {
                                "preconditions_valid": False,
                                "effects_valid": False
                            },
                            "issues": []
                        }

                        # Test executability with current character state
                        try:
                            action_info["executable"] = action_instance.can_execute(current_state)
                            if action_info["executable"]:
                                diagnosis["summary"]["executable_actions"] += 1
                        except (AttributeError, TypeError) as e:
                            action_info["issues"].append(f"Executability check failed - component error: {type(e).__name__}: {e}")
                        except ValueError as e:
                            action_info["issues"].append(f"Executability check failed - invalid data: {e}")

                        costs.append(action_instance.cost)

                        # Get preconditions and effects if requested
                        if show_preconditions:
                            try:
                                preconditions = action_instance.get_preconditions()
                                action_info["preconditions"] = {
                                    key.value if isinstance(key, GameState) else str(key): value
                                    for key, value in preconditions.items()
                                }
                            except (AttributeError, TypeError) as e:
                                action_info["issues"].append(f"Failed to get preconditions - component error: {type(e).__name__}: {e}")
                            except ValueError as e:
                                action_info["issues"].append(f"Failed to get preconditions - invalid data: {e}")

                            try:
                                effects = action_instance.get_effects()
                                action_info["effects"] = {
                                    key.value if isinstance(key, GameState) else str(key): value
                                    for key, value in effects.items()
                                }
                            except (AttributeError, TypeError) as e:
                                action_info["issues"].append(f"Failed to get effects - component error: {type(e).__name__}: {e}")
                            except ValueError as e:
                                action_info["issues"].append(f"Failed to get effects - invalid data: {e}")

                        # Validate action
                        try:
                            action_info["validation"]["preconditions_valid"] = action_instance.validate_preconditions()
                            action_info["validation"]["effects_valid"] = action_instance.validate_effects()
                        except (AttributeError, TypeError) as e:
                            action_info["issues"].append(f"Validation failed - component error: {type(e).__name__}: {e}")
                        except ValueError as e:
                            action_info["issues"].append(f"Validation failed - invalid data: {e}")

                        # Track action type
                        action_type = action_instance.__class__.__name__.replace("Action", "")
                        diagnosis["summary"]["action_types"][action_type] = (
                            diagnosis["summary"]["action_types"].get(action_type, 0) + 1
                        )

                        diagnosis["actions_analyzed"].append(action_info)

                    except (AttributeError, TypeError) as e:
                        diagnosis["actions_analyzed"].append({
                            "name": f"{action_instance.name} (component error)",
                            "class": action_instance.__class__.__name__,
                            "issues": [f"Analysis failed - component error: {type(e).__name__}: {str(e)}"]
                        })
                    except ValueError as e:
                        diagnosis["actions_analyzed"].append({
                            "name": f"{action_instance.name} (data error)",
                            "class": action_instance.__class__.__name__,
                            "issues": [f"Analysis failed - invalid data: {str(e)}"]
                        })
            else:
                # Fallback to action types when no state/goal manager available
                action_types = self.action_registry.get_all_action_types()
                diagnosis["summary"]["total_actions"] = len(action_types)
                diagnosis["recommendations"].append("Limited analysis - provide --character for full action generation")

                costs = []
                for action_class in action_types:
                    try:
                        try:
                            action_instance = action_class()
                            action_info = {
                                "name": action_instance.name,
                                "class": action_class.__name__,
                                "cost": action_instance.cost,
                                "executable": "Unknown (no character state)",
                                "issues": []
                            }
                            costs.append(action_instance.cost)
                            diagnosis["actions_analyzed"].append(action_info)
                        except TypeError:
                            action_info = {
                                "name": f"{action_class.__name__} (parameterized)",
                                "class": action_class.__name__,
                                "cost": "Variable",
                                "executable": "Requires parameters and state",
                                "issues": ["Parameterized action - use --character to see generated instances"]
                            }
                            diagnosis["actions_analyzed"].append(action_info)
                    except (AttributeError, TypeError) as e:
                        diagnosis["actions_analyzed"].append({
                            "name": f"{action_class.__name__} (component error)",
                            "class": action_class.__name__,
                            "issues": [f"Analysis failed - component error: {type(e).__name__}: {str(e)}"]
                        })
                    except ValueError as e:
                        diagnosis["actions_analyzed"].append({
                            "name": f"{action_class.__name__} (data error)",
                            "class": action_class.__name__,
                            "issues": [f"Analysis failed - invalid data: {str(e)}"]
                        })

            # Calculate cost statistics
            if costs:
                diagnosis["summary"]["cost_range"]["min"] = min(costs)
                diagnosis["summary"]["cost_range"]["max"] = max(costs)

            # Generate recommendations
            if registry_errors:
                diagnosis["recommendations"].append(f"Fix {len(registry_errors)} registry validation errors")

            if cost_warnings:
                diagnosis["recommendations"].append(f"Review {len(cost_warnings)} cost warnings")

            if diagnosis["summary"]["total_actions"] == 0:
                diagnosis["recommendations"].append("No actions found - check action registry implementation")

        except (AttributeError, TypeError) as e:
            diagnosis["registry_validation"]["valid"] = False
            diagnosis["registry_validation"]["errors"].append(f"Component error during action analysis: {type(e).__name__}: {str(e)}")
            diagnosis["recommendations"].append("System component issue detected during action analysis")
        except ValueError as e:
            diagnosis["registry_validation"]["valid"] = False
            diagnosis["registry_validation"]["errors"].append(f"Data validation error during action analysis: {str(e)}")
            diagnosis["recommendations"].append("Invalid data encountered during action analysis")

        return diagnosis

    async def diagnose_plan(self, character_name: str,
                          goal: str,
                          verbose: bool = False,
                          show_steps: bool = False) -> dict[str, Any]:
        """Diagnose GOAP planning process for specific goal.

        Parameters:
            character_name: Name of the character for planning analysis
            goal: String representation of the goal to plan for
            verbose: Whether to include detailed planning algorithm steps
            show_steps: Whether to display each step in the generated plan

        Return values:
            Dictionary containing planning analysis, step details, and optimization data

        This method analyzes the GOAP planning process for a specific goal,
        providing detailed insights into plan generation, action selection,
        and optimization for troubleshooting planning issues.
        """
        diagnosis = {
            "character_name": character_name,
            "goal": goal,
            "diagnostic_time": "",
            "planning_available": self.planning_diagnostics is not None,
            "planning_analysis": {},
            "plan_efficiency": {},
            "bottlenecks": [],
            "performance_metrics": {},
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        if not self.planning_diagnostics:
            diagnosis["recommendations"].append(
                "Planning diagnostics unavailable - GoalManager required for full analysis"
            )
            return diagnosis

        try:
            # Use actual character state if API client is available
            if character_name and self.api_client:
                try:
                    character_state = await self.api_client.get_character(character_name)
                    # Get map content for location context
                    game_map = await self.api_client.get_map(character_state.x, character_state.y)

                    # Convert to internal state format
                    char_state = CharacterGameState.from_api_character(character_state, game_map.content, self.api_client.cooldown_manager)
                    typed_state = char_state.to_goap_state()
                    GameState.validate_state_dict(typed_state)
                except (ConnectionError, TimeoutError) as e:
                    diagnosis["recommendations"].append(f"Network error getting character state: {type(e).__name__}: {str(e)}")
                    return diagnosis
                except (AttributeError, TypeError) as e:
                    diagnosis["recommendations"].append(f"Component error getting character state: {type(e).__name__}: {str(e)}")
                    return diagnosis
                except ValueError as e:
                    diagnosis["recommendations"].append(f"Invalid character state data: {str(e)}")
                    return diagnosis
            else:
                # Use default CharacterGameState for testing
                char_state = CharacterGameState(
                    name="test_character",
                    level=1,
                    xp=0,
                    gold=0,
                    hp=100,
                    max_hp=100,
                    x=0,
                    y=0,
                    mining_level=1,
                    mining_xp=0,
                    woodcutting_level=1,
                    woodcutting_xp=0,
                    fishing_level=1,
                    fishing_xp=0,
                    weaponcrafting_level=1,
                    weaponcrafting_xp=0,
                    gearcrafting_level=1,
                    gearcrafting_xp=0,
                    jewelrycrafting_level=1,
                    jewelrycrafting_xp=0,
                    cooking_level=1,
                    cooking_xp=0,
                    alchemy_level=1,
                    alchemy_xp=0,
                    cooldown=0,
                    cooldown_ready=True
                )

            # Use goal manager's intelligent goal selection based on character state
            # The goal parameter is used for diagnostic labeling but goal selection is handled by the goal manager
            selected_goal = await self.goal_manager.select_next_goal(char_state)
            goal_state = selected_goal.target_states if selected_goal else {}

            # Now use the actual goal manager to plan
            plan = await self.goal_manager.plan_actions(char_state, selected_goal)

            diagnosis["planning_analysis"] = {
                "planning_successful": not plan.is_empty,
                "goal_reachable": not plan.is_empty,
                "total_cost": plan.total_cost,
                "planning_time": 0.1  # Placeholder
            }

            # Add detailed information if verbose
            if verbose and plan:
                diagnosis["plan_steps"] = plan

            # Use planning diagnostics if available
            if self.planning_diagnostics:
                try:
                    # Pass CharacterGameState directly to diagnostics methods

                    # Test goal reachability
                    goal_reachable = await self.planning_diagnostics.test_goal_reachability(
                        char_state, goal_state
                    )
                    diagnosis["planning_analysis"]["goal_reachable"] = goal_reachable

                    # Identify bottlenecks
                    bottlenecks = await self.planning_diagnostics.identify_planning_bottlenecks(
                        char_state, goal_state
                    )
                    diagnosis["bottlenecks"] = bottlenecks

                    # Measure performance
                    performance = await self.planning_diagnostics.measure_planning_performance(
                        char_state, goal_state
                    )
                    diagnosis["performance_metrics"] = performance

                    # Analyze plan efficiency if we have a plan
                    if plan:
                        efficiency = self.planning_diagnostics.analyze_plan_efficiency(plan)
                        diagnosis["plan_efficiency"] = efficiency

                except (AttributeError, TypeError) as e:
                    diagnosis["recommendations"].append(f"Component error during planning diagnostics: {type(e).__name__}: {str(e)}")
                except ValueError as e:
                    diagnosis["recommendations"].append(f"Invalid data during planning diagnostics: {str(e)}")

            # Generate recommendations based on analysis
            if not plan or plan.is_empty:
                if not diagnosis["planning_analysis"].get("goal_reachable", True):
                    diagnosis["recommendations"].append("Goal appears to be unreachable with current actions")
                else:
                    diagnosis["recommendations"].append("No plan found - goal may be unreachable")
            else:
                diagnosis["recommendations"].append("Plan is efficient - no optimization needed")

            # Add bottleneck recommendations
            if diagnosis.get("bottlenecks") and len(diagnosis["bottlenecks"]) > 0:
                diagnosis["recommendations"].append(f"Found {len(diagnosis['bottlenecks'])} bottlenecks to address")

        except (AttributeError, TypeError) as e:
            diagnosis["recommendations"].append(f"Component error during planning analysis: {type(e).__name__}: {str(e)}")
        except ValueError as e:
            diagnosis["recommendations"].append(f"Invalid data during planning analysis: {str(e)}")

        return diagnosis


    async def test_planning(self, mock_state_file: str | None = None,
                          character: str | None = None,
                          goal: str | None = None,
                          start_level: int | None = None,
                          goal_level: int | None = None,
                          dry_run: bool = False) -> dict[str, Any]:
        """Test planning with mock scenarios and custom goals.

        Parameters:
            mock_state_file: Optional path to JSON file containing mock character state
            character: Optional character name for real character testing
            goal: Optional custom goal string (e.g. 'move to (1,1)', 'gain xp')
            start_level: Optional starting character level for simulation
            goal_level: Optional target level for planning simulation
            dry_run: Whether to simulate without API calls

        Return values:
            Dictionary containing planning test results, scenarios, and performance metrics

        This method enables testing of GOAP planning algorithms using mock scenarios
        and simulated character states, providing validation of planning logic without
        requiring live character data or API interactions.
        """
        test_results = {
            "test_time": "",
            "planning_available": self.planning_diagnostics is not None,
            "scenarios_tested": [],
            "overall_success": True,
            "performance_summary": {},
            "issues": [],
            "recommendations": []
        }

        # Add timestamp
        test_results["test_time"] = datetime.now().isoformat()

        if not self.planning_diagnostics:
            test_results["recommendations"].append(
                "Planning test unavailable - GoalManager required for testing"
            )
            test_results["overall_success"] = False
            return test_results

        try:
            # Load mock state if provided
            start_state = {}
            if mock_state_file:
                try:
                    state_file = Path(mock_state_file)
                    if state_file.exists():
                        with state_file.open('r') as f:
                            state_data = json.load(f)

                        # Convert string keys to GameState enums
                        for key, value in state_data.items():
                            try:
                                enum_key = GameState(key)
                                start_state[enum_key] = value
                            except ValueError:
                                test_results["issues"].append(f"Invalid state key in mock file: {key}")
                    else:
                        test_results["issues"].append(f"Mock state file not found: {mock_state_file}")

                except FileNotFoundError as e:
                    test_results["issues"].append(f"Mock state file not found: {e.filename}")
                except (json.JSONDecodeError, ValueError) as e:
                    test_results["issues"].append(f"Invalid mock state file format: {str(e)}")
                except (OSError, PermissionError) as e:
                    test_results["issues"].append(f"File system error loading mock state: {str(e)}")

            # Create default start state if not loaded from file
            if not start_state:
                start_state = {
                    GameState.CHARACTER_LEVEL: start_level or 1,
                    GameState.CHARACTER_XP: 0,
                    GameState.CHARACTER_GOLD: 100,
                    GameState.HP_CURRENT: 100,
                    GameState.HP_MAX: 100,
                    GameState.CURRENT_X: 0,
                    GameState.CURRENT_Y: 0,
                    GameState.COOLDOWN_READY: True
                }

            # Handle custom character and goal testing
            if character and goal:
                try:
                    # Get real character state if testing with a specific character
                    if self.api_client:
                        api_character = await self.api_client.get_character(character)
                        game_map = await self.api_client.get_map(api_character.x, api_character.y)
                        CharacterGameState.from_api_character(
                            api_character, game_map.content, self.api_client.cooldown_manager
                        )

                        # Test planning with real character state and custom goal
                        planning_result = await self.diagnose_plan(
                            character_name=character,
                            goal=goal,
                            verbose=False
                        )

                        test_results["scenarios_tested"].append({
                            "name": f"Custom Goal Test: {character} -> {goal}",
                            "success": planning_result.get("planning_successful", False),
                            "cost": planning_result.get("total_cost", 0),
                            "time": planning_result.get("planning_time", 0),
                            "character": character,
                            "goal": goal
                        })

                        # Update overall success
                        if not planning_result.get("planning_successful", False):
                            test_results["overall_success"] = False
                            test_results["issues"].append(f"Custom goal planning failed: {goal}")
                    else:
                        test_results["issues"].append("API client required for character-based testing")
                        test_results["overall_success"] = False

                except (AttributeError, TypeError) as e:
                    test_results["issues"].append(f"Component error during custom goal test: {type(e).__name__}: {str(e)}")
                    test_results["overall_success"] = False
                except ValueError as e:
                    test_results["issues"].append(f"Invalid goal configuration: {str(e)}")
                    test_results["overall_success"] = False

            # Test scenarios
            scenarios = []

            # Scenario 1: Level progression
            if goal_level:
                scenarios.append({
                    "name": "Level Progression",
                    "goal_state": {GameState.CHARACTER_LEVEL: goal_level},
                    "description": f"Increase character level from {start_state.get(GameState.CHARACTER_LEVEL, 1)} to {goal_level}"
                })

            # Scenario 2: Gold accumulation
            scenarios.append({
                "name": "Gold Accumulation",
                "goal_state": {GameState.CHARACTER_GOLD: 1000},
                "description": "Accumulate 1000 gold"
            })

            # Scenario 3: Position movement
            scenarios.append({
                "name": "Position Movement",
                "goal_state": {GameState.CURRENT_X: 5, GameState.CURRENT_Y: 5},
                "description": "Move to position (5, 5)"
            })

            # Test each scenario
            total_planning_time = 0.0
            successful_scenarios = 0

            for scenario in scenarios:
                scenario_result = {
                    "name": scenario["name"],
                    "description": scenario["description"],
                    "success": False,
                    "planning_time": 0.0,
                    "plan_length": 0,
                    "reachable": False,
                    "issues": []
                }

                try:
                    goal_state = scenario["goal_state"]

                    # Test reachability
                    scenario_result["reachable"] = await self.planning_diagnostics.test_goal_reachability(
                        start_state, goal_state
                    )

                    # Measure planning performance
                    performance = await self.planning_diagnostics.measure_planning_performance(
                        start_state, goal_state
                    )

                    scenario_result["planning_time"] = performance.get("planning_time_seconds", 0.0)
                    scenario_result["plan_length"] = performance.get("plan_length", 0)
                    scenario_result["success"] = performance.get("success", False)

                    if performance.get("error"):
                        scenario_result["issues"].append(performance["error"])

                    total_planning_time += scenario_result["planning_time"]

                    if scenario_result["success"]:
                        successful_scenarios += 1

                except (AttributeError, TypeError) as e:
                    scenario_result["issues"].append(f"Component error during scenario test: {type(e).__name__}: {str(e)}")
                except ValueError as e:
                    scenario_result["issues"].append(f"Invalid scenario configuration: {str(e)}")

                test_results["scenarios_tested"].append(scenario_result)

            # Calculate summary metrics
            test_results["performance_summary"] = {
                "total_scenarios": len(scenarios),
                "successful_scenarios": successful_scenarios,
                "success_rate": (successful_scenarios / len(scenarios) * 100) if scenarios else 0,
                "total_planning_time": total_planning_time,
                "average_planning_time": (total_planning_time / len(scenarios)) if scenarios else 0
            }

            # Overall success assessment
            test_results["overall_success"] = successful_scenarios > 0

            # Generate recommendations
            if successful_scenarios == 0:
                test_results["recommendations"].append("No scenarios succeeded - check planning implementation")
            elif successful_scenarios < len(scenarios):
                test_results["recommendations"].append(f"Only {successful_scenarios}/{len(scenarios)} scenarios succeeded - investigate failures")

            if total_planning_time > 5.0:
                test_results["recommendations"].append("Planning is slow - consider optimization")

            if test_results["issues"]:
                test_results["recommendations"].append(f"Fix {len(test_results['issues'])} identified issues")

        except (AttributeError, TypeError) as e:
            test_results["issues"].append(f"Component error during test execution: {type(e).__name__}: {str(e)}")
            test_results["overall_success"] = False
        except ValueError as e:
            test_results["issues"].append(f"Invalid test configuration: {str(e)}")
            test_results["overall_success"] = False

        return test_results

    async def diagnose_weights(self, show_action_costs: bool = False) -> dict[str, Any]:
        """Diagnose action weights and GOAP configuration.

        Parameters:
            show_action_costs: Whether to display detailed action cost breakdowns

        Return values:
            Dictionary containing weight analysis, configuration validation, and optimization suggestions

        This method analyzes the GOAP action weights and configuration settings
        to identify potential optimization opportunities, validate weight balance,
        and ensure effective planning performance for the AI player system.
        """
        diagnosis = {
            "diagnostic_time": "",
            "action_diagnostics_available": self.action_diagnostics is not None,
            "cost_analysis": {
                "total_actions_analyzed": 0,
                "cost_distribution": {},
                "cost_statistics": {},
                "outliers": []
            },
            "configuration_validation": {
                "valid": True,
                "warnings": [],
                "errors": []
            },
            "optimization_opportunities": [],
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        if not self.action_diagnostics:
            diagnosis["configuration_validation"]["valid"] = False
            diagnosis["configuration_validation"]["errors"].append("ActionRegistry not available for weight analysis")
            diagnosis["recommendations"].append(
                "Weight diagnostics unavailable - ActionRegistry required for analysis"
            )
            return diagnosis

        try:
            # Validate action costs
            cost_warnings = self.action_diagnostics.validate_action_costs()
            diagnosis["configuration_validation"]["warnings"] = cost_warnings
            if cost_warnings:
                diagnosis["configuration_validation"]["valid"] = False

            # Analyze action costs in detail
            action_types = self.action_registry.get_all_action_types()
            costs = []
            cost_by_type = {}
            action_details = []

            for action_class in action_types:
                try:
                    action_instance = action_class()
                    cost = action_instance.cost
                    action_name = action_instance.name
                    action_type = action_class.__name__.replace("Action", "")

                    costs.append(cost)

                    if action_type not in cost_by_type:
                        cost_by_type[action_type] = []
                    cost_by_type[action_type].append(cost)

                    if show_action_costs:
                        action_details.append({
                            "name": action_name,
                            "type": action_type,
                            "cost": cost,
                            "class": action_class.__name__
                        })

                except TypeError:
                    # Parameterized action
                    action_type = action_class.__name__.replace("Action", "")
                    if show_action_costs:
                        action_details.append({
                            "name": f"{action_class.__name__} (parameterized)",
                            "type": action_type,
                            "cost": "Variable",
                            "class": action_class.__name__
                        })
                except (AttributeError, TypeError) as e:
                    diagnosis["configuration_validation"]["errors"].append(
                        f"Component error analyzing {action_class.__name__}: {type(e).__name__}: {str(e)}"
                    )
                except ValueError as e:
                    diagnosis["configuration_validation"]["errors"].append(
                        f"Data validation error analyzing {action_class.__name__}: {str(e)}"
                    )

            diagnosis["cost_analysis"]["total_actions_analyzed"] = len(costs)

            if show_action_costs:
                diagnosis["cost_analysis"]["action_details"] = action_details

            # Calculate cost statistics
            if costs:
                diagnosis["cost_analysis"]["cost_statistics"] = {
                    "min_cost": min(costs),
                    "max_cost": max(costs),
                    "average_cost": sum(costs) / len(costs),
                    "median_cost": sorted(costs)[len(costs) // 2],
                    "cost_range": max(costs) - min(costs)
                }

                # Analyze cost distribution by type
                diagnosis["cost_analysis"]["cost_distribution"] = {}
                for action_type, type_costs in cost_by_type.items():
                    diagnosis["cost_analysis"]["cost_distribution"][action_type] = {
                        "count": len(type_costs),
                        "average": sum(type_costs) / len(type_costs),
                        "min": min(type_costs),
                        "max": max(type_costs)
                    }

                # Identify cost outliers
                avg_cost = diagnosis["cost_analysis"]["cost_statistics"]["average_cost"]
                outlier_threshold = avg_cost * 3  # Actions costing more than 3x average

                for action_class in action_types:
                    try:
                        action_instance = action_class()
                        if action_instance.cost > outlier_threshold:
                            diagnosis["cost_analysis"]["outliers"].append({
                                "name": action_instance.name,
                                "cost": action_instance.cost,
                                "multiplier": action_instance.cost / avg_cost
                            })
                    except TypeError:
                        continue
                    except (AttributeError, TypeError, ValueError):
                        # Skip actions that can't be analyzed due to missing data or methods
                        continue

            # Detect conflicts between actions
            try:
                conflicts = self.action_diagnostics.detect_action_conflicts()
                if conflicts:
                    diagnosis["configuration_validation"]["warnings"].extend(conflicts)
                    diagnosis["configuration_validation"]["valid"] = False
            except (AttributeError, TypeError) as e:
                diagnosis["configuration_validation"]["errors"].append(f"Component error during conflict detection: {type(e).__name__}: {str(e)}")
            except ValueError as e:
                diagnosis["configuration_validation"]["errors"].append(f"Invalid data during conflict detection: {str(e)}")

            # Generate optimization opportunities
            stats = diagnosis["cost_analysis"]["cost_statistics"]
            if stats:
                if stats["cost_range"] > stats["average_cost"] * 10:
                    diagnosis["optimization_opportunities"].append(
                        "Large cost variance detected - consider normalizing action costs"
                    )

                if stats["max_cost"] > 1000:
                    diagnosis["optimization_opportunities"].append(
                        "Very high cost actions detected - may slow down planning"
                    )

                if stats["min_cost"] <= 0:
                    diagnosis["optimization_opportunities"].append(
                        "Zero or negative cost actions detected - may cause planning issues"
                    )

            # Check for unbalanced action types
            distribution = diagnosis["cost_analysis"]["cost_distribution"]
            if distribution:
                type_counts = {t: d["count"] for t, d in distribution.items()}
                max_count = max(type_counts.values())
                min_count = min(type_counts.values())

                if max_count > min_count * 5:
                    diagnosis["optimization_opportunities"].append(
                        "Unbalanced action type distribution - some types heavily overrepresented"
                    )

            # Generate recommendations
            if diagnosis["cost_analysis"]["outliers"]:
                diagnosis["recommendations"].append(
                    f"Review {len(diagnosis['cost_analysis']['outliers'])} high-cost outlier actions"
                )

            if diagnosis["configuration_validation"]["warnings"]:
                diagnosis["recommendations"].append(
                    f"Address {len(diagnosis['configuration_validation']['warnings'])} configuration warnings"
                )

            if diagnosis["configuration_validation"]["errors"]:
                diagnosis["recommendations"].append(
                    f"Fix {len(diagnosis['configuration_validation']['errors'])} configuration errors"
                )

            if diagnosis["optimization_opportunities"]:
                diagnosis["recommendations"].append(
                    f"Consider {len(diagnosis['optimization_opportunities'])} optimization opportunities"
                )

        except (AttributeError, TypeError) as e:
            diagnosis["configuration_validation"]["errors"].append(f"Component error during weight analysis: {type(e).__name__}: {str(e)}")
            diagnosis["configuration_validation"]["valid"] = False
        except ValueError as e:
            diagnosis["configuration_validation"]["errors"].append(f"Data validation error during weight analysis: {str(e)}")
            diagnosis["configuration_validation"]["valid"] = False

        return diagnosis

    async def diagnose_cooldowns(self, character_name: str, monitor: bool = False) -> dict[str, Any]:
        """Diagnose cooldown management and timing.

        Parameters:
            character_name: Name of the character to monitor cooldown status
            monitor: Whether to provide continuous cooldown monitoring

        Return values:
            Dictionary containing cooldown status, timing analysis, and compliance metrics

        This method analyzes character cooldown management including timing accuracy,
        API compliance, and cooldown prediction for troubleshooting timing issues
        and ensuring proper action execution scheduling.
        """
        diagnosis = {
            "character_name": character_name,
            "diagnostic_time": "",
            "api_available": self.api_client is not None,
            "cooldown_manager_available": self.cooldown_manager is not None,
            "cooldown_status": {
                "ready": None,
                "estimated_ready_time": None,
                "last_action_time": None,
                "compliance_status": "unknown"
            },
            "timing_analysis": {
                "api_cooldown_seconds": 30,  # Standard ArtifactsMMO cooldown
                "precision_issues": [],
                "timing_warnings": []
            },
            "monitoring_data": [],
            "recommendations": []
        }

        # Add timestamp
        diagnosis["diagnostic_time"] = datetime.now().isoformat()

        if not self.api_client or not self.cooldown_manager:
            diagnosis["recommendations"].append(
                "API client and cooldown manager not available - initialize DiagnosticCommands with APIClientWrapper for real cooldown data"
            )

            # If monitoring is requested, provide placeholder monitoring data
            if monitor:
                current_time = datetime.now()
                diagnosis["monitoring_data"] = [{
                    "timestamp": current_time.isoformat(),
                    "status": "monitoring_started",
                    "notes": "Continuous monitoring would track cooldown state changes over time"
                }]

                diagnosis["recommendations"].append(
                    "Monitoring mode requires background task to track cooldown state changes"
                )

            return diagnosis

        try:
            # Get real character data from API to check current state
            character_data = await self.api_client.get_character(character_name)
            diagnosis["character_found"] = True

            # Check current cooldown status from cooldown manager
            cooldown_info = self.cooldown_manager.get_cooldown_info(character_name)
            is_ready = self.cooldown_manager.is_ready(character_name)
            remaining_time = self.cooldown_manager.get_remaining_time(character_name)

            diagnosis["cooldown_status"]["ready"] = is_ready
            diagnosis["cooldown_status"]["remaining_seconds"] = remaining_time
            diagnosis["cooldown_status"]["compliance_status"] = "compliant" if is_ready else "on_cooldown"

            if cooldown_info:
                diagnosis["cooldown_status"]["estimated_ready_time"] = cooldown_info.expiration
                diagnosis["cooldown_status"]["reason"] = cooldown_info.reason
                diagnosis["cooldown_status"]["total_seconds"] = cooldown_info.total_seconds

            # Perform timing analysis
            if remaining_time > 0:
                if remaining_time > 35:  # Standard cooldown is 30 seconds, warn if too long
                    diagnosis["timing_analysis"]["timing_warnings"].append(
                        f"Cooldown remaining time ({remaining_time:.1f}s) exceeds standard API cooldown"
                    )

                if remaining_time < 0:
                    diagnosis["timing_analysis"]["precision_issues"].append(
                        "Negative remaining time detected - cooldown calculation issue"
                    )

            # Validate cooldown compliance
            if is_ready:
                diagnosis["recommendations"].append("Character is ready for action execution")
            else:
                diagnosis["recommendations"].append(
                    f"Character on cooldown for {remaining_time:.1f}s - wait before executing actions"
                )

            # Additional character-specific analysis
            if hasattr(character_data, 'speed') and character_data.speed:
                diagnosis["timing_analysis"]["character_speed"] = character_data.speed
                if character_data.speed < 1:
                    diagnosis["timing_analysis"]["timing_warnings"].append(
                        "Low character speed may affect movement timing calculations"
                    )

            # If monitoring is requested, set up real monitoring data
            if monitor:
                current_time = datetime.now()
                diagnosis["monitoring_data"] = [{
                    "timestamp": current_time.isoformat(),
                    "status": "active_monitoring",
                    "cooldown_ready": is_ready,
                    "remaining_seconds": remaining_time,
                    "character_level": character_data.level,
                    "character_hp": character_data.hp,
                    "character_position": {"x": character_data.x, "y": character_data.y}
                }]

                # For real monitoring, we would set up a background task
                # For now, provide the current snapshot
                diagnosis["recommendations"].append(
                    "Monitoring enabled - use continuous polling for real-time cooldown tracking"
                )

            # Validate character state for common issues
            if character_data.hp <= 0:
                diagnosis["timing_analysis"]["timing_warnings"].append(
                    "Character HP is 0 - may affect action execution and cooldown behavior"
                )

            if character_data.hp < character_data.max_hp * 0.3:
                diagnosis["recommendations"].append(
                    "Low HP detected - consider rest action before combat activities"
                )

        except (ConnectionError, TimeoutError) as e:
            diagnosis["character_found"] = False
            diagnosis["cooldown_status"]["compliance_status"] = "network_error"
            diagnosis["recommendations"].append(f"Network error during cooldown diagnostics: {type(e).__name__}: {str(e)}")
            diagnosis["timing_analysis"]["precision_issues"].append(f"API access failed due to network issue: {str(e)}")
        except (AttributeError, TypeError) as e:
            diagnosis["character_found"] = False
            diagnosis["cooldown_status"]["compliance_status"] = "component_error"
            diagnosis["recommendations"].append(f"Component error during cooldown diagnostics: {type(e).__name__}: {str(e)}")
            diagnosis["timing_analysis"]["precision_issues"].append(f"System component issue: {str(e)}")
        except ValueError as e:
            diagnosis["character_found"] = False
            diagnosis["cooldown_status"]["compliance_status"] = "data_error"
            diagnosis["recommendations"].append(f"Invalid cooldown data: {str(e)}")
            diagnosis["timing_analysis"]["precision_issues"].append(f"Data validation failed: {str(e)}")

        return diagnosis

    def format_state_output(self, diagnostic_result: dict[str, Any]) -> str:
        """Format state diagnostic results for CLI display.

        Parameters:
            diagnostic_result: Full diagnostic result dictionary from diagnose_state()

        Return values:
            Formatted string representation suitable for CLI output

        This method formats complete state diagnostic results into a human-readable
        format for CLI display, including validation, statistics, and recommendations.
        """
        lines = []

        # Header
        character_name = diagnostic_result.get("character_name", "Unknown")
        lines.append(f"=== STATE DIAGNOSTICS: {character_name} ===")

        # API character data if available
        if "api_character_data" in diagnostic_result:
            lines.append("\n=== API CHARACTER DATA ===")
            char_data = diagnostic_result["api_character_data"]
            lines.append(f"Level: {char_data.get('level', 'N/A')}")
            lines.append(f"XP: {char_data.get('xp', 'N/A')}")
            lines.append(f"Gold: {char_data.get('gold', 'N/A')}")
            lines.append(f"HP: {char_data.get('hp', 'N/A')}/{char_data.get('max_hp', 'N/A')}")
            position = char_data.get('position', {})
            lines.append(f"Position: ({position.get('x', 'N/A')}, {position.get('y', 'N/A')})")
            lines.append(f"Skin: {char_data.get('skin', 'N/A')}")

        # State validation
        validation = diagnostic_result.get("state_validation", {})
        lines.append("\n=== STATE VALIDATION ===")
        lines.append(f"Valid: {validation.get('valid', 'Unknown')}")

        issues = validation.get("issues", [])
        if issues:
            lines.append(f"Issues ({len(issues)}):")
            for issue in issues:
                lines.append(f"  • {issue}")

        missing_keys = validation.get("missing_required_keys", [])
        if missing_keys:
            lines.append(f"Missing required keys: {missing_keys}")

        invalid_values = validation.get("invalid_values", [])
        if invalid_values:
            lines.append(f"Invalid values: {invalid_values}")

        # State statistics
        stats = diagnostic_result.get("state_statistics", {})
        if stats:
            lines.append("\n=== STATE STATISTICS ===")
            lines.append(f"Character level: {stats.get('character_level', 'N/A')}")
            lines.append(f"Total XP: {stats.get('total_xp', 'N/A')}")
            lines.append(f"Gold: {stats.get('gold', 'N/A')}")
            lines.append(f"HP percentage: {stats.get('hp_percentage', 0):.1f}%")
            lines.append(f"Total skill levels: {stats.get('total_skill_levels', 0)}")
            lines.append(f"Average skill level: {stats.get('average_skill_level', 0):.1f}")
            lines.append(f"Progress to max: {stats.get('progress_to_max', 0):.1f}%")

        # Cooldown status
        if "cooldown_status" in diagnostic_result:
            cooldown = diagnostic_result["cooldown_status"]
            lines.append("\n=== COOLDOWN STATUS ===")
            lines.append(f"On cooldown: {cooldown.get('on_cooldown', 'Unknown')}")
            lines.append(f"Remaining seconds: {cooldown.get('remaining_seconds', 'N/A')}")
            if cooldown.get('reason'):
                lines.append(f"Reason: {cooldown['reason']}")

        # Recommendations
        recommendations = diagnostic_result.get("recommendations", [])
        if recommendations:
            lines.append(f"\n=== RECOMMENDATIONS ({len(recommendations)}) ===")
            for rec in recommendations:
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def format_action_output(self, diagnostic_result: dict[str, Any]) -> str:
        """Format action diagnostic results for CLI display.

        Parameters:
            diagnostic_result: Full diagnostic result dictionary from diagnose_actions()

        Return values:
            Formatted string representation suitable for CLI output

        This method formats complete action diagnostic results into a readable format
        for CLI display, including action analysis, summary, and recommendations.
        """
        # Handle empty or None input
        if not diagnostic_result:
            return "No action data to display"

        lines = []

        # Header
        character_name = diagnostic_result.get("character_name", "All Actions")
        lines.append(f"=== ACTION DIAGNOSTICS: {character_name} ===")

        # Registry status
        registry_available = diagnostic_result.get("registry_available", False)
        lines.append(f"Action registry available: {registry_available}")

        # Summary
        summary = diagnostic_result.get("summary", {})
        total_actions = summary.get("total_actions", 0)
        lines.append(f"Total actions analyzed: {total_actions}")

        if total_actions > 0:
            executable_actions = summary.get("executable_actions", 0)
            cost_range = summary.get("cost_range", {})
            lines.append(f"Executable actions: {executable_actions}")
            lines.append(f"Cost range: {cost_range.get('min', 0)} - {cost_range.get('max', 0)}")

            action_types = summary.get("action_types", {})
            if action_types:
                lines.append(f"Action types: {', '.join(f'{k}({v})' for k, v in action_types.items())}")

        # Registry validation
        registry_validation = diagnostic_result.get("registry_validation", {})
        valid = registry_validation.get("valid", True)
        lines.append(f"Registry validation: {'✓ Valid' if valid else '✗ Invalid'}")

        errors = registry_validation.get("errors", [])
        if errors:
            lines.append(f"\nRegistry errors ({len(errors)}):")
            for error in errors:
                lines.append(f"  • {error}")

        warnings = registry_validation.get("warnings", [])
        if warnings:
            lines.append(f"\nRegistry warnings ({len(warnings)}):")
            for warning in warnings:
                lines.append(f"  • {warning}")

        # Individual action analysis
        actions_analyzed = diagnostic_result.get("actions_analyzed", [])
        if actions_analyzed:
            lines.append(f"\n=== INDIVIDUAL ACTIONS ({len(actions_analyzed)}) ===")
            for i, action_info in enumerate(actions_analyzed):
                lines.append(f"\n[{i+1}] Action: {action_info.get('name', 'Unknown')}")
                lines.append(f"    Class: {action_info.get('class', 'Unknown')}")
                lines.append(f"    Cost: {action_info.get('cost', 'N/A')}")
                lines.append(f"    Executable: {action_info.get('executable', 'Unknown')}")

                if 'preconditions' in action_info and action_info['preconditions']:
                    lines.append("    Preconditions:")
                    for key, value in action_info['preconditions'].items():
                        lines.append(f"      {key}: {value}")

                if 'effects' in action_info and action_info['effects']:
                    lines.append("    Effects:")
                    for key, value in action_info['effects'].items():
                        lines.append(f"      {key}: {value}")

                validation_info = action_info.get('validation', {})
                if validation_info:
                    precond_valid = validation_info.get('preconditions_valid', 'Unknown')
                    effects_valid = validation_info.get('effects_valid', 'Unknown')
                    lines.append(f"    Validation: preconditions={precond_valid}, effects={effects_valid}")

                if 'issues' in action_info and action_info['issues']:
                    lines.append("    Issues:")
                    for issue in action_info['issues']:
                        lines.append(f"      • {issue}")

        # Recommendations
        recommendations = diagnostic_result.get("recommendations", [])
        if recommendations:
            lines.append(f"\n=== RECOMMENDATIONS ({len(recommendations)}) ===")
            for rec in recommendations:
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def format_planning_output(self, diagnostic_result: dict[str, Any]) -> str:
        """Format planning diagnostic results for CLI display.

        Parameters:
            diagnostic_result: Full diagnostic result dictionary from diagnose_plan()

        Return values:
            Formatted string representation suitable for CLI planning visualization

        This method formats complete planning diagnostic results into a visual representation
        for CLI display, showing planning analysis, performance metrics, and recommendations.
        """
        # Handle empty or None input
        if not diagnostic_result:
            return "No planning data to display"

        lines = []

        # Header
        character_name = diagnostic_result.get("character_name", "Unknown")
        goal = diagnostic_result.get("goal", "Unknown")
        lines.append(f"=== PLANNING DIAGNOSTICS: {character_name} ===")
        lines.append(f"Goal: {goal}")

        # Planning availability
        planning_available = diagnostic_result.get("planning_available", False)
        lines.append(f"Planning system available: {planning_available}")

        # Planning analysis
        analysis = diagnostic_result.get("planning_analysis", {})
        if analysis:
            lines.append("\n=== PLANNING ANALYSIS ===")
            success = analysis.get('planning_successful', False)
            lines.append(f"Planning successful: {success}")

            goal_reachable = analysis.get('goal_reachable', 'Unknown')
            lines.append(f"Goal reachable: {goal_reachable}")

            # Basic metrics
            total_cost = analysis.get('total_cost', 0)
            planning_time = analysis.get('planning_time', 0.0)
            lines.append(f"Total cost: {total_cost}")
            lines.append(f"Planning time: {planning_time:.3f} seconds")

            # Issues
            issues = analysis.get('issues', [])
            if issues:
                lines.append(f"\nIssues ({len(issues)}):")
                for issue in issues:
                    lines.append(f"  • {issue}")

            # Plan steps
            steps = analysis.get('steps', [])
            if steps:
                lines.append(f"\nPlan steps ({len(steps)} actions):")
                for i, step in enumerate(steps):
                    step_name = step.get('name', f'Step {i+1}')
                    step_cost = step.get('cost', 1)
                    lines.append(f"  [{i+1}] {step_name} (cost: {step_cost})")

            # State transitions
            transitions = analysis.get('state_transitions', [])
            if transitions:
                lines.append(f"\nState Transitions ({len(transitions)}):")
                for transition in transitions:
                    step_num = transition.get('step', '?')
                    action_name = transition.get('action', 'Unknown')
                    lines.append(f"  Step {step_num}: {action_name}")

        # Plan efficiency
        efficiency = diagnostic_result.get("plan_efficiency", {})
        if efficiency:
            lines.append("\n=== PLAN EFFICIENCY ===")
            efficiency_score = efficiency.get('efficiency_score', 0)
            lines.append(f"Efficiency score: {efficiency_score:.2f}")

            suggestions = efficiency.get('optimization_suggestions', [])
            if suggestions:
                lines.append("Optimization suggestions:")
                for suggestion in suggestions:
                    lines.append(f"  • {suggestion}")

        # Bottlenecks
        bottlenecks = diagnostic_result.get("bottlenecks", [])
        if bottlenecks:
            lines.append(f"\n=== BOTTLENECKS ({len(bottlenecks)}) ===")
            for bottleneck in bottlenecks:
                lines.append(f"  • {bottleneck}")

        # Performance metrics
        performance = diagnostic_result.get("performance_metrics", {})
        if performance:
            lines.append("\n=== PERFORMANCE METRICS ===")
            planning_time = performance.get('planning_time_seconds', 0)
            success = performance.get('success', False)
            performance_class = performance.get('performance_class', 'unknown')
            lines.append(f"Planning time: {planning_time:.3f}s")
            lines.append(f"Success: {success}")
            lines.append(f"Performance class: {performance_class}")

            if 'error' in performance:
                lines.append(f"Error: {performance['error']}")

        # Recommendations
        recommendations = diagnostic_result.get("recommendations", [])
        if recommendations:
            lines.append(f"\n=== RECOMMENDATIONS ({len(recommendations)}) ===")
            for rec in recommendations:
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def validate_state_keys(self, state_dict: dict[str, Any]) -> list[str]:
        """Validate that all state keys exist in GameState enum.

        Parameters:
            state_dict: Dictionary with string keys representing game state

        Return values:
            List of invalid state keys that don't exist in GameState enum

        This method validates state dictionary keys against the GameState enum
        to identify invalid keys that could cause runtime errors, ensuring
        type safety throughout the state management system.
        """
        return self.state_diagnostics.validate_state_enum_usage(state_dict)
