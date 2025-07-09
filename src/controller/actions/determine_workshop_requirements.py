"""
Determine Workshop Requirements Action

This bridge action determines which workshop is required for
each material transformation.
"""

from typing import Dict, Any, List, Tuple, Optional

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from .base import ActionBase, ActionResult


class DetermineWorkshopRequirementsAction(ActionBase):
    """
    Bridge action to determine workshop requirements for transformations.
    
    This action takes a list of material transformations and determines
    which workshop type is required for each transformation.
    """
    
    def __init__(self):
        """Initialize determine workshop requirements action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Determine workshop requirements for transformations.
        
        Args:
            client: API client
            context: Action context containing:
                - transformations_needed: List of (raw, refined, quantity) tuples
                - knowledge_base: Knowledge base instance
                
        Returns:
            Dict with workshop requirements
        """
        self._context = context
        try:
            transformations = context.get(StateParameters.TRANSFORMATIONS_NEEDED, [])
            knowledge_base = context.knowledge_base
            
            self.logger.debug(f"🏭 Determining workshop requirements for {len(transformations)} transformations")
            
            # Build workshop requirements list
            workshop_requirements = []
            
            for raw_material, refined_material, quantity in transformations:
                workshop_type = self._determine_workshop_for_transformation(
                    raw_material, refined_material, client, knowledge_base
                )
                
                workshop_requirements.append({
                    'raw_material': raw_material,
                    'refined_material': refined_material,
                    'quantity': quantity,
                    'workshop_type': workshop_type
                })
                
                self.logger.info(f"🔧 {raw_material} → {refined_material} requires {workshop_type} workshop")
            
            # Store results in context
            context.set_result(StateParameters.WORKSHOP_REQUIREMENTS, workshop_requirements)
            
            return self.create_success_result(
                message="Workshop requirements determined successfully",
                workshop_requirements=workshop_requirements,
                unique_workshops=list(set(req['workshop_type'] for req in workshop_requirements if req['workshop_type']))
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to determine workshop requirements: {e}")
    
    def _determine_workshop_for_transformation(
        self, raw_material: str, refined_material: str, client, knowledge_base
    ) -> Optional[str]:
        """Determine which workshop is needed for a specific transformation."""
        try:
            # Look up the refined material to get crafting skill
            from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
            
            item_response = get_item_api(code=refined_material, client=client)
            if item_response and item_response.data and hasattr(item_response.data, 'craft'):
                craft_data = item_response.data.craft
                if hasattr(craft_data, 'skill'):
                    skill = craft_data.skill
                    # Map skill to workshop type
                    return self._get_workshop_for_skill(skill, knowledge_base)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error determining workshop for {raw_material} → {refined_material}: {e}")
            return None
    
    def _get_workshop_for_skill(self, skill: str, knowledge_base) -> str:
        """Map skill to workshop type."""
        # Check knowledge base first
        if knowledge_base and hasattr(knowledge_base, 'data'):
            workshops = knowledge_base.data.get('workshops', {})
            for workshop_code, workshop_data in workshops.items():
                if workshop_data.get('skill') == skill:
                    # Extract workshop type from code
                    return workshop_code.split('_')[0]
        
        # Fallback mappings
        skill_workshop_map = {
            'mining': 'mining',
            'smelting': 'mining',
            'woodcutting': 'woodcutting',
            'woodworking': 'woodcutting',
            'weaponcrafting': 'weaponcrafting',
            'gearcrafting': 'gearcrafting',
            'jewelrycrafting': 'jewelrycrafting',
            'cooking': 'cooking',
            'alchemy': 'alchemy'
        }
        
        return skill_workshop_map.get(skill, skill)
    
    def __repr__(self):
        return "DetermineWorkshopRequirementsAction()"