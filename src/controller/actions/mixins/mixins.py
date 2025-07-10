"""
Mixins for common action functionality

This module provides mixins that encapsulate common patterns found across
multiple action classes, reducing code duplication.

Note: CharacterDataMixin was removed for architecture compliance.
Actions should read character data from UnifiedStateContext instead of making direct API calls.
"""

from typing import Any, Dict, List, Optional, Tuple


class KnowledgeBaseSearchMixin:
    """Mixin for actions that search knowledge base with API fallback."""
    
    def search_knowledge_base_items(self, knowledge_base, item_type: str = None, 
                                   level_range: Tuple[int, int] = None) -> List[Dict]:
        """
        Search knowledge base for items.
        
        Args:
            knowledge_base: Knowledge base instance
            item_type: Optional item type filter
            level_range: Optional (min_level, max_level) tuple
            
        Returns:
            List of matching items
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return []
            
        items = knowledge_base.data.get('items', {})
        results = []
        
        for item_code, item_data in items.items():
            # Apply type filter
            if item_type and item_data.get('item_type', '').lower() != item_type.lower():
                continue
                
            # Apply level filter
            if level_range:
                item_level = item_data.get('level', 1)
                min_level, max_level = level_range
                if not (min_level <= item_level <= max_level):
                    continue
                    
            results.append({
                'code': item_code,
                'data': item_data
            })
            
        return results
    
    def search_knowledge_base_resources(self, knowledge_base, resource_code: str = None,
                                       skill_type: str = None) -> List[Dict]:
        """
        Search knowledge base for resources.
        
        Args:
            knowledge_base: Knowledge base instance
            resource_code: Optional specific resource code
            skill_type: Optional skill type filter
            
        Returns:
            List of matching resources
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return []
            
        resources = knowledge_base.data.get('resources', {})
        results = []
        
        for code, resource_data in resources.items():
            # Apply code filter
            if resource_code and code != resource_code:
                continue
                
            # Apply skill filter
            if skill_type and resource_data.get('skill_required', '') != skill_type:
                continue
                
            results.append({
                'code': code,
                'data': resource_data
            })
            
        return results
    
    def search_knowledge_base_workshops(self, knowledge_base, workshop_type: str = None) -> List[Dict]:
        """
        Search knowledge base for workshops.
        
        Args:
            knowledge_base: Knowledge base instance
            workshop_type: Optional workshop type/skill filter
            
        Returns:
            List of matching workshops with location data
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return []
            
        workshops = knowledge_base.data.get('workshops', {})
        results = []
        
        for code, workshop_data in workshops.items():
            # Apply type filter
            if workshop_type:
                craft_skill = workshop_data.get('craft_skill', '')
                if craft_skill != workshop_type and code != workshop_type:
                    continue
                    
            # Include location data
            x = workshop_data.get('x')
            y = workshop_data.get('y')
            if x is not None and y is not None:
                results.append({
                    'code': code,
                    'data': workshop_data,
                    'location': (x, y)
                })
                
        return results
    
    def search_map_state_for_content(self, map_state, content_type: str = None,
                                    content_code: str = None, 
                                    center: Tuple[int, int] = None,
                                    radius: int = None) -> List[Dict]:
        """
        Search map state for specific content.
        
        Args:
            map_state: Map state instance
            content_type: Optional content type filter
            content_code: Optional specific content code
            center: Optional (x, y) center point for radius search
            radius: Optional search radius
            
        Returns:
            List of matching locations with content
        """
        if not map_state or not hasattr(map_state, 'data'):
            return []
            
        results = []
        
        for coord_key, location_data in map_state.data.items():
            if not isinstance(location_data, dict):
                continue
                
            content = location_data.get('content')
            if not content:
                continue
                
            # Apply content filters
            if content_type and content.get('type') != content_type:
                continue
            if content_code and content.get('code') != content_code:
                continue
                
            # Extract coordinates
            try:
                x, y = map(int, coord_key.split(','))
            except (ValueError, AttributeError):
                continue
                
            # Apply radius filter
            if center and radius is not None:
                cx, cy = center
                distance = abs(x - cx) + abs(y - cy)  # Manhattan distance
                if distance > radius:
                    continue
                    
            results.append({
                'location': (x, y),
                'content': content,
                'data': location_data
            })
            
        return results


class MapStateAccessMixin:
    """Mixin for consistent map state access across actions."""
    
    def get_location_from_map_state(self, map_state, x: int, y: int) -> Optional[Dict]:
        """
        Get location data from map state using various method names.
        
        Args:
            map_state: Map state instance
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Location data or None
        """
        if not map_state:
            return None
            
        # Try different method names
        method_names = ['get_location_info', 'get_location', 'get_location_data']
        
        for method_name in method_names:
            if hasattr(map_state, method_name):
                try:
                    location_data = getattr(map_state, method_name)(x, y)
                    if location_data:
                        return location_data
                except Exception as e:
                    self.logger.debug(f"Failed to get location using {method_name}: {e}")
                    
        # Fallback to direct data access
        try:
            coord_key = f"{x},{y}"
            return map_state.data.get(coord_key)
        except Exception:
            return None
    
    def extract_map_state(self, kwargs: Dict) -> Optional[Any]:
        """
        Extract map state from kwargs with error handling.
        
        Args:
            kwargs: Keyword arguments dictionary
            
        Returns:
            Map state instance or None
        """
        return kwargs.get('map_state')
    
    def extract_knowledge_base(self, kwargs: Dict) -> Optional[Any]:
        """
        Extract knowledge base from kwargs with error handling.
        
        Args:
            kwargs: Keyword arguments dictionary
            
        Returns:
            Knowledge base instance or None
        """
        return kwargs.get('knowledge_base')