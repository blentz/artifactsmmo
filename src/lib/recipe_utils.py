"""
Recipe Utility Functions - Zero Backward Compatibility

Centralized recipe lookup using StateParameters registry only.
Single execution path for all recipe operations.

Design Principles:
- Single Responsibility: Recipe data access only
- DRY: Eliminates code duplication across actions
- KISS: Simple StateParameters-only access
- Zero backward compatibility: Clean slate
"""

import logging
from typing import Dict, Optional, Any

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


def get_recipe_from_context(context: ActionContext) -> Optional[Dict[str, Any]]:
    """
    Get recipe data using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        
    Returns:
        Recipe dictionary or None if not found
    """
    return context.get(StateParameters.EQUIPMENT_TARGET_RECIPE)


def get_recipe_materials(recipe: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract material requirements with quantities from recipe data.
    
    Args:
        recipe: Recipe dictionary from API response
        
    Returns:
        Dictionary mapping material codes to required quantities
    """
    materials = {}
    
    if not recipe or not isinstance(recipe, dict):
        return materials
    
    # Extract from craft.items structure (API format)
    craft_data = recipe.get('craft', {})
    if 'items' in craft_data and isinstance(craft_data['items'], list):
        for item in craft_data['items']:
            if isinstance(item, dict) and 'code' in item:
                material_code = item['code']
                quantity = item.get('quantity', 1)
                materials[material_code] = quantity
    
    return materials


def get_selected_item_from_context(context: ActionContext) -> Optional[str]:
    """
    Get selected item using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        
    Returns:
        Selected item code or None if not set
    """
    return context.get(StateParameters.EQUIPMENT_SELECTED_ITEM)


def get_target_slot_from_context(context: ActionContext) -> Optional[str]:
    """
    Get target equipment slot using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        
    Returns:
        Target slot name or None if not set
    """
    return context.get(StateParameters.EQUIPMENT_TARGET_SLOT)


def get_upgrade_status_from_context(context: ActionContext) -> Optional[str]:
    """
    Get equipment upgrade status using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        
    Returns:
        Upgrade status or None if not set
    """
    return context.get(StateParameters.EQUIPMENT_UPGRADE_STATUS)


def set_selected_item_in_context(context: ActionContext, item_code: str) -> None:
    """
    Set selected item using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        item_code: Item code to set as selected
    """
    context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, item_code)
    context.set(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM, bool(item_code))


def set_target_recipe_in_context(context: ActionContext, recipe: Dict[str, Any]) -> None:
    """
    Set target recipe using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        recipe: Recipe dictionary to set
    """
    context.set(StateParameters.EQUIPMENT_TARGET_RECIPE, recipe)


def set_upgrade_status_in_context(context: ActionContext, status: str) -> None:
    """
    Set equipment upgrade status using StateParameters registry.
    
    Args:
        context: ActionContext with StateParameters access
        status: Status to set
    """
    context.set(StateParameters.EQUIPMENT_UPGRADE_STATUS, status)