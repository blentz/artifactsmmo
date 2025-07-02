""" FindMonstersAction module """

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import sync as get_all_monsters_api

from src.lib.action_context import ActionContext

from .coordinate_mixin import CoordinateStandardizationMixin
from .search_base import SearchActionBase


class FindMonstersAction(SearchActionBase, CoordinateStandardizationMixin):
    """ Action to find the nearest map location with specified monsters """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
            'combat_context': {
                'status': 'searching',
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
                'status': 'ready',
            },
            'location_context': {
                'at_target': True,
            },
        }
    weights = {'find_monsters': 2.0}  # Medium-high priority for exploration

    def __init__(self):
        """
        Initialize the find monsters action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Find the nearest monster location using unified search algorithm """
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        search_radius = context.get('search_radius', 2)
        monster_types = context.get('monster_types', [])
        character_level = context.get('character_level', context.character_level)
        level_range = context.get('level_range', 2)
        use_exponential_search = context.get('use_exponential_search', True)
        max_search_radius = context.get('max_search_radius', 4)
        
        # Parameters will be passed directly to helper methods via context
        
        self.log_execution_start(
            character_x=character_x, 
            character_y=character_y, 
            search_radius=search_radius,
            monster_types=monster_types
        )
        
        # Validation is now handled by centralized ActionValidator
        if client is None:
            error_response = self.get_error_response("No API client provided")
            self.log_execution_result(error_response)
            return error_response
        
        try:
            # Get target monster codes from API
            target_codes = self._get_target_monster_codes(client, monster_types, character_level, level_range)
            if not target_codes:
                error_response = self.get_error_response("No suitable monsters found matching criteria")
                self.log_execution_result(error_response)
                return error_response

            # Create monster filter using the unified search base
            monster_filter = self.create_monster_filter(
                monster_types=target_codes,
                character_level=character_level,
                level_range=level_range
            )
            
            # Convert context to kwargs dict for helper methods
            kwargs = dict(context) if hasattr(context, '__iter__') else {}
            
            # Ensure character_level is available for viability checks
            if 'character_level' not in kwargs and character_level is not None:
                kwargs['character_level'] = character_level
            
            # Collect all viable monsters across all search radii for smart selection
            result = self._find_best_monster_target(client, monster_filter, target_codes, context)
            
            # If no viable monsters found, provide helpful error
            if not result or not result.get('success'):
                error_response = self.get_error_response(
                    f"No viable monsters found within radius {search_radius}",
                    max_radius_searched=search_radius,
                    suggestion="Consider map exploration or resource gathering for equipment upgrades"
                )
                self.log_execution_result(error_response)
                return error_response
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Monster search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response
    
    def _find_best_monster_target(self, client, monster_filter, target_codes, context: ActionContext):
        """
        Find the best monster target based on level priority, win rate, and distance.
        
        Priority order:
        1. Lower level monsters (safer for character)
        2. Higher win rates (known successful combat)
        3. Closer distance (efficiency)
        """
        # Extract parameters from context
        search_radius = context.get('search_radius', 2)
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        monster_types = context.get('monster_types', [])
        character_level = context.get('character_level', context.character_level)
        level_range = context.get('level_range', 2)
        use_exponential_search = context.get('use_exponential_search', True)
        
        knowledge_base = context.knowledge_base
        map_state = context.map_state
        action_config = context.get('action_config', {})
        viable_monsters = []
        
        # Search all radii to collect viable monster candidates
        for radius in range(1, search_radius + 1):
            locations_at_radius = self._search_radius_for_content(client, character_x, character_y, radius, monster_filter, map_state)
            
            for location, content_code, content_data in locations_at_radius:
                x, y = location
                distance = abs(x - character_x) + abs(y - character_y)  # Manhattan distance
                
                # Get monster level from knowledge base (with API fallback)
                monster_data = knowledge_base.get_monster_data(content_code, client=client)
                if not monster_data:
                    # Knowledge base couldn't get data, skip this monster
                    self.logger.warning(f"⚠️ Could not get data for {content_code}, skipping")
                    continue
                
                monster_level = monster_data.get('level', 1)
                
                # Check combat viability with known monster level
                win_rate = self._get_monster_win_rate(content_code, knowledge_base, 
                                                     action_config=action_config) if knowledge_base else None
                
                # Pass monster level for viability check
                viability_context = {
                    'monster_level': monster_level,
                    'character_level': character_level,
                    'monster_types': monster_types,
                    'level_range': level_range
                }
                
                if not self._is_combat_viable(content_code, win_rate, viability_context):
                    continue  # Skip non-viable monsters
                
                # Store monster candidate with all selection criteria
                monster_candidate = {
                    'location': location,
                    'content_code': content_code,
                    'content_data': content_data,
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
        best_monster = self._select_best_monster(viable_monsters)
        
        if best_monster:
            x, y = best_monster['x'], best_monster['y']
            content_code = best_monster['content_code']
            distance = best_monster['distance']
            win_rate = best_monster['win_rate']
            monster_level = best_monster['monster_level']
            
            win_rate_str = f"{win_rate:.1%}" if win_rate > 0 else "unknown"
            self.logger.info(f"🎯 Selected {content_code} (level {monster_level}) at ({x}, {y}) - distance: {distance:.1f}, win rate: {win_rate_str}")
            
            # Create standardized coordinate response
            coordinate_data = self.create_coordinate_response(
                x, y,
                distance=distance,
                monster_code=content_code,
                target_codes=target_codes,
                search_radius_used=search_radius,
                exponential_search_used=use_exponential_search,
                win_rate=win_rate
            )
            
            return self.get_success_response(**coordinate_data)
        
        return None
    
    def _select_best_monster(self, viable_monsters):
        """
        Select the best monster from viable candidates.
        
        Priority:
        1. Lowest level (safest)
        2. Highest win rate among same level
        3. Closest distance as tiebreaker
        """
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
        
        return best
    
    def _get_target_monster_codes(self, client, monster_types: List[str], character_level: int, level_range: int) -> List[str]:
        """Get list of target monster codes based on filters."""
        try:
            monsters_response = get_all_monsters_api(client=client, size=100)
            if not monsters_response or not monsters_response.data:
                return []

            target_codes = []
            for monster in monsters_response.data:
                # Check type filter if specified
                type_match = True
                if monster_types:
                    name_match = any(monster_type.lower() in monster.name.lower()
                                    for monster_type in monster_types)
                    code_match = any(monster_type.lower() in monster.code.lower()
                                    for monster_type in monster_types)
                    type_match = name_match or code_match
                
                # Check level filter if specified
                level_match = True
                if character_level is not None and level_range is not None:
                    monster_level = getattr(monster, 'level', 1)
                    # Only fight monsters at or below character level + level_range
                    # This ensures safety - prefer monsters at character level or below
                    level_match = monster_level <= character_level + level_range
                
                if type_match and level_match:
                    target_codes.append(monster.code)

            return target_codes
        except Exception as e:
            self.logger.warning(f"Error getting target monster codes: {e}")
            return []
    
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
