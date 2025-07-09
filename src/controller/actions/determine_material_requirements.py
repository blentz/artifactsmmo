"""
Determine Material Requirements Action

This action determines what materials are needed to craft the selected recipe,
checking the recipe requirements and current inventory status.
"""

from typing import Dict, List, Optional

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.recipe_utils import get_recipe_from_context, get_recipe_materials, get_selected_item_from_context


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
        },
        'inventory': {
            'updated': True
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the material requirements action."""
        super().__init__()
        # Import here to avoid circular imports
        from src.controller.knowledge.base import KnowledgeBase
        self.knowledge_base = KnowledgeBase()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material requirements determination.
        
        Args:
            client: API client (not used for this analysis)
            context: ActionContext containing selected recipe
            
        Returns:
            ActionResult with material requirements
        """
        super().execute(client, context)
        
        # Use utility functions to get recipe data from singleton context
        selected_item = get_selected_item_from_context(context)
        selected_recipe = get_recipe_from_context(context)
        
        if not selected_item:
            return self.create_error_result("No selected item available")
        
        self.logger.info(f"🔍 Determining material requirements for {selected_item}")
        
        try:
            # Use recipe data to get direct material requirements if available
            material_requirements = {}
            if selected_recipe:
                material_requirements = get_recipe_materials(selected_recipe)
            
            # If no direct materials found, try recursive calculation
            if not material_requirements:
                material_requirements = self._calculate_material_requirements_with_quantities(selected_item, context)
            
            if not material_requirements:
                return self.create_error_result(f"Could not determine materials for {selected_item}")
            
            # Extract material names for backward compatibility
            materials = list(material_requirements.keys())
            
            # Store results in context using StateParameters
            context.set_result(StateParameters.REQUIRED_MATERIALS, materials)
            context.set_result(StateParameters.MATERIAL_REQUIREMENTS, material_requirements)
            context.set_result(StateParameters.MATERIAL_ANALYSIS, {
                'item_code': selected_item,
                'materials_needed': materials,
                'material_requirements': material_requirements,
                'total_materials': len(materials)
            })
            
            # Store on context using StateParameters for other actions to access
            context.set(StateParameters.REQUIRED_MATERIALS, materials)
            context.set(StateParameters.MATERIAL_REQUIREMENTS, material_requirements)
            
            # Log the detailed requirements showing quantities
            requirements_display = [f"{qty} {material}" for material, qty in material_requirements.items()]
            self.logger.info(f"📋 Found material requirements: {', '.join(requirements_display)}")
            
            # Create state changes to mark requirements as determined
            state_changes = {
                'materials': {
                    'requirements_determined': True,
                    'status': 'checking',
                    'required': material_requirements  # Store requirements in world state
                },
                'inventory': {
                    'updated': True
                }
            }
            
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=f"Found material requirements: {', '.join(requirements_display)}",
                item_code=selected_item,
                required_materials=materials,
                material_requirements=material_requirements,
                total_materials=len(materials)
            )
            
        except Exception as e:
            return self.create_error_result(f"Material requirements determination failed: {str(e)}")
            
    def _get_recipe_materials(self, recipe: Dict, item_code: str, context: ActionContext) -> List[str]:
        """Get materials needed for the recipe, recursively finding raw materials."""
        try:
            # Get direct materials first
            direct_materials = self._get_direct_materials(recipe, item_code, context)
            if not direct_materials:
                return []
            
            # Recursively resolve materials to raw materials
            all_materials = []
            knowledge_base = getattr(context, 'knowledge_base', None)
            
            for material in direct_materials:
                raw_materials = self._resolve_to_raw_materials(material, context, knowledge_base)
                all_materials.extend(raw_materials)
            
            # Remove duplicates while preserving order
            unique_materials = []
            seen = set()
            for material in all_materials:
                if material not in seen:
                    unique_materials.append(material)
                    seen.add(material)
            
            return unique_materials
            
        except Exception as e:
            self.logger.warning(f"Error determining materials for {item_code}: {e}")
            return []
    
    def _get_direct_materials(self, recipe: Dict, item_code: str, context: ActionContext) -> List[str]:
        """Get direct materials from recipe without recursion."""
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
            self.logger.warning(f"Error determining direct materials for {item_code}: {e}")
            return []
    
    def _resolve_to_raw_materials(self, material: str, context: ActionContext, knowledge_base, visited=None) -> List[str]:
        """Recursively resolve a material to its raw materials."""
        if visited is None:
            visited = set()
        
        # Prevent infinite recursion
        if material in visited:
            return [material]
        
        visited.add(material)
        
        try:
            # Check if this material has a crafting recipe
            if knowledge_base:
                item_data = knowledge_base.get_item_data(material)
                if item_data and isinstance(item_data, dict):
                    craft_info = item_data.get('craft', {})
                    if craft_info and 'items' in craft_info:
                        # This material can be crafted - get its components
                        craft_items = craft_info['items']
                        if isinstance(craft_items, list):
                            sub_materials = []
                            for item in craft_items:
                                if isinstance(item, dict) and 'code' in item:
                                    # Recursively resolve each component
                                    sub_raw_materials = self._resolve_to_raw_materials(
                                        item['code'], context, knowledge_base, visited.copy()
                                    )
                                    sub_materials.extend(sub_raw_materials)
                            return sub_materials
            
            # This material has no crafting recipe - it's a raw material
            return [material]
            
        except Exception as e:
            self.logger.warning(f"Error resolving material {material}: {e}")
            return [material]
            
    def _calculate_material_requirements_with_quantities(self, item_code: str, context: ActionContext, quantity: int = 1) -> Dict[str, int]:
        """
        Calculate material requirements with quantities recursively.
        
        Args:
            item_code: The item to craft
            context: ActionContext for knowledge base access
            quantity: How many to craft
            
        Returns:
            Dict mapping material codes to total quantities needed
        """
        requirements = {}
        
        # Use instance knowledge base with API fallback
        client = getattr(context, 'client', None) if hasattr(context, 'client') else None
        item_data = self.knowledge_base.get_item_data(item_code, client=client)
        if not item_data or not isinstance(item_data, dict):
            # This is a raw material
            return {item_code: quantity}
            
        # Check if item has crafting recipe
        craft_info = item_data.get('craft', {})
        if not craft_info or 'items' not in craft_info:
            # This is a raw material
            return {item_code: quantity}
            
        # Process each material in the recipe
        craft_items = craft_info['items']
        if isinstance(craft_items, list):
            for item in craft_items:
                if isinstance(item, dict) and 'code' in item:
                    material_code = item['code']
                    material_quantity = item.get('quantity', 1) * quantity
                    
                    # Recursively calculate requirements for this material
                    sub_requirements = self._calculate_material_requirements_with_quantities(
                        material_code, context, material_quantity
                    )
                    
                    # Merge sub-requirements
                    for sub_code, sub_quantity in sub_requirements.items():
                        if sub_code in requirements:
                            requirements[sub_code] += sub_quantity
                        else:
                            requirements[sub_code] = sub_quantity
                            
        return requirements
        
    def __repr__(self):
        return "DetermineMaterialRequirementsAction()"