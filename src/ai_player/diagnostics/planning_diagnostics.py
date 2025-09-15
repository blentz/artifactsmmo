"""
Planning Diagnostics Module

Provides diagnostic functions for GOAP planning process visualization and troubleshooting.
Includes step-by-step planning analysis, goal reachability testing, and planning
performance metrics for CLI diagnostic commands.
"""

import sys
from datetime import datetime
from typing import Any

from ..goal_manager import GoalManager
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState


class PlanningDiagnostics:
    """GOAP planning diagnostic utilities"""

    def __init__(self, goal_manager: GoalManager):
        """Initialize PlanningDiagnostics with goal manager reference.

        Parameters:
            goal_manager: GoalManager instance for planning analysis

        Return values:
            None (constructor)

        This constructor initializes the planning diagnostics system with
        access to the goal manager for comprehensive GOAP planning analysis,
        visualization, and troubleshooting capabilities.
        """
        self.goal_manager = goal_manager

    async def analyze_planning_steps(
        self, start_state: "CharacterGameState", goal_state: dict[GameState, Any]
    ) -> dict[str, Any]:
        """Analyze step-by-step GOAP planning process.

        Parameters:
            start_state: CharacterGameState instance defining initial state
            goal_state: Dictionary with GameState enum keys defining target state

        Return values:
            Dictionary containing detailed analysis of each planning step

        This method provides step-by-step analysis of the GOAP planning
        process including action selection, state transitions, and cost
        calculations for debugging planning algorithm behavior.
        """
        analysis: dict[str, Any] = {
            "planning_successful": False,
            "steps": [],
            "total_cost": 0,
            "planning_time": 0.0,
            "issues": [],
            "state_transitions": [],
        }

        start_time = datetime.now()

        # Use the goal manager's planning functionality with CharacterGameState
        from ..types.goap_models import GOAPTargetState

        target_state = GOAPTargetState(target_states=goal_state)
        plan = await self.goal_manager.plan_actions(start_state, target_state)

        # Handle both GOAPActionPlan and list types for compatibility
        is_empty = False
        if hasattr(plan, "is_empty"):
            is_empty = plan.is_empty
        elif isinstance(plan, list):
            is_empty = len(plan) == 0
        else:
            is_empty = plan is None

        if plan and not is_empty:
            analysis["planning_successful"] = True

            # Handle both GOAPActionPlan and legacy list formats
            if hasattr(plan, "to_legacy_plan"):
                # GOAPActionPlan format
                analysis["steps"] = plan.to_legacy_plan()
                analysis["total_cost"] = plan.total_cost
                actions = plan.actions
            else:
                # Legacy list format
                analysis["steps"] = plan
                analysis["total_cost"] = sum(action.get("cost", 1) for action in plan)
                actions = plan

            # Analyze state transitions - start_state must be CharacterGameState
            current_state = start_state.to_goap_state()
            for i, action in enumerate(actions):
                # Handle both GOAPAction objects and dict formats
                if hasattr(action, "name"):
                    action_name = action.name
                    action_dict = action.to_dict() if hasattr(action, "to_dict") else {"name": action_name}
                else:
                    action_name = action.get("name", f"action_{i}")
                    action_dict = action

                analysis["state_transitions"].append(
                    {
                        "step": i + 1,
                        "action": action_name,
                        "state_before": dict(current_state),
                        "estimated_state_after": self._estimate_state_after_action(current_state, action_dict),
                    }
                )
        else:
            analysis["issues"].append("No plan found - goal may be unreachable")

        end_time = datetime.now()
        analysis["planning_time"] = (end_time - start_time).total_seconds()

        return analysis

    async def test_goal_reachability(self, start_state: CharacterGameState, goal_state: dict[GameState, Any]) -> bool:
        """Test if goal is reachable from start state.

        Parameters:
            start_state: CharacterGameState instance defining initial state
            goal_state: Dictionary with GameState enum keys defining target state

        Return values:
            Boolean indicating whether goal is reachable with available actions

        This method tests whether the specified goal can be reached from
        the start state using available actions, identifying impossible
        goals before attempting expensive planning operations.
        """
        # Check if the goal manager can determine reachability
        if hasattr(self.goal_manager, "is_goal_achievable"):
            # Handle both CharacterGameState objects and dictionary states
            if hasattr(start_state, "to_goap_state"):
                # Convert CharacterGameState to dict format that GoalManager expects
                current_state_dict = start_state.to_goap_state()
                # Convert string keys back to GameState enums
                current_state_enum_dict = {
                    GameState(k): v for k, v in current_state_dict.items() if k in [gs.value for gs in GameState]
                }
            else:
                # start_state is already a dictionary with GameState enum keys
                current_state_enum_dict = start_state
            return self.goal_manager.is_goal_achievable(goal_state, current_state_enum_dict)

        # Simple heuristic checks for obviously unreachable goals
        for goal_key, goal_value in goal_state.items():
            current_value = start_state.get(goal_key)

            # Character level cannot decrease
            if goal_key == GameState.CHARACTER_LEVEL:
                if isinstance(current_value, int) and isinstance(goal_value, int):
                    if goal_value < current_value:
                        return False

            # XP cannot decrease
            xp_keys = {
                GameState.CHARACTER_XP,
                GameState.MINING_XP,
                GameState.WOODCUTTING_XP,
                GameState.FISHING_XP,
                GameState.WEAPONCRAFTING_XP,
                GameState.GEARCRAFTING_XP,
                GameState.JEWELRYCRAFTING_XP,
                GameState.COOKING_XP,
                GameState.ALCHEMY_XP,
            }
            if goal_key in xp_keys:
                if isinstance(current_value, int) and isinstance(goal_value, int):
                    if goal_value < current_value:
                        return False

        # Try a quick planning attempt
        from ..types.goap_models import GOAPTargetState

        target_state = GOAPTargetState(target_states=goal_state)
        plan = await self.goal_manager.plan_actions(start_state, target_state)

        # Handle both GOAPActionPlan and list types for compatibility
        if plan is None:
            return False
        if hasattr(plan, "is_empty"):
            return not plan.is_empty
        elif isinstance(plan, list):
            return len(plan) > 0
        else:
            return False

    def visualize_plan(self, plan: list[dict[str, Any]]) -> str:
        """Create visual representation of action plan.

        Parameters:
            plan: List of action dictionaries representing the planned sequence

        Return values:
            String containing visual representation suitable for CLI display

        This method creates a visual representation of the action plan
        showing action sequences, state transitions, and dependencies
        for clear understanding of the planning result.
        """
        if not plan:
            return "No plan to visualize"

        lines = []
        lines.append("=== ACTION PLAN VISUALIZATION ===")
        lines.append(f"Total actions: {len(plan)}")
        lines.append("")

        for i, action in enumerate(plan):
            action_name = action.get("name", f"Action_{i + 1}")
            action_cost = action.get("cost", 1)

            # Create visual step indicator
            if i == 0:
                lines.append("START")

            lines.append("  |")
            lines.append("  v")
            lines.append(f"[{i + 1}] {action_name} (cost: {action_cost})")

            # Add any additional action details if available
            if "preconditions" in action:
                lines.append(f"    Requires: {action['preconditions']}")
            if "effects" in action:
                lines.append(f"    Results: {action['effects']}")

        lines.append("  |")
        lines.append("  v")
        lines.append("GOAL ACHIEVED")

        return "\n".join(lines)

    def _estimate_state_after_action(
        self, current_state: dict[GameState, Any], action: dict[str, Any]
    ) -> dict[GameState, Any]:
        """Helper method to estimate state after executing an action."""
        new_state = current_state.copy()

        # Apply action effects if available
        if "effects" in action:
            for key, value in action["effects"].items():
                if isinstance(key, str):
                    # Convert string key to GameState enum if possible
                    try:
                        enum_key = GameState(key)
                        new_state[enum_key] = value
                    except ValueError:
                        # Invalid key, skip
                        continue
                else:
                    new_state[key] = value

        return new_state

    def analyze_plan_efficiency(self, plan: "GOAPActionPlan") -> dict[str, Any]:
        """Analyze plan for efficiency and optimization opportunities.

        Parameters:
            plan: GOAPActionPlan to analyze for efficiency

        Return values:
            Dictionary containing efficiency analysis and optimization suggestions

        This method analyzes the generated plan for efficiency including
        redundant actions, suboptimal sequences, and potential optimizations
        to improve GOAP planning performance and execution time.
        """
        analysis: dict[str, Any] = {
            "total_actions": 0,  # Will be set below
            "total_cost": 0,  # Will be set below
            "efficiency_score": 0.0,
            "redundant_actions": [],
            "optimization_suggestions": [],
            "action_types": {},
        }

        # Check if plan is empty using compatibility approach
        is_empty = False
        if hasattr(plan, "is_empty"):
            is_empty = plan.is_empty
        elif isinstance(plan, list):
            is_empty = len(plan) == 0
        else:
            is_empty = plan is None

        if is_empty:
            return analysis

        # Get actions list - handle both formats
        if hasattr(plan, "actions"):
            actions = plan.actions
            total_cost = plan.total_cost
        else:
            actions = plan
            total_cost = sum(action.get("cost", 1) for action in plan)

        analysis["total_actions"] = len(actions)
        analysis["total_cost"] = total_cost

        # Calculate action type distribution
        for action in actions:
            # Handle both GOAPAction objects and dict formats
            if hasattr(action, "name"):
                action_name = action.name
            else:
                action_name = action.get("name", "unknown")

            action_type = action_name.split("_")[0] if "_" in action_name else action_name
            analysis["action_types"][action_type] = analysis["action_types"].get(action_type, 0) + 1

        # Look for redundant sequences
        for i in range(len(actions) - 1):
            if hasattr(actions[i], "name"):
                current_action = actions[i].name
                next_action = actions[i + 1].name
            else:
                current_action = actions[i].get("name", "unknown")
                next_action = actions[i + 1].get("name", "unknown")

            # Check for repeated actions
            if current_action == next_action:
                analysis["redundant_actions"].append(f"Repeated action at steps {i + 1}-{i + 2}: {current_action}")

        # Calculate efficiency score (higher is better)
        if analysis["total_cost"] > 0:
            # Simple efficiency metric: fewer total actions with lower cost is better
            analysis["efficiency_score"] = 100.0 / (analysis["total_cost"] + analysis["total_actions"])

        # Generate optimization suggestions
        if analysis["total_actions"] > 10:
            analysis["optimization_suggestions"].append("Plan is quite long - consider if goal can be simplified")

        if len(analysis["action_types"]) == 1:
            analysis["optimization_suggestions"].append(
                "Plan uses only one action type - verify if more diverse actions are available"
            )

        return analysis

    def simulate_plan_execution(self, plan: list[dict[str, Any]], start_state: dict[GameState, Any]) -> dict[str, Any]:
        """Simulate plan execution to predict final state.

        Parameters:
            plan: List of action dictionaries to simulate execution for
            start_state: Dictionary with GameState enum keys defining initial state

        Return values:
            Dictionary containing simulation results and predicted final state

        This method simulates the execution of a plan from the start state
        to predict the final state, validating that the plan achieves the
        intended goal and identifying potential execution issues.
        """
        simulation: dict[str, Any] = {
            "success": True,
            "final_state": start_state.copy(),
            "execution_steps": [],
            "issues": [],
        }

        current_state = start_state.copy()

        for i, action in enumerate(plan):
            step_info = {
                "step": i + 1,
                "action": action.get("name", "unknown"),
                "state_before": dict(current_state),
                "executed": False,
                "issues": [],
            }

            # Check if action preconditions would be met
            preconditions = action.get("preconditions", {})
            preconditions_met = True

            for key, required_value in preconditions.items():
                if isinstance(key, str):
                    enum_key = GameState(key)
                else:
                    enum_key = key

                current_value = current_state.get(enum_key)
                if current_value != required_value:
                    preconditions_met = False
                    step_info["issues"].append(
                        f"Precondition not met: {enum_key.value} = {current_value}, required {required_value}"
                    )

            if preconditions_met:
                # Apply action effects
                effects = action.get("effects", {})
                for key, value in effects.items():
                    if isinstance(key, str):
                        enum_key = GameState(key)
                        current_state[enum_key] = value
                    else:
                        current_state[key] = value

                step_info["executed"] = True
            else:
                simulation["success"] = False
                step_info["executed"] = False

            step_info["state_after"] = dict(current_state)
            simulation["execution_steps"].append(step_info)

        simulation["final_state"] = current_state

        # Collect all issues
        for step in simulation["execution_steps"]:
            simulation["issues"].extend(step["issues"])

        return simulation

    async def identify_planning_bottlenecks(
        self, start_state: CharacterGameState, goal_state: dict[GameState, Any]
    ) -> list[str]:
        """Identify what prevents efficient planning.

        Parameters:
            start_state: CharacterGameState instance defining initial state
            goal_state: Dictionary with GameState enum keys defining target state

        Return values:
            List of identified bottlenecks that slow down or prevent planning

        This method identifies factors that hinder efficient planning including
        missing actions, unreachable states, and performance bottlenecks
        that affect GOAP algorithm effectiveness.
        """
        bottlenecks = []

        # Check for unreachable goals
        if not await self.test_goal_reachability(start_state, goal_state):
            bottlenecks.append("Goal appears to be unreachable from current state")

        # Get state as dict once
        start_state_dict = start_state.to_goap_state()

        # Check for large state space
        state_diff = len(goal_state) + len(start_state_dict)
        if state_diff > 20:
            bottlenecks.append("Large state space may slow down planning")

        # Check for very high goal values
        for key, value in goal_state.items():
            current_value = start_state_dict.get(key.value, 0)
            if isinstance(value, int) and isinstance(current_value, int):
                if value > current_value + 100:
                    bottlenecks.append(f"Large gap in {key.value}: {current_value} -> {value}")

        # Check if actions are available
        # Try to get some actions from goal manager
        actions = await self.goal_manager.create_goap_actions(start_state)
        if not actions or len(actions.conditions) == 0:
            bottlenecks.append("No actions available for planning")

        # Check for missing required state keys
        required_keys = {GameState.CHARACTER_LEVEL, GameState.COOLDOWN_READY}
        missing_keys = [key for key in required_keys if key.value not in start_state_dict]
        if missing_keys:
            bottlenecks.append(f"Missing required state keys: {[k.value for k in missing_keys]}")

        return bottlenecks

    async def measure_planning_performance(
        self, start_state: CharacterGameState, goal_state: dict[GameState, Any]
    ) -> dict[str, Any]:
        """Measure planning algorithm performance metrics.

        Parameters:
            start_state: CharacterGameState instance defining initial state
            goal_state: Dictionary with GameState enum keys defining target state

        Return values:
            Dictionary containing performance metrics and timing analysis

        This method measures GOAP planning performance including execution
        time, memory usage, nodes explored, and algorithm efficiency for
        optimization and troubleshooting planning performance issues.
        """
        metrics: dict[str, Any] = {"planning_time_seconds": 0.0, "plan_length": 0, "success": False, "error": None}

        start_time = datetime.now()

        # Measure memory before planning - handle both CharacterGameState objects and dictionaries
        if hasattr(start_state, "to_goap_state"):
            start_state_dict = start_state.to_goap_state()
        else:
            # start_state is already a dictionary
            start_state_dict = start_state
        initial_memory = sys.getsizeof(start_state_dict) + sys.getsizeof(goal_state)

        # Attempt planning
        from ..types.goap_models import GOAPTargetState

        target_state = GOAPTargetState(target_states=goal_state)

        # Convert dictionary state to CharacterGameState if needed
        if not hasattr(start_state, "to_goap_state"):
            # Create a CharacterGameState from the dictionary
            from ..state.character_game_state import CharacterGameState

            # Extract values from the state dictionary with defaults
            start_state_obj = CharacterGameState(
                name="test_character",
                level=start_state.get(GameState.CHARACTER_LEVEL, 1),
                xp=start_state.get(GameState.CHARACTER_XP, 0),
                gold=start_state.get(GameState.CHARACTER_GOLD, 0),
                hp=start_state.get(GameState.HP_CURRENT, 100),
                max_hp=start_state.get(GameState.HP_MAX, 100),
                x=start_state.get(GameState.CURRENT_X, 0),
                y=start_state.get(GameState.CURRENT_Y, 0),
                mining_level=start_state.get(GameState.MINING_LEVEL, 1),
                mining_xp=start_state.get(GameState.MINING_XP, 0),
                woodcutting_level=start_state.get(GameState.WOODCUTTING_LEVEL, 1),
                woodcutting_xp=start_state.get(GameState.WOODCUTTING_XP, 0),
                fishing_level=start_state.get(GameState.FISHING_LEVEL, 1),
                fishing_xp=start_state.get(GameState.FISHING_XP, 0),
                weaponcrafting_level=start_state.get(GameState.WEAPONCRAFTING_LEVEL, 1),
                weaponcrafting_xp=start_state.get(GameState.WEAPONCRAFTING_XP, 0),
                gearcrafting_level=start_state.get(GameState.GEARCRAFTING_LEVEL, 1),
                gearcrafting_xp=start_state.get(GameState.GEARCRAFTING_XP, 0),
                jewelrycrafting_level=start_state.get(GameState.JEWELRYCRAFTING_LEVEL, 1),
                jewelrycrafting_xp=start_state.get(GameState.JEWELRYCRAFTING_XP, 0),
                cooking_level=start_state.get(GameState.COOKING_LEVEL, 1),
                cooking_xp=start_state.get(GameState.COOKING_XP, 0),
                alchemy_level=start_state.get(GameState.ALCHEMY_LEVEL, 1),
                alchemy_xp=start_state.get(GameState.ALCHEMY_XP, 0),
                cooldown=0,
            )
        else:
            start_state_obj = start_state

        plan = await self.goal_manager.plan_actions(start_state_obj, target_state)

        # Check plan success with compatibility approach
        is_empty = False
        if plan is None:
            is_empty = True
        elif hasattr(plan, "is_empty"):
            is_empty = plan.is_empty
        elif isinstance(plan, list):
            is_empty = len(plan) == 0
        else:
            is_empty = True

        if plan and not is_empty:
            metrics["success"] = True
            metrics["plan_length"] = len(plan.actions) if hasattr(plan, "actions") else len(plan)
        else:
            metrics["success"] = False
            metrics["plan_length"] = 0

        end_time = datetime.now()
        metrics["planning_time_seconds"] = (end_time - start_time).total_seconds()

        # Simple memory usage estimate
        metrics["memory_usage_estimate"] = initial_memory

        # Performance classification
        planning_time = metrics["planning_time_seconds"]
        if planning_time is not None and planning_time < 0.1:
            metrics["performance_class"] = "fast"
        elif planning_time is not None and planning_time < 1.0:
            metrics["performance_class"] = "acceptable"
        else:
            metrics["performance_class"] = "slow"

        return metrics

    def validate_plan_feasibility(self, plan: list[dict[str, Any]], start_state: dict[GameState, Any]) -> list[str]:
        """Validate that plan is actually executable.

        Parameters:
            plan: List of action dictionaries to validate for feasibility
            start_state: Dictionary with GameState enum keys defining initial state

        Return values:
            List of feasibility issues found in the plan

        This method validates that the generated plan is actually executable
        by checking action preconditions, state transitions, and resource
        requirements to identify potential execution failures.
        """
        issues = []

        if not plan:
            return ["Plan is empty - nothing to validate"]

        # Use simulation to validate feasibility
        simulation_result = self.simulate_plan_execution(plan, start_state)

        if not simulation_result["success"]:
            issues.append("Plan simulation failed - plan is not feasible")
            issues.extend(simulation_result["issues"])

        # Additional feasibility checks
        current_state = start_state.copy()

        for i, action in enumerate(plan):
            action_name = action.get("name", f"Action_{i + 1}")

            # Check for invalid action structure
            if "name" not in action:
                issues.append(f"Action at step {i + 1} missing name")

            # Check for unrealistic state transitions
            preconditions = action.get("preconditions", {})
            effects = action.get("effects", {})

            # Validate that effects are reasonable given preconditions
            for effect_key, effect_value in effects.items():
                if isinstance(effect_key, str):
                    try:
                        enum_key = GameState(effect_key)
                    except ValueError:
                        issues.append(f"Action {action_name} has invalid effect key: {effect_key}")
                        continue
                else:
                    enum_key = effect_key

                # Check for logical inconsistencies
                if enum_key in preconditions:
                    precond_value = preconditions[enum_key]
                    if effect_value == precond_value:
                        issues.append(f"Action {action_name} sets {enum_key.value} to same value as precondition")

            # Update state for next iteration
            for key, value in effects.items():
                if isinstance(key, str):
                    try:
                        enum_key = GameState(key)
                        current_state[enum_key] = value
                    except ValueError:
                        continue
                else:
                    current_state[key] = value

        return issues
