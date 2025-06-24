""" RestAction module """

from artifactsmmo_api_client.api.my_characters.action_rest_my_name import sync as rest_character_api
import logging

# Import to support testing with character state
try:
    from src.game.character.state import CharacterState
except ImportError:
    # Handle import for testing scenarios
    CharacterState = None

logger = logging.getLogger(__name__)


class RestAction:
    """ Rest action for recovering HP when character is critically low """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self, char_name):
        self.char_name = char_name
        self.critical_hp_threshold = 20  # Rest when HP is below this level
        self.safe_hp_threshold = 50      # Target HP level after resting

    def execute(self, client, character_state=None):
        """ Execute the rest action - recover HP by resting """
        logger.info(f"Executing rest action with character: {self.char_name}")
        
        # Check if rest is needed if character state is provided
        if character_state is not None:
            character_hp = character_state.data.get('hp', 0)
            character_max_hp = character_state.data.get('max_hp', 100)
            
            if not self.should_rest(character_hp, character_max_hp):
                logger.info(f"Rest not needed: HP ({character_hp}/{character_max_hp}) is sufficient")
                return None
        
        response = rest_character_api(
            name=self.char_name,
            client=client
        )
        
        # Log detailed rest results
        if response and hasattr(response, 'data'):
            rest_data = response.data
            
            # Log character stats after rest
            if hasattr(rest_data, 'character'):
                char = rest_data.character
                logger.info(f"Post-rest stats: HP: {char.hp}/{char.max_hp}")
                
                # Check if HP is now at safe levels
                hp_percentage = (char.hp / char.max_hp) * 100 if char.max_hp > 0 else 0
                if hp_percentage >= 80:
                    logger.info(f"Character HP restored to safe levels ({hp_percentage:.1f}%)")
                elif hp_percentage >= 50:
                    logger.info(f"Character HP partially restored ({hp_percentage:.1f}%)")
                else:
                    logger.warning(f"Character HP still low after rest ({hp_percentage:.1f}%)")
            
            # Log rest duration if available
            if hasattr(rest_data, 'cooldown'):
                cooldown_data = rest_data.cooldown
                if hasattr(cooldown_data, 'total_seconds'):
                    logger.info(f"Rest duration: {cooldown_data.total_seconds} seconds")
        
        return response

    def should_rest(self, character_hp, character_max_hp=100):
        """ Check if character should rest based on current HP """
        if character_max_hp <= 0:
            return False
        
        hp_percentage = (character_hp / character_max_hp) * 100
        
        # Rest if HP is below critical threshold
        if hp_percentage < (self.critical_hp_threshold / character_max_hp) * 100:
            logger.info(f"Rest needed: HP ({character_hp}/{character_max_hp}) is critically low")
            return True
        
        return False

    def is_hp_safe(self, character_hp, character_max_hp=100):
        """ Check if character HP is at safe levels """
        if character_max_hp <= 0:
            return False
        
        hp_percentage = (character_hp / character_max_hp) * 100
        return hp_percentage >= (self.safe_hp_threshold / character_max_hp) * 100

    def estimate_rest_time(self, current_hp, target_hp):
        """ Estimate rest time needed (1 second per 5 HP, minimum 3 seconds) """
        hp_to_recover = max(0, target_hp - current_hp)
        estimated_seconds = max(3, hp_to_recover / 5)
        return estimated_seconds

    def __repr__(self):
        return f"RestAction({self.char_name})"