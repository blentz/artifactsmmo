"""
Analyze Workshop Requirements Action

This action analyzes workshop discovery needs and crafting facility requirements
for the character's current goals and strategic planning.
"""

from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class AnalyzeWorkshopRequirementsAction(ActionBase):
    """
    Action to analyze workshop requirements and discovery needs.
    
    This action evaluates current crafting goals, analyzes available workshops,
    identifies missing workshop access, and provides strategic guidance for
    workshop discovery and utilization.
    """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
        "workshop_requirements_known": True,
        "workshops_discovered": True,
        "at_correct_workshop": True
    }
    weights = {"workshop_requirements_known": 10}

    def __init__(self):
        """
        Initialize the workshop requirements analysis action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """Analyze workshop requirements and discovery needs."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        goal_type = context.get('goal_type', 'general')
        
        self.log_execution_start(
            character_name=character_name,
            goal_type=goal_type
        )
        
        try:
            # Get current character data
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            
            # Get context data
            knowledge_base = context.knowledge_base
            map_state = context.map_state
            
            # Analyze current workshop knowledge
            workshop_analysis = self._analyze_workshop_knowledge(knowledge_base, map_state)
            
            # Determine workshop requirements for current goals
            requirements_analysis = self._analyze_workshop_requirements(
                character_data, knowledge_base, goal_type
            )
            
            # Identify missing workshops and discovery needs
            discovery_analysis = self._analyze_discovery_needs(
                workshop_analysis, requirements_analysis, character_data
            )
            
            # Check current location workshop status
            location_analysis = self._analyze_current_location(
                character_data, workshop_analysis, map_state
            )
            
            # Generate recommendations
            recommendations = self._generate_workshop_recommendations(
                workshop_analysis, requirements_analysis, discovery_analysis, location_analysis
            )
            
            # Determine GOAP state updates
            goap_updates = self._determine_workshop_state_updates(
                workshop_analysis, discovery_analysis, location_analysis, recommendations
            )
            
            # Create result
            result = self.get_success_response(
                workshop_requirements_known=True,
                goal_type=goal_type,
                **workshop_analysis,
                **requirements_analysis,
                **discovery_analysis,
                **location_analysis,
                **recommendations,
                **goap_updates
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Workshop requirements analysis failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _analyze_workshop_knowledge(self, knowledge_base, map_state) -> Dict:
        """Analyze current knowledge of workshops."""
        try:
            analysis = {
                'known_workshops': {},
                'workshop_locations': {},
                'total_workshops_known': 0,
                'workshop_types_known': [],
                'has_workshop_data': False
            }
            
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return analysis
            
            # Get workshop data from knowledge base
            workshops_data = knowledge_base.data.get('workshops', {})
            maps_data = knowledge_base.data.get('maps', {})
            
            if workshops_data:
                analysis['known_workshops'] = workshops_data
                analysis['total_workshops_known'] = len(workshops_data)
                analysis['has_workshop_data'] = True
                
                # Extract workshop types
                workshop_types = set()
                for workshop_code, workshop_info in workshops_data.items():
                    workshop_type = workshop_info.get('skill', 'unknown')
                    if workshop_type != 'unknown':
                        workshop_types.add(workshop_type)
                
                analysis['workshop_types_known'] = list(workshop_types)
            
            # Get workshop locations from map data
            workshop_locations = {}
            if maps_data:
                for location_key, location_data in maps_data.items():
                    content = location_data.get('content', {})
                    if content.get('type') == 'workshop':
                        workshop_code = content.get('code')
                        if workshop_code:
                            if workshop_code not in workshop_locations:
                                workshop_locations[workshop_code] = []
                            workshop_locations[workshop_code].append({
                                'x': location_data.get('x', 0),
                                'y': location_data.get('y', 0),
                                'name': location_data.get('name', '')
                            })
            
            analysis['workshop_locations'] = workshop_locations
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Workshop knowledge analysis failed: {e}")
            return {'has_workshop_data': False, 'total_workshops_known': 0}

    def _analyze_workshop_requirements(self, character_data, knowledge_base, goal_type: str) -> Dict:
        """Analyze workshop requirements for current goals."""
        try:
            analysis = {
                'required_workshops': [],
                'required_workshop_types': [],
                'priority_workshops': {},
                'goal_specific_needs': {}
            }
            
            character_level = getattr(character_data, 'level', 1)
            
            # Determine workshop needs based on goal type and character level
            if goal_type in ['weaponcrafting', 'general'] and character_level >= 2:
                # Need weaponcrafting workshop for weapons
                analysis['required_workshop_types'].append('weaponcrafting')
                analysis['priority_workshops']['weaponcrafting'] = {
                    'priority': 'high',
                    'reason': 'Needed for weapon crafting and upgrades',
                    'level_requirement': 2
                }
            
            if goal_type in ['gearcrafting', 'general'] and character_level >= 3:
                # Need gearcrafting workshop for armor
                analysis['required_workshop_types'].append('gearcrafting')
                analysis['priority_workshops']['gearcrafting'] = {
                    'priority': 'medium',
                    'reason': 'Needed for armor crafting',
                    'level_requirement': 3
                }
            
            if goal_type in ['cooking', 'general'] and character_level >= 2:
                # Cooking workshop for food/consumables
                analysis['required_workshop_types'].append('cooking')
                analysis['priority_workshops']['cooking'] = {
                    'priority': 'low',
                    'reason': 'Useful for consumables and buffs',
                    'level_requirement': 2
                }
            
            # Look for specific workshop codes in knowledge base
            if knowledge_base and hasattr(knowledge_base, 'data'):
                workshops_data = knowledge_base.data.get('workshops', {})
                for workshop_code, workshop_info in workshops_data.items():
                    workshop_skill = workshop_info.get('skill', 'unknown')
                    if workshop_skill in analysis['required_workshop_types']:
                        analysis['required_workshops'].append({
                            'code': workshop_code,
                            'skill': workshop_skill,
                            'name': workshop_info.get('name', workshop_code),
                            'priority': analysis['priority_workshops'].get(workshop_skill, {}).get('priority', 'medium')
                        })
            
            # Goal-specific analysis
            analysis['goal_specific_needs'] = self._analyze_goal_specific_needs(
                goal_type, character_data, knowledge_base
            )
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Workshop requirements analysis failed: {e}")
            return {'required_workshops': [], 'required_workshop_types': []}

    def _analyze_goal_specific_needs(self, goal_type: str, character_data, knowledge_base) -> Dict:
        """Analyze goal-specific workshop needs."""
        try:
            needs = {}
            character_level = getattr(character_data, 'level', 1)
            
            if goal_type == 'weaponcrafting':
                # Specific weaponcrafting needs
                weaponcrafting_level = getattr(character_data, 'weaponcrafting_level', 0)
                needs['primary_focus'] = 'weaponcrafting'
                needs['skill_level'] = weaponcrafting_level
                needs['immediate_needs'] = []
                
                if weaponcrafting_level < 5:
                    needs['immediate_needs'].append('Basic weaponcrafting workshop access')
                if character_level >= 5:
                    needs['immediate_needs'].append('Advanced weaponcrafting capabilities')
                    
            elif goal_type == 'equipment_upgrade':
                # Equipment upgrade specific needs
                needs['primary_focus'] = 'equipment_crafting'
                needs['immediate_needs'] = ['weaponcrafting', 'gearcrafting']
                needs['secondary_needs'] = ['jewelrycrafting', 'cooking']
                
            elif goal_type == 'resource_processing':
                # Resource processing needs
                needs['primary_focus'] = 'material_processing'
                needs['immediate_needs'] = ['mining_workshop', 'woodcutting_workshop']
                
            else:
                # General needs based on character level
                needs['primary_focus'] = 'general_progression'
                if character_level >= 2:
                    needs['immediate_needs'] = ['weaponcrafting']
                if character_level >= 3:
                    needs['immediate_needs'].append('gearcrafting')
                if character_level >= 4:
                    needs['secondary_needs'] = ['cooking', 'alchemy']
            
            return needs
            
        except Exception as e:
            self.logger.warning(f"Goal-specific needs analysis failed: {e}")
            return {}

    def _analyze_discovery_needs(self, workshop_analysis: Dict, requirements_analysis: Dict, 
                               character_data) -> Dict:
        """Analyze workshop discovery needs."""
        try:
            analysis = {
                'missing_workshops': [],
                'missing_workshop_types': [],
                'discovery_priority': 'low',
                'discovery_needed': False,
                'total_missing': 0,
                'critical_missing': 0
            }
            
            known_workshop_types = workshop_analysis.get('workshop_types_known', [])
            required_workshop_types = requirements_analysis.get('required_workshop_types', [])
            required_workshops = requirements_analysis.get('required_workshops', [])
            
            # Find missing workshop types
            missing_types = []
            for required_type in required_workshop_types:
                if required_type not in known_workshop_types:
                    missing_types.append(required_type)
            
            analysis['missing_workshop_types'] = missing_types
            analysis['total_missing'] = len(missing_types)
            
            # Find missing specific workshops
            known_workshop_codes = set(workshop_analysis.get('known_workshops', {}).keys())
            missing_workshops = []
            
            for workshop_info in required_workshops:
                workshop_code = workshop_info['code']
                if workshop_code not in known_workshop_codes:
                    missing_workshops.append(workshop_info)
                    if workshop_info.get('priority') == 'high':
                        analysis['critical_missing'] += 1
            
            analysis['missing_workshops'] = missing_workshops
            
            # Determine discovery priority and need
            character_level = getattr(character_data, 'level', 1)
            
            if analysis['critical_missing'] > 0:
                analysis['discovery_priority'] = 'high'
                analysis['discovery_needed'] = True
            elif analysis['total_missing'] > 0 and character_level >= 2:
                analysis['discovery_priority'] = 'medium'
                analysis['discovery_needed'] = True
            elif analysis['total_missing'] > 0:
                analysis['discovery_priority'] = 'low'
                analysis['discovery_needed'] = True
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Discovery needs analysis failed: {e}")
            return {'discovery_needed': True, 'discovery_priority': 'medium'}

    def _analyze_current_location(self, character_data, workshop_analysis: Dict, map_state) -> Dict:
        """Analyze current location for workshop availability."""
        try:
            analysis = {
                'at_workshop': False,
                'current_workshop_code': None,
                'current_workshop_type': None,
                'at_correct_workshop': False,
                'location_capabilities': []
            }
            
            character_x = getattr(character_data, 'x', 0)
            character_y = getattr(character_data, 'y', 0)
            
            # Check if current location is a workshop
            location_key = f"{character_x},{character_y}"
            workshop_locations = workshop_analysis.get('workshop_locations', {})
            
            for workshop_code, locations in workshop_locations.items():
                for location in locations:
                    if location['x'] == character_x and location['y'] == character_y:
                        analysis['at_workshop'] = True
                        analysis['current_workshop_code'] = workshop_code
                        
                        # Get workshop type from known workshops
                        known_workshops = workshop_analysis.get('known_workshops', {})
                        workshop_info = known_workshops.get(workshop_code, {})
                        analysis['current_workshop_type'] = workshop_info.get('skill', 'unknown')
                        analysis['location_capabilities'].append('crafting')
                        break
            
            # Determine if this is the correct workshop for current goals
            if analysis['at_workshop']:
                # This is simplified - could be enhanced with goal-specific checking
                analysis['at_correct_workshop'] = True
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Current location analysis failed: {e}")
            return {'at_workshop': False, 'at_correct_workshop': False}

    def _generate_workshop_recommendations(self, workshop_analysis: Dict, requirements_analysis: Dict,
                                         discovery_analysis: Dict, location_analysis: Dict) -> Dict:
        """Generate workshop-related recommendations."""
        try:
            recommendations = {
                'primary_recommendation': 'assess_workshops',
                'specific_actions': [],
                'priority_discoveries': [],
                'immediate_steps': []
            }
            
            discovery_needed = discovery_analysis.get('discovery_needed', False)
            discovery_priority = discovery_analysis.get('discovery_priority', 'low')
            missing_workshops = discovery_analysis.get('missing_workshops', [])
            
            if discovery_needed and discovery_priority == 'high':
                recommendations['primary_recommendation'] = 'urgent_workshop_discovery'
                recommendations['specific_actions'].extend([
                    'Prioritize workshop discovery',
                    'Explore map systematically for workshops',
                    'Focus on critical workshop types first'
                ])
                
                # Sort missing workshops by priority
                high_priority = [w for w in missing_workshops if w.get('priority') == 'high']
                recommendations['priority_discoveries'] = high_priority
                
            elif discovery_needed:
                recommendations['primary_recommendation'] = 'planned_workshop_discovery'
                recommendations['specific_actions'].extend([
                    'Include workshop discovery in exploration plans',
                    'Map exploration with workshop focus',
                    'Combine with other objectives'
                ])
                
            else:
                recommendations['primary_recommendation'] = 'utilize_known_workshops'
                recommendations['specific_actions'].extend([
                    'Use existing workshop knowledge',
                    'Plan crafting activities',
                    'Optimize workshop utilization'
                ])
            
            # Add immediate steps
            if location_analysis.get('at_workshop'):
                recommendations['immediate_steps'].append('Utilize current workshop location')
            
            if missing_workshops:
                next_workshop = missing_workshops[0]  # Highest priority
                recommendations['immediate_steps'].append(
                    f"Discover {next_workshop['name']} workshop for {next_workshop['skill']}"
                )
            
            return recommendations
            
        except Exception as e:
            self.logger.warning(f"Workshop recommendations generation failed: {e}")
            return {'primary_recommendation': 'assess_workshops'}

    def _determine_workshop_state_updates(self, workshop_analysis: Dict, discovery_analysis: Dict,
                                        location_analysis: Dict, recommendations: Dict) -> Dict:
        """Determine GOAP state updates for workshop analysis."""
        try:
            discovery_needed = discovery_analysis.get('discovery_needed', False)
            has_workshop_data = workshop_analysis.get('has_workshop_data', False)
            at_workshop = location_analysis.get('at_workshop', False)
            at_correct_workshop = location_analysis.get('at_correct_workshop', False)
            
            return {
                'need_workshop_discovery': discovery_needed,
                'workshops_discovered': has_workshop_data and not discovery_needed,
                'workshop_discovery_priority': discovery_analysis.get('discovery_priority', 'low'),
                'workshop_recommendation': recommendations.get('primary_recommendation', 'assess_workshops')
            }
            
        except Exception as e:
            self.logger.warning(f"Workshop state updates determination failed: {e}")
            return {'need_workshop_discovery': True}

    def __repr__(self):
        return "AnalyzeWorkshopRequirementsAction()"