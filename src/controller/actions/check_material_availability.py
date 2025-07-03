"""
Check Material Availability Action

This action checks if the required materials are available in inventory
and determines what materials need to be gathered.
"""

from typing import Dict, List

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase
from src.lib.action_context import ActionContext


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
            'status': 'checking'
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
            'status': 'sufficient'  # Will be overridden if materials are missing
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material availability check action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> Dict:
        """
        Execute material availability check.
        
        Args:
            client: API client for character data
            context: ActionContext containing required materials
            
        Returns:
            Action result with availability status
        """
        super().execute(client, context)
        
        character_name = context.character_name
        required_materials = context.get('required_materials', [])
        
        if not required_materials:
            return self.get_error_response("No required materials specified")
            
        self.logger.info(f"🔍 Checking availability of {len(required_materials)} materials")
        
        try:
            # Get current character inventory
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
                
            character_data = character_response.data
            inventory = getattr(character_data, 'inventory', [])
            
            # Check material availability
            availability_results = self._check_material_availability(required_materials, inventory)
            
            # Determine if all materials are sufficient
            missing_materials = [item for item in availability_results if not item['sufficient']]
            all_sufficient = len(missing_materials) == 0
            
            # Update reactions based on results
            if all_sufficient:
                self.reactions = {
                    'materials': {
                        'availability_checked': True,
                        'status': 'sufficient',
                        'gathered': True
                    }
                }
                self.logger.info("✅ All materials are available in inventory!")
            else:
                self.reactions = {
                    'materials': {
                        'availability_checked': True, 
                        'status': 'insufficient',
                        'gathered': False
                    }
                }
                self.logger.info(f"❌ Missing {len(missing_materials)} materials: {[item['material'] for item in missing_materials]}")
            
            # Store detailed results in context
            context.set_result('material_availability', availability_results)
            context.set_result('missing_materials', [item['material'] for item in missing_materials])
            context.set_result('sufficient_materials', [item['material'] for item in availability_results if item['sufficient']])
            
            return self.get_success_response(
                total_materials=len(required_materials),
                sufficient_materials=len(availability_results) - len(missing_materials),
                missing_materials=len(missing_materials),
                all_sufficient=all_sufficient,
                availability_details=availability_results
            )
            
        except Exception as e:
            return self.get_error_response(f"Material availability check failed: {str(e)}")
            
    def _check_material_availability(self, required_materials: List[str], inventory: List) -> List[Dict]:
        """Check availability of each required material in inventory."""
        results = []
        
        # Convert inventory to dict for easy lookup
        inventory_dict = {}
        for item in inventory:
            if hasattr(item, 'code') and hasattr(item, 'quantity'):
                inventory_dict[item.code] = item.quantity
                
        for material in required_materials:
            # For now, assume we need 1 of each material
            required_quantity = 1
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