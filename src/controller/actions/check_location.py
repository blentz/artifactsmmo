"""
Check Location Action

This action checks the character's current location and provides spatial context
for planning decisions. Used as a GOAP reaction to determine location state
and update action context with current coordinates.
"""

from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class CheckLocationAction(ActionBase):
    """ Action to check current location and update spatial context """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
            'location_known': True,
            'location_context': {
                'at_target': True,
            },
            'spatial_context_updated': True,
        }
    weights = {"location_known": 1.0}

    def __init__(self):
        """
        Initialize the check location action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Check current location and update spatial context """
        # Get parameters from context
        character_name = context.character_name
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get current character location
            character_response = get_character_api(name=character_name, client=client)
            
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            current_x = getattr(character_data, 'x', 0)
            current_y = getattr(character_data, 'y', 0)
            
            # Get map information if available
            map_state = context.map_state
            location_info = {}
            
            if map_state:
                # Check what's at the current location using available MapState methods
                try:
                    if hasattr(map_state, 'get_location_info'):
                        location_data = map_state.get_location_info(current_x, current_y)
                    elif hasattr(map_state, 'get_location'):
                        location_data = map_state.get_location(current_x, current_y)
                    elif hasattr(map_state, 'get_location_data'):
                        location_data = map_state.get_location_data(current_x, current_y)
                    else:
                        # Fallback - just indicate location is checked
                        location_data = None
                        
                    if location_data:
                        location_info = {
                            'content_type': getattr(location_data, 'content_type', 'unknown'),
                            'content_code': getattr(location_data, 'content_code', ''),
                            'name': getattr(location_data, 'name', ''),
                        }
                except Exception as e:
                    # If map state access fails, continue without location details
                    self.logger.warning(f"Could not access map state: {e}")
                    location_info = {'content_type': 'unknown'}
            
            # Determine location capabilities using knowledge base and config data
            knowledge_base = context.knowledge_base
            config_data = context.get('config_data')
            location_capabilities = self._analyze_location_capabilities(
                location_info, knowledge_base=knowledge_base, config_data=config_data
            )
            
            result = {
                'success': True,
                'character_name': character_name,
                'current_x': current_x,
                'current_y': current_y,
                'location_info': location_info,
                'location_capabilities': location_capabilities,
                'target_x': current_x,  # Set target coordinates to current location
                'target_y': current_y,  # for action context passing
                'at_location': True,
                'location_known': True,
                'spatial_context_updated': True
            }
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Location check failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _analyze_location_capabilities(self, location_info: Dict, knowledge_base=None, **kwargs) -> Dict[str, bool]:
        """
        Analyze what can be done at the current location using API/knowledge base data.
        
        Args:
            location_info: Information about the current location
            knowledge_base: Knowledge base to get workshop/facility data from
            **kwargs: Additional context including config_data
            
        Returns:
            Dictionary of location capabilities
        """
        capabilities = {
            'can_craft': False,
            'can_gather': False,
            'can_deposit': False,
            'can_withdraw': False,
            'is_workshop': False,
            'is_resource': False,
            'is_bank': False
        }
        
        content_type = location_info.get('content_type', '').lower()
        content_code = location_info.get('content_code', '').lower()
        
        # Check for workshop capabilities using API/knowledge base data
        if self._is_workshop_location(content_type, content_code, knowledge_base, kwargs.get('config_data')):
            capabilities['can_craft'] = True
            capabilities['is_workshop'] = True
        
        # Check for resource capabilities
        if content_type in ['resource', 'monster']:
            capabilities['can_gather'] = True
            capabilities['is_resource'] = True
        
        # Check for bank capabilities
        if content_type == 'bank' or 'bank' in content_code:
            capabilities['can_deposit'] = True
            capabilities['can_withdraw'] = True
            capabilities['is_bank'] = True
        
        return capabilities
    
    def _is_workshop_location(self, content_type: str, content_code: str, knowledge_base=None, config_data=None) -> bool:
        """
        Determine if a location is a workshop using API/knowledge base data.
        
        Args:
            content_type: Type of content at the location
            content_code: Code of the content at the location
            knowledge_base: Knowledge base to get workshop data from
            config_data: Configuration data for fallback patterns
            
        Returns:
            True if location is a workshop, False otherwise
        """
        # Primary check: content type indicates workshop
        if content_type == 'workshop':
            return True
            
        # Try to get workshop information from knowledge base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # Check if content_code exists in workshops data
            workshops = knowledge_base.data.get('workshops', {})
            if content_code in workshops:
                return True
                
            # Check maps data for workshop-type locations
            maps = knowledge_base.data.get('maps', {})
            for location_key, location_data in maps.items():
                if location_data.get('content', {}).get('code') == content_code:
                    if location_data.get('content', {}).get('type') == 'workshop':
                        return True
        
        # Fallback to knowledge base scanning if no API data available
        workshop_patterns = self._get_workshop_patterns(config_data, knowledge_base)
        return any(pattern in content_code for pattern in workshop_patterns)
    
    def _get_workshop_patterns(self, config_data=None, knowledge_base=None) -> list:
        """
        Get workshop patterns by scanning knowledge base for all known workshops.
        
        Args:
            config_data: Configuration data (unused, maintained for compatibility)
            knowledge_base: Knowledge base to scan for workshop codes
            
        Returns:
            List of workshop patterns to match against
        """
        # Scan knowledge base for all known workshops
        if knowledge_base and hasattr(knowledge_base, 'data'):
            workshops = knowledge_base.data.get('workshops', {})
            if workshops:
                # Extract all workshop codes from knowledge base
                return list(workshops.keys())
        
        # Return empty list if no workshops found in knowledge base
        return []

    def __repr__(self):
        return "CheckLocationAction()"