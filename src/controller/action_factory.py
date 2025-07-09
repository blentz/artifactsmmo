"""
Action Factory for dynamic action instantiation.

This module provides a factory pattern for creating action instances based on YAML configuration,
eliminating the need for hardcoded if-elif blocks in the controller.
"""

import importlib
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type

from ..lib.action_context import ActionContext
from ..lib.actions_data import ActionsData
from ..lib.state_parameters import StateParameters
from .actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from .actions.attack import AttackAction
from .actions.base import ActionBase, ActionResult
from .actions.check_inventory import CheckInventoryAction
from .actions.check_location import CheckLocationAction
from .actions.craft_item import CraftItemAction
from .actions.determine_material_insufficiency import DetermineMaterialInsufficencyAction
from .actions.calculate_material_quantities import CalculateMaterialQuantitiesAction
from .actions.gather_resource_quantity import GatherResourceQuantityAction
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
from .actions.analyze_equipment import AnalyzeEquipmentAction
from .actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from .actions.analyze_nearby_resources import AnalyzeNearbyResourcesAction
from .actions.select_optimal_slot import SelectOptimalSlotAction
from .actions.select_recipe import SelectRecipeAction
from .actions.mark_equipment_crafting import MarkEquipmentCraftingAction
from .actions.complete_equipment_upgrade import CompleteEquipmentUpgradeAction
from .actions.verify_skill_requirements import VerifySkillRequirementsAction
from .actions.check_material_availability import CheckMaterialAvailabilityAction
from .actions.determine_material_requirements import DetermineMaterialRequirementsAction
from .actions.gather_missing_materials import GatherMissingMaterialsAction
from .actions.check_gathering_complete import CheckGatheringCompleteAction
from .actions.initiate_combat_search import InitiateCombatSearchAction
from .actions.universal_search import UniversalSearchAction
from .actions.universal_movement import UniversalMovementAction
from .actions.universal_material import UniversalMaterialAction


@dataclass
class ActionExecutorConfig:
    """Configuration for action execution."""
    action_class: Type[ActionBase]
    constructor_params: Dict[str, str] = None
    preprocessors: Dict[str, Callable] = None
    postprocessors: Dict[str, Callable] = None


class ActionFactory:
    """
    Factory for creating action instances dynamically.
    
    This class enables metaprogramming by allowing actions to be created and executed
    based on configuration rather than hardcoded logic.
    """
    
    def __init__(self, config_data: Any = None):
        self.logger = logging.getLogger(__name__)
        self.config_data = config_data
        self._action_registry: Dict[str, ActionExecutorConfig] = {}
        
        # Register all available actions
        self._register_builtin_actions()
        
        # Load any additional actions from configuration
        if config_data:
            self._load_configured_actions()
    
    def _register_builtin_actions(self) -> None:
        """Register built-in action types."""
        # Movement actions
        self.register_action('move', ActionExecutorConfig(
            action_class=MoveAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_resource', ActionExecutorConfig(
            action_class=MoveToResourceAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_workshop', ActionExecutorConfig(
            action_class=MoveToWorkshopAction,
            constructor_params={}
        ))
        
        # Combat actions
        self.register_action('attack', ActionExecutorConfig(
            action_class=AttackAction,
            constructor_params={}
        ))
        
        self.register_action('initiate_combat_search', ActionExecutorConfig(
            action_class=InitiateCombatSearchAction,
            constructor_params={}
        ))
        
        # Resource actions
        self.register_action('gather_resources', ActionExecutorConfig(
            action_class=GatherResourcesAction,
            constructor_params={}
        ))
        
        self.register_action('find_resources', ActionExecutorConfig(
            action_class=FindResourcesAction,
            constructor_params={}
        ))
        
        # Maintenance actions
        self.register_action('rest', ActionExecutorConfig(
            action_class=RestAction,
            constructor_params={}
        ))
        
        self.register_action('wait', ActionExecutorConfig(
            action_class=WaitAction,
            constructor_params={}
        ))
        
        # Discovery actions
        self.register_action('find_monsters', ActionExecutorConfig(
            action_class=FindMonstersAction,
            constructor_params={}
        ))
        
        # Universal search actions - consolidates find_monsters, find_resources, find_workshops
        self.register_action('universal_search', ActionExecutorConfig(
            action_class=UniversalSearchAction,
            constructor_params={}
        ))
        
        self.register_action('search_monsters', ActionExecutorConfig(
            action_class=UniversalSearchAction,
            constructor_params={}
        ))
        
        self.register_action('search_resources', ActionExecutorConfig(
            action_class=UniversalSearchAction,
            constructor_params={}
        ))
        
        self.register_action('search_workshops', ActionExecutorConfig(
            action_class=UniversalSearchAction,
            constructor_params={}
        ))
        
        # Universal movement actions - consolidates move, move_to_resource, move_to_workshop
        self.register_action('universal_movement', ActionExecutorConfig(
            action_class=UniversalMovementAction,
            constructor_params={}
        ))
        
        self.register_action('move_coordinates', ActionExecutorConfig(
            action_class=UniversalMovementAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_target_resource', ActionExecutorConfig(
            action_class=UniversalMovementAction,
            constructor_params={}
        ))
        
        self.register_action('move_to_target_workshop', ActionExecutorConfig(
            action_class=UniversalMovementAction,
            constructor_params={}
        ))
        
        # Universal material actions - consolidates material workflow actions
        self.register_action('universal_material', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('determine_requirements', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('check_availability', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('determine_insufficiency', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('calculate_quantities', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('gather_materials', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('check_gathering', ActionExecutorConfig(
            action_class=UniversalMaterialAction,
            constructor_params={}
        ))
        
        self.register_action('find_workshops', ActionExecutorConfig(
            action_class=FindWorkshopsAction,
            constructor_params={}
        ))
        
        # Crafting actions
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
        
        self.register_action('analyze_nearby_resources', ActionExecutorConfig(
            action_class=AnalyzeNearbyResourcesAction,
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
        
        self.register_action('determine_material_insufficiency', ActionExecutorConfig(
            action_class=DetermineMaterialInsufficencyAction,
            constructor_params={}
        ))
        
        self.register_action('calculate_material_quantities', ActionExecutorConfig(
            action_class=CalculateMaterialQuantitiesAction,
            constructor_params={}
        ))
        
        self.register_action('gather_resource_quantity', ActionExecutorConfig(
            action_class=GatherResourceQuantityAction,
            constructor_params={}
        ))
        
        self.register_action('complete_equipment_upgrade', ActionExecutorConfig(
            action_class=CompleteEquipmentUpgradeAction,
            constructor_params={}
        ))
        
        self.register_action('analyze_equipment', ActionExecutorConfig(
            action_class=AnalyzeEquipmentAction,
            constructor_params={}
        ))
        
        self.register_action('verify_skill_requirements', ActionExecutorConfig(
            action_class=VerifySkillRequirementsAction,
            constructor_params={}
        ))
        
        self.register_action('check_material_availability', ActionExecutorConfig(
            action_class=CheckMaterialAvailabilityAction,
            constructor_params={}
        ))
        
        self.register_action('determine_material_requirements', ActionExecutorConfig(
            action_class=DetermineMaterialRequirementsAction,
            constructor_params={}
        ))
        
        # Map/location actions
        self.register_action('map_lookup', ActionExecutorConfig(
            action_class=MapLookupAction,
            constructor_params={}
        ))
        
        # Material gathering actions
        self.register_action('gather_missing_materials', ActionExecutorConfig(
            action_class=GatherMissingMaterialsAction,
            constructor_params={}
        ))
        
        self.register_action('check_gathering_complete', ActionExecutorConfig(
            action_class=CheckGatheringCompleteAction,
            constructor_params={}
        ))
        
        # Bridge actions for material transformation
        self.register_action('analyze_materials_for_transformation', ActionExecutorConfig(
            action_class=AnalyzeMaterialsForTransformationAction,
            constructor_params={}
        ))
        
        self.register_action('determine_workshop_requirements', ActionExecutorConfig(
            action_class=DetermineWorkshopRequirementsAction,
            constructor_params={}
        ))
        
        self.register_action('navigate_to_workshop', ActionExecutorConfig(
            action_class=NavigateToWorkshopAction,
            constructor_params={}
        ))
        
        self.register_action('execute_material_transformation', ActionExecutorConfig(
            action_class=ExecuteMaterialTransformationAction,
            constructor_params={}
        ))
        
        self.register_action('verify_transformation_results', ActionExecutorConfig(
            action_class=VerifyTransformationResultsAction,
            constructor_params={}
        ))
    
    def _load_configured_actions(self) -> None:
        """Load actions defined in YAML configuration."""
        # This would load any YAML-defined actions
        # For now, we only have builtin actions
        pass
    
    def register_action(self, action_name: str, config: ActionExecutorConfig) -> None:
        """Register an action configuration."""
        self._action_registry[action_name] = config
        self.logger.debug(f"Registered action: {action_name}")
    
    # Removed register_action_from_yaml - dead placeholder code
    
    def _build_preprocessors(self, function_configs: Dict[str, str]) -> Dict[str, Callable]:
        """
        Build preprocessor functions from configuration.
        
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
    
    def create_action(self, action_name: str, context: 'ActionContext') -> Optional[ActionBase]:
        """
        Create an action instance based on configuration.
        
        Args:
            action_name: Name of the action to create
            context: ActionContext instance with unified state
            
        Returns:
            Action instance ready for execution, or None if creation failed
        """
        if action_name not in self._action_registry:
            self.logger.error(f"Unknown action: {action_name}")
            return None
        
        config = self._action_registry[action_name]
        
        try:
            # All actions now use ActionContext pattern
            action = config.action_class()
            self.logger.debug(f"Created action {action_name} with ActionContext pattern: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to create action {action_name}: {e}")
            return None
    
    def execute_action(self, action_name: str, client, context: 'ActionContext') -> ActionResult:
        """
        Create and execute an action in one step.
        
        Args:
            action_name: Name of the action to execute
            client: API client for action execution
            context: ActionContext instance with unified state
            
        Returns:
            ActionResult object with execution results
        """
        action = self.create_action(action_name, context)
        if not action:
            return ActionResult(
                success=False,
                error=f"Failed to create action: {action_name}",
                action_name=action_name
            )
        
        try:
            # Auto-load action parameters from default_actions.yaml
            self._load_action_parameters(action_name, context)
            
            # Store action instance in context for dynamic reactions
            context.action_instance = action
            
            # Execute the action with ActionContext
            result = action.execute(client, context)
            
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
    
    def _load_action_parameters(self, action_name: str, context: 'ActionContext') -> None:
        """
        Auto-load action parameters from default_actions.yaml into the action context.
        
        Args:
            action_name: Name of the action being executed
            context: ActionContext to load parameters into
        """
        # Load action configuration from default_actions.yaml
        actions_data = ActionsData()  # Loads config/default_actions.yaml
        action_config = actions_data.get_actions().get(action_name, {})
        action_parameters = action_config.get('parameters', {})
        
        # Set individual action parameters using flat storage
        for param_name, param_value in action_parameters.items():
            context.set(param_name, param_value)
        
        self.logger.debug(f"Auto-loaded {len(action_parameters)} parameters for {action_name}: {action_parameters}")

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