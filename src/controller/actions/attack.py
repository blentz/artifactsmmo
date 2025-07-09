""" AttackAction module """

from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as fight_character_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


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
        
        # Get fresh character state to ensure coordinates are current
        character_state = context.character_state
        if character_state and hasattr(character_state, 'refresh'):
            try:
                character_state.refresh(client)
                # Update context coordinates from fresh character state
                if hasattr(character_state, 'data') and character_state.data:
                    context.set(StateParameters.CHARACTER_X, character_state.data.get('x', context.get(StateParameters.CHARACTER_X)))
                    context.set(StateParameters.CHARACTER_Y, character_state.data.get('y', context.get(StateParameters.CHARACTER_Y)))
                    self.logger.debug(f"🔄 Refreshed character position: ({context.get(StateParameters.CHARACTER_X)}, {context.get(StateParameters.CHARACTER_Y)})")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to refresh character state: {e}")
        
        # Get current character coordinates
        character_x = context.character_x
        character_y = context.character_y
        
        # Use knowledge base to get fresh monster data at current location
        knowledge_base = context.knowledge_base
        if knowledge_base and hasattr(knowledge_base, 'get_monster_at_location'):
            try:
                monster_data = knowledge_base.get_monster_at_location(
                    character_x, character_y, client=client
                )
                if not monster_data:
                    self.logger.warning(f"🚫 No monster found at current location ({character_x}, {character_y}) via knowledge base")
                    result = self.create_error_result(
                        f"No monster at location ({character_x}, {character_y}). Monster may have moved or been defeated.",
                        suggestion="Searching for new monster targets",
                        no_monster=True,
                        state_changes={
                            'resource_availability': {'monsters': False},
                            'combat_context': {'status': 'searching'}
                        }
                    )
                    # Request fresh monster search to avoid infinite loop at same location
                    result.request_subgoal(
                        goal_name="find_monsters",
                        parameters={"force_new_search": True, "exclude_location": (character_x, character_y)},
                        preserve_context=[]
                    )
                    return result
                else:
                    monster_code = monster_data.get('code', 'unknown')
                    self.logger.info(f"✅ Confirmed monster '{monster_code}' at ({character_x}, {character_y}) via knowledge base")
            except Exception as e:
                self.logger.warning(f"⚠️ Knowledge base monster check failed: {e}")
                # Fall back to map state scan
                pass
        
        # Fallback: Validate monster presence using map_state scan
        map_state = context.map_state
        if map_state:
            try:
                # Use map_state to scan current location with fresh data
                map_state.scan(character_x, character_y, cache=False)  # Force refresh
                coord_key = f"{character_x},{character_y}"
                
                location_data = map_state.data.get(coord_key, {})
                content = location_data.get('content')
                
                if not content or content.get('type') != 'monster':
                    # No monster at current location
                    self.logger.warning(f"🚫 No monster found at current location ({character_x}, {character_y}) via map scan")
                    result = self.create_error_result(
                        f"No monster at location ({character_x}, {character_y}). Monster may have moved or been defeated.",
                        suggestion="Searching for new monster targets",
                        no_monster=True,
                        state_changes={
                            'resource_availability': {'monsters': False},
                            'combat_context': {'status': 'searching'}
                        }
                    )
                    # Request fresh monster search to avoid infinite loop at same location
                    result.request_subgoal(
                        goal_name="find_monsters",
                        parameters={"force_new_search": True, "exclude_location": (character_x, character_y)},
                        preserve_context=[]
                    )
                    return result
                else:
                    monster_code = content.get('code', 'unknown')
                    self.logger.info(f"✅ Confirmed monster '{monster_code}' at ({character_x}, {character_y}) via map scan")
            except Exception as e:
                self.logger.warning(f"⚠️ Map state scan failed: {e}")
                # Proceed with API call and let it handle the error
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
                
                # If we lost the fight, trigger equipment analysis
                if result == 'loss':
                    self.logger.info(f"💀 Defeated in combat - triggering equipment analysis")
                    # Update reactions to trigger equipment upgrade chain
                    self.reactions = {
                        'combat_context': {
                            'status': 'completed',
                        },
                        'equipment_status': {
                            'upgrade_status': 'needs_analysis',
                        }
                    }
                    
            # Return enhanced response with XP tracking
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
            
            # Check for specific error conditions
            if "Character is in cooldown" in error_msg:
                return self.create_error_result("Attack failed: Character is in cooldown", is_cooldown=True)
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
