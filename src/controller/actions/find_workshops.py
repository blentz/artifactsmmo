""" FindWorkshopsAction module """

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .coordinate_mixin import CoordinateStandardizationMixin
from .search_base import SearchActionBase


class FindWorkshopsAction(SearchActionBase, CoordinateStandardizationMixin):
    """ Action to find the nearest workshop location """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
            },
        }
    reactions = {
        'workshop_status': {
            'discovered': True
        },
        'location_context': {
            'workshop_known': True
        }
    }
    weights = {"workshops_discovered": 15}

    def __init__(self):
        """
        Initialize the find workshops action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Find the nearest workshop location using unified search algorithm """
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        search_radius = context.get('search_radius', 5)
        workshop_type = context.get('workshop_type')
        
        # Parameters will be passed directly to helper methods via context
        
        self.log_execution_start(
            character_x=character_x,
            character_y=character_y, 
            search_radius=search_radius,
            workshop_type=workshop_type
        )
        
        try:
            # Create workshop filter using the unified search base
            workshop_filter = self.create_workshop_filter(workshop_type=workshop_type)
            
            # Define result processor for workshop-specific response format
            def workshop_result_processor(location, content_code, content_data):
                x, y = location
                distance = abs(x - character_x) + abs(y - character_y)  # Manhattan distance
                
                # Create standardized coordinate response
                coordinate_data = self.create_coordinate_response(
                    x, y,
                    distance=distance,
                    workshop_code=content_code,
                    workshop_name=content_code,
                    workshop_type=workshop_type or 'general'
                )
                
                return self.get_success_response(**coordinate_data)
            
            # Get map_state from context for cached access
            map_state = context.map_state
            
            # Use unified search algorithm
            result = self.unified_search(client, character_x, character_y, search_radius, workshop_filter, workshop_result_processor, map_state)
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Workshop search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response


    
    
    

    def __repr__(self):
        # Handle case where instance variables might not be set
        character_x = getattr(self, 'character_x', 0)
        character_y = getattr(self, 'character_y', 0)
        search_radius = getattr(self, 'search_radius', 5)
        workshop_type = getattr(self, 'workshop_type', None)
        
        workshop_filter = f", type={workshop_type}" if workshop_type else ""
        return (f"FindWorkshopsAction({character_x}, {character_y}, "
               f"radius={search_radius}{workshop_filter})")