"""
Calculate Material Quantities Action

This action calculates the total quantities of raw materials needed
for a crafting chain, taking into account intermediate transformations.
"""

from typing import Dict, List, Tuple
from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import MaterialStatus
from src.controller.knowledge.base import KnowledgeBase


class CalculateMaterialQuantitiesAction(ActionBase):
    """
    Calculate total material quantities needed for crafting.
    
    This action determines the full quantity requirements for a crafting chain,
    including intermediate materials that need to be crafted.
    """
    
    # GOAP parameters
    conditions = {
        'materials': {
            'requirements_determined': True,
            'status': MaterialStatus.INSUFFICIENT,
            'availability_checked': True
        },
        'equipment_status': {
            'has_selected_item': True
        },
        'character_status': {
            'alive': True
        }
    }
    
    reactions = {
        'materials': {
            'quantities_calculated': True,
            'raw_materials_needed': True
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material quantity calculation action."""
        super().__init__()
        self.knowledge_base = KnowledgeBase()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Calculate total material quantities needed.
        
        Args:
            client: API client (not used in this action)
            context: ActionContext containing selected item and material info
            
        Returns:
            ActionResult with calculated quantities
        """
        self._context = context
        self._client = client
        
        try:
            # Debug context
            self.logger.debug(f"Context type: {type(context)}")
            
            # Get the target item we're crafting
            selected_item = context.get(StateParameters.SELECTED_ITEM)
            if not selected_item:
                return self.create_error_result("No selected item to calculate materials for")
                
            self.logger.info(f"📊 Calculating material quantities for {selected_item}")
            
            # Get missing materials from context (should be a dict)
            missing_materials = context.get(StateParameters.MISSING_MATERIALS, {})
                
            if not missing_materials:
                self.logger.error(f"No missing materials found in context")
                return self.create_error_result("No missing materials to calculate quantities for")
                
            # Calculate full material requirements
            total_requirements = self._calculate_full_requirements(selected_item)
            
            # Calculate raw material needs
            raw_material_needs = {}
            for material, shortage in missing_materials.items():
                if material in total_requirements:
                    raw_material_needs[material] = total_requirements[material]
                else:
                    # If not in total requirements, use the shortage amount
                    raw_material_needs[material] = shortage if shortage > 0 else 1
                    
            self.logger.info(f"🎯 Total raw materials needed: {raw_material_needs}")
            
            # Store in context for resource gathering
            context.set_result(StateParameters.RAW_MATERIAL_NEEDS, raw_material_needs)
            context.set_result(StateParameters.TOTAL_REQUIREMENTS, total_requirements)
            
            # Set material goal for resource gathering
            if raw_material_needs:
                # Pick the first material to gather
                first_material = list(raw_material_needs.keys())[0]
                quantity_needed = raw_material_needs[first_material]
                
                context.set_result(StateParameters.CURRENT_GATHERING_GOAL, {
                    'material': first_material,
                    'quantity': quantity_needed
                })
                
                self.logger.info(f"🎯 Setting gathering goal: {quantity_needed} {first_material}")
            
            state_changes = {
                'materials': {
                    'quantities_calculated': True,
                    'raw_materials_needed': True
                }
            }
            
            # Create the result with state changes
            result = self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=f"Calculated material quantities for {selected_item}",
                raw_material_needs=raw_material_needs,
                total_requirements=total_requirements
            )
            
            # If raw materials are needed, request a gather_resource subgoal for the first material
            if raw_material_needs:
                first_material = list(raw_material_needs.keys())[0]
                quantity_needed = raw_material_needs[first_material]
                
                result.request_subgoal(
                    goal_name="gather_resource",
                    parameters={
                        "resource": first_material,
                        "quantity": quantity_needed,
                        "raw_material_needs": raw_material_needs
                    },
                    preserve_context=["selected_item", "target_slot", "total_requirements"]
                )
                self.logger.info(f"🎯 Requesting gather_resource subgoal: {quantity_needed} {first_material}")
            
            return result
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error in calculate_material_quantities: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self.create_error_result(f"Failed to calculate material quantities: {str(e)}")
            
    def _calculate_full_requirements(self, item_code: str, quantity: int = 1) -> Dict[str, int]:
        """
        Recursively calculate all material requirements for an item.
        
        Args:
            item_code: The item to craft
            quantity: How many to craft
            
        Returns:
            Dict mapping material codes to total quantities needed
        """
        requirements = {}
        
        # Get item data from knowledge base with API fallback
        client = self._client if hasattr(self, '_client') else None
        self.logger.debug(f"Getting item data for {item_code}, client available: {client is not None}")
        
        item_data = self.knowledge_base.get_item_data(item_code, client=client)
        self.logger.debug(f"Item data for {item_code}: {item_data}")
        
        if not item_data or 'craft' not in item_data:
            # This is a raw material or unknown item
            self.logger.debug(f"{item_code} is a raw material or has no craft data")
            return {item_code: quantity}
            
        craft_info = item_data.get('craft')
        if not craft_info:
            self.logger.debug(f"No craft info for {item_code}")
            return {item_code: quantity}
            
        craft_items = craft_info.get('items', [])
        
        # For each required material
        for material in craft_items:
            if not material:
                self.logger.warning(f"Skipping None material in craft_items for {item_code}")
                continue
                
            if isinstance(material, dict):
                material_code = material.get('code')
            else:
                self.logger.warning(f"Material is not a dict: {type(material)}, value: {material}")
                continue
                
            if not material_code:
                self.logger.warning(f"Material has no code: {material}")
                continue
                
            material_quantity = material.get('quantity', 1) * quantity
            
            # Check if this material itself needs crafting
            sub_requirements = self._calculate_full_requirements(material_code, material_quantity)
            
            # Merge sub-requirements into our requirements
            for sub_code, sub_quantity in sub_requirements.items():
                if sub_code in requirements:
                    requirements[sub_code] += sub_quantity
                else:
                    requirements[sub_code] = sub_quantity
                    
        return requirements
        
    def __repr__(self):
        return "CalculateMaterialQuantitiesAction()"