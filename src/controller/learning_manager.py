"""
Learning Management System

This module provides YAML-configurable learning and optimization services,
replacing hardcoded learning logic in the AI controller.
"""

import logging
from typing import Any, Dict, List, Optional

from artifactsmmo_api_client.api.effects.get_all_effects_effects_get import sync as get_all_effects_api
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items_api
from artifactsmmo_api_client.api.maps.get_all_maps_maps_get import sync as get_all_maps_api
from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import sync as get_all_monsters_api
from artifactsmmo_api_client.api.np_cs.get_all_npcs_npcs_details_get import sync as get_all_npcs_api

# API client imports
from artifactsmmo_api_client.api.resources.get_all_resources_resources_get import sync as get_all_resources_api

from src.controller.capability_analyzer import CapabilityAnalyzer
from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


class LearningManager:
    """
    YAML-configurable learning and knowledge management system.
    
    Handles learning from gameplay, optimization suggestions, and insights generation
    using configuration-driven behavior patterns.
    """
    
    def __init__(self, knowledge_base, map_state, client=None, config_file: str = None):
        """Initialize learning manager with dependencies."""
        self.logger = logging.getLogger(__name__)
        self.knowledge_base = knowledge_base
        self.map_state = map_state
        
        # Initialize capability analyzer if client provided
        self.capability_analyzer = None
        if client:
            self.capability_analyzer = CapabilityAnalyzer(client)
        
        # Load configuration - using clean templates for testing
        if config_file is None:
            config_file = f"{CONFIG_PREFIX}/goal_templates.yaml"
        
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
    
    def learn_from_capability_analysis(self, resource_code: str = None, item_code: str = None) -> Dict:
        """
        Learn about capabilities of resources and items for upgrade planning.
        
        Args:
            resource_code: Resource to analyze (e.g., "ash_tree")
            item_code: Item to analyze (e.g., "wooden_staff")
            
        Returns:
            Dictionary with capability analysis results
        """
        if not self.capability_analyzer:
            self.logger.warning("Capability analyzer not available - client not provided")
            return {"error": "Capability analyzer not initialized"}
        
        try:
            learning_results = {
                "timestamp": None,
                "resource_analysis": None,
                "item_analysis": None
            }
            
            if resource_code:
                self.logger.info(f"🧠 Learning resource capabilities: {resource_code}")
                drops = self.capability_analyzer.analyze_resource_drops(resource_code)
                learning_results["resource_analysis"] = {
                    "resource_code": resource_code,
                    "drops": drops
                }
                
                # Store in knowledge base for future planning
                self.knowledge_base.learn_resource_capabilities(resource_code, drops)
            
            if item_code:
                self.logger.info(f"🧠 Learning item capabilities: {item_code}")
                capabilities = self.capability_analyzer.analyze_item_capabilities(item_code)
                learning_results["item_analysis"] = capabilities
                
                # Store in knowledge base for future planning
                self.knowledge_base.learn_item_capabilities(item_code, capabilities)
            
            return learning_results
            
        except Exception as e:
            self.logger.error(f"❌ Failed capability learning: {e}")
            return {"error": str(e)}
    
    def analyze_upgrade_chain(self, resource_code: str, target_item_code: str) -> Dict:
        """
        Analyze complete upgrade chain for planning multi-step goals.
        
        Args:
            resource_code: Starting resource (e.g., "ash_tree")
            target_item_code: Target item (e.g., "wooden_staff")
            
        Returns:
            Dictionary with upgrade chain analysis and viability
        """
        if not self.capability_analyzer:
            return {"error": "Capability analyzer not initialized"}
        
        try:
            self.logger.info(f"🔗 Analyzing upgrade chain: {resource_code} → {target_item_code}")
            chain_analysis = self.capability_analyzer.analyze_upgrade_chain(resource_code, target_item_code)
            
            # Store learning results for future planning
            if chain_analysis.get("viable"):
                self.knowledge_base.learn_upgrade_chain(resource_code, target_item_code, chain_analysis)
                
                # Generate specific goal recommendations
                for path in chain_analysis.get("paths", []):
                    self.logger.info(f"  ✅ Learned viable path: {path['resource']} → {path['intermediate']} → {path['target']}")
            
            return chain_analysis
            
        except Exception as e:
            self.logger.error(f"❌ Failed upgrade chain analysis: {e}")
            return {"error": str(e)}
    
    def evaluate_weapon_upgrade(self, current_weapon: str, potential_upgrade: str) -> Dict:
        """
        Evaluate if a weapon upgrade is worthwhile based on stats.
        
        Args:
            current_weapon: Current weapon code
            potential_upgrade: Potential upgrade weapon code
            
        Returns:
            Dictionary with upgrade evaluation and recommendation
        """
        if not self.capability_analyzer:
            return {"error": "Capability analyzer not initialized"}
        
        try:
            self.logger.info(f"⚔️ Evaluating weapon upgrade: {current_weapon} → {potential_upgrade}")
            comparison = self.capability_analyzer.compare_weapon_upgrades(current_weapon, potential_upgrade)
            
            # Store upgrade evaluation for future reference
            self.knowledge_base.learn_weapon_comparison(current_weapon, potential_upgrade, comparison)
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"❌ Failed weapon upgrade evaluation: {e}")
            return {"error": str(e)}
    
    def learn_all_resources_bulk(self, client) -> Dict:
        """
        Learn about all available resources efficiently using get_all_resource API.
        
        Args:
            client: API client for making requests
            
        Returns:
            Dictionary with learning results and statistics
        """
        try:
            self.logger.info("🔍 Learning all resources using get_all_resource API...")
            
            total_learned = 0
            resources_learned = []
            page = 1
            page_size = 100  # Large page size for efficiency
            
            while True:
                # Fetch one page of resources
                response = get_all_resources_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                # Process resources from this page
                for resource in response.data:
                    try:
                        resource_data = resource.to_dict() if hasattr(resource, 'to_dict') else resource.__dict__
                        resource_code = resource_data.get('code', 'unknown')
                        
                        self.knowledge_base.learn_resource(resource_code, resource_data)
                        resources_learned.append(resource_code)
                        total_learned += 1
                        
                    except Exception as resource_error:
                        self.logger.debug(f"Failed to process resource: {resource_error}")
                        continue
                
                # Check if there are more pages
                if len(response.data) < page_size:
                    break  # Last page reached
                    
                page += 1
            
            # Save the learned resources
            self.knowledge_base.save()
            
            self.logger.info(f"✅ Resource learning complete: learned {total_learned} resources")
            
            return {
                'success': True,
                'method_used': 'get_all_resource_api',
                'total_resources_learned': total_learned,
                'resources_learned': resources_learned,
                'message': f"Successfully learned {total_learned} resources using get_all_resource API"
            }
            
        except Exception as e:
            error_msg = f"Failed to learn resources: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'total_resources_learned': 0,
                'resources_learned': []
            }

    def learn_all_game_data_bulk(self, client) -> Dict:
        """
        Learn about all available game data efficiently using get_all_* APIs.
        
        This comprehensive method replaces inefficient map scanning with direct API queries
        for all major game content types.
        
        Args:
            client: API client for making requests
            
        Returns:
            Dictionary with comprehensive learning results and statistics
        """
        total_stats = {
            'resources': 0,
            'monsters': 0,
            'items': 0,
            'npcs': 0,
            'maps': 0,
            'effects': 0,
            'total': 0
        }
        
        results = {
            'success': True,
            'stats': total_stats,
            'details': {},
            'errors': []
        }
        
        try:
            # Learn all resources
            self.logger.info("📚 Learning all resources...")
            resource_result = self.learn_all_resources_bulk(client)
            total_stats['resources'] = resource_result.get('total_resources_learned', 0)
            results['details']['resources'] = resource_result
            if not resource_result.get('success'):
                results['errors'].append(f"Resources: {resource_result.get('error', 'Unknown error')}")
            
            # Learn all monsters
            self.logger.info("🐉 Learning all monsters...")
            monster_result = self._learn_all_monsters_bulk(client)
            total_stats['monsters'] = monster_result.get('total_monsters_learned', 0)
            results['details']['monsters'] = monster_result
            if not monster_result.get('success'):
                results['errors'].append(f"Monsters: {monster_result.get('error', 'Unknown error')}")
            
            # Learn all items
            self.logger.info("🛡️ Learning all items...")
            item_result = self._learn_all_items_bulk(client)
            total_stats['items'] = item_result.get('total_items_learned', 0)
            results['details']['items'] = item_result
            if not item_result.get('success'):
                results['errors'].append(f"Items: {item_result.get('error', 'Unknown error')}")
            
            # Learn all NPCs
            self.logger.info("👥 Learning all NPCs...")
            npc_result = self._learn_all_npcs_bulk(client)
            total_stats['npcs'] = npc_result.get('total_npcs_learned', 0)
            results['details']['npcs'] = npc_result
            if not npc_result.get('success'):
                results['errors'].append(f"NPCs: {npc_result.get('error', 'Unknown error')}")
            
            # Learn all maps
            self.logger.info("🗺️ Learning all map locations...")
            map_result = self._learn_all_maps_bulk(client)
            total_stats['maps'] = map_result.get('total_maps_learned', 0)
            results['details']['maps'] = map_result
            if not map_result.get('success'):
                results['errors'].append(f"Maps: {map_result.get('error', 'Unknown error')}")
            
            # Learn all effects for XP analysis
            self.logger.info("✨ Learning all effects for XP analysis...")
            effects_result = self.learn_all_effects_bulk(client)
            total_stats['effects'] = effects_result.get('total_effects_learned', 0)
            results['details']['effects'] = effects_result
            if not effects_result.get('success'):
                results['errors'].append(f"Effects: {effects_result.get('error', 'Unknown error')}")
            
            # Calculate total
            total_stats['total'] = sum(total_stats.values()) - total_stats['total']  # Subtract to avoid double counting
            
            # Update overall success based on individual results
            if results['errors']:
                results['success'] = False
                
            self.logger.info(f"✅ Bulk learning complete: {total_stats['total']} total items learned")
            self.logger.info(f"📊 Breakdown: {total_stats['resources']} resources, {total_stats['monsters']} monsters, "
                           f"{total_stats['items']} items, {total_stats['npcs']} NPCs, {total_stats['maps']} maps, "
                           f"{total_stats['effects']} effects")
            
            return results
            
        except Exception as e:
            error_msg = f"Failed bulk learning: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'stats': total_stats,
                'details': results.get('details', {}),
                'errors': results.get('errors', []) + [error_msg]
            }
    
    def _learn_all_monsters_bulk(self, client) -> Dict:
        """Learn all monsters using get_all_monster API."""
        try:
            total_learned = 0
            monsters_learned = []
            page = 1
            page_size = 100
            
            while True:
                response = get_all_monsters_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                for monster in response.data:
                    try:
                        monster_data = monster.to_dict() if hasattr(monster, 'to_dict') else monster.__dict__
                        monster_code = monster_data.get('code', 'unknown')
                        
                        # Learn monster discovery without specific location
                        self.knowledge_base._learn_monster_discovery(monster_code, 0, 0, monster_data)
                        monsters_learned.append(monster_code)
                        total_learned += 1
                        
                    except Exception as monster_error:
                        self.logger.debug(f"Failed to process monster: {monster_error}")
                        continue
                
                if len(response.data) < page_size:
                    break
                    
                page += 1
            
            self.knowledge_base.save()
            
            return {
                'success': True,
                'total_monsters_learned': total_learned,
                'monsters_learned': monsters_learned
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_monsters_learned': 0,
                'monsters_learned': []
            }
    
    def _learn_all_items_bulk(self, client) -> Dict:
        """Learn all items using get_all_item API."""
        try:
            total_learned = 0
            items_learned = []
            page = 1
            page_size = 100
            
            while True:
                response = get_all_items_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                for item in response.data:
                    try:
                        item_data = item.to_dict() if hasattr(item, 'to_dict') else item.__dict__
                        item_code = item_data.get('code', 'unknown')
                        
                        # Learn item discovery without specific location
                        self.knowledge_base._learn_item_discovery(item_code, 0, 0, item_data)
                        items_learned.append(item_code)
                        total_learned += 1
                        
                    except Exception as item_error:
                        self.logger.debug(f"Failed to process item: {item_error}")
                        continue
                
                if len(response.data) < page_size:
                    break
                    
                page += 1
            
            self.knowledge_base.save()
            
            return {
                'success': True,
                'total_items_learned': total_learned,
                'items_learned': items_learned
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_items_learned': 0,
                'items_learned': []
            }
    
    def _learn_all_npcs_bulk(self, client) -> Dict:
        """Learn all NPCs using get_all_npc API."""
        try:
            total_learned = 0
            npcs_learned = []
            page = 1
            page_size = 100
            
            while True:
                response = get_all_npcs_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                for npc in response.data:
                    try:
                        npc_data = npc.to_dict() if hasattr(npc, 'to_dict') else npc.__dict__
                        npc_code = npc_data.get('code', 'unknown')
                        
                        # Learn NPC discovery without specific location
                        self.knowledge_base._learn_npc_discovery(npc_code, 0, 0, npc_data)
                        npcs_learned.append(npc_code)
                        total_learned += 1
                        
                    except Exception as npc_error:
                        self.logger.debug(f"Failed to process NPC: {npc_error}")
                        continue
                
                if len(response.data) < page_size:
                    break
                    
                page += 1
            
            self.knowledge_base.save()
            
            return {
                'success': True,
                'total_npcs_learned': total_learned,
                'npcs_learned': npcs_learned
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_npcs_learned': 0,
                'npcs_learned': []
            }
    
    def _learn_all_maps_bulk(self, client) -> Dict:
        """Learn all map locations using get_all_map API."""
        try:
            total_learned = 0
            maps_learned = []
            page = 1
            page_size = 100
            
            while True:
                response = get_all_maps_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                for map_location in response.data:
                    try:
                        map_data = map_location.to_dict() if hasattr(map_location, 'to_dict') else map_location.__dict__
                        x = map_data.get('x', 0)
                        y = map_data.get('y', 0)
                        
                        # Store map location in map_state if available
                        if self.map_state:
                            location_key = f"{x},{y}"
                            self.map_state.data[location_key] = {
                                'x': x,
                                'y': y,
                                'content': map_data.get('content'),
                                'last_scanned': None,  # Mark as not yet scanned in detail
                                'discovered_via': 'bulk_api'
                            }
                        
                        # Learn about content if present
                        content = map_data.get('content')
                        if content:
                            content_type = content.get('type')
                            content_code = content.get('code')
                            if content_type and content_code:
                                self.knowledge_base.learn_from_content_discovery(
                                    content_type, content_code, x, y, content
                                )
                        
                        maps_learned.append(f"{x},{y}")
                        total_learned += 1
                        
                    except Exception as map_error:
                        self.logger.debug(f"Failed to process map location: {map_error}")
                        continue
                
                if len(response.data) < page_size:
                    break
                    
                page += 1
            
            # Save both knowledge base and map state
            self.knowledge_base.save()
            if self.map_state:
                self.map_state.save()
            
            return {
                'success': True,
                'total_maps_learned': total_learned,
                'maps_learned': maps_learned
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_maps_learned': 0,
                'maps_learned': []
            }

    def learn_all_effects_bulk(self, client) -> Dict:
        """
        Learn about all available effects efficiently using get_all_effect API.
        
        This enables XP effect analysis for skill leveling decisions by discovering
        what actions/items grant XP in specific skills.
        
        Args:
            client: API client for making requests
            
        Returns:
            Dictionary with effects learning results and XP effect analysis
        """
        try:
            self.logger.info("🔍 Learning all effects using get_all_effect API...")
            
            total_learned = 0
            effects_learned = []
            xp_effects = {}  # Track XP-granting effects by skill
            page = 1
            page_size = 100
            
            while True:
                # Fetch one page of effects
                response = get_all_effects_api(
                    client=client,
                    page=page,
                    size=page_size
                )
                
                if not response or not response.data:
                    break
                
                # Process effects from this page
                for effect in response.data:
                    try:
                        effect_data = effect.to_dict() if hasattr(effect, 'to_dict') else effect.__dict__
                        effect_name = effect_data.get('name', 'unknown')
                        
                        # Store effect data in knowledge base
                        self.knowledge_base.learn_effect(effect_name, effect_data)
                        effects_learned.append(effect_name)
                        total_learned += 1
                        
                        # Analyze if this effect grants XP in any skill
                        self._analyze_xp_effect(effect_data, xp_effects)
                        
                    except Exception as effect_error:
                        self.logger.debug(f"Failed to process effect: {effect_error}")
                        continue
                
                # Check if there are more pages
                if len(response.data) < page_size:
                    break  # Last page reached
                    
                page += 1
            
            # Save the learned effects and XP analysis
            self.knowledge_base.learn_xp_effects_analysis(xp_effects)
            self.knowledge_base.save()
            
            self.logger.info(f"✅ Effects learning complete: learned {total_learned} effects")
            self.logger.info(f"📊 XP Effects Analysis: {len(xp_effects)} skills have XP-granting effects")
            
            # Log skill XP sources for debugging
            for skill, sources in xp_effects.items():
                self.logger.debug(f"  {skill} XP sources: {len(sources)} effects")
            
            return {
                'success': True,
                'method_used': 'get_all_effect_api',
                'total_effects_learned': total_learned,
                'effects_learned': effects_learned,
                'xp_effects_by_skill': xp_effects,
                'skills_with_xp_effects': list(xp_effects.keys()),
                'message': f"Successfully learned {total_learned} effects using get_all_effect API"
            }
            
        except Exception as e:
            error_msg = f"Failed to learn effects: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'total_effects_learned': 0,
                'effects_learned': [],
                'xp_effects_by_skill': {},
                'skills_with_xp_effects': []
            }

    def _analyze_xp_effect(self, effect_data: Dict, xp_effects: Dict) -> None:
        """
        Analyze effect data to identify XP-granting effects for skills.
        
        Args:
            effect_data: Effect data from API
            xp_effects: Dictionary to store XP effects by skill
        """
        try:
            effect_name = effect_data.get('name', '').lower()
            
            # Look for XP-related keywords in effect name
            if 'xp' in effect_name:
                # Extract skill from effect name by finding known skills from knowledge base
                known_skills = self._get_known_skills_from_knowledge_base()
                
                for skill_keyword in known_skills:
                    if skill_keyword in effect_name:
                        if skill_keyword not in xp_effects:
                            xp_effects[skill_keyword] = []
                        
                        xp_effect_info = {
                            'effect_name': effect_data.get('name'),
                            'effect_description': effect_data.get('description', ''),
                            'effect_value': effect_data.get('value', 0)
                        }
                        xp_effects[skill_keyword].append(xp_effect_info)
                        break
                        
        except Exception as e:
            self.logger.debug(f"Error analyzing XP effect: {e}")

    def find_xp_sources_for_skill(self, skill: str) -> List[Dict]:
        """
        Find all known sources that grant XP for a specific skill.
        
        Args:
            skill: Skill name (e.g., 'weaponcrafting', 'mining')
            
        Returns:
            List of XP sources with effect information
        """
        try:
            if not self.knowledge_base or not hasattr(self.knowledge_base, 'data'):
                return []
            
            xp_effects = self.knowledge_base.data.get('xp_effects_analysis', {})
            skill_sources = xp_effects.get(skill, [])
            
            self.logger.info(f"🔍 Found {len(skill_sources)} XP sources for {skill} skill")
            for source in skill_sources:
                self.logger.debug(f"  {source.get('effect_name')}: {source.get('effect_description')}")
            
            return skill_sources
            
        except Exception as e:
            self.logger.warning(f"Error finding XP sources for {skill}: {e}")
            return []

    def _get_known_skills_from_knowledge_base(self) -> List[str]:
        """Get all known skills by scanning the knowledge base for skill-related data."""
        skills = set()
        
        try:
            if not self.knowledge_base or not hasattr(self.knowledge_base, 'data'):
                return []
            
            # Scan items for craft skills
            items = self.knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {}) or item_data.get('craft', {})
                if craft_data:
                    skill = craft_data.get('skill')
                    if skill and skill != 'unknown':
                        skills.add(skill)
            
            # Scan resources for related skills
            resources = self.knowledge_base.data.get('resources', {})
            for resource_code, resource_data in resources.items():
                skill = resource_data.get('skill')
                if skill:
                    skills.add(skill)
            
            # Scan monsters for combat skill
            monsters = self.knowledge_base.data.get('monsters', {})
            if monsters:
                skills.add('combat')
            
            # Scan workshops for associated skills
            workshops = self.knowledge_base.data.get('workshops', {})
            for workshop_code, workshop_data in workshops.items():
                craft_skill = workshop_data.get('craft_skill')
                if craft_skill:
                    skills.add(craft_skill)
            
            return sorted(list(skills))
            
        except Exception as e:
            self.logger.debug(f"Error getting known skills from knowledge base: {e}")
            return []

    def reload_configuration(self) -> None:
        """Reload learning configuration from YAML."""
        # Force reload from disk
        self.config_data.data = self.config_data.load() or {}
        self._load_configuration()
        self.logger.info("Learning configuration reloaded")