"""
Analyze Crafting Requirements Action

This action analyzes crafting requirements, material needs, and recipe availability
for strategic crafting planning and material gathering guidance.
"""

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class AnalyzeCraftingRequirementsAction(ActionBase):
    """
    Action to analyze crafting requirements and material needs.
    
    This action evaluates crafting goals, analyzes recipe requirements,
    checks material availability, and provides strategic guidance for
    material gathering and crafting planning.
    """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {
        "crafting_requirements_known": True,
        "need_crafting_materials": True,
        "has_crafting_materials": True,
        "materials_sufficient": True
    }
    weights = {"crafting_requirements_known": 12}

    def __init__(self):
        """
        Initialize the crafting requirements analysis action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """Analyze crafting requirements and material needs."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        target_items = context.get('target_items', [])
        crafting_goal = context.get('crafting_goal', 'equipment')
        
        self.log_execution_start(
            character_name=character_name,
            target_items=target_items,
            crafting_goal=crafting_goal
        )
        
        try:
            # Get current character data
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            
            # Get context data
            knowledge_base = context.knowledge_base
            
            # Determine target items if not specified
            if not target_items:
                target_items = self._determine_target_items(character_data, knowledge_base, crafting_goal)
            
            # Analyze crafting requirements for each target item
            requirements_analysis = self._analyze_item_requirements(
                target_items, client, knowledge_base
            )
            
            # Analyze current material availability
            material_analysis = self._analyze_material_availability(
                character_data, requirements_analysis, knowledge_base
            )
            
            # Identify missing materials and gathering needs
            gathering_analysis = self._analyze_gathering_needs(
                requirements_analysis, material_analysis, knowledge_base
            )
            
            # Analyze skill requirements
            skill_analysis = self._analyze_skill_requirements(
                requirements_analysis, character_data
            )
            
            # Generate crafting strategy recommendations
            strategy_recommendations = self._generate_crafting_strategy(
                requirements_analysis, material_analysis, gathering_analysis, skill_analysis
            )
            
            # Determine GOAP state updates
            goap_updates = self._determine_crafting_state_updates(
                requirements_analysis, material_analysis, gathering_analysis, skill_analysis
            )
            
            # Create result
            result = self.get_success_response(
                crafting_requirements_known=True,
                target_items=target_items,
                crafting_goal=crafting_goal,
                **requirements_analysis,
                **material_analysis,
                **gathering_analysis,
                **skill_analysis,
                **strategy_recommendations,
                **goap_updates
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Crafting requirements analysis failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _determine_target_items(self, character_data, knowledge_base, crafting_goal: str) -> List[str]:
        """Determine target items to craft based on character needs and goal."""
        try:
            target_items = []
            character_level = getattr(character_data, 'level', 1)
            weapon_slot = getattr(character_data, 'weapon_slot', '')
            
            if crafting_goal == 'equipment':
                # Determine equipment needs
                if weapon_slot in ['wooden_stick', '', None] and character_level >= 2:
                    target_items.extend(['copper_dagger', 'wooden_staff'])
                
                # Add basic armor if needed
                if character_level >= 3:
                    target_items.extend(['leather_helmet', 'leather_boots'])
                    
            elif crafting_goal == 'consumables':
                # Basic consumables
                target_items.extend(['cooked_chicken', 'fried_eggs'])
                
            elif crafting_goal == 'materials':
                # Material processing items
                target_items.extend(['copper', 'iron', 'logs'])
                
            else:
                # General progression items
                if character_level >= 2:
                    target_items.append('copper_dagger')
                if character_level >= 3:
                    target_items.append('leather_helmet')
            
            # Filter to items that exist in knowledge base
            if knowledge_base and hasattr(knowledge_base, 'data'):
                items_data = knowledge_base.data.get('items', {})
                target_items = [item for item in target_items if item in items_data]
            
            return target_items[:5]  # Limit to 5 items for focused analysis
            
        except Exception as e:
            self.logger.warning(f"Target item determination failed: {e}")
            return ['copper_dagger']  # Fallback to basic item

    def _analyze_item_requirements(self, target_items: List[str], client, knowledge_base) -> Dict:
        """Analyze crafting requirements for target items."""
        try:
            analysis = {
                'item_requirements': {},
                'total_materials_needed': {},
                'workshop_requirements': set(),
                'skill_requirements': {},
                'craftable_items': [],
                'uncraftable_items': []
            }
            
            for item_code in target_items:
                item_analysis = self._analyze_single_item(item_code, client, knowledge_base)
                
                if item_analysis['craftable']:
                    analysis['craftable_items'].append(item_code)
                    analysis['item_requirements'][item_code] = item_analysis
                    
                    # Aggregate material requirements
                    materials = item_analysis.get('materials', [])
                    for material in materials:
                        material_code = material['code']
                        quantity = material['quantity']
                        
                        if material_code in analysis['total_materials_needed']:
                            analysis['total_materials_needed'][material_code] += quantity
                        else:
                            analysis['total_materials_needed'][material_code] = quantity
                    
                    # Collect workshop and skill requirements
                    if item_analysis.get('skill'):
                        skill = item_analysis['skill']
                        level = item_analysis.get('skill_level', 1)
                        if skill not in analysis['skill_requirements'] or analysis['skill_requirements'][skill] < level:
                            analysis['skill_requirements'][skill] = level
                    
                    if item_analysis.get('workshop_type'):
                        analysis['workshop_requirements'].add(item_analysis['workshop_type'])
                        
                else:
                    analysis['uncraftable_items'].append(item_code)
            
            analysis['workshop_requirements'] = list(analysis['workshop_requirements'])
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Item requirements analysis failed: {e}")
            return {'craftable_items': [], 'total_materials_needed': {}}

    def _analyze_single_item(self, item_code: str, client, knowledge_base) -> Dict:
        """Analyze crafting requirements for a single item."""
        try:
            analysis = {
                'item_code': item_code,
                'craftable': False,
                'materials': [],
                'skill': None,
                'skill_level': 1,
                'workshop_type': None,
                'item_name': item_code
            }
            
            # Try to get item data from API
            try:
                item_response = get_item_api(code=item_code, client=client)
                if item_response and item_response.data:
                    item_data = item_response.data
                    analysis['item_name'] = getattr(item_data, 'name', item_code)
                    
                    # Check if item has crafting recipe
                    craft_info = getattr(item_data, 'craft', None)
                    if craft_info:
                        analysis['craftable'] = True
                        analysis['skill'] = getattr(craft_info, 'skill', None)
                        analysis['skill_level'] = getattr(craft_info, 'level', 1)
                        
                        # Get materials if available
                        materials = getattr(craft_info, 'items', [])
                        if materials:
                            for material in materials:
                                analysis['materials'].append({
                                    'code': getattr(material, 'code', ''),
                                    'quantity': getattr(material, 'quantity', 1)
                                })
                        
                        # Determine workshop type from skill
                        analysis['workshop_type'] = analysis['skill']
                        
            except Exception as api_error:
                self.logger.debug(f"API item lookup failed for {item_code}: {api_error}")
            
            # Fall back to knowledge base if API failed
            if not analysis['craftable'] and knowledge_base and hasattr(knowledge_base, 'data'):
                items_data = knowledge_base.data.get('items', {})
                item_kb_data = items_data.get(item_code, {})
                
                craft_data = item_kb_data.get('craft_data', {})
                if craft_data:
                    analysis['craftable'] = True
                    analysis['skill'] = craft_data.get('skill', 'unknown')
                    analysis['skill_level'] = craft_data.get('level', 1)
                    analysis['workshop_type'] = analysis['skill']
                    
                    # Get materials from knowledge base
                    materials = craft_data.get('materials', [])
                    if materials:
                        analysis['materials'] = materials
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Single item analysis failed for {item_code}: {e}")
            return {'item_code': item_code, 'craftable': False}

    def _analyze_material_availability(self, character_data, requirements_analysis: Dict, 
                                     knowledge_base) -> Dict:
        """Analyze current material availability vs requirements."""
        try:
            analysis = {
                'current_materials': {},
                'material_sufficiency': {},
                'total_sufficiency_score': 0.0,
                'missing_materials': {},
                'excess_materials': {},
                'ready_to_craft': []
            }
            
            # Get current inventory
            inventory = getattr(character_data, 'inventory', [])
            
            # Count current materials
            for item in inventory:
                if hasattr(item, 'code') and hasattr(item, 'quantity'):
                    code = item.code
                    quantity = item.quantity
                    if quantity > 0:
                        analysis['current_materials'][code] = quantity
            
            # Analyze sufficiency for each required material
            total_materials_needed = requirements_analysis.get('total_materials_needed', {})
            sufficient_count = 0
            total_requirements = len(total_materials_needed)
            
            for material_code, needed_quantity in total_materials_needed.items():
                current_quantity = analysis['current_materials'].get(material_code, 0)
                
                if current_quantity >= needed_quantity:
                    analysis['material_sufficiency'][material_code] = 'sufficient'
                    analysis['excess_materials'][material_code] = current_quantity - needed_quantity
                    sufficient_count += 1
                else:
                    analysis['material_sufficiency'][material_code] = 'insufficient'
                    analysis['missing_materials'][material_code] = needed_quantity - current_quantity
            
            # Calculate overall sufficiency
            if total_requirements > 0:
                analysis['total_sufficiency_score'] = sufficient_count / total_requirements
            
            # Check which items are ready to craft
            for item_code, item_req in requirements_analysis.get('item_requirements', {}).items():
                can_craft = True
                for material in item_req.get('materials', []):
                    material_code = material['code']
                    needed = material['quantity']
                    available = analysis['current_materials'].get(material_code, 0)
                    
                    if available < needed:
                        can_craft = False
                        break
                
                if can_craft:
                    analysis['ready_to_craft'].append(item_code)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Material availability analysis failed: {e}")
            return {'total_sufficiency_score': 0.0, 'missing_materials': {}}

    def _analyze_gathering_needs(self, requirements_analysis: Dict, material_analysis: Dict,
                               knowledge_base) -> Dict:
        """Analyze material gathering needs and strategies."""
        try:
            analysis = {
                'gathering_priorities': [],
                'resource_sources': {},
                'gathering_strategy': 'mixed',
                'estimated_gathering_time': 'unknown'
            }
            
            missing_materials = material_analysis.get('missing_materials', {})
            
            # Prioritize materials by urgency and quantity needed
            material_priorities = []
            for material_code, needed_quantity in missing_materials.items():
                priority_score = needed_quantity  # Simple prioritization by quantity
                
                # Boost priority for critical materials
                if material_code in ['copper_ore', 'iron_ore', 'coal']:
                    priority_score += 10  # Higher priority for processing materials
                
                material_priorities.append({
                    'material': material_code,
                    'quantity_needed': needed_quantity,
                    'priority_score': priority_score,
                    'source_type': self._determine_material_source(material_code, knowledge_base)
                })
            
            # Sort by priority score (highest first)
            material_priorities.sort(key=lambda x: x['priority_score'], reverse=True)
            analysis['gathering_priorities'] = material_priorities
            
            # Determine gathering strategy
            if len(material_priorities) <= 2:
                analysis['gathering_strategy'] = 'focused'
            elif any(p['source_type'] == 'monster' for p in material_priorities):
                analysis['gathering_strategy'] = 'combat_and_gathering'
            else:
                analysis['gathering_strategy'] = 'resource_gathering'
            
            # Build resource sources map
            for priority_item in material_priorities:
                material = priority_item['material']
                source_info = self._get_material_source_info(material, knowledge_base)
                analysis['resource_sources'][material] = source_info
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Gathering needs analysis failed: {e}")
            return {'gathering_priorities': [], 'gathering_strategy': 'mixed'}

    def _determine_material_source(self, material_code: str, knowledge_base) -> str:
        """Determine the primary source type for a material."""
        try:
            # Common material source patterns
            ore_materials = ['copper_ore', 'iron_ore', 'coal', 'gold_ore']
            wood_materials = ['ash_wood', 'birch_wood', 'dead_wood']
            processed_materials = ['copper', 'iron', 'logs', 'plank']
            
            if material_code in ore_materials:
                return 'mining'
            elif material_code in wood_materials:
                return 'woodcutting'
            elif material_code in processed_materials:
                return 'processing'
            else:
                # Check knowledge base for more specific info
                if knowledge_base and hasattr(knowledge_base, 'data'):
                    # Could check resources or monsters data for source info
                    resources = knowledge_base.data.get('resources', {})
                    if material_code in resources:
                        return 'resource'
                    
                    monsters = knowledge_base.data.get('monsters', {})
                    for monster_data in monsters.values():
                        drops = monster_data.get('drops', [])
                        if any(drop.get('code') == material_code for drop in drops):
                            return 'monster'
                
                return 'unknown'
                
        except Exception as e:
            self.logger.warning(f"Material source determination failed for {material_code}: {e}")
            return 'unknown'

    def _get_material_source_info(self, material_code: str, knowledge_base) -> Dict:
        """Get detailed source information for a material."""
        try:
            source_info = {
                'material': material_code,
                'source_type': self._determine_material_source(material_code, knowledge_base),
                'locations': [],
                'methods': []
            }
            
            if knowledge_base and hasattr(knowledge_base, 'data'):
                # Check resources for location info
                resources = knowledge_base.data.get('resources', {})
                resource_data = resources.get(material_code, {})
                if resource_data:
                    locations = resource_data.get('locations', [])
                    source_info['locations'] = locations
                    source_info['methods'].append('gathering')
                
                # Check monsters for drop info
                monsters = knowledge_base.data.get('monsters', {})
                for monster_code, monster_data in monsters.items():
                    drops = monster_data.get('drops', [])
                    for drop in drops:
                        if drop.get('code') == material_code:
                            source_info['methods'].append('combat')
                            monster_locations = monster_data.get('locations', [])
                            source_info['locations'].extend(monster_locations)
                            break
            
            return source_info
            
        except Exception as e:
            self.logger.warning(f"Material source info lookup failed for {material_code}: {e}")
            return {'material': material_code, 'source_type': 'unknown', 'locations': []}

    def _analyze_skill_requirements(self, requirements_analysis: Dict, character_data) -> Dict:
        """Analyze skill requirements for crafting goals."""
        try:
            analysis = {
                'required_skills': {},
                'current_skills': {},
                'skill_gaps': {},
                'skills_sufficient': True,
                'priority_skill_upgrades': []
            }
            
            skill_requirements = requirements_analysis.get('skill_requirements', {})
            
            # Get current skill levels
            for skill in skill_requirements.keys():
                skill_attr = f"{skill}_level"
                current_level = getattr(character_data, skill_attr, 0)
                analysis['current_skills'][skill] = current_level
            
            # Calculate skill gaps
            for skill, required_level in skill_requirements.items():
                current_level = analysis['current_skills'].get(skill, 0)
                analysis['required_skills'][skill] = required_level
                
                if current_level < required_level:
                    gap = required_level - current_level
                    analysis['skill_gaps'][skill] = gap
                    analysis['skills_sufficient'] = False
                    
                    analysis['priority_skill_upgrades'].append({
                        'skill': skill,
                        'current_level': current_level,
                        'required_level': required_level,
                        'gap': gap
                    })
            
            # Sort skill upgrades by gap (largest first)
            analysis['priority_skill_upgrades'].sort(key=lambda x: x['gap'], reverse=True)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Skill requirements analysis failed: {e}")
            return {'skills_sufficient': True, 'skill_gaps': {}}

    def _generate_crafting_strategy(self, requirements_analysis: Dict, material_analysis: Dict,
                                  gathering_analysis: Dict, skill_analysis: Dict) -> Dict:
        """Generate comprehensive crafting strategy recommendations."""
        try:
            strategy = {
                'primary_strategy': 'assess_needs',
                'immediate_actions': [],
                'material_gathering_plan': [],
                'skill_development_plan': [],
                'crafting_sequence': []
            }
            
            skills_sufficient = skill_analysis.get('skills_sufficient', True)
            material_sufficiency = material_analysis.get('total_sufficiency_score', 0.0)
            ready_to_craft = material_analysis.get('ready_to_craft', [])
            
            # Determine primary strategy
            if not skills_sufficient:
                strategy['primary_strategy'] = 'skill_development_first'
                strategy['immediate_actions'].extend([
                    'Upgrade required skills before crafting',
                    'Focus on skill training activities'
                ])
                
                # Add skill development plan
                skill_upgrades = skill_analysis.get('priority_skill_upgrades', [])
                for upgrade in skill_upgrades:
                    strategy['skill_development_plan'].append(
                        f"Train {upgrade['skill']} from level {upgrade['current_level']} to {upgrade['required_level']}"
                    )
                    
            elif material_sufficiency >= 0.8:
                strategy['primary_strategy'] = 'ready_to_craft'
                strategy['immediate_actions'].extend([
                    'Begin crafting available items',
                    'Gather remaining materials for complete goals'
                ])
                
                # Set crafting sequence
                strategy['crafting_sequence'] = ready_to_craft
                
            elif material_sufficiency >= 0.5:
                strategy['primary_strategy'] = 'mixed_gathering_and_crafting'
                strategy['immediate_actions'].extend([
                    'Craft items with available materials',
                    'Gather missing materials for remaining items'
                ])
                
            else:
                strategy['primary_strategy'] = 'material_gathering_focus'
                strategy['immediate_actions'].extend([
                    'Focus on material gathering',
                    'Prioritize high-value materials first'
                ])
            
            # Generate material gathering plan
            gathering_priorities = gathering_analysis.get('gathering_priorities', [])
            for priority_item in gathering_priorities[:3]:  # Top 3 priorities
                material = priority_item['material']
                quantity = priority_item['quantity_needed']
                source_type = priority_item['source_type']
                
                strategy['material_gathering_plan'].append(
                    f"Gather {quantity}x {material} via {source_type}"
                )
            
            return strategy
            
        except Exception as e:
            self.logger.warning(f"Crafting strategy generation failed: {e}")
            return {'primary_strategy': 'assess_needs', 'immediate_actions': []}

    def _determine_crafting_state_updates(self, requirements_analysis: Dict, material_analysis: Dict,
                                        gathering_analysis: Dict, skill_analysis: Dict) -> Dict:
        """Determine GOAP state updates for crafting analysis."""
        try:
            materials_sufficient = material_analysis.get('total_sufficiency_score', 0.0) >= 0.8
            has_some_materials = material_analysis.get('total_sufficiency_score', 0.0) > 0.0
            skills_sufficient = skill_analysis.get('skills_sufficient', True)
            ready_to_craft = len(material_analysis.get('ready_to_craft', [])) > 0
            
            # Determine need for crafting materials
            need_materials = not materials_sufficient and len(gathering_analysis.get('gathering_priorities', [])) > 0
            
            return {
                'need_crafting_materials': need_materials,
                'has_crafting_materials': has_some_materials,
                'materials_sufficient': materials_sufficient,
                'material_requirements_known': True,
                'skills_sufficient_for_crafting': skills_sufficient,
                'ready_to_craft_items': ready_to_craft,
                'crafting_strategy_determined': True
            }
            
        except Exception as e:
            self.logger.warning(f"Crafting state updates determination failed: {e}")
            return {'need_crafting_materials': True, 'materials_sufficient': False}

    def __repr__(self):
        return "AnalyzeCraftingRequirementsAction()"