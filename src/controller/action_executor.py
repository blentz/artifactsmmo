"""
YAML-driven Action Executor for AI Player Controller.

This module provides a metaprogramming approach to action execution,
replacing hardcoded if-elif blocks with YAML-configurable action handling.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from ..game.globals import CONFIG_PREFIX
from ..lib.yaml_data import YamlData
from ..lib.state_parameters import StateParameters
from .action_factory import ActionFactory
from .actions.base import ActionResult


from dataclasses import dataclass



class ActionExecutor:
    """
    YAML-driven action executor that handles GOAP actions through metaprogramming.
    
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
        
        # Learning callbacks for action execution
        self.learning_callbacks = {}
        self.state_updaters = {}
    
    def _load_configurations(self) -> None:
        """Load action configurations from YAML."""
        try:
            configs = self.config_data.data.get('action_configurations', {})
            self.logger.info(f"Loaded {len(configs)} action configurations")
            
        except Exception as e:
            self.logger.error(f"Failed to load action configurations: {e}")
    
    def get_action_configurations(self) -> Dict[str, Any]:
        """Get action configurations for GOAP planning."""
        return self.config_data.data.get('action_configurations', {})
    
    def execute_action(self, action_name: str, client, context: Any) -> ActionResult:
        """
        Execute an action using configuration-driven approach.
        
        Args:
            action_name: Name of the action to execute
            client: API client for action execution
            context: ActionContext instance with unified state
            
        Returns:
            ActionResult with execution details
        """
        # Context is required - no fallback needed
        if context is None:
            raise ValueError("ActionContext is required for action execution")
        
        start_time = None
        
        try:
            start_time = time.time()
            
            
            # All actions should go through GOAP planning - no special cases
            
            # Phase 1 - Pre-execution: Parameters are already in context
            
            # Phase 2 - Validation: Handled by unified context architecture
            # StateParameters provides built-in validation and type checking
            
            # Phase 3 - Execution: Standard action execution through factory
            final_result = self.factory.execute_action(action_name, client, context)
            
            # All actions must return ActionResult now
            if not isinstance(final_result, ActionResult):
                raise TypeError(f"Action {action_name} must return ActionResult, got {type(final_result)}")
            
            # Phase 4 - Post-execution processing - UNIFIED handler
            # Get controller from unified context
            controller = getattr(context, 'controller', None)
            if controller:
                self.apply_post_execution_updates(action_name, final_result, controller, context)
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            
            return ActionResult(
                success=False,
                error=str(e),
                action_name=action_name
            )
    
    
    
    def _handle_learning_callbacks(self, action_name: str, response: Any, context: Any) -> None:
        """Handle learning callbacks for actions."""
        controller = getattr(context, 'controller', None) if context else None
        if not controller:
            return
        
        try:
            # Configuration-driven learning callbacks
            learning_handlers = {
                'move': self._handle_move_learning,
                'attack': self._handle_attack_learning
            }
            
            handler = learning_handlers.get(action_name)
            if handler:
                handler(controller, response)
        
        except Exception as e:
            self.logger.warning(f"Learning callback failed for {action_name}: {e}")
    
    def _handle_move_learning(self, controller, response) -> None:
        """Handle learning for move actions - methods removed and replaced with KnowledgeBase helpers."""
        # Learning methods were removed from controller and replaced with KnowledgeBase helpers
        # that actions can use directly when needed
        pass
    
    def _handle_attack_learning(self, controller, response) -> None:
        """Handle learning for attack actions - methods removed and replaced with KnowledgeBase helpers."""
        # Learning methods were removed from controller and replaced with KnowledgeBase helpers
        # that actions can use directly when needed
        pass


    def apply_post_execution_updates(self, action_name: str, action_result: ActionResult, 
                                    controller, context) -> None:
        """
        Unified handler for ALL state updates after action execution.
        This is the ONLY place where state should be modified.
        """
        
        if not action_result.success:
            self.logger.debug(f"Skipping state updates for failed action {action_name}")
            return
            
        # Skip post-execution updates if action requested a subgoal
        # The GOAP manager will handle the recursive execution and state management
        if hasattr(action_result, 'subgoal_request') and action_result.subgoal_request:
            self.logger.debug(f"⏸️ Skipping post-execution updates for {action_name} - subgoal requested")
            return
            
        try:
            # 1. Apply unified state changes (GOAP reactions + action context + explicit)
            self._apply_unified_state_changes(action_name, action_result, controller, context)
            
            # 2. Update action context for inter-action data flow
            self._update_action_context(action_name, action_result, controller)
            
            # 3. Handle learning callbacks (existing functionality)
            # Pass context directly since it has controller attribute
            self._handle_learning_callbacks(action_name, action_result, context)
            
        except Exception as e:
            self.logger.error(f"Error in post-execution updates for {action_name}: {e}")
            # Don't re-raise - we want execution to continue even if state updates fail
        
        # 5. Persist state changes (if needed)
        self._persist_state_changes(controller)
        
        self.logger.debug(f"✓ Post-execution updates completed for {action_name}")
    
    def _apply_unified_state_changes(self, action_name: str, action_result: ActionResult, 
                                    controller, context) -> None:
        """Apply unified state changes from GOAP reactions and action context."""
        
        # Track only the changes to pass to update_world_state
        state_changes = {}
        
        # 1. Handle explicit state changes from ActionResult
        if action_result.state_changes:
            self.logger.debug(f"Adding explicit state changes from ActionResult: {action_result.state_changes}")
            state_changes.update(action_result.state_changes)
        
        # 2. Apply GOAP reactions from action class
        self._collect_goap_reactions(action_name, action_result, controller, context, state_changes)
        
        # 3. Apply action context results (equipment workflow)
        self._collect_action_context_results(action_name, action_result, state_changes)
        
        # Apply all collected state changes in one operation
        if state_changes:
            self.logger.debug(f"About to update world state with unified changes: {state_changes}")
            
            # Update context with flat StateParameters
            for param_name, value in state_changes.items():
                context.set(param_name, value)
            
            # Recalculate boolean flags after state changes to maintain consistency
            self._recalculate_boolean_flags(context)
            
            self.logger.debug(f"Updated world state via unified changes: {state_changes}")
        else:
            self.logger.debug(f"No state changes collected for {action_name}")
    
    def _collect_goap_reactions(self, action_name: str, action_result: ActionResult, 
                               controller, context, state_changes: Dict) -> None:
        """Collect GOAP reactions into state changes using direct value assignment."""
        
        self.logger.debug(f"🔧 GOAP REACTIONS: Looking for reactions on {action_name}")
        
        # Get reactions with priority: instance-level > YAML > class-level
        reactions = None
        
        # Check for instance-level reactions first (for dynamic modifications like combat defeats)
        if hasattr(context, 'action_instance') and context.action_instance:
            reactions = getattr(context.action_instance, 'reactions', {})
            if reactions:
                self.logger.debug(f"🔧 Instance reactions for {action_name}: {reactions}")
        
        if not reactions:
            # Load reactions from default_actions.yaml which contains the GOAP definitions
            from src.lib.yaml_data import YamlData
            from src.game.globals import CONFIG_PREFIX
            default_actions_data = YamlData(f"{CONFIG_PREFIX}/default_actions.yaml")
            actions_config = default_actions_data.data.get('actions', {})
            action_config = actions_config.get(action_name, {})
            reactions = action_config.get('reactions', {})
            
            if reactions:
                self.logger.debug(f"🔧 YAML reactions for {action_name}: {reactions}")
        
        if not reactions:
            # Fall back to action class reactions if no instance or YAML reactions
            action_class = self._get_action_class(action_name)
            if action_class:
                reactions = getattr(action_class, 'reactions', {})
                if reactions:
                    self.logger.debug(f"🔧 Class reactions for {action_name}: {reactions}")
            
        if not reactions:
            self.logger.warning(f"🔧 No reactions found for {action_name}")
            return
            
        # Get current world state for reference
        world_state = controller.get_current_world_state()
        
        # Apply direct value assignment using flat StateParameters
        for param_name, value in reactions.items():
            # Validate parameter is registered
            if not StateParameters.validate_parameter(param_name):
                self.logger.warning(f"Unknown parameter '{param_name}' in reactions for {action_name}")
                continue
                
            # Handle increment operations for counter fields
            if param_name.endswith('.steps_completed') and value == 1:
                # Get current value and increment
                current_val = context.get(param_name, 0)
                value = current_val + 1
                self.logger.debug(f"Incrementing {param_name}: {current_val} -> {value}")
            
            # Direct value assignment using StateParameters
            state_changes[param_name] = value
            
            self.logger.debug(f"Applied reaction: {param_name} = {value}")
    
    def _collect_action_context_results(self, action_name: str, action_result: ActionResult, 
                                       state_changes: Dict) -> None:
        """Collect action context results into state changes."""
        
        # Actions should use create_result_with_state_changes() and set state_changes explicitly
        # This method is kept for future extensibility but no legacy data extraction is performed
        pass
    
    
    
    def _update_action_context(self, action_name: str, action_result: ActionResult, controller) -> None:
        """Update unified action context for inter-action data flow."""
        # Actions should handle their own context updates through ActionContext.set_result()
        # The executor should not be doing parameter mapping or translation
        # This method is kept for future extensibility but no parameter mapping is performed
        self.logger.debug(f"Action {action_name} completed - context updates handled by action itself")
    
    
    def _persist_state_changes(self, controller) -> None:
        """Persist state changes if needed."""
        # This is a placeholder for future state persistence needs
        # Currently, state is persisted by the controller when needed
        pass
    
    def _recalculate_boolean_flags(self, context) -> None:
        """
        Recalculate boolean flags after state changes to maintain consistency.
        
        This ensures boolean flags like has_target_slot, has_selected_item, etc.
        are always consistent with their underlying state values using StateParameters.
        """
        # Calculate equipment status boolean flags
        target_slot = context.get(StateParameters.TARGET_SLOT)
        has_target_slot = target_slot is not None
        context.set(StateParameters.EQUIPMENT_HAS_TARGET_SLOT, has_target_slot)
        
        target_item = context.get(StateParameters.TARGET_ITEM)
        has_target_item = target_item is not None
        # HAS_TARGET_ITEM removed - use knowledge_base.has_target_item() instead
        
        self.logger.debug(f"Recalculated equipment flags: has_target_slot={has_target_slot}, has_target_item={has_target_item}")
        
        # Calculate combat context boolean flags
        win_rate = context.get(StateParameters.COMBAT_RECENT_WIN_RATE, 1.0)
        low_win_rate = win_rate < 0.2
        context.set(StateParameters.COMBAT_LOW_WIN_RATE, low_win_rate)
        
        self.logger.debug(f"Recalculated combat flags: low_win_rate={low_win_rate} (win_rate={win_rate})")
        
        # Add more boolean flag calculations here as needed
    
    
    
    
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
        """Get list of all available GOAP actions."""
        return self.factory.get_available_actions()
    
    def reload_configuration(self) -> None:
        """Reload action configurations from YAML."""
        self.config_data.load()
        self._load_configurations()
        self.validator.reload_configuration()
        self.logger.info("Action configurations and validation rules reloaded")
