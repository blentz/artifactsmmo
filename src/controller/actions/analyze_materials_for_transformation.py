"""
Analyze Materials for Transformation Action

This bridge action analyzes the character's inventory to determine
which raw materials should be transformed into refined materials.
"""

from typing import Dict, Any, List, Tuple, Optional

from src.lib.action_context import ActionContext
from .base import ActionBase


class AnalyzeMaterialsForTransformationAction(ActionBase):
    """
    Bridge action to analyze inventory and determine transformation opportunities.
    
    This action examines the character's inventory and determines which raw
    materials can and should be transformed based on the target item requirements
    or general transformation opportunities.
    """
    
    def __init__(self):
        """Initialize analyze materials action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> Dict[str, Any]:
        """
        Analyze inventory for transformation opportunities.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - inventory: Current inventory
                - target_item: Optional target item to craft
                - knowledge_base: Knowledge base instance
                
        Returns:
            Dict with transformation analysis results
        """
        try:
            inventory = context.get('inventory', [])
            target_item = context.get('target_item')
            knowledge_base = context.knowledge_base
            
            self.logger.debug(f"🔍 Analyzing materials for transformation, target: {target_item}")
            
            # Convert inventory to dict for easier lookup
            inventory_dict = self._build_inventory_dict(inventory)
            
            # Get material transformation mappings
            transformations_map = self._get_transformation_mappings(knowledge_base)
            
            # Determine what to transform
            if target_item:
                transformations = self._analyze_for_target_item(
                    inventory_dict, transformations_map, target_item, client
                )
            else:
                transformations = self._analyze_general_transformations(
                    inventory_dict, transformations_map, context
                )
            
            # Store results in context for next action
            context.set_result('transformations_needed', transformations)
            
            self.logger.info(f"📊 Found {len(transformations)} transformation opportunities")
            
            return self.get_success_response(
                transformations=transformations,
                transformation_count=len(transformations),
                target_item=target_item
            )
            
        except Exception as e:
            return self.get_error_response(f"Failed to analyze materials: {e}")
    
    def _build_inventory_dict(self, inventory: list) -> Dict[str, int]:
        """Convert inventory list to dict for easier lookup."""
        inventory_dict = {}
        for item in inventory:
            # Handle both dict and object formats
            if hasattr(item, 'code') and hasattr(item, 'quantity'):
                code = item.code
                quantity = item.quantity
            elif isinstance(item, dict):
                code = item.get('code')
                quantity = item.get('quantity', 0)
            else:
                continue
                
            if code and quantity > 0:
                inventory_dict[code] = quantity
                
        return inventory_dict
    
    def _get_transformation_mappings(self, knowledge_base) -> Dict[str, str]:
        """Get raw material to refined material mappings."""
        transformations = {}
        
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # Check for direct transformation mappings
            transformations = knowledge_base.data.get('material_transformations', {})
            
            # If not found, derive from items
            if not transformations:
                items = knowledge_base.data.get('items', {})
                for item_code, item_data in items.items():
                    craft_data = item_data.get('craft_data', {})
                    if craft_data and 'items' in craft_data:
                        craft_items = craft_data.get('items', [])
                        # Simple transformations (1 input -> 1 output)
                        if len(craft_items) == 1:
                            input_item = craft_items[0]
                            if isinstance(input_item, dict):
                                raw_material = input_item.get('code')
                                if raw_material and self._is_raw_material(raw_material):
                                    transformations[raw_material] = item_code
        
        return transformations
    
    def _is_raw_material(self, material_code: str) -> bool:
        """Check if material is a raw material based on patterns."""
        raw_patterns = ['_ore', '_wood', 'coal']
        return any(pattern in material_code for pattern in raw_patterns)
    
    def _analyze_for_target_item(
        self, inventory_dict: Dict[str, int], 
        transformations_map: Dict[str, str],
        target_item: str,
        client
    ) -> List[Tuple[str, str, int]]:
        """Analyze transformations needed for a specific target item."""
        transformations = []
        
        # Get requirements for target item
        required_materials = self._get_item_requirements(target_item, client)
        
        for raw_material, refined_material in transformations_map.items():
            if raw_material not in inventory_dict:
                continue
                
            raw_quantity = inventory_dict[raw_material]
            
            # Check if we need this refined material
            if refined_material in required_materials:
                needed_quantity = required_materials[refined_material]
                current_quantity = inventory_dict.get(refined_material, 0)
                
                if current_quantity < needed_quantity:
                    # Calculate how much to transform
                    deficit = needed_quantity - current_quantity
                    # For now, assume 1:1 transformation ratio
                    # In real usage, we'd check the actual recipe requirements
                    can_transform = min(raw_quantity, deficit)
                    
                    if can_transform > 0:
                        transformations.append((raw_material, refined_material, can_transform))
        
        return transformations
    
    def _analyze_general_transformations(
        self, inventory_dict: Dict[str, int],
        transformations_map: Dict[str, str],
        context: ActionContext
    ) -> List[Tuple[str, str, int]]:
        """Analyze general transformation opportunities."""
        transformations = []
        
        # Get default transform quantity from config
        action_config = context.get('action_config', {})
        default_quantity = action_config.get('default_transform_quantity', 1)
        
        for raw_material, refined_material in transformations_map.items():
            if raw_material in inventory_dict:
                raw_quantity = inventory_dict[raw_material]
                if raw_quantity > 0:
                    transform_quantity = min(raw_quantity, default_quantity)
                    transformations.append((raw_material, refined_material, transform_quantity))
        
        return transformations
    
    def _get_item_requirements(self, item_code: str, client) -> Dict[str, int]:
        """Get material requirements for an item."""
        try:
            from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
            
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return {}
            
            item_data = item_response.data
            if not hasattr(item_data, 'craft') or not item_data.craft:
                return {}
            
            requirements = {}
            if hasattr(item_data.craft, 'items') and item_data.craft.items:
                for item in item_data.craft.items:
                    if hasattr(item, 'code') and hasattr(item, 'quantity'):
                        requirements[item.code] = item.quantity
            
            return requirements
            
        except Exception as e:
            self.logger.warning(f"Could not get requirements for {item_code}: {e}")
            return {}
    
    def __repr__(self):
        return "AnalyzeMaterialsForTransformationAction()"