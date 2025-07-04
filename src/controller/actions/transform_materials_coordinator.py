"""
Transform Materials Coordinator Action

This action coordinates the material transformation workflow using
bridge actions for each step of the process.
"""

from typing import Dict, Any

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult
from .analyze_materials_for_transformation import AnalyzeMaterialsForTransformationAction
from .determine_workshop_requirements import DetermineWorkshopRequirementsAction
from .navigate_to_workshop import NavigateToWorkshopAction
from .execute_material_transformation import ExecuteMaterialTransformationAction
from .verify_transformation_results import VerifyTransformationResultsAction


class TransformMaterialsCoordinatorAction(ActionBase):
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
        Coordinate material transformation workflow.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - target_item: Optional target item to craft
                - knowledge_base: Knowledge base instance
                - map_state: Map state instance
                
        Returns:
            Dict with transformation results
        """
        self._context = context
        
        try:
            character_name = context.character_name
            target_item = context.get('target_item')
            
            self.logger.info(f"🎯 Starting material transformation workflow, target: {target_item}")
            
            # Get current inventory
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return self.create_error_result('Could not get character data')
            
            character_data = char_response.data
            inventory = character_data.inventory or []
            
            # Step 1: Analyze materials
            analyze_context = ActionContext()
            analyze_context.update(context)
            analyze_context['inventory'] = inventory
            
            analyze_action = AnalyzeMaterialsForTransformationAction()
            analyze_result = analyze_action.execute(client, analyze_context)
            
            if not analyze_result.get('success'):
                return self.create_error_result('Failed to analyze materials for transformation')
            
            transformations_needed = analyze_context.get('transformations_needed', [])
            
            if not transformations_needed:
                return self.create_error_result('No raw materials found that need transformation')
            
            self.logger.info(f"📊 Found {len(transformations_needed)} materials to transform")
            
            # Step 2: Determine workshop requirements
            workshop_context = ActionContext()
            workshop_context.update(context)
            workshop_context['transformations_needed'] = transformations_needed
            
            workshop_action = DetermineWorkshopRequirementsAction()
            workshop_result = workshop_action.execute(client, workshop_context)
            
            if not workshop_result.get('success'):
                return self.create_error_result('Failed to determine workshop requirements')
            
            workshop_requirements = workshop_context.get('workshop_requirements', [])
            
            # Step 3: Execute transformations
            transformations_completed = []
            current_workshop = None
            
            for requirement in workshop_requirements:
                workshop_type = requirement['workshop_type']
                
                # Navigate to workshop if needed
                if workshop_type and workshop_type != current_workshop:
                    nav_context = ActionContext()
                    nav_context.update(context)
                    nav_context['workshop_type'] = workshop_type
                    
                    nav_action = NavigateToWorkshopAction()
                    nav_result = nav_action.execute(client, nav_context)
                    
                    if not nav_result.get('success'):
                        self.logger.error(f"Failed to navigate to {workshop_type} workshop")
                        continue
                    
                    current_workshop = workshop_type
                
                # Execute transformation
                transform_context = ActionContext()
                transform_context.update(context)
                transform_context['raw_material'] = requirement['raw_material']
                transform_context['refined_material'] = requirement['refined_material']
                transform_context['quantity'] = requirement['quantity']
                
                transform_action = ExecuteMaterialTransformationAction()
                transform_result = transform_action.execute(client, transform_context)
                
                if transform_result.get('success'):
                    transformation = transform_context.get('last_transformation')
                    if transformation:
                        transformations_completed.append(transformation)
                        self.logger.info(
                            f"✅ Transformed {requirement['raw_material']} → {requirement['refined_material']}"
                        )
                else:
                    self.logger.error(
                        f"❌ Failed to transform {requirement['raw_material']} → {requirement['refined_material']}"
                    )
            
            # Step 4: Verify results
            verify_context = ActionContext()
            verify_context.update(context)
            verify_context['transformations_completed'] = transformations_completed
            
            verify_action = VerifyTransformationResultsAction()
            verify_result = verify_action.execute(client, verify_context)
            
            # Return results
            if transformations_completed:
                return self.create_success_result(
                    f"Material transformation workflow completed: {len(transformations_completed)} transformations",
                    materials_transformed=transformations_completed,
                    total_transformations=len(transformations_completed),
                    verification=verify_result.get('verification_results', []),
                    target_item=target_item
                )
            else:
                return self.create_error_result('All material transformations failed')
                
        except Exception as e:
            return self.create_error_result(f"Material transformation workflow failed: {str(e)}")
    
    def __repr__(self):
        return "TransformMaterialsCoordinatorAction()"