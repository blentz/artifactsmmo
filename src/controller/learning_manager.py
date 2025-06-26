"""
Learning Management System

This module provides YAML-configurable learning and optimization services,
replacing hardcoded learning logic in the AI controller.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.yaml_data import YamlData
from src.game.globals import DATA_PREFIX


class LearningManager:
    """
    YAML-configurable learning and knowledge management system.
    
    Handles learning from gameplay, optimization suggestions, and insights generation
    using configuration-driven behavior patterns.
    """
    
    def __init__(self, knowledge_base, map_state, config_file: str = None):
        """Initialize learning manager with dependencies."""
        self.logger = logging.getLogger(__name__)
        self.knowledge_base = knowledge_base
        self.map_state = map_state
        
        # Load configuration
        if config_file is None:
            config_file = f"{DATA_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load learning configuration from YAML."""
        try:
            thresholds = self.config_data.data.get('thresholds', {})
            
            # Load learning thresholds with defaults
            self.min_monsters_for_recommendations = thresholds.get('min_monsters_for_recommendations', 3)
            self.min_locations_for_exploration = thresholds.get('min_locations_for_exploration', 20)
            self.good_success_rate_threshold = thresholds.get('good_success_rate_threshold', 0.7)
            self.dangerous_success_rate_threshold = thresholds.get('dangerous_success_rate_threshold', 0.3)
            self.optimization_distance_radius = thresholds.get('optimization_distance_radius', 20)
            
            self.logger.debug(f"Loaded learning configuration: monsters_threshold={self.min_monsters_for_recommendations}, "
                            f"locations_threshold={self.min_locations_for_exploration}")
            
        except Exception as e:
            self.logger.error(f"Failed to load learning configuration: {e}")
            # Use hardcoded defaults as fallback
            self.min_monsters_for_recommendations = 3
            self.min_locations_for_exploration = 20
            self.good_success_rate_threshold = 0.7
            self.dangerous_success_rate_threshold = 0.3
            self.optimization_distance_radius = 20
    
    def get_learning_insights(self) -> Dict:
        """
        Get insights and statistics about what the AI has learned.
        
        Returns:
            Dictionary containing learning statistics and insights
        """
        try:
            summary = self.knowledge_base.get_knowledge_summary(self.map_state)
            learning_stats = self.knowledge_base.get_learning_stats()
            
            insights = {
                'knowledge_summary': summary,
                'learning_stats': learning_stats,
                'recommendations': []
            }
            
            # Add intelligent recommendations based on learned data
            if summary['monsters_discovered'] == 0:
                insights['recommendations'].append("Explore more areas to discover monsters for combat")
            elif summary['monsters_discovered'] < self.min_monsters_for_recommendations:
                insights['recommendations'].append("Continue exploring to find more monster varieties")
                
            if summary['total_locations_discovered'] < self.min_locations_for_exploration:
                insights['recommendations'].append("Expand exploration radius to learn about more locations")
                
            return insights
            
        except Exception as e:
            self.logger.warning(f"Error getting learning insights: {e}")
            return {'error': str(e)}
    
    def optimize_with_knowledge(self, character_state, goal_type: str = None) -> Dict[str, Any]:
        """
        Use learned knowledge to optimize planning and decision making.
        
        Args:
            character_state: Current character state
            goal_type: Type of goal to optimize for ('combat', 'exploration', 'resources')
            
        Returns:
            Dictionary with optimization suggestions
        """
        try:
            if not character_state:
                return {'error': 'No character state available'}
                
            char_level = character_state.data.get('level', 1)
            current_x = character_state.data.get('x', 0)
            current_y = character_state.data.get('y', 0)
            
            optimizations = {
                'goal_type': goal_type,
                'character_level': char_level,
                'current_position': (current_x, current_y),
                'suggestions': []
            }
            
            if goal_type == 'combat' or goal_type is None:
                # Combat optimization using configuration-driven thresholds
                combat_suggestions = self._generate_combat_optimizations(
                    char_level, current_x, current_y
                )
                optimizations['suggestions'].extend(combat_suggestions)
            
            if goal_type == 'exploration' or goal_type is None:
                # Exploration optimization using MapState
                exploration_suggestions = self._generate_exploration_optimizations()
                optimizations['suggestions'].extend(exploration_suggestions)
                
            return optimizations
            
        except Exception as e:
            self.logger.warning(f"Error optimizing with knowledge: {e}")
            return {'error': str(e)}
    
    def _generate_combat_optimizations(self, char_level: int, current_x: int, current_y: int) -> List[Dict]:
        """Generate combat-related optimization suggestions."""
        suggestions = []
        
        try:
            # Use configurable distance radius for monster search
            known_monsters = self.knowledge_base.find_suitable_monsters(
                map_state=self.map_state,
                character_level=char_level,
                level_range=2,
                max_distance=self.optimization_distance_radius,
                current_x=current_x,
                current_y=current_y
            )
            
            if known_monsters:
                # Find monsters with good success rates using configurable threshold
                good_targets = [m for m in known_monsters 
                              if m.get('success_rate', 0) > self.good_success_rate_threshold]
                
                if good_targets:
                    best_target = good_targets[0]
                    suggestions.append({
                        'type': 'combat_target',
                        'description': f"High success rate target: {best_target['monster_code']} at {best_target['location']}",
                        'success_rate': best_target['success_rate'],
                        'location': best_target['location']
                    })
                
                # Warn about dangerous monsters using configurable threshold
                dangerous = [m for m in known_monsters 
                           if m.get('success_rate', 1) < self.dangerous_success_rate_threshold]
                
                if dangerous:
                    suggestions.append({
                        'type': 'combat_warning',
                        'description': f"Avoid dangerous monsters: {[m['monster_code'] for m in dangerous[:3]]}",
                        'dangerous_monsters': dangerous[:3]
                    })
                    
        except Exception as e:
            self.logger.warning(f"Error generating combat optimizations: {e}")
            
        return suggestions
    
    def _generate_exploration_optimizations(self) -> List[Dict]:
        """Generate exploration-related optimization suggestions."""
        suggestions = []
        
        try:
            # Exploration optimization using MapState
            total_locations = 0
            if self.map_state and hasattr(self.map_state, 'data'):
                total_locations = len(self.map_state.data)
                
            # Use configurable threshold for exploration recommendations
            if total_locations < self.min_locations_for_exploration:
                suggestions.append({
                    'type': 'exploration',
                    'description': f"Explore more areas (visited {total_locations} locations so far)",
                    'recommended_action': 'systematic_exploration'
                })
                
        except Exception as e:
            self.logger.warning(f"Error generating exploration optimizations: {e}")
            
        return suggestions
    
    def find_known_monsters_nearby(self, character_state, max_distance: int = 15, 
                                 character_level: int = None, level_range: int = 2) -> Optional[List[Dict]]:
        """
        Find known monster locations near the character using learned knowledge and MapState.
        
        Args:
            character_state: Current character state
            max_distance: Maximum distance to search
            character_level: Character level for level filtering
            level_range: Acceptable level range for monsters
            
        Returns:
            List of monster location info dictionaries or None
        """
        if not character_state:
            return None
            
        try:
            current_x = character_state.data.get('x', 0)
            current_y = character_state.data.get('y', 0)
            char_level = character_level or character_state.data.get('level', 1)
            
            # Use integrated knowledge base with MapState
            suitable_monsters = self.knowledge_base.find_suitable_monsters(
                map_state=self.map_state,
                character_level=char_level,
                level_range=level_range,
                max_distance=max_distance,
                current_x=current_x,
                current_y=current_y
            )
            
            return suitable_monsters if suitable_monsters else None
            
        except Exception as e:
            self.logger.warning(f"Error finding known monsters nearby: {e}")
            return None
    
    def reload_configuration(self) -> None:
        """Reload learning configuration from YAML."""
        # Force reload from disk
        self.config_data.data = self.config_data.load() or {}
        self._load_configuration()
        self.logger.info("Learning configuration reloaded")