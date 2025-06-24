""" AttackAction module """

from artifactsmmo_api_client.api.my_characters.action_fight_my_name import sync as fight_character_api
import logging

# Import to support testing with character state
try:
    from src.game.character.state import CharacterState
except ImportError:
    # Handle import for testing scenarios
    CharacterState = None

logger = logging.getLogger(__name__)


class AttackAction:
    """ Attack action for fighting monsters with XP tracking and HP safety """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self, char_name):
        self.char_name = char_name
        self.min_hp_threshold = 1  # Stop attacking if HP would drop to this level or below

    def execute(self, client, character_state=None):
        """ Execute the attack action - fight the monster at current location """
        logger.info(f"Executing attack with character: {self.char_name}")
        
        # Perform HP safety check if character state is provided
        if character_state is not None:
            character_hp = character_state.data.get('hp', 0)
            if not self.can_safely_attack(character_hp):
                logger.warning(f"Attack cancelled: HP ({character_hp}) is too low for safe combat")
                return None
        
        response = fight_character_api(
            name=self.char_name,
            client=client
        )
        
        # Log detailed attack results for tracking
        if response and hasattr(response, 'data'):
            attack_data = response.data
            
            # Log character stats after attack
            if hasattr(attack_data, 'character'):
                char = attack_data.character
                logger.info(f"Post-attack stats: HP: {char.hp}/{char.max_hp}, XP: {char.xp}")
                
                # Check if HP is critically low
                try:
                    if char.hp <= self.min_hp_threshold:
                        logger.warning(f"WARNING: Character HP critically low ({char.hp})")
                except (TypeError, AttributeError):
                    # Handle case where char.hp is a mock or not a number
                    logger.debug("Unable to compare HP for low HP warning")
            
            # Log fight results
            if hasattr(attack_data, 'fight'):
                fight = attack_data.fight
                if hasattr(fight, 'result'):
                    logger.info(f"Fight result: {fight.result}")
                if hasattr(fight, 'xp'):
                    try:
                        if fight.xp > 0:
                            logger.info(f"XP gained from fight: {fight.xp}")
                    except (TypeError, AttributeError):
                        # Handle case where fight.xp is a mock or not a number
                        logger.debug("Unable to compare XP for logging")
        
        return response

    def can_safely_attack(self, character_hp, estimated_enemy_damage=0):
        """ Check if it's safe to attack given current HP and estimated enemy damage """
        # For basic safety check without enemy damage, HP must be greater than threshold
        if estimated_enemy_damage == 0:
            return character_hp > self.min_hp_threshold
        
        # Calculate projected HP after taking damage
        projected_hp = character_hp - estimated_enemy_damage
        
        # When considering enemy damage, HP can equal threshold (inclusive)
        return projected_hp >= self.min_hp_threshold

    def is_safe_to_continue(self, character_hp):
        """ Check if it's safe to continue attacking based on HP """
        return character_hp > self.min_hp_threshold

    def detect_victory(self, current_xp, initial_xp, fight_result=None):
        """ Detect if victory occurred through XP gain or fight result """
        xp_gained = current_xp > initial_xp
        result_win = fight_result == 'win'
        
        if xp_gained:
            logger.info(f"Victory detected: XP increased from {initial_xp} to {current_xp}")
        if result_win:
            logger.info("Victory detected: Fight result is 'win'")
            
        return xp_gained or result_win

    def __repr__(self):
        return f"AttackAction({self.char_name})"
