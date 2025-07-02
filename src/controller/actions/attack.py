""" AttackAction module """

from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as fight_character_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class AttackAction(ActionBase):
    """ Attack action for fighting monsters with XP tracking and HP safety """
    
    # GOAP parameters - can be overridden by configuration  
    conditions = {
            'combat_context': {
                'status': 'ready',
            },
            'character_status': {
                'safe': True,
                'alive': True,
            },
        }
    reactions = {
            'combat_context': {
                'status': 'completed',
            },
        }
    weights = {'attack': 3.0}  # Higher weight since it's a goal action

    def __init__(self):
        """Initialize attack action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext'):
        """ Execute the attack action """
            
        # Get character name from context
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            response = fight_character_api(
                name=character_name,
                client=client
            )
            
            # Extract fight data if present
            fight_data = None
            if hasattr(response, 'data') and response.data:
                response_data = response.data
                if hasattr(response_data, 'fight') and response_data.fight:
                    fight_data = response_data.fight.to_dict()
            
            # Check XP gains
            xp_gained = 0
            drops = []
            gold_gained = 0
            monster_defeated = False
            
            if fight_data:
                xp_gained = fight_data.get('xp', 0)
                drops = fight_data.get('drops', [])
                gold_gained = fight_data.get('gold', 0)
                result = fight_data.get('result', 'unknown')
                monster_defeated = result == 'win'
                
                # Log detailed results
                self.logger.info(f"⚔️ Combat result: {result}")
                if xp_gained > 0:
                    self.logger.info(f"💰 XP gained: {xp_gained}")
                if gold_gained > 0:
                    self.logger.info(f"💰 Gold gained: {gold_gained}")
                if drops:
                    self.logger.info(f"📦 Items dropped: {[drop.get('code', 'unknown') for drop in drops]}")
                    
            # Return enhanced response with XP tracking
            return self.get_success_response(
                fight_response=response,
                xp_gained=xp_gained,
                gold_gained=gold_gained,
                drops=drops,
                monster_defeated=monster_defeated
            )
            
        except Exception as e:
            # Handle specific error codes
            error_msg = str(e)
            
            # Check for specific error conditions
            if "Character is in cooldown" in error_msg:
                return self.get_error_response("Attack failed: Character is in cooldown", is_cooldown=True)
            elif "Character not found" in error_msg:
                return self.get_error_response("Attack failed: Character not found")
            elif "Monster not found at this location" in error_msg:
                return self.get_error_response("Attack failed: No monster at location", no_monster=True)
            elif "497" in error_msg:
                # Character already at this location
                if "already at this location" in error_msg.lower():
                    return self.get_error_response("Attack failed: Character must be at monster location", wrong_location=True)
            elif "486" in error_msg:
                # Action not allowed  
                if "action is not allowed" in error_msg.lower():
                    return self.get_error_response("Attack failed: Action not allowed", action_not_allowed=True)
            else:
                return self.get_error_response(f"Attack failed: {error_msg}")

    def estimate_fight_duration(self, context: 'ActionContext', monster_data=None):
        """
        Estimate how long a fight will take based on character and monster stats.
        
        Args:
            context: ActionContext with character information
            monster_data: Optional monster data for more accurate estimates
            
        Returns:
            Estimated number of turns
        """
        # If we have specific monster data, use it for accurate calculation
        if monster_data:
            monster_hp = monster_data.get('hp', 50)
            # Very simplified damage calculation - assumes ~10 damage per turn
            estimated_player_damage = 10
            return max(1, monster_hp // estimated_player_damage)
        
        # Default estimate based on character level
        char_level = getattr(context, 'character_level', None) or context.get('character_level', 1)
        # Higher level characters tend to fight stronger monsters that take longer
        return min(5, max(2, 5 - char_level // 5))  # 2-5 turns based on level

    def __repr__(self):
        return "AttackAction()"
