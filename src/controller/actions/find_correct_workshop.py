""" FindCorrectWorkshopAction module """

from typing import Dict, Optional, Tuple

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionResult
from .find_workshops import FindWorkshopsAction
from .mixins.subgoal_mixins import MovementSubgoalMixin


class FindCorrectWorkshopAction(FindWorkshopsAction, MovementSubgoalMixin):
    """ Action to find the correct workshop type for a specific item """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
            },
        }
    reactions = {"at_correct_workshop": True, "workshops_discovered": True}
    weight = 20

    def __init__(self):
        """
        Initialize the find correct workshop action.
        """
        # Don't set workshop_type yet - we'll determine it from the item
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Find the correct workshop for the specified item and move there using subgoal patterns.
        
        Continuation logic:
        - First execution: Find workshop location and request movement
        - After movement: Verify arrival at workshop
        """
        self._context = context
        
        # Check for continuation from movement subgoal
        if self.is_at_target_location(client, context):
            # Continuation: We've arrived at the workshop
            return self._verify_workshop_arrival(context)
        
        # Initial execution: Find workshop and request movement
        character_x = context.get(StateParameters.CHARACTER_X)
        character_y = context.get(StateParameters.CHARACTER_Y)
        search_radius = context.get(StateParameters.SEARCH_RADIUS, 10)
        item_code = context.get(StateParameters.ITEM_CODE) or context.get(StateParameters.TARGET_ITEM)
        character_name = context.get(StateParameters.CHARACTER_NAME)
        
        if not item_code:
            return self.create_error_result("No item code specified")
        
        try:
            # 1. Look up item details to determine required workshop type
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return self.create_error_result(f'Could not get details for item {item_code}')
            
            item_data = item_response.data
            required_skill = None
            
            if hasattr(item_data, 'craft') and item_data.craft:
                required_skill = getattr(item_data.craft, 'skill', None)
            
            if not required_skill:
                return self.create_error_result(f'Item {item_code} does not have crafting information')
            
            # 2. Skills and workshops have identical names, so direct assignment
            required_workshop = required_skill
            
            # Store workshop info for continuation
            context.set_result(StateParameters.REQUIRED_WORKSHOP_TYPE, required_workshop)
            context.set_result(StateParameters.REQUIRED_CRAFT_SKILL, required_skill)
            context.set_result(StateParameters.ITEM_CODE, item_code)
            
            # 3. Set the workshop type and search for it
            self.workshop_type = required_workshop
            
            # Create workshop filter for the specific type
            workshop_filter = self.create_workshop_filter(workshop_type=required_workshop)
            
            # 4. Get map_state and knowledge_base from context for cached access
            map_state = context.map_state
            knowledge_base = context.knowledge_base
            self._map_state_context = map_state
            
            # 5. First try to find workshop in knowledge base
            known_workshop = self._search_knowledge_base_for_workshop(knowledge_base, required_workshop, character_x, character_y)
            if known_workshop:
                target_x, target_y = known_workshop['x'], known_workshop['y']
                self.logger.info(f"Found {required_workshop} workshop in knowledge base at ({target_x}, {target_y})")
            else:
                # 6. Use unified search algorithm to discover new workshops
                def workshop_result_processor(location, content_code, content_data):
                    x, y = location
                    return self.create_success_result(
                        location=location,
                        distance=self._calculate_distance(character_x, character_y, x, y),
                        workshop_code=content_code,
                        workshop_type=required_workshop,
                        target_x=x,
                        target_y=y
                    )
                
                search_result = self.unified_search(client, character_x, character_y, search_radius, workshop_filter, workshop_result_processor, map_state)
                
                if not search_result or not search_result.success:
                    return self.create_error_result(
                        f'No {required_workshop} workshop found within radius {search_radius}',
                        required_skill=required_skill,
                        required_workshop=required_workshop,
                        item_code=item_code
                    )
                
                target_x = search_result.data.get('target_x')
                target_y = search_result.data.get('target_y')
                
                if target_x is None or target_y is None:
                    return self.create_error_result("Workshop found but no coordinates available")
            
            # Check if already at workshop
            if character_x == target_x and character_y == target_y:
                self.logger.info(f"Already at {required_workshop} workshop")
                return self.create_success_result(
                    message=f"Already at {required_workshop} workshop",
                    workshop_code=required_workshop,
                    workshop_type=required_workshop,
                    required_skill=required_skill,
                    item_code=item_code,
                    location=(target_x, target_y),  # For test compatibility
                    target_x=target_x,  # Standardized location parameter
                    target_y=target_y,  # Standardized location parameter
                    distance=0,  # Already at workshop
                    already_at_workshop=True
                )
            
            # Request movement subgoal but include workshop data for testability
            self.logger.info(f"🎯 Requesting movement to {required_workshop} workshop at ({target_x}, {target_y})")
            result = self.request_movement_subgoal(
                context,
                target_x,
                target_y,
                preserve_keys=['required_workshop', 'required_skill', 'item_code']
            )
            
            # Add workshop data to result for consistent testing
            result.data.update({
                'workshop_code': required_workshop,
                'workshop_type': required_workshop,
                'required_skill': required_skill,
                'item_code': item_code,
                'location': (target_x, target_y),  # For test compatibility
                'target_x': target_x,  # Standardized location parameter
                'target_y': target_y,  # Standardized location parameter
                'distance': self._calculate_distance(character_x, character_y, target_x, target_y),
                'already_at_workshop': False
            })
            
            return result
                
        except Exception as e:
            return self.create_error_result(f"Workshop search failed: {str(e)}")
    
    def _verify_workshop_arrival(self, context: ActionContext) -> ActionResult:
        """Verify that we've arrived at the correct workshop."""
        required_workshop = context.get(StateParameters.REQUIRED_WORKSHOP_TYPE)
        required_skill = context.get(StateParameters.REQUIRED_CRAFT_SKILL)
        item_code = context.get(StateParameters.ITEM_CODE)
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        self.logger.info(f"✅ Arrived at {required_workshop} workshop at ({target_x}, {target_y})")
        return self.create_success_result(
            message=f"Successfully found and moved to {required_workshop} workshop",
            workshop_code=required_workshop,
            workshop_type=required_workshop,
            required_skill=required_skill,
            item_code=item_code,
            target_x=target_x,  # Standardized location parameter
            target_y=target_y,  # Standardized location parameter
            moved_to_workshop=True
        )

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