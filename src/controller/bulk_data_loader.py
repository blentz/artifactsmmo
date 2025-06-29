"""
Bulk Data Loader for ArtifactsMMO AI Player

This module loads complete game world information using bulk API calls to ensure
the AI player has comprehensive knowledge of all maps, workshops, resources, and NPCs
from the start, eliminating discovery dependencies.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from artifactsmmo_api_client.api.maps.get_all_map import sync as get_all_maps_api
from artifactsmmo_api_client.api.npcs.get_all_npc import sync as get_all_npcs_api
from artifactsmmo_api_client.api.items.get_all_item import sync as get_all_items_api
from artifactsmmo_api_client.api.resources.get_all_resource import sync as get_all_resources_api
from artifactsmmo_api_client.api.monsters.get_all_monster import sync as get_all_monsters_api


class BulkDataLoader:
    """
    Loads complete game world data using bulk API calls and populates
    the knowledge base and map state with comprehensive information.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def load_all_game_data(self, client, map_state, knowledge_base) -> bool:
        """
        Load all game world data using bulk API calls.
        
        Args:
            client: API client for making requests
            map_state: MapState instance to populate with map data
            knowledge_base: KnowledgeBase instance to populate with game knowledge
            
        Returns:
            True if loading was successful, False otherwise
        """
        try:
            self.logger.info("🌍 Starting bulk game data loading...")
            
            # Load maps with all location information
            maps_loaded = self._load_all_maps(client, map_state, knowledge_base)
            if not maps_loaded:
                self.logger.error("Failed to load map data")
                return False
                
            # Load NPCs (includes workshops and other facilities)  
            npcs_loaded = self._load_all_npcs(client, knowledge_base)
            if not npcs_loaded:
                self.logger.error("Failed to load NPC data")
                return False
                
            # Load resources information
            resources_loaded = self._load_all_resources(client, knowledge_base)
            if not resources_loaded:
                self.logger.error("Failed to load resource data")
                return False
                
            # Load monsters information
            monsters_loaded = self._load_all_monsters(client, knowledge_base)
            if not monsters_loaded:
                self.logger.error("Failed to load monster data")
                return False
                
            # Load items information (for crafting knowledge)
            items_loaded = self._load_all_items(client, knowledge_base)
            if not items_loaded:
                self.logger.error("Failed to load item data")
                return False
                
            self.logger.info("✅ Bulk game data loading completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Bulk data loading failed: {e}")
            return False
    
    def _load_all_maps(self, client, map_state, knowledge_base) -> bool:
        """Load all map locations into map state and knowledge base."""
        try:
            self.logger.info("📍 Loading all map locations...")
            
            # Get all maps with pagination
            page = 1
            total_locations = 0
            workshop_count = 0
            
            while True:
                response = get_all_maps_api(client=client, page=page, size=100)
                if not response or not response.data:
                    break
                    
                for location in response.data:
                    x, y = location.x, location.y
                    
                    # Create location data for map state
                    location_data = {
                        'x': x,
                        'y': y,
                        'content': None,
                        'discovered_via': 'bulk_api',
                        'last_scanned': datetime.now().isoformat()
                    }
                    
                    # Add content information if present
                    if hasattr(location, 'content') and location.content:
                        content_data = {
                            'code': location.content.code,
                            'type': getattr(location.content, 'type_', getattr(location.content, 'type', 'unknown'))
                        }
                        location_data['content'] = content_data
                        
                        # Check if this is a workshop/facility and add to knowledge base
                        if self._is_workshop_or_facility(location.content):
                            self._add_workshop_to_knowledge(knowledge_base, location.content, x, y)
                            workshop_count += 1
                    
                    # Store in map state
                    coord_key = f"{x},{y}"
                    map_state.data[coord_key] = location_data
                    total_locations += 1
                
                # Check if we have more pages
                if len(response.data) < 100:
                    break
                page += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
            
            self.logger.info(f"📍 Loaded {total_locations} map locations, found {workshop_count} workshops/facilities")
            map_state.save()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load map data: {e}")
            return False
    
    def _load_all_npcs(self, client, knowledge_base) -> bool:
        """Load all NPCs into knowledge base."""
        try:
            self.logger.info("👥 Loading all NPCs...")
            
            page = 1
            npc_count = 0
            
            while True:
                response = get_all_npcs_api(client=client, page=page, size=100)
                if not response or not response.data:
                    break
                    
                for npc in response.data:
                    # Add NPC to knowledge base
                    if npc.code not in knowledge_base.data['npcs']:
                        knowledge_base.data['npcs'][npc.code] = {
                            'code': npc.code,
                            'name': getattr(npc, 'name', npc.code),
                            'npc_type': getattr(npc, 'type', 'unknown'),
                            'first_discovered': datetime.now().isoformat(),
                            'services': getattr(npc, 'services', []),
                            'trades': getattr(npc, 'trades', [])
                        }
                        npc_count += 1
                
                if len(response.data) < 100:
                    break
                page += 1
                time.sleep(0.1)
            
            self.logger.info(f"👥 Loaded {npc_count} NPCs")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load NPC data: {e}")
            return False
    
    def _load_all_resources(self, client, knowledge_base) -> bool:
        """Load all resources into knowledge base."""
        try:
            self.logger.info("🌿 Loading all resources...")
            
            page = 1
            resource_count = 0
            
            while True:
                response = get_all_resources_api(client=client, page=page, size=100)
                if not response or not response.data:
                    break
                    
                for resource in response.data:
                    if resource.code not in knowledge_base.data['resources']:
                        knowledge_base.data['resources'][resource.code] = {
                            'code': resource.code,
                            'name': getattr(resource, 'name', resource.code),
                            'resource_type': getattr(resource, 'type', 'unknown'),
                            'skill_required': getattr(resource, 'skill', 'unknown'),
                            'level_required': getattr(resource, 'level', 1),
                            'first_discovered': datetime.now().isoformat(),
                            'harvest_attempts': 0,
                            'total_yield': 0
                        }
                        resource_count += 1
                
                if len(response.data) < 100:
                    break
                page += 1
                time.sleep(0.1)
            
            self.logger.info(f"🌿 Loaded {resource_count} resources")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load resource data: {e}")
            return False
    
    def _load_all_monsters(self, client, knowledge_base) -> bool:
        """Load all monsters into knowledge base."""
        try:
            self.logger.info("👹 Loading all monsters...")
            
            page = 1
            monster_count = 0
            
            while True:
                response = get_all_monsters_api(client=client, page=page, size=100)
                if not response or not response.data:
                    break
                    
                for monster in response.data:
                    if monster.code not in knowledge_base.data['monsters']:
                        knowledge_base.data['monsters'][monster.code] = {
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
                        monster_count += 1
                
                if len(response.data) < 100:
                    break
                page += 1
                time.sleep(0.1)
            
            self.logger.info(f"👹 Loaded {monster_count} monsters")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load monster data: {e}")
            return False
    
    def _load_all_items(self, client, knowledge_base) -> bool:
        """Load all items into knowledge base."""
        try:
            self.logger.info("⚔️ Loading all items...")
            
            page = 1
            item_count = 0
            
            while True:
                response = get_all_items_api(client=client, page=page, size=100)
                if not response or not response.data:
                    break
                    
                for item in response.data:
                    if item.code not in knowledge_base.data['items']:
                        knowledge_base.data['items'][item.code] = {
                            'code': item.code,
                            'name': getattr(item, 'name', item.code),
                            'item_type': getattr(item, 'type', 'unknown'),
                            'level': getattr(item, 'level', 1),
                            'tradeable': getattr(item, 'tradeable', False),
                            'craft_data': getattr(item, 'craft', None),
                            'effects': getattr(item, 'effects', []),
                            'first_discovered': datetime.now().isoformat(),
                            'discovery_count': 1,
                            'last_seen': datetime.now().isoformat(),
                            'sources': [],
                            'uses': []
                        }
                        item_count += 1
                
                if len(response.data) < 100:
                    break
                page += 1
                time.sleep(0.1)
            
            self.logger.info(f"⚔️ Loaded {item_count} items")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load item data: {e}")
            return False
    
    def _is_workshop_or_facility(self, content) -> bool:
        """Check if content represents a workshop or facility."""
        content_code = getattr(content, 'code', '').lower()
        content_type = getattr(content, 'type_', getattr(content, 'type', '')).lower()
        
        # Workshop patterns
        workshop_patterns = ['crafting', 'smithy', 'workshop', 'forge', 'anvil']
        workshop_codes = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy', 'mining', 'woodcutting']
        
        # Facility patterns  
        facility_patterns = ['bank', 'exchange', 'market', 'shop', 'store']
        
        return (content_type in ['workshop', 'facility'] or
                any(pattern in content_code for pattern in workshop_patterns + facility_patterns) or
                content_code in workshop_codes)
    
    def _add_workshop_to_knowledge(self, knowledge_base, content, x: int, y: int):
        """Add workshop/facility to knowledge base."""
        content_code = getattr(content, 'code', '')
        content_type = getattr(content, 'type_', getattr(content, 'type', 'unknown'))
        
        # Determine if it's a workshop or facility
        if (content_type == 'workshop' or 
            any(pattern in content_code.lower() for pattern in ['crafting', 'smithy', 'workshop', 'forge']) or
            content_code.lower() in ['mining', 'woodcutting', 'weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']):
            category = 'workshops'
        else:
            category = 'facilities'
        
        if content_code not in knowledge_base.data[category]:
            knowledge_base.data[category][content_code] = {
                'code': content_code,
                'name': getattr(content, 'name', content_code),
                'facility_type': content_type,
                'x': x,
                'y': y,
                'craft_skill': self._determine_craft_skill(content_code),
                'first_discovered': datetime.now().isoformat(),
                'usage_count': 0,
                'encounter_count': 1,
                'last_seen': datetime.now().isoformat()
            }
            
            # Update learning stats
            if category == 'workshops':
                knowledge_base.data['learning_stats']['unique_workshops_found'] += 1
            else:
                knowledge_base.data['learning_stats']['unique_facilities_found'] += 1
    
    def _determine_craft_skill(self, workshop_code: str) -> str:
        """Determine the crafting skill for a workshop."""
        workshop_code = workshop_code.lower()
        if 'weapon' in workshop_code:
            return 'weaponcrafting'
        elif 'gear' in workshop_code:
            return 'gearcrafting'
        elif 'jewelry' in workshop_code:
            return 'jewelrycrafting'
        elif 'cooking' in workshop_code:
            return 'cooking'
        elif 'alchemy' in workshop_code:
            return 'alchemy'
        elif 'mining' in workshop_code:
            return 'mining'
        elif 'woodcutting' in workshop_code:
            return 'woodcutting'
        else:
            return 'unknown'