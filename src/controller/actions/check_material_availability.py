"""
Check Material Availability Action

This action checks if the required materials are available in inventory
and determines what materials need to be gathered.
"""

from typing import Dict, List

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.recipe_utils import get_recipe_materials
from src.game.globals import MaterialStatus


class CheckMaterialAvailabilityAction(ActionBase):
    """
    Action to check material availability in inventory.
    
    This action checks the current inventory against required materials
    and determines what needs to be gathered.
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
            # Don't set status here - let runtime determine if sufficient/insufficient
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material availability check action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material availability check.
        
        Args:
            client: API client for character data
            context: ActionContext containing required materials
            
        Returns:
            Action result with availability status
        """
        self._context = context
        
        character_name = context.get(StateParameters.CHARACTER_NAME)
        
        # Get the target recipe we're working with
        target_recipe = context.get(StateParameters.TARGET_RECIPE)
        if not target_recipe:
            return self.create_error_result("No target recipe to check material availability for")
            
        self.logger.info(f"🔍 Checking material availability for recipe: {target_recipe}")
        
        # Get required materials from knowledge base
        knowledge_base = context.knowledge_base
        material_requirements = knowledge_base.get_material_requirements(target_recipe)
        if not material_requirements:
            return self.create_error_result(f"Could not determine requirements for recipe: {target_recipe}")
            
        self.logger.info(f"🔍 Checking availability of {len(material_requirements)} materials")
        
        try:
            # Get current character inventory
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
                
            character_data = character_response.data
            inventory = getattr(character_data, 'inventory', [])
            
            # Check material availability
            availability_results = self._check_material_availability(material_requirements, inventory)
            
            # Determine if all materials are sufficient
            missing_materials = [item for item in availability_results if not item['sufficient']]
            all_sufficient = len(missing_materials) == 0
            
            # Determine state changes based on results
            if all_sufficient:
                state_changes = {
                    'materials': {
                        'availability_checked': True,
                        'status': MaterialStatus.SUFFICIENT,
                        'gathered': True
                    }
                }
                self.logger.info("✅ All materials are available in inventory!")
            else:
                state_changes = {
                    'materials': {
                        'availability_checked': True, 
                        'status': MaterialStatus.INSUFFICIENT,
                        'gathered': False
                    }
                }
                self.logger.info(f"❌ Missing {len(missing_materials)} materials: {[item['material'] for item in missing_materials]}")
            
            # Context already has TARGET_RECIPE - no additional parameters needed
            
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=f"Material availability check completed: {'All materials available' if all_sufficient else f'{len(missing_materials)} materials missing'}",
                total_materials=len(material_requirements),
                sufficient_materials=len(availability_results) - len(missing_materials),
                missing_materials=len(missing_materials),
                all_sufficient=all_sufficient,
                availability_details=availability_results
            )
            
        except Exception as e:
            return self.create_error_result(f"Material availability check failed: {str(e)}")
            
    def _check_material_availability(self, material_requirements: Dict[str, int], inventory: List) -> List[Dict]:
        """Check availability of each required material in inventory."""
        results = []
        
        # Convert inventory to dict for easy lookup
        inventory_dict = {}
        for item in inventory:
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
        return "CheckMaterialAvailabilityAction()"