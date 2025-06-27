"""
Knowledge Base for AI Player Learning

This module extends the existing WorldState system to add learning capabilities
while integrating with the existing MapState and CharacterState systems.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from src.lib.goap_data import GoapData
from src.game.globals import DATA_PREFIX


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
        monster_info['encounter_count'] += 1
        
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

    def _sanitize_object(self, obj):
        """
        Recursively sanitize an object to remove DropSchema instances and other non-serializable objects.
        """
        if obj is None:
            return obj
        elif hasattr(obj, '__class__'):
            class_name = str(obj.__class__)
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