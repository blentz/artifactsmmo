"""
GOAP Execution Management System

This module provides centralized GOAP planning and execution services,
eliminating redundant GOAP methods from the AI controller.
"""

import logging
from typing import Any, Dict, List, Optional

from src.game.globals import CONFIG_PREFIX
from src.lib.actions_data import ActionsData
from src.lib.goap import Action_List, Planner, World
from src.lib.yaml_data import YamlData


class GOAPExecutionManager:
    """
    Centralized GOAP planning and execution system.
    
    Handles world creation, planning, and goal achievement using GOAP,
    eliminating redundant GOAP logic from the AI controller.
    """
    
    def __init__(self):
        """Initialize GOAP execution manager."""
        self.logger = logging.getLogger(__name__)
        
        # Current GOAP state
        self.current_world = None
        self.current_planner = None
        
        # Cached start state configuration
        self._start_state_config = None
        
    def _load_start_state_defaults(self) -> Dict[str, Any]:
        """
        Load default start state configuration from YAML file.
        
        Returns:
            Dictionary of default state variables with their initial values
        """
        if self._start_state_config is not None:
            return self._start_state_config
            
        try:
            start_state_data = YamlData(f"{CONFIG_PREFIX}/goap_start_state.yaml")
            
            # Get the core states section
            defaults = start_state_data.data.get('core_states', {})
            
            self._start_state_config = defaults
            self.logger.debug(f"Loaded {len(defaults)} default start state variables from configuration")
            return defaults
            
        except Exception as e:
            self.logger.warning(f"Could not load start state configuration: {e}")
            # Return minimal fallback defaults
            return {
                'can_move': True,
                'can_attack': True,
                'character_safe': True,
                'character_alive': True,
                'need_combat': True,
                'at_target_location': False,
                'monsters_available': False,
                'monster_present': False,
                'is_on_cooldown': False,
                'needs_rest': False
            }
    
    def create_world_with_planner(self, start_state: Dict[str, Any], 
                                goal_state: Dict[str, Any], 
                                actions_config: Dict[str, Dict]) -> World:
        """
        Create a GOAP world with a planner for the given scenario.
        
        Args:
            start_state: The starting state as a dictionary
            goal_state: The desired goal state as a dictionary
            actions_config: Configuration for available actions
            
        Returns:
            A World instance with the planner added
        """
        world = World()
        
        # Load default start state configuration first to get all possible state keys
        start_state_defaults = self._load_start_state_defaults()
        
        # Get all keys from start state, goal state, action conditions/reactions, AND defaults
        all_keys = set(start_state.keys()) | set(goal_state.keys()) | set(start_state_defaults.keys())
        
        # Extract all state variables used in action conditions and reactions
        for action_name, action_config in actions_config.items():
            # Add condition variables
            conditions = action_config.get('conditions', {})
            all_keys.update(conditions.keys())
            
            # Add reaction variables
            reactions = action_config.get('reactions', {})
            all_keys.update(reactions.keys())
        
        # Create planner with all required state keys
        planner = Planner(*all_keys)
        
        # Build complete start state with proper precedence:
        # 1. Start with configuration defaults
        # 2. Add any additional keys from actions with False defaults  
        # 3. Override with actual start_state values
        complete_start_state = start_state_defaults.copy()
        
        # Add any missing action-required keys with False defaults
        for key in all_keys:
            if key not in complete_start_state:
                complete_start_state[key] = False
        
        # Override with actual runtime state values
        complete_start_state.update(start_state)
        
        # Set start and goal states on the planner
        planner.set_start_state(**complete_start_state)
        planner.set_goal_state(**goal_state)
        
        # Create actions from configuration
        action_list = Action_List()
        for action_name, action_config in actions_config.items():
            action_list.add_condition(
                action_name,
                **action_config.get('conditions', {})
            )
            action_list.add_reaction(
                action_name,
                **action_config.get('reactions', {})
            )
            weight = action_config.get('weight', 1.0)
            action_list.set_weight(action_name, weight)
        
        # Set action list on planner
        planner.set_action_list(action_list)
        
        # Add planner to world
        world.add_planner(planner)
        
        # Store for potential reuse
        self.current_world = world
        self.current_planner = planner
        
        self.logger.debug(f"Created GOAP world with {len(actions_config)} actions and {len(all_keys)} state variables")
        return world
    
    def create_plan(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                   actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Create a GOAP plan to achieve a goal.
        
        Args:
            start_state: Current state
            goal_state: Desired state
            actions_config: Available actions
            
        Returns:
            List of action dictionaries or None if no plan found
        """
        try:
            world = self.create_world_with_planner(start_state, goal_state, actions_config)
            planner = self.current_planner
            
            self.logger.debug(f"📊 Starting GOAP calculation with {len(actions_config)} actions...")
            plans = planner.calculate()
            self.logger.debug("📊 GOAP calculation completed successfully")
            
            if plans:
                best_plan = plans  # Plans is already the list of nodes
                self.logger.info(f"GOAP plan created with {len(best_plan)} actions")
                
                
                # Convert GOAP actions to controller-compatible format
                plan_actions = []
                for action in best_plan:
                    if isinstance(action, dict):
                        # GOAP node is a dictionary with action name
                        action_name = action.get('name', 'unknown')
                        action_dict = {'name': action_name}
                        plan_actions.append(action_dict)
                    else:
                        # Action is an object with name and reactions
                        action_dict = {
                            'name': getattr(action, 'name', str(action)),
                            **getattr(action, 'reactions', {})
                        }
                        plan_actions.append(action_dict)
                
                return plan_actions
            else:
                self.logger.warning("No GOAP plan found for goal")
                self.logger.info("Start state key values:")
                self.logger.info(f"  - character_safe: {start_state.get('character_safe')}")
                self.logger.info(f"  - needs_rest: {start_state.get('needs_rest')}")
                self.logger.info(f"  - is_on_cooldown: {start_state.get('is_on_cooldown')}")
                self.logger.info(f"  - hp_percentage: {start_state.get('hp_percentage')}")
                self.logger.info(f"  - character_alive: {start_state.get('character_alive')}")
                self.logger.info(f"Goal state: {goal_state}")
                self.logger.info(f"Available actions: {list(actions_config.keys())}")
                # Check which actions have their conditions met
                self.logger.info("Checking action conditions:")
                for action_name, action_config in actions_config.items():
                    conditions = action_config.get('conditions', {})
                    all_met = True
                    unmet_conditions = []
                    for cond_key, cond_value in conditions.items():
                        if start_state.get(cond_key) != cond_value:
                            all_met = False
                            unmet_conditions.append(f"{cond_key}: need {cond_value}, have {start_state.get(cond_key)}")
                    if all_met:
                        self.logger.info(f"  ✓ {action_name}: all conditions met")
                    else:
                        self.logger.info(f"  ✗ {action_name}: unmet conditions - {unmet_conditions}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating GOAP plan: {e}")
            return None
    
    def achieve_goal_with_goap(self, goal_state: Dict[str, Any], 
                             controller, 
                             config_file: str = None, 
                             max_iterations: int = 50) -> bool:
        """
        Use knowledge-based GOAP planning to achieve a specific goal.
        
        Architecture:
        1. Knowledge Loading: Load all available knowledge and develop complete plan
        2. Plan Execution: Execute plan steps, only replanning on discovery actions
        3. Cooldown Handling: Insert wait actions into current plan
        
        Args:
            goal_state: The desired end state
            controller: AI controller for execution and state access
            config_file: Optional path to action configuration file
            max_iterations: Maximum planning iterations to prevent infinite loops
            
        Returns:
            True if goal was achieved, False otherwise
        """
        if not controller.client:
            self.logger.error("Cannot achieve goal without API client")
            return False
        
        # Phase 1: Knowledge Loading and Plan Development
        self.logger.info("🧠 Phase 1: Loading knowledge and developing complete plan")
        complete_plan = self._develop_complete_plan(controller, goal_state, config_file)
        
        if not complete_plan:
            self.logger.error("Could not develop a complete plan with available knowledge")
            return False
        
        # Phase 2: Plan Execution with Selective Replanning
        self.logger.info(f"🚀 Phase 2: Executing plan with {len(complete_plan)} actions")
        self.logger.debug(f"🚀 Plan: {[i['name'] for i in complete_plan]}")
        return self._execute_plan_with_selective_replanning(
            complete_plan, controller, goal_state, config_file, max_iterations
        )
    
    def _develop_complete_plan(self, controller, goal_state: Dict[str, Any], 
                             config_file: str = None) -> Optional[List[Dict]]:
        """
        Develop a complete plan using available knowledge without API calls.
        
        This phase should use the analyze_crafting_chain action and existing
        knowledge to build a comprehensive plan before execution begins.
        """
        # Get current state without forcing refresh to avoid infinite loops
        current_state = controller.get_current_world_state(force_refresh=False)
        
        # Check if goal is already achieved
        if self._is_goal_achieved(goal_state, current_state):
            self.logger.info("🎯 Goal already achieved!")
            return []
        
        # Load actions configuration
        actions_config = self._load_actions_from_config(config_file)
        if not actions_config:
            self.logger.error("No actions available for planning")
            return None
        
        # First, try to use existing knowledge to create a complete plan
        self.logger.info("🧠 Attempting knowledge-based planning...")
        knowledge_based_plan = self._create_knowledge_based_plan(
            current_state, goal_state, actions_config, controller
        )
        
        if knowledge_based_plan:
            self.logger.info(f"📋 Created knowledge-based plan with {len(knowledge_based_plan)} actions")
            return knowledge_based_plan
        
        # If knowledge-based planning fails, create a discovery plan
        self.logger.info("🔍 Knowledge-based planning failed, attempting discovery planning...")
        discovery_plan = self._create_discovery_plan(
            current_state, goal_state, actions_config
        )
        
        if discovery_plan:
            self.logger.info(f"🔍 Created discovery plan with {len(discovery_plan)} actions")
            return discovery_plan
        
        self.logger.error("❌ Both knowledge-based and discovery planning failed")
        return None
    
    def _execute_plan_with_selective_replanning(self, plan: List[Dict], controller, 
                                              goal_state: Dict[str, Any], 
                                              config_file: str = None,
                                              max_iterations: int = 50) -> bool:
        """
        Execute plan with selective replanning based on action types.
        
        Discovery actions trigger replanning, execution actions continue plan.
        Cooldowns insert wait actions into current plan.
        """
        current_plan = plan.copy()
        action_index = 0
        iterations = 0
        
        # Load actions configuration for updating world state with reactions
        actions_config = self._load_actions_from_config(config_file)
        
        while action_index < len(current_plan) and iterations < max_iterations:
            iterations += 1
            
            # Check for cooldown and handle by inserting wait action and replanning
            current_state = controller.get_current_world_state(force_refresh=False)
            if current_state.get('is_on_cooldown', False):
                # Only insert wait action if current action isn't already a wait action
                if action_index < len(current_plan):
                    current_action = current_plan[action_index]
                    if current_action.get('name') != 'wait':
                        # Insert wait action and replan
                        current_plan = self._handle_cooldown_with_plan_insertion(
                            current_plan, action_index, controller
                        )
                        # Reset action index to start of new plan with wait action
                        action_index = 0
                        continue
            
            # Check if goal is achieved
            if self._is_goal_achieved(goal_state, current_state):
                self.logger.info("🎯 Goal achieved during plan execution!")
                return True
            
            # Execute next action
            if action_index >= len(current_plan):
                self.logger.warning("Reached end of plan without achieving goal")
                break
                
            current_action = current_plan[action_index]
            action_name = current_action.get('name', 'unknown')
            
            self.logger.info(f"Executing action {action_index + 1}/{len(current_plan)}: {action_name}")
            
            # Execute the action
            success = controller._execute_single_action(action_name, current_action)
            
            if success:
                # Update world state with action reactions if available
                self._update_world_state_with_reactions(controller, action_name, actions_config)
            else:
                self.logger.warning(f"Action {action_name} failed")
                
                # Handle specific failure types with targeted recovery
                if self._is_authentication_failure(action_name, controller):
                    self.logger.error("🚨 Authentication failure detected - aborting execution")
                    return False
                elif self._is_coordinate_failure(action_name, controller):
                    self.logger.warning("📍 Coordinate failure detected - forcing find_monsters replan")
                    # Force a complete replan starting with find_monsters
                    remaining_plan = self._create_recovery_plan_with_find_monsters(
                        controller, goal_state, config_file
                    )
                    if remaining_plan:
                        current_plan = remaining_plan
                        action_index = 0  # Reset to start of new plan
                        continue
                    else:
                        return False
                else:
                    # For other failures, try replanning from current position
                    remaining_plan = self._replan_from_current_position(
                        controller, goal_state, config_file, current_plan[action_index:]
                    )
                    if remaining_plan:
                        current_plan = current_plan[:action_index] + remaining_plan
                        continue
                    else:
                        return False
            
            # Check if this action requires replanning
            if self._is_discovery_action(action_name):
                self.logger.info(f"🔍 Discovery action {action_name} completed - checking for replanning")
                
                # Learn from the action
                self._learn_from_action_response(action_name, controller)
                
                # Check if we need to replan based on new knowledge
                updated_state = controller.get_current_world_state(force_refresh=True)
                if self._should_replan_after_discovery(current_action, updated_state):
                    self.logger.info("📋 New knowledge acquired - replanning remaining actions")
                    remaining_plan = self._replan_from_current_position(
                        controller, goal_state, config_file, current_plan[action_index + 1:]
                    )
                    if remaining_plan:
                        current_plan = current_plan[:action_index + 1] + remaining_plan
                    
            action_index += 1
            
            # Check for cooldown after action execution
            # Move and attack actions can put character on cooldown
            if action_name in ['move', 'attack', 'gather_resources', 'craft_item']:
                current_state = controller.get_current_world_state(force_refresh=True)
                if current_state.get('is_on_cooldown', False):
                    # Insert wait action at next position if not already present
                    if action_index < len(current_plan) and current_plan[action_index].get('name') != 'wait':
                        self.logger.info("🕐 Cooldown detected after action - inserting wait action")
                        current_plan = self._handle_cooldown_with_plan_insertion(
                            current_plan, action_index, controller
                        )
        
        # Check final goal achievement
        final_state = controller.get_current_world_state(force_refresh=True)
        return self._is_goal_achieved(goal_state, final_state)
    
    def _create_knowledge_based_plan(self, current_state: Dict[str, Any], 
                                   goal_state: Dict[str, Any], 
                                   actions_config: Dict[str, Dict],
                                   controller) -> Optional[List[Dict]]:
        """
        Create a complete plan using existing knowledge without API discovery calls.
        """
        self.logger.debug("📊 Starting knowledge-based plan creation")
        
        # Check if we have sufficient knowledge to plan
        knowledge_base = getattr(controller, 'knowledge_base', None)
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            self.logger.debug("📊 No knowledge base available for planning")
            return None
        
        # For equipment goals, try to use analyze_crafting_chain
        if goal_state.get('has_better_weapon') or goal_state.get('need_equipment'):
            # First check if we already know what weapon to craft
            if hasattr(controller, 'action_context') and controller.action_context.get('item_code'):
                target_item = controller.action_context['item_code']
                self.logger.debug(f"Found selected weapon in action context: {target_item}")
                
                # Use crafting chain analysis to build complete plan
                try:
                    chain_action_data = {'target_item': target_item}
                    context = controller._build_execution_context(chain_action_data)
                    
                    # Execute crafting chain analysis (this uses existing knowledge, no API calls)
                    from .actions.analyze_crafting_chain import AnalyzeCraftingChainAction
                    chain_analyzer = AnalyzeCraftingChainAction()
                    
                    # This should use only existing knowledge
                    chain_result = chain_analyzer.execute(controller.client, context)
                    
                    if chain_result and chain_result.get('success'):
                        action_sequence = chain_result.get('action_sequence', [])
                        if action_sequence:
                            self.logger.info(f"📋 Built {len(action_sequence)}-step plan from knowledge")
                            return action_sequence
                            
                except Exception as e:
                    self.logger.warning(f"Knowledge-based planning failed: {e}")
        
        # Fall back to standard GOAP planning
        self.logger.debug("📊 Falling back to standard GOAP planning")
        try:
            plan = self.create_plan(current_state, goal_state, actions_config)
            if plan:
                self.logger.debug(f"📊 Standard GOAP planning created {len(plan)} action plan")
            else:
                self.logger.debug("📊 Standard GOAP planning found no valid plan")
            return plan
        except Exception as e:
            self.logger.warning(f"📊 Standard GOAP planning failed: {e}")
            return None
    
    def _create_discovery_plan(self, current_state: Dict[str, Any], 
                             goal_state: Dict[str, Any], 
                             actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Create a plan focused on discovery actions to gather needed knowledge.
        """
        # Create plan that prioritizes discovery actions
        discovery_focused_state = current_state.copy()
        
        # Adjust state to favor discovery actions
        discovery_focused_state.update({
            'need_workshop_discovery': True,
            'equipment_info_unknown': True,
            'material_requirements_known': False
        })
        
        return self.create_plan(discovery_focused_state, goal_state, actions_config)
    
    def _handle_cooldown_with_plan_insertion(self, current_plan: List[Dict], 
                                           action_index: int, 
                                           controller) -> List[Dict]:
        """
        Handle cooldown by inserting wait action into current plan instead of replanning.
        """
        # Get cooldown duration
        character_state = controller.get_current_world_state(force_refresh=True)
        cooldown_seconds = self._get_cooldown_duration(controller)
        
        if cooldown_seconds > 0:
            # Create wait action
            wait_action = {
                'name': 'wait',
                'wait_duration': cooldown_seconds,
                'description': f'Wait for {cooldown_seconds}s cooldown'
            }
            
            # Insert wait action at current position
            new_plan = current_plan.copy()
            new_plan.insert(action_index, wait_action)
            
            self.logger.info(f"🕐 Inserted {cooldown_seconds}s wait action into plan at position {action_index}")
            return new_plan
        
        return current_plan
    
    def _get_cooldown_duration(self, controller) -> float:
        """Get remaining cooldown duration in seconds."""
        try:
            if hasattr(controller, 'character_state') and controller.character_state:
                cooldown = controller.character_state.data.get('cooldown', 0)
                return max(0, cooldown)
        except Exception as e:
            self.logger.warning(f"Could not get cooldown duration: {e}")
        return 0
    
    def _is_discovery_action(self, action_name: str) -> bool:
        """
        Determine if an action is a discovery action that might provide new knowledge.
        
        Discovery actions should trigger replanning, execution actions should not.
        """
        discovery_actions = {
            'analyze_crafting_chain',
            'evaluate_weapon_recipes', 
            'find_monsters',
            'find_resources',
            'find_workshops',
            'find_correct_workshop',
            'lookup_item_info',
            'explore_map'
        }
        
        return action_name in discovery_actions
    
    def _should_replan_after_discovery(self, action: Dict[str, Any], 
                                     updated_state: Dict[str, Any]) -> bool:
        """
        Determine if replanning is needed after a discovery action.
        
        This should check if the discovery action provided significant new knowledge
        that would change the optimal plan.
        """
        action_name = action.get('name', '')
        
        # Only replan if discovery action provided NEW knowledge
        if action_name == 'find_correct_workshop':
            # Don't replan if workshop was already found in knowledge base
            # (no new API discovery was needed)
            return False
        elif action_name == 'analyze_crafting_chain':
            # Only replan if this provided new crafting knowledge
            # For now, allow one replan per chain analysis
            chain_replans = getattr(self, '_chain_analysis_replans', 0)
            if chain_replans >= 1:
                return False
            self._chain_analysis_replans = chain_replans + 1
            return True
        elif action_name == 'evaluate_recipes':
            # Only replan after recipe evaluation if we haven't already done so
            # Track if we've already evaluated and selected a recipe
            recipe_eval_replans = getattr(self, '_recipe_eval_replans', 0)
            if recipe_eval_replans >= 1:
                self.logger.debug("Already replanned after recipe evaluation, skipping replan")
                return False
            self._recipe_eval_replans = recipe_eval_replans + 1
            return True
        
        return False
    
    def _replan_from_current_position(self, controller, goal_state: Dict[str, Any],
                                    config_file: str = None, 
                                    remaining_actions: List[Dict] = None) -> Optional[List[Dict]]:
        """
        Replan from current position when action fails or new knowledge is acquired.
        """
        current_state = controller.get_current_world_state(force_refresh=True)
        actions_config = self._load_actions_from_config(config_file)
        
        if not actions_config:
            return None
        
        # Try knowledge-based planning first
        new_plan = self._create_knowledge_based_plan(
            current_state, goal_state, actions_config, controller
        )
        
        if new_plan:
            return new_plan
        
        # Fall back to discovery planning
        return self._create_discovery_plan(current_state, goal_state, actions_config)
    
    def _execute_single_action_with_learning(self, plan: List[Dict], controller, 
                                           current_state: Dict, goal_state: Dict) -> str:
        """
        Execute a single action from the plan, learn from the response, and determine next step.
        
        Returns:
            "goal_achieved" - Goal has been reached
            "continue" - Continue to next planning iteration  
            "failed" - Action failed, should replan
        """
        if not plan:
            return "failed"
            
        # Execute only the first action in the plan
        next_action = plan[0]
        action_name = next_action.get('name', 'unknown')
        
        self.logger.info(f"Executing single action: {action_name}")
        
        # Set up execution context
        controller.current_plan = plan
        controller.current_action_index = 0
        
        # Execute the single action
        action_success = controller._execute_single_action(action_name, next_action)
        
        if not action_success:
            self.logger.warning(f"Action {action_name} failed")
            return "failed"
        
        # Learn from the action execution
        self._learn_from_action_response(action_name, controller)
        
        # Check if goal was achieved after this action
        updated_state = controller.get_current_world_state(force_refresh=True)
        if self._is_goal_achieved(goal_state, updated_state):
            return "goal_achieved"
        
        # Action succeeded but goal not yet achieved - continue planning
        self.logger.info(f"Action {action_name} completed successfully - continuing to replan")
        return "continue"
    
    def _learn_from_action_response(self, action_name: str, controller) -> None:
        """
        Learn from action execution and update world knowledge.
        
        This is where we incorporate API responses into our planning knowledge.
        Each action type may provide different kinds of learning opportunities.
        """
        try:
            # Update character state to reflect any changes
            controller._refresh_character_state()
            
            # Action-specific learning patterns
            if action_name == "evaluate_weapon_recipes":
                self._learn_from_weapon_evaluation(controller)
            elif action_name == "find_correct_workshop":
                self._learn_from_workshop_discovery(controller)
            elif action_name == "transform_raw_materials":
                self._learn_from_material_transformation(controller)
            elif action_name == "craft_item":
                self._learn_from_crafting(controller)
            elif action_name in ["move", "gather_resources", "find_resources"]:
                self._learn_from_exploration(controller)
            
            # Save learned knowledge
            if hasattr(controller, 'knowledge_base') and controller.knowledge_base:
                controller.knowledge_base.save()
            if hasattr(controller, 'map_state') and controller.map_state:
                controller.map_state.save()
                
        except Exception as e:
            self.logger.warning(f"Learning from action {action_name} failed: {e}")
    
    def _learn_from_weapon_evaluation(self, controller) -> None:
        """Learn from weapon recipe evaluation results."""
        # Check if we have learned about available recipes
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'item_code' in context:
                self.logger.info(f"🧠 Learned: Selected weapon {context.get('item_code')} for crafting")
    
    def _learn_from_workshop_discovery(self, controller) -> None:
        """Learn from workshop finding results."""
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'workshop_location' in context:
                location = context['workshop_location']
                self.logger.info(f"🧠 Learned: Found workshop at {location}")
    
    def _learn_from_material_transformation(self, controller) -> None:
        """Learn from material transformation attempts."""
        # This is where we can learn about what materials are actually available
        # and what transformations are possible at different workshops
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'transformation_results' in context:
                results = context['transformation_results']
                self.logger.info(f"🧠 Learned: Material transformation results: {results}")
    
    def _learn_from_crafting(self, controller) -> None:
        """Learn from crafting attempts."""
        # Learn about successful/failed crafting attempts and requirements
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'crafting_result' in context:
                result = context['crafting_result']
                self.logger.info(f"🧠 Learned: Crafting result: {result}")
    
    def _learn_from_exploration(self, controller) -> None:
        """Learn from movement and exploration actions."""
        # Update map knowledge and resource/monster locations
        if hasattr(controller, 'map_state') and controller.map_state:
            self.logger.debug("🧠 Updated map knowledge from exploration")
    
    def _is_goal_achieved(self, goal_state: Dict[str, Any], 
                         current_state: Dict[str, Any]) -> bool:
        """Check if the goal state has been achieved."""
        self.logger.debug("🔍 Checking goal achievement:")
        self.logger.debug(f"  Goal state: {goal_state}")
        
        for key, value in goal_state.items():
            current_value = current_state.get(key, None)
            self.logger.debug(f"  Checking {key}: goal={value}, current={current_value}")
            
            if key not in current_state:
                self.logger.debug(f"  ❌ Missing key '{key}' in current state")
                return False
                
            if isinstance(value, str) and value.startswith('>'):
                # Handle greater-than conditions like "character_level: >2"
                target_value = int(value[1:])
                if current_state[key] <= target_value:
                    self.logger.debug(f"  ❌ {key}: {current_state[key]} <= {target_value}")
                    return False
            elif isinstance(value, str) and value.startswith('<'):
                # Handle less-than conditions
                target_value = int(value[1:])
                if current_state[key] >= target_value:
                    self.logger.debug(f"  ❌ {key}: {current_state[key]} >= {target_value}")
                    return False
            else:
                # Direct equality check
                if current_state[key] != value:
                    self.logger.debug(f"  ❌ {key}: {current_state[key]} != {value}")
                    return False
                else:
                    self.logger.debug(f"  ✅ {key}: {current_state[key]} == {value}")
        
        self.logger.debug("🎯 Goal achieved: All conditions met!")
        return True
    
    def _load_actions_from_config(self, config_file: str = None) -> Dict[str, Dict]:
        """
        Load action configurations for GOAP planning.
        
        Args:
            config_file: Path to action configuration file (optional, defaults to actions.yaml)
            
        Returns:
            Dictionary of action configurations
        """
        # Try to load from specified config file first
        if config_file:
            try:
                config_actions = ActionsData(config_file)
                actions = config_actions.get_actions()
                if actions:
                    self.logger.debug(f"Loaded {len(actions)} actions from {config_file}")
                    return actions
                else:
                    self.logger.warning(f"No actions found in {config_file}")
            except Exception as e:
                self.logger.warning(f"Could not load action config from {config_file}: {e}")
        
        # Fall back to default actions from default_actions.yaml
        try:
            default_actions_data = ActionsData(f"{CONFIG_PREFIX}/default_actions.yaml")
            default_actions = default_actions_data.get_actions()
            if default_actions:
                self.logger.debug(f"Loaded {len(default_actions)} default actions")
                return default_actions
            else:
                self.logger.error("No actions found in default_actions.yaml")
                return {}
        except Exception as e:
            self.logger.error(f"Could not load default actions: {e}")
            return {}
    
    def get_current_world(self) -> Optional[World]:
        """Get the current GOAP world instance."""
        return self.current_world
    
    def get_current_planner(self) -> Optional[Planner]:
        """Get the current GOAP planner instance."""
        return self.current_planner
    
    def reset_world(self) -> None:
        """Reset the current world and planner."""
        self.current_world = None
        self.current_planner = None
    
    def initialize_session_state(self, controller) -> None:
        """
        Initialize clean session state for XP-seeking goal achievement.
        
        This method ensures that GOAP planning starts with a clean state that
        requires find_monsters action, preventing incomplete 2-action plans.
        
        Args:
            controller: AI controller for state access and data persistence
        """
        try:
            # Reset action context to prevent stale coordinates
            if hasattr(controller, 'action_context'):
                controller.action_context = {}
            
            # Load start state defaults from configuration
            start_state_defaults = self._load_start_state_defaults()
            
            # Force critical states for XP-seeking cycle
            session_state = start_state_defaults.copy()
            session_state.update({
                # Ensure find_monsters is required for complete 3-action plans
                'monsters_available': False,
                'monster_present': False,
                'at_target_location': False,
                
                # Reset goal completion states
                'has_hunted_monsters': False,
                'monster_defeated': False,
                
                # Ensure character can act
                'character_alive': True,
                'character_safe': True,
                'can_move': True,
                'can_attack': True,
                'need_combat': True,
                
                # Clear cooldown states
                'is_on_cooldown': False,
                'needs_rest': False
            })
            
            # Initialize world state for GOAP planning
            if hasattr(controller, 'goap_data') and controller.goap_data:
                # Preserve existing structure but update critical values
                current_data = controller.goap_data.data.copy()
                current_data.update(session_state)
                controller.goap_data.data = current_data
                controller.goap_data.save()
                
                self.logger.info(f"🔧 Initialized session state with {len(session_state)} GOAP variables")
                self.logger.info("🎯 Ensured find_monsters → move → attack cycle will be planned")
            else:
                self.logger.warning("No GOAP data available for session state initialization")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize session state: {e}")
            # Continue execution with default behavior
    
    def _is_authentication_failure(self, action_name: str, controller) -> bool:
        """
        Detect authentication failures to prevent infinite retry loops.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller for error context
            
        Returns:
            True if authentication failure detected, False otherwise
        """
        try:
            # Check for authentication-related errors in recent log messages
            # This is a simple heuristic - could be enhanced with actual error inspection
            return False  # For now, let authentication failures be handled by the application
        except Exception:
            return False
    
    def _update_world_state_with_reactions(self, controller, action_name: str, actions_config: Dict[str, Dict]) -> None:
        """
        Update the world state with action reactions after successful execution.
        
        This ensures that the GOAP planner knows about state changes from completed actions.
        """
        if not actions_config or action_name not in actions_config:
            return
            
        action_config = actions_config[action_name]
        reactions = action_config.get('reactions', {})
        
        if reactions and hasattr(controller, 'world_state') and controller.world_state:
            # Update world state data with reactions
            if not controller.world_state.data:
                controller.world_state.data = {}
                
            for key, value in reactions.items():
                controller.world_state.data[key] = value
                self.logger.debug(f"Updated world state: {key} = {value}")
            
            # Save the updated world state
            controller.world_state.save()
            self.logger.debug(f"World state updated with reactions from {action_name}")
    
    def _is_coordinate_failure(self, action_name: str, controller) -> bool:
        """
        Detect coordinate/movement failures that require find_monsters replan.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller for error context
            
        Returns:
            True if coordinate failure detected, False otherwise
        """
        try:
            # Check if this is a move action failing due to missing coordinates
            if action_name == 'move':
                # Check if action context lacks target coordinates
                if hasattr(controller, 'action_context'):
                    context = controller.action_context
                    if context.get('target_x') is None or context.get('target_y') is None:
                        self.logger.info("🔍 Move action failed due to missing target coordinates")
                        return True
            return False
        except Exception as e:
            self.logger.warning(f"Error checking coordinate failure: {e}")
            return False
    
    def _create_recovery_plan_with_find_monsters(self, controller, goal_state: Dict[str, Any],
                                               config_file: str = None) -> Optional[List[Dict]]:
        """
        Create a recovery plan that starts with find_monsters to get fresh coordinates.
        
        Args:
            controller: AI controller
            goal_state: Desired goal state  
            config_file: Optional action configuration file
            
        Returns:
            List of action dictionaries for recovery plan
        """
        try:
            # Force a clean state that requires find_monsters
            recovery_state = controller.get_current_world_state(force_refresh=False)
            recovery_state.update({
                'monsters_available': False,
                'monster_present': False,
                'at_target_location': False
            })
            
            # Clear action context to force fresh coordinate discovery
            if hasattr(controller, 'action_context'):
                # Keep some context but remove location data
                preserved_context = {}
                for key in ['item_code', 'recipe_item_code', 'craft_skill']:
                    if key in controller.action_context:
                        preserved_context[key] = controller.action_context[key]
                controller.action_context = preserved_context
            
            # Load actions configuration
            actions_config = self._load_actions_from_config(config_file)
            if not actions_config:
                return None
            
            # Create plan with forced find_monsters requirement
            recovery_plan = self.create_plan(recovery_state, goal_state, actions_config)
            if recovery_plan:
                self.logger.info(f"🔄 Created recovery plan with {len(recovery_plan)} actions")
                return recovery_plan
            else:
                self.logger.warning("Failed to create recovery plan")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating recovery plan: {e}")
            return None
