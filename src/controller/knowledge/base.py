"""
Knowledge Base for AI Player Learning

This module extends the existing WorldState system to add learning capabilities
while integrating with the existing MapState and CharacterState systems.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get import sync as get_monster_api
from artifactsmmo_api_client.api.np_cs.get_npc_npcs_details_code_get import sync as get_npc_api
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api

from src.game.globals import DATA_PREFIX
from src.lib.goap_data import GoapData


class KnowledgeBase(GoapData):
    """
    Extended world state with learning capabilities.
    
    Integrates with existing MapState and WorldState systems to add:
    - Combat learning and monster analysis
    - Resource discovery patterns
    - Character progression insights
    - Smart location recommendations
    
    Uses the same persistence system as WorldState but adds learned knowledge.
    """
    
    def __init__(self, filename="knowledge.yaml"):
        """Initialize the knowledge base with GOAP data structure."""
        if "/" not in filename:
            filename = f"{DATA_PREFIX}/{filename}"
        super().__init__(filename)
        self.logger = logging.getLogger(__name__)
        
        # Initialize learning data if it doesn't exist
        if not self.data:
            self.data = {}
            
        # Configuration caching for performance optimization
        self._action_cache = None
        self._goal_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5 minutes
            
        self._ensure_learning_structure()
        
    def _ensure_learning_structure(self):
        """Ensure learning data structure exists without duplicating MapState functionality."""
        learning_structure = {
            # Combat learning - not covered by existing states  
            'monsters': {},           # {monster_code: {combat_results, estimated_stats, etc}}
            'combat_insights': {},    # {level: {success_rates, damage_patterns, etc}}
            
            # Resource learning - extends MapState with harvest experience
            'resources': {},          # {resource_code: {harvest_attempts, yields, skill_requirements}}
            
            # NPC learning - character interactions and services
            'npcs': {},               # {npc_code: {services, dialogue_options, trade_info}}
            
            # Workshop learning - crafting locations and recipes
            'workshops': {},          # {workshop_code: {available_recipes, skill_requirements, efficiency}}
            
            # Facility learning - banks, exchanges, and service locations
            'facilities': {},         # {facility_code: {services, usage_patterns, efficiency}}
            
            # Item learning - discovered items and their properties
            'items': {},              # {item_code: {properties, sources, uses, market_data}}
            
            # Character progression insights
            'character_insights': {
                'level_progression': {},  # {level: {xp_sources, time_taken, strategies_used}}
                'combat_performance': {}, # {level: {avg_success_rate, preferred_monsters}}
                'exploration_patterns': {}  # {area: {visit_frequency, productivity}}
            },
            
            # Learning statistics
            'learning_stats': {
                'total_combats': 0,
                'unique_monsters_fought': 0,
                'unique_npcs_met': 0,
                'unique_workshops_found': 0,
                'unique_facilities_found': 0,
                'unique_items_discovered': 0,
                'last_learning_session': None,
                'learning_version': '2.0'  # Updated for new content types
            }
        }
        
        for category, default_value in learning_structure.items():
            if category not in self.data:
                self.data[category] = default_value
    
    def _needs_cache_refresh(self, config_file: str) -> bool:
        """Check if configuration cache needs refresh."""
        import os
        import time
        
        if self._cache_timestamp is None:
            return True
            
        # Check if cache is older than duration
        if time.time() - self._cache_timestamp > self._cache_duration:
            return True
            
        # Check if config file was modified since cache
        try:
            config_mtime = os.path.getmtime(config_file)
            return config_mtime > self._cache_timestamp
        except (OSError, IOError):
            return True
    
    def get_cached_actions(self, config_file: str = "config/default_actions.yaml") -> Dict:
        """Cache and return parsed action configurations for performance."""
        if self._action_cache is None or self._needs_cache_refresh(config_file):
            import time
            start_time = time.time()
            
            # Load actions using existing YAML infrastructure
            from src.lib.yaml_data import YamlData
            yaml_data = YamlData(config_file)
            self._action_cache = yaml_data.data.get('actions', {})
            self._cache_timestamp = time.time()
            
            load_time = time.time() - start_time
            self.logger.info(f"🕐 Action Config Cache Refresh: {load_time:.3f}s ({len(self._action_cache)} actions)")
            
        return self._action_cache
    
    def get_relevant_actions(self, goal_state: Dict, start_state: Dict = None) -> List[str]:
        """Return only actions relevant to goal state and start state to reduce search space."""
        cached_actions = self.get_cached_actions()
        
        if not goal_state:
            return list(cached_actions.keys())
        
        # Filter actions based on both goal state and start state analysis
        relevant_actions = set()
        
        # Analyze all relevant state keys (both goal and start state)
        all_state_keys = set(goal_state.keys())
        if start_state:
            all_state_keys.update(start_state.keys())
        
        for state_key in all_state_keys:
            # Get actions that have conditions or reactions matching the state key
            for action_name, action_config in cached_actions.items():
                conditions = action_config.get('conditions', {})
                reactions = action_config.get('reactions', {})
                
                # Include action if it affects or depends on the state key
                if state_key in conditions or state_key in reactions:
                    relevant_actions.add(action_name)
        
        # Always include core movement and utility actions
        core_actions = ['move', 'wait', 'rest']
        for action_name in core_actions:
            if action_name in cached_actions:
                relevant_actions.add(action_name)
        
        # Log performance gain
        total_actions = len(cached_actions)
        filtered_actions = len(relevant_actions)
        self.logger.debug(f"🎯 Action Filtering: {total_actions} → {filtered_actions} actions for goal state: {list(goal_state.keys())}")
        
        return list(relevant_actions)
    
    def learn_from_content_discovery(self, content_type: str, content_code: str, 
                                   x: int, y: int, content_data: Dict = None) -> None:
        """
        Learn from discovering content at a location (integrates with MapState).
        
        Args:
            content_type: Type of content ('monster', 'resource', 'npc', 'workshop', 'skill_station', 'facility', 'item')
            content_code: Code/identifier of the content
            x: X coordinate
            y: Y coordinate  
            content_data: Additional content data from API
        """
        content_data = content_data or {}
        
        if content_type == 'monster':
            self._learn_monster_discovery(content_code, x, y, content_data)
        elif content_type == 'resource':
            self._learn_resource_discovery(content_code, x, y, content_data)
        elif content_type == 'npc':
            self._learn_npc_discovery(content_code, x, y, content_data)
        elif content_type == 'workshop':
            self._learn_workshop_discovery(content_code, x, y, content_data)
        elif content_type == 'skill_station':
            # Treat skill_station as a specialized workshop
            self._learn_workshop_discovery(content_code, x, y, content_data)
        elif content_type == 'facility':
            self._learn_facility_discovery(content_code, x, y, content_data)
        elif content_type == 'item':
            self._learn_item_discovery(content_code, x, y, content_data)
        else:
            # Log unknown content type for future implementation
            self.logger.warning(f"Unknown content type '{content_type}' for '{content_code}' - not learning")
            
    def _learn_monster_discovery(self, monster_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering a monster (does not duplicate MapState location tracking)."""
        if monster_code not in self.data['monsters']:
            self.data['monsters'][monster_code] = {
                'code': monster_code,
                'name': content_data.get('name', monster_code),
                'first_discovered': datetime.now().isoformat(),
                'encounter_count': 0,
                'combat_results': [],
                'estimated_level': None,
                'estimated_hp': None,
                'estimated_damage': None
            }
            self.data['learning_stats']['unique_monsters_fought'] += 1
            
        monster_info = self.data['monsters'][monster_code]
        monster_info['last_seen'] = datetime.now().isoformat()
        monster_info['encounter_count'] = monster_info.get('encounter_count', 0) + 1
        
    def _learn_resource_discovery(self, resource_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering a resource (extends MapState with harvest experience)."""
        if resource_code not in self.data['resources']:
            self.data['resources'][resource_code] = {
                'code': resource_code,
                'name': content_data.get('name', resource_code),
                'first_discovered': datetime.now().isoformat(),
                'harvest_attempts': 0,
                'successful_harvests': 0,
                'estimated_skill_required': None,
                'estimated_yield': [],
                'best_locations': []  # Locations with high yield
            }
            
        resource_info = self.data['resources'][resource_code]
        resource_info['last_seen'] = datetime.now().isoformat()
        
    def record_combat_result(self, monster_code: str, result: str, character_data: Dict, 
                           fight_data: Dict = None) -> None:
        """
        Record the result of combat with a monster.
        
        Args:
            monster_code: The monster that was fought
            result: Combat result ('win', 'loss', 'flee')
            character_data: Character state before/after combat
            fight_data: Detailed fight information if available
        """
        if monster_code not in self.data['monsters']:
            self.data['monsters'][monster_code] = {
                'code': monster_code,
                'name': monster_code,
                'locations': [],
                'first_discovered': datetime.now().isoformat(),
                'encounter_count': 0,
                'combat_results': [],
                'estimated_level': None,
                'estimated_hp': None,
                'estimated_damage': None
            }
            
        monster_info = self.data['monsters'][monster_code]
        
        combat_record = {
            'timestamp': datetime.now().isoformat(),
            'result': result,
            'character_level': character_data.get('level', 1),
            'character_hp_before': character_data.get('hp_before', character_data.get('hp', 0)),
            'character_hp_after': character_data.get('hp', 0),
            'xp_gained': fight_data.get('xp', 0) if fight_data else 0,
            'damage_taken': None,
            'damage_dealt': None
        }
        
        # Calculate damage if we have before/after HP
        hp_before = combat_record['character_hp_before']
        hp_after = combat_record['character_hp_after']
        if hp_before and hp_after and hp_before > hp_after:
            combat_record['damage_taken'] = hp_before - hp_after
            
        if fight_data:
            # Convert DropSchema objects to serializable dictionaries
            drops_data = []
            drops = fight_data.get('drops')
            if drops is not None:
                for drop in drops:
                    if drop is None:
                        continue  # Skip None entries
                    elif hasattr(drop, '__dict__') and hasattr(drop, 'code'):
                        # Convert DropSchema object to dict, filtering out non-serializable fields
                        drop_dict = {
                            'code': getattr(drop, 'code', None),
                            'quantity': getattr(drop, 'quantity', 0)
                        }
                        drops_data.append(drop_dict)
                    elif isinstance(drop, dict):
                        # Already a dict, just keep essential fields
                        drops_data.append({
                            'code': drop.get('code'),
                            'quantity': drop.get('quantity', 0)
                        })
                    elif isinstance(drop, str):
                        # Legacy string format - keep for backward compatibility
                        drops_data.append(drop)
                    else:
                        # Unknown format, try to store as-is
                        drops_data.append(drop)
            
            combat_record.update({
                'turns': fight_data.get('turns', 0),
                'drops': drops_data,
                'gold_gained': fight_data.get('gold', 0)
            })
            
        monster_info['combat_results'].append(combat_record)
        
        # Update learning statistics
        self.data['learning_stats']['total_combats'] += 1
        self.data['learning_stats']['last_learning_session'] = datetime.now().isoformat()
        
        # Update monster estimates based on combat data
        self._update_monster_estimates(monster_code)
        
        self.logger.info(f"Recorded combat result vs {monster_code}: {result}")
        
    def _update_monster_estimates(self, monster_code: str) -> None:
        """Update monster level/damage estimates based on combat history."""
        monster_info = self.data['monsters'][monster_code]
        combat_results = monster_info['combat_results']
        
        if not combat_results:
            return
            
        # Estimate monster level based on character levels that won/lost
        wins = [r for r in combat_results if r['result'] == 'win']
        losses = [r for r in combat_results if r['result'] == 'loss']
        
        if wins:
            # Monster level is likely around the character levels that can beat it
            win_levels = [r['character_level'] for r in wins]
            monster_info['estimated_level'] = sum(win_levels) // len(win_levels)
            
        # Estimate damage based on HP loss patterns
        damage_records = [r['damage_taken'] for r in combat_results 
                         if r['damage_taken'] is not None]
        if damage_records:
            monster_info['estimated_damage'] = sum(damage_records) // len(damage_records)
    
    def find_suitable_monsters(self, map_state, character_level: int = None,
                             level_range: int = 2, max_distance: int = 20,
                             current_x: int = 0, current_y: int = 0) -> List[Dict]:
        """
        Find suitable monsters using MapState data and learning insights.
        
        Args:
            map_state: MapState instance with location data
            character_level: Character level for filtering
            level_range: Acceptable level range
            max_distance: Maximum search distance
            current_x: Current X position
            current_y: Current Y position
            
        Returns:
            List of monster location dictionaries with learning insights
        """
        suitable_monsters = []
        
        if not map_state or not hasattr(map_state, 'data'):
            return suitable_monsters
            
        # Search through MapState's discovered locations
        for location_key, location_data in map_state.data.items():
            if not isinstance(location_data, dict):
                continue
                
            content = location_data.get('content')
            if not content or content.get('type_') != 'monster':
                continue
                
            # Parse coordinates from location key "x,y"
            try:
                x, y = map(int, location_key.split(','))
            except (ValueError, AttributeError):
                continue
                
            # Check distance
            distance = ((x - current_x) ** 2 + (y - current_y) ** 2) ** 0.5
            if distance > max_distance:
                continue
                
            monster_code = content.get('code', 'unknown')
            
            # Get learning insights for this monster
            monster_info = self.data['monsters'].get(monster_code, {})
            estimated_level = monster_info.get('estimated_level')
            
            # Level filtering with learned data
            if character_level is not None and estimated_level is not None:
                level_diff = abs(estimated_level - character_level)
                if level_diff > level_range:
                    continue
                    
            # Calculate success rate based on learning
            success_rate = self.get_monster_combat_success_rate(monster_code, character_level or 1)
            
            suitable_monsters.append({
                'location': (x, y),
                'distance': distance,
                'monster_code': monster_code,
                'estimated_level': estimated_level,
                'success_rate': success_rate,
                'encounter_count': monster_info.get('encounter_count', 0),
                'last_seen': monster_info.get('last_seen'),
                'content_data': content
            })
            
        # Sort by success rate and distance
        suitable_monsters.sort(key=lambda m: (-m.get('success_rate', 0.5), m['distance']))
        return suitable_monsters
        
    def is_location_known(self, map_state, x: int, y: int) -> bool:
        """Check if a location has been visited before (uses MapState)."""
        if not map_state:
            return False
        location_key = f"{x},{y}"
        return location_key in map_state.data
        
    def get_location_info(self, map_state, x: int, y: int) -> Optional[Dict]:
        """Get stored information about a specific location (uses MapState)."""
        if not map_state:
            return None
        location_key = f"{x},{y}"
        return map_state.data.get(location_key)
        
    def find_monsters_in_map(self, map_state, character_x: int, character_y: int, 
                            monster_types: List[str] = None, character_level: int = None, 
                            level_range: int = 2, max_radius: int = 10) -> List[Dict]:
        """
        Find monsters from cached map data, using knowledge base for monster details.
        
        Args:
            map_state: MapState instance with cached map data
            character_x: Character's current X coordinate
            character_y: Character's current Y coordinate
            monster_types: Optional list of monster types to filter by
            character_level: Character level for level-appropriate filtering
            level_range: Level range for monster selection
            max_radius: Maximum search radius
            
        Returns:
            List of monster location dictionaries with distance and monster data
        """
        if not map_state or not map_state.data:
            return []
            
        found_monsters = []
        
        # Search through all cached map locations
        for location_key, location_data in map_state.data.items():
            if not isinstance(location_data, dict):
                continue
                
            content = location_data.get('content')
            if not content or content.get('type') != 'monster':
                continue
                
            # Parse coordinates
            try:
                x, y = map(int, location_key.split(','))
            except (ValueError, AttributeError):
                continue
                
            # Check if within search radius
            distance = ((x - character_x) ** 2 + (y - character_y) ** 2) ** 0.5
            if distance > max_radius:
                continue
                
            monster_code = content.get('code')
            if not monster_code:
                continue
                
            # Get monster details from knowledge base
            monster_data = self.get_monster_data(monster_code)
            if not monster_data:
                # If no detailed data, create basic entry from map content
                monster_data = {
                    'code': monster_code,
                    'name': monster_code,
                    'level': 1,  # Default level
                    'hp': 0
                }
                
            # Apply filters
            if monster_types:
                type_match = any(monster_type.lower() in monster_code.lower() or 
                               monster_type.lower() in monster_data.get('name', '').lower() 
                               for monster_type in monster_types)
                if not type_match:
                    continue
                    
            if character_level is not None and level_range is not None:
                monster_level = monster_data.get('level', 1)
                if monster_level > character_level + level_range:
                    continue
                    
            # Add to results
            found_monsters.append({
                'location': (x, y),
                'x': x,
                'y': y,
                'distance': distance,
                'monster_code': monster_code,
                'monster_data': monster_data,
                'content_data': content
            })
            
        # Sort by distance
        found_monsters.sort(key=lambda m: m['distance'])
        
        self.logger.info(f"🔍 Found {len(found_monsters)} monsters in cached map data within radius {max_radius}")
        return found_monsters

    def get_monster_data(self, monster_code: str, client=None) -> Optional[Dict]:
        """
        Get monster data from knowledge base, with API fallback if not found.
        
        Args:
            monster_code: Monster code to look up
            client: API client for fallback (optional)
            
        Returns:
            Monster data dictionary or None if not found
        """
        # Check if we already have the monster data
        if monster_code in self.data['monsters']:
            return self.data['monsters'][monster_code]
        
        # If not found and client provided, fetch from API
        if client:
            try:
                self.logger.info(f"📊 Fetching {monster_code} data from API...")
                response = get_monster_api(code=monster_code, client=client)
                
                if response:
                    monster = response.data
                    # Store the monster data for future use
                    monster_data = {
                        'code': monster.code,
                        'name': getattr(monster, 'name', monster.code),
                        'level': getattr(monster, 'level', 1),
                        'hp': getattr(monster, 'hp', 0),
                        'attack_stats': {
                            'attack_fire': getattr(monster, 'attack_fire', 0),
                            'attack_earth': getattr(monster, 'attack_earth', 0),
                            'attack_water': getattr(monster, 'attack_water', 0),
                            'attack_air': getattr(monster, 'attack_air', 0)
                        },
                        'resistance_stats': {
                            'res_fire': getattr(monster, 'res_fire', 0),
                            'res_earth': getattr(monster, 'res_earth', 0),
                            'res_water': getattr(monster, 'res_water', 0),
                            'res_air': getattr(monster, 'res_air', 0)
                        },
                        'drops': getattr(monster, 'drops', []),
                        'first_discovered': datetime.now().isoformat(),
                        'combat_results': [],
                        'total_combats': 0
                    }
                    
                    # Store in knowledge base
                    self.data['monsters'][monster_code] = monster_data
                    self.save()
                    
                    self.logger.info(f"✅ Added {monster_code} (level {monster_data['level']}) to knowledge base")
                    return monster_data
                else:
                    self.logger.warning(f"❓ Monster {monster_code} not found in API")
            except Exception as e:
                self.logger.error(f"Failed to fetch monster data from API: {e}")
        
        return None
    
    def get_monster_combat_success_rate(self, monster_code: str, 
                                      character_level: int) -> float:
        """
        Get the success rate for fighting a specific monster at character level.
        
        Args:
            monster_code: Monster to check
            character_level: Current character level
            
        Returns:
            Success rate as a float between 0.0 and 1.0, or -1.0 if no data
        """
        if monster_code not in self.data['monsters']:
            return -1.0
            
        monster_info = self.data['monsters'][monster_code]
        combat_results = monster_info['combat_results']
        
        # Filter combat results for similar character level (±1 level)
        relevant_results = [
            r for r in combat_results 
            if abs(r['character_level'] - character_level) <= 1
        ]
        
        if not relevant_results:
            return -1.0
            
        wins = len([r for r in relevant_results if r['result'] == 'win'])
        total = len(relevant_results)
        
        return wins / total if total > 0 else -1.0
        
    def get_learning_stats(self) -> Dict:
        """Get learning statistics."""
        return self.data['learning_stats'].copy()
        
    def get_knowledge_summary(self, map_state=None) -> Dict:
        """Get a summary of all learned knowledge."""
        summary = {
            'monsters_discovered': len(self.data['monsters']),
            'resources_discovered': len(self.data['resources']),
            'total_combats': self.data['learning_stats']['total_combats'],
            'learning_stats': self.get_learning_stats()
        }
        
        # Add map exploration stats if MapState is provided
        if map_state and hasattr(map_state, 'data'):
            summary['total_locations_discovered'] = len(map_state.data)
        else:
            summary['total_locations_discovered'] = 0
            
        return summary
        
    def find_nearest_known_content(self, map_state, current_x: int, current_y: int, 
                                 content_type: str, max_distance: int = 20) -> Optional[Tuple[int, int, float]]:
        """
        Find the nearest known location with specific content (uses MapState).
        
        Args:
            map_state: MapState instance with location data
            current_x: Current X coordinate
            current_y: Current Y coordinate
            content_type: Type of content to find
            max_distance: Maximum search distance
            
        Returns:
            Tuple of (x, y, distance) or None if not found
        """
        if not map_state or not hasattr(map_state, 'data'):
            return None
            
        nearest_location = None
        min_distance = float('inf')
        
        for location_key, location_data in map_state.data.items():
            if not isinstance(location_data, dict):
                continue
                
            content = location_data.get('content')
            if not content or content.get('type_') != content_type:
                continue
                
            try:
                x, y = map(int, location_key.split(','))
            except (ValueError, AttributeError):
                continue
                
            distance = ((x - current_x) ** 2 + (y - current_y) ** 2) ** 0.5
            
            if distance <= max_distance and distance < min_distance:
                min_distance = distance
                nearest_location = (x, y, distance)
                
        return nearest_location
    
    def _learn_npc_discovery(self, npc_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering an NPC."""
        if npc_code not in self.data['npcs']:
            self.data['npcs'][npc_code] = {
                'code': npc_code,
                'name': content_data.get('name', npc_code),
                'type': content_data.get('type_', 'unknown'),
                'description': content_data.get('description', ''),
                'first_discovered': datetime.now().isoformat(),
                'interaction_count': 0,
                'services': content_data.get('services', []),
                'dialogue_options': [],
                'trade_history': []
            }
            self.data['learning_stats']['unique_npcs_met'] += 1
            
        npc_info = self.data['npcs'][npc_code]
        npc_info['last_seen'] = datetime.now().isoformat()
        npc_info['encounter_count'] = npc_info.get('encounter_count', 0) + 1
    
    def _learn_workshop_discovery(self, workshop_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering a workshop/crafting location."""
        if workshop_code not in self.data['workshops']:
            self.data['workshops'][workshop_code] = {
                'code': workshop_code,
                'name': content_data.get('name', workshop_code),
                'craft_skill': content_data.get('skill', content_data.get('craft_skill', 'unknown')),
                'first_discovered': datetime.now().isoformat(),
                'usage_count': 0,
                'available_recipes': content_data.get('recipes', []),
                'skill_requirements': content_data.get('level', 1),
                'efficiency_ratings': {},
                'best_times': []  # When it's least busy
            }
            self.data['learning_stats']['unique_workshops_found'] += 1
            
        workshop_info = self.data['workshops'][workshop_code]
        workshop_info['last_seen'] = datetime.now().isoformat()
        workshop_info['encounter_count'] = workshop_info.get('encounter_count', 0) + 1
    
    def _learn_facility_discovery(self, facility_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering a facility (bank, exchange, etc.)."""
        if facility_code not in self.data['facilities']:
            self.data['facilities'][facility_code] = {
                'code': facility_code,
                'name': content_data.get('name', facility_code),
                'facility_type': content_data.get('type_', 'unknown'),
                'first_discovered': datetime.now().isoformat(),
                'usage_count': 0,
                'services': content_data.get('services', []),
                'efficiency_ratings': {},
                'usage_patterns': {
                    'peak_hours': [],
                    'avg_wait_time': 0
                }
            }
            self.data['learning_stats']['unique_facilities_found'] += 1
            
        facility_info = self.data['facilities'][facility_code]
        facility_info['last_seen'] = datetime.now().isoformat()
        facility_info['encounter_count'] = facility_info.get('encounter_count', 0) + 1
    
    def _learn_item_discovery(self, item_code: str, x: int, y: int, content_data: Dict) -> None:
        """Learn from discovering an item."""
        if item_code not in self.data['items']:
            self.data['items'][item_code] = {
                'code': item_code,
                'name': content_data.get('name', item_code),
                'item_type': content_data.get('type_', 'unknown'),
                'subtype': content_data.get('subtype', ''),
                'first_discovered': datetime.now().isoformat(),
                'discovery_count': 0,
                'tradeable': content_data.get('tradeable', False),
                'description': content_data.get('description', ''),
                'effects': content_data.get('effects', []),
                'sources': [],  # Where it can be obtained
                'uses': [],     # What it's used for
                'market_data': {
                    'min_price': None,
                    'max_price': None,
                    'avg_price': None,
                    'price_history': []
                }
            }
            self.data['learning_stats']['unique_items_discovered'] += 1
            
        item_info = self.data['items'][item_code]
        item_info['last_seen'] = datetime.now().isoformat()
        item_info['discovery_count'] += 1
    
    def learn_resource_capabilities(self, resource_code: str, drops: List[Dict]) -> None:
        """
        Learn about resource drop capabilities from API data.
        
        Args:
            resource_code: Resource code (e.g., "ash_tree")
            drops: List of drop data from capability analyzer
        """
        if 'resource_capabilities' not in self.data:
            self.data['resource_capabilities'] = {}
        
        self.data['resource_capabilities'][resource_code] = {
            'resource_code': resource_code,
            'drops': drops,
            'last_analyzed': datetime.now().isoformat()
        }
        
        self.logger.info(f"💾 Learned resource capabilities: {resource_code} → {len(drops)} drops")
        self.save()
    
    def learn_item_capabilities(self, item_code: str, capabilities: Dict) -> None:
        """
        Learn about item capabilities including effects and crafting requirements.
        
        Args:
            item_code: Item code (e.g., "wooden_staff")
            capabilities: Item capability data from analyzer
        """
        if 'item_capabilities' not in self.data:
            self.data['item_capabilities'] = {}
        
        self.data['item_capabilities'][item_code] = {
            **capabilities,
            'last_analyzed': datetime.now().isoformat()
        }
        
        self.logger.info(f"💾 Learned item capabilities: {item_code}")
        self.save()
    
    def learn_upgrade_chain(self, resource_code: str, target_item_code: str, chain_analysis: Dict) -> None:
        """
        Learn about viable upgrade chains for multi-step planning.
        
        Args:
            resource_code: Starting resource
            target_item_code: Target item
            chain_analysis: Complete chain analysis data
        """
        if 'upgrade_chains' not in self.data:
            self.data['upgrade_chains'] = {}
        
        chain_key = f"{resource_code}→{target_item_code}"
        self.data['upgrade_chains'][chain_key] = {
            'resource': resource_code,
            'target': target_item_code,
            'analysis': chain_analysis,
            'last_analyzed': datetime.now().isoformat()
        }
        
        self.logger.info(f"💾 Learned upgrade chain: {chain_key}")
        self.save()
    
    def learn_weapon_comparison(self, current_weapon: str, potential_upgrade: str, comparison: Dict) -> None:
        """
        Learn about weapon upgrade comparisons for decision making.
        
        Args:
            current_weapon: Current weapon code
            potential_upgrade: Potential upgrade weapon code
            comparison: Comparison analysis data
        """
        if 'weapon_comparisons' not in self.data:
            self.data['weapon_comparisons'] = {}
        
        comparison_key = f"{current_weapon}→{potential_upgrade}"
        self.data['weapon_comparisons'][comparison_key] = {
            'current': current_weapon,
            'upgrade': potential_upgrade,
            'comparison': comparison,
            'last_analyzed': datetime.now().isoformat()
        }
        
        self.logger.info(f"💾 Learned weapon comparison: {comparison_key}")
        self.save()
    
    def get_known_upgrade_chains(self, resource_code: str = None, target_item: str = None) -> List[Dict]:
        """
        Get known upgrade chains, optionally filtered by resource or target.
        
        Args:
            resource_code: Filter by starting resource
            target_item: Filter by target item
            
        Returns:
            List of known upgrade chain data
        """
        if 'upgrade_chains' not in self.data:
            return []
        
        chains = []
        for chain_key, chain_data in self.data['upgrade_chains'].items():
            if resource_code and chain_data['resource'] != resource_code:
                continue
            if target_item and chain_data['target'] != target_item:
                continue
            chains.append(chain_data)
        
        return chains
    
    def get_weapon_upgrade_recommendation(self, current_weapon: str) -> Optional[Dict]:
        """
        Get learned weapon upgrade recommendations for current weapon.
        
        Args:
            current_weapon: Current weapon code
            
        Returns:
            Best upgrade recommendation or None
        """
        if 'weapon_comparisons' not in self.data:
            return None
        
        best_upgrade = None
        best_improvement = 0
        
        for comparison_key, comparison_data in self.data['weapon_comparisons'].items():
            if comparison_data['current'] == current_weapon:
                comparison = comparison_data['comparison']
                if comparison.get('recommendUpgrade', False):
                    improvement = comparison.get('attack_improvement', 0)
                    if improvement > best_improvement:
                        best_improvement = improvement
                        best_upgrade = comparison_data
        
        return best_upgrade

    def save(self) -> None:
        """
        Override save method to sanitize DropSchema objects before saving.
        """
        try:
            # Sanitize the data before saving to remove any DropSchema objects
            self._sanitize_data()
            super().save()
        except Exception as e:
            self.logger.error(f"Failed to save knowledge base: {e}")
            raise

    def _sanitize_data(self) -> None:
        """
        Recursively sanitize data to convert any DropSchema objects to dictionaries.
        """
        self.data = self._sanitize_object(self.data)

    def learn_resource(self, resource_code: str, resource_data: Dict) -> None:
        """
        Learn about a resource from API data.
        
        Args:
            resource_code: The resource code/identifier
            resource_data: Resource data from API response
        """
        if resource_code not in self.data['resources']:
            self.data['resources'][resource_code] = {
                'code': resource_code,
                'name': resource_data.get('name', resource_code),
                'first_discovered': datetime.now().isoformat(),
                'harvest_attempts': 0,
                'successful_harvests': 0,
                'estimated_skill_required': None,
                'estimated_yield': [],
                'last_updated': datetime.now().isoformat(),
                'api_data': self._sanitize_object(resource_data)
            }
        else:
            # Update existing resource with API data
            resource_info = self.data['resources'][resource_code]
            resource_info['last_updated'] = datetime.now().isoformat()
            resource_info['api_data'] = self._sanitize_object(resource_data)
            
            # Update name if it's better than current
            if resource_data.get('name') and resource_data['name'] != resource_code:
                resource_info['name'] = resource_data['name']
        
        # Update learning stats
        self.data['learning_stats']['resources_discovered'] = len(self.data['resources'])
        self.logger.debug(f"📚 Learned resource: {resource_code}")

    def get_all_known_resource_codes(self) -> List[str]:
        """
        Get all known resource codes from the knowledge base.
        
        Returns:
            List of resource codes that have been discovered
        """
        return list(self.data.get('resources', {}).keys())

    def _sanitize_object(self, obj):
        """
        Recursively sanitize an object to remove DropSchema instances and other non-serializable objects.
        """
        if obj is None:
            return obj
        elif hasattr(obj, '__class__'):
            class_name = str(obj.__class__)
            
            # Handle enum objects (like MapContentType) - convert to string value
            if hasattr(obj, 'value') and hasattr(obj, '__class__') and 'Enum' in str(obj.__class__.__bases__):
                return obj.value
            
            # Check for any API client objects that can't be serialized
            if any(schema in class_name for schema in ['DropSchema', 'Schema', 'Response']):
                if 'DropSchema' in class_name:
                    # Convert DropSchema to dict
                    return {
                        'code': getattr(obj, 'code', None),
                        'quantity': getattr(obj, 'quantity', 0)
                    }
                else:
                    # For other schemas, try to extract basic attributes or skip
                    try:
                        if hasattr(obj, 'to_dict'):
                            return obj.to_dict()
                        elif hasattr(obj, '__dict__'):
                            # Extract only basic attributes
                            basic_attrs = {}
                            for attr, value in obj.__dict__.items():
                                if not attr.startswith('_') and isinstance(value, (str, int, float, bool, type(None))):
                                    basic_attrs[attr] = value
                            return basic_attrs if basic_attrs else None
                        else:
                            return None
                    except Exception:
                        return None
        
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                sanitized_value = self._sanitize_object(value)
                if sanitized_value is not None or value is None:
                    sanitized[key] = sanitized_value
            return sanitized
        elif isinstance(obj, list):
            return [self._sanitize_object(item) for item in obj if self._sanitize_object(item) is not None or item is None]
        elif isinstance(obj, tuple):
            sanitized_items = [self._sanitize_object(item) for item in obj if self._sanitize_object(item) is not None or item is None]
            return tuple(sanitized_items)
        else:
            return obj

    def learn_effect(self, effect_name: str, effect_data: Dict) -> None:
        """
        Learn about an effect from API data.
        
        Args:
            effect_name: Name of the effect
            effect_data: Effect data from the API
        """
        try:
            if 'effects' not in self.data:
                self.data['effects'] = {}
            
            # Store sanitized effect data
            sanitized_data = self._sanitize_object(effect_data)
            self.data['effects'][effect_name] = sanitized_data
            
        except Exception as e:
            self.logger.debug(f"Failed to learn effect {effect_name}: {e}")

    def learn_xp_effects_analysis(self, xp_effects: Dict) -> None:
        """
        Store the XP effects analysis by skill.
        
        Args:
            xp_effects: Dictionary mapping skills to their XP-granting effects
        """
        try:
            self.data['xp_effects_analysis'] = xp_effects
            
            # Update learning stats
            if 'learning_stats' not in self.data:
                self.data['learning_stats'] = {}
            
            total_xp_effects = sum(len(effects) for effects in xp_effects.values())
            self.data['learning_stats']['total_xp_effects_learned'] = total_xp_effects
            self.data['learning_stats']['skills_with_xp_effects'] = len(xp_effects)
            
        except Exception as e:
            self.logger.debug(f"Failed to store XP effects analysis: {e}")
    
    def get_combat_statistics(self) -> Dict[str, Dict]:
        """
        Generate combat statistics from monster combat results.
        
        Returns:
            Dictionary mapping monster codes to their combat statistics
        """
        combat_stats = {}
        
        if 'monsters' not in self.data:
            return combat_stats
        
        for monster_code, monster_info in self.data['monsters'].items():
            combat_results = monster_info.get('combat_results', [])
            
            if not combat_results:
                continue
            
            # Calculate statistics for this monster
            total_combats = len(combat_results)
            wins = sum(1 for r in combat_results if r.get('result') == 'win')
            losses = sum(1 for r in combat_results if r.get('result') == 'loss')
            
            combat_stats[monster_code] = {
                'total_combats': total_combats,
                'wins': wins,
                'losses': losses,
                'win_rate': wins / total_combats if total_combats > 0 else 0,
                'combat_results': combat_results  # Include full results for recent analysis
            }
        
        return combat_stats
    
    def get_resource_data(self, resource_code: str, client=None) -> Optional[Dict]:
        """
        Get resource data from knowledge base, with API fallback if not found.
        
        Args:
            resource_code: Resource code to look up
            client: API client for fallback (optional)
            
        Returns:
            Resource data dictionary or None if not found
        """
        # Check if we already have the resource data
        if resource_code in self.data['resources']:
            return self.data['resources'][resource_code]
        
        # If not found and client provided, fetch from API
        if client:
            try:
                self.logger.info(f"📊 Fetching {resource_code} data from API...")
                response = get_resource_api(code=resource_code, client=client)
                
                if response:
                    resource = response.data
                    # Store the resource data for future use
                    resource_data = {
                        'code': resource.code,
                        'name': getattr(resource, 'name', resource.code),
                        'skill': getattr(resource, 'skill', 'unknown'),
                        'level': getattr(resource, 'level', 1),
                        'drops': getattr(resource, 'drops', []),
                        'first_discovered': datetime.now().isoformat(),
                        'harvest_attempts': 0,
                        'successful_harvests': 0,
                        'estimated_skill_required': getattr(resource, 'level', 1),
                        'estimated_yield': []
                    }
                    
                    # Store in knowledge base
                    self.data['resources'][resource_code] = resource_data
                    self.save()
                    
                    self.logger.info(f"✅ Added {resource_code} (skill: {resource_data['skill']}, level: {resource_data['level']}) to knowledge base")
                    return resource_data
                else:
                    self.logger.warning(f"❓ Resource {resource_code} not found in API")
            except Exception as e:
                self.logger.error(f"Failed to fetch resource data from API: {e}")
        
        return None
    
    def get_item_data(self, item_code: str, client=None) -> Optional[Dict]:
        """
        Get item data from knowledge base, with API fallback if not found.
        
        Args:
            item_code: Item code to look up
            client: API client for fallback (optional)
            
        Returns:
            Item data dictionary or None if not found
        """
        # Check if we already have the item data
        if item_code in self.data['items']:
            return self.data['items'][item_code]
        
        # If not found and client provided, fetch from API
        if client:
            try:
                self.logger.info(f"📊 Fetching {item_code} data from API...")
                response = get_item_api(code=item_code, client=client)
                
                if response:
                    item = response.data
                    # Store the item data for future use
                    item_data = {
                        'code': item.code,
                        'name': getattr(item, 'name', item.code),
                        'type': getattr(item, 'type', 'unknown'),
                        'subtype': getattr(item, 'subtype', ''),
                        'level': getattr(item, 'level', 1),
                        'effects': self._sanitize_object(getattr(item, 'effects', [])),
                        'description': getattr(item, 'description', ''),
                        'tradeable': getattr(item, 'tradeable', False),
                        'craft': self._sanitize_object(getattr(item, 'craft', None)),
                        'first_discovered': datetime.now().isoformat(),
                        'discovery_count': 1,
                        'sources': [],
                        'uses': [],
                        'market_data': {
                            'min_price': None,
                            'max_price': None,
                            'avg_price': None,
                            'price_history': []
                        }
                    }
                    
                    # Store in knowledge base
                    self.data['items'][item_code] = item_data
                    self.save()
                    
                    self.logger.info(f"✅ Added {item_code} (type: {item_data['type']}, level: {item_data['level']}) to knowledge base")
                    return item_data
                else:
                    self.logger.warning(f"❓ Item {item_code} not found in API")
            except Exception as e:
                self.logger.error(f"Failed to fetch item data from API: {e}")
        
        return None
    
    def get_npc_data(self, npc_code: str, client=None) -> Optional[Dict]:
        """
        Get NPC data from knowledge base, with API fallback if not found.
        
        Args:
            npc_code: NPC code to look up
            client: API client for fallback (optional)
            
        Returns:
            NPC data dictionary or None if not found
        """
        # Check if we already have the NPC data
        if npc_code in self.data['npcs']:
            return self.data['npcs'][npc_code]
        
        # If not found and client provided, fetch from API
        if client:
            try:
                self.logger.info(f"📊 Fetching {npc_code} data from API...")
                response = get_npc_api(code=npc_code, client=client)
                
                if response:
                    npc = response.data
                    # Store the NPC data for future use
                    npc_data = {
                        'code': npc.code,
                        'name': getattr(npc, 'name', npc.code),
                        'type': getattr(npc, 'type', 'unknown'),
                        'subtype': getattr(npc, 'subtype', ''),
                        'description': getattr(npc, 'description', ''),
                        'services': self._sanitize_object(getattr(npc, 'services', [])),
                        'first_discovered': datetime.now().isoformat(),
                        'interaction_count': 0,
                        'dialogue_options': [],
                        'trade_history': []
                    }
                    
                    # Store in knowledge base
                    self.data['npcs'][npc_code] = npc_data
                    self.save()
                    
                    self.logger.info(f"✅ Added {npc_code} (type: {npc_data['type']}) to knowledge base")
                    return npc_data
                else:
                    self.logger.warning(f"❓ NPC {npc_code} not found in API")
            except Exception as e:
                self.logger.error(f"Failed to fetch NPC data from API: {e}")
        
        return None
    
    def get_recipe_chain(self, item_code: str) -> List[Dict]:
        """
        Get the complete recipe chain for an item, traversing all dependencies.
        
        Args:
            item_code: The item to find the recipe chain for
            
        Returns:
            List of recipe steps from final item back to raw materials
        """
        chain = []
        visited = set()  # Prevent infinite loops
        
        def _traverse_recipe(current_item):
            if current_item in visited:
                return
            visited.add(current_item)
            
            # Get item data
            item_data = self.data.get('items', {}).get(current_item)
            if not item_data:
                return
                
            craft_data = item_data.get('craft')
            if not craft_data:
                # This is a raw material (no craft recipe)
                chain.append({
                    'item': current_item,
                    'type': 'raw_material',
                    'subtype': item_data.get('subtype'),
                    'skill': None,
                    'level': item_data.get('level', 1),
                    'quantity': 1
                })
                return
            
            # This is a craftable item
            chain.append({
                'item': current_item,
                'type': 'craftable',
                'skill': craft_data.get('skill'),
                'level': craft_data.get('level', 1),
                'quantity': craft_data.get('quantity', 1),
                'materials': craft_data.get('items', [])
            })
            
            # Traverse each material requirement
            for material in craft_data.get('items', []):
                material_code = material.get('code')
                if material_code:
                    _traverse_recipe(material_code)
        
        _traverse_recipe(item_code)
        return chain
    
    def get_resource_for_material(self, material_code: str) -> Optional[str]:
        """
        Find the resource that produces a given material.
        
        Args:
            material_code: The material item code
            
        Returns:
            Resource code that produces this material, or None if not found
        """
        # Check if the material itself is a raw material with mining/woodcutting/etc subtype
        item_data = self.data.get('items', {}).get(material_code)
        if item_data:
            craft_data = item_data.get('craft')
            subtype = item_data.get('subtype', '')
            
            # If craft is null and subtype indicates it's gathered from resources
            if craft_data is None and subtype in ['mining', 'woodcutting', 'fishing']:
                # Look for a resource with a similar name pattern
                resource_pattern = f"{material_code.replace('_ore', '_rocks').replace('_wood', '_tree').replace('_fish', '_spot')}"
                
                # Check if there's a resource with this pattern
                resources = self.data.get('resources', {})
                for resource_code in resources:
                    if (resource_code.startswith(material_code.split('_')[0]) and 
                        resources[resource_code].get('skill_required') == subtype):
                        return resource_code
                
                # Direct pattern matching
                if resource_pattern in resources:
                    return resource_pattern
        
        # Search through resources to find which one drops this material
        resources = self.data.get('resources', {})
        for resource_code, resource_info in resources.items():
            # Check drops from API data
            api_data = resource_info.get('api_data', {})
            drops = api_data.get('drops', [])
            
            for drop in drops:
                if isinstance(drop, dict) and drop.get('code') == material_code:
                    return resource_code
        
        return None
    
    def get_raw_materials_needed(self, item_code: str, quantity: int = 1) -> Dict[str, int]:
        """
        Calculate all raw materials needed to craft an item, following the complete recipe chain.
        
        Args:
            item_code: The item to craft
            quantity: How many of the item to craft
            
        Returns:
            Dictionary of {material_code: total_quantity_needed}
        """
        raw_materials = {}
        
        def _calculate_materials(current_item, needed_quantity):
            item_data = self.data.get('items', {}).get(current_item)
            if not item_data:
                return
                
            craft_data = item_data.get('craft')
            if not craft_data:
                # This is a raw material
                if current_item in raw_materials:
                    raw_materials[current_item] += needed_quantity
                else:
                    raw_materials[current_item] = needed_quantity
                return
            
            # This is craftable - calculate material requirements
            for material in craft_data.get('items', []):
                material_code = material.get('code')
                material_quantity = material.get('quantity', 1)
                total_needed = material_quantity * needed_quantity
                
                if material_code:
                    _calculate_materials(material_code, total_needed)
        
        _calculate_materials(item_code, quantity)
        return raw_materials