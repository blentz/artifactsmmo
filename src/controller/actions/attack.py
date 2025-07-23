""" AttackAction module """
import re

from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as fight_character_api
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class AttackAction(ActionBase):
    """ Attack action for fighting monsters with XP tracking and HP safety """
    
    # GOAP parameters - using flat StateParameters format (architecture-compliant)
    conditions = {
            'combat_context.status': 'ready',
            'character_status.healthy': True,
        }
    reactions = {
            'combat_context.status': 'completed',
        }
    weight = 3.0  # Higher weight since it's a goal action

    def __init__(self):
        """Initialize attack action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """ Execute the attack action """
            
        # Get character name from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        # Get current character coordinates from API (more reliable than context)
        try:
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
            
            character_data = character_response.data
            character_x = getattr(character_data, 'x', None)
            character_y = getattr(character_data, 'y', None)
            
            if character_x is None or character_y is None:
                return self.create_error_result("Character coordinates not available from API")
        except Exception as e:
            return self.create_error_result(f"Failed to get character position: {e}")
        
        
        try:
            self.logger.debug(f"Attempting to attack with character {character_name}")
            response = fight_character_api(
                name=character_name,
                client=client
            )
            self.logger.debug("Fight API call completed successfully")
            
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
                
                # Get combat details from API response (using correct field names)
                turns = fight_data.get('turns', 0)
                combat_logs = fight_data.get('logs', [])
                
                # Get player HP from character data
                current_hp = response.data.character.hp
                max_hp = response.data.character.max_hp
                
                # Get monster name from current location via knowledge base
                char_x = response.data.character.x
                char_y = response.data.character.y
                
                try:
                    location_info = context.knowledge_base.get_location_info(char_x, char_y)
                    if location_info and 'content' in location_info:
                        monster_name = location_info['content']['code']
                    else:
                        self.logger.warning(f"No location info found at ({char_x}, {char_y}), using generic monster name")
                        monster_name = "unknown_monster"
                except AttributeError:
                    self.logger.error("No knowledge_base available in context")
                    monster_name = "unknown_monster"
                except Exception as e:
                    self.logger.error(f"Failed to get location info: {e}")
                    monster_name = "unknown_monster"
                
                # Parse combat logs for damage information
                damage_dealt = 'unknown'
                damage_received = 'unknown'
                blocked_hits = 0
                
                for log_entry in combat_logs:
                    log_str = str(log_entry).lower()
                    if 'dealt' in log_str and 'damage' in log_str:
                        damage_match = re.search(r'dealt (\d+) damage', log_str)
                        if damage_match:
                            damage_value = int(damage_match.group(1))
                            if 'you dealt' in log_str:
                                damage_dealt = damage_value
                            elif 'dealt.*to you' in log_str:
                                damage_received = damage_value
                    elif 'blocked' in log_str:
                        blocked_hits += 1
                
                # Log detailed combat information as requested
                hp_percentage = (current_hp / max_hp * 100)
                self.logger.info(f"⚔️ Combat with {monster_name}: {result} (turns: {turns})")
                self.logger.info(f"💊 Player HP: {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
                if damage_dealt != 'unknown':
                    self.logger.info(f"⚔️ Damage dealt: {damage_dealt}")
                if damage_received != 'unknown':
                    self.logger.info(f"💔 Damage received: {damage_received}")
                if blocked_hits > 0:
                    self.logger.info(f"🛡️ Blocked hits: {blocked_hits}")
                    
                # Log rewards
                if xp_gained > 0:
                    self.logger.info(f"💰 XP gained: {xp_gained}")
                if gold_gained > 0:
                    self.logger.info(f"💰 Gold gained: {gold_gained}")
                if drops:
                    self.logger.info(f"📦 Items dropped: {[drop.get('code', 'unknown') for drop in drops]}")
                
                # If we lost the fight, trigger equipment analysis
                if result == 'loss':
                    self.logger.info(f"💀 Defeated in combat - triggering equipment analysis")
                    # Update reactions to trigger equipment upgrade chain
                    # NOTE: Use 'defeated' status instead of 'completed' so hunt_monsters goal is not satisfied
                    self.reactions = {
                        'combat_context.status': 'defeated',
                        'equipment_status.upgrade_status': 'needs_analysis',
                    }
            
            # Post-combat flow: handle cooldown and HP recovery
            # 1. Check for cooldown from API response
            if response.data:
                character_data = response.data.character
                cooldown_expiration = character_data.cooldown_expiration
                current_hp = character_data.hp
                max_hp = character_data.max_hp
                
                # Handle cooldown if present
                if cooldown_expiration:
                    self.logger.info(f"⏰ Character on cooldown until {cooldown_expiration}")
                    # Create wait subgoal for cooldown
                    result = self.create_success_result(
                        fight_response=response,
                        xp_gained=xp_gained,
                        gold_gained=gold_gained,
                        drops=drops,
                        monster_defeated=monster_defeated
                    )
                    result.request_subgoal(
                        goal_name="wait_for_cooldown",
                        parameters={},
                        preserve_context=[]
                    )
                    return result
                
                # Check HP after combat and create rest subgoal if needed
                if current_hp is not None and max_hp is not None:
                    hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
                    self.logger.info(f"💊 Post-combat HP: {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
                    
                    # If HP is critically low (< 30%), create rest subgoal
                    if hp_percentage < 30.0:
                        self.logger.info(f"🏥 HP critically low after combat - requesting rest")
                        result = self.create_success_result(
                            fight_response=response,
                            xp_gained=xp_gained,
                            gold_gained=gold_gained,
                            drops=drops,
                            monster_defeated=monster_defeated
                        )
                        result.request_subgoal(
                            goal_name="get_healthy",
                            parameters={},
                            preserve_context=[]
                        )
                        return result
            
            # Return enhanced response with XP tracking
            self.logger.debug(f"Attack completed successfully, returning success result")
            return self.create_success_result(
                fight_response=response,
                xp_gained=xp_gained,
                gold_gained=gold_gained,
                drops=drops,
                monster_defeated=monster_defeated
            )
            
        except Exception as e:
            # Handle specific error codes
            error_msg = str(e)
            
            # Check for cooldown error first using ActionBase method
            if self.is_cooldown_error(e):
                return self.handle_cooldown_error()
            elif "Character not found" in error_msg:
                return self.create_error_result("Attack failed: Character not found")
            elif "Monster not found at this location" in error_msg:
                return self.create_error_result("Attack failed: No monster at location", no_monster=True)
            elif "497" in error_msg:
                # Character already at this location
                if "already at this location" in error_msg.lower():
                    return self.create_error_result("Attack failed: Character must be at monster location", wrong_location=True)
            elif "486" in error_msg:
                # Action not allowed  
                if "action is not allowed" in error_msg.lower():
                    return self.create_error_result("Attack failed: Action not allowed", action_not_allowed=True)
            else:
                return self.create_error_result(f"Attack failed: {error_msg}")

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
        char_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        # Higher level characters tend to fight stronger monsters that take longer
        return min(5, max(2, 5 - char_level // 5))  # 2-5 turns based on level

    def __repr__(self):
        return "AttackAction()"
