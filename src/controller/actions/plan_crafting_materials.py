"""
Plan Crafting Materials Action

This action analyzes what materials are needed for a selected item and sets
appropriate GOAP states to trigger material gathering and crafting.
"""

from typing import TYPE_CHECKING, Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from .base import ActionBase

if TYPE_CHECKING:
    from src.lib.action_context import ActionContext


class PlanCraftingMaterialsAction(ActionBase):
    """
    Action to analyze crafting requirements for a selected item and plan material gathering.
    
    This is a general-purpose action that:
    1. Checks what item was selected for crafting (from action context)
    2. Analyzes what materials are needed vs what's available
    3. Sets appropriate GOAP states to trigger gathering/crafting
    """
    
    # GOAP parameters
    conditions = {
        "character_alive": True,
        "best_weapon_selected": True,  # Or any item selected for crafting
        "craft_plan_available": False  # Haven't planned materials yet
    }
    reactions = {
        "craft_plan_available": True,
        "need_resources": True,  # If materials are missing
        "materials_sufficient": True,  # If we have everything
        "material_requirements_known": True
    }
    weights = {"material_requirements_known": 10}
    
    def __init__(self):
        """
        Initialize the crafting materials planning action.
        """
        super().__init__()
        
    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """Plan material gathering for crafting"""
        # Call superclass to set self._context
        super().execute(client, context)
        
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
            
        # Get parameters from context
        character_name = context.character_name
        target_item = context.get('target_item')
        
        self.log_execution_start(
            character_name=character_name,
            target_item=target_item
        )
        
        try:
            # Get knowledge base from context
            knowledge_base = context.knowledge_base
            if not knowledge_base:
                return self.get_error_response("No knowledge base available")
            
            # Determine target item from context
            if not target_item:
                target_item = self._determine_target_item(context)
            if not target_item:
                return self.get_error_response("No target item specified for crafting")
            
            # Get character inventory
            inventory_lookup = self._get_character_inventory(client, character_name)
            
            # Get item crafting requirements from knowledge base
            item_data = knowledge_base.get_item_data(target_item, client=client)
            if not item_data:
                return self.get_error_response(f"Could not find item data for {target_item}")
            
            # Analyze material requirements
            craft_data = item_data.get('craft_data', {})
            if not craft_data:
                return self.get_error_response(f"Item {target_item} is not craftable")
            
            required_materials = craft_data.get('items', [])
            if not required_materials:
                return self.get_error_response(f"No materials required for {target_item}")
            
            # Check what materials we have vs what we need
            material_analysis = self._analyze_material_availability(
                required_materials, inventory_lookup, knowledge_base, client
            )
            
            # Build the crafting plan
            crafting_plan = self._build_crafting_plan(
                target_item, material_analysis, craft_data, knowledge_base
            )
            
            # Determine GOAP state updates
            state_updates = self._determine_state_updates(material_analysis)
            
            # Store target item in result for execute_crafting_plan to use
            result = self.get_success_response(
                target_item=target_item,
                item_code=target_item,  # For compatibility
                material_analysis=material_analysis,
                crafting_plan=crafting_plan,
                missing_materials=material_analysis['missing_materials'],
                total_materials_needed=len(required_materials),
                materials_available=material_analysis['available_count'],
                **state_updates
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Crafting planning failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response
    
    def _determine_target_item(self, context: 'ActionContext') -> Optional[str]:
        """Determine target item from context or parameters"""
        # Check context for selected weapon/item
        if 'selected_weapon' in context:
            return context['selected_weapon']
        if 'item_code' in context:
            return context['item_code']
        if 'target_item' in context:
            return context['target_item']
        
        # Fall back to using target_item from context directly
        return self._context.get('target_item') if self._context else None
    
    def _get_character_inventory(self, client, character_name: str) -> Dict[str, int]:
        """Get character inventory as item_code -> quantity lookup"""
        try:
            character_response = get_character_api(name=character_name, client=client)
            
            if not character_response or not character_response.data:
                return {}
            
            character_data = character_response.data
            inventory = getattr(character_data, 'inventory', [])
            inventory_lookup = {}
            
            # Add items from inventory
            for item in inventory:
                if hasattr(item, 'code') and hasattr(item, 'quantity'):
                    code = item.code
                    quantity = item.quantity
                    if code and quantity > 0:
                        inventory_lookup[code] = quantity
            
            # Also count equipped items
            for attr_name in dir(character_data):
                if attr_name.endswith('_slot') and not attr_name.startswith('_'):
                    equipped_item = getattr(character_data, attr_name, '')
                    if equipped_item:
                        inventory_lookup[equipped_item] = inventory_lookup.get(equipped_item, 0) + 1
                        self.logger.info(f"Counting equipped {equipped_item} in {attr_name}")
            
            return inventory_lookup
            
        except Exception as e:
            self.logger.warning(f"Could not get character inventory: {e}")
            return {}
    
    def _analyze_material_availability(self, required_materials: List[Dict], 
                                     inventory_lookup: Dict[str, int],
                                     knowledge_base, client) -> Dict:
        """Analyze what materials we have vs what we need"""
        analysis = {
            'required_materials': [],
            'missing_materials': [],
            'available_materials': [],
            'total_needed': 0,
            'total_available': 0,
            'available_count': 0,
            'missing_count': 0,
            'all_materials_available': True
        }
        
        for material in required_materials:
            material_code = material.get('code', '')
            required_qty = material.get('quantity', 1)
            available_qty = inventory_lookup.get(material_code, 0)
            
            material_info = {
                'code': material_code,
                'required': required_qty,
                'available': available_qty,
                'missing': max(0, required_qty - available_qty)
            }
            
            # Get material details from knowledge base
            material_data = knowledge_base.get_item_data(material_code, client=client)
            if material_data:
                material_info['name'] = material_data.get('name', material_code)
                material_info['type'] = material_data.get('type', 'unknown')
                
                # Check if this is a gatherable resource
                sources = material_data.get('sources', [])
                if sources:
                    material_info['gatherable'] = True
                    material_info['sources'] = sources
                else:
                    # Check if it needs to be crafted
                    if material_data.get('craft_data'):
                        material_info['craftable'] = True
                        material_info['workshop'] = material_data['craft_data'].get('skill', 'unknown')
            
            analysis['required_materials'].append(material_info)
            analysis['total_needed'] += required_qty
            analysis['total_available'] += min(available_qty, required_qty)
            
            if available_qty >= required_qty:
                analysis['available_count'] += 1
                analysis['available_materials'].append(material_info)
            else:
                analysis['missing_count'] += 1
                analysis['missing_materials'].append(material_info)
                analysis['all_materials_available'] = False
        
        return analysis
    
    def _build_crafting_plan(self, target_item: str, material_analysis: Dict,
                           craft_data: Dict, knowledge_base) -> Dict:
        """Build a plan for gathering materials and crafting"""
        plan = {
            'target_item': target_item,
            'workshop_type': craft_data.get('skill', 'unknown'),
            'steps': []
        }
        
        # Add gathering steps for missing materials
        for material in material_analysis['missing_materials']:
            if material.get('gatherable'):
                plan['steps'].append({
                    'action': 'gather_resources',
                    'resource': material['code'],
                    'quantity': material['missing'],
                    'sources': material.get('sources', [])
                })
            elif material.get('craftable'):
                plan['steps'].append({
                    'action': 'craft_material',
                    'item': material['code'],
                    'quantity': material['missing'],
                    'workshop': material.get('workshop', 'unknown')
                })
        
        # Add crafting step
        plan['steps'].append({
            'action': 'craft_item',
            'item': target_item,
            'workshop': plan['workshop_type']
        })
        
        return plan
    
    def _determine_state_updates(self, material_analysis: Dict) -> Dict:
        """Determine GOAP state updates based on material analysis"""
        updates = {}
        
        if material_analysis['all_materials_available']:
            updates['materials_sufficient'] = True
            updates['need_resources'] = False
        else:
            updates['materials_sufficient'] = False
            updates['need_resources'] = True
            
            # Set specific resource needs
            for material in material_analysis['missing_materials']:
                if material.get('gatherable'):
                    updates[f'need_{material["code"]}'] = True
        
        return updates
    
    def __repr__(self):
        return "PlanCraftingMaterialsAction()"