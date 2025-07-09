"""
Transform Materials Coordinator Action

This action coordinates the material transformation workflow using
bridge actions for each step of the process.
"""

from typing import Dict, Any

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from .base import ActionBase, ActionResult
from .subgoal_mixins import WorkflowSubgoalMixin


class TransformMaterialsCoordinatorAction(ActionBase, WorkflowSubgoalMixin):
    """
    Coordinator action for material transformation workflow.
    
    This action orchestrates the complete material transformation process:
    1. Analyze materials to determine what to transform
    2. Determine workshop requirements
    3. Navigate to workshops and execute transformations
    4. Verify results
    """
    
    # GOAP parameters
    conditions = {
        'character_status': {
            'alive': True,
            'safe': True,
        },
        'inventory_status': {
            'has_raw_materials': True
        }
    }
    reactions = {
        'inventory_status': {
            'has_refined_materials': True,
            'materials_sufficient': True
        }
    }
    weight = 15
    
    def __init__(self):
        """Initialize transform materials coordinator action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Coordinate material transformation workflow using proper subgoal patterns.
        
        Workflow steps:
        1. analyze_materials: Analyze materials to determine transformations needed
        2. determine_workshops: Determine workshop requirements
        3. execute_transformations: Execute each transformation via subgoals
        4. verify_results: Verify transformation results
        
        Args:
            client: API client
            context: Action context containing character and target item data
                
        Returns:
            ActionResult with transformation results
        """
        self._context = context
        
        try:
            character_name = context.get(StateParameters.CHARACTER_NAME)
            target_item = context.get(StateParameters.TARGET_ITEM)
            workflow_step = self.get_workflow_step(context, 'analyze_materials')
            
            self.logger.info(f"🎯 Material transformation workflow step: {workflow_step}")
            
            if workflow_step == 'analyze_materials':
                return self._handle_analyze_materials_step(client, context, target_item)
            elif workflow_step == 'determine_workshops':
                return self._handle_determine_workshops_step(client, context, target_item)
            elif workflow_step == 'execute_transformations':
                return self._handle_execute_transformations_step(client, context, target_item)
            elif workflow_step == 'verify_results':
                return self._handle_verify_results_step(client, context, target_item)
            else:
                return self.create_error_result(f"Unknown workflow step: {workflow_step}")
                
        except Exception as e:
            return self.create_error_result(f"Material transformation workflow failed: {str(e)}")
    
    def _handle_analyze_materials_step(self, client, context: ActionContext, target_item: str) -> ActionResult:
        """Handle materials analysis step."""
        # Get current inventory
        char_response = get_character_api(name=context.get(StateParameters.CHARACTER_NAME), client=client)
        if not char_response or not char_response.data:
            return self.create_error_result('Could not get character data')
        
        character_data = char_response.data
        inventory = character_data.inventory or []
        
        # Request materials analysis subgoal (inventory will be re-fetched by subgoal)
        return self.request_workflow_subgoal(
            context,
            goal_name="analyze_materials",
            parameters={
                "target_item": target_item
            },
            next_step="determine_workshops",
            preserve_keys=[StateParameters.TARGET_ITEM]
        )
    
    def _handle_determine_workshops_step(self, client, context: ActionContext, target_item: str) -> ActionResult:
        """Handle workshop requirements determination step."""
        transformations_needed = context.get(StateParameters.TRANSFORMATIONS_NEEDED, [])
        
        if not transformations_needed:
            return self.create_error_result('No raw materials found that need transformation')
        
        self.logger.info(f"📊 Found {len(transformations_needed)} materials to transform")
        
        # Request workshop requirements analysis subgoal
        return self.request_workflow_subgoal(
            context,
            goal_name="determine_workshop_requirements",
            parameters={
                "transformations_needed": transformations_needed
            },
            next_step="execute_transformations",
            preserve_keys=[StateParameters.TARGET_ITEM, StateParameters.TRANSFORMATIONS_NEEDED]
        )
    
    def _handle_execute_transformations_step(self, client, context: ActionContext, target_item: str) -> ActionResult:
        """Handle transformation execution step."""
        workshop_requirements = context.get(StateParameters.WORKSHOP_REQUIREMENTS, [])
        
        if not workshop_requirements:
            return self.create_error_result('No workshop requirements found')
        
        # Get current transformation index
        transformation_index = context.get(StateParameters.CURRENT_TRANSFORMATION_INDEX, 0)
        
        if transformation_index >= len(workshop_requirements):
            # All transformations completed, move to verification
            self.set_workflow_step(context, 'verify_results')
            return self._handle_verify_results_step(client, context, target_item)
        
        # Get current transformation requirement
        current_requirement = workshop_requirements[transformation_index]
        
        # Request transformation subgoal
        return self.request_workflow_subgoal(
            context,
            goal_name="execute_material_transformation",
            parameters={
                "workshop_type": current_requirement['workshop_type'],
                "raw_material": current_requirement['raw_material'],
                "refined_material": current_requirement['refined_material'],
                "quantity": current_requirement['quantity']
            },
            next_step="execute_transformations",  # Continue with next transformation
            preserve_keys=[StateParameters.TARGET_ITEM, StateParameters.WORKSHOP_REQUIREMENTS, StateParameters.TRANSFORMATIONS_COMPLETED]
        )
    
    def _handle_verify_results_step(self, client, context: ActionContext, target_item: str) -> ActionResult:
        """Handle results verification step."""
        transformations_completed = context.get(StateParameters.TRANSFORMATIONS_COMPLETED, [])
        
        if not transformations_completed:
            return self.create_error_result('No transformations were completed')
        
        # Request verification subgoal
        return self.request_workflow_subgoal(
            context,
            goal_name="verify_transformation_results",
            parameters={
                "transformations_completed": transformations_completed
            },
            next_step="completed",
            preserve_keys=[StateParameters.TARGET_ITEM, StateParameters.TRANSFORMATIONS_COMPLETED]
        )
    
    def _complete_workflow(self, context: ActionContext, target_item: str) -> ActionResult:
        """Complete the workflow and return final results."""
        transformations_completed = context.get(StateParameters.TRANSFORMATIONS_COMPLETED, [])
        verification_results = context.get(StateParameters.VERIFICATION_RESULTS, [])
        
        if transformations_completed:
            return self.create_success_result(
                f"Material transformation workflow completed: {len(transformations_completed)} transformations",
                materials_transformed=transformations_completed,
                total_transformations=len(transformations_completed),
                verification=verification_results,
                target_item=target_item
            )
        else:
            return self.create_error_result('All material transformations failed')
    
    def __repr__(self):
        return "TransformMaterialsCoordinatorAction()"