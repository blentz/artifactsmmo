"""
Universal Material Action

This action consolidates material-related actions like determine_material_requirements,
check_material_availability, determine_material_insufficiency, calculate_material_quantities,
gather_missing_materials, and check_gathering_complete into configurable workflows.
"""

from typing import Dict, List, Optional, Any
from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult


class UniversalMaterialAction(ActionBase):
    """
    Universal material action that can handle various material-related workflows
    based on configuration parameters.
    """
    
    def __init__(self):
        super().__init__()
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute universal material workflow based on action configuration.
        
        Expected action_config parameters:
        - material_workflow: "determine_requirements" | "check_availability" | 
                           "determine_insufficiency" | "calculate_quantities" |
                           "gather_materials" | "check_gathering_complete"
        """
        if client is None:
            return self.create_error_result("No API client provided")
        
        try:
            # Get action configuration
            action_config = context.get('action_config', {})
            material_workflow = action_config.get('material_workflow', 'determine_requirements')
            
            self._context = context
            
            # Route to appropriate workflow method
            if material_workflow == 'determine_requirements':
                return self._determine_material_requirements(client, context, action_config)
            elif material_workflow == 'check_availability':
                return self._check_material_availability(client, context, action_config)
            elif material_workflow == 'determine_insufficiency':
                return self._determine_material_insufficiency(client, context, action_config)
            elif material_workflow == 'calculate_quantities':
                return self._calculate_material_quantities(client, context, action_config)
            elif material_workflow == 'gather_materials':
                return self._gather_missing_materials(client, context, action_config)
            elif material_workflow == 'check_gathering_complete':
                return self._check_gathering_complete(client, context, action_config)
            else:
                return self.create_error_result(f"Unknown material workflow: {material_workflow}")
                
        except Exception as e:
            return self.create_error_result(f"Universal material workflow failed: {str(e)}")
    
    def _determine_material_requirements(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Determine what materials are needed for the selected recipe."""
        try:
            # Import here to avoid circular imports
            from .determine_material_requirements import DetermineMaterialRequirementsAction
            
            # Create action and delegate
            action = DetermineMaterialRequirementsAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Determine material requirements failed: {str(e)}")
    
    def _check_material_availability(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Check if required materials are available in inventory."""
        try:
            # Import here to avoid circular imports
            from .check_material_availability import CheckMaterialAvailabilityAction
            
            # Create action and delegate
            action = CheckMaterialAvailabilityAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Check material availability failed: {str(e)}")
    
    def _determine_material_insufficiency(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Determine that required materials are insufficient and need gathering."""
        try:
            # Import here to avoid circular imports
            from .determine_material_insufficiency import DetermineMaterialInsufficencyAction
            
            # Create action and delegate
            action = DetermineMaterialInsufficencyAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Determine material insufficiency failed: {str(e)}")
    
    def _calculate_material_quantities(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Calculate total quantities of raw materials needed."""
        try:
            # Import here to avoid circular imports
            from .calculate_material_quantities import CalculateMaterialQuantitiesAction
            
            # Create action and delegate
            action = CalculateMaterialQuantitiesAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Calculate material quantities failed: {str(e)}")
    
    def _gather_missing_materials(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Gather materials that are missing from inventory."""
        try:
            # Import here to avoid circular imports
            from .gather_missing_materials import GatherMissingMaterialsAction
            
            # Create action and delegate
            action = GatherMissingMaterialsAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Gather missing materials failed: {str(e)}")
    
    def _check_gathering_complete(self, client, context: ActionContext, action_config: Dict) -> ActionResult:
        """Check if material gathering is complete."""
        try:
            # Import here to avoid circular imports
            from .check_gathering_complete import CheckGatheringCompleteAction
            
            # Create action and delegate
            action = CheckGatheringCompleteAction()
            action._context = context
            return action.execute(client, context)
            
        except Exception as e:
            return self.create_error_result(f"Check gathering complete failed: {str(e)}")
    
    def __repr__(self):
        return "UniversalMaterialAction()"