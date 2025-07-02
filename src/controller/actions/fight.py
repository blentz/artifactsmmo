"""
Fight Action

This action handles combat with monsters using the consolidated state format
for GOAP planning and execution.
"""

from typing import TYPE_CHECKING, Dict, Optional

from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as fight_character_api

from .base import ActionBase

if TYPE_CHECKING:
    from src.lib.action_context import ActionContext

class FightAction(ActionBase):
    """
    Action to fight monsters using consolidated state format.
    
    This action handles combat encounters, checking combat readiness
    and updating combat status appropriately.
    """

    # GOAP parameters - consolidated state format
    conditions = {
        "combat_context": {
            "status": "ready"
        },
        "character_status": {
            "hp_percentage": ">=15",
            "cooldown_active": False
        }
    }
    reactions = {
        "combat_context": {
            "status": "completed"
        },
        "goal_progress": {
            "steps_completed": 1
        }
    }
    weight = 5

    def __init__(self):
        """Initialize the fight action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """Execute combat with a monster."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        
        self.log_execution_start(character_name=character_name)
        
        try:
            # Execute the fight command
            response = fight_character_api(
                name=character_name,
                client=client
            )
            
            if not response or not response.data:
                return self.get_error_response("Fight command failed - no response data")
                
            fight_data = response.data
            
            # Analyze fight results
            fight_result = self._analyze_fight_result(fight_data)
            
            # Update combat context based on results
            combat_status = "completed" if fight_result['success'] else "failed"
            
            # Create result with consolidated state updates
            result = self.get_success_response(
                combat_context={
                    "status": combat_status,
                    "last_fight_result": fight_result['result'],
                    "experience_gained": fight_result.get('xp_gained', 0),
                    "damage_taken": fight_result.get('damage_taken', 0)
                },
                goal_progress={
                    "steps_completed": 1 if fight_result['success'] else 0
                },
                fight_data=fight_data,
                success=fight_result['success']
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Fight execution failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _analyze_fight_result(self, fight_data) -> Dict:
        """Analyze the fight result data."""
        try:
            # Extract fight information
            fight_result = getattr(fight_data, 'fight', {})
            
            # Determine success based on fight result
            result_type = fight_result.get('result', 'unknown')
            success = result_type in ['win', 'victory']
            
            # Extract XP and damage information
            xp_gained = fight_result.get('xp', 0)
            damage_taken = 0
            
            # Extract character HP changes if available
            character_data = getattr(fight_data, 'character', None)
            if character_data:
                current_hp = getattr(character_data, 'hp', 0)
                max_hp = getattr(character_data, 'max_hp', 100)
                # Estimate damage taken (this is approximate)
                if current_hp < max_hp:
                    damage_taken = max_hp - current_hp
            
            return {
                'success': success,
                'result': result_type,
                'xp_gained': xp_gained,
                'damage_taken': damage_taken,
                'character_hp': getattr(character_data, 'hp', 0) if character_data else 0
            }
            
        except Exception as e:
            self.logger.warning(f"Fight result analysis failed: {e}")
            return {
                'success': False,
                'result': 'error',
                'xp_gained': 0,
                'damage_taken': 0
            }

    def __repr__(self):
        return "FightAction()"