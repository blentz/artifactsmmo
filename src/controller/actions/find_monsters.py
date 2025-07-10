""" FindMonstersAction module """

from typing import Dict, List, Optional

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import CombatStatus, CommonStatus

from .base import ActionResult
from .mixins.coordinate_mixin import CoordinateStandardizationMixin
from .base.search import SearchActionBase


class FindMonstersAction(SearchActionBase, CoordinateStandardizationMixin):
    """ Action to find the nearest map location with specified monsters """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
            'combat_context': {
                'status': CombatStatus.SEARCHING,
            },
            'resource_availability': {
                'monsters': False,
            },
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
            'resource_availability': {
                'monsters': True,
            },
            'combat_context': {
                'status': CombatStatus.READY,
            },
            # location_context.at_target will be set dynamically based on whether movement is needed
        }
    weight = 2.0  # Medium-high priority for exploration

    def __init__(self):
        """
        Initialize the find monsters action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Find the nearest monster location using unified search algorithm """
        # Get parameters from context using StateParameters - direct property access
        character_x = context.get(StateParameters.CHARACTER_X, 0)
        character_y = context.get(StateParameters.CHARACTER_Y, 0)
        search_radius = context.get(StateParameters.SEARCH_RADIUS, 3)
        target_monster = context.get(StateParameters.TARGET_MONSTER, [])
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        level_range = context.get(StateParameters.LEVEL_RANGE, 2)
        
        self._context = context
        
        if client is None:
            return self.create_error_result("No API client provided")
        
        try:
            # Use knowledge base to find monsters from cached map data
            knowledge_base = context.knowledge_base
            map_state = context.map_state
                
            # Find monsters using knowledge base search on cached map data
            found_monsters = knowledge_base.find_monsters_in_map(
                map_state=map_state,
                character_x=character_x,
                character_y=character_y,
                monster_types=target_monster,
                character_level=character_level,
                level_range=level_range,
                max_radius=search_radius
            )
            
            if not found_monsters:
                return self.create_error_result(
                    f"No suitable monsters found in cached map data within radius {search_radius}",
                    max_radius_searched=search_radius,
                    suggestion="Consider map exploration to discover more monsters"
                )
            
            # Select the best monster using existing logic
            result = self._select_best_monster_from_candidates(found_monsters, context)
            
            if not result:
                return self.create_error_result(
                    f"No viable monsters found within radius {search_radius}",
                    max_radius_searched=search_radius,
                    suggestion="Consider map exploration or resource gathering for equipment upgrades"
                )
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Monster search failed: {str(e)}")
    
    def _select_best_monster_from_candidates(self, found_monsters, context: ActionContext):
        """
        Select the best monster from knowledge base candidates.
        
        Priority order:
        1. Lower level monsters (safer for character)
        2. Higher win rates (known successful combat)
        3. Closer distance (efficiency)
        """
        # Extract parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        monster_types = context.get('monster_types', [])
        character_level = context.get('character_level', context.character_level)
        level_range = context.get('level_range', 2)
        search_radius = context.get('search_radius', 2)
        
        knowledge_base = context.knowledge_base
        action_config = context.get('action_config', {})
        viable_monsters = []
        
        # Get exclusion parameters from context
        exclude_location = context.get('exclude_location')
        
        # Process each monster candidate from knowledge base
        for monster_info in found_monsters:
            x, y = monster_info['x'], monster_info['y']
            monster_code = monster_info['monster_code']
            monster_data = monster_info['monster_data']
            distance = monster_info['distance']
            
            # Skip excluded location if specified
            if exclude_location:
                exclude_x, exclude_y = exclude_location
                if x == exclude_x and y == exclude_y:
                    self.logger.debug(f"⏭️ Skipping excluded location ({x}, {y}) with {monster_code}")
                    continue
            
            monster_level = monster_data.get('level', 1)
            
            # Check combat viability with known monster level
            win_rate = self._get_monster_win_rate(monster_code, knowledge_base, 
                                                 action_config=action_config) if knowledge_base else None
            
            # Pass monster level for viability check
            viability_context = {
                'monster_level': monster_level,
                'character_level': character_level,
                'monster_types': monster_types,
                'level_range': level_range,
                'knowledge_base': knowledge_base,
                'action_config': action_config,
                'character_state': getattr(context, 'character_state', None)
            }
            
            if not self._is_combat_viable(monster_code, win_rate, viability_context):
                continue  # Skip non-viable monsters
            
            # Store monster candidate with all selection criteria
            monster_candidate = {
                'location': (x, y),
                'content_code': monster_code,
                'content_data': monster_info['content_data'],
                'distance': distance,
                'monster_level': monster_level,
                'win_rate': win_rate if win_rate is not None else 0.0,
                'x': x,
                'y': y
            }
            viable_monsters.append(monster_candidate)
        
        if not viable_monsters:
            return None
        
        # Select the best monster based on priority criteria
        best_monster_result = self._select_best_monster(viable_monsters)
        
        if best_monster_result and best_monster_result.success:
            # Extract data from ActionResult following ActionContext<->ActionResult pattern
            x = best_monster_result.data['target_x']
            y = best_monster_result.data['target_y']
            content_code = best_monster_result.data['monster_code']
            distance = best_monster_result.data['distance']
            win_rate = best_monster_result.data['win_rate']
            monster_level = best_monster_result.data['monster_level']
            
            win_rate_str = f"{win_rate:.1%}" if win_rate > 0 else CommonStatus.UNKNOWN
            self.logger.info(f"🎯 Selected {content_code} (level {monster_level}) at ({x}, {y}) - distance: {distance:.1f}, win rate: {win_rate_str}")
            
            # Set coordinates directly on ActionContext for unified access
            if hasattr(self, '_context') and self._context:
                self._context.target_x = x
                self._context.target_y = y
                self._context.monster_code = content_code
                self.logger.debug(f"Set target coordinates on ActionContext: ({x}, {y}) for {content_code}")
            
            # Get fresh character position before checking movement needs
            char_x = getattr(self._context, 'character_x', 0)
            char_y = getattr(self._context, 'character_y', 0)
            
            # Refresh character position if possible
            character_state = context.character_state
            if character_state and hasattr(character_state, 'refresh'):
                try:
                    character_state.refresh()  # Get fresh position data
                    if hasattr(character_state, 'data') and character_state.data:
                        char_x = character_state.data.get('x', char_x)
                        char_y = character_state.data.get('y', char_y)
                        # Update context with fresh coordinates
                        self._context.character_x = char_x
                        self._context.character_y = char_y
                        self.logger.debug(f"🔄 Refreshed character position for movement check: ({char_x}, {char_y})")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to refresh character position: {e}")
            
            # Create base result
            result = self.create_success_result(
                distance=distance,
                monster_code=content_code,
                target_codes=[content_code],
                search_radius_used=search_radius,
                win_rate=win_rate,
                found=True,
                target_x=x,
                target_y=y
            )
            
            # Set reactions dynamically based on whether movement is needed
            if char_x != x or char_y != y:
                # Character needs to move - don't set at_target=True yet
                self.logger.info(f"🚶 Character at ({char_x}, {char_y}) needs to move to monster at ({x}, {y})")
                result.request_subgoal(
                    goal_name="move_to_location",
                    parameters={
                        "target_x": x,
                        "target_y": y
                    },
                    preserve_context=["monster_code", "target_x", "target_y"]
                )
                # Set state changes to indicate monsters found but movement needed
                result.state_changes = {
                    'resource_availability': {'monsters': True},
                    'combat_context': {'status': 'ready'},
                    # Don't set at_target=True since movement is needed
                }
            else:
                # Character is already at monster location
                self.logger.info(f"✅ Character already at monster location ({x}, {y})")
                result.state_changes = {
                    'resource_availability': {'monsters': True},
                    'combat_context': {'status': 'ready'},
                    'location_context': {'at_target': True},
                }
            
            return result
        else:
            # Handle error case from _select_best_monster
            if best_monster_result and not best_monster_result.success:
                return best_monster_result  # Return the error ActionResult
        
        return None
    
    def _select_best_monster(self, viable_monsters):
        """
        Select the best monster from viable candidates.
        
        Priority:
        1. Lowest level (safest)
        2. Highest win rate among same level
        3. Closest distance as tiebreaker
        
        Returns:
            ActionResult: Success with monster data or error if no monsters
        """
        if not viable_monsters:
            return self.create_error_result("No viable monsters to select from")
        
        # Sort by level (ascending), then win rate (descending), then distance (ascending)
        sorted_monsters = sorted(viable_monsters, key=lambda m: (
            m['monster_level'],      # Lower level = safer = better
            -m['win_rate'],          # Higher win rate = better (negative for desc sort)
            m['distance']            # Closer distance = better
        ))
        
        best = sorted_monsters[0]
        self.logger.debug(f"Monster selection from {len(viable_monsters)} candidates:")
        for i, monster in enumerate(sorted_monsters[:3]):  # Log top 3 choices
            marker = "👑" if i == 0 else f"{i+1}."
            self.logger.debug(f"  {marker} {monster['content_code']} (lvl {monster['monster_level']}) "
                             f"- win rate: {monster['win_rate']:.1%}, distance: {monster['distance']:.1f}")
        
        # Return ActionResult with monster data following ActionContext<->ActionResult pattern
        return self.create_success_result(
            message=f"Selected {best['content_code']} (level {best['monster_level']}) at ({best['x']}, {best['y']})",
            monster_code=best['content_code'],
            target_x=best['x'],
            target_y=best['y'],
            distance=best['distance'],
            win_rate=best['win_rate'],
            monster_level=best['monster_level'],
            location=best['location']
        )
    
    
    def _is_combat_viable(self, monster_code: str, win_rate: Optional[float], kwargs: Dict) -> bool:
        """Check if combat with this monster is viable based on weighted win rate and combat stats."""
        # Get viability thresholds from knowledge base or configuration
        knowledge_base = kwargs.get('knowledge_base')
        action_config = kwargs.get('action_config', {})
        character_state = kwargs.get('character_state')
        
        # Get minimum win rate from configuration
        min_win_rate = action_config.get('minimum_win_rate', 0.2)
        
        # For known monsters, check win rate (this is from _get_monster_win_rate which uses min_combats)
        if win_rate is not None:
            if win_rate < min_win_rate:
                self.logger.warning(f"🚫 Combat not viable: {monster_code} win rate {win_rate:.1%} is below threshold {min_win_rate:.1%}")
                return False
            return True
        
        # For unknown monsters or those with limited data, check knowledge base
        if knowledge_base and hasattr(knowledge_base, 'data'):
            monsters = knowledge_base.data.get('monsters', {})
            monster_data = monsters.get(monster_code, {})
            
            # If we have any combat data, use weighted recency calculation
            if 'combat_results' in monster_data and len(monster_data['combat_results']) > 0:
                weighted_win_rate = self._calculate_weighted_win_rate(
                    monster_data['combat_results'], 
                    action_config
                )
                
                # Get combat power score adjustment
                combat_power_adjustment = 0.0
                if character_state and hasattr(character_state, 'data'):
                    combat_power_adjustment = self._calculate_combat_power_adjustment(
                        character_state.data,
                        monster_data,
                        action_config
                    )
                
                # Adjust win rate based on combat power
                adjusted_win_rate = weighted_win_rate + combat_power_adjustment
                
                # Log detailed viability assessment
                total_combats = len(monster_data['combat_results'])
                wins = sum(1 for result in monster_data['combat_results'] if result.get('result') == 'win')
                
                if adjusted_win_rate < min_win_rate:
                    self.logger.warning(
                        f"🚫 Combat not viable: {monster_code} has {wins}/{total_combats} wins "
                        f"(weighted: {weighted_win_rate:.1%}, adjusted: {adjusted_win_rate:.1%}) "
                        f"below threshold {min_win_rate:.1%}"
                    )
                    return False
                
                self.logger.info(
                    f"✅ Combat viable: {monster_code} has {wins}/{total_combats} wins "
                    f"(weighted: {weighted_win_rate:.1%}, adjusted: {adjusted_win_rate:.1%})"
                )
                return True
            
            # Check if monster is marked as dangerous in knowledge base
            if monster_data.get('dangerous', False):
                self.logger.warning(f"🚫 Combat not viable: {monster_code} is marked as dangerous")
                return False
        
        # Unknown monster with no data - check if we can determine its level
        character_level = kwargs.get('character_level', 1)
        unknown_monster_max_level = action_config.get('unknown_monster_max_level', 2)
        
        # Try to get monster level from kwargs (passed from _find_best_monster_target)
        monster_level = kwargs.get('monster_level')
        
        if monster_level is not None:
            # We know the monster level, apply strict filtering
            if monster_level > character_level + 1:
                self.logger.warning(f"🚫 Combat not viable: {monster_code} (level {monster_level}) is too high for character level {character_level}")
                return False
            self.logger.info(f"ℹ️ Accepting unknown monster {monster_code} (level {monster_level}) for character level {character_level}")
            return True
        
        # If we still don't know the level, be cautious
        if character_level <= unknown_monster_max_level or not knowledge_base:
            self.logger.info(f"ℹ️ Accepting unknown monster {monster_code} (character level {character_level})")
            return True
        else:
            self.logger.info(f"⏭️ Skipping unknown monster {monster_code} - character level {character_level} exceeds caution threshold")
            return False

    def _calculate_weighted_win_rate(self, combat_results, action_config):
        """Calculate win rate with recency weighting - recent victories weigh higher."""
        if not combat_results:
            return 0.0
        
        # Get recency decay factor from config (default 0.9 means each older combat is worth 90% of the next)
        recency_decay = action_config.get('recency_decay_factor', 0.9)
        
        # Sort combat results by timestamp (most recent first)
        sorted_results = sorted(
            combat_results, 
            key=lambda x: x.get('timestamp', ''), 
            reverse=True
        )
        
        weighted_wins = 0.0
        total_weight = 0.0
        
        for i, result in enumerate(sorted_results):
            # Calculate weight for this combat (most recent = 1.0, older = decaying)
            weight = recency_decay ** i
            total_weight += weight
            
            if result.get('result') == 'win':
                weighted_wins += weight
        
        # Calculate weighted win rate
        weighted_win_rate = weighted_wins / total_weight if total_weight > 0 else 0.0
        
        return weighted_win_rate
    
    def _calculate_combat_power_adjustment(self, character_data, monster_data, action_config):
        """Calculate combat power adjustment based on character vs monster stats."""
        # Get configuration for stat importance
        attack_weight = action_config.get('attack_stat_weight', 0.4)
        defense_weight = action_config.get('defense_stat_weight', 0.3)
        critical_weight = action_config.get('critical_stat_weight', 0.3)
        
        # Get character combat stats
        char_attack = (
            character_data.get('attack_fire', 0) +
            character_data.get('attack_earth', 0) +
            character_data.get('attack_water', 0) +
            character_data.get('attack_air', 0)
        )
        char_defense = (
            character_data.get('res_fire', 0) +
            character_data.get('res_earth', 0) +
            character_data.get('res_water', 0) +
            character_data.get('res_air', 0)
        )
        char_critical = character_data.get('critical_strike', 0)
        char_level = character_data.get('level', 1)
        
        # Get monster combat stats
        monster_attack_stats = monster_data.get('attack_stats', {})
        monster_attack = (
            monster_attack_stats.get('attack_fire', 0) +
            monster_attack_stats.get('attack_earth', 0) +
            monster_attack_stats.get('attack_water', 0) +
            monster_attack_stats.get('attack_air', 0)
        )
        
        monster_resist_stats = monster_data.get('resistance_stats', {})
        monster_defense = (
            monster_resist_stats.get('res_fire', 0) +
            monster_resist_stats.get('res_earth', 0) +
            monster_resist_stats.get('res_water', 0) +
            monster_resist_stats.get('res_air', 0)
        )
        
        monster_level = monster_data.get('level', 1)
        
        # Calculate combat power scores
        # Attack advantage: positive if character has more attack than monster defense
        attack_advantage = (char_attack - monster_defense) / max(char_attack + monster_defense, 1)
        
        # Defense advantage: positive if character has more defense than monster attack
        defense_advantage = (char_defense - monster_attack) / max(char_defense + monster_attack, 1)
        
        # Critical advantage: scaled by percentage (5% crit = 0.05 advantage)
        critical_advantage = char_critical / 100.0
        
        # Level advantage: significant boost/penalty based on level difference
        level_difference = char_level - monster_level
        level_advantage = level_difference * 0.05  # Each level = 5% adjustment
        
        # Combine advantages with weights
        total_adjustment = (
            attack_advantage * attack_weight +
            defense_advantage * defense_weight +
            critical_advantage * critical_weight +
            level_advantage
        )
        
        # Cap adjustment to reasonable range (-0.3 to +0.3)
        total_adjustment = max(-0.3, min(0.3, total_adjustment))
        
        self.logger.debug(
            f"Combat power adjustment: attack={attack_advantage:.2f}, "
            f"defense={defense_advantage:.2f}, critical={critical_advantage:.2f}, "
            f"level={level_advantage:.2f}, total={total_adjustment:.2f}"
        )
        
        return total_adjustment

    def _get_monster_win_rate(self, monster_code, knowledge_base, **kwargs):
        """Get win rate for a monster from knowledge base."""
        try:
            if not hasattr(knowledge_base, 'data') or 'monsters' not in knowledge_base.data:
                return None
            
            monster_data = knowledge_base.data['monsters'].get(monster_code, {})
            combat_results = monster_data.get('combat_results', [])
            
            # Get minimum combats from configuration
            action_config = kwargs.get('action_config', {})
            min_combats = action_config.get('minimum_combat_results', 2)
            
            if len(combat_results) < min_combats:
                return None
            
            wins = sum(1 for result in combat_results if result.get('result') == 'win')
            total_combats = len(combat_results)
            
            return wins / total_combats if total_combats > 0 else None
            
        except Exception as e:
            self.logger.debug(f"Error getting win rate for {monster_code}: {e}")
            return None

    def __repr__(self):
        return "FindMonstersAction()"
