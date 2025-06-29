""" FindWorkshopsAction module """

from typing import Dict, Optional
from .search_base import SearchActionBase


class FindWorkshopsAction(SearchActionBase):
    """ Action to find the nearest workshop location """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True}
    reactions = {"workshops_discovered": True, "at_target_location": False}
    weights = {"workshops_discovered": 15}

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 5,
                 workshop_type: Optional[str] = None):
        """
        Initialize the find workshops action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            search_radius: Radius to search for workshops
            workshop_type: Type of workshop to search for (e.g., 'weaponcrafting', 'gearcrafting')
        """
        super().__init__(character_x, character_y, search_radius)
        self.workshop_type = workshop_type

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest workshop location using unified search algorithm """
        self.log_execution_start(
            character_x=self.character_x,
            character_y=self.character_y, 
            search_radius=self.search_radius,
            workshop_type=self.workshop_type
        )
        
        try:
            # Create workshop filter using the unified search base
            workshop_filter = self.create_workshop_filter(workshop_type=self.workshop_type)
            
            # Define result processor for workshop-specific response format
            def workshop_result_processor(location, content_code, content_data):
                x, y = location
                distance = self._calculate_distance(x, y)
                return self.get_success_response(
                    location=location,
                    distance=distance,
                    workshop_code=content_code,
                    workshop_name=content_code,
                    workshop_type=self.workshop_type or 'general'
                )
            
            # Get map_state from context for cached access
            map_state = kwargs.get('map_state')
            
            # Use unified search algorithm
            result = self.unified_search(client, workshop_filter, workshop_result_processor, map_state)
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Workshop search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response


    
    
    

    def __repr__(self):
        workshop_filter = f", type={self.workshop_type}" if self.workshop_type else ""
        return (f"FindWorkshopsAction({self.character_x}, {self.character_y}, "
               f"radius={self.search_radius}{workshop_filter})")