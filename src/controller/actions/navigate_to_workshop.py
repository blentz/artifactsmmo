"""
Navigate to Workshop Action

This bridge action moves the character to a required workshop.
"""

from typing import Dict, Any, Optional, Tuple

from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult
from .move import MoveAction


class NavigateToWorkshopAction(ActionBase):
    """
    Bridge action to navigate character to a specific workshop.
    
    This action finds the workshop location and moves the character there
    if they're not already at the workshop.
    """
    
    # GOAP parameters
    conditions = {
        'character_status': {
            'alive': True,
            'cooldown_active': False
        }
    }
    reactions = {
        'at_workshop': True
    }
    weight = 1.0
    
    def __init__(self):
        """Initialize navigate to workshop action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Navigate to the specified workshop.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - workshop_type: Type of workshop to navigate to
                - knowledge_base: Knowledge base instance
                - map_state: Map state instance
                
        Returns:
            Dict with navigation results
        """
        self._context = context
        
        try:
            character_name = context.character_name
            workshop_type = context.get('workshop_type')
            
            if not workshop_type:
                return self.create_error_result("No workshop type specified")
            
            self.logger.debug(f"🗺️ Navigating to {workshop_type} workshop")
            
            # Check current location
            from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
            
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return self.create_error_result("Could not get character location")
            
            current_x = char_response.data.x
            current_y = char_response.data.y
            
            # Find workshop location
            workshop_location = self._find_workshop_location(workshop_type, context.knowledge_base)
            
            if not workshop_location:
                return self.create_error_result(f"Could not find {workshop_type} workshop")
            
            target_x, target_y = workshop_location
            
            # Check if already at workshop
            if current_x == target_x and current_y == target_y:
                self.logger.info(f"✅ Already at {workshop_type} workshop")
                return self.create_success_result(
                    message=f"Already at {workshop_type} workshop",
                    already_at_workshop=True,
                    workshop_type=workshop_type,
                    location={'x': target_x, 'y': target_y}
                )
            
            # Move to workshop
            move_action = MoveAction()
            move_context = ActionContext(
                character_name=character_name,
                action_data={'x': target_x, 'y': target_y},
                knowledge_base=context.knowledge_base,
                map_state=context.map_state
            )
            
            move_result = move_action.execute(client, move_context)
            
            if move_result and move_result.success:
                self.logger.info(f"✅ Moved to {workshop_type} workshop at ({target_x}, {target_y})")
                return self.create_success_result(
                    message=f"Moved to {workshop_type} workshop",
                    moved_to_workshop=True,
                    workshop_type=workshop_type,
                    location={'x': target_x, 'y': target_y}
                )
            else:
                return self.create_error_result(f"Failed to move to {workshop_type} workshop")
                
        except Exception as e:
            return self.create_error_result(f"Failed to navigate to workshop: {e}")
    
    def _find_workshop_location(self, workshop_type: str, knowledge_base) -> Optional[Tuple[int, int]]:
        """Find workshop location from knowledge base."""
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
        
        # Search in workshops data
        workshops = knowledge_base.data.get('workshops', {})
        for workshop_code, workshop_data in workshops.items():
            if workshop_type.lower() in workshop_code.lower():
                x = workshop_data.get('x')
                y = workshop_data.get('y')
                if x is not None and y is not None:
                    return (x, y)
        
        # Search in maps data as fallback
        maps = knowledge_base.data.get('maps', {})
        for coords, map_data in maps.items():
            content = map_data.get('content', {})
            if content.get('type') == 'workshop' and workshop_type.lower() in content.get('code', '').lower():
                try:
                    x, y = map(int, coords.split(','))
                    return (x, y)
                except:
                    continue
        
        return None
    
    def __repr__(self):
        return "NavigateToWorkshopAction()"