""" 
Architecture-Compliant FindMonstersAction

This action implements the player vs character knowledge pattern:
- Player knowledge: Uses knowledge base to know where monsters are globally  
- Character perception: Character can only "find" monsters at their current location
- Subgoal requests: Requests movement when character needs to get close to monsters

Follows the architectural principle that actions request subgoals instead of 
handling complex logic internally.
"""

from typing import Dict, List, Optional, Tuple
import logging

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.unified_state_context import get_unified_context
from .base import ActionBase, ActionResult


class FindMonstersAction(ActionBase):
    """
    Architecture-compliant action to find monsters using player vs character knowledge pattern.
    
    Player Knowledge: AI system knows monster locations from knowledge base globally
    Character Perception: Character can only "find" monsters at their current location
    Subgoal Pattern: Requests movement subgoals when character needs to get close to monsters
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Find monsters using architecture-compliant player vs character knowledge pattern.
        
        Flow:
        1. Use player knowledge (knowledge base) to identify optimal monster locations
        2. Check if character is at monster location (character perception)  
        3. If not, request movement subgoal to get character close enough
        4. If yes, character "finds" the monsters at current location
        """
        try:
            # Get character's current position from context (character knowledge)
            current_x = context.get(StateParameters.CHARACTER_X)
            current_y = context.get(StateParameters.CHARACTER_Y)
            character_level = context.get(StateParameters.CHARACTER_LEVEL)
            
            if current_x is None or current_y is None or character_level is None:
                return self.create_error_result("Character position/level not available in context")
            
            self.logger.info(f"🔍 Character at ({current_x}, {current_y}) looking for monsters")
            
            # Check if this is a continuation from previous execution (movement completed)
            target_x = getattr(context, 'target_x', None)
            target_y = getattr(context, 'target_y', None)
            
            if target_x is not None and target_y is not None:
                # This is continuation - check if we reached the target
                if current_x == target_x and current_y == target_y:
                    self.logger.info(f"✅ Reached target location ({target_x}, {target_y}) - refreshing location data and validating monster presence")
                    # Character reached target - refresh location data to ensure accuracy
                    context.knowledge_base.refresh_location(current_x, current_y)
                    
                    # Character is now at monster location - proceed with "finding"
                    result = self._character_finds_monsters_at_location(
                        current_x, current_y, character_level, context
                    )
                    
                    # If no monster found at expected location after refresh, clear stale data and restart search
                    if not result.success:
                        self.logger.info("🔄 No monster found at expected location after refresh - adding to failed locations and restarting search")
                        # Track failed location to prevent retrying
                        if not hasattr(context, 'failed_monster_locations'):
                            context.failed_monster_locations = set()
                        context.failed_monster_locations.add((target_x, target_y))
                        # Clear stale target data
                        context.target_x = None
                        context.target_y = None
                        context.target_monster_code = None
                        # Fall through to restart monster search with fresh data
                    else:
                        return result
                else:
                    # Still moving to target, shouldn't happen but handle gracefully
                    self.logger.warning(f"⚠️ Expected to be at ({target_x}, {target_y}) but at ({current_x}, {current_y})")
                    # Fall through to normal logic
            
            # Use player knowledge to find optimal monster location from knowledge base
            # Get list of failed locations to exclude from search
            if not hasattr(context, 'failed_monster_locations'):
                context.failed_monster_locations = set()
            failed_locations = context.failed_monster_locations
            
            optimal_location = self._player_finds_optimal_monster_location(
                current_x, current_y, character_level, context, exclude_locations=failed_locations
            )
            
            if not optimal_location:
                return self.create_error_result(
                    "No suitable monsters found in knowledge base",
                    suggestion="Consider exploring more areas to discover monsters"
                )
                
            monster_x, monster_y, monster_code = optimal_location
            
            # Check if character is already at monster location (character perception)
            if current_x == monster_x and current_y == monster_y:
                self.logger.info(f"🎯 Character already at monster location ({monster_x}, {monster_y}) - refreshing location data to validate")
                # Refresh location data to ensure it's current before claiming success
                context.knowledge_base.refresh_location(current_x, current_y)
                
                result = self._character_finds_monsters_at_location(
                    current_x, current_y, character_level, context
                )
                
                # If no monster found at expected location after refresh, continue searching for alternatives
                if not result.success:
                    self.logger.info("🔄 No monster found at expected location after refresh - adding to failed locations and continuing search")
                    # Track failed location to prevent retrying
                    if not hasattr(context, 'failed_monster_locations'):
                        context.failed_monster_locations = set()
                    context.failed_monster_locations.add((monster_x, monster_y))
                    # Continue to search for other monster locations
                    # Fall through to normal search logic
                else:
                    return result
            
            # Character needs to move to monster location - request movement subgoal
            self.logger.info(f"🚶 Character needs to move from ({current_x}, {current_y}) to ({monster_x}, {monster_y}) to find {monster_code}")
            
            # Set target coordinates AND current character coordinates in UnifiedStateContext for GOAP planning (business logic in action)
            unified_context = get_unified_context()
            unified_context.set(StateParameters.TARGET_X, monster_x)
            unified_context.set(StateParameters.TARGET_Y, monster_y)
            unified_context.set(StateParameters.CHARACTER_X, current_x)
            unified_context.set(StateParameters.CHARACTER_Y, current_y)
            
            # Store target in action context for continuation 
            context.target_x = monster_x
            context.target_y = monster_y  
            context.target_monster_code = monster_code
            
            result = self.create_success_result(f"Need to move to monster location ({monster_x}, {monster_y})")
            result.request_subgoal(
                goal_name="move_to_location",
                parameters={},  # No parameters needed - coordinates set in UnifiedStateContext
                preserve_context=["target_x", "target_y", "target_monster_code"]
            )
            return result
            
        except Exception as e:
            self.logger.error(f"FindMonstersAction failed: {e}")
            return self.create_error_result(f"Failed to find monsters: {str(e)}")

    def _player_finds_optimal_monster_location(
        self, current_x: int, current_y: int, character_level: int, context: ActionContext, exclude_locations: set = None
    ) -> Optional[Tuple[int, int, str]]:
        """
        Use player knowledge (knowledge base) to find optimal monster location.
        
        Player knows about monsters globally but character can only perceive locally.
        Returns (x, y, monster_code) of best monster location or None.
        """
        try:
            # Access knowledge base through context (player knowledge)
            knowledge_base = context.knowledge_base
            if not knowledge_base:
                self.logger.warning("No knowledge base available")
                return None
            
            # Use knowledge base method to find monsters in map
            monsters_found = knowledge_base.find_monsters_in_map(
                character_x=current_x,
                character_y=current_y,
                character_level=character_level,
                level_range=2,  # Allow some challenge
                max_radius=10   # Reasonable search radius
            )
            
            if not monsters_found:
                self.logger.info("No suitable monsters found using knowledge base")
                return None
                
            # Filter out excluded locations if provided
            if exclude_locations:
                original_count = len(monsters_found)
                monsters_found = [m for m in monsters_found if (m['x'], m['y']) not in exclude_locations]
                if len(monsters_found) < original_count:
                    self.logger.info(f"🚫 Filtered out {original_count - len(monsters_found)} failed locations")
                
            if not monsters_found:
                self.logger.info("No suitable monsters found after filtering failed locations")
                return None
                
            # Knowledge base returns sorted list - take the best option
            best_monster = monsters_found[0]
            x = best_monster['x']
            y = best_monster['y']
            monster_code = best_monster['monster_code']
            distance = best_monster['distance']
            
            self.logger.info(f"🎯 Player knowledge: Best monster is {monster_code} at ({x}, {y}), distance: {distance:.1f}")
            return (x, y, monster_code)
            
        except Exception as e:
            self.logger.error(f"Error finding optimal monster location: {e}")
            return None
    
    def _character_finds_monsters_at_location(
        self, x: int, y: int, character_level: int, context: ActionContext
    ) -> ActionResult:
        """
        Character "finds" monsters at their current location (character perception).
        
        This represents what the character can actually perceive from their position.
        """
        try:
            # Access knowledge base through context
            knowledge_base = context.knowledge_base
            
            if not knowledge_base:
                return self.create_error_result(
                    "Knowledge base not available",
                    suggestion="Ensure context contains knowledge_base"
                )
            
            # Check if there are monsters at the current location
            monsters_at_location = knowledge_base.find_monsters_in_map(
                character_x=x,
                character_y=y,
                character_level=character_level,
                max_radius=0  # Only at exact location
            )
            
            if not monsters_at_location:
                return self.create_error_result(
                    f"No monsters found at current location ({x}, {y})",
                    suggestion="Character needs to move to a monster location first"
                )
                
            # Get the first monster at this location
            monster_info = monsters_at_location[0]
            monster_x = monster_info['x']
            monster_y = monster_info['y']
            monster_code = monster_info['monster_code']
            self.logger.info(f"👁️ Character perceives {monster_code} at current location ({x}, {y})")
            
            # Character successfully "finds" the monster at their location
            # Set target monster in unified context for subsequent actions
            unified_context = get_unified_context()
            unified_context.set(StateParameters.TARGET_MONSTER, monster_code)
            unified_context.set(StateParameters.TARGET_X, x)
            unified_context.set(StateParameters.TARGET_Y, y)
            
            return self.create_success_result(
                f"Found {monster_code} at current location"
            )
            
        except Exception as e:
            self.logger.error(f"Error with character perception: {e}")
            return self.create_error_result(f"Character perception failed: {str(e)}")

    def __repr__(self):
        return "FindMonstersAction(architecture_compliant=True)"