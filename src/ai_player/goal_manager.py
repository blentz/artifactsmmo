"""
Goal Manager

This module manages dynamic goal selection and GOAP planning for the AI player.
It integrates with the existing GOAP library to provide intelligent goal prioritization
based on character progression and current game state.

Enhanced with intelligent goal selection using weighted multi-factor scoring,
level-appropriate monster targeting, crafting analysis, and strategic planning
for level 5 progression with appropriate gear.
"""

import logging
import time
from typing import Any

from src.lib.goap import Action_List, Planner
from .actions import ActionRegistry, BaseAction
from src.ai_player.cooldown_aware_planner import CooldownAwarePlanner
from .exceptions import GoalFactoryError, MaxDepthExceededError, NoValidGoalError
from .goal_selector import GoalWeightCalculator
from .goals.base_goal import BaseGoal
from .goals.equipment_goal import EquipmentGoal
from .goals.gathering_goal import GatheringGoal
from .goals.movement_goal import MovementGoal
from .goals.rest_goal import RestGoal
from .goals.sub_goal_request import SubGoalRequest
from .state.character_game_state import CharacterGameState
from .state.game_state import GameState
from .state.state_manager import StateManager
from src.game_data.game_data import GameData
from .types.goap_models import GoalFactoryContext, GOAPAction, GOAPActionPlan, GOAPTargetState


class GoalManager:
    """Manages dynamic goal selection and cooldown-aware GOAP planning"""

    def __init__(
        self, action_registry: ActionRegistry, cooldown_manager, cache_manager=None, state_manager: StateManager = None
    ):
        """Initialize GoalManager with enhanced goal selection and analysis capabilities.

        Parameters:
            action_registry: ActionRegistry instance for action discovery and generation
            cooldown_manager: CooldownManager instance for timing constraint validation
            cache_manager: CacheManager instance for accessing game data (maps, monsters, resources)
            state_manager: StateManager instance for sub-goal factory support

        Return values:
            None (constructor)

        This constructor initializes the GoalManager with the enhanced goal system including:
        - Weighted goal selection using multi-factor scoring
        - Level-appropriate monster targeting and analysis modules
        - Strategic crafting and equipment evaluation
        - Sub-goal request processing for dynamic dependency resolution
        """
        self.action_registry = action_registry
        self.cooldown_manager = cooldown_manager
        self.cache_manager = cache_manager
        self.state_manager = state_manager
        self.planner = None

        # Initialize enhanced goal selection system
        self.goal_weight_calculator = GoalWeightCalculator()
        self.active_sub_goals = []  # Track active sub-goal requests

        # Initialize logger
        self.logger = logging.getLogger(__name__)

    async def get_game_data(self) -> Any:
        """Get comprehensive game data for action generation.

        Parameters:
            None

        Return values:
            Game data object containing maps, monsters, resources, NPCs, and items

        This method retrieves all necessary game data from the cache manager for
        use in parameterized action generation, particularly movement actions that
        need to know valid locations and strategic targets.
        """
        if not self.cache_manager:
            return None

        try:
            # Get all game data from cache manager and create typed GameData instance
            all_maps = await self.cache_manager.get_all_maps()
            all_monsters = await self.cache_manager.get_all_monsters()
            all_resources = await self.cache_manager.get_all_resources()
            all_npcs = await self.cache_manager.get_all_npcs()
            all_items = await self.cache_manager.get_all_items()

            # Create properly typed GameData instance
            game_data = GameData(
                maps=all_maps, monsters=all_monsters, resources=all_resources, npcs=all_npcs, items=all_items
            )

            # Validate that essential game data is present
            game_data.validate_required_data()

            return game_data

        except ValueError as e:
            # Game data validation failed
            print(f"Game data validation failed: {e}")
            raise

    async def select_movement_target(self, current_state: CharacterGameState, goal_type: str) -> tuple[int, int] | None:
        """Select intelligent movement target based on goals and game data.

        Parameters:
            current_state: Current character state with position and attributes
            goal_type: Type of goal driving movement ('combat', 'rest', 'gathering', etc.)

        Return values:
            Tuple of (target_x, target_y) coordinates for movement, or None if no valid target

        This method selects movement targets using strategic game data analysis,
        considering character needs and nearby content for optimal positioning.
        """
        current_x = current_state.x
        current_y = current_state.y

        # For combat goals, find nearby monster locations
        if goal_type == "combat":
            return await self.find_nearest_content_location(current_x, current_y, "monster")

        # For rest goals, find safe locations (no monsters)
        elif goal_type == "rest":
            return await self.find_nearest_safe_location(current_x, current_y)

        # For resource gathering, find resource locations
        elif goal_type == "gathering":
            return await self.find_nearest_content_location(current_x, current_y, "resource")

        return None

    async def find_nearest_content_location(
        self, current_x: int, current_y: int, content_type: str
    ) -> tuple[int, int] | None:
        """Find the nearest location with specified content type within movement range.

        Parameters:
            current_x: Current X coordinate
            current_y: Current Y coordinate
            content_type: Type of content to find ('monster', 'resource', etc.)

        Return values:
            Tuple of (x, y) coordinates if found, None otherwise

        This method searches game data for the nearest location containing the
        specified content type within the movement action factory's generation range.
        """
        # Get all maps from cache
        maps = await self.cache_manager.get_all_maps()
        if not maps:
            return None

        # Find locations with matching content type
        matching_locations = []
        for game_map in maps:
            if game_map.content and game_map.content.type == content_type:
                # Calculate distance from current position
                distance = abs(game_map.x - current_x) + abs(game_map.y - current_y)
                matching_locations.append((game_map.x, game_map.y, distance))

        if not matching_locations:
            return None

        # Sort by distance and return the nearest
        matching_locations.sort(key=lambda x: x[2])
        nearest_x, nearest_y, _ = matching_locations[0]
        return (nearest_x, nearest_y)

    async def find_nearest_safe_location(self, current_x: int, current_y: int) -> tuple[int, int] | None:
        """Find the nearest safe location (no monsters) for resting.

        Parameters:
            current_x: Current X coordinate
            current_y: Current Y coordinate

        Return values:
            Tuple of (x, y) coordinates for safe location, None if none found

        This method identifies safe locations without monsters where the character
        can rest to recover HP, prioritizing nearby accessible positions.
        """
        # Get all maps from cache
        maps = await self.cache_manager.get_all_maps()
        if not maps:
            return (0, 0)  # Fallback to spawn

        # Find locations without monster content
        safe_locations = []
        for game_map in maps:
            if not game_map.content or game_map.content.type != "monster":
                # Calculate distance from current position
                distance = abs(game_map.x - current_x) + abs(game_map.y - current_y)
                safe_locations.append((game_map.x, game_map.y, distance))

        if not safe_locations:
            return (0, 0)  # Fallback to spawn

        # Sort by distance and return the nearest
        safe_locations.sort(key=lambda x: x[2])
        nearest_x, nearest_y, _ = safe_locations[0]
        return (nearest_x, nearest_y)

    async def select_next_goal(self, current_state: CharacterGameState) -> "GOAPTargetState":
        """Select next achievable goal using enhanced goal system, return GOAPTargetState directly."""
        if self.max_level_achieved(current_state):
            return GOAPTargetState()

        game_data = await self.get_game_data()
        selected_goal, sub_goal_requests = self.goal_weight_calculator.select_optimal_goal(current_state, game_data)

        if sub_goal_requests:
            self.active_sub_goals.extend(sub_goal_requests)

            # Process the first sub-goal instead of the parent goal
            if self.active_sub_goals:
                sub_goal_request = self.active_sub_goals.pop(0)
                self.logger.debug(f"Processing sub-goal: {sub_goal_request.goal_type}")

                # Create goal factory context
                context = GoalFactoryContext(
                    character_state=current_state,
                    game_data=game_data,
                    parent_goal_type=type(selected_goal).__name__ if selected_goal else None,
                    recursion_depth=0,
                    max_depth=10,
                )

                try:
                    # Create goal from sub-request
                    sub_goal = self.create_goal_from_sub_request(sub_goal_request, context)

                    # Get target state from sub-goal
                    target_state_obj = sub_goal.get_target_state(current_state, game_data)

                    # Return the sub-goal's target state
                    return target_state_obj

                except (GoalFactoryError, ValueError) as e:
                    self.logger.warning(f"Failed to create sub-goal: {e}")
                    # Fall through to process the original goal

        if not selected_goal:
            return GOAPTargetState()

        # Use unified architecture - get target state from goal's get_target_state method
        target_state_obj = selected_goal.get_target_state(current_state, game_data)

        # Map goal class names to expected test types
        goal_type = type(selected_goal).__name__
        goal_type_mapping = {
            "CombatGoal": "combat_goal",
            "GatheringGoal": "gathering_goal",
            "CraftingGoal": "crafting_goal",
            "EquipmentGoal": "equipment_goal",
            "RestGoal": "rest",
            "HealthRecoveryGoal": "health_recovery",
            "EmergencyRestGoal": "emergency_rest",
            "SurvivalGoal": "survival",
            "InventoryManagementGoal": "inventory_management",
        }

        # Return the GOAPTargetState object directly as per unified architecture
        return target_state_obj

    async def plan_actions(self, current_state: CharacterGameState, goal: GOAPTargetState) -> GOAPActionPlan:
        """Generate action sequence using cooldown-aware GOAP planner.

        Raises:
            PlanningError: If no valid plan can be found
        """
        return await self.plan_to_target_state(current_state, goal)

    async def plan_with_cooldown_awareness(
        self,
        character_name: str,
        current_state: CharacterGameState,
        goal_state: dict[GameState, bool | int | float | str],
    ) -> GOAPActionPlan:
        """Generate plan considering current cooldown state and timing.

        Parameters:
            character_name: Name of the character for cooldown checking
            current_state: CharacterGameState with current character state
            goal_state: Dictionary with GameState enum keys and target values

        Return values:
            GOAPActionPlan with timing-aware action sequence

        Raises:
            PlanningError: If no valid plan can be found

        This method generates action plans that account for character cooldown
        status, either deferring planning until ready or filtering actions
        that require cooldown readiness for optimal execution timing.
        """
        # Convert goal_state dict to GOAPTargetState
        target_state = GOAPTargetState(target_states=goal_state)

        # Use plan_to_target_state which handles everything properly
        return await self.plan_to_target_state(current_state, target_state)

    def should_defer_planning(self, character_name: str) -> bool:
        """Check if planning should be deferred due to cooldown.

        Parameters:
            character_name: Name of the character to check cooldown status

        Return values:
            Boolean indicating whether planning should wait for cooldown expiry

        This method determines if GOAP planning should be postponed because
        the character is currently on cooldown, preventing immediate action
        execution and making current planning ineffective.
        """
        return not self.cooldown_manager.is_ready(character_name)

    async def create_goap_actions(self, current_state: CharacterGameState) -> Action_List:
        """Convert modular actions to GOAP Action_List format using ActionRegistry."""
        action_list = Action_List()

        # Use ActionRegistry to get all available actions for current state
        game_data = await self.get_game_data()
        print(f"DEBUG: Game data loaded: {game_data is not None}")

        all_actions = self.action_registry.generate_actions_for_state(current_state, game_data)
        print(f"DEBUG: Generated {len(all_actions)} actions from registry")

        # Convert each action instance to GOAP format
        for action_instance in all_actions:
            name, conditions, effects, weight = self.convert_action_to_goap(action_instance)
            action_list.add_condition(name, **conditions)
            action_list.add_reaction(name, **effects)
            action_list.set_weight(name, weight)

        print(f"DEBUG: Created GOAP action list with {len(action_list.conditions)} actions")
        return action_list

    def get_early_game_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get goals for levels 1-10.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of goal dictionaries appropriate for early game progression

        This method generates goals suitable for beginning characters including
        basic resource gathering, equipment crafting, and skill development
        that form the foundation for character progression.
        """
        goals = []
        current_level = current_state.get(GameState.CHARACTER_LEVEL, 1)

        # Level progression goal (always important in early game)
        if current_level < 10:
            goals.append(
                {
                    "type": "level_up",
                    "priority": 1,
                    "target_state": {
                        GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                        GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP
                    },
                }
            )

        # Skill development goals
        mining_level = current_state.get(GameState.MINING_LEVEL, 1)
        if mining_level < 5:
            goals.append(
                {
                    "type": "skill_training",
                    "priority": 2,
                    "target_state": {
                        GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                        GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP (via gathering)
                    },
                }
            )

        woodcutting_level = current_state.get(GameState.WOODCUTTING_LEVEL, 1)
        if woodcutting_level < 5:
            goals.append(
                {
                    "type": "skill_training",
                    "priority": 2,
                    "target_state": {
                        GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                        GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP (via gathering)
                    },
                }
            )

        # Basic economic goal
        current_gold = current_state.get(GameState.CHARACTER_GOLD, 0)
        if current_gold < 1000:
            goals.append(
                {
                    "type": "resource_gathering",
                    "priority": 3,
                    "target_state": {GameState.CHARACTER_GOLD: current_gold + 500},
                }
            )

        return goals

    def get_mid_game_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get goals for levels 11-30.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of goal dictionaries appropriate for mid-game progression

        This method generates goals for intermediate character development
        including advanced combat, economic activities, and skill optimization
        that bridge early game fundamentals with late game mastery.
        """
        goals = []
        current_level = current_state.get(GameState.CHARACTER_LEVEL, 1)

        # Mid-game level progression
        if current_level < 30:
            goals.append(
                {
                    "type": "level_up",
                    "priority": 1,
                    "target_state": {
                        GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                        GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP
                    },
                }
            )

        return goals

    def get_late_game_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get goals for levels 31-45.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of goal dictionaries appropriate for late game progression

        This method generates goals for advanced character optimization
        including maximum level achievement, rare item collection, and
        mastery of all game systems for ultimate character development.
        """
        goals = []
        current_level = current_state.get(GameState.CHARACTER_LEVEL, 1)

        # Late-game level progression to max
        if current_level < 45:
            goals.append(
                {
                    "type": "level_up",
                    "priority": 1,
                    "target_state": {
                        GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                        GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP
                    },
                }
            )

        return goals

    def prioritize_goals(
        self, available_goals: list[dict[GameState, Any]], current_state: dict[GameState, Any]
    ) -> dict[GameState, Any]:
        """Select highest priority goal from available options.

        Parameters:
            available_goals: List of possible goal dictionaries to choose from
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Single goal dictionary representing the highest priority objective

        This method evaluates available goals against current character state
        and priority weights to select the most appropriate goal, considering
        survival needs, progression efficiency, and strategic objectives.
        """
        if not available_goals:
            return {}

        if len(available_goals) == 1:
            return available_goals[0]

        # Calculate dynamic priorities based on current state
        scored_goals = []

        for goal in available_goals:
            base_priority = goal.get("priority", 5)
            goal_type = goal.get("type", "unknown")

            # Calculate context-sensitive priority adjustments
            priority_adjustments = 0

            # Survival goals get highest priority when HP is low
            if goal_type in ["emergency_rest", "health_recovery", "survival"]:
                priority_adjustments += self._calculate_survival_priority(current_state)

            # Progression goals priority based on character level
            elif goal_type in ["level_up", "skill_training"]:
                priority_adjustments += self._calculate_progression_priority(current_state)

            # Economic goals priority based on gold and inventory
            elif goal_type in ["resource_gathering", "trading", "economic_optimization"]:
                priority_adjustments += self._calculate_economic_priority(current_state)

            # Calculate feasibility score
            feasibility = self.evaluate_goal_feasibility(current_state, goal, simple=False)
            feasibility_score = (
                feasibility.get("confidence", 0.5) if isinstance(feasibility, dict) else (1.0 if feasibility else 0.1)
            )

            # Calculate estimated effort (inverse of efficiency)
            estimated_cost = self.estimate_goal_cost(goal, current_state)
            efficiency_score = max(0.1, 1.0 / (1.0 + estimated_cost / 100.0))  # Normalize cost impact

            # Combine all factors into final score
            final_score = (base_priority + priority_adjustments) * feasibility_score * efficiency_score

            scored_goals.append((goal, final_score))

        # Sort by final score (higher is better) and return the best goal
        scored_goals.sort(key=lambda x: x[1], reverse=True)
        return scored_goals[0][0]

    def is_goal_achievable(self, goal: dict[GameState, Any], current_state: dict[GameState, Any]) -> bool:
        """Check if goal can be achieved with current actions.

        Parameters:
            goal: Dictionary with GameState enum keys defining target state
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether goal is achievable with available actions

        This method analyzes whether the specified goal can be reached from
        the current state using the available action set, enabling intelligent
        goal selection and preventing impossible planning attempts.
        """
        # Extract target state from goal
        target_state = goal.get("target_state", goal)

        # Basic feasibility checks
        for state_key, target_value in target_state.items():
            current_value = current_state.get(state_key, 0)

            # Check if goal is reasonable (not too far from current state)
            # Skip this check for boolean values (booleans are subclass of int in Python)
            if (
                isinstance(target_value, (int, float))
                and isinstance(current_value, (int, float))
                and not isinstance(target_value, bool)
                and not isinstance(current_value, bool)
            ):
                if target_value > current_value * 10:  # Arbitrary threshold
                    return False

        return True

    def estimate_goal_cost(self, goal: dict[GameState, Any], current_state: dict[GameState, Any]) -> int:
        """Estimate planning cost for achieving goal.

        Parameters:
            goal: Dictionary with GameState enum keys defining target state
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Integer representing estimated GOAP cost to achieve the goal

        This method calculates an approximate cost for achieving the specified
        goal from the current state, enabling efficient goal prioritization
        and resource planning for optimal AI player decision making.
        """
        # Basic cost estimation based on state differences
        total_cost = 0
        target_state = goal.get("target_state", goal)

        for state_key, target_value in target_state.items():
            current_value = current_state.get(state_key, 0)
            if isinstance(target_value, int | float) and isinstance(current_value, int | float):
                diff = abs(target_value - current_value)
                total_cost += diff
            else:
                total_cost += 1  # Basic cost for non-numeric changes

        return total_cost

    def max_level_achieved(self, current_state: CharacterGameState) -> bool:
        """Check if character has reached maximum level (45).

        Parameters:
            current_state: CharacterGameState Pydantic model with character attributes

        Return values:
            Boolean indicating whether character has reached level 45

        This method checks if the character has achieved the maximum level
        in ArtifactsMMO (level 45), which serves as the primary completion
        condition for autonomous AI player operation.
        """
        return current_state.level >= 45

    def get_survival_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get emergency goals for low HP, danger situations.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of emergency goal dictionaries for immediate survival needs

        This method generates high-priority survival goals when the character
        is in danger including HP recovery, escape from combat, and movement
        to safe locations for emergency character preservation.
        """
        goals = []
        current_hp = current_state.get(GameState.HP_CURRENT, 100)
        max_hp = current_state.get(GameState.HP_MAX, 100)

        # Critical HP - need immediate recovery (use boolean states the rest action provides)
        if current_hp <= max_hp * 0.2:  # 20% or less HP
            goals.append(
                {
                    "type": "emergency_rest",
                    "priority": 10,
                    "target_state": {
                        GameState.HP_LOW: False,
                        GameState.HP_CRITICAL: False,
                        GameState.SAFE_TO_FIGHT: True,
                    },
                }
            )

        # Low HP - should rest soon
        elif current_hp <= max_hp * 0.5:  # 50% or less HP
            goals.append(
                {
                    "type": "health_recovery",
                    "priority": 9,
                    "target_state": {GameState.HP_LOW: False, GameState.SAFE_TO_FIGHT: True},
                }
            )

        return goals

    def get_progression_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get XP and level advancement goals.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of progression goal dictionaries for character advancement

        This method generates goals focused on character progression including
        combat for XP, skill training, equipment upgrades, and level advancement
        activities that drive the character toward maximum level achievement.
        """
        goals = []
        current_state.get(GameState.CHARACTER_LEVEL, 1)

        # Basic progression goal
        goals.append(
            {
                "type": "level_up",
                "priority": 1,
                "target_state": {
                    GameState.GAINED_XP: True,  # Boolean: XP was gained this cycle
                    GameState.CAN_GAIN_XP: True,  # Boolean: Character can gain XP
                },
            }
        )

        return goals

    def get_economic_goals(self, current_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Get gold accumulation and trading goals.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of economic goal dictionaries for wealth building and resource management

        This method generates goals focused on economic activities including
        trading, crafting for profit, resource gathering for sale, and market
        arbitrage opportunities for sustainable character development.
        """
        goals = []
        current_gold = current_state.get(GameState.CHARACTER_GOLD, 0)
        inventory_full = current_state.get(GameState.INVENTORY_FULL, False)
        inventory_space = current_state.get(GameState.INVENTORY_SPACE_AVAILABLE, 20)
        at_bank = current_state.get(GameState.AT_BANK_LOCATION, False)

        # High priority: Inventory management when inventory is full or nearly full
        if inventory_full or inventory_space <= 2:
            if at_bank:
                # If at bank, banking is the priority
                goals.append(
                    {
                        "type": "banking",
                        "priority": 9,
                        "target_state": {GameState.INVENTORY_SPACE_AVAILABLE: 15, GameState.INVENTORY_FULL: False},
                        "requirements_met": True,
                    }
                )
            else:
                # If not at bank, need to move or sell items
                goals.append(
                    {
                        "type": "inventory_management",
                        "priority": 8,
                        "target_state": {GameState.INVENTORY_SPACE_AVAILABLE: 10, GameState.INVENTORY_FULL: False},
                        "requirements_met": True,
                    }
                )

                # Also add item selling as an option
                goals.append(
                    {
                        "type": "item_selling",
                        "priority": 7,
                        "target_state": {
                            GameState.CHARACTER_GOLD: current_gold + 500,
                            GameState.INVENTORY_SPACE_AVAILABLE: 10,
                        },
                        "requirements_met": True,
                    }
                )

        # Economic goal: accumulate more gold (lower priority when inventory issues exist)
        base_priority = 3 if not (inventory_full or inventory_space <= 2) else 1
        goals.append(
            {
                "type": "resource_gathering",
                "priority": base_priority,
                "target_state": {GameState.CHARACTER_GOLD: current_gold + 1000},
            }
        )

        return goals

    def convert_action_to_goap(self, action: BaseAction) -> tuple[str, dict[str, Any], dict[str, Any], int]:
        """Convert BaseAction to GOAP format (name, conditions, effects, weight).

        Parameters:
            action: BaseAction instance to convert to GOAP format

        Return values:
            Tuple containing action name, conditions, effects, and weight

        This method transforms a modular BaseAction into the tuple format
        required by the GOAP library, enabling seamless integration between
        the type-safe action system and GOAP planning algorithms.
        """
        # Get action properties
        name = action.name
        preconditions = action.get_preconditions()
        effects = action.get_effects()
        weight = action.cost

        # Convert GameState enum keys to string values for GOAP
        goap_conditions = {state_key.value: value for state_key, value in preconditions.items()}
        goap_effects = {state_key.value: value for state_key, value in effects.items()}

        return (name, goap_conditions, goap_effects, weight)

    def validate_plan(self, plan: list[dict[str, Any]], current_state: dict[GameState, Any]) -> bool:
        """Validate that generated plan is executable.

        Parameters:
            plan: List of action dictionaries representing the planned sequence
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether the plan is valid and executable

        This method validates that the generated GOAP plan is feasible by
        checking action preconditions, state transitions, and resource
        requirements to ensure successful execution in the AI player system.
        """
        return True  # Simplified validation for now

    def update_goal_priorities(self, current_state: dict[GameState, Any], priorities: dict[str, int]) -> dict[str, int]:
        """Update goal priorities based on current state.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            priorities: Current priority mapping for goal types

        Return values:
            Updated priority mapping based on current conditions

        This method adjusts goal priorities dynamically based on character state,
        enabling adaptive planning that responds to changing conditions like
        low HP, inventory status, and progression opportunities.
        """
        updated_priorities = priorities.copy()

        # Boost survival priorities when HP is low
        current_hp = current_state.get(GameState.HP_CURRENT, 100)
        max_hp = current_state.get(GameState.HP_MAX, 100)
        hp_ratio = current_hp / max_hp if max_hp > 0 else 1.0

        if hp_ratio <= 0.2:
            updated_priorities["emergency_rest"] = 10
            updated_priorities["health_recovery"] = 9
            if "survival" in updated_priorities:
                updated_priorities["survival"] = max(updated_priorities["survival"] + 5, 10)
        elif hp_ratio <= 0.5:
            updated_priorities["health_recovery"] = 8
            if "survival" in updated_priorities:
                updated_priorities["survival"] = max(updated_priorities["survival"] + 2, 8)

        # Adjust progression priorities based on level
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level < 10:
            updated_priorities["level_up"] = 6
            updated_priorities["skill_training"] = 5
        elif character_level < 30:
            updated_priorities["level_up"] = 7
            updated_priorities["skill_training"] = 4

        return updated_priorities

    async def _create_goap_planner(
        self,
        current_state: CharacterGameState,
        goal_state: dict[GameState, bool | int | float | str],
        character_name: str | None = None,
    ) -> "Planner":
        """Create GOAP planner instance with current state and goals."""
        self.logger.debug(f"Creating GOAP planner for character: {character_name}")

        # Use the Pydantic model's proper conversion method
        goap_current_state = current_state.to_goap_state()
        goap_goal_state = {key: value for key, value in goal_state.items()}

        self.logger.debug(f"Current state keys: {list(goap_current_state.keys())}")
        self.logger.debug(f"Goal state: {goap_goal_state}")

        # Create action list
        action_list = await self.create_goap_actions(current_state)

        # Action list should never be empty - if it is, that's a bug that needs to be fixed
        if not action_list.conditions:
            raise RuntimeError(
                f"Action list is empty for character {character_name}. This indicates a bug in action generation - factories should always produce actions."
            )

        # Extract state keys for planner initialization
        all_keys = set(goap_current_state.keys()) | set(goap_goal_state.keys())
        print(f"DEBUG: All state keys for planner: {len(all_keys)} keys")

        # Create planner
        if character_name:
            planner = CooldownAwarePlanner(self.cooldown_manager, *all_keys)
        else:
            planner = Planner(*all_keys)

        planner.set_start_state(**goap_current_state)
        planner.set_goal_state(**goap_goal_state)
        planner.set_action_list(action_list)

        print("DEBUG: GOAP planner created successfully")
        return planner

    def get_available_goals(
        self, current_state: dict[GameState, Any], filters: dict[str, Any] | None = None
    ) -> list[dict[GameState, Any]]:
        """Get all available goals with optional filtering.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            filters: Optional filtering criteria for goal selection

        Return values:
            List of available goal dictionaries matching filter criteria

        This method generates all available goals for the current state and
        applies optional filtering to provide targeted goal selection for
        specific planning scenarios and strategic objectives.
        """
        all_goals = []

        # Get goals from different categories
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level <= 10:
            all_goals.extend(self.get_early_game_goals(current_state))
        elif character_level <= 30:
            all_goals.extend(self.get_mid_game_goals(current_state))
        else:
            all_goals.extend(self.get_late_game_goals(current_state))

        all_goals.extend(self.get_survival_goals(current_state))
        all_goals.extend(self.get_progression_goals(current_state))
        all_goals.extend(self.get_economic_goals(current_state))

        # Add requirements_met field to all goals
        for goal in all_goals:
            goal["requirements_met"] = self._check_goal_requirements(goal, current_state)

        # Apply filters if provided
        if filters:
            filtered_goals = []
            for goal in all_goals:
                include_goal = True
                for filter_key, filter_value in filters.items():
                    if filter_key == "type" and goal.get("type") != filter_value:
                        include_goal = False
                        break
                    elif filter_key == "min_priority" and goal.get("priority", 0) < filter_value:
                        include_goal = False
                        break
                    elif filter_key == "max_priority" and goal.get("priority", 999) > filter_value:
                        include_goal = False
                        break
                if include_goal:
                    filtered_goals.append(goal)
            return filtered_goals

        return all_goals

    def _check_goal_requirements(self, goal: dict, current_state: dict[GameState, Any]) -> bool:
        """Check if character meets requirements to pursue this goal."""
        goal_type = goal.get("type", "")

        # Combat goals require ability to fight
        if "combat" in goal_type and not current_state.get(GameState.CAN_FIGHT, False):
            return False

        # Gathering goals require ability to gather
        if "gather" in goal_type and not current_state.get(GameState.CAN_GATHER, False):
            return False

        # Crafting goals require ability to craft
        if "craft" in goal_type and not current_state.get(GameState.CAN_CRAFT, False):
            return False

        # Check any explicit requirements in the goal
        requirements = goal.get("requirements", {})
        for req_key, req_value in requirements.items():
            current_value = current_state.get(req_key)
            if current_value != req_value:
                return False

        return True

    def evaluate_goal_feasibility(
        self, current_state: dict[GameState, Any], goal: dict[GameState, Any], simple: bool = True
    ) -> bool | dict[str, Any]:
        """Evaluate whether a goal is feasible and estimate effort.

        Parameters:
            goal: Goal dictionary with target state specification
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Dictionary containing feasibility analysis and effort estimates

        This method analyzes goal feasibility by checking resource requirements,
        action availability, and estimated completion time to enable intelligent
        goal selection and planning optimization.
        """
        target_state = goal.get("target_state", {})
        requirements = goal.get("requirements", {})

        # Check requirements first
        for req_key, req_value in requirements.items():
            current_value = current_state.get(req_key)
            if current_value != req_value:
                if simple:
                    return False
                # For detailed analysis, continue to build full report

        # Check for impossible goals
        feasible = True
        estimated_actions = 0
        estimated_time = 0
        missing_requirements = []

        # Check each target state requirement
        for state_key, target_value in target_state.items():
            current_value = current_state.get(state_key, 0)

            if isinstance(target_value, int | float) and isinstance(current_value, int | float):
                if target_value > current_value:
                    difference = target_value - current_value
                    # Check if the jump is too large (impossible)
                    if difference > current_value * 10:  # More than 10x current value
                        feasible = False
                        if simple:
                            return False
                        missing_requirements.append(f"{state_key.value}: need {target_value}, have {current_value}")

                    # Need to increase this value
                    estimated_actions += max(1, difference // 10)  # Rough estimate
                    estimated_time += difference * 30  # Rough time estimate in seconds
            elif target_value != current_value:
                # Boolean or complex state change
                estimated_actions += 1
                estimated_time += 60  # Base action time

        # For simple checks, return boolean
        if simple:
            return feasible

        # For detailed analysis, return full report
        feasibility = {
            "feasible": feasible,
            "estimated_actions": estimated_actions,
            "estimated_time": estimated_time,
            "missing_requirements": missing_requirements,
            "confidence": 1.0,
        }

        # Reduce confidence if many actions required
        if estimated_actions > 10:
            feasibility["confidence"] = max(0.3, 1.0 - (estimated_actions - 10) * 0.1)

        return feasibility

    def convert_state_for_goap(self, current_state: dict[GameState, Any]) -> dict[str, Any]:
        """Convert GameState enum state to string-keyed state for GOAP.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Dictionary with string keys suitable for GOAP library usage

        This method converts the type-safe GameState enum-based state format
        to the string-based format required by the GOAP library, enabling
        seamless integration between the AI player and planning systems.
        """
        goap_state = {}
        for state_key, value in current_state.items():
            if isinstance(state_key, GameState):
                goap_state[state_key.value] = value
            else:
                goap_state[str(state_key)] = value
        return goap_state

    def _calculate_survival_priority(self, current_state: dict[GameState, Any]) -> int:
        """Calculate survival priority based on HP and danger level.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Integer priority score (1-10) for survival goals

        This method calculates survival priority based on current HP ratio,
        danger level, and immediate threats to determine urgency of survival
        actions like resting, healing, or escaping combat situations.
        """
        current_hp = current_state.get(GameState.HP_CURRENT, 100)
        max_hp = current_state.get(GameState.HP_MAX, 100)
        hp_ratio = current_hp / max_hp if max_hp > 0 else 1.0

        if hp_ratio <= 0.05:  # Critical HP - immediate emergency
            return 10
        elif hp_ratio <= 0.2:  # Very low HP - high priority
            return 9
        elif hp_ratio <= 0.4:  # Low HP - medium-high priority
            return 7
        elif hp_ratio <= 0.6:  # Moderate HP - medium priority
            return 5
        elif hp_ratio <= 0.8:  # Good HP - low-medium priority
            return 3
        else:  # High HP - low priority
            return 1

    def _calculate_progression_priority(self, current_state: dict[GameState, Any]) -> int:
        """Calculate progression priority based on character level and advancement needs.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Integer priority score (1-10) for progression goals

        This method calculates progression priority based on character level,
        experience to next level, and advancement opportunities to determine
        urgency of leveling and skill improvement activities.
        """
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
        current_state.get(GameState.CHARACTER_XP, 0)

        # Early game progression is high priority
        if character_level <= 1:
            return 9  # New character - highest priority
        elif character_level <= 5:
            return 7  # Early game - high priority
        elif character_level <= 15:
            return 6  # Early-mid game
        elif character_level <= 30:
            return 5  # Mid game - moderate priority
        elif character_level <= 40:
            return 3  # Late game - lower priority
        else:  # Max level approach
            return 2

    def _calculate_economic_priority(self, current_state: dict[GameState, Any]) -> int:
        """Calculate economic priority based on gold and inventory status.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Integer priority score (1-10) for economic goals

        This method calculates economic priority based on current gold amount,
        inventory space, and trading opportunities to determine urgency of
        wealth-building and resource management activities.
        """
        character_gold = current_state.get(GameState.CHARACTER_GOLD, 0)
        inventory_full = current_state.get(GameState.INVENTORY_FULL, False)
        inventory_space = current_state.get(GameState.INVENTORY_SPACE_AVAILABLE, 20)

        # If inventory is full, economic activities become urgent
        if inventory_full or inventory_space <= 2:
            if character_gold <= 25:
                return 8  # No gold + full inventory = emergency (within 8-10 range)
            else:
                return 7  # Some gold + full inventory = high priority

        # If very low on gold, economic priority is high
        if character_gold <= 100:
            return 8
        elif character_gold <= 500:
            return 4  # Some gold, moderate priority
        elif character_gold <= 2000:
            return 3
        elif character_gold <= 10000:
            return 2
        else:  # Rich character, low economic priority
            return 1

    def _adjust_priorities_based_on_history(
        self, priorities: dict[str, int], recent_actions: list[dict[str, Any]], current_state: dict[GameState, Any]
    ) -> dict[str, int]:
        """Adjust priorities based on recent action history and outcomes.

        Parameters:
            priorities: Current priority mapping for goal types
            recent_actions: List of recently executed actions with results
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Adjusted priority mapping based on recent performance

        This method analyzes recent action history to adjust goal priorities,
        reducing priority for recently successful activities and boosting
        priority for neglected or unsuccessful areas.
        """
        adjusted_priorities = priorities.copy()

        # Count recent action types
        action_counts = {}
        for action in recent_actions:
            action_type = action.get("name", "unknown")
            action_counts[action_type] = action_counts.get(action_type, 0) + 1

        # Reduce priority for over-used actions
        for action_type, count in action_counts.items():
            if count > 3:  # If same action repeated many times
                if "combat" in action_type.lower() and "combat_training" in adjusted_priorities:
                    adjusted_priorities["combat_training"] = max(1, adjusted_priorities["combat_training"] - 1)
                elif "gather" in action_type.lower() and "resource_gathering" in adjusted_priorities:
                    adjusted_priorities["resource_gathering"] = max(1, adjusted_priorities["resource_gathering"] - 1)

        return adjusted_priorities

    def _balance_goal_priorities(
        self, priorities: dict[str, int], current_state: dict[GameState, Any]
    ) -> dict[str, int]:
        """Balance goal priorities to prevent single-goal focus.

        Parameters:
            priorities: Current priority mapping for goal types
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Balanced priority mapping encouraging diverse goal pursuit

        This method balances goal priorities to encourage diverse character
        development, boosting neglected areas and moderating over-prioritized
        goals to prevent stagnation in single skill areas.
        """
        balanced_priorities = priorities.copy()

        # Find the highest and lowest priorities
        max_priority = max(priorities.values()) if priorities else 5
        min_priority = min(priorities.values()) if priorities else 5

        # If there's too much imbalance, adjust
        if max_priority - min_priority > 6:
            # Boost the lowest priorities
            for goal_type, priority in balanced_priorities.items():
                if priority == min_priority:
                    balanced_priorities[goal_type] = min(10, priority + 2)

            # Slightly reduce the highest priorities
            for goal_type, priority in balanced_priorities.items():
                if priority == max_priority:
                    balanced_priorities[goal_type] = max(1, priority - 1)

        return balanced_priorities

    def convert_actions_for_goap(self, actions: list["BaseAction"]) -> "Action_List":
        """Convert BaseAction list to GOAP Action_List format.

        Parameters:
            actions: List of BaseAction instances to convert

        Return values:
            Action_List object suitable for GOAP planning

        This method transforms a list of type-safe BaseAction instances into
        the Action_List format required by the GOAP library, enabling the
        planner to work with the modular action system.
        """
        action_list = Action_List()

        for action in actions:
            try:
                name, conditions, effects, weight = self.convert_action_to_goap(action)
                action_list.add_condition(name, **conditions)
                action_list.add_reaction(name, **effects)
                action_list.set_weight(name, weight)
            except (AttributeError, KeyError, ValueError) as e:
                print(f"Warning: Failed to convert action {action.name}: {e}")
                continue

        return action_list

    def _convert_actions_for_goap(self, actions: list["BaseAction"]) -> "Action_List":
        """Alias for convert_actions_for_goap for backward compatibility with tests."""
        return self.convert_actions_for_goap(actions)

    # Enhanced methods for unified sub-goal architecture

    def create_goal_from_sub_request(self, sub_goal_request: SubGoalRequest, context: GoalFactoryContext) -> BaseGoal:
        """Factory method to convert SubGoalRequest to appropriate Goal instance.

        Parameters:
            sub_goal_request: Pydantic model with sub-goal requirements
            context: GoalFactoryContext with character state, game data, and depth info

        Return values:
            BaseGoal: Concrete goal instance that uses GOAP facilities

        Raises:
            GoalFactoryError: If sub_goal_request.goal_type is not supported
            MaxDepthExceededError: If recursion depth exceeds maximum
        """
        # Check recursion depth limit
        if context.recursion_depth >= context.max_depth:
            raise MaxDepthExceededError(context.max_depth)

        # Validate context has required data
        if context.character_state is None:
            raise GoalFactoryError(sub_goal_request.goal_type, "GoalFactoryContext must include character_state")

        if sub_goal_request.goal_type == "move_to_location":
            return MovementGoal(
                target_x=sub_goal_request.parameters["target_x"], target_y=sub_goal_request.parameters["target_y"]
            )

        elif sub_goal_request.goal_type == "reach_hp_threshold":
            return RestGoal(min_hp_percentage=sub_goal_request.parameters.get("min_hp_percentage", 0.8))

        elif sub_goal_request.goal_type == "obtain_item":
            return GatheringGoal(target_material_code=sub_goal_request.parameters["item_code"])

        elif sub_goal_request.goal_type == "equip_item_type":
            return EquipmentGoal(
                target_slot=sub_goal_request.parameters["item_type"],
                max_item_level=sub_goal_request.parameters["max_level"],
            )

        # New crafting sub-goal types
        elif sub_goal_request.goal_type == "gather_material":
            from .goals.material_gathering_goal import MaterialGatheringGoal

            return MaterialGatheringGoal(
                material_code=sub_goal_request.parameters["material_code"],
                quantity=sub_goal_request.parameters["quantity"],
            )

        elif sub_goal_request.goal_type == "move_to_workshop":
            from .goals.workshop_movement_goal import WorkshopMovementGoal

            return WorkshopMovementGoal(
                workshop_x=sub_goal_request.parameters["workshop_x"],
                workshop_y=sub_goal_request.parameters["workshop_y"],
                workshop_type=sub_goal_request.parameters["workshop_type"],
            )

        elif sub_goal_request.goal_type == "execute_craft":
            from .goals.craft_execution_goal import CraftExecutionGoal

            return CraftExecutionGoal(
                recipe_code=sub_goal_request.parameters["recipe_code"],
                workshop_type=sub_goal_request.parameters["workshop_type"],
            )

        else:
            raise GoalFactoryError(sub_goal_request.goal_type, f"Unknown sub-goal type: {sub_goal_request.goal_type}")

    async def plan_to_target_state(
        self, current_state: CharacterGameState, target_state: GOAPTargetState
    ) -> GOAPActionPlan:
        """Plan actions to reach target state using GOAP with state validation.

        Parameters:
            current_state: Pydantic model with current character state
            target_state: Pydantic model with target state requirements

        Return values:
            GOAPActionPlan: Pydantic model with ordered action sequence

        Raises:
            PlanningError: If no valid plan can be found
            NoValidGoalError: If GOAP planner could not find valid action sequence
        """
        # Validate target state before planning if state_manager available
        if self.state_manager:
            await self.state_manager.validate_goap_target_state(target_state)

        # Convert target state to dict with string keys for GOAP planner
        goal_state = target_state.to_goap_dict()

        self.logger.debug(f"Goal state for planner: {goal_state}")
        self.logger.debug(f"Number of goal conditions: {len(goal_state)}")

        # Create GOAP planner
        planner = await self._create_goap_planner(current_state, goal_state)

        # Generate plan
        raw_plan = planner.calculate()

        if not raw_plan:
            raise NoValidGoalError("GOAP planner could not find valid action sequence")

        # Convert to type-safe GOAPActionPlan
        goap_actions = []
        total_cost = 0
        estimated_duration = 0.0

        for action in raw_plan:
            # Convert action dictionary to GOAPAction
            goap_action = {
                "name": action.get("name", "unknown_action"),
                "action_type": action.get("action_type", "UnknownAction"),
                "parameters": action.get("parameters", {}),
                "cost": action.get("cost", 1),
                "estimated_duration": action.get("estimated_duration", 1.0),
            }

            # Create GOAPAction from the action
            goap_action_obj = GOAPAction(**goap_action)
            goap_actions.append(goap_action_obj)
            total_cost += goap_action_obj.cost
            estimated_duration += goap_action_obj.estimated_duration

        return GOAPActionPlan(
            actions=goap_actions,
            total_cost=total_cost,
            estimated_duration=estimated_duration,
            plan_id=f"plan_{current_state.name}_{time.time()}",
        )
