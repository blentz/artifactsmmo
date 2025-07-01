""" FindCorrectWorkshopAction module """

from typing import Dict, Optional, Tuple

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api

from src.lib.action_context import ActionContext

from .find_workshops import FindWorkshopsAction
from .move import MoveAction


class FindCorrectWorkshopAction(FindWorkshopsAction):
    """ Action to find the correct workshop type for a specific item """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True}
    reactions = {"at_correct_workshop": True, "workshops_discovered": True}
    weights = {"at_correct_workshop": 20}

    def __init__(self):
        """
        Initialize the find correct workshop action.
        """
        # Don't set workshop_type yet - we'll determine it from the item
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Find the correct workshop for the specified item and move there """        
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        search_radius = context.get('search_radius', 10)
        item_code = context.get('item_code')
        character_name = context.character_name
        
        # Parameters will be passed directly to helper methods via context
            
        if not item_code:
            return self.get_error_response("No item code specified")
            
        self.log_execution_start(
            character_x=character_x,
            character_y=character_y, 
            search_radius=search_radius,
            item_code=item_code
        )
        
        try:
            # 1. Look up item details to determine required workshop type
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return self.get_error_response(f'Could not get details for item {item_code}')
            
            item_data = item_response.data
            required_skill = None
            
            if hasattr(item_data, 'craft') and item_data.craft:
                required_skill = getattr(item_data.craft, 'skill', None)
            
            if not required_skill:
                return self.get_error_response(f'Item {item_code} does not have crafting information')
            
            # 2. Skills and workshops have identical names, so direct assignment
            required_workshop = required_skill
            
            # 3. Set the workshop type and search for it
            self.workshop_type = required_workshop
            
            # Create workshop filter for the specific type
            workshop_filter = self.create_workshop_filter(workshop_type=required_workshop)
            
            # Define result processor for workshop-specific response format
            def workshop_result_processor(location, content_code, content_data):
                x, y = location
                distance = self._calculate_distance(character_x, character_y, x, y)
                return {
                    'success': True,
                    'location': location,
                    'distance': distance,
                    'workshop_code': content_code,
                    'workshop_type': required_workshop,
                    'required_skill': required_skill,
                    'item_code': item_code,
                    'target_x': x,
                    'target_y': y
                }
            
            # 4. Get map_state and knowledge_base from context for cached access
            map_state = context.map_state
            knowledge_base = context.knowledge_base
            
            # Store map_state for use in helper methods
            self._map_state_context = map_state
            
            # 5. First try to find workshop in knowledge base (previously discovered workshops)
            known_workshop = self._search_knowledge_base_for_workshop(knowledge_base, required_workshop, character_x, character_y)
            if known_workshop:
                location = (known_workshop['x'], known_workshop['y'])
                result = workshop_result_processor(location, known_workshop['code'], known_workshop)
                self.logger.info(f"Found {required_workshop} workshop in knowledge base at {location}")
            else:
                # 6. Use unified search algorithm to discover new workshops
                result = self.unified_search(client, character_x, character_y, search_radius, workshop_filter, workshop_result_processor, map_state)
            
            if result and result.get('success'):
                # 7. If we found a workshop, move to it if we have character_name
                if character_name and result.get('target_x') is not None:
                    target_x = result['target_x']
                    target_y = result['target_y']
                    
                    # Only move if we're not already there
                    if character_x != target_x or character_y != target_y:
                        move_action = MoveAction()
                        move_context = ActionContext(
                            character_name=character_name,
                            knowledge_base=knowledge_base,
                            map_state=map_state,
                            action_data={'x': target_x, 'y': target_y}
                        )
                        move_result = move_action.execute(client, move_context)
                        
                        # Handle both dict and API response object formats
                        if move_result:
                            if hasattr(move_result, 'data') and move_result.data:
                                # API response object format
                                result['moved_to_workshop'] = True
                                result['move_result'] = f"Moved successfully: {move_result.data}"
                            elif isinstance(move_result, dict) and move_result.get('success'):
                                # Dict format
                                result['moved_to_workshop'] = True
                                result['move_result'] = move_result
                            else:
                                result['moved_to_workshop'] = False
                                move_error = move_result.get('error', 'Unknown move error') if isinstance(move_result, dict) else str(move_result)
                                result['move_error'] = move_error
                        else:
                            result['moved_to_workshop'] = False
                            result['move_error'] = 'Move failed - no result'
                    else:
                        result['moved_to_workshop'] = True
                        result['already_at_workshop'] = True
                
                self.log_execution_result(result)
                return result
            else:
                error_msg = f'No {required_workshop} workshop found within radius {search_radius}'
                error_response = self.get_error_response(error_msg)
                error_response.update({
                    'required_skill': required_skill,
                    'required_workshop': required_workshop,
                    'item_code': item_code
                })
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f"Workshop search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _search_knowledge_base_for_workshop(self, knowledge_base, workshop_type: str, character_x: int, character_y: int) -> Optional[Dict]:
        """
        Search the knowledge base and map data for workshops of the required type.
        
        Args:
            knowledge_base: KnowledgeBase instance with learned workshop data
            workshop_type: Type of workshop to search for (e.g., 'weaponcrafting')
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            
        Returns:
            Workshop data dict with location if found, None otherwise
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
            
        workshops = knowledge_base.data.get('workshops', {})
        if not workshops:
            return None
            
        # Search for workshops that match the required type
        for workshop_code, workshop_data in workshops.items():
            if workshop_type.lower() in workshop_code.lower():
                # Check if we have location data for this workshop in the workshop data
                if 'x' in workshop_data and 'y' in workshop_data:
                    # Calculate distance from character
                    distance = self._calculate_distance(character_x, character_y, workshop_data['x'], workshop_data['y'])
                    
                    # Return workshop data with location info
                    return {
                        'code': workshop_code,
                        'x': workshop_data['x'],
                        'y': workshop_data['y'],
                        'distance': distance,
                        'craft_skill': workshop_data.get('craft_skill', workshop_type),
                        'name': workshop_data.get('name', workshop_code)
                    }
                else:
                    # Location not in workshop data, search map data for workshop locations
                    location = self._find_workshop_location_in_map_data(workshop_code)
                    if location:
                        x, y = location
                        distance = self._calculate_distance(character_x, character_y, x, y)
                        
                        return {
                            'code': workshop_code,
                            'x': x,
                            'y': y,
                            'distance': distance,
                            'craft_skill': workshop_data.get('craft_skill', workshop_type),
                            'name': workshop_data.get('name', workshop_code)
                        }
        
        return None
    
    def _find_workshop_location_in_map_data(self, workshop_code: str) -> Optional[Tuple[int, int]]:
        """
        Find workshop location by searching through map data.
        
        Args:
            workshop_code: Workshop code to search for
            
        Returns:
            (x, y) tuple if found, None otherwise
        """
        # Get map state from context (passed via kwargs)
        map_state = getattr(self, '_map_state_context', None)
        if not map_state or not hasattr(map_state, 'data'):
            return None
            
        # Search through all map locations for the workshop
        for coord_key, location_data in map_state.data.items():
            if isinstance(location_data, dict):
                content = location_data.get('content')
                if content and isinstance(content, dict):
                    if content.get('code') == workshop_code:
                        # Found the workshop, extract coordinates
                        x = location_data.get('x')
                        y = location_data.get('y')
                        if x is not None and y is not None:
                            return (x, y)
        
        return None

    def __repr__(self):
        return "FindCorrectWorkshopAction()"