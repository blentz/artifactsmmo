"""
Determine Material Requirements Action

This action determines what materials are needed to craft the selected recipe,
checking the recipe requirements and current inventory status.
"""

from typing import Dict, List, Optional

from src.controller.actions.base import ActionBase
from src.lib.action_context import ActionContext


class DetermineMaterialRequirementsAction(ActionBase):
    """
    Action to determine material requirements for selected recipe.
    
    This action analyzes the selected recipe and determines what materials
    are needed, checking inventory and setting up for material gathering.
    """
    
    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'ready',
            'has_selected_item': True
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'materials': {
            'requirements_determined': True,
            'status': 'checking'
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material requirements action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> Dict:
        """
        Execute material requirements determination.
        
        Args:
            client: API client (not used for this analysis)
            context: ActionContext containing selected recipe
            
        Returns:
            Action result with material requirements
        """
        super().execute(client, context)
        
        # Get selected recipe from context
        selected_item = context.get('selected_item')
        selected_recipe = context.get('selected_recipe', {})
        
        if not selected_item:
            return self.get_error_response("No selected item available")
            
        self.logger.info(f"🔍 Determining material requirements for {selected_item}")
        
        try:
            # Get materials from recipe or use knowledge base
            materials = self._get_recipe_materials(selected_recipe, selected_item, context)
            
            if not materials:
                return self.get_error_response(f"Could not determine materials for {selected_item}")
            
            # Store results in context
            context.set_result('required_materials', materials)
            context.set_result('material_analysis', {
                'item_code': selected_item,
                'materials_needed': materials,
                'total_materials': len(materials)
            })
            
            self.logger.info(f"📋 Found {len(materials)} material requirements: {', '.join(materials)}")
            
            return self.get_success_response(
                item_code=selected_item,
                required_materials=materials,
                total_materials=len(materials)
            )
            
        except Exception as e:
            return self.get_error_response(f"Material requirements determination failed: {str(e)}")
            
    def _get_recipe_materials(self, recipe: Dict, item_code: str, context: ActionContext) -> List[str]:
        """Get materials needed for the recipe."""
        try:
            # First try from the recipe data if available
            if recipe and 'materials' in recipe:
                materials = recipe['materials']
                if isinstance(materials, list):
                    return materials
                    
            # Fall back to knowledge base lookup
            knowledge_base = getattr(context, 'knowledge_base', None)
            if knowledge_base:
                item_data = knowledge_base.get_item_data(item_code)
                if item_data and isinstance(item_data, dict):
                    craft_info = item_data.get('craft', {})
                    if craft_info and 'items' in craft_info:
                        # Extract material names from craft items
                        craft_items = craft_info['items']
                        if isinstance(craft_items, list):
                            materials = []
                            for item in craft_items:
                                if isinstance(item, dict) and 'code' in item:
                                    materials.append(item['code'])
                            return materials
                            
            # No hardcoded fallbacks - API is the source of truth
            self.logger.warning(f"Could not determine materials for {item_code} - API data required")
            return []
            
        except Exception as e:
            self.logger.warning(f"Error determining materials for {item_code}: {e}")
            return []
            
        
    def __repr__(self):
        return "DetermineMaterialRequirementsAction()"