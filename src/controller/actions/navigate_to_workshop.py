"""
Navigate to Workshop Action

This bridge action moves the character to a required workshop.
"""

from typing import Dict, Any, Optional, Tuple

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from .base import ActionBase, ActionResult
from .subgoal_mixins import MovementSubgoalMixin


class NavigateToWorkshopAction(ActionBase, MovementSubgoalMixin):
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
        Navigate to the specified workshop using proper subgoal patterns.
        
        Continuation logic:
        - First execution: Find workshop location and request movement  
        - After movement: Verify arrival at workshop
        
        Args:
            client: API client
            context: Action context containing workshop_type and character data
                
        Returns:
            ActionResult with navigation results
        """
        self._context = context
        
        try:
            character_name = context.get(StateParameters.CHARACTER_NAME)
            workshop_type = context.get(StateParameters.WORKSHOP_TYPE)
            
            if not workshop_type:
                return self.create_error_result("No workshop type specified")
            
            # Check for continuation from previous execution
            if self.is_at_target_location(client, context):
                # Continuation: Verify we're at the workshop
                return self._verify_workshop_arrival(client, context, workshop_type)
            
            # Initial execution: Find workshop location and request movement
            self.logger.debug(f"🗺️ Finding location for {workshop_type} workshop")
            
            workshop_location = self._find_workshop_location(workshop_type, context.knowledge_base)
            if not workshop_location:
                return self.create_error_result(f"Could not find {workshop_type} workshop")
            
            target_x, target_y = workshop_location
            
            # Check if already at workshop (before requesting movement)
            from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
            char_response = get_character_api(name=character_name, client=client)
            if char_response and char_response.data:
                current_x = char_response.data.x
                current_y = char_response.data.y
                
                if current_x == target_x and current_y == target_y:
                    self.logger.info(f"✅ Already at {workshop_type} workshop")
                    return self.create_success_result(
                        message=f"Already at {workshop_type} workshop",
                        already_at_workshop=True,
                        workshop_type=workshop_type,
                        location={'x': target_x, 'y': target_y}
                    )
            
            # Request movement subgoal
            self.logger.info(f"🎯 Requesting movement to {workshop_type} workshop at ({target_x}, {target_y})")
            return self.request_movement_subgoal(
                context,
                target_x,
                target_y,
                preserve_keys=['workshop_type']
            )
                
        except Exception as e:
            return self.create_error_result(f"Failed to navigate to workshop: {e}")
    
    def _verify_workshop_arrival(self, client, context: ActionContext, workshop_type: str) -> ActionResult:
        """Verify that we've arrived at the correct workshop."""
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        if target_x is None or target_y is None:
            return self.create_error_result("No target coordinates found for verification")
        
        self.logger.info(f"✅ Arrived at {workshop_type} workshop at ({target_x}, {target_y})")
        return self.create_success_result(
            message=f"Successfully navigated to {workshop_type} workshop",
            moved_to_workshop=True,
            workshop_type=workshop_type,
            location={'x': target_x, 'y': target_y}
        )
    
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