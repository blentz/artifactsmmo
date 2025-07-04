"""
Analyze Knowledge State Action

This action analyzes the knowledge base completeness, information gaps,
and learning progress to guide exploration and information gathering.
"""

from typing import Dict, List

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


class AnalyzeKnowledgeStateAction(ActionBase):
    """
    Action to analyze knowledge base state and information completeness.
    
    This action evaluates the knowledge base for completeness, identifies
    information gaps, analyzes learning progress, and provides guidance
    for targeted exploration and information gathering activities.
    """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
        "knowledge_state_analyzed": True,
        "map_explored": True,
        "equipment_info_known": True,
        "recipe_known": True,
        "exploration_data_available": True
    }
    weight = 8

    def __init__(self):
        """
        Initialize the knowledge state analysis action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Analyze knowledge base state and completeness."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        analysis_scope = context.get('analysis_scope', 'comprehensive')
        
        self._context = context
        
        try:
            # Get current character data for context
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
            
            character_data = character_response.data
            
            # Get knowledge base and map state
            knowledge_base = context.knowledge_base
            map_state = context.map_state
            
            if not knowledge_base:
                return self.create_error_result("No knowledge base available for analysis")
            
            # Perform comprehensive knowledge analysis
            general_analysis = self._analyze_general_knowledge_state(knowledge_base, character_data)
            
            # Scope-specific analyses
            analysis_scope = analysis_scope
            if analysis_scope in ['comprehensive', 'combat']:
                combat_analysis = self._analyze_combat_knowledge(knowledge_base, character_data)
            else:
                combat_analysis = {}
            
            if analysis_scope in ['comprehensive', 'crafting']:
                crafting_analysis = self._analyze_crafting_knowledge(knowledge_base, character_data)
            else:
                crafting_analysis = {}
            
            if analysis_scope in ['comprehensive', 'exploration']:
                exploration_analysis = self._analyze_exploration_knowledge(knowledge_base, map_state, character_data)
            else:
                exploration_analysis = {}
            
            # Identify priority information gaps
            gap_analysis = self._identify_information_gaps(
                general_analysis, combat_analysis, crafting_analysis, exploration_analysis, character_data
            )
            
            # Generate learning recommendations
            learning_recommendations = self._generate_learning_recommendations(
                general_analysis, gap_analysis, character_data
            )
            
            # Determine GOAP state updates
            goap_updates = self._determine_knowledge_state_updates(
                general_analysis, combat_analysis, crafting_analysis, exploration_analysis, gap_analysis
            )
            
            # Create result
            result = self.create_success_result(
                knowledge_state_analyzed=True,
                analysis_scope=analysis_scope,
                **general_analysis,
                **combat_analysis,
                **crafting_analysis,
                **exploration_analysis,
                **gap_analysis,
                **learning_recommendations,
                **goap_updates
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Knowledge state analysis failed: {str(e)}")
            return error_response

    def _analyze_general_knowledge_state(self, knowledge_base, character_data) -> Dict:
        """Analyze general knowledge base completeness."""
        try:
            analysis = {
                'knowledge_completeness_score': 0.0,
                'total_data_categories': 0,
                'populated_categories': 0,
                'category_completeness': {},
                'knowledge_base_size': 0,
                'last_learning_activity': None
            }
            
            if not hasattr(knowledge_base, 'data'):
                return analysis
            
            kb_data = knowledge_base.data
            
            # Define expected knowledge categories
            expected_categories = [
                'monsters', 'items', 'resources', 'workshops', 'maps',
                'character_insights', 'combat_performance', 'exploration_patterns'
            ]
            
            analysis['total_data_categories'] = len(expected_categories)
            
            # Analyze each category
            for category in expected_categories:
                category_data = kb_data.get(category, {})
                
                if category_data:
                    analysis['populated_categories'] += 1
                    
                    # Calculate category-specific completeness
                    if category == 'monsters':
                        completeness = self._calculate_monster_knowledge_completeness(category_data)
                    elif category == 'items':
                        completeness = self._calculate_item_knowledge_completeness(category_data)
                    elif category == 'resources':
                        completeness = self._calculate_resource_knowledge_completeness(category_data)
                    elif category == 'workshops':
                        completeness = self._calculate_workshop_knowledge_completeness(category_data)
                    elif category == 'maps':
                        completeness = self._calculate_map_knowledge_completeness(category_data)
                    else:
                        # For other categories, just check if they have data
                        completeness = 1.0 if category_data else 0.0
                    
                    analysis['category_completeness'][category] = completeness
                else:
                    analysis['category_completeness'][category] = 0.0
            
            # Calculate overall completeness score
            if analysis['total_data_categories'] > 0:
                total_completeness = sum(analysis['category_completeness'].values())
                analysis['knowledge_completeness_score'] = total_completeness / analysis['total_data_categories']
            
            # Calculate knowledge base size (rough estimate)
            analysis['knowledge_base_size'] = sum(
                len(category_data) if isinstance(category_data, dict) else 1
                for category_data in kb_data.values()
                if category_data
            )
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"General knowledge analysis failed: {e}")
            return {'knowledge_completeness_score': 0.0}

    def _calculate_monster_knowledge_completeness(self, monsters_data: Dict) -> float:
        """Calculate completeness of monster knowledge."""
        try:
            if not monsters_data:
                return 0.0
            
            total_monsters = len(monsters_data)
            comprehensive_knowledge = 0
            
            for monster_code, monster_data in monsters_data.items():
                score = 0
                
                # Check for basic information
                if monster_data.get('name'):
                    score += 0.2
                if monster_data.get('level'):
                    score += 0.2
                
                # Check for location data
                locations = monster_data.get('locations', [])
                if locations:
                    score += 0.2
                
                # Check for combat data
                combat_results = monster_data.get('combat_results', [])
                if len(combat_results) >= 3:  # Sufficient combat data
                    score += 0.2
                
                # Check for drop data
                drops = monster_data.get('drops', [])
                if drops:
                    score += 0.2
                
                if score >= 0.8:  # Consider comprehensive if >= 80%
                    comprehensive_knowledge += 1
            
            return comprehensive_knowledge / total_monsters if total_monsters > 0 else 0.0
            
        except Exception as e:
            self.logger.warning(f"Monster knowledge completeness calculation failed: {e}")
            return 0.0

    def _calculate_item_knowledge_completeness(self, items_data: Dict) -> float:
        """Calculate completeness of item knowledge."""
        try:
            if not items_data:
                return 0.0
            
            total_items = len(items_data)
            comprehensive_knowledge = 0
            
            for item_code, item_data in items_data.items():
                score = 0
                
                # Check for basic information
                if item_data.get('name'):
                    score += 0.3
                if item_data.get('type'):
                    score += 0.2
                
                # Check for craft data
                craft_data = item_data.get('craft_data', {})
                if craft_data:
                    score += 0.3
                    if craft_data.get('materials'):
                        score += 0.2
                
                if score >= 0.7:  # Consider comprehensive if >= 70%
                    comprehensive_knowledge += 1
            
            return comprehensive_knowledge / total_items if total_items > 0 else 0.0
            
        except Exception as e:
            self.logger.warning(f"Item knowledge completeness calculation failed: {e}")
            return 0.0

    def _calculate_resource_knowledge_completeness(self, resources_data: Dict) -> float:
        """Calculate completeness of resource knowledge."""
        try:
            if not resources_data:
                return 0.0
            
            total_resources = len(resources_data)
            comprehensive_knowledge = 0
            
            for resource_code, resource_data in resources_data.items():
                score = 0
                
                # Check for location data
                locations = resource_data.get('locations', [])
                if locations:
                    score += 0.5
                    if len(locations) >= 3:  # Multiple known locations
                        score += 0.3
                
                # Check for additional data
                if resource_data.get('skill'):
                    score += 0.2
                
                if score >= 0.7:
                    comprehensive_knowledge += 1
            
            return comprehensive_knowledge / total_resources if total_resources > 0 else 0.0
            
        except Exception as e:
            self.logger.warning(f"Resource knowledge completeness calculation failed: {e}")
            return 0.0

    def _calculate_workshop_knowledge_completeness(self, workshops_data: Dict) -> float:
        """Calculate completeness of workshop knowledge."""
        try:
            if not workshops_data:
                return 0.0
            
            # For workshops, if we have any data, it's usually comprehensive
            return 1.0 if workshops_data else 0.0
            
        except Exception as e:
            self.logger.warning(f"Workshop knowledge completeness calculation failed: {e}")
            return 0.0

    def _calculate_map_knowledge_completeness(self, maps_data: Dict) -> float:
        """Calculate completeness of map knowledge."""
        try:
            if not maps_data:
                return 0.0
            
            # Rough estimate based on number of explored locations
            # This could be enhanced with actual map size knowledge
            explored_locations = len(maps_data)
            
            if explored_locations >= 50:
                return 1.0
            elif explored_locations >= 20:
                return 0.7
            elif explored_locations >= 10:
                return 0.4
            elif explored_locations >= 5:
                return 0.2
            else:
                return 0.1
                
        except Exception as e:
            self.logger.warning(f"Map knowledge completeness calculation failed: {e}")
            return 0.0

    def _analyze_combat_knowledge(self, knowledge_base, character_data) -> Dict:
        """Analyze combat-specific knowledge completeness."""
        try:
            analysis = {
                'combat_knowledge_score': 0.0,
                'monsters_with_combat_data': 0,
                'total_combat_encounters': 0,
                'win_rate_data_available': False,
                'combat_patterns_identified': False
            }
            
            if not hasattr(knowledge_base, 'data'):
                return analysis
            
            monsters_data = knowledge_base.data.get('monsters', {})
            
            if not monsters_data:
                return analysis
            
            total_monsters = len(monsters_data)
            monsters_with_data = 0
            total_encounters = 0
            
            for monster_code, monster_data in monsters_data.items():
                combat_results = monster_data.get('combat_results', [])
                if combat_results:
                    monsters_with_data += 1
                    total_encounters += len(combat_results)
            
            analysis['monsters_with_combat_data'] = monsters_with_data
            analysis['total_combat_encounters'] = total_encounters
            
            if total_monsters > 0:
                analysis['combat_knowledge_score'] = monsters_with_data / total_monsters
            
            # Check if we have sufficient data for win rate analysis
            analysis['win_rate_data_available'] = monsters_with_data >= 3 and total_encounters >= 10
            
            # Check for combat patterns
            character_insights = knowledge_base.data.get('character_insights', {})
            combat_performance = character_insights.get('combat_performance', {})
            analysis['combat_patterns_identified'] = bool(combat_performance)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Combat knowledge analysis failed: {e}")
            return {'combat_knowledge_score': 0.0}

    def _analyze_crafting_knowledge(self, knowledge_base, character_data) -> Dict:
        """Analyze crafting-specific knowledge completeness."""
        try:
            analysis = {
                'crafting_knowledge_score': 0.0,
                'items_with_recipes': 0,
                'workshops_known': 0,
                'material_sources_known': False,
                'recipe_completeness': 0.0
            }
            
            if not hasattr(knowledge_base, 'data'):
                return analysis
            
            kb_data = knowledge_base.data
            items_data = kb_data.get('items', {})
            workshops_data = kb_data.get('workshops', {})
            
            # Analyze item recipe knowledge
            if items_data:
                total_items = len(items_data)
                items_with_recipes = 0
                
                for item_code, item_data in items_data.items():
                    craft_data = item_data.get('craft_data', {})
                    if craft_data and craft_data.get('materials'):
                        items_with_recipes += 1
                
                analysis['items_with_recipes'] = items_with_recipes
                analysis['recipe_completeness'] = items_with_recipes / total_items if total_items > 0 else 0.0
            
            # Workshop knowledge
            analysis['workshops_known'] = len(workshops_data)
            
            # Material sources (check resources and monsters for material drops)
            resources_data = kb_data.get('resources', {})
            monsters_data = kb_data.get('monsters', {})
            
            material_sources = len(resources_data)
            for monster_data in monsters_data.values():
                if monster_data.get('drops'):
                    material_sources += 1
            
            analysis['material_sources_known'] = material_sources > 0
            
            # Overall crafting knowledge score
            recipe_score = analysis['recipe_completeness']
            workshop_score = 1.0 if analysis['workshops_known'] > 0 else 0.0
            materials_score = 1.0 if analysis['material_sources_known'] else 0.0
            
            analysis['crafting_knowledge_score'] = (recipe_score + workshop_score + materials_score) / 3.0
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Crafting knowledge analysis failed: {e}")
            return {'crafting_knowledge_score': 0.0}

    def _analyze_exploration_knowledge(self, knowledge_base, map_state, character_data) -> Dict:
        """Analyze exploration-specific knowledge completeness."""
        try:
            analysis = {
                'exploration_knowledge_score': 0.0,
                'locations_explored': 0,
                'content_discovery_rate': 0.0,
                'map_coverage_estimate': 0.0,
                'exploration_efficiency': 'unknown'
            }
            
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return analysis
            
            maps_data = knowledge_base.data.get('maps', {})
            analysis['locations_explored'] = len(maps_data)
            
            if maps_data:
                # Calculate content discovery rate
                locations_with_content = 0
                for location_data in maps_data.values():
                    content = location_data.get('content')
                    if content and content.get('type') and content.get('type') != 'unknown':
                        locations_with_content += 1
                
                analysis['content_discovery_rate'] = locations_with_content / len(maps_data)
                
                # Estimate map coverage (rough calculation)
                # This assumes a reasonable game world size
                if analysis['locations_explored'] >= 100:
                    analysis['map_coverage_estimate'] = 1.0
                elif analysis['locations_explored'] >= 50:
                    analysis['map_coverage_estimate'] = 0.7
                elif analysis['locations_explored'] >= 25:
                    analysis['map_coverage_estimate'] = 0.4
                elif analysis['locations_explored'] >= 10:
                    analysis['map_coverage_estimate'] = 0.2
                else:
                    analysis['map_coverage_estimate'] = 0.1
            
            # Calculate overall exploration knowledge score
            coverage_score = analysis['map_coverage_estimate']
            discovery_score = analysis['content_discovery_rate']
            analysis['exploration_knowledge_score'] = (coverage_score + discovery_score) / 2.0
            
            # Determine exploration efficiency
            if analysis['exploration_knowledge_score'] >= 0.8:
                analysis['exploration_efficiency'] = 'excellent'
            elif analysis['exploration_knowledge_score'] >= 0.6:
                analysis['exploration_efficiency'] = 'good'
            elif analysis['exploration_knowledge_score'] >= 0.4:
                analysis['exploration_efficiency'] = 'fair'
            else:
                analysis['exploration_efficiency'] = 'poor'
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Exploration knowledge analysis failed: {e}")
            return {'exploration_knowledge_score': 0.0}

    def _identify_information_gaps(self, general_analysis: Dict, combat_analysis: Dict,
                                 crafting_analysis: Dict, exploration_analysis: Dict, character_data) -> Dict:
        """Identify priority information gaps and learning needs."""
        try:
            analysis = {
                'priority_gaps': [],
                'learning_opportunities': [],
                'recommended_activities': [],
                'information_gaps_score': 0.0
            }
            
            character_level = getattr(character_data, 'level', 1)
            
            # Identify gaps based on completeness scores
            overall_completeness = general_analysis.get('knowledge_completeness_score', 0.0)
            combat_completeness = combat_analysis.get('combat_knowledge_score', 0.0)
            crafting_completeness = crafting_analysis.get('crafting_knowledge_score', 0.0)
            exploration_completeness = exploration_analysis.get('exploration_knowledge_score', 0.0)
            
            # Priority gaps (most important)
            if combat_completeness < 0.3 and character_level >= 2:
                analysis['priority_gaps'].append({
                    'category': 'combat',
                    'severity': 'high',
                    'description': 'Limited combat knowledge and experience',
                    'recommended_action': 'Engage in combat to gather performance data'
                })
            
            if crafting_completeness < 0.4 and character_level >= 2:
                analysis['priority_gaps'].append({
                    'category': 'crafting',
                    'severity': 'high',
                    'description': 'Insufficient crafting and recipe knowledge',
                    'recommended_action': 'Explore workshops and analyze crafting requirements'
                })
            
            if exploration_completeness < 0.3:
                analysis['priority_gaps'].append({
                    'category': 'exploration',
                    'severity': 'medium',
                    'description': 'Limited map and location knowledge',
                    'recommended_action': 'Systematic map exploration and content discovery'
                })
            
            # Learning opportunities
            if general_analysis.get('populated_categories', 0) < general_analysis.get('total_data_categories', 1):
                analysis['learning_opportunities'].append('Comprehensive knowledge base development')
            
            if not combat_analysis.get('win_rate_data_available', False):
                analysis['learning_opportunities'].append('Combat performance data collection')
            
            if crafting_analysis.get('workshops_known', 0) < 3:
                analysis['learning_opportunities'].append('Workshop discovery and cataloging')
            
            # Recommended activities
            analysis['recommended_activities'] = self._generate_activity_recommendations(
                overall_completeness, combat_completeness, crafting_completeness, exploration_completeness
            )
            
            # Calculate information gaps score (inverse of completeness)
            avg_completeness = (overall_completeness + combat_completeness + 
                              crafting_completeness + exploration_completeness) / 4.0
            analysis['information_gaps_score'] = 1.0 - avg_completeness
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Information gaps identification failed: {e}")
            return {'priority_gaps': [], 'information_gaps_score': 1.0}

    def _generate_activity_recommendations(self, overall: float, combat: float, 
                                         crafting: float, exploration: float) -> List[str]:
        """Generate specific activity recommendations based on knowledge gaps."""
        try:
            recommendations = []
            
            # Prioritize based on lowest scores
            scores = [
                ('exploration', exploration),
                ('combat', combat),
                ('crafting', crafting),
                ('overall', overall)
            ]
            scores.sort(key=lambda x: x[1])  # Sort by score, lowest first
            
            for category, score in scores:
                if score < 0.5:
                    if category == 'exploration':
                        recommendations.append('Systematic map exploration in unexplored areas')
                    elif category == 'combat':
                        recommendations.append('Engage in combat with various monsters for data collection')
                    elif category == 'crafting':
                        recommendations.append('Workshop discovery and recipe analysis')
                    elif category == 'overall':
                        recommendations.append('Comprehensive knowledge gathering across all areas')
            
            # Ensure we have at least one recommendation
            if not recommendations:
                recommendations.append('Continue current activities to maintain knowledge base')
            
            return recommendations[:3]  # Limit to top 3 recommendations
            
        except Exception as e:
            self.logger.warning(f"Activity recommendations generation failed: {e}")
            return ['Continue exploration and learning activities']

    def _generate_learning_recommendations(self, general_analysis: Dict, gap_analysis: Dict, 
                                         character_data) -> Dict:
        """Generate comprehensive learning recommendations."""
        try:
            recommendations = {
                'primary_learning_focus': 'general_exploration',
                'specific_learning_goals': [],
                'learning_strategy': 'balanced',
                'estimated_learning_time': 'medium'
            }
            
            priority_gaps = gap_analysis.get('priority_gaps', [])
            overall_completeness = general_analysis.get('knowledge_completeness_score', 0.0)
            
            # Determine primary learning focus
            if priority_gaps:
                highest_priority = priority_gaps[0]
                recommendations['primary_learning_focus'] = highest_priority['category']
                recommendations['learning_strategy'] = 'focused'
            
            # Generate specific learning goals
            for gap in priority_gaps:
                recommendations['specific_learning_goals'].append(gap['recommended_action'])
            
            # Add general goals if not many specific gaps
            if len(recommendations['specific_learning_goals']) < 2:
                if overall_completeness < 0.7:
                    recommendations['specific_learning_goals'].append('Improve overall knowledge base coverage')
                recommendations['specific_learning_goals'].append('Maintain active learning through varied activities')
            
            # Estimate learning time based on gaps
            gap_score = gap_analysis.get('information_gaps_score', 0.0)
            if gap_score >= 0.7:
                recommendations['estimated_learning_time'] = 'long'
            elif gap_score >= 0.4:
                recommendations['estimated_learning_time'] = 'medium'
            else:
                recommendations['estimated_learning_time'] = 'short'
            
            return recommendations
            
        except Exception as e:
            self.logger.warning(f"Learning recommendations generation failed: {e}")
            return {'primary_learning_focus': 'general_exploration'}

    def _determine_knowledge_state_updates(self, general_analysis: Dict, combat_analysis: Dict,
                                         crafting_analysis: Dict, exploration_analysis: Dict,
                                         gap_analysis: Dict) -> Dict:
        """Determine GOAP state updates for knowledge analysis."""
        try:
            overall_completeness = general_analysis.get('knowledge_completeness_score', 0.0)
            exploration_score = exploration_analysis.get('exploration_knowledge_score', 0.0)
            crafting_score = crafting_analysis.get('crafting_knowledge_score', 0.0)
            
            return {
                'map_explored': exploration_score >= 0.6,
                'equipment_info_known': crafting_score >= 0.5,
                'recipe_known': crafting_analysis.get('recipe_completeness', 0.0) >= 0.3,
                'exploration_data_available': exploration_score >= 0.3,
                'knowledge_base_comprehensive': overall_completeness >= 0.7,
                'learning_focus_needed': gap_analysis.get('information_gaps_score', 0.0) >= 0.5
            }
            
        except Exception as e:
            self.logger.warning(f"Knowledge state updates determination failed: {e}")
            return {'knowledge_base_comprehensive': False}

    def __repr__(self):
        return "AnalyzeKnowledgeStateAction()"