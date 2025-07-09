"""
Analyze Nearby Resources Action

Simplified action that focuses on discovering and analyzing nearby resources
for crafting opportunities. Replaces the complex AnalyzeResourcesAction.
"""

from typing import Dict, List

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionResult
from .resource_analysis_base import ResourceAnalysisBase


class AnalyzeNearbyResourcesAction(ResourceAnalysisBase):
    """
    Action to analyze nearby resources for equipment crafting opportunities.
    
    This simplified version focuses on the core functionality:
    1. Find nearby resources
    2. Analyze crafting potential
    3. Return prioritized opportunities
    """

    # GOAP parameters
    conditions = {
        'character_status': {
            'alive': True,
        },
    }
    reactions = {
        "resource_analysis_complete": True,
        "nearby_resources_known": True,
        "crafting_opportunities_identified": True,
        "resource_locations_known": True
    }
    weight = 6.0

    def __init__(self):
        """Initialize the analyze nearby resources action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Analyze nearby resources for crafting opportunities."""
        self._context = context
        
        # Get parameters from context
        character_x = context.get(StateParameters.CHARACTER_X, 0)
        character_y = context.get(StateParameters.CHARACTER_Y, 0)
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        analysis_radius = context.get(StateParameters.ANALYSIS_RADIUS, 10)
        equipment_types = context.get(StateParameters.EQUIPMENT_TYPES, ["weapon", "armor", "utility"])
        
        self.logger.debug(f"Starting {self.__class__.__name__} (character_x={character_x}, "
                         f"character_y={character_y}, character_level={character_level}, "
                         f"analysis_radius={analysis_radius})")
        
        try:
            # Step 1: Find nearby resources using mixin
            nearby_resources = self.find_nearby_resources(client, context)
            
            if not nearby_resources:
                return self.create_error_result("No resources found in analysis radius")
            
            # Step 2: Analyze each resource for crafting potential
            resource_analysis = {}
            
            for resource_location in nearby_resources:
                analysis = self._analyze_single_resource(
                    client, resource_location, context
                )
                if analysis:
                    resource_analysis[resource_location['resource_code']] = analysis
            
            # Step 3: Find equipment crafting opportunities
            equipment_opportunities = self._find_equipment_opportunities(
                client, resource_analysis, context
            )
            
            # Step 4: Prioritize opportunities
            prioritized_opportunities = self._prioritize_opportunities(
                equipment_opportunities, context.get(StateParameters.CONFIG_DATA)
            )
            
            # Create state changes to mark analysis complete
            state_changes = {
                "resource_analysis_complete": True,
                "nearby_resources_known": True,
                "crafting_opportunities_identified": True,
                "resource_locations_known": True
            }
            
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=f"Analyzed {len(nearby_resources)} resources, found {len(prioritized_opportunities)} opportunities",
                nearby_resources_count=len(nearby_resources),
                analyzed_resources=list(resource_analysis.keys()),
                equipment_opportunities=equipment_opportunities,
                prioritized_opportunities=prioritized_opportunities,
                recommended_action=self._recommend_next_action(prioritized_opportunities)
            )
            
        except Exception as e:
            return self.create_error_result(f'Resource analysis failed: {str(e)}')

    def _analyze_single_resource(self, client, resource_location: Dict, context: ActionContext) -> Dict:
        """
        Analyze a specific resource for its crafting potential.
        
        Args:
            client: API client
            resource_location: Resource location info
            context: ActionContext singleton with all parameters
            
        Returns:
            Analysis results dictionary
        """
        resource_code = resource_location['resource_code']
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        
        # Get detailed resource information using mixin
        resource_data = self.get_resource_details(client, resource_code, context)
        if not resource_data:
            return None
        
        analysis = {
            'resource_code': resource_code,
            'resource_name': getattr(resource_data, 'name', ''),
            'skill_required': getattr(resource_data, 'skill', 'unknown'),
            'level_required': getattr(resource_data, 'level', 1),
            'location': (resource_location['x'], resource_location['y']),
            'distance': resource_location['distance'],
            'crafting_uses': []
        }
        
        # Check if character can gather this resource
        analysis['can_gather'] = analysis['level_required'] <= character_level
        
        # Find what this resource can be used to craft
        if hasattr(resource_data, 'drops') and resource_data.drops:
            for drop in resource_data.drops:
                drop_code = getattr(drop, 'code', '')
                if drop_code:
                    # Use mixin method for finding crafting uses
                    crafting_uses = self.find_crafting_uses_for_item(
                        client, drop_code, context
                    )
                    analysis['crafting_uses'].extend(crafting_uses)
        
        return analysis

    def _find_equipment_opportunities(self, client, resource_analysis: Dict, 
                                    context: ActionContext) -> List[Dict]:
        """
        Find equipment that can be crafted from analyzed resources.
        
        Args:
            client: API client
            resource_analysis: Analysis results for all resources
            context: ActionContext singleton with all parameters
            
        Returns:
            List of equipment crafting opportunities
        """
        opportunities = []
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        
        for resource_code, analysis in resource_analysis.items():
            if not analysis['can_gather']:
                continue
            
            for craft_use in analysis['crafting_uses']:
                # Calculate feasibility score
                level_diff = abs(craft_use['item_level'] - character_level)
                distance_factor = 1.0 / (1.0 + analysis['distance'])
                level_factor = 1.0 / (1.0 + level_diff)
                
                opportunity = {
                    'item_code': craft_use['item_code'],
                    'item_name': craft_use['item_name'],
                    'item_type': craft_use['item_type'],
                    'item_level': craft_use['item_level'],
                    'resource_location': analysis['location'],
                    'resource_code': resource_code,
                    'resource_name': analysis['resource_name'],
                    'distance_to_resource': analysis['distance'],
                    'materials_needed': craft_use['all_materials_needed'],
                    'workshop_skill': craft_use['workshop_required'],
                    'feasibility_score': distance_factor * level_factor,
                    'level_appropriateness': 'good' if level_diff <= 1 else 'acceptable' if level_diff <= 3 else 'poor'
                }
                opportunities.append(opportunity)
        
        return opportunities

    def _prioritize_opportunities(self, opportunities: List[Dict], config_data=None) -> List[Dict]:
        """
        Prioritize crafting opportunities based on character needs.
        
        Args:
            opportunities: List of crafting opportunities
            config_data: Configuration data for priorities
            
        Returns:
            Sorted list of prioritized opportunities
        """
        def priority_key(opp):
            type_priority = self._get_equipment_type_priority(opp['item_type'], config_data)
            level_priority = self._get_level_appropriateness_priority(opp['level_appropriateness'], config_data)
            return (type_priority, level_priority, opp['feasibility_score'])
        
        return sorted(opportunities, key=priority_key, reverse=True)

    def _get_equipment_type_priority(self, item_type: str, config_data=None) -> int:
        """Get priority for equipment type based on configuration."""
        if config_data and hasattr(config_data, 'data'):
            resource_analysis_config = config_data.data.get('resource_analysis_priorities', {})
            priorities_config = resource_analysis_config.get('equipment_type_priorities', {})
            if priorities_config and item_type in priorities_config:
                return priorities_config[item_type]
        
        # Fallback priorities
        fallback_priorities = {
            'weapon': 3, 'body_armor': 2, 'helmet': 2, 'leg_armor': 2, 
            'boots': 2, 'ring': 1, 'amulet': 1, 'utility': 1
        }
        return fallback_priorities.get(item_type, 0)

    def _get_level_appropriateness_priority(self, level_appropriateness: str, config_data=None) -> int:
        """Get priority for level appropriateness based on configuration."""
        if config_data and hasattr(config_data, 'data'):
            resource_analysis_config = config_data.data.get('resource_analysis_priorities', {})
            priorities_config = resource_analysis_config.get('level_appropriateness_priorities', {})
            if priorities_config and level_appropriateness in priorities_config:
                return priorities_config[level_appropriateness]
        
        # Fallback priorities
        fallback_priorities = {'good': 3, 'acceptable': 2, 'poor': 1}
        return fallback_priorities.get(level_appropriateness, 0)

    def _recommend_next_action(self, prioritized_opportunities: List[Dict]) -> Dict:
        """
        Recommend the next action based on crafting analysis.
        
        Args:
            prioritized_opportunities: Prioritized list of opportunities
            
        Returns:
            Action recommendation
        """
        if not prioritized_opportunities:
            return {
                'action': 'continue_hunting',
                'reason': 'No viable equipment crafting opportunities found',
                'priority': 'low'
            }
        
        best_opportunity = prioritized_opportunities[0]
        
        return {
            'action': 'gather_for_crafting',
            'reason': f'Craft {best_opportunity["item_name"]} (level {best_opportunity["item_level"]}) to improve equipment',
            'priority': 'high',
            'target_item': best_opportunity['item_code'],
            'target_resource': best_opportunity['resource_code'],
            'resource_location': best_opportunity['resource_location'],
            'materials_needed': best_opportunity['materials_needed'],
            'workshop_skill': best_opportunity['workshop_skill']
        }

    def __repr__(self):
        return "AnalyzeNearbyResourcesAction()"