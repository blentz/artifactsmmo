""" FindMonstersAction module """

import math
from typing import Dict, List, Optional
from artifactsmmo_api_client.api.monsters.get_all_monster import sync as get_all_monsters_api
from .search_base import SearchActionBase


class FindMonstersAction(SearchActionBase):
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
        super().__init__(character_x, character_y, search_radius)
        self.monster_types = monster_types or []
        self.character_level = character_level
        self.level_range = level_range
        self.use_exponential_search = use_exponential_search
        self.max_search_radius = max_search_radius

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest monster location using unified search algorithm """
        self.log_execution_start(
            character_x=self.character_x, 
            character_y=self.character_y, 
            search_radius=self.search_radius,
            monster_types=self.monster_types
        )
        
        try:
            # Get target monster codes from API
            target_codes = self._get_target_monster_codes(client)
            if not target_codes:
                error_response = self.get_error_response("No suitable monsters found matching criteria")
                self.log_execution_result(error_response)
                return error_response

            # Create monster filter using the unified search base
            monster_filter = self.create_monster_filter(
                monster_types=target_codes,
                character_level=self.character_level,
                level_range=self.level_range
            )
            
            # Define result processor for monster-specific response format with combat viability
            def monster_result_processor(location, content_code, content_data):
                # Check combat viability before accepting the monster
                knowledge_base = kwargs.get('knowledge_base')
                win_rate = self._get_monster_win_rate(content_code, knowledge_base) if knowledge_base else None
                
                # Determine if combat is viable
                if not self._is_combat_viable(content_code, win_rate, kwargs):
                    return None  # Reject this monster, continue searching
                
                x, y = location
                distance = self._calculate_distance(x, y)
                win_rate_str = f"{win_rate:.1%}" if win_rate is not None else "unknown"
                self.logger.info(f"🎯 Selected {content_code} at {location} (win rate: {win_rate_str})")
                
                return self.get_success_response(
                    location=location,
                    distance=distance,
                    monster_code=content_code,
                    target_codes=target_codes,
                    search_radius_used=self.search_radius,
                    exponential_search_used=self.use_exponential_search,
                    win_rate=win_rate
                )
            
            # Use unified search algorithm
            result = self.unified_search(client, monster_filter, monster_result_processor)
            
            # If no viable monsters found, provide helpful error
            if not result or not result.get('success'):
                error_response = self.get_error_response(
                    f"No viable monsters found within radius {self.search_radius}",
                    max_radius_searched=self.search_radius,
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
    
    def _get_target_monster_codes(self, client) -> List[str]:
        """Get list of target monster codes based on filters."""
        try:
            monsters_response = get_all_monsters_api(client=client, size=100)
            if not monsters_response or not monsters_response.data:
                return []

            target_codes = []
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

            return target_codes
        except Exception as e:
            self.logger.warning(f"Error getting target monster codes: {e}")
            return []
    
    def _is_combat_viable(self, monster_code: str, win_rate: Optional[float], kwargs: Dict) -> bool:
        """Check if combat with this monster is viable based on win rate."""
        # Require minimum 20% win rate for known monsters
        if win_rate is not None and win_rate < 0.2:
            self.logger.warning(f"🚫 Combat not viable: {monster_code} win rate {win_rate:.1%} is too low")
            return False
        
        # Unknown monsters - be cautious but allow for low-level characters
        if win_rate is None:
            character_level = kwargs.get('character_level', 1)
            if character_level <= 2:
                self.logger.info(f"ℹ️ Accepting unknown monster {monster_code} at level {character_level}")
                return True
            else:
                self.logger.info(f"⏭️ Skipping unknown monster {monster_code} - searching for safer options")
                return False
        
        return True

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
