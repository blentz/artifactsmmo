""" AttackAction module """

from artifactsmmo_api_client.api.my_characters.action_fight_my_name import sync as fight_character_api
from .base import ActionBase

# Import to support testing with character state
try:
    from src.game.character.state import CharacterState
except ImportError:
    # Handle import for testing scenarios
    CharacterState = None


class AttackAction(ActionBase):
    """ Attack action for fighting monsters with XP tracking and HP safety """
    
    # GOAP parameters - can be overridden by configuration  
    conditions = {
        'monster_present': True,
        'can_attack': True,
        'character_safe': True,
        'character_alive': True
    }
    reactions = {
        'monster_present': False,  # Monster defeated or fled
        'has_hunted_monsters': True
    }
    weights = {'attack': 3.0}  # Higher weight since it's a goal action

    def __init__(self, char_name):
        super().__init__()
        self.char_name = char_name
        self.min_hp_threshold = 1  # Stop attacking if HP would drop to this level or below

    def execute(self, client, character_state=None, **kwargs):
        """ Execute the attack action - fight the monster at current location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(char_name=self.char_name)
        
        # Perform HP safety check if character state is provided
        if character_state is not None:
            character_hp = character_state.data.get('hp', 0)
            if not self.can_safely_attack(character_hp):
                error_response = self.get_error_response(
                    f"Attack cancelled: HP ({character_hp}) is too low for safe combat",
                    character_hp=character_hp,
                    min_hp_threshold=self.min_hp_threshold
                )
                self.log_execution_result(error_response)
                return error_response
            
            # Check combat viability using knowledge base
            combat_viable = self.check_combat_viability(character_state, **kwargs)
            if not combat_viable:
                error_response = self.get_error_response(
                    "Attack cancelled: Poor win rate against this monster suggests combat is not viable",
                    reason="poor_win_rate"
                )
                self.log_execution_result(error_response)
                return error_response
        
        try:
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
                    self.logger.info(f"Post-attack stats: HP: {char.hp}/{char.max_hp}, XP: {char.xp}")
                    
                    # Check if HP is critically low
                    try:
                        if char.hp <= self.min_hp_threshold:
                            self.logger.warning(f"WARNING: Character HP critically low ({char.hp})")
                    except (TypeError, AttributeError):
                        # Handle case where char.hp is a mock or not a number
                        self.logger.debug("Unable to compare HP for low HP warning")
                
                # Log fight results with monster name
                if hasattr(attack_data, 'fight'):
                    fight = attack_data.fight
                    monster_name = 'unknown monster'
                    
                    # Extract monster name for better logging
                    if hasattr(fight, 'monster'):
                        monster = fight.monster
                        if hasattr(monster, 'code'):
                            monster_name = monster.code
                        elif hasattr(monster, 'name'):
                            monster_name = monster.name
                        elif isinstance(monster, dict):
                            monster_name = monster.get('code') or monster.get('name', 'unknown monster')
                    
                    if hasattr(fight, 'result'):
                        self.logger.info(f"⚔️ Combat vs {monster_name}: {fight.result}")
                    if hasattr(fight, 'xp'):
                        try:
                            if fight.xp > 0:
                                self.logger.info(f"💰 XP gained from {monster_name}: {fight.xp}")
                        except (TypeError, AttributeError):
                            # Handle case where fight.xp is a mock or not a number
                            self.logger.debug("Unable to compare XP for logging")
            
            self.log_execution_result(response)
            return response
            
        except Exception as e:
            error_str = str(e)
            
            # Check if this is a cooldown error (status 499)
            if "499" in error_str and "cooldown" in error_str.lower():
                # This is a cooldown error - should be treated as a temporary failure
                error_response = self.get_error_response(f"Attack failed: {error_str}")
                self.log_execution_result(error_response)
                return error_response
            else:
                # Other errors
                error_response = self.get_error_response(f"Attack failed: {error_str}")
                self.log_execution_result(error_response)
                return error_response

    def check_combat_viability(self, character_state, **kwargs):
        """
        Check if combat is viable based on learned win/loss ratios.
        Returns False if the monster has consistently poor results.
        """
        try:
            # Get current location and monster information
            character_x = character_state.data.get('x', 0)
            character_y = character_state.data.get('y', 0)
            character_level = character_state.data.get('level', 1)
            
            # Try to get knowledge base from context or map_state
            knowledge_base = None
            context = kwargs.get('context', {})
            
            # Look for knowledge base in various places
            if 'knowledge_base' in context:
                knowledge_base = context['knowledge_base']
            elif 'map_state' in context and hasattr(context['map_state'], 'knowledge_base'):
                knowledge_base = context['map_state'].knowledge_base
            elif hasattr(self, 'knowledge_base'):
                knowledge_base = self.knowledge_base
            
            if not knowledge_base:
                # If no knowledge base available, allow combat (default behavior)
                self.logger.debug("No knowledge base available for combat viability check")
                return True
            
            # Get monster at current location from knowledge base or map state
            monster_code = None
            map_state = context.get('map_state')
            if map_state and hasattr(map_state, 'get_content'):
                location_content = map_state.get_content(character_x, character_y)
                if location_content and location_content.get('type') == 'monster':
                    monster_code = location_content.get('code')
            
            if not monster_code:
                # Try to get monster from learning data
                if hasattr(knowledge_base, 'data') and 'monsters' in knowledge_base.data:
                    for code, monster_data in knowledge_base.data['monsters'].items():
                        locations = monster_data.get('locations', [])
                        for loc in locations:
                            if loc.get('x') == character_x and loc.get('y') == character_y:
                                monster_code = code
                                break
                        if monster_code:
                            break
            
            if not monster_code:
                # If we can't identify the monster, allow combat (default behavior)
                self.logger.debug(f"Unable to identify monster at ({character_x}, {character_y})")
                return True
            
            # Check combat history for this monster
            if hasattr(knowledge_base, 'data') and 'monsters' in knowledge_base.data:
                monster_data = knowledge_base.data['monsters'].get(monster_code, {})
                combat_results = monster_data.get('combat_results', [])
                
                if len(combat_results) >= 3:  # Only check if we have sufficient data
                    wins = sum(1 for result in combat_results if result.get('result') == 'win')
                    total_combats = len(combat_results)
                    win_rate = wins / total_combats
                    
                    # If win rate is very poor (less than 10%), consider combat not viable
                    if win_rate < 0.1:
                        self.logger.warning(f"⚠️ Combat not viable: {monster_code} win rate {win_rate:.1%} ({wins}/{total_combats})")
                        self.logger.info(f"💡 Suggestion: Seek better equipment or weaker monsters")
                        return False
                    
                    self.logger.debug(f"Combat viable: {monster_code} win rate {win_rate:.1%} ({wins}/{total_combats})")
                else:
                    self.logger.debug(f"Insufficient combat data for {monster_code} ({len(combat_results)} combats)")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error checking combat viability: {e}")
            # On error, default to allowing combat
            return True

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
