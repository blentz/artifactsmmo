"""
Universal Search Action

This action consolidates find_monsters, find_resources, and find_workshops into a single
configurable search action. It uses the existing SearchActionBase infrastructure but
adds configuration-driven behavior to eliminate code duplication.
"""

from typing import Dict, List, Optional, Any
from src.lib.action_context import ActionContext
from .base import ActionResult
from .coordinate_mixin import CoordinateStandardizationMixin
from .search_base import SearchActionBase


class UniversalSearchAction(SearchActionBase, CoordinateStandardizationMixin):
    """
    Universal search action that can find monsters, resources, or workshops
    based on configuration parameters.
    """
    
    def __init__(self):
        super().__init__()
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute universal search based on action configuration.
        
        Expected action_config parameters:
        - search_content_type: "monster" | "resource" | "workshop"
        - content_filter_params: Dict with specific filtering criteria
        - result_context_mapping: Dict defining how to map results to context
        """
        if client is None:
            return self.create_error_result("No API client provided")
        
        try:
            # Get action configuration
            action_config = context.get('action_config', {})
            search_content_type = action_config.get('search_content_type', 'monster')
            
            # Get search parameters from context
            character_x = context.get('character_x', context.character_x)
            character_y = context.get('character_y', context.character_y)
            search_radius = context.get('search_radius', 3)
            
            self._context = context
            
            # Route to appropriate search method based on content type
            if search_content_type == 'monster':
                return self._search_monsters(client, context, character_x, character_y, search_radius, action_config)
            elif search_content_type == 'resource':
                return self._search_resources(client, context, character_x, character_y, search_radius, action_config)
            elif search_content_type == 'workshop':
                return self._search_workshops(client, context, character_x, character_y, search_radius, action_config)
            else:
                return self.create_error_result(f"Unknown search content type: {search_content_type}")
                
        except Exception as e:
            return self.create_error_result(f"Universal search failed: {str(e)}")
    
    def _search_monsters(self, client, context: ActionContext, character_x: int, character_y: int, 
                        search_radius: int, action_config: Dict) -> ActionResult:
        """Search for monsters using unified search algorithm."""
        try:
            # Get character information for combat viability
            character = client.get_character()
            character_level = character.level
            
            # Get configuration parameters
            minimum_win_rate = action_config.get('minimum_win_rate', 0.0)
            exclude_location = context.get('exclude_location')
            
            # Get map state for cached access
            map_state = context.map_state
            
            # Create monster filter with combat viability logic
            def monster_filter(content_dict: Dict, x: int, y: int) -> bool:
                # Skip if this is the excluded location
                if exclude_location and (x, y) == exclude_location:
                    return False
                
                content_type = content_dict.get('type_', 'unknown')
                content_code = content_dict.get('code', '')
                
                # Check if it's a monster
                if content_type not in ['monster', 'unknown']:
                    return False
                
                # Check if it matches monster patterns
                monster_patterns = ['slime', 'goblin', 'wolf', 'orc', 'cyclops', 'chicken', 'cow', 'pig']
                if not any(pattern in content_code.lower() for pattern in monster_patterns):
                    return False
                
                # Combat viability check
                monster_level = content_dict.get('level', 1)
                if character_level < monster_level:
                    win_rate = 0.1 * (character_level / monster_level)
                else:
                    win_rate = min(0.9, 0.7 + 0.2 * (character_level - monster_level))
                
                return win_rate >= minimum_win_rate
            
            # Execute unified search
            result = self.unified_search(
                client=client,
                character_x=character_x,
                character_y=character_y,
                search_radius=search_radius,
                content_filter=monster_filter,
                map_state=map_state
            )
            
            if result and 'error' not in result:
                # Store results in context for attack action
                context.set_result('target_monster', {
                    'code': result.get('content_code'),
                    'location': result.get('location'),
                    'distance': result.get('distance')
                })
                
                return ActionResult(
                    success=True,
                    message=f"Found monster {result.get('content_code')} at {result.get('location')}",
                    data=result,
                    action_name="search_monsters"
                )
            else:
                # Request subgoal to search new area
                return ActionResult(
                    success=False,
                    message="No suitable monsters found for combat",
                    action_name="search_monsters",
                    subgoal_request={
                        'goal': 'find_new_hunting_area',
                        'priority': 'high',
                        'context': {'search_radius': search_radius + 2}
                    }
                )
                
        except Exception as e:
            return self.create_error_result(f"Monster search failed: {str(e)}")
    
    def _search_resources(self, client, context: ActionContext, character_x: int, character_y: int,
                         search_radius: int, action_config: Dict) -> ActionResult:
        """Search for resources using unified search algorithm."""
        try:
            # Get character information
            character = client.get_character()
            character_level = character.level
            
            # Get required resource from context
            required_resource = context.get('required_resource')
            if not required_resource:
                return self.create_error_result("No required resource specified in context")
            
            # Get map state for cached access
            map_state = context.map_state
            
            # Create resource filter
            def resource_filter(content_dict: Dict, x: int, y: int) -> bool:
                content_type = content_dict.get('type_', 'unknown')
                content_code = content_dict.get('code', '')
                
                # Check if it matches the required resource
                if content_code != required_resource:
                    return False
                
                # Check if it's a resource type
                resource_patterns = ['_rocks', '_tree', '_fishing_spot', '_field', 'mushmush', 'glowstem']
                is_likely_resource = (content_type in ['resource', 'unknown'] or
                                    any(pattern in content_code for pattern in resource_patterns))
                
                if not is_likely_resource:
                    return False
                
                # Check level appropriateness
                resource_level = content_dict.get('level', 1)
                if resource_level > character_level + 3:  # Allow resources up to 3 levels higher
                    return False
                
                return True
            
            # Execute unified search
            result = self.unified_search(
                client=client,
                character_x=character_x,
                character_y=character_y,
                search_radius=search_radius,
                content_filter=resource_filter,
                map_state=map_state
            )
            
            if result and 'error' not in result:
                # Store results in context for movement action
                context.set_result('target_resource', {
                    'code': result.get('content_code'),
                    'location': result.get('location'),
                    'distance': result.get('distance')
                })
                
                return ActionResult(
                    success=True,
                    message=f"Found resource {result.get('content_code')} at {result.get('location')}",
                    data=result,
                    action_name="search_resources"
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"No {required_resource} resources found within radius {search_radius}",
                    action_name="search_resources"
                )
                
        except Exception as e:
            return self.create_error_result(f"Resource search failed: {str(e)}")
    
    def _search_workshops(self, client, context: ActionContext, character_x: int, character_y: int,
                         search_radius: int, action_config: Dict) -> ActionResult:
        """Search for workshops using unified search algorithm."""
        try:
            # Get required workshop type from context
            required_workshop = context.get('required_workshop')
            workshop_skill = context.get('workshop_skill')
            
            # Get map state for cached access
            map_state = context.map_state
            
            # Create workshop filter
            def workshop_filter(content_dict: Dict, x: int, y: int) -> bool:
                content_type = content_dict.get('type', content_dict.get('type_', 'unknown'))
                content_code = content_dict.get('code', '')
                
                # Check if it's a workshop-type content
                workshop_patterns = ['crafting', 'smithy', 'workshop']
                workshop_codes = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']
                
                is_likely_workshop = (content_type == 'workshop' or
                                    any(pattern in content_code for pattern in workshop_patterns) or
                                    content_code in workshop_codes)
                
                if not is_likely_workshop:
                    return False
                
                # Check if it matches required workshop if specified
                if required_workshop and required_workshop.lower() not in content_code.lower():
                    return False
                
                # Check if it matches required skill if specified
                if workshop_skill:
                    skill_workshop_map = {
                        'weaponcrafting': ['weaponcrafting'],
                        'gearcrafting': ['gearcrafting'],
                        'jewelrycrafting': ['jewelrycrafting'],
                        'cooking': ['cooking'],
                        'alchemy': ['alchemy']
                    }
                    valid_workshops = skill_workshop_map.get(workshop_skill, [])
                    if not any(ws in content_code for ws in valid_workshops):
                        return False
                
                return True
            
            # Execute unified search
            result = self.unified_search(
                client=client,
                character_x=character_x,
                character_y=character_y,
                search_radius=search_radius,
                content_filter=workshop_filter,
                map_state=map_state
            )
            
            if result and 'error' not in result:
                # Store results in context for movement action
                context.set_result('target_workshop', {
                    'code': result.get('content_code'),
                    'location': result.get('location'),
                    'distance': result.get('distance')
                })
                
                return ActionResult(
                    success=True,
                    message=f"Found workshop {result.get('content_code')} at {result.get('location')}",
                    data=result,
                    action_name="search_workshops"
                )
            else:
                workshop_type = required_workshop or workshop_skill or "workshop"
                return ActionResult(
                    success=False,
                    message=f"No {workshop_type} found within radius {search_radius}",
                    action_name="search_workshops"
                )
                
        except Exception as e:
            return self.create_error_result(f"Workshop search failed: {str(e)}")
    
    def __repr__(self):
        return "UniversalSearchAction()"