"""
Check Inventory Action

This action checks the character's inventory for specific items and quantities,
updating world state accordingly. Used as a GOAP reaction to determine if
sufficient materials are available for crafting.
"""

from typing import Any, Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class CheckInventoryAction(ActionBase):
    """ Action to check inventory for specific items and update world state """

    # GOAP parameters
    conditions = {"character_alive": True}
    reactions = {
        "has_crafting_materials": True, 
        "materials_sufficient": True,
        "has_raw_materials": True,
        "has_refined_materials": True,
        "inventory_updated": True
    }
    weights = {"inventory_updated": 1.0}

    def __init__(self):
        """
        Initialize the check inventory action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Check inventory for required items and update world state """
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_name = context.character_name
        required_items = context.get('required_items', [])
        
        # Handle both single string and list formats for required_items
        if isinstance(required_items, str):
            required_items = [{'item_code': required_items, 'quantity': 1}]
        elif isinstance(required_items, list) and len(required_items) > 0 and isinstance(required_items[0], str):
            required_items = [{'item_code': item, 'quantity': 1} for item in required_items]
            
        self.log_execution_start(character_name=character_name, required_items=required_items)
        
        try:
            # Get current character inventory
            inventory_dict = self._get_character_inventory(client, character_name)
            
            # Check for specific required items if provided
            item_checks = {}
            if required_items:
                for item_req in required_items:
                    item_code = item_req.get('item_code')
                    required_qty = item_req.get('quantity', 1)
                    current_qty = inventory_dict.get(item_code, 0)
                    
                    has_sufficient = current_qty >= required_qty
                    item_checks[item_code] = {
                        'required': required_qty,
                        'current': current_qty,
                        'sufficient': has_sufficient
                    }
                    
                    self.logger.info(f"📦 {item_code}: {current_qty}/{required_qty} {'✅' if has_sufficient else '❌'}")
            
            # Analyze inventory for common material categories using API/knowledge base data
            knowledge_base = context.knowledge_base
            config_data = context.get('config_data')
            inventory_analysis = self._analyze_inventory_categories(inventory_dict, knowledge_base, config_data)
            
            # Update world state based on findings
            world_state_updates = self._determine_world_state_updates(item_checks, inventory_analysis)
            
            result = {
                'success': True,
                'inventory': inventory_dict,
                'item_checks': item_checks,
                'inventory_analysis': inventory_analysis,
                'world_state_updates': world_state_updates,
                'total_items': len([k for k, v in inventory_dict.items() if v > 0]),
                'inventory_summary': self._create_inventory_summary(inventory_dict),
                # Add inventory_status for compatibility with transform_raw_materials
                'inventory_status': {item: {'available': qty} for item, qty in inventory_dict.items()}
            }
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Inventory check failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _get_character_inventory(self, client, character_name: str) -> Dict[str, int]:
        """
        Get character inventory as a dictionary of item_code -> quantity.
        """
        try:
            character_response = get_character_api(name=character_name, client=client)
            
            if not character_response or not character_response.data:
                return {}
            
            inventory = character_response.data.inventory or []
            inventory_dict = {}
            
            for item in inventory:
                # Handle both dict and InventorySlot object formats
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
            
        except Exception as e:
            self.logger.warning(f"Could not get character inventory: {e}")
            return {}

    def _analyze_inventory_categories(self, inventory_dict: Dict[str, int], knowledge_base=None, config_data=None) -> Dict[str, Any]:
        """
        Analyze inventory for different material categories using API/knowledge base data.
        """
        analysis = {
            'raw_materials': {},
            'refined_materials': {},
            'crafted_items': {},
            'consumables': {},
            'other': {}
        }
        
        for item_code, quantity in inventory_dict.items():
            category = self._categorize_item(item_code, knowledge_base, config_data)
            analysis[category][item_code] = quantity
        
        return analysis

    def _categorize_item(self, item_code: str, knowledge_base=None, config_data=None) -> str:
        """
        Categorize an item based on its properties from knowledge base or API data.
        
        Args:
            item_code: Code of the item to categorize
            knowledge_base: Knowledge base to get item data from
            config_data: Configuration data for fallback patterns
            
        Returns:
            Category string: 'raw_materials', 'refined_materials', 'crafted_items', 'consumables', or 'other'
        """
        # Try to get item information from knowledge base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            items = knowledge_base.data.get('items', {})
            if item_code in items:
                item_data = items[item_code]
                return self._categorize_from_item_data(item_code, item_data)
        
        # Try to get item information from resources data
        if knowledge_base and hasattr(knowledge_base, 'data'):
            resources = knowledge_base.data.get('resources', {})
            if item_code in resources:
                # Items found in resources are typically raw materials
                return 'raw_materials'
        
        # Fallback to pattern-based categorization if no API data available
        return self._categorize_by_patterns(item_code, config_data)

    def _categorize_from_item_data(self, item_code: str, item_data: Dict) -> str:
        """
        Categorize item based on API item data.
        
        Args:
            item_code: Code of the item
            item_data: Item data from knowledge base/API
            
        Returns:
            Category string
        """
        item_type = item_data.get('item_type', '').lower()
        craft_data = item_data.get('craft_data')
        
        # Check if it's equipment (crafted items)
        equipment_types = ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'ring', 'amulet', 'shield']
        if item_type in equipment_types:
            return 'crafted_items'
        
        # Check if it's consumable
        consumable_types = ['consumable', 'food', 'potion']
        if item_type in consumable_types or 'consumable' in item_type:
            return 'consumables'
        
        # Check if it has crafting data (indicates it's refined/processed)
        if craft_data:
            # Items that require crafting are refined materials or crafted items
            # If it's not equipment, it's likely a refined material
            if item_type not in equipment_types:
                return 'refined_materials'
            else:
                return 'crafted_items'
        
        # Check if it's a resource type (raw materials)
        if item_type in ['resource', 'ore', 'wood', 'stone']:
            return 'raw_materials'
        
        # If we can't determine from API data, fall back to patterns
        return self._categorize_by_patterns(item_code)

    def _categorize_by_patterns(self, item_code: str, config_data=None) -> str:
        """
        Fallback categorization using YAML-configured patterns.
        Only used when API/knowledge base data is not available.
        
        Args:
            item_code: Code of the item to categorize
            config_data: Configuration data to get patterns from
            
        Returns:
            Category string
        """
        # Try to get patterns from configuration
        if config_data and hasattr(config_data, 'data'):
            patterns_config = config_data.data.get('inventory_categorization_patterns', {})
            
            for category, patterns in patterns_config.items():
                if any(pattern in item_code for pattern in patterns):
                    return category
        
        # Minimal hardcoded fallback if configuration is not available
        if any(pattern in item_code for pattern in ['_ore', '_rocks', '_tree', '_wood', '_spot']):
            return 'raw_materials'
        elif any(pattern in item_code for pattern in ['copper', 'iron', 'coal', 'gold', '_plank']):
            return 'refined_materials'
        elif any(pattern in item_code for pattern in ['_dagger', '_sword', '_staff', '_helmet', '_armor']):
            return 'crafted_items'
        elif any(pattern in item_code for pattern in ['potion', 'food', 'raw_', 'cooked_']):
            return 'consumables'
        else:
            return 'other'

    def _determine_world_state_updates(self, item_checks: Dict, inventory_analysis: Dict) -> Dict[str, bool]:
        """
        Determine world state updates based on inventory analysis.
        """
        updates = {}
        
        # Check if we have raw materials
        has_raw_materials = len(inventory_analysis['raw_materials']) > 0
        updates['has_raw_materials'] = has_raw_materials
        
        # Check if we have refined materials
        has_refined_materials = len(inventory_analysis['refined_materials']) > 0
        updates['has_refined_materials'] = has_refined_materials
        
        # Check if all required items are sufficient
        if item_checks:
            materials_sufficient = all(check['sufficient'] for check in item_checks.values())
            updates['materials_sufficient'] = materials_sufficient
            updates['has_crafting_materials'] = materials_sufficient
        else:
            # If no specific requirements, consider sufficient if we have any materials
            updates['has_crafting_materials'] = has_raw_materials or has_refined_materials
        
        # Update inventory state
        updates['inventory_updated'] = True
        
        return updates

    def _create_inventory_summary(self, inventory_dict: Dict[str, int]) -> str:
        """
        Create a human-readable inventory summary.
        """
        if not inventory_dict:
            return "Empty inventory"
        
        items = []
        for item_code, quantity in sorted(inventory_dict.items()):
            items.append(f"{item_code}({quantity})")
        
        return f"{len(items)} items: {', '.join(items[:5])}" + ("..." if len(items) > 5 else "")

    def __repr__(self):
        return "CheckInventoryAction()"