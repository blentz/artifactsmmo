"""
GOAP Execution Management System

This module provides centralized GOAP planning and execution services,
eliminating redundant GOAP methods from the AI controller.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.lib.actions_data import ActionsData
from src.game.globals import CONFIG_PREFIX


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
        
        # Get all keys from start state, goal state, AND action conditions/reactions
        all_keys = set(start_state.keys()) | set(goal_state.keys())
        
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
        
        # Ensure start state has values for all required state variables
        complete_start_state = {}
        for key in all_keys:
            if key in start_state:
                complete_start_state[key] = start_state[key]
            else:
                # Default to False for missing boolean state variables
                complete_start_state[key] = False
        
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
            plans = planner.calculate()
            
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
        # Get current state
        current_state = controller.get_current_world_state(force_refresh=True)
        
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
        knowledge_based_plan = self._create_knowledge_based_plan(
            current_state, goal_state, actions_config, controller
        )
        
        if knowledge_based_plan:
            self.logger.info(f"📋 Created knowledge-based plan with {len(knowledge_based_plan)} actions")
            return knowledge_based_plan
        
        # If knowledge-based planning fails, create a discovery plan
        discovery_plan = self._create_discovery_plan(
            current_state, goal_state, actions_config
        )
        
        if discovery_plan:
            self.logger.info(f"🔍 Created discovery plan with {len(discovery_plan)} actions")
            return discovery_plan
        
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
            
            if not success:
                self.logger.warning(f"Action {action_name} failed")
                # For failed actions, try replanning from current position
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
        # Check if we have sufficient knowledge to plan
        knowledge_base = getattr(controller, 'knowledge_base', None)
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
        
        # For equipment goals, try to use analyze_crafting_chain
        if goal_state.get('has_better_weapon') or goal_state.get('need_equipment'):
            # First check if we already know what weapon to craft
            if hasattr(controller, 'action_context') and controller.action_context.get('item_code'):
                target_item = controller.action_context['item_code']
                
                # Use crafting chain analysis to build complete plan
                try:
                    chain_action_data = {'target_item': target_item}
                    context = controller._build_execution_context(chain_action_data)
                    
                    # Execute crafting chain analysis (this uses existing knowledge, no API calls)
                    from .actions.analyze_crafting_chain import AnalyzeCraftingChainAction
                    chain_analyzer = AnalyzeCraftingChainAction(controller.character_state.name, target_item)
                    
                    # This should use only existing knowledge
                    chain_result = chain_analyzer.execute(controller.client, **context)
                    
                    if chain_result and chain_result.get('success'):
                        action_sequence = chain_result.get('action_sequence', [])
                        if action_sequence:
                            self.logger.info(f"📋 Built {len(action_sequence)}-step plan from knowledge")
                            return action_sequence
                            
                except Exception as e:
                    self.logger.warning(f"Knowledge-based planning failed: {e}")
        
        # Fall back to standard GOAP planning
        return self.create_plan(current_state, goal_state, actions_config)
    
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
        elif action_name == 'evaluate_weapon_recipes':
            # Replan after weapon evaluation to incorporate weapon selection
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
        self.logger.debug(f"🔍 Checking goal achievement:")
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
        
        self.logger.debug(f"🎯 Goal achieved: All conditions met!")
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