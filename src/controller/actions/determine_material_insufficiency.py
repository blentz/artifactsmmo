"""
Determine Material Insufficiency Action

This action determines that required materials are insufficient and need gathering.
It's specifically used when the GOAP planner needs to explicitly set the path to 'insufficient'.
"""

from typing import Dict, List

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import MaterialStatus


class DetermineMaterialInsufficiencyAction(ActionBase):
    """
    Action to determine that materials are insufficient.
    
    This action performs the same check as CheckMaterialAvailabilityAction
    but specifically sets the status to 'insufficient' when that's the desired path.
    This allows GOAP to have separate action paths for sufficient vs insufficient materials.
    """
    
    # GOAP parameters
    conditions = {
        'materials': {
            'requirements_determined': True,
            'status': MaterialStatus.CHECKING
        },
        'inventory': {
            'updated': True
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'materials': {
            'availability_checked': True,
            'status': MaterialStatus.INSUFFICIENT
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material insufficiency determination action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material insufficiency determination.
        
        Args:
            client: API client for character data
            context: ActionContext containing required materials
            
        Returns:
            Action result with insufficiency status
        """
        self._context = context
        
        character_name = context.get(StateParameters.CHARACTER_NAME)
        
        # Get the target recipe we're working with
        target_recipe = context.get(StateParameters.TARGET_RECIPE)
        if not target_recipe:
            return self.create_error_result("No target recipe to check material insufficiency for")
            
        self.logger.info(f"🔍 Checking material insufficiency for recipe: {target_recipe}")
        
        # Get required materials from knowledge base
        knowledge_base = context.knowledge_base
        material_requirements = knowledge_base.get_material_requirements(target_recipe)
        if not material_requirements:
            return self.create_error_result(f"Could not determine requirements for recipe: {target_recipe}")
            
        self.logger.info(f"🔍 Determining insufficiency of {len(material_requirements)} materials")
        
        try:
            # Get current character inventory
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
                
            character_data = character_response.data
            inventory = getattr(character_data, 'inventory', [])
            
            # Check material availability using quantities
            availability_results = self._check_material_availability(material_requirements, inventory)
            
            # Determine if any materials are missing
            missing_materials = [item for item in availability_results if not item['sufficient']]
            has_missing = len(missing_materials) > 0
            
            # Always set status to insufficient - this action is for the insufficient path
            state_changes = {
                'materials': {
                    'availability_checked': True,
                    'status': MaterialStatus.INSUFFICIENT,
                    'gathered': False
                }
            }
            
            if has_missing:
                self.logger.info(f"✅ Confirmed {len(missing_materials)} materials are missing: {[item['material'] for item in missing_materials]}")
            else:
                self.logger.info("⚠️ All materials are actually available, but forcing insufficient status for GOAP path")
            
            # Store results in context using available StateParameters
            missing_materials_dict = {item['material']: item['shortfall'] for item in missing_materials}
            context.set_result(StateParameters.CURRENT_GATHERING_GOAL, {
                'material': list(missing_materials_dict.keys())[0] if missing_materials_dict else None,
                'quantity': list(missing_materials_dict.values())[0] if missing_materials_dict else 0
            })
            context.set_result(StateParameters.TOTAL_REQUIREMENTS, material_requirements)
            
            # Create the result with state changes
            result = self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=f"Material insufficiency determined: {len(missing_materials)} materials missing",
                total_materials=len(material_requirements),
                sufficient_materials=len(availability_results) - len(missing_materials),
                missing_materials_count=len(missing_materials),
                availability_details=availability_results
            )
            
            # If materials are missing, request a gather_resource subgoal for the first material
            if has_missing:
                first_material = list(missing_materials_dict.keys())[0]
                quantity_needed = missing_materials_dict[first_material]
                
                result.request_subgoal(
                    goal_name="gather_resource",
                    parameters={
                        "resource": first_material,
                        "quantity": quantity_needed,
                        "missing_materials": missing_materials_dict
                    },
                    preserve_context=["target_recipe", "target_slot", "total_requirements"]
                )
                self.logger.info(f"🎯 Requesting gather_resource subgoal: {quantity_needed} {first_material}")
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Material insufficiency determination failed: {str(e)}")
            
    def _check_material_availability(self, material_requirements: Dict[str, int], inventory: List) -> List[Dict]:
        """Check availability of each required material in inventory with quantities."""
        results = []
        
        # Convert inventory to dict for easy lookup
        inventory_dict = {}
        for item in inventory:
            if hasattr(item, 'code') and hasattr(item, 'quantity'):
                inventory_dict[item.code] = item.quantity
                
        for material, required_quantity in material_requirements.items():
            available_quantity = inventory_dict.get(material, 0)
            sufficient = available_quantity >= required_quantity
            
            results.append({
                'material': material,
                'required': required_quantity,
                'available': available_quantity,
                'sufficient': sufficient,
                'shortfall': max(0, required_quantity - available_quantity)
            })
            
            self.logger.debug(f"  {material}: {available_quantity}/{required_quantity} {'✓' if sufficient else '✗'}")
            
        return results
        
    def __repr__(self):
        return "DetermineMaterialInsufficiencyAction()"