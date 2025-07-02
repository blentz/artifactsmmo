"""
YAML-driven Action Executor for AI Player Controller.

This module provides a metaprogramming approach to action execution,
replacing hardcoded if-elif blocks with YAML-configurable action handling.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..game.globals import CONFIG_PREFIX
from ..lib.yaml_data import YamlData
from .action_factory import ActionFactory
from .action_validator import ActionValidator, ValidationResult


@dataclass
class ActionResult:
    """Result of action execution with metadata."""
    success: bool
    response: Any
    action_name: str
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class CompositeActionStep:
    """Definition of a step in a composite action."""
    name: str
    action: str
    required: bool = True
    params: Dict[str, Any] = None
    conditions: Dict[str, Any] = None
    on_failure: str = "continue"  # "continue", "abort", "retry"


class ActionExecutor:
    """
    YAML-driven action executor that handles both simple and composite actions.
    
    Eliminates the need for hardcoded if-elif blocks in the controller by using
    configuration-driven action execution with metaprogramming techniques.
    """
    
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        if config_path is None:
            config_path = f"{CONFIG_PREFIX}/action_configurations.yaml"
        
        self.config_data = YamlData(config_path)
        self.factory = ActionFactory(self.config_data)
        self._load_configurations()
        
        # Initialize action validator
        self.validator = ActionValidator()
        
        # Special handling for composite actions and learning
        self.learning_callbacks = {}
        self.state_updaters = {}
        
        # Feature flag for validation (can be configured)
        self.validation_enabled = True
    
    def _load_configurations(self) -> None:
        """Load action configurations from YAML."""
        try:
            configs = self.config_data.data.get('action_configurations', {})
            
            # Register YAML-defined actions
            for action_name, config in configs.items():
                if config.get('type') == 'yaml_defined':
                    self.factory.register_action_from_yaml(action_name, config)
                    
            self.logger.info(f"Loaded {len(configs)} action configurations")
            
        except Exception as e:
            self.logger.error(f"Failed to load action configurations: {e}")
    
    def execute_action(self, action_name: str, action_data: Dict[str, Any], 
                      client, context: Dict[str, Any] = None) -> ActionResult:
        """
        Execute an action using configuration-driven approach.
        
        Args:
            action_name: Name of the action to execute
            action_data: Data from the action plan
            client: API client for action execution
            context: Additional context (character state, etc.)
            
        Returns:
            ActionResult with execution details
        """
        context = context or {}
        start_time = None
        
        try:
            start_time = time.time()
            
            # Check if this is a composite action
            if self._is_composite_action(action_name):
                return self._execute_composite_action(action_name, action_data, client, context)
            
            # Handle special cases that require custom logic
            result = self._execute_special_action(action_name, action_data, client, context)
            if result:
                return result
            
            # Phase 1 - Pre-execution: Resolve template parameters
            resolved_action_data = self._resolve_action_parameters(action_name, action_data, context)
            
            # Phase 2 - Validation: Validate action parameters and preconditions
            if self.validation_enabled:
                validation_result = self._validate_action(action_name, resolved_action_data, context, client)
                if not validation_result.is_valid:
                    execution_time = time.time() - start_time if start_time else None
                    return ActionResult(
                        success=False,
                        response={'validation_errors': [e.__dict__ for e in validation_result.errors]},
                        action_name=action_name,
                        execution_time=execution_time,
                        error_message=f"Validation failed: {validation_result.summary}",
                        metadata={'validation_failed': True}
                    )
            
            # Phase 3 - Execution: Standard action execution through factory
            success, response = self.factory.execute_action(action_name, resolved_action_data, client, context)
            
            # Convert response to dict if needed
            if not isinstance(response, dict):
                response = {'data': response, 'success': success}
            
            # Phase 4 - Post-execution processing - UNIFIED handler
            # Always get controller from context (ActionContext has controller attribute)
            controller = context.controller if hasattr(context, 'controller') else context.get('controller') if isinstance(context, dict) else None
            if controller:
                self.apply_post_execution_updates(action_name, response, controller, context)
            
            execution_time = time.time() - start_time if start_time else None
            
            return ActionResult(
                success=success,
                response=response,
                action_name=action_name,
                execution_time=execution_time,
                metadata={'factory_execution': True}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            execution_time = time.time() - start_time if start_time else None
            
            return ActionResult(
                success=False,
                response=None,
                action_name=action_name,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _is_composite_action(self, action_name: str) -> bool:
        """Check if an action is defined as composite."""
        try:
            composite_actions = self.config_data.data.get('composite_actions', {})
            return action_name in composite_actions
        except TypeError:
            # Handle case where config_data.data is a Mock
            return False
    
    def _execute_composite_action(self, action_name: str, action_data: Dict[str, Any],
                                 client, context: Dict[str, Any]) -> ActionResult:
        """Execute a composite action with multiple steps."""
        composite_config = self.config_data.data.get('composite_actions', {}).get(action_name, {})
        steps = composite_config.get('steps', [])
        
        if not steps:
            return ActionResult(
                success=False,
                response=None,
                action_name=action_name,
                error_message=f"No steps defined for composite action {action_name}"
            )
        
        step_results = []
        overall_success = True
        
        for step_config in steps:
            step = CompositeActionStep(
                name=step_config['name'],
                action=step_config['action'],
                required=step_config.get('required', True),
                params=step_config.get('params', {}),
                conditions=step_config.get('conditions', {}),
                on_failure=step_config.get('on_failure', 'continue')
            )
            
            # Check conditions
            if not self._check_step_conditions(step.conditions, context):
                self.logger.debug(f"Skipping step {step.name} - conditions not met")
                continue
            
            # Merge step params with action data
            step_action_data = {**action_data, **step.params}
            step_action_data = self._resolve_parameter_templates(step_action_data, action_data, context)
            
            # Execute step
            step_result = self.execute_action(step.action, step_action_data, client, context)
            step_results.append(step_result)
            
            if not step_result.success:
                if step.required and step.on_failure == 'abort':
                    overall_success = False
                    break
                elif step.required:
                    overall_success = False
        
        return ActionResult(
            success=overall_success,
            response={'steps': step_results, 'composite': True},
            action_name=action_name,
            metadata={'composite_execution': True, 'steps_count': len(step_results)}
        )
    
    def _check_step_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if step conditions are met."""
        if not conditions:
            return True
        
        for condition, expected_value in conditions.items():
            if condition == 'monster_found':
                # Check if previous find_monsters was successful
                continue  # Simplified for now
            elif condition == 'hp_low':
                char_state = context.get('character_state')
                if char_state:
                    hp = char_state.data.get('hp', 100)
                    max_hp = char_state.data.get('max_hp', 100)
                    hp_percent = (hp / max_hp) * 100 if max_hp > 0 else 100
                    if expected_value and hp_percent > 30:  # Not low
                        return False
        
        return True
    
    def _resolve_parameter_templates(self, params: Dict[str, Any], 
                                   action_data: Dict[str, Any], 
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter templates like ${action_data.search_radius:15}."""
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                # Parse template: ${source.key:default}
                template = value[2:-1]  # Remove ${ and }
                if ':' in template:
                    path, default = template.split(':', 1)
                    try:
                        default = int(default)
                    except ValueError:
                        pass  # Keep as string
                else:
                    path, default = template, None
                
                # Resolve the path
                if path.startswith('action_data.'):
                    key_name = path[12:]  # Remove 'action_data.'
                    resolved[key] = action_data.get(key_name, default)
                elif path.startswith('context.'):
                    key_name = path[8:]  # Remove 'context.'
                    resolved[key] = context.get(key_name, default)
                else:
                    resolved[key] = default
            else:
                resolved[key] = value
        
        return resolved
    
    def _execute_special_action(self, action_name: str, action_data: Dict[str, Any],
                               client, context: Dict[str, Any]) -> Optional[ActionResult]:
        """Handle special actions that require custom logic (like hunt)."""
        if action_name == 'hunt':
            return self._execute_hunt_action(action_data, client, context)
        return None
    
    def _execute_hunt_action(self, action_data: Dict[str, Any], 
                            client, context: Dict[str, Any]) -> ActionResult:
        """Execute hunt action with intelligent monster search."""
        try:
            # Use intelligent search from context if available
            controller = context.get('controller')
            if controller and hasattr(controller, 'intelligent_monster_search'):
                search_radius = action_data.get('search_radius', 8)
                success = controller.intelligent_monster_search(search_radius)
                
                if success:
                    # Attack if monster found
                    char_name = context.get('character_state', {}).name if context.get('character_state') else None
                    if char_name:
                        attack_result = self.execute_action('attack', {'character_name': char_name}, client, context)
                        return ActionResult(
                            success=attack_result.success,
                            response=attack_result.response,
                            action_name='hunt',
                            metadata={'hunt_method': 'intelligent_search'}
                        )
                
                return ActionResult(
                    success=False,
                    response=None,
                    action_name='hunt',
                    error_message="No monsters found during hunt"
                )
            else:
                # Fallback to composite action
                return self._execute_composite_action('hunt', action_data, client, context)
                
        except Exception as e:
            return ActionResult(
                success=False,
                response=None,
                action_name='hunt',
                error_message=f"Hunt action failed: {str(e)}"
            )
    
    def _handle_learning_callbacks(self, action_name: str, response: Any, context: Dict[str, Any]) -> None:
        """Handle learning callbacks for actions."""
        controller = context.get('controller')
        if not controller:
            return
        
        try:
            if action_name == 'move' and hasattr(controller, 'learn_from_map_exploration'):
                if hasattr(response, 'data') and hasattr(response.data, 'character'):
                    char = response.data.character
                    controller.learn_from_map_exploration(char.x, char.y, response)
            
            elif action_name == 'attack' and hasattr(controller, 'learn_from_combat'):
                self.logger.info(f"🔍 Processing attack learning for response: {type(response)}")
                
                # Handle both object responses and dict responses
                if isinstance(response, dict) and 'fight_response' in response:
                    # AttackAction returns a dict with fight_response key
                    actual_response = response.get('fight_response')
                    if hasattr(actual_response, 'data'):
                        response = actual_response  # Use the actual API response
                
                if hasattr(response, 'data'):
                    # Initialize variables
                    fight_data = None
                    monster_code = 'unknown'
                    result = 'unknown'
                    
                    # Primary extraction: response.data.fight
                    if hasattr(response.data, 'fight'):
                        fight_data = response.data.fight
                        self.logger.debug(f"🔍 Found fight data object: {type(fight_data)}")
                        
                        # Extract monster information with improved error handling
                        try:
                            if hasattr(fight_data, 'monster'):
                                monster = fight_data.monster
                                self.logger.debug(f"🔍 Monster object type: {type(monster)}")
                                
                                if hasattr(monster, 'code'):
                                    monster_code = str(monster.code)
                                elif hasattr(monster, 'name'): 
                                    monster_code = str(monster.name)
                                elif isinstance(monster, dict):
                                    monster_code = monster.get('code') or monster.get('name', 'unknown')
                                elif isinstance(monster, str):
                                    monster_code = monster
                                else:
                                    # Last resort: try to convert to string
                                    monster_code = str(monster) if monster else 'unknown'
                            
                            # Extract result with improved error handling
                            if hasattr(fight_data, 'result'):
                                result = str(fight_data.result) if fight_data.result else 'unknown'
                                
                        except Exception as e:
                            self.logger.warning(f"⚠️ Error extracting fight data: {e}")
                    
                    # Fallback extraction: try to get monster from combat location via map
                    if monster_code == 'unknown':
                        try:
                            # PRIORITY 1: Use target location from action context (where find_monsters found the monster)
                            combat_x, combat_y = None, None
                            if context and ('target_x' in context and 'target_y' in context):
                                combat_x, combat_y = context['target_x'], context['target_y']
                                self.logger.info(f"🔍 Got combat location from action context: ({combat_x}, {combat_y})")
                            elif context and ('x' in context and 'y' in context):
                                combat_x, combat_y = context['x'], context['y']
                                self.logger.info(f"🔍 Got combat location from action context: ({combat_x}, {combat_y})")
                            
                            # PRIORITY 2: Get character position from the combat response 
                            elif hasattr(response, 'data') and hasattr(response.data, 'character'):
                                combat_char = response.data.character
                                if hasattr(combat_char, 'x') and hasattr(combat_char, 'y'):
                                    combat_x, combat_y = combat_char.x, combat_char.y
                                    self.logger.info(f"🔍 Combat location from response: ({combat_x}, {combat_y})")
                            
                            # PRIORITY 3: Fallback to current character state position (for direct attacks)
                            elif hasattr(controller, 'character_state') and hasattr(controller.character_state, 'data'):
                                char_state = controller.character_state
                                combat_x = char_state.data.get('x', 0)
                                combat_y = char_state.data.get('y', 0)
                                self.logger.info(f"🔍 Using character state position (direct attack): ({combat_x}, {combat_y})")
                            
                            # Look up monster at combat location
                            if combat_x is not None and combat_y is not None and hasattr(controller, 'map_state') and controller.map_state:
                                location_key = f"{combat_x},{combat_y}"
                                self.logger.debug(f"🔍 Looking for monster at location: {location_key}")
                                
                                location_data = controller.map_state.data.get(location_key, {})
                                if location_data:
                                    content = location_data.get('content', {})
                                    if content and content.get('type') == 'monster':
                                        monster_code = content.get('code', 'unknown')
                                        self.logger.info(f"🔍 ✅ SUCCESS: Extracted monster '{monster_code}' from map location ({combat_x},{combat_y})")
                                    else:
                                        self.logger.debug(f"🔍 Location ({combat_x},{combat_y}) content: {content}")
                                else:
                                    self.logger.debug(f"🔍 No location data found for position ({combat_x},{combat_y})")
                                    
                        except Exception as e:
                            self.logger.warning(f"🔍 Fallback monster extraction failed: {e}")
                    
                    # If we have response but still no data, try alternative structure
                    if monster_code == 'unknown' and result == 'unknown':
                        # Check if response has different structure
                        try:
                            # Sometimes the data might be nested differently
                            if hasattr(response, 'parsed') and hasattr(response.parsed, 'fight'):
                                alt_fight = response.parsed.fight
                                if hasattr(alt_fight, 'monster'):
                                    monster_code = str(alt_fight.monster.code if hasattr(alt_fight.monster, 'code') else alt_fight.monster)
                                if hasattr(alt_fight, 'result'):
                                    result = str(alt_fight.result)
                        except Exception as e:
                            self.logger.debug(f"Alternative extraction failed: {e}")
                    
                    # Get pre-combat HP from context - this should be the HP before the attack
                    pre_combat_hp = context.get('pre_combat_hp', 0)
                    post_combat_hp = None
                    
                    # Extract post-combat HP from the response
                    if hasattr(response, 'data') and hasattr(response.data, 'character'):
                        post_combat_char = response.data.character
                        if hasattr(post_combat_char, 'hp'):
                            post_combat_hp = post_combat_char.hp
                            self.logger.debug(f"🔍 Post-combat HP from response: {post_combat_hp}")
                    
                    # If no pre-combat HP in context, estimate it
                    if pre_combat_hp == 0:
                        if post_combat_hp is not None:
                            # Try to calculate pre-combat HP from fight data
                            if fight_data:
                                # Look for damage taken or calculate from turns
                                damage_taken = 0
                                if hasattr(fight_data, 'damage') and fight_data.damage:
                                    damage_taken = fight_data.damage
                                elif result == 'loss' and hasattr(fight_data, 'turns') and fight_data.turns:
                                    # Estimate damage based on turns for losses
                                    damage_taken = min(100, fight_data.turns * 5)  # ~5 HP per turn
                                
                                if damage_taken > 0:
                                    pre_combat_hp = post_combat_hp + damage_taken
                                    self.logger.debug(f"🔍 Calculated pre-combat HP: {post_combat_hp} + {damage_taken} = {pre_combat_hp}")
                                else:
                                    # Default to max HP if we can't calculate damage
                                    max_hp = getattr(post_combat_char, 'max_hp', 125) if hasattr(response.data, 'character') else 125
                                    pre_combat_hp = max_hp
                            else:
                                # No fight data, assume started at max HP
                                max_hp = getattr(post_combat_char, 'max_hp', 125) if hasattr(response.data, 'character') else 125
                                pre_combat_hp = max_hp
                        else:
                            # Fallback to current character state
                            current_hp = controller.character_state.data.get('hp', 0) if hasattr(controller, 'character_state') else 125
                            pre_combat_hp = current_hp
                    
                    self.logger.info(f"🔍 Final combat data - Monster: '{monster_code}', Result: '{result}', Pre-HP: {pre_combat_hp}, Post-HP: {post_combat_hp}")
                    
                    # Process the learning if we have valid data
                    if monster_code != 'unknown' or result != 'unknown':
                        self.logger.info(f"⚔️ Recording combat: {monster_code} - {result}")
                        
                        # Convert fight_data to dict for knowledge base
                        fight_dict = {}
                        if fight_data:
                            # Safely extract all available fight attributes
                            for attr in ['xp', 'gold', 'drops', 'turns', 'duration', 'damage']:
                                try:
                                    if hasattr(fight_data, attr):
                                        value = getattr(fight_data, attr)
                                        if value is not None:
                                            # Handle drops specially to convert DropSchema objects to dicts
                                            if attr == 'drops' and value is not None:
                                                if isinstance(value, list):
                                                    serializable_drops = []
                                                    for drop in value:
                                                        if drop is None:
                                                            continue  # Skip None entries
                                                        elif hasattr(drop, '__dict__') and hasattr(drop, 'code'):
                                                            # Convert DropSchema object to dict
                                                            drop_dict = {
                                                                'code': getattr(drop, 'code', None),
                                                                'quantity': getattr(drop, 'quantity', 0)
                                                            }
                                                            serializable_drops.append(drop_dict)
                                                        elif isinstance(drop, dict):
                                                            # Already a dict, just keep essential fields
                                                            serializable_drops.append({
                                                                'code': drop.get('code'),
                                                                'quantity': drop.get('quantity', 0)
                                                            })
                                                        elif isinstance(drop, str):
                                                            # Legacy string format - keep for backward compatibility
                                                            serializable_drops.append(drop)
                                                        else:
                                                            # Unknown format, try to store as-is
                                                            serializable_drops.append(drop)
                                                    fight_dict[attr] = serializable_drops
                                                else:
                                                    # Single drop item, handle similarly
                                                    if hasattr(value, '__dict__'):
                                                        fight_dict[attr] = {
                                                            'code': getattr(value, 'code', None),
                                                            'quantity': getattr(value, 'quantity', 0)
                                                        }
                                                    else:
                                                        fight_dict[attr] = value
                                            else:
                                                fight_dict[attr] = value
                                except Exception as e:
                                    self.logger.debug(f"Failed to extract {attr}: {e}")
                        
                        # Always call learning even with partial data - knowledge base can handle it
                        # Pass both pre and post combat HP
                        combat_context = {
                            'pre_combat_hp': pre_combat_hp,
                            'post_combat_hp': post_combat_hp
                        }
                        controller.learn_from_combat(monster_code, result, pre_combat_hp, fight_dict, combat_context)
                    else:
                        self.logger.debug(f"🔍 No combat data available to record - monster: {monster_code}, result: {result}")
                else:
                    self.logger.warning("⚠️ No response data available for attack learning")
            
        
        except Exception as e:
            self.logger.warning(f"Learning callback failed for {action_name}: {e}")
    
    
    def apply_post_execution_updates(self, action_name: str, action_result: Dict, 
                                    controller, context) -> None:
        """
        Unified handler for ALL state updates after action execution.
        This is the ONLY place where state should be modified.
        """
        
        if not action_result.get('success', False):
            self.logger.debug(f"Skipping state updates for failed action {action_name}")
            return
            
        # 1. Apply GOAP reactions from action class
        self._apply_goap_reactions(action_name, action_result, controller, context)
        
        # 2. Update action context for inter-action data flow
        self._update_action_context(action_name, action_result, controller)
        
        # 3. Process any state changes returned by the action
        self._apply_action_state_changes(action_name, action_result, controller)
        
        # 4. Handle learning callbacks (existing functionality)
        self._handle_learning_callbacks(action_name, action_result, {'controller': controller})
        
        # 5. Persist state changes (if needed)
        self._persist_state_changes(controller)
        
        self.logger.debug(f"✓ Post-execution updates completed for {action_name}")
    
    def _apply_goap_reactions(self, action_name: str, action_result: Dict, 
                             controller, context) -> None:
        """Apply GOAP reactions with proper template resolution."""
        
        # Get action class to access reactions
        action_class = self._get_action_class(action_name)
        if not action_class:
            return
            
        reactions = getattr(action_class, 'reactions', {})
        if not reactions:
            return
            
        # Get current world state
        world_state = controller.get_current_world_state()
        
        # Resolve templates and apply reactions
        for state_group, group_reactions in reactions.items():
            if isinstance(group_reactions, dict):
                # Handle nested state groups (e.g., equipment_status)
                if state_group not in world_state:
                    world_state[state_group] = {}
                    
                for key, value in group_reactions.items():
                    resolved_key = self._resolve_template(key, context, action_result)
                    resolved_value = self._resolve_template(value, context, action_result)
                    
                    # Handle increment operations for counter fields
                    if resolved_key in ['steps_completed'] and resolved_value == 1:
                        # Get current value and increment
                        current_val = world_state.get(state_group, {}).get(resolved_key, 0)
                        resolved_value = current_val + 1
                        self.logger.debug(f"Incrementing {state_group}.{resolved_key}: {current_val} -> {resolved_value}")
                    
                    # Update nested state
                    world_state[state_group][resolved_key] = resolved_value
                    
                    self.logger.debug(f"Applied reaction: {state_group}.{resolved_key} = {resolved_value}")
            else:
                # Handle flat state values
                resolved_value = self._resolve_template(group_reactions, context, action_result)
                world_state[state_group] = resolved_value
                
        # Update world state in controller
        controller.update_world_state(world_state)
        self.logger.debug(f"Updated world state via reactions: {world_state}")
    
    def _resolve_template(self, template: Any, context, action_result: Dict) -> Any:
        """Resolve template variables in reaction values."""
        
        if not isinstance(template, str):
            return template
            
        if not template.startswith('${'):
            return template
            
        # Extract variable name
        var_name = template[2:-1]  # Remove ${ and }
        
        # Resolution priority order:
        # 1. Check action result
        if var_name in action_result:
            return action_result[var_name]
            
        # 2. Check action context
        if hasattr(context, var_name):
            return getattr(context, var_name)
            
        # 3. Check controller from context
        controller = context.controller if hasattr(context, 'controller') else context.get('controller') if isinstance(context, dict) else None
        if controller:
            world_state = controller.get_current_world_state()
            for state_group, group_data in world_state.items():
                if isinstance(group_data, dict) and var_name in group_data:
                    return group_data[var_name]
                    
        # 4. Check action context results from previous actions
        if hasattr(context, 'action_results') and context.action_results:
            for prev_action, prev_result in context.action_results.items():
                if isinstance(prev_result, dict) and var_name in prev_result:
                    return prev_result[var_name]
                    
        self.logger.warning(f"Could not resolve template variable: {template}")
        return None
    
    def _update_action_context(self, action_name: str, action_result: Dict, controller) -> None:
        """Update action context for inter-action data flow."""
        
        # Store action result in controller's action context
        if not hasattr(controller, 'action_context'):
            controller.action_context = {}
            
        controller.action_context[action_name] = {
            'result': action_result,
            'timestamp': time.time()
        }
        
        # Also store specific values that might be used as template variables
        if 'selected_item' in action_result:
            controller.action_context['selected_item'] = action_result['selected_item']
        if 'target_slot' in action_result:
            controller.action_context['target_slot'] = action_result['target_slot']
            
        self.logger.debug(f"Updated action context with results from {action_name}")
    
    def _apply_action_state_changes(self, action_name: str, action_result: Dict, 
                                   controller) -> None:
        """Apply any explicit state changes returned by the action."""
        
        # Check for state changes in standard locations
        state_changes = {}
        
        # 1. Check 'state_changes' key (preferred)
        if 'state_changes' in action_result:
            state_changes.update(action_result['state_changes'])
            
        # 2. Check specific state keys (backward compatibility)
        state_keys = ['equipment_status', 'character_status', 'location_context', 
                      'combat_context', 'materials', 'skills', 'goal_progress']
        
        for key in state_keys:
            if key in action_result and isinstance(action_result[key], dict):
                state_changes[key] = action_result[key]
                
        # Apply all state changes
        if state_changes:
            world_state = controller.get_current_world_state()
            for key, value in state_changes.items():
                if isinstance(value, dict) and key in world_state and isinstance(world_state[key], dict):
                    # Merge nested dictionaries
                    world_state[key].update(value)
                else:
                    # Replace value
                    world_state[key] = value
                    
            controller.update_world_state(world_state)
            self.logger.debug(f"Applied {len(state_changes)} state changes from {action_name}")
    
    def _persist_state_changes(self, controller) -> None:
        """Persist state changes if needed."""
        # This is a placeholder for future state persistence needs
        # Currently, state is persisted by the controller when needed
        pass
    
    def _validate_action(self, action_name: str, action_data: Dict[str, Any], 
                        context: Any, client: Any = None) -> ValidationResult:
        """
        Validate action parameters and preconditions.
        
        Args:
            action_name: Name of the action to validate
            action_data: Resolved action parameters
            context: Execution context
            
        Returns:
            ValidationResult indicating if action is valid to execute
        """
        # Extract parameters for validation
        # Some actions have params nested, others have them at top level
        params = action_data.copy()
        
        # If params are nested under 'params' key, merge them to top level for validation
        if 'params' in params and isinstance(params['params'], dict):
            nested_params = params.pop('params')
            params.update(nested_params)
        
        # Run validation
        return self.validator.validate_action(action_name, params, context, client)
    
    def _resolve_action_parameters(self, action_name: str, action_data: Dict, context: Dict) -> Dict:
        """Resolve template parameters in action data before execution."""
        
        resolved_data = action_data.copy()
        
        # Get controller from context for world state access
        controller = context.get('controller')
        if not controller:
            return resolved_data
            
        # Special handling for equip action
        if action_name == 'equip' and 'params' not in resolved_data:
            resolved_data['params'] = {}
            
            # Get world state to find selected_item
            world_state = controller.get_current_world_state()
            equipment_status = world_state.get('equipment_status', {})
            
            # Try to get item_code from various sources
            item_code = None
            
            # 1. Check equipment_status.selected_item
            if 'selected_item' in equipment_status:
                item_code = equipment_status['selected_item']
                
            # 2. Check action context
            if not item_code and hasattr(controller, 'action_context'):
                item_code = controller.action_context.get('selected_item')
                
            # Set parameters for equip action
            if item_code:
                resolved_data['params']['item_code'] = item_code
                resolved_data['params']['slot'] = equipment_status.get('target_slot', 'weapon')
                self.logger.debug(f"Resolved equip parameters: item_code={item_code}, slot={resolved_data['params']['slot']}")
        
        # General template resolution for params
        if 'params' in resolved_data:
            for key, value in resolved_data['params'].items():
                if isinstance(value, str) and value.startswith('${'):
                    resolved_value = self._resolve_template(value, context, {})
                    if resolved_value is not None:
                        resolved_data['params'][key] = resolved_value
                        
        return resolved_data
    
    def _get_action_class(self, action_name: str):
        """Get action class by name for accessing GOAP metadata."""
        
        # Try to get from factory's action map
        if hasattr(self.factory, 'action_class_map'):
            action_class = self.factory.action_class_map.get(action_name)
            if action_class:
                return action_class
                
        # Try to import dynamically from action configurations
        action_config = self.config_data.data.get('action_classes', {}).get(action_name)
        if action_config:
            try:
                module_path, class_name = action_config.rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                return getattr(module, class_name)
            except Exception as e:
                self.logger.debug(f"Could not import action class {action_name}: {e}")
                
        return None
    
    def register_learning_callback(self, action_name: str, callback) -> None:
        """Register a learning callback for an action."""
        self.learning_callbacks[action_name] = callback
    
    def register_state_updater(self, action_name: str, updater) -> None:
        """Register a state updater for an action."""
        self.state_updaters[action_name] = updater
    
    def get_available_actions(self) -> List[str]:
        """Get list of all available actions (simple + composite)."""
        simple_actions = self.factory.get_available_actions()
        composite_actions = list(self.config_data.data.get('composite_actions', {}).keys())
        return simple_actions + composite_actions
    
    def reload_configuration(self) -> None:
        """Reload action configurations from YAML."""
        self.config_data.load()
        self._load_configurations()
        self.validator.reload_configuration()
        self.logger.info("Action configurations and validation rules reloaded")
