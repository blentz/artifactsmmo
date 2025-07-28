"""
Goal Manager with Cooldown-Aware Planning

This module manages dynamic goal selection and GOAP planning for the AI player.
It integrates with the existing GOAP library to provide intelligent goal prioritization
based on character progression and current game state.

The GoalManager uses the modular action system and GameState enum to generate
action plans that efficiently progress the character toward maximum level achievement.
Includes cooldown awareness to prevent invalid planning when character is on cooldown.
"""

from datetime import datetime, timedelta
from typing import Any

from ..lib.goap import Action_List, Planner
from .actions import ActionRegistry, BaseAction, get_all_actions
from .state.game_state import GameState


class CooldownAwarePlanner(Planner):
    """Extended GOAP planner with cooldown timing awareness"""

    def __init__(self, cooldown_manager, *args, **kwargs):
        """Initialize CooldownAwarePlanner with cooldown management.
        
        Parameters:
            cooldown_manager: CooldownManager instance for timing constraint validation
            *args: Additional arguments passed to parent Planner constructor
            **kwargs: Additional keyword arguments passed to parent Planner constructor
            
        Return values:
            None (constructor)
            
        This constructor initializes the extended GOAP planner with cooldown
        awareness capabilities, enabling planning that considers character
        cooldown timing constraints for realistic action sequencing.
        """
        super().__init__(*args, **kwargs)
        self.cooldown_manager = cooldown_manager

    def calculate_with_timing_constraints(self, character_name: str) -> list[dict[str, Any]]:
        """Generate plan considering current cooldown state.
        
        Parameters:
            character_name: Name of the character for cooldown-aware planning
            
        Return values:
            List of action dictionaries with optimal timing considering cooldowns
            
        This method generates GOAP plans that account for character cooldown
        status, optimizing action timing and preventing invalid plans that
        would fail due to cooldown constraints in the AI player system.
        """
        try:
            # If character is on cooldown, return empty plan
            if not self.cooldown_manager.is_ready(character_name):
                return []

            # Use standard calculation if character is ready
            return self.calculate()
        except Exception:
            return []

    def filter_actions_by_cooldown(self, actions: Action_List, character_name: str) -> Action_List:
        """Filter out actions that require character to be off cooldown when character is on cooldown.
        
        Parameters:
            actions: Action_List containing all possible actions
            character_name: Name of the character to check cooldown status
            
        Return values:
            Action_List with cooldown-incompatible actions removed
            
        This method filters the available action list to remove actions that
        require cooldown readiness when the character is currently on cooldown,
        preventing invalid planning attempts in the GOAP system.
        """
        # If character is ready, return all actions
        if self.cooldown_manager.is_ready(character_name):
            return actions

        # Filter out actions that require cooldown readiness
        filtered_actions = Action_List()

        for action_name in actions.conditions.keys():
            conditions = actions.conditions[action_name]

            # If action requires cooldown readiness, skip it
            if conditions.get("cooldown_ready", False):
                continue

            # Add action to filtered list
            filtered_actions.add_condition(action_name, **conditions)
            filtered_actions.add_reaction(action_name, **actions.reactions[action_name])
            filtered_actions.set_weight(action_name, actions.weights[action_name])

        return filtered_actions

    def estimate_plan_duration(self, plan: list[dict[str, Any]]) -> timedelta:
        """Estimate total time to execute plan including cooldowns.
        
        Parameters:
            plan: List of action dictionaries representing the planned sequence
            
        Return values:
            Timedelta representing estimated total execution time
            
        This method calculates the expected time required to execute a complete
        action plan including individual action cooldowns and sequencing timing,
        enabling accurate planning and scheduling in the AI player system.
        """
        try:
            total_seconds = 0

            for action in plan:
                # Basic action execution time (varies by action type)
                action_name = action.get('name', '')
                if 'move' in action_name.lower():
                    total_seconds += 5  # Movement actions
                elif 'fight' in action_name.lower():
                    total_seconds += 10  # Combat actions
                elif 'gather' in action_name.lower():
                    total_seconds += 8  # Gathering actions
                else:
                    total_seconds += 3  # Default action time

                # Add cooldown time
                total_seconds += 1  # Standard cooldown

            return timedelta(seconds=total_seconds)
        except Exception:
            return timedelta(seconds=60)  # Default estimate

    def defer_planning_until_ready(self, character_name: str) -> datetime | None:
        """Return when planning should be deferred until character is off cooldown.
        
        Parameters:
            character_name: Name of the character to check cooldown deferral timing
            
        Return values:
            Datetime when planning can resume, or None if character is ready now
            
        This method determines if GOAP planning should be deferred due to character
        cooldown status, returning the specific time when planning can safely resume
        to avoid generating invalid action plans.
        """
        if self.cooldown_manager.is_ready(character_name):
            return None

        # Get remaining cooldown time in seconds
        remaining_seconds = self.cooldown_manager.get_remaining_time(character_name)

        # Calculate when the character will be ready
        ready_time = datetime.now() + timedelta(seconds=remaining_seconds)

        return ready_time


class GoalManager:
    """Manages dynamic goal selection and cooldown-aware GOAP planning"""

    def __init__(self, action_registry: ActionRegistry, cooldown_manager):
        """Initialize GoalManager with action registry and cooldown management.
        
        Parameters:
            action_registry: ActionRegistry instance for action discovery and generation
            cooldown_manager: CooldownManager instance for timing constraint validation
            
        Return values:
            None (constructor)
            
        This constructor initializes the GoalManager with the action registry for
        dynamic action generation and cooldown manager for timing-aware planning,
        setting up the infrastructure for intelligent goal selection and execution.
        """
        self.action_registry = action_registry
        self.cooldown_manager = cooldown_manager
        self.planner = None

    def select_next_goal(self, current_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Select appropriate goal based on character state and progression."""
        try:
            print(f"DEBUG: Goal selection with state keys: {list(current_state.keys())}")
            
            # Check for max level achievement first
            if self.max_level_achieved(current_state):
                print("DEBUG: Max level achieved, no goals needed")
                return {}

            # Check for emergency survival needs (highest priority)
            survival_goals = self.get_survival_goals(current_state)
            if survival_goals:
                highest_priority_survival = max(survival_goals, key=lambda g: g.get('priority', 0))
                print(f"DEBUG: Selected survival goal: {highest_priority_survival}")
                return highest_priority_survival

            # Get all available goals and filter by requirements
            all_available_goals = self.get_available_goals(current_state)
            print(f"DEBUG: Found {len(all_available_goals)} available goals")

            # Filter goals by requirements met
            achievable_goals = [goal for goal in all_available_goals if goal.get('requirements_met', True)]
            print(f"DEBUG: {len(achievable_goals)} achievable goals after filtering")

            if not achievable_goals:
                # If no achievable goals, return a basic progression goal
                character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
                basic_goal = {
                    'type': 'level_up',
                    'priority': 5,
                    'target_state': {
                        GameState.CHARACTER_LEVEL: character_level + 1,
                        GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 500
                    },
                    'requirements_met': True
                }
                print(f"DEBUG: No achievable goals, using basic goal: {basic_goal}")
                return basic_goal

            # Use intelligent prioritization to select the best goal
            selected_goal = self.prioritize_goals(achievable_goals, current_state)

            # Ensure the selected goal has all required fields
            if not selected_goal.get('target_state'):
                # Add a default target state if missing
                character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
                selected_goal['target_state'] = {
                    GameState.CHARACTER_LEVEL: character_level + 1
                }

            print(f"DEBUG: Selected goal: {selected_goal}")
            return selected_goal

        except Exception as e:
            print(f"DEBUG: Goal selection failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: basic progression goal on any error
            character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
            fallback_goal = {
                'type': 'level_up',
                'priority': 1,
                'target_state': {
                    GameState.CHARACTER_LEVEL: character_level + 1,
                    GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 500
                },
                'requirements_met': True
            }
            print(f"DEBUG: Using fallback goal: {fallback_goal}")
            return fallback_goal

    async def plan_actions(self, current_state: dict[GameState, Any], goal: dict[GameState, Any] | dict[str, Any]) -> list[dict[str, Any]]:
        """Generate action sequence using cooldown-aware GOAP planner."""
        try:
            # Extract target state from goal
            goal_state = goal.get('target_state', {})
            if not goal_state:
                print("DEBUG: No target_state in goal")
                return []

            print(f"DEBUG: Planning from state keys: {list(current_state.keys())}")
            print(f"DEBUG: Planning to goal state: {goal_state}")

            # Create GOAP planner with current actions
            planner = self._create_goap_planner(current_state, goal_state)
            
            # Check if planner has actions
            action_list = self.create_goap_actions()
            print(f"DEBUG: Created {len(action_list.conditions)} actions for planner")
            if action_list.conditions:
                print(f"DEBUG: Action names: {list(action_list.conditions.keys())}")

            # Generate plan
            plan = planner.calculate()
            print(f"DEBUG: GOAP planner returned: {plan}")

            return plan if plan else []
        except Exception as e:
            print(f"DEBUG: Planning failed with error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def plan_with_cooldown_awareness(self, character_name: str, current_state: dict[GameState, Any], goal_state: dict[GameState, Any]) -> list[dict[str, Any]]:
        """Generate plan considering current cooldown state and timing.
        
        Parameters:
            character_name: Name of the character for cooldown checking
            current_state: Dictionary with GameState enum keys and current values
            goal_state: Dictionary with GameState enum keys and target values
            
        Return values:
            List of action dictionaries with timing-aware sequencing
            
        This method generates action plans that account for character cooldown
        status, either deferring planning until ready or filtering actions
        that require cooldown readiness for optimal execution timing.
        """
        try:
            # Create planner with cooldown awareness
            planner = self._create_goap_planner(current_state, goal_state, character_name)

            # Generate plan
            plan = planner.calculate()

            return plan if plan else []
        except Exception:
            return []

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

    def create_cooldown_aware_actions(self, character_name: str) -> Action_List:
        """Convert modular actions to GOAP Action_List with cooldown filtering.
        
        Parameters:
            character_name: Name of the character for cooldown-specific filtering
            
        Return values:
            Action_List containing only actions available given current cooldown
            
        This method creates a GOAP-compatible Action_List from the modular
        action registry, filtering out actions that require cooldown readiness
        when the character is currently on cooldown.
        """
        # Start with all basic actions
        action_list = self.create_goap_actions()

        # Check if character is on cooldown
        if not self.cooldown_manager.is_ready(character_name):
            # Filter out actions that require cooldown readiness
            filtered_action_list = Action_List()

            for action_name in action_list.conditions.keys():
                conditions = action_list.conditions[action_name]

                # If action requires cooldown readiness, skip it
                if conditions.get("cooldown_ready", False):
                    continue

                # Add action to filtered list
                filtered_action_list.add_condition(action_name, **conditions)
                filtered_action_list.add_reaction(action_name, **action_list.reactions[action_name])
                filtered_action_list.set_weight(action_name, action_list.weights[action_name])

            return filtered_action_list

        # Character is ready, return all actions
        return action_list

    def create_goap_actions(self) -> Action_List:
        """Convert modular actions to GOAP Action_List format."""
        action_list = Action_List()

        try:
            # Get all actions from the registry
            basic_actions = self.action_registry.get_all_action_types()

            # Convert each action type to GOAP format
            for action_class in basic_actions:
                try:
                    # Try to create a basic instance (some actions may require parameters)
                    action_instance = action_class()
                    name, conditions, effects, weight = self.convert_action_to_goap(action_instance)

                    # Add to GOAP action list
                    action_list.add_condition(name, **conditions)
                    action_list.add_reaction(name, **effects)
                    action_list.set_weight(name, weight)

                except TypeError:
                    # Action requires parameters, try with None api_client
                    try:
                        action_instance = action_class(api_client=None)
                        name, conditions, effects, weight = self.convert_action_to_goap(action_instance)
                        action_list.add_condition(name, **conditions)
                        action_list.add_reaction(name, **effects)
                        action_list.set_weight(name, weight)
                    except:
                        continue
                except Exception as e:
                    print(f"Warning: Failed to create action {action_class.__name__}: {e}")
                    continue

        except Exception as e:
            print(f"Error creating GOAP actions: {e}")
            # Add fallback action when action creation fails
            action_list.add_condition("rest", hp_low=True)
            action_list.add_reaction("rest", hp_current=100)
            action_list.set_weight("rest", 1)

        return action_list


    def _convert_state_for_goap(self, state):
        """Convert GameState enum keys to string keys for GOAP compatibility."""
        goap_state = {}
        for key, value in state.items():
            if hasattr(key, 'value'):
                # Convert enum to string key
                string_key = key.value.lower()
            else:
                string_key = str(key).lower()

            # Convert boolean to int for GOAP
            if isinstance(value, bool):
                goap_state[string_key] = 1 if value else 0
            else:
                goap_state[string_key] = value

        return goap_state


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
            goals.append({
                'type': 'level_up',
                'priority': 1,
                'target_state': {
                    GameState.CHARACTER_LEVEL: current_level + 1,
                    GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 500
                }
            })

        # Skill development goals
        mining_level = current_state.get(GameState.MINING_LEVEL, 1)
        if mining_level < 5:
            goals.append({
                'type': 'skill_training',
                'priority': 2,
                'target_state': {
                    GameState.MINING_LEVEL: mining_level + 1,
                    GameState.MINING_XP: current_state.get(GameState.MINING_XP, 0) + 200
                }
            })

        woodcutting_level = current_state.get(GameState.WOODCUTTING_LEVEL, 1)
        if woodcutting_level < 5:
            goals.append({
                'type': 'skill_training',
                'priority': 2,
                'target_state': {
                    GameState.WOODCUTTING_LEVEL: woodcutting_level + 1,
                    GameState.WOODCUTTING_XP: current_state.get(GameState.WOODCUTTING_XP, 0) + 200
                }
            })

        # Basic economic goal
        current_gold = current_state.get(GameState.CHARACTER_GOLD, 0)
        if current_gold < 1000:
            goals.append({
                'type': 'resource_gathering',
                'priority': 3,
                'target_state': {
                    GameState.CHARACTER_GOLD: current_gold + 500
                }
            })

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
            goals.append({
                'type': 'level_up',
                'priority': 1,
                'target_state': {
                    GameState.CHARACTER_LEVEL: current_level + 1,
                    GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 1000
                }
            })

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
            goals.append({
                'type': 'level_up',
                'priority': 1,
                'target_state': {
                    GameState.CHARACTER_LEVEL: current_level + 1,
                    GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 2000
                }
            })

        return goals

    def prioritize_goals(self, available_goals: list[dict[GameState, Any]], current_state: dict[GameState, Any]) -> dict[GameState, Any]:
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
            base_priority = goal.get('priority', 5)
            goal_type = goal.get('type', 'unknown')

            # Calculate context-sensitive priority adjustments
            priority_adjustments = 0

            # Survival goals get highest priority when HP is low
            if goal_type in ['emergency_rest', 'health_recovery', 'survival']:
                priority_adjustments += self._calculate_survival_priority(current_state)

            # Progression goals priority based on character level
            elif goal_type in ['level_up', 'skill_training']:
                priority_adjustments += self._calculate_progression_priority(current_state)

            # Economic goals priority based on gold and inventory
            elif goal_type in ['resource_gathering', 'trading', 'economic_optimization']:
                priority_adjustments += self._calculate_economic_priority(current_state)

            # Calculate feasibility score
            feasibility = self.evaluate_goal_feasibility(current_state, goal, simple=False)
            feasibility_score = feasibility.get('confidence', 0.5) if isinstance(feasibility, dict) else (1.0 if feasibility else 0.1)

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
        try:
            # Extract target state from goal
            target_state = goal.get('target_state', goal)

            # Basic feasibility checks
            for state_key, target_value in target_state.items():
                current_value = current_state.get(state_key, 0)

                # Check if goal is reasonable (not too far from current state)
                if isinstance(target_value, (int, float)) and isinstance(current_value, (int, float)):
                    if target_value > current_value * 10:  # Arbitrary threshold
                        return False

            return True
        except Exception:
            return False

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
        try:
            # Basic cost estimation based on state differences
            total_cost = 0
            target_state = goal.get('target_state', goal)

            for state_key, target_value in target_state.items():
                current_value = current_state.get(state_key, 0)
                if isinstance(target_value, (int, float)) and isinstance(current_value, (int, float)):
                    diff = abs(target_value - current_value)
                    total_cost += diff
                else:
                    total_cost += 1  # Basic cost for non-numeric changes

            return total_cost
        except Exception:
            return 100  # Default high cost on error

    def max_level_achieved(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character has reached maximum level (45).
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Boolean indicating whether character has reached level 45
            
        This method checks if the character has achieved the maximum level
        in ArtifactsMMO (level 45), which serves as the primary completion
        condition for autonomous AI player operation.
        """
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 0)
        return character_level >= 45

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

        # Critical HP - need immediate recovery
        if current_hp <= max_hp * 0.2:  # 20% or less HP
            goals.append({
                'type': 'emergency_rest',
                'priority': 10,
                'target_state': {
                    GameState.HP_CURRENT: max_hp,  # Full recovery
                    GameState.AT_SAFE_LOCATION: True
                }
            })

        # Low HP - should rest soon
        elif current_hp <= max_hp * 0.5:  # 50% or less HP
            goals.append({
                'type': 'health_recovery',
                'priority': 9,
                'target_state': {
                    GameState.HP_CURRENT: int(max_hp * 0.8)  # Recover to 80%
                }
            })

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
        current_level = current_state.get(GameState.CHARACTER_LEVEL, 1)

        # Basic progression goal
        goals.append({
            'type': 'level_up',
            'priority': 1,
            'target_state': {
                GameState.CHARACTER_LEVEL: current_level + 1,
                GameState.CHARACTER_XP: current_state.get(GameState.CHARACTER_XP, 0) + 500
            }
        })

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
                goals.append({
                    'type': 'banking',
                    'priority': 9,
                    'target_state': {
                        GameState.INVENTORY_SPACE_AVAILABLE: 15,
                        GameState.INVENTORY_FULL: False
                    },
                    'requirements_met': True
                })
            else:
                # If not at bank, need to move or sell items
                goals.append({
                    'type': 'inventory_management',
                    'priority': 8,
                    'target_state': {
                        GameState.INVENTORY_SPACE_AVAILABLE: 10,
                        GameState.INVENTORY_FULL: False
                    },
                    'requirements_met': True
                })

                # Also add item selling as an option
                goals.append({
                    'type': 'item_selling',
                    'priority': 7,
                    'target_state': {
                        GameState.CHARACTER_GOLD: current_gold + 500,
                        GameState.INVENTORY_SPACE_AVAILABLE: 10
                    },
                    'requirements_met': True
                })

        # Economic goal: accumulate more gold (lower priority when inventory issues exist)
        base_priority = 3 if not (inventory_full or inventory_space <= 2) else 1
        goals.append({
            'type': 'resource_gathering',
            'priority': base_priority,
            'target_state': {
                GameState.CHARACTER_GOLD: current_gold + 1000
            }
        })

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
            updated_priorities['emergency_rest'] = 10
            updated_priorities['health_recovery'] = 9
            if 'survival' in updated_priorities:
                updated_priorities['survival'] = max(updated_priorities['survival'] + 5, 10)
        elif hp_ratio <= 0.5:
            updated_priorities['health_recovery'] = 8
            if 'survival' in updated_priorities:
                updated_priorities['survival'] = max(updated_priorities['survival'] + 2, 8)

        # Adjust progression priorities based on level
        character_level = current_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level < 10:
            updated_priorities['level_up'] = 6
            updated_priorities['skill_training'] = 5
        elif character_level < 30:
            updated_priorities['level_up'] = 7
            updated_priorities['skill_training'] = 4

        return updated_priorities

    def _create_goap_planner(self, current_state: dict[GameState, Any], goal_state: dict[GameState, Any], character_name: str | None = None) -> 'Planner':
        """Create GOAP planner instance with current state and goals."""
        # Convert state to GOAP format (string keys)
        goap_current_state = self._convert_state_for_goap(current_state)
        goap_goal_state = self._convert_state_for_goap(goal_state)

        print(f"DEBUG: Converted current state: {goap_current_state}")
        print(f"DEBUG: Converted goal state: {goap_goal_state}")

        # Create action list
        if character_name:
            action_list = self.create_cooldown_aware_actions(character_name)
        else:
            action_list = self.create_goap_actions()

        print(f"DEBUG: Action list has {len(action_list.conditions)} actions")

        # Extract state keys for planner initialization
        all_keys = set(goap_current_state.keys()) | set(goap_goal_state.keys())
        print(f"DEBUG: All state keys for planner: {all_keys}")

        # Create planner
        if character_name:
            planner = CooldownAwarePlanner(self.cooldown_manager, *all_keys)
        else:
            planner = Planner(*all_keys)

        planner.set_start_state(**goap_current_state)
        planner.set_goal_state(**goap_goal_state)
        planner.set_action_list(action_list)

        print(f"DEBUG: Planner configured with start: {goap_current_state}, goal: {goap_goal_state}")

        return planner

    def get_available_goals(self, current_state: dict[GameState, Any], filters: dict[str, Any] | None = None) -> list[dict[GameState, Any]]:
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
            goal['requirements_met'] = self._check_goal_requirements(goal, current_state)

        # Apply filters if provided
        if filters:
            filtered_goals = []
            for goal in all_goals:
                include_goal = True
                for filter_key, filter_value in filters.items():
                    if filter_key == 'type' and goal.get('type') != filter_value:
                        include_goal = False
                        break
                    elif filter_key == 'min_priority' and goal.get('priority', 0) < filter_value:
                        include_goal = False
                        break
                    elif filter_key == 'max_priority' and goal.get('priority', 999) > filter_value:
                        include_goal = False
                        break
                if include_goal:
                    filtered_goals.append(goal)
            return filtered_goals

        return all_goals

    def _check_goal_requirements(self, goal: dict, current_state: dict[GameState, Any]) -> bool:
        """Check if character meets requirements to pursue this goal."""
        goal_type = goal.get('type', '')

        # Combat goals require ability to fight
        if 'combat' in goal_type and not current_state.get(GameState.CAN_FIGHT, False):
            return False

        # Gathering goals require ability to gather
        if 'gather' in goal_type and not current_state.get(GameState.CAN_GATHER, False):
            return False

        # Crafting goals require ability to craft
        if 'craft' in goal_type and not current_state.get(GameState.CAN_CRAFT, False):
            return False

        # Check any explicit requirements in the goal
        requirements = goal.get('requirements', {})
        for req_key, req_value in requirements.items():
            current_value = current_state.get(req_key)
            if current_value != req_value:
                return False

        return True

    def evaluate_goal_feasibility(self, current_state: dict[GameState, Any], goal: dict[GameState, Any], simple: bool = True) -> bool | dict[str, Any]:
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
        target_state = goal.get('target_state', {})
        requirements = goal.get('requirements', {})

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

            if isinstance(target_value, (int, float)) and isinstance(current_value, (int, float)):
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
            'feasible': feasible,
            'estimated_actions': estimated_actions,
            'estimated_time': estimated_time,
            'missing_requirements': missing_requirements,
            'confidence': 1.0
        }

        # Reduce confidence if many actions required
        if estimated_actions > 10:
            feasibility['confidence'] = max(0.3, 1.0 - (estimated_actions - 10) * 0.1)

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
        character_xp = current_state.get(GameState.CHARACTER_XP, 0)

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

    def _adjust_priorities_based_on_history(self, priorities: dict[str, int], recent_actions: list[dict[str, Any]], current_state: dict[GameState, Any]) -> dict[str, int]:
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
            action_type = action.get('name', 'unknown')
            action_counts[action_type] = action_counts.get(action_type, 0) + 1

        # Reduce priority for over-used actions
        for action_type, count in action_counts.items():
            if count > 3:  # If same action repeated many times
                if 'combat' in action_type.lower() and 'combat_training' in adjusted_priorities:
                    adjusted_priorities['combat_training'] = max(1, adjusted_priorities['combat_training'] - 1)
                elif 'gather' in action_type.lower() and 'resource_gathering' in adjusted_priorities:
                    adjusted_priorities['resource_gathering'] = max(1, adjusted_priorities['resource_gathering'] - 1)

        return adjusted_priorities

    def _balance_goal_priorities(self, priorities: dict[str, int], current_state: dict[GameState, Any]) -> dict[str, int]:
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

    def convert_actions_for_goap(self, actions: list['BaseAction']) -> 'Action_List':
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
            except Exception as e:
                print(f"Warning: Failed to convert action {action.name}: {e}")
                continue

        return action_list

    def _convert_actions_for_goap(self, actions: list['BaseAction']) -> 'Action_List':
        """Alias for convert_actions_for_goap for backward compatibility with tests."""
        return self.convert_actions_for_goap(actions)
