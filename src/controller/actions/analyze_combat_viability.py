"""
Analyze Combat Viability Action

This action analyzes combat effectiveness and viability in the current area,
providing strategic guidance for combat engagement decisions.
"""

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import CombatStatus

from .base import ActionBase, ActionResult


class AnalyzeCombatViabilityAction(ActionBase):
    """
    Action to analyze combat viability and effectiveness.
    
    This action evaluates combat performance data, monster win rates,
    character stats, and area-specific combat conditions to provide
    strategic guidance for combat planning.
    """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
            'combat_viability_known': True,
            'combat_not_viable': True,
            'combat_context': {
                'status': True,
            },
            'goal_progress': {
                'monsters_hunted': 1,
            },
        }
    weight = 12

    def __init__(self):
        """
        Initialize the combat viability analysis action.
        """
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """Analyze combat viability in current area."""
        # Get character name from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        # Get analysis radius from context or use default
        analysis_radius = context.get('analysis_radius', 3)
            
        self._context = context
        
        try:
            # Get current character data from context or API
            if context.character_state and hasattr(context.character_state, 'data'):
                character_data = context.character_state
                character_x = context.get(StateParameters.CHARACTER_X)
                character_y = context.get(StateParameters.CHARACTER_Y)
            else:
                # Fallback to API call
                character_response = get_character_api(name=character_name, client=client)
                if not character_response or not character_response.data:
                    return self.create_error_result("Could not get character data")
                
                character_data = character_response.data
                character_x = getattr(character_data, 'x', 0)
                character_y = getattr(character_data, 'y', 0)
            
            # Get knowledge base and map state from context
            knowledge_base = context.knowledge_base
            map_state = context.map_state
            
            # Perform combat viability analysis
            viability_results = self._analyze_combat_viability(
                character_data, character_x, character_y, knowledge_base, map_state, analysis_radius
            )
            
            # Analyze character combat readiness
            readiness_results = self._analyze_combat_readiness(character_data)
            
            # Generate strategic recommendations
            recommendations = self._generate_combat_recommendations(
                viability_results, readiness_results, character_data
            )
            
            # Determine GOAP state updates
            goap_updates = self._determine_combat_state_updates(
                viability_results, readiness_results, recommendations
            )
            
            # Create result
            return self.create_success_result(
                combat_viability_known=True,
                character_x=character_x,
                character_y=character_y,
                analysis_radius=analysis_radius,
                **viability_results,
                **readiness_results,
                **recommendations,
                **goap_updates
            )
            
        except Exception as e:
            return self.create_error_result(f"Combat viability analysis failed: {str(e)}")

    def _analyze_combat_viability(self, character_data, character_x: int, character_y: int,
                                knowledge_base, map_state, analysis_radius: int = 3) -> Dict:
        """Analyze combat viability in the current area."""
        try:
            viability_data = {
                'nearby_monsters': [],
                'monster_analysis': {},
                'area_win_rate': 0.0,
                'total_nearby_monsters': 0,
                'monsters_with_data': 0,
                'poor_win_rate_count': 0,
                'combat_viable': True,
                'viability_reason': 'No combat data available'
            }
            
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                viability_data['viability_reason'] = 'No knowledge base available'
                return viability_data
            
            # Get monsters data from knowledge base
            monsters_data = {}
            if hasattr(knowledge_base, 'data'):
                monsters_data = knowledge_base.data.get('monsters', {})
            elif hasattr(knowledge_base, 'get_all_monster_data'):
                # Use knowledge base method if available
                monsters_data = knowledge_base.get_all_monster_data()
            
            if not monsters_data:
                viability_data['viability_reason'] = 'No monster data in knowledge base'
                return viability_data
            
            # Find nearby monsters
            nearby_monsters = self._find_nearby_monsters(
                monsters_data, character_x, character_y, analysis_radius
            )
            
            viability_data['nearby_monsters'] = nearby_monsters
            viability_data['total_nearby_monsters'] = len(nearby_monsters)
            
            if not nearby_monsters:
                viability_data['viability_reason'] = 'No monsters nearby'
                return viability_data
            
            # Analyze each nearby monster
            total_win_rate = 0.0
            monsters_with_sufficient_data = 0
            poor_performers = 0
            
            for monster_info in nearby_monsters:
                monster_code = monster_info['code']
                monster_data = monsters_data.get(monster_code, {})
                
                analysis = self._analyze_monster_performance(monster_data, monster_code)
                viability_data['monster_analysis'][monster_code] = analysis
                
                if analysis['has_sufficient_data']:
                    monsters_with_sufficient_data += 1
                    total_win_rate += analysis['win_rate']
                    
                    if analysis['win_rate'] < 0.2:  # Less than 20% win rate
                        poor_performers += 1
            
            viability_data['monsters_with_data'] = monsters_with_sufficient_data
            viability_data['poor_win_rate_count'] = poor_performers
            
            # Calculate overall area viability
            if monsters_with_sufficient_data > 0:
                viability_data['area_win_rate'] = total_win_rate / monsters_with_sufficient_data
                
                # Combat is not viable if:
                # 1. We have at least 2 monsters with data
                # 2. More than 50% have poor win rates OR average win rate < 30%
                if monsters_with_sufficient_data >= 2:
                    poor_rate_threshold = monsters_with_sufficient_data * 0.5
                    if (poor_performers >= poor_rate_threshold or 
                        viability_data['area_win_rate'] < 0.3):
                        viability_data['combat_viable'] = False
                        viability_data['viability_reason'] = (
                            f"Poor combat performance: {poor_performers}/{monsters_with_sufficient_data} "
                            f"monsters have poor win rates (avg: {viability_data['area_win_rate']:.1%})"
                        )
                    else:
                        viability_data['viability_reason'] = (
                            f"Good combat performance: avg win rate {viability_data['area_win_rate']:.1%}"
                        )
                else:
                    viability_data['viability_reason'] = f"Limited data: only {monsters_with_sufficient_data} monsters with combat history"
            else:
                viability_data['viability_reason'] = 'No combat data for nearby monsters'
            
            return viability_data
            
        except Exception as e:
            self.logger.warning(f"Combat viability analysis failed: {e}")
            return {'combat_viable': True, 'viability_reason': f'Analysis error: {e}'}

    def _find_nearby_monsters(self, monsters_data: Dict, char_x: int, char_y: int, radius: int) -> List[Dict]:
        """Find monsters within the specified radius."""
        try:
            nearby_monsters = []
            
            for monster_code, monster_data in monsters_data.items():
                locations = monster_data.get('locations', [])
                
                for location in locations:
                    loc_x = location.get('x', 0)
                    loc_y = location.get('y', 0)
                    
                    # Calculate distance
                    distance = ((loc_x - char_x) ** 2 + (loc_y - char_y) ** 2) ** 0.5
                    
                    if distance <= radius:
                        nearby_monsters.append({
                            'code': monster_code,
                            'x': loc_x,
                            'y': loc_y,
                            'distance': distance,
                            'name': monster_data.get('name', monster_code)
                        })
            
            # Sort by distance
            nearby_monsters.sort(key=lambda x: x['distance'])
            return nearby_monsters
            
        except Exception as e:
            self.logger.warning(f"Error finding nearby monsters: {e}")
            return []

    def _analyze_monster_performance(self, monster_data: Dict, monster_code: str) -> Dict:
        """Analyze combat performance against a specific monster."""
        try:
            combat_results = monster_data.get('combat_results', [])
            
            analysis = {
                'monster_code': monster_code,
                'total_combats': len(combat_results),
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'has_sufficient_data': False,
                'performance_category': 'unknown',
                'last_combat': None
            }
            
            if len(combat_results) < 3:
                analysis['performance_category'] = 'insufficient_data'
                return analysis
            
            # Count wins and losses
            for result in combat_results:
                if result.get('result') == 'win':
                    analysis['wins'] += 1
                elif result.get('result') == 'loss':
                    analysis['losses'] += 1
            
            # Calculate win rate
            total_decisive_combats = analysis['wins'] + analysis['losses']
            if total_decisive_combats > 0:
                analysis['win_rate'] = analysis['wins'] / total_decisive_combats
                analysis['has_sufficient_data'] = True
            
            # Categorize performance
            if analysis['win_rate'] >= 0.8:
                analysis['performance_category'] = 'excellent'
            elif analysis['win_rate'] >= 0.6:
                analysis['performance_category'] = 'good'
            elif analysis['win_rate'] >= 0.4:
                analysis['performance_category'] = 'fair'
            elif analysis['win_rate'] >= 0.2:
                analysis['performance_category'] = 'poor'
            else:
                analysis['performance_category'] = 'very_poor'
            
            # Get most recent combat data
            if combat_results:
                analysis['last_combat'] = combat_results[-1]
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Monster performance analysis failed for {monster_code}: {e}")
            return {'monster_code': monster_code, 'has_sufficient_data': False}

    def _analyze_combat_readiness(self, character_data) -> Dict:
        """Analyze character's combat readiness."""
        try:
            # Extract character stats
            if hasattr(character_data, 'data'):
                # Using CharacterState from context
                char_data = character_data.data
                hp = char_data.get('hp', 0)
                max_hp = char_data.get('max_hp', 100)
                level = char_data.get('level', 1)
                weapon = char_data.get('weapon', '')
            else:
                # Using API response
                hp = getattr(character_data, 'hp', 0)
                max_hp = getattr(character_data, 'max_hp', 100)
                level = getattr(character_data, 'level', 1)
                weapon = getattr(character_data, 'weapon', '')
            
            # Calculate combat readiness factors
            hp_percentage = (hp / max_hp) if max_hp > 0 else 0
            has_weapon = weapon and weapon != 'wooden_stick'
            is_healthy = hp_percentage >= 0.8
            is_experienced = level >= 2
            
            readiness_score = 0
            readiness_factors = []
            
            # Score factors
            if is_healthy:
                readiness_score += 30
                readiness_factors.append("Good health")
            else:
                readiness_factors.append(f"Low health ({hp_percentage:.1%})")
            
            if has_weapon:
                readiness_score += 25
                readiness_factors.append("Has weapon")
            else:
                readiness_factors.append("Using starter weapon")
            
            if is_experienced:
                readiness_score += 20
                readiness_factors.append("Experienced")
            else:
                readiness_factors.append("Low level")
            
            # Equipment bonus (basic check)
            armor_slots = ['helmet', 'body_armor', 'leg_armor', 'boots']
            equipped_armor = 0
            
            if hasattr(character_data, 'data'):
                # Using CharacterState from context
                char_data = character_data.data
                equipped_armor = sum(1 for slot in armor_slots if char_data.get(slot, ''))
            else:
                # Using API response
                equipped_armor = sum(1 for slot in armor_slots if getattr(character_data, slot, ''))
            
            if equipped_armor >= 2:
                readiness_score += 15
                readiness_factors.append("Some armor equipped")
            elif equipped_armor >= 1:
                readiness_score += 10
                readiness_factors.append("Minimal armor")
            else:
                readiness_factors.append("No armor")
            
            # Base readiness
            readiness_score += 10
            
            # Determine readiness level
            if readiness_score >= 80:
                readiness_level = 'excellent'
            elif readiness_score >= 60:
                readiness_level = 'good'
            elif readiness_score >= 40:
                readiness_level = 'fair'
            else:
                readiness_level = 'poor'
            
            return {
                'combat_readiness_score': readiness_score,
                'combat_readiness_level': readiness_level,
                'hp_percentage': hp_percentage,
                'has_weapon': has_weapon,
                'is_healthy': is_healthy,
                'equipped_armor_count': equipped_armor,
                'readiness_factors': readiness_factors,
                'ready_for_combat': readiness_score >= 50 and is_healthy
            }
            
        except Exception as e:
            self.logger.warning(f"Combat readiness analysis failed: {e}")
            return {'ready_for_combat': False, 'combat_readiness_level': 'unknown'}

    def _generate_combat_recommendations(self, viability_results: Dict, 
                                       readiness_results: Dict, character_data) -> Dict:
        """Generate strategic combat recommendations."""
        try:
            recommendations = {
                'primary_recommendation': 'assess_situation',
                'recommendation_reason': 'General assessment needed',
                'specific_actions': [],
                'alternative_strategies': [],
                'risk_level': 'medium'
            }
            
            combat_viable = viability_results.get('combat_viable', True)
            ready_for_combat = readiness_results.get('ready_for_combat', False)
            area_win_rate = viability_results.get('area_win_rate', 0.0)
            
            # Determine primary recommendation
            if not ready_for_combat:
                recommendations['primary_recommendation'] = 'improve_readiness'
                recommendations['recommendation_reason'] = 'Character not ready for combat'
                recommendations['specific_actions'].extend([
                    'Rest to recover health',
                    'Equip better equipment',
                    'Improve combat skills'
                ])
                recommendations['risk_level'] = 'high'
                
            elif not combat_viable:
                recommendations['primary_recommendation'] = 'avoid_combat'
                recommendations['recommendation_reason'] = viability_results.get('viability_reason', 'Poor combat performance in area')
                recommendations['specific_actions'].extend([
                    'Move to different area',
                    'Improve equipment first',
                    'Focus on non-combat activities'
                ])
                recommendations['alternative_strategies'].extend([
                    'Resource gathering',
                    'Skill training',
                    'Equipment crafting'
                ])
                recommendations['risk_level'] = 'high'
                
            elif area_win_rate >= 0.7:
                recommendations['primary_recommendation'] = 'engage_combat'
                recommendations['recommendation_reason'] = f'Excellent combat performance (win rate: {area_win_rate:.1%})'
                recommendations['specific_actions'].extend([
                    'Continue hunting in current area',
                    'Focus on high-value monsters'
                ])
                recommendations['risk_level'] = 'low'
                
            elif area_win_rate >= 0.4:
                recommendations['primary_recommendation'] = 'cautious_combat'
                recommendations['recommendation_reason'] = f'Moderate combat performance (win rate: {area_win_rate:.1%})'
                recommendations['specific_actions'].extend([
                    'Fight selectively',
                    'Monitor health carefully',
                    'Be ready to retreat'
                ])
                recommendations['risk_level'] = 'medium'
                
            else:
                recommendations['primary_recommendation'] = 'limited_combat'
                recommendations['recommendation_reason'] = f'Poor combat performance (win rate: {area_win_rate:.1%})'
                recommendations['specific_actions'].extend([
                    'Minimal combat engagement',
                    'Improve equipment first',
                    'Consider area change'
                ])
                recommendations['risk_level'] = 'high'
            
            # Add general alternative strategies
            if 'alternative_strategies' not in recommendations or not recommendations['alternative_strategies']:
                recommendations['alternative_strategies'] = [
                    'Resource gathering for equipment upgrades',
                    'Skill development for better combat performance',
                    'Exploration of new areas'
                ]
            
            return recommendations
            
        except Exception as e:
            self.logger.warning(f"Combat recommendation generation failed: {e}")
            return {'primary_recommendation': 'assess_situation', 'risk_level': 'unknown'}

    def _determine_combat_state_updates(self, viability_results: Dict, readiness_results: Dict, 
                                      recommendations: Dict) -> Dict:
        """Determine GOAP state updates based on analysis."""
        try:
            combat_viable = viability_results.get('combat_viable', True)
            ready_for_combat = readiness_results.get('ready_for_combat', False)
            primary_rec = recommendations.get('primary_recommendation', '')
            
            # Determine combat state flags
            combat_not_viable = not combat_viable or not ready_for_combat
            
            # Determine combat context status
            if combat_not_viable:
                combat_status = CombatStatus.NOT_VIABLE
            elif primary_rec in ['engage_combat', 'cautious_combat'] and ready_for_combat:
                combat_status = CombatStatus.SEARCHING
            else:
                combat_status = CombatStatus.IDLE
            
            # Return consolidated state format
            return {
                'combat_context': {
                    'status': combat_status,
                    'recommendation': primary_rec,
                    'risk_level': recommendations.get('risk_level', 'medium'),
                    'recent_win_rate': viability_results.get('area_win_rate', 0.0)
                },
                'goal_progress': {
                    'monsters_analyzed': viability_results.get('monsters_with_data', 0)
                }
            }
            
        except Exception as e:
            self.logger.warning(f"Combat state update determination failed: {e}")
            return {
                'combat_context': {
                    'status': CombatStatus.NOT_VIABLE
                }
            }

    def __repr__(self):
        return "AnalyzeCombatViabilityAction()"
