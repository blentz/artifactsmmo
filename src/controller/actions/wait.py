""" WaitAction module """

import time
from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from src.lib.action_context import ActionContext
from src.lib.unified_state_context import UnifiedStateContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class WaitAction(ActionBase):
    """ Wait action for handling cooldown periods """
    
    # GOAP parameters - flat StateParameters format
    conditions = {
        "character_status.cooldown_active": True
    }
    reactions = {
        "character_status.cooldown_active": False
    }
    weight = 0.1  # Low weight as specified in default_actions.yaml

    def __init__(self):
        """
        Initialize the wait action.
        """
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """ Execute the wait action - wait for cooldown to expire """
        self._context = context
        
        # Get character name for API call
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name available")
            
        try:
            # Get current character data from API to get actual cooldown
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data from API")
            
            # Get cooldown from API response
            cooldown_seconds = getattr(character_response.data, 'cooldown', 1.0)
            remaining_cooldown = float(cooldown_seconds)
            
            # Clamp to reasonable bounds for safety
            remaining_cooldown = max(0.1, min(remaining_cooldown, 60.0))
            
            if remaining_cooldown > 0.0:
                self.logger.info(f"Waiting {remaining_cooldown:.1f} seconds for cooldown to expire")
                time.sleep(remaining_cooldown)
            
            return self.create_success_result(
                message=f"Waited {remaining_cooldown:.1f} seconds for cooldown",
                wait_duration=remaining_cooldown,
                cooldown_handled=True
            )
            
        except Exception as e:
            return self.create_error_result(f"Wait failed: {str(e)}")

    def __repr__(self):
        return "WaitAction()"
