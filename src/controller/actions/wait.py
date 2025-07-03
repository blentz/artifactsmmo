""" WaitAction module """

import time
from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class WaitAction(ActionBase):
    """ Wait action for handling cooldown periods """
    
    # GOAP parameters - consolidated state format
    conditions = {
        "character_status": {
            "cooldown_active": True
        }
    }
    reactions = {
        "character_status": {
            "cooldown_active": False
        }
    }
    weight = 1

    def __init__(self):
        """
        Initialize the wait action.
        """
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """ Execute the wait action - wait for cooldown to expire """
        # Get wait duration from context - this is calculated by GOAP planning
        # GOAP's _handle_cooldown_with_plan_insertion already calculates the exact remaining time
        wait_duration = context.get('wait_duration', 1.0)
        
        self.log_execution_start(wait_duration=wait_duration)
        
        # Trust the wait_duration provided by GOAP planning
        remaining_cooldown = float(wait_duration)
        
        # Clamp to reasonable bounds for safety
        remaining_cooldown = max(0.1, min(remaining_cooldown, 60.0))
        
        try:
            if remaining_cooldown > 0.0:
                self.logger.info(f"Waiting {remaining_cooldown:.1f} seconds for cooldown to expire")
                time.sleep(remaining_cooldown)
            
            success_response = self.get_success_response(
                message=f"Waited {remaining_cooldown:.1f} seconds for cooldown",
                wait_duration=remaining_cooldown,
                cooldown_handled=True
            )
            self.log_execution_result(success_response)
            return success_response
            
        except Exception as e:
            error_response = self.get_error_response(f"Wait failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "WaitAction()"
