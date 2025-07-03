""" RestAction module """

from artifactsmmo_api_client.api.my_characters.action_rest_my_name_action_rest_post import sync as rest_character_api

from src.lib.action_context import ActionContext

from .character_base import CharacterActionBase

# Import to support testing with character state
try:
    from src.game.character.state import CharacterState
except ImportError:
    # Handle import for testing scenarios
    CharacterState = None

class RestAction(CharacterActionBase):
    """ Rest action for recovering HP when character is critically low """
    
    # GOAP parameters - removed, now defined in actions.yaml

    def __init__(self):
        """
        Initialize rest action.
        """
        super().__init__()

    def execute(self, client, context: 'ActionContext'):
        """ Execute the rest action """
            
        # Get character name from context
        character_name = context.character_name
            
        self.log_execution_start(character_name=character_name)
        
        try:
            response = rest_character_api(
                name=character_name,
                client=client
            )
            
            # Extract HP recovery information
            hp_recovered = 0
            current_hp = 0
            max_hp = 0
            hp_percentage = 0
            
            if hasattr(response, 'data') and response.data:
                response_data = response.data
                
                # Get character data from response
                if hasattr(response_data, 'character') and response_data.character:
                    char_data = response_data.character
                    current_hp = getattr(char_data, 'hp', 0)
                    max_hp = getattr(char_data, 'max_hp', 100)
                    hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
                    
                # Calculate HP recovered if we have previous HP info
                previous_hp = context.get('previous_hp', 0)
                if previous_hp:
                    hp_recovered = current_hp - previous_hp
                    if hp_recovered > 0:
                        self.logger.info(f"💚 Recovered {hp_recovered} HP (now {current_hp}/{max_hp})")
            
            # Return enhanced response with HP tracking
            return self.get_success_response(
                rest_response=response,
                hp_recovered=hp_recovered,
                current_hp=current_hp,
                max_hp=max_hp,
                hp_percentage=hp_percentage
            )
            
        except Exception as e:
            # Handle specific error codes
            error_msg = str(e)
            
            # Check for specific error conditions
            if "Character is in cooldown" in error_msg or "499" in error_msg:
                # Extract cooldown information if available
                cooldown_data = {}
                
                # Try to extract cooldown duration from error response
                if hasattr(e, 'response'):
                    try:
                        # The API might return cooldown info in the error response
                        if hasattr(e.response, 'json') and callable(e.response.json):
                            error_data = e.response.json()
                            if 'detail' in error_data:
                                # Extract cooldown seconds from detail message if present
                                import re
                                match = re.search(r'(\d+(?:\.\d+)?)\s*seconds?', str(error_data['detail']))
                                if match:
                                    cooldown_data['cooldown_seconds'] = float(match.group(1))
                    except:
                        pass
                
                return self.get_error_response(
                    "Rest failed: Character is in cooldown", 
                    is_cooldown=True,
                    **cooldown_data
                )
            elif "Character not found" in error_msg:
                return self.get_error_response("Rest failed: Character not found")
            else:
                return self.get_error_response(f"Rest failed: {error_msg}")

    def __repr__(self):
        return "RestAction()"
