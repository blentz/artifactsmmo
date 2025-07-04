"""
Action Factory for dynamic action instantiation.

This module provides a factory pattern for creating action instances based on YAML configuration,
eliminating the need for hardcoded if-elif blocks in the controller.
"""

import importlib
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type, Union

from ..lib.action_context import ActionContext
from .actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from .actions.attack import AttackAction
from .actions.base import ActionBase, ActionResult
from .actions.check_inventory import CheckInventoryAction
from .actions.check_location import CheckLocationAction
from .actions.craft_item import CraftItemAction
from .actions.equip_item import EquipItemAction
from .actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from .actions.execute_crafting_plan import ExecuteCraftingPlanAction
from .actions.find_correct_workshop import FindCorrectWorkshopAction
from .actions.find_monsters import FindMonstersAction
from .actions.find_resources import FindResourcesAction
from .actions.find_workshops import FindWorkshopsAction
from .actions.gather_resources import GatherResourcesAction
from .actions.lookup_item_info import LookupItemInfoAction
from .actions.map_lookup import MapLookupAction

# Action imports
from .actions.move import MoveAction
from .actions.move_to_resource import MoveToResourceAction
from .actions.move_to_workshop import MoveToWorkshopAction
from .actions.plan_crafting_materials import PlanCraftingMaterialsAction
from .actions.rest import RestAction
from .actions.transform_materials_coordinator import TransformMaterialsCoordinatorAction
# Bridge actions for material transformation
from .actions.analyze_materials_for_transformation import AnalyzeMaterialsForTransformationAction
from .actions.determine_workshop_requirements import DetermineWorkshopRequirementsAction
from .actions.navigate_to_workshop import NavigateToWorkshopAction
from .actions.execute_material_transformation import ExecuteMaterialTransformationAction
from .actions.verify_transformation_results import VerifyTransformationResultsAction
from .actions.unequip_item import UnequipItemAction
from .actions.wait import WaitAction
# Equipment upgrade actions
from .actions.initiate_equipment_analysis import InitiateEquipmentAnalysisAction
from .actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from .actions.select_optimal_slot import SelectOptimalSlotAction
from .actions.select_recipe import SelectRecipeAction
from .actions.mark_equipment_crafting import MarkEquipmentCraftingAction
from .actions.complete_equipment_upgrade import CompleteEquipmentUpgradeAction


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
        
        # Register default actions with their parameter mappings
        self.register_action('move', ActionExecutorConfig(
            action_class=MoveAction,
            constructor_params={}
        ))
        
        self.register_action('attack', ActionExecutorConfig(
            action_class=AttackAction,
            constructor_params={}
        ))
        
        self.register_action('rest', ActionExecutorConfig(
            action_class=RestAction,
            constructor_params={}
        ))
        
        self.register_action('map_lookup', ActionExecutorConfig(
            action_class=MapLookupAction,
            constructor_params={}
        ))
        
        self.register_action('find_monsters', ActionExecutorConfig(
            action_class=FindMonstersAction,
            constructor_params={}
        ))
        
        self.register_action('find_resources', ActionExecutorConfig(
            action_class=FindResourcesAction,
            constructor_params={}
        ))
        
        self.register_action('gather_resources', ActionExecutorConfig(
            action_class=GatherResourcesAction,
            constructor_params={}
        ))
        
        self.register_action('transform_raw_materials', ActionExecutorConfig(
            action_class=TransformMaterialsCoordinatorAction,
            constructor_params={}
        ))
        
        self.register_action('wait', ActionExecutorConfig(
            action_class=WaitAction,
            constructor_params={}
        ))
        
        self.register_action('find_workshops', ActionExecutorConfig(
            action_class=FindWorkshopsAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_workshop', ActionExecutorConfig(
            action_class=MoveToWorkshopAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_resource', ActionExecutorConfig(
            action_class=MoveToResourceAction,
            constructor_params={}
        ))
        
        self.register_action('lookup_item_info', ActionExecutorConfig(
            action_class=LookupItemInfoAction,
            constructor_params={}
        ))
        
        self.register_action('craft_item', ActionExecutorConfig(
            action_class=CraftItemAction,
            constructor_params={}
        ))
        
        self.register_action('smelt_materials', ActionExecutorConfig(
            action_class=CraftItemAction,  # Reuse CraftItemAction since smelting is just crafting
            constructor_params={}
        ))
        
        self.register_action('transform_material', ActionExecutorConfig(
            action_class=TransformMaterialsCoordinatorAction,  # Specialized raw material transformation action
            constructor_params={}
        ))
        
        self.register_action('evaluate_weapon_recipes', ActionExecutorConfig(
            action_class=EvaluateWeaponRecipesAction,
            constructor_params={}
        ))
        
        self.register_action('find_correct_workshop', ActionExecutorConfig(
            action_class=FindCorrectWorkshopAction,
            constructor_params={}
        ))
        
        self.register_action('analyze_crafting_chain', ActionExecutorConfig(
            action_class=AnalyzeCraftingChainAction,
            constructor_params={}
        ))
        
        self.register_action('equip_item', ActionExecutorConfig(
            action_class=EquipItemAction,
            constructor_params={}
        ))
        
        self.register_action('unequip_item', ActionExecutorConfig(
            action_class=UnequipItemAction,
            constructor_params={}
        ))
        
        self.register_action('check_inventory', ActionExecutorConfig(
            action_class=CheckInventoryAction,
            constructor_params={}
        ))
        
        self.register_action('check_location', ActionExecutorConfig(
            action_class=CheckLocationAction,
            constructor_params={}
        ))
        
        self.register_action('plan_crafting_materials', ActionExecutorConfig(
            action_class=PlanCraftingMaterialsAction,
            constructor_params={}
        ))
        
        self.register_action('execute_crafting_plan', ActionExecutorConfig(
            action_class=ExecuteCraftingPlanAction,
            constructor_params={}
        ))
        
        # Equipment upgrade actions
        self.register_action('initiate_equipment_analysis', ActionExecutorConfig(
            action_class=InitiateEquipmentAnalysisAction,
            constructor_params={}
        ))
        
        self.register_action('analyze_equipment_gaps', ActionExecutorConfig(
            action_class=AnalyzeEquipmentGapsAction,
            constructor_params={}
        ))
        
        self.register_action('select_optimal_slot', ActionExecutorConfig(
            action_class=SelectOptimalSlotAction,
            constructor_params={}
        ))
        
        self.register_action('select_recipe', ActionExecutorConfig(
            action_class=SelectRecipeAction,
            constructor_params={}
        ))
        
        self.register_action('mark_equipment_crafting', ActionExecutorConfig(
            action_class=MarkEquipmentCraftingAction,
            constructor_params={}
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
                     context: Union[Dict[str, Any], 'ActionContext'] = None) -> Optional[ActionBase]:
        """
        Create an action instance based on configuration and data.
        
        Args:
            action_name: Name of the action to create
            action_data: Data from the action plan
            context: Additional context (character state, etc.) or ActionContext instance
            
        Returns:
            Action instance ready for execution, or None if creation failed
        """
        if action_name not in self._action_registry:
            self.logger.error(f"Unknown action: {action_name}")
            return None
        
        config = self._action_registry[action_name]
        context = context or {}
        
        try:
            # Check if this action has no constructor params (uses ActionContext)
            if not config.constructor_params:
                # Action uses ActionContext pattern, no constructor args needed
                action = config.action_class()
                self.logger.debug(f"Created action {action_name} with ActionContext pattern: {action}")
                return action
            
            # Legacy pattern: Build constructor arguments
            constructor_args = {}
            
            # Convert ActionContext to dict if needed
            if isinstance(context, ActionContext):
                context_dict = dict(context)  # Uses ActionContext's __iter__ and __getitem__
            else:
                context_dict = context
            
            for param_name, data_key in config.constructor_params.items():
                if data_key in action_data:
                    value = action_data[data_key]
                elif data_key in context_dict:
                    value = context_dict[data_key]
                else:
                    # Special handling for craft_item action - fallback to recipe_item_code
                    if action_name == 'craft_item' and param_name == 'item_code' and 'recipe_item_code' in context_dict:
                        value = context_dict['recipe_item_code']
                        self.logger.debug(f"Using recipe_item_code fallback for craft_item: {value}")
                    # Special handling for smelt_materials action - fallback to smelt_item_code
                    elif action_name == 'smelt_materials' and param_name == 'item_code' and 'smelt_item_code' in context_dict:
                        value = context_dict['smelt_item_code']
                        self.logger.debug(f"Using smelt_item_code fallback for smelt_materials: {value}")
                    # General handling for transform_material action - detect required transformation
                    elif action_name == 'transform_material' and param_name == 'item_code':
                        value = self._determine_material_transformation(context_dict)
                        self.logger.debug(f"Determined transformation item_code for transform_material: {value}")
                    elif action_name == 'transform_material' and param_name == 'character_name':
                        value = context_dict.get('character_name', context_dict.get('char_name', 'unknown'))
                        self.logger.debug(f"Using character_name for transform_material: {value}")
                    elif action_name == 'transform_material' and param_name == 'quantity':
                        value = context_dict.get('quantity', 1)
                        self.logger.debug(f"Using quantity for transform_material: {value}")
                    else:
                        # Special handling for move action - enable use_target_coordinates if target coordinates are available
                        if (action_name == 'move' and param_name == 'use_target_coordinates' and 
                            ('target_x' in context_dict or 'target_y' in context_dict or 'x' in context_dict or 'y' in context_dict)):
                            value = True
                            self.logger.debug("Auto-enabling use_target_coordinates for move action due to available coordinates")
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
            # Check if the action class accepts **kwargs
            sig = inspect.signature(config.action_class.__init__)
            accepts_kwargs = any(
                param.kind == inspect.Parameter.VAR_KEYWORD 
                for param in sig.parameters.values()
            )
            
            if accepts_kwargs:
                # For actions that expect additional kwargs (like knowledge_base, action_config), pass context items
                # that aren't already in constructor_args
                additional_kwargs = {}
                for key, value in context_dict.items():
                    if key not in constructor_args and key in ['knowledge_base', 'action_config', 'map_state', 'world_state']:
                        additional_kwargs[key] = value
                
                action = config.action_class(**constructor_args, **additional_kwargs)
            else:
                # Action doesn't accept **kwargs, only pass constructor args
                action = config.action_class(**constructor_args)
            self.logger.debug(f"Created action {action_name}: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to create action {action_name}: {e}")
            return None
    
    def execute_action(self, action_name: str, action_data: Dict[str, Any], 
                      client, context: Union[Dict[str, Any], 'ActionContext'] = None) -> ActionResult:
        """
        Create and execute an action in one step.
        
        Args:
            action_name: Name of the action to execute
            action_data: Data from the action plan
            client: API client for action execution
            context: Additional context (character state, etc.) or ActionContext instance
            
        Returns:
            ActionResult object with execution results
        """
        action = self.create_action(action_name, action_data, context)
        if not action:
            return ActionResult(
                success=False,
                error=f"Failed to create action: {action_name}",
                action_name=action_name
            )
        
        try:
            # Convert dict context to ActionContext if needed
            if isinstance(context, dict):
                # Create ActionContext from dict
                action_context = ActionContext()
                action_context.update(context)
            elif isinstance(context, ActionContext):
                action_context = context
            else:
                action_context = ActionContext()
            
            # Store action instance in context for dynamic reactions
            action_context.action_instance = action
            
            # Execute the action with ActionContext
            result = action.execute(client, action_context)
            
            # All actions MUST return ActionResult - no exceptions
            if not isinstance(result, ActionResult):
                raise TypeError(f"Action {action_name} must return ActionResult, got {type(result)}")
            
            # Apply postprocessors if available
            config = self._action_registry[action_name]
            if config.postprocessors:
                for processor in config.postprocessors.values():
                    result.data = processor(result.data)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            return ActionResult(
                success=False,
                error=f"Action execution failed: {str(e)}",
                action_name=action_name
            )
    
    def get_available_actions(self) -> list[str]:
        """Get list of available action names."""
        return list(self._action_registry.keys())
    
    def is_action_registered(self, action_name: str) -> bool:
        """Check if an action is registered."""
        return action_name in self._action_registry
    
    @property
    def action_class_map(self) -> Dict[str, Type[ActionBase]]:
        """
        Get a mapping of action names to their action classes.
        
        This property extracts action classes from the action registry to provide
        compatibility with code that expects direct access to action classes.
        
        Returns:
            Dictionary mapping action names to their corresponding action classes
        """
        class_map = {}
        for action_name, config in self._action_registry.items():
            class_map[action_name] = config.action_class
        return class_map
    
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