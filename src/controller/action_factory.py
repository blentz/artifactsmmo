"""
Action Factory for dynamic action instantiation.

This module provides a factory pattern for creating action instances based on YAML configuration,
eliminating the need for hardcoded if-elif blocks in the controller.
"""

import importlib
import inspect
import logging
from typing import Any, Dict, Optional, Type, Callable
from dataclasses import dataclass

from .actions.base import ActionBase


@dataclass
class ActionExecutorConfig:
    """Configuration for action execution including parameters and preprocessing."""
    action_class: Type[ActionBase]
    constructor_params: Dict[str, str]  # Maps constructor param names to action_data keys
    preprocessors: Dict[str, Callable] = None  # Optional data preprocessing functions
    postprocessors: Dict[str, Callable] = None  # Optional response post-processing


class ActionFactory:
    """
    Factory class for creating and executing actions dynamically based on configuration.
    
    Supports YAML-driven action execution without hardcoded if-elif blocks.
    """
    
    def __init__(self, config_data=None):
        self.logger = logging.getLogger(__name__)
        self._action_registry: Dict[str, ActionExecutorConfig] = {}
        self._config_data = config_data
        self._setup_default_actions()
        
        # Load additional action classes from YAML if available
        if self._config_data:
            self._load_action_classes_from_yaml()
    
    def _setup_default_actions(self) -> None:
        """Set up the default action mappings with their parameter configurations."""
        from .actions.move import MoveAction
        from .actions.attack import AttackAction
        from .actions.rest import RestAction
        from .actions.map_lookup import MapLookupAction
        from .actions.find_monsters import FindMonstersAction
        from .actions.find_resources import FindResourcesAction
        from .actions.find_workshops import FindWorkshopsAction
        from .actions.move_to_workshop import MoveToWorkshopAction
        from .actions.move_to_resource import MoveToResourceAction
        from .actions.gather_resources import GatherResourcesAction
        from .actions.wait import WaitAction
        from .actions.lookup_item_info import LookupItemInfoAction
        from .actions.craft_item import CraftItemAction
        from .actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
        from .actions.find_correct_workshop import FindCorrectWorkshopAction
        from .actions.analyze_crafting_chain import AnalyzeCraftingChainAction
        from .actions.equip_item import EquipItemAction
        from .actions.transform_raw_materials import TransformRawMaterialsAction
        from .actions.check_inventory import CheckInventoryAction
        from .actions.check_location import CheckLocationAction
        
        # Register default actions with their parameter mappings
        self.register_action('move', ActionExecutorConfig(
            action_class=MoveAction,
            constructor_params={
                'char_name': 'character_name',  # Will be provided by controller
                'x': 'x',
                'y': 'y',
                'use_target_coordinates': 'use_target_coordinates'
            }
        ))
        
        self.register_action('attack', ActionExecutorConfig(
            action_class=AttackAction,
            constructor_params={
                'char_name': 'character_name'  # Will be provided by controller
            }
        ))
        
        self.register_action('rest', ActionExecutorConfig(
            action_class=RestAction,
            constructor_params={
                'char_name': 'character_name'  # Will be provided by controller
            }
        ))
        
        self.register_action('map_lookup', ActionExecutorConfig(
            action_class=MapLookupAction,
            constructor_params={
                'x': 'x',
                'y': 'y'
            }
        ))
        
        self.register_action('find_monsters', ActionExecutorConfig(
            action_class=FindMonstersAction,
            constructor_params={
                'character_x': 'character_x',
                'character_y': 'character_y',
                'search_radius': 'search_radius',
                'monster_types': 'monster_types',
                'character_level': 'character_level',
                'level_range': 'level_range'
            }
        ))
        
        self.register_action('find_resources', ActionExecutorConfig(
            action_class=FindResourcesAction,
            constructor_params={
                'character_x': 'character_x',
                'character_y': 'character_y',
                'search_radius': 'search_radius',
                'resource_types': 'resource_types',
                'character_level': 'character_level',
                'skill_type': 'skill_type'
            }
        ))
        
        self.register_action('gather_resources', ActionExecutorConfig(
            action_class=GatherResourcesAction,
            constructor_params={
                'character_name': 'character_name',
                'target_resource': 'target_resource'
            }
        ))
        
        self.register_action('transform_raw_materials', ActionExecutorConfig(
            action_class=TransformRawMaterialsAction,
            constructor_params={
                'character_name': 'character_name',
                'target_item': 'target_item'
            }
        ))
        
        self.register_action('wait', ActionExecutorConfig(
            action_class=WaitAction,
            constructor_params={
                'wait_duration': 'wait_duration'
            }
        ))
        
        self.register_action('find_workshops', ActionExecutorConfig(
            action_class=FindWorkshopsAction,
            constructor_params={
                'character_x': 'character_x',
                'character_y': 'character_y',
                'search_radius': 'search_radius',
                'workshop_type': 'workshop_type'
            }
        ))
        
        self.register_action('move_to_workshop', ActionExecutorConfig(
            action_class=MoveToWorkshopAction,
            constructor_params={
                'char_name': 'character_name',
                'target_x': 'target_x',
                'target_y': 'target_y'
            }
        ))
        
        self.register_action('move_to_resource', ActionExecutorConfig(
            action_class=MoveToResourceAction,
            constructor_params={
                'char_name': 'character_name',
                'target_x': 'target_x',
                'target_y': 'target_y'
            }
        ))
        
        self.register_action('lookup_item_info', ActionExecutorConfig(
            action_class=LookupItemInfoAction,
            constructor_params={
                'item_code': 'item_code',
                'search_term': 'search_term',
                'item_type': 'item_type',
                'max_level': 'max_level'
            }
        ))
        
        self.register_action('craft_item', ActionExecutorConfig(
            action_class=CraftItemAction,
            constructor_params={
                'character_name': 'character_name',
                'item_code': 'item_code',  # Try item_code first
                'quantity': 'quantity'
            }
        ))
        
        self.register_action('smelt_materials', ActionExecutorConfig(
            action_class=CraftItemAction,  # Reuse CraftItemAction since smelting is just crafting
            constructor_params={
                'character_name': 'character_name',
                'item_code': 'item_code',  # Will be "copper" for smelting
                'quantity': 'quantity'
            }
        ))
        
        self.register_action('transform_material', ActionExecutorConfig(
            action_class=TransformRawMaterialsAction,  # Specialized raw material transformation action
            constructor_params={
                'character_name': 'character_name',
                'target_item': 'item_code'  # Target item to determine required materials
            }
        ))
        
        self.register_action('evaluate_weapon_recipes', ActionExecutorConfig(
            action_class=EvaluateWeaponRecipesAction,
            constructor_params={
                'character_name': 'character_name',
                'current_weapon': 'current_weapon',
                'character_level': 'character_level'
            }
        ))
        
        self.register_action('find_correct_workshop', ActionExecutorConfig(
            action_class=FindCorrectWorkshopAction,
            constructor_params={
                'character_x': 'character_x',
                'character_y': 'character_y',
                'search_radius': 'search_radius',
                'item_code': 'item_code',
                'character_name': 'character_name'
            }
        ))
        
        self.register_action('analyze_crafting_chain', ActionExecutorConfig(
            action_class=AnalyzeCraftingChainAction,
            constructor_params={
                'character_name': 'character_name',
                'target_item': 'target_item'
            }
        ))
        
        self.register_action('equip_item', ActionExecutorConfig(
            action_class=EquipItemAction,
            constructor_params={
                'character_name': 'character_name',
                'item_code': 'item_code',
                'slot': 'slot'
            }
        ))
        
        self.register_action('check_inventory', ActionExecutorConfig(
            action_class=CheckInventoryAction,
            constructor_params={
                'character_name': 'character_name',
                'required_items': 'required_items'
            }
        ))
        
        self.register_action('check_location', ActionExecutorConfig(
            action_class=CheckLocationAction,
            constructor_params={
                'character_name': 'character_name'
            }
        ))
    
    def _load_action_classes_from_yaml(self) -> None:
        """Load action class mappings from YAML configuration."""
        try:
            if not self._config_data or not hasattr(self._config_data, 'data'):
                return
                
            action_classes = self._config_data.data.get('action_classes', {})
            
            for action_name, class_path in action_classes.items():
                # Only register if not already registered (avoid overriding defaults)
                if action_name not in self._action_registry:
                    try:
                        action_class = self._import_action_class(class_path)
                        # Use a basic configuration for YAML-loaded classes
                        config = ActionExecutorConfig(
                            action_class=action_class,
                            constructor_params={}  # Will be determined dynamically
                        )
                        self.register_action(action_name, config)
                        self.logger.debug(f"Loaded action class from YAML: {action_name} -> {class_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load action class {action_name} from {class_path}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error loading action classes from YAML: {e}")
    
    def register_action(self, action_name: str, config: ActionExecutorConfig) -> None:
        """
        Register an action with its execution configuration.
        
        Args:
            action_name: Name of the action
            config: Configuration for action execution
        """
        self._action_registry[action_name] = config
        self.logger.debug(f"Registered action: {action_name}")
    
    def register_action_from_yaml(self, action_name: str, yaml_config: Dict[str, Any]) -> None:
        """
        Register an action from YAML configuration.
        
        Args:
            action_name: Name of the action
            yaml_config: YAML configuration dictionary
        """
        if 'class_path' not in yaml_config:
            raise ValueError(f"Action {action_name} missing 'class_path' in YAML config")
        
        # Dynamically import the action class
        action_class = self._import_action_class(yaml_config['class_path'])
        
        # Build constructor parameter mapping
        constructor_params = yaml_config.get('constructor_params', {})
        
        # Set up preprocessors and postprocessors if defined
        preprocessors = self._build_function_map(yaml_config.get('preprocessors', {}))
        postprocessors = self._build_function_map(yaml_config.get('postprocessors', {}))
        
        config = ActionExecutorConfig(
            action_class=action_class,
            constructor_params=constructor_params,
            preprocessors=preprocessors,
            postprocessors=postprocessors
        )
        
        self.register_action(action_name, config)
    
    def _import_action_class(self, class_path: str) -> Type[ActionBase]:
        """
        Dynamically import an action class from a module path.
        
        Args:
            class_path: Module path like 'src.controller.actions.move.MoveAction'
            
        Returns:
            The imported action class
        """
        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        action_class = getattr(module, class_name)
        
        if not issubclass(action_class, ActionBase):
            raise ValueError(f"Class {class_path} is not a subclass of ActionBase")
        
        return action_class
    
    def _build_function_map(self, function_configs: Dict[str, str]) -> Dict[str, Callable]:
        """
        Build a map of functions from configuration strings.
        
        Args:
            function_configs: Dict mapping param names to function paths
            
        Returns:
            Dict mapping param names to callable functions
        """
        function_map = {}
        for param_name, func_path in function_configs.items():
            module_path, func_name = func_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            function_map[param_name] = getattr(module, func_name)
        return function_map
    
    def create_action(self, action_name: str, action_data: Dict[str, Any], 
                     context: Dict[str, Any] = None) -> Optional[ActionBase]:
        """
        Create an action instance based on configuration and data.
        
        Args:
            action_name: Name of the action to create
            action_data: Data from the action plan
            context: Additional context (character state, etc.)
            
        Returns:
            Action instance ready for execution, or None if creation failed
        """
        if action_name not in self._action_registry:
            self.logger.error(f"Unknown action: {action_name}")
            return None
        
        config = self._action_registry[action_name]
        context = context or {}
        
        
        try:
            # Build constructor arguments
            constructor_args = {}
            for param_name, data_key in config.constructor_params.items():
                if data_key in action_data:
                    value = action_data[data_key]
                elif data_key in context:
                    value = context[data_key]
                else:
                    # Special handling for craft_item action - fallback to recipe_item_code
                    if action_name == 'craft_item' and param_name == 'item_code' and 'recipe_item_code' in context:
                        value = context['recipe_item_code']
                        self.logger.debug(f"Using recipe_item_code fallback for craft_item: {value}")
                    # Special handling for smelt_materials action - fallback to smelt_item_code
                    elif action_name == 'smelt_materials' and param_name == 'item_code' and 'smelt_item_code' in context:
                        value = context['smelt_item_code']
                        self.logger.debug(f"Using smelt_item_code fallback for smelt_materials: {value}")
                    # General handling for transform_material action - detect required transformation
                    elif action_name == 'transform_material' and param_name == 'item_code':
                        value = self._determine_material_transformation(context)
                        self.logger.debug(f"Determined transformation item_code for transform_material: {value}")
                    elif action_name == 'transform_material' and param_name == 'character_name':
                        value = context.get('character_name', context.get('char_name', 'unknown'))
                        self.logger.debug(f"Using character_name for transform_material: {value}")
                    elif action_name == 'transform_material' and param_name == 'quantity':
                        value = context.get('quantity', 1)
                        self.logger.debug(f"Using quantity for transform_material: {value}")
                    else:
                        # Special handling for move action - enable use_target_coordinates if target coordinates are available
                        if (action_name == 'move' and param_name == 'use_target_coordinates' and 
                            ('target_x' in context or 'target_y' in context or 'x' in context or 'y' in context)):
                            value = True
                            self.logger.debug(f"Auto-enabling use_target_coordinates for move action due to available coordinates")
                        else:
                            # Check if parameter has a default value
                            sig = inspect.signature(config.action_class.__init__)
                            param = sig.parameters.get(param_name)
                            if param and param.default != inspect.Parameter.empty:
                                continue  # Skip - will use default
                            else:
                                self.logger.warning(f"Missing required parameter {param_name} for action {action_name}")
                                return None
                
                # Apply preprocessor if available
                if config.preprocessors and param_name in config.preprocessors:
                    value = config.preprocessors[param_name](value)
                
                constructor_args[param_name] = value
            
            # Create the action instance
            action = config.action_class(**constructor_args)
            self.logger.debug(f"Created action {action_name}: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to create action {action_name}: {e}")
            return None
    
    def execute_action(self, action_name: str, action_data: Dict[str, Any], 
                      client, context: Dict[str, Any] = None) -> tuple[bool, Any]:
        """
        Create and execute an action in one step.
        
        Args:
            action_name: Name of the action to execute
            action_data: Data from the action plan
            client: API client for action execution
            context: Additional context (character state, etc.)
            
        Returns:
            Tuple of (success: bool, response: Any)
        """
        action = self.create_action(action_name, action_data, context)
        if not action:
            return False, None
        
        try:
            # Execute the action with context passed as kwargs
            kwargs = context.copy() if context else {}
            response = action.execute(client, **kwargs)
            
            # Apply postprocessors if available
            config = self._action_registry[action_name]
            if config.postprocessors:
                for processor in config.postprocessors.values():
                    response = processor(response)
            
            # Check if response indicates success or failure
            if response is None:
                success = False
            elif isinstance(response, dict) and 'success' in response:
                success = response['success']
            else:
                # For API responses that don't have a 'success' field, consider them successful
                success = True
            
            return success, response
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            return False, None
    
    def get_available_actions(self) -> list[str]:
        """Get list of available action names."""
        return list(self._action_registry.keys())
    
    def is_action_registered(self, action_name: str) -> bool:
        """Check if an action is registered."""
        return action_name in self._action_registry
    
    def _determine_material_transformation(self, context: Dict[str, Any]) -> str:
        """
        Determine what material needs to be transformed based on available raw materials.
        
        This implements general-case material transformation logic that works for any materials.
        """
        try:
            # Material transformation mappings: raw -> refined
            transformations = {
                'copper_ore': 'copper',
                'iron_ore': 'iron', 
                'coal': 'coal',  # Already refined
                'ash_wood': 'logs',
                'birch_wood': 'logs',
                'dead_wood': 'logs'
            }
            
            # Check character inventory for available raw materials
            character_inventory = context.get('character_inventory', [])
            if not character_inventory:
                character_inventory = context.get('inventory', [])
            
            # Find the first raw material we have that can be transformed
            for item in character_inventory:
                if isinstance(item, dict):
                    item_code = item.get('code', '')
                    quantity = item.get('quantity', 0)
                    
                    if item_code in transformations and quantity > 0:
                        refined_item = transformations[item_code]
                        self.logger.debug(f"Found transformable material: {item_code} -> {refined_item} (quantity: {quantity})")
                        return refined_item
            
            # Fallback: try common materials in order of preference
            preferred_order = ['copper_ore', 'iron_ore', 'ash_wood']
            for raw_material in preferred_order:
                if raw_material in transformations:
                    return transformations[raw_material]
            
            # Final fallback
            return 'copper'
            
        except Exception as e:
            self.logger.warning(f"Error determining material transformation: {e}")
            return 'copper'  # Safe fallback