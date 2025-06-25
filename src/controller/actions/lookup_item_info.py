""" LookupItemInfoAction module """

from typing import Dict, List, Optional
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
# Note: get_all_items API endpoint not available in current client
from artifactsmmo_api_client.api.resources.get_resource import sync as get_resource_api
# Note: get_all_resources API endpoint not available in current client
from .base import ActionBase


class LookupItemInfoAction(ActionBase):
    """ Action to lookup item information, recipes, and crafting requirements """

    def __init__(self, item_code: Optional[str] = None, search_term: Optional[str] = None, 
                 item_type: Optional[str] = None, max_level: Optional[int] = None):
        """
        Initialize the lookup item info action.

        Args:
            item_code: Specific item code to lookup
            search_term: Search term to find items by name/description
            item_type: Filter by item type (weapon, armor, etc.)
            max_level: Maximum level requirement for items
        """
        super().__init__()
        self.item_code = item_code
        self.search_term = search_term
        self.item_type = item_type
        self.max_level = max_level

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Lookup item information and crafting requirements """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(item_code=self.item_code, search_term=self.search_term)
        
        try:
            if self.item_code:
                # Lookup specific item
                result = self._lookup_specific_item(client, self.item_code)
            else:
                # Search for items matching criteria
                result = self._search_items(client)
            
            self.log_execution_result(result)
            return result
                
        except Exception as e:
            error_response = self.get_error_response(f'Item lookup failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _lookup_specific_item(self, client, item_code: str) -> Dict:
        """ Lookup details for a specific item """
        item_response = get_item_api(code=item_code, client=client)
        
        if not item_response or not item_response.data:
            return {
                'success': False,
                'error': f'Item {item_code} not found'
            }
        
        item_data = item_response.data
        result = {
            'success': True,
            'item_code': item_code,
            'name': getattr(item_data, 'name', ''),
            'description': getattr(item_data, 'description', ''),
            'type': getattr(item_data, 'type', ''),
            'subtype': getattr(item_data, 'subtype', ''),
            'level': getattr(item_data, 'level', 0),
            'tradeable': getattr(item_data, 'tradeable', False)
        }
        
        # Add crafting information if available
        if hasattr(item_data, 'craft') and item_data.craft:
            craft_info = item_data.craft
            result['craftable'] = True
            result['craft_skill'] = getattr(craft_info, 'skill', '')
            result['craft_level'] = getattr(craft_info, 'level', 0)
            result['craft_items'] = []
            
            if hasattr(craft_info, 'items') and craft_info.items:
                for craft_item in craft_info.items:
                    result['craft_items'].append({
                        'code': getattr(craft_item, 'code', ''),
                        'quantity': getattr(craft_item, 'quantity', 0)
                    })
        else:
            result['craftable'] = False
        
        # Add equipment stats if applicable
        if hasattr(item_data, 'effects') and item_data.effects:
            result['effects'] = []
            for effect in item_data.effects:
                result['effects'].append({
                    'name': getattr(effect, 'name', ''),
                    'value': getattr(effect, 'value', 0)
                })
        
        return result

    def _search_items(self, client) -> Dict:
        """ Search for items matching the specified criteria """
        # Note: get_all_items API is not available, so we can't search items
        # This method would need the get_all_items endpoint to be implemented
        return {
            'success': False,
            'error': 'Item search not available - get_all_items API endpoint missing',
            'suggestion': 'Use specific item lookup instead'
        }

    def lookup_crafting_materials(self, client, item_code: str) -> Dict:
        """ Get detailed information about materials needed to craft an item """
        item_info = self._lookup_specific_item(client, item_code)
        
        if not item_info['success'] or not item_info.get('craftable'):
            return {
                'success': False,
                'error': f'Item {item_code} is not craftable or not found'
            }
        
        materials_info = []
        
        for craft_item in item_info.get('craft_items', []):
            material_code = craft_item['code']
            quantity_needed = craft_item['quantity']
            
            # Get detailed info about this material
            material_response = get_item_api(code=material_code, client=client)
            if material_response and material_response.data:
                material_data = material_response.data
                material_info = {
                    'code': material_code,
                    'name': getattr(material_data, 'name', ''),
                    'type': getattr(material_data, 'type', ''),
                    'quantity_needed': quantity_needed,
                    'obtainable_from': []
                }
                
                # Check if it's a resource that can be gathered
                try:
                    resource_response = get_resource_api(code=material_code, client=client)
                    if resource_response and resource_response.data:
                        resource_data = resource_response.data
                        material_info['is_resource'] = True
                        material_info['skill_required'] = getattr(resource_data, 'skill', '')
                        material_info['level_required'] = getattr(resource_data, 'level', 0)
                    else:
                        material_info['is_resource'] = False
                except:
                    material_info['is_resource'] = False
                
                materials_info.append(material_info)
        
        return {
            'success': True,
            'item_code': item_code,
            'item_name': item_info.get('name', ''),
            'craft_skill': item_info.get('craft_skill', ''),
            'craft_level': item_info.get('craft_level', 0),
            'materials': materials_info
        }

    def __repr__(self):
        if self.item_code:
            return f"LookupItemInfoAction({self.item_code})"
        else:
            filters = []
            if self.search_term:
                filters.append(f"search='{self.search_term}'")
            if self.item_type:
                filters.append(f"type='{self.item_type}'")
            if self.max_level is not None:
                filters.append(f"max_level={self.max_level}")
            return f"LookupItemInfoAction({', '.join(filters)})"