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
    
    def __init__(self, filename=f"{DATA_PREFIX}/knowledge.yaml"):
        """Initialize the knowledge base with GOAP data structure."""
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
                'last_learning_session': None,
                'learning_version': '1.0'
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
            content_type: Type of content ('monster', 'resource', etc.)
            content_code: Code/identifier of the content
            x: X coordinate
            y: Y coordinate  
            content_data: Additional content data from API
        """
        if content_type == 'monster':
            self._learn_monster_discovery(content_code, x, y, content_data or {})
        elif content_type == 'resource':
            self._learn_resource_discovery(content_code, x, y, content_data or {})
            
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
            combat_record.update({
                'turns': fight_data.get('turns', 0),
                'drops': fight_data.get('drops', []),
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