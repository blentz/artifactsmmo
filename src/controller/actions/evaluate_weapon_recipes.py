"""
Simple Weapon Recipe Evaluation Action

This action follows the architecture principles:
- Simple boolean/string conditions
- Single responsibility 
- Declarative configuration
- Direct property access with StateParameters
"""

import logging
from typing import Dict, List, Optional

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class EvaluateWeaponRecipesAction(ActionBase):
    """
    Simple action to evaluate weapon recipes using declarative configuration.
    
    Follows architecture principles:
    - Simple boolean conditions
    - Single responsibility
    - Uses StateParameters for all data
    - No complex business logic
    """

    # GOAP parameters - simple boolean conditions
    conditions = {
        'character_status': {
            'alive': True,
        },
    }
    reactions = {
        'equipment_status': {
            'target_item_selected': True,
        }
    }
    weight = 10

    def __init__(self):
        """Initialize the simple weapon recipe evaluation action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Simple weapon recipe evaluation using declarative configuration."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context using StateParameters
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
        
        current_weapon = context.get(StateParameters.EQUIPMENT_WEAPON)
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        knowledge_base = context.knowledge_base
        
        if not knowledge_base:
            return self.create_error_result("No knowledge base available")
        
        self._context = context
        
        try:
            # Simple approach: Find first craftable weapon better than current
            items = knowledge_base.data.get('items', {})
            
            # Get configuration from StateParameters
            max_level_above = context.get(StateParameters.ACTION_MAX_WEAPON_LEVEL_ABOVE_CHARACTER, 1)
            max_level = character_level + max_level_above
            
            # Find suitable weapons
            suitable_weapons = []
            for item_code, item_data in items.items():
                # Check if it's a weapon with craft data
                craft_data = item_data.get('craft_data')
                if not craft_data:
                    continue
                    
                # Check if it's a weaponcrafting item
                if craft_data.get('skill') != 'weaponcrafting':
                    continue
                    
                # Check level requirement
                item_level = item_data.get('level', 1)
                if item_level > max_level:
                    continue
                    
                suitable_weapons.append({
                    'code': item_code,
                    'name': item_data.get('name', item_code),
                    'level': item_level,
                    'materials': craft_data.get('items', [])
                })
            
            if not suitable_weapons:
                return self.create_error_result("No suitable weapons found")
            
            # Select first suitable weapon (simple selection)
            selected_weapon = suitable_weapons[0]
            
            # Simple success result
            result = self.create_success_result(
                selected_weapon=selected_weapon['code'],
                target_item=selected_weapon['code'],
                item_code=selected_weapon['code'],
                weapon_name=selected_weapon['name'],
                current_weapon=current_weapon,
                required_materials=selected_weapon['materials']
            )
            
            # Update context with selected weapon
            context.set_result(StateParameters.TARGET_ITEM, selected_weapon['code'])
            context.set_result(StateParameters.ITEM_CODE, selected_weapon['code'])
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Weapon evaluation failed: {str(e)}")
    
    def __repr__(self):
        return "EvaluateWeaponRecipesAction()"