""" FindMonstersAction module """

import math
from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.monsters.get_all_monster import sync as get_all_monsters_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class FindMonstersAction(ActionBase):
    """ Action to find the nearest map location with specified monsters """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'need_combat': True,
        'monsters_available': False,
        'character_alive': True
    }
    reactions = {
        'monsters_available': True,
        'monster_present': True,
        'at_target_location': True
    }
    weights = {'find_monsters': 2.0}  # Medium-high priority for exploration

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 2,
                 monster_types: Optional[List[str]] = None, character_level: Optional[int] = None,
                 level_range: int = 2, use_exponential_search: bool = True, max_search_radius: int = 4):
        """
        Initialize the find monsters action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            search_radius: Initial radius to search for monsters (default: 2)
            monster_types: List of monster types to search for. If None, searches for all monsters.
            character_level: Character's current level for level-appropriate filtering. If None, no level filtering.
            level_range: Acceptable level range (+/-) for monster selection (default: 2)
            use_exponential_search: Whether to use exponential search radius expansion (default: True)
            max_search_radius: Maximum search radius when using exponential search (default: 4)
        """
        super().__init__()
        self.character_x = character_x
        self.character_y = character_y
        self.search_radius = search_radius
        self.monster_types = monster_types or []
        self.character_level = character_level
        self.level_range = level_range
        self.use_exponential_search = use_exponential_search
        self.max_search_radius = max_search_radius

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest monster location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_x=self.character_x, 
            character_y=self.character_y, 
            search_radius=self.search_radius,
            monster_types=self.monster_types
        )
        
        try:
            # First, get all monsters to find target monsters
            monsters_response = get_all_monsters_api(client=client, size=100)

            if not monsters_response or monsters_response.data is None:
                error_response = self.get_error_response("No monsters data available from API")
                self.log_execution_result(error_response)
                return error_response

            # Find target monsters with level filtering
            target_codes = []
            target_monsters = {}  # Store monster data for level checking
        
            for monster in monsters_response.data:
                # Check type filter if specified
                type_match = True
                if self.monster_types:
                    name_match = any(monster_type.lower() in monster.name.lower()
                                    for monster_type in self.monster_types)
                    code_match = any(monster_type.lower() in monster.code.lower()
                                    for monster_type in self.monster_types)
                    type_match = name_match or code_match
                
                # Check level filter if specified
                level_match = True
                if self.character_level is not None:
                    monster_level = getattr(monster, 'level', 1)
                    level_diff = abs(monster_level - self.character_level)
                    level_match = level_diff <= self.level_range
                
                if type_match and level_match:
                    target_codes.append(monster.code)
                    target_monsters[monster.code] = monster

            if not target_codes:
                error_response = self.get_error_response("No suitable monsters found matching criteria")
                self.log_execution_result(error_response)
                return error_response

            # Search around the character's position for target monsters
            nearest_monster_location = None
            min_distance = float('inf')
            found_monster_code = None
            
            # Determine search radii to use
            search_radii = self._get_search_radii()
            
            # Search with expanding radii
            # Get map_state from kwargs if available  
            map_state = kwargs.get('map_state', None)
            for radius in search_radii:
                self.logger.info(f"Searching for monsters at radius {radius}")
                locations_found = self._search_radius_for_monsters(client, target_codes, radius, map_state)

                if locations_found:
                    # Find the best monster considering both distance and win rate
                    best_monster = self._select_best_monster(locations_found, kwargs)
                    if best_monster:
                        # Check if combat is viable before proceeding
                        win_rate = best_monster.get('win_rate')
                        # Require minimum 20% win rate for known monsters, or accept unknown monsters only if no better option exists
                        combat_viable = True
                        if win_rate is not None and win_rate < 0.2:  # Less than 20% win rate for known monsters
                            combat_viable = False
                            self.logger.warning(f"🚫 Combat not viable: {best_monster['monster_code']} "
                                              f"win rate {win_rate:.1%} is too low for safe combat")
                        elif win_rate is None:  # Unknown monster - be more cautious
                            # Only accept unknown monsters if we've searched extensively or if character level is low enough
                            character_level = kwargs.get('character_level', 1)
                            if character_level <= 2 and radius <= 2:  # Low level, close monsters are probably safe
                                combat_viable = True
                                self.logger.info(f"ℹ️ Accepting unknown monster {best_monster['monster_code']} at level {character_level}")
                            elif radius >= max(search_radii):  # Searched everywhere, take what we can get
                                combat_viable = True
                                self.logger.warning(f"⚠️ Accepting unknown monster {best_monster['monster_code']} - no alternatives found")
                            else:
                                combat_viable = False
                                self.logger.info(f"⏭️ Skipping unknown monster {best_monster['monster_code']} - searching for safer options")
                        
                        if not combat_viable:
                            # Continue searching at larger radius or fail if this is max radius
                            if radius >= max(search_radii):
                                # This is the maximum radius, combat is not viable
                                error_response = self.get_error_response(
                                    f"Combat not viable: All nearby monsters have poor win rates or are unknown",
                                    suggestion="Seek equipment upgrades or explore new areas before combat",
                                    best_monster_found=best_monster['monster_code'],
                                    best_win_rate=win_rate,
                                    combat_viable=False
                                )
                                self.log_execution_result(error_response)
                                return error_response
                            else:
                                continue  # Try larger radius
                        
                        x, y = best_monster['location']
                        min_distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                        nearest_monster_location = (x, y)
                        found_monster_code = best_monster['monster_code']
                        
                        win_rate_str = f"{win_rate:.1%}" if win_rate is not None else "unknown"
                        self.logger.info(f"🎯 Selected {found_monster_code} at {nearest_monster_location} "
                                       f"(win rate: {win_rate_str})")
                        break

            if nearest_monster_location:
                success_response = self.get_success_response(
                    location=nearest_monster_location,
                    distance=min_distance,
                    monster_code=found_monster_code,
                    target_codes=target_codes,
                    search_radius_used=radius,
                    exponential_search_used=self.use_exponential_search
                )
                self.log_execution_result(success_response)
                return success_response

            # No monsters found - suggest alternative strategies
            max_radius_used = max(search_radii) if search_radii else self.search_radius
            alternative_locations = self._suggest_exploration_locations()
            
            error_response = self.get_error_response(
                f"No monsters found within maximum radius {max_radius_used}",
                max_radius_searched=max_radius_used,
                alternative_exploration_locations=alternative_locations,
                suggestion="Consider map exploration or resource gathering for equipment upgrades"
            )
            self.log_execution_result(error_response)
            return error_response
            
        except Exception as e:
            error_response = self.get_error_response(f"Monster search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _search_radius_for_monsters(self, client, target_codes: List[str],
                                   radius: int, map_state=None) -> List[Tuple[Tuple[int, int], str]]:
        """ Search for target monsters at a specific radius around the character """
        monster_locations = []

        # Generate coordinates at the given radius
        y_range = range(self.character_y - radius, self.character_y + radius + 1)
        x_range = range(self.character_x - radius, self.character_x + radius + 1)

        for y in y_range:
            for x in x_range:
                # Skip if this is not at the current radius (for optimization)
                distance_check = (abs(x - self.character_x) != radius and
                                 abs(y - self.character_y) != radius)
                if distance_check:
                    continue

                try:
                    # Use map state for persistence if available, otherwise direct API call
                    if map_state:
                        map_data_dict = map_state.scan(x, y)
                        # Extract the specific tile data
                        tile_key = f"{x},{y}"
                        if tile_key in map_data_dict:
                            map_tile_data = map_data_dict[tile_key]
                            
                            # Convert dict back to object-like access for compatibility
                            class MapTileWrapper:
                                def __init__(self, data_dict):
                                    # Filter out timestamp data that's not part of the game tile
                                    filtered_data = {k: v for k, v in data_dict.items() if k != 'last_scanned'}
                                    self.data = filtered_data
                                    if 'content' in filtered_data and filtered_data['content']:
                                        # Create content object with proper attribute access
                                        content_data = filtered_data['content']
                                        content_obj = type('Content', (), {})()
                                        content_obj.type_ = content_data.get('type')
                                        content_obj.code = content_data.get('code')
                                        self.content = content_obj
                                    else:
                                        self.content = None
                            
                            map_data = MapTileWrapper(map_tile_data)
                        else:
                            continue
                    else:
                        # Fallback to direct API call
                        map_response = get_map_api(x=x, y=y, client=client)
                        if map_response and map_response.data:
                            map_data = map_response.data
                        else:
                            continue

                    # Check if this location has a target monster
                    has_content = hasattr(map_data, 'content') and map_data.content
                    is_monster = (has_content and
                                 hasattr(map_data.content, 'type_') and
                                 map_data.content.type_ == 'monster')
                    has_target_code = (is_monster and
                                      hasattr(map_data.content, 'code') and
                                      map_data.content.code in target_codes)

                    if has_target_code:
                        monster_locations.append(((x, y), map_data.content.code))

                except Exception:
                    # Continue searching even if one location fails
                    continue

        return monster_locations

    def _get_search_radii(self) -> List[int]:
        """
        Generate search radii using exponential expansion algorithm.
        
        Returns:
            List of radii to search in order
        """
        if not self.use_exponential_search:
            return list(range(1, self.search_radius + 1))
        
        radii = []
        current_radius = self.search_radius
        
        # Start with the initial radius, then expand exponentially
        while current_radius <= self.max_search_radius:
            radii.append(current_radius)
            # Exponential growth: multiply by 1.5 and round up
            current_radius = math.ceil(current_radius * 1.5)
        
        # Ensure we don't exceed max_search_radius
        radii = [r for r in radii if r <= self.max_search_radius]
        
        # If we haven't covered all radii up to the initial search_radius, fill in gaps
        if radii and radii[0] > 1:
            small_radii = list(range(1, min(radii[0], self.search_radius + 1)))
            radii = small_radii + radii
        
        return sorted(set(radii))  # Remove duplicates and sort

    def _suggest_exploration_locations(self) -> List[Tuple[int, int]]:
        """
        Suggest alternative exploration locations when no monsters are found.
        
        Returns:
            List of (x, y) coordinates to explore
        """
        suggestions = []
        
        # Cardinal directions from current position
        cardinal_offsets = [
            (0, self.max_search_radius),    # North
            (self.max_search_radius, 0),   # East  
            (0, -self.max_search_radius),  # South
            (-self.max_search_radius, 0),  # West
        ]
        
        for dx, dy in cardinal_offsets:
            new_x = self.character_x + dx
            new_y = self.character_y + dy
            suggestions.append((new_x, new_y))
        
        # Diagonal directions at half max radius
        half_radius = self.max_search_radius // 2
        diagonal_offsets = [
            (half_radius, half_radius),    # Northeast
            (half_radius, -half_radius),   # Southeast
            (-half_radius, -half_radius),  # Southwest
            (-half_radius, half_radius),   # Northwest
        ]
        
        for dx, dy in diagonal_offsets:
            new_x = self.character_x + dx
            new_y = self.character_y + dy
            suggestions.append((new_x, new_y))
        
        return suggestions

    def _select_best_monster(self, locations_found, kwargs):
        """
        Select the best monster from available locations considering win rates.
        
        Args:
            locations_found: List of tuples (location, monster_code)
            kwargs: Context containing knowledge_base
            
        Returns:
            Dict with best monster info or None
        """
        try:
            knowledge_base = kwargs.get('knowledge_base')
            if not knowledge_base:
                # No knowledge base, fall back to closest monster
                return self._select_closest_monster(locations_found)
            
            # Evaluate each monster location
            monster_evaluations = []
            for location, monster_code in locations_found:
                x, y = location
                distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                
                # Get win rate from knowledge base
                win_rate = self._get_monster_win_rate(monster_code, knowledge_base)
                
                # Calculate score: higher win rate is better, closer distance is better
                # Prioritize win rate heavily but still consider distance
                if win_rate is not None:
                    # Score: win_rate (0-1) * 100 - distance penalty
                    score = win_rate * 100 - (distance * 0.1)
                else:
                    # Unknown win rate: use moderate score based on distance
                    score = 50 - distance
                
                monster_evaluations.append({
                    'location': location,
                    'monster_code': monster_code,
                    'distance': distance,
                    'win_rate': win_rate,
                    'score': score
                })
            
            if not monster_evaluations:
                return None
            
            # Sort by score (highest first)
            monster_evaluations.sort(key=lambda x: x['score'], reverse=True)
            
            # Select best monster, but warn if win rate is poor
            best_monster = monster_evaluations[0]
            if best_monster['win_rate'] is not None and best_monster['win_rate'] < 0.3:
                self.logger.warning(f"⚠️ Best available monster {best_monster['monster_code']} "
                                  f"has poor win rate: {best_monster['win_rate']:.1%}")
                self.logger.info("💡 Consider seeking equipment upgrades or exploring new areas")
            
            return best_monster
            
        except Exception as e:
            self.logger.warning(f"Error selecting best monster: {e}")
            # Fall back to closest monster
            return self._select_closest_monster(locations_found)
    
    def _select_closest_monster(self, locations_found):
        """Fall back to selecting the closest monster."""
        if not locations_found:
            return None
        
        min_distance = float('inf')
        best_monster = None
        
        for location, monster_code in locations_found:
            x, y = location
            distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
            
            if distance < min_distance:
                min_distance = distance
                best_monster = {
                    'location': location,
                    'monster_code': monster_code,
                    'distance': distance,
                    'win_rate': None,
                    'score': -distance
                }
        
        return best_monster
    
    def _get_monster_win_rate(self, monster_code, knowledge_base):
        """Get win rate for a monster from knowledge base."""
        try:
            if not hasattr(knowledge_base, 'data') or 'monsters' not in knowledge_base.data:
                return None
            
            monster_data = knowledge_base.data['monsters'].get(monster_code, {})
            combat_results = monster_data.get('combat_results', [])
            
            if len(combat_results) < 2:  # Need at least 2 combats for meaningful data
                return None
            
            wins = sum(1 for result in combat_results if result.get('result') == 'win')
            total_combats = len(combat_results)
            
            return wins / total_combats if total_combats > 0 else None
            
        except Exception as e:
            self.logger.debug(f"Error getting win rate for {monster_code}: {e}")
            return None

    def __repr__(self):
        monster_filter = f", types={self.monster_types}" if self.monster_types else ""
        exp_search = f", exp_search={self.use_exponential_search}" if self.use_exponential_search else ""
        return (f"FindMonstersAction({self.character_x}, {self.character_y}, "
                f"radius={self.search_radius}{monster_filter}{exp_search})")
