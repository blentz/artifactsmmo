""" WaitAction module """

import time
from datetime import datetime, timezone
from .base import ActionBase


class WaitAction(ActionBase):
    """ Wait action for handling cooldown periods """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'character_alive': True,
        'is_on_cooldown': True
    }
    reactions = {
        'is_on_cooldown': False,
        'can_move': True,
        'can_attack': True
    }
    weights = {'wait': 0.1}  # Lowest priority - only when we have to wait

    def __init__(self, wait_duration: float = 1.0):
        """
        Initialize the wait action.
        
        Args:
            wait_duration: Duration to wait in seconds (default: 1.0)
        """
        super().__init__()
        self.wait_duration = wait_duration

    def execute(self, client, character_state=None, **kwargs):
        """ Execute the wait action - wait for cooldown to expire """
        self.log_execution_start(wait_duration=self.wait_duration)
        
        # Check if we have character state with cooldown information
        remaining_cooldown = self.wait_duration
        
        if character_state is not None:
            char_data = character_state.data
            cooldown_seconds = char_data.get('cooldown', 0)
            cooldown_expiration = char_data.get('cooldown_expiration', None)
            
            if cooldown_seconds > 0:
                if cooldown_expiration:
                    try:
                        if isinstance(cooldown_expiration, str):
                            cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
                        else:
                            cooldown_end = cooldown_expiration
                        
                        current_time = datetime.now(timezone.utc)
                        if current_time < cooldown_end:
                            remaining_cooldown = (cooldown_end - current_time).total_seconds()
                            # Clamp to reasonable bounds
                            remaining_cooldown = max(0.1, min(remaining_cooldown, 60.0))
                        else:
                            # Cooldown has already expired, no need to wait
                            remaining_cooldown = 0.0
                            
                    except Exception as e:
                        self.logger.warning(f"Error parsing cooldown for wait: {e}")
                        remaining_cooldown = min(cooldown_seconds, 60.0)
                else:
                    # Use cooldown seconds directly if no expiration time
                    remaining_cooldown = min(cooldown_seconds, 60.0)
            else:
                # No cooldown, use minimum wait
                remaining_cooldown = 0.1
        
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
        return f"WaitAction(duration={self.wait_duration})"