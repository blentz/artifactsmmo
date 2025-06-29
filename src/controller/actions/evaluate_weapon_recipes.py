""" EvaluateWeaponRecipesAction module """

import logging
from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.items.get_all_item import sync as get_all_items_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from artifactsmmo_api_client.models.item_type import ItemType
from .base import ActionBase


class EvaluateWeaponRecipesAction(ActionBase):
    """ 
    Action to intelligently evaluate all available weapon recipes and select 
    the best craftable option based on:
    1. Weapon stats improvement over current equipment
    2. Material availability (inventory + nearby resources)
    3. Workshop compatibility
    4. Character skill levels
    """

    def __init__(self, character_name: str, current_weapon: str = None, character_level: int = 1, **kwargs):
        """
        Initialize the weapon recipe evaluation action.

        Args:
            character_name: Name of the character
            current_weapon: Current weapon equipped (for comparison)
            character_level: Character level for filtering appropriate weapons
            **kwargs: Additional parameters including knowledge_base and action_config
        """
        super().__init__()
        self.character_name = character_name
        self.current_weapon = current_weapon or 'wooden_stick'
        self.character_level = character_level
        self.kwargs = kwargs
        self.logger = logging.getLogger(__name__)

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Evaluate all weapon recipes and select the best craftable option """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_name=self.character_name,
            current_weapon=self.current_weapon,
            character_level=self.character_level
        )
        
        try:
            # Get current character data to extract skills and inventory
            from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
            character_response = get_character_api(name=self.character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            # Store character data for skill discovery
            self.character_data = character_data
            inventory = getattr(character_data, 'inventory', [])
            character_skills = self._extract_character_skills_from_api(character_data)
            
            # Step 1: Fetch all weapon recipes
            weapon_recipes = self._fetch_weapon_recipes(client)
            if not weapon_recipes:
                return self.get_error_response("No weapon recipes found")
            
            self.logger.info(f"Found {len(weapon_recipes)} weapon recipes to evaluate")
            
            # Step 2: Get current weapon stats for comparison
            current_weapon_stats = self._get_weapon_stats(client, self.current_weapon)
            
            # Step 3: Evaluate each weapon recipe
            recipe_evaluations = []
            for weapon_code, recipe_data in weapon_recipes.items():
                evaluation = self._evaluate_weapon_recipe(
                    client, weapon_code, recipe_data, current_weapon_stats,
                    inventory, character_skills
                )
                if evaluation:
                    recipe_evaluations.append(evaluation)
            
            if not recipe_evaluations:
                # Check if the issue is skill requirements - check a few basic weapons
                skill_blocked_weapons = self._check_skill_blocked_weapons(client, character_skills)
                if skill_blocked_weapons:
                    # Found weapons that are blocked by skill requirements
                    lowest_skill_weapon = min(skill_blocked_weapons, key=lambda w: w['required_skill_level'])
                    
                    result = self.get_success_response(
                        skill_upgrade_needed=True,
                        required_skill=lowest_skill_weapon['required_skill'],
                        required_skill_level=lowest_skill_weapon['required_skill_level'],
                        current_skill_level=character_skills.get(f"{lowest_skill_weapon['required_skill']}_level", 0),
                        blocked_weapon=lowest_skill_weapon['weapon_code'],
                        message=f"Need {lowest_skill_weapon['required_skill']} level {lowest_skill_weapon['required_skill_level']} to craft {lowest_skill_weapon['weapon_code']}"
                    )
                    self.log_execution_result(result)
                    return result
                
                return self.get_error_response("No craftable weapon recipes found")
            
            # Step 4: Select the best recipe
            best_recipe = self._select_best_recipe(recipe_evaluations)
            
            result = self.get_success_response(
                selected_weapon=best_recipe['weapon_code'],
                item_code=best_recipe['weapon_code'],  # For find_correct_workshop compatibility
                weapon_name=best_recipe['weapon_name'],
                stat_improvement=best_recipe['stat_improvement'],
                required_materials=best_recipe['required_materials'],
                workshop_type=best_recipe['workshop_type'],
                craftability_score=best_recipe['craftability_score'],
                recipe_evaluation=best_recipe
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Weapon recipe evaluation failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _fetch_weapon_recipes(self, client) -> Dict[str, Dict]:
        """Fetch weapon recipes from the API - only real data"""
        try:
            # Get all weapons from API with pagination to avoid timeouts
            items_response = get_all_items_api(client=client, type_=ItemType.WEAPON, page=1, size=20)
            
            if not items_response or not items_response.data:
                self.logger.warning("No weapons found in API response")
                return {}
            
            weapon_recipes = {}
            processed = 0
            max_weapons = 5  # Limit to prevent hanging
            
            for weapon in items_response.data:
                if processed >= max_weapons:
                    break
                    
                if not hasattr(weapon, 'code'):
                    continue
                    
                weapon_code = weapon.code
                
                try:
                    # Get detailed weapon information
                    weapon_details = get_item_api(code=weapon_code, client=client)
                    if weapon_details and weapon_details.data:
                        craft_data = getattr(weapon_details.data, 'craft', None)
                        
                        # Only include weapons that have craft data
                        if craft_data and hasattr(craft_data, 'items') and craft_data.items:
                            weapon_recipes[weapon_code] = {
                                'name': getattr(weapon_details.data, 'name', weapon_code),
                                'level': getattr(weapon_details.data, 'level', 1),
                                'type': getattr(weapon_details.data, 'type', 'weapon'),
                                'craft': craft_data,
                                'effects': getattr(weapon_details.data, 'effects', []),
                                'stats': self._extract_weapon_stats(weapon_details.data)
                            }
                            self.logger.info(f"Found craftable weapon: {weapon_code} (level {weapon_recipes[weapon_code]['level']})")
                            processed += 1
                    
                    # Small delay to avoid API rate limits
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.warning(f"Could not fetch weapon {weapon_code}: {e}")
                    continue
            
            self.logger.info(f"Successfully loaded {len(weapon_recipes)} weapon recipes from API")
            return weapon_recipes
            
        except Exception as e:
            self.logger.error(f"Error fetching weapon recipes: {e}")
            return {}

    def _get_weapon_stats(self, client, weapon_code: str) -> Dict:
        """Get stats for a specific weapon"""
        try:
            weapon_response = get_item_api(code=weapon_code, client=client)
            if weapon_response and weapon_response.data:
                return self._extract_weapon_stats(weapon_response.data)
            return {}
        except Exception as e:
            self.logger.warning(f"Could not get stats for weapon {weapon_code}: {e}")
            return {}

    def _extract_weapon_stats(self, weapon_data) -> Dict:
        """Extract weapon statistics from API response"""
        stats = {}
        
        # Get stat fields from knowledge base discovery
        stat_fields = self._get_stat_fields_from_knowledge_base()
        
        for field in stat_fields:
            if hasattr(weapon_data, field):
                value = getattr(weapon_data, field, 0)
                if value and value > 0:
                    stats[field] = value
        
        # Extract effects
        if hasattr(weapon_data, 'effects') and weapon_data.effects:
            for effect in weapon_data.effects:
                if hasattr(effect, 'name') and hasattr(effect, 'value'):
                    effect_name = effect.name.lower().replace(' ', '_')
                    stats[effect_name] = effect.value
        
        return stats

    def _evaluate_weapon_recipe(self, client, weapon_code: str, recipe_data: Dict,
                               current_stats: Dict, inventory: List, 
                               character_skills: Dict) -> Optional[Dict]:
        """Evaluate a single weapon recipe for craftability and improvement"""
        
        # Check character level requirement
        weapon_level = recipe_data.get('level', 1)
        if weapon_level > self.character_level + 2:  # Allow weapons up to 2 levels higher
            return None
        
        # Get crafting requirements - only use real API data
        craft_info = recipe_data.get('craft')
        if not craft_info:
            # No craft data = not craftable, skip this weapon
            return None
        
        # Extract material requirements from real craft data
        required_materials = self._extract_material_requirements(craft_info)
        if not required_materials:
            # No materials = invalid craft data, skip this weapon
            return None
        
        # Get skill requirements from craft data
        required_skill = getattr(craft_info, 'skill', 'weaponcrafting')
        required_skill_level = getattr(craft_info, 'level', 1)
        
        # Check skill requirements
        character_skill_level = character_skills.get(f"{required_skill}_level", 0)
        if character_skill_level < required_skill_level:
            self.logger.info(f"Skipping {weapon_code}: requires {required_skill} level {required_skill_level}, character has {character_skill_level}")
            return None  # Don't allow weapons we can't craft
        
        # Evaluate material availability
        material_availability = self._evaluate_material_availability(required_materials, inventory)
        
        # Calculate stat improvement
        weapon_stats = recipe_data.get('stats', {})
        stat_improvement = self._calculate_stat_improvement(current_stats, weapon_stats)
        
        # Calculate overall craftability score
        craftability_score = self._calculate_craftability_score(
            stat_improvement, material_availability, weapon_level, required_skill_level
        )
        
        return {
            'weapon_code': weapon_code,
            'weapon_name': recipe_data.get('name', weapon_code),
            'weapon_level': weapon_level,
            'required_materials': required_materials,
            'material_availability': material_availability,
            'workshop_type': required_skill,
            'required_skill_level': required_skill_level,
            'stat_improvement': stat_improvement,
            'craftability_score': craftability_score,
            'weapon_stats': weapon_stats
        }

    def _extract_material_requirements(self, craft_info) -> List[Dict]:
        """Extract material requirements from craft info"""
        materials = []
        
        if hasattr(craft_info, 'items') and craft_info.items:
            for item in craft_info.items:
                if hasattr(item, 'code') and hasattr(item, 'quantity'):
                    materials.append({
                        'code': item.code,
                        'quantity': item.quantity
                    })
        
        return materials

    def _evaluate_material_availability(self, required_materials: List[Dict], 
                                      inventory: List) -> Dict:
        """Evaluate how many required materials are available"""
        inventory_lookup = {}
        for item in inventory:
            # Handle both dict and InventorySlot object formats
            if hasattr(item, 'code') and hasattr(item, 'quantity'):
                # InventorySlot object from API
                code = getattr(item, 'code', '')
                quantity = getattr(item, 'quantity', 0)
            else:
                # Dictionary format
                code = item.get('code', '')
                quantity = item.get('quantity', 0)
            
            if code and quantity > 0:
                inventory_lookup[code] = quantity
        
        availability = {
            'available_materials': 0,
            'total_materials': len(required_materials),
            'missing_materials': [],
            'sufficient_quantities': 0
        }
        
        for material in required_materials:
            material_code = material['code']
            required_quantity = material['quantity']
            available_quantity = inventory_lookup.get(material_code, 0)
            
            if available_quantity > 0:
                availability['available_materials'] += 1
                if available_quantity >= required_quantity:
                    availability['sufficient_quantities'] += 1
                else:
                    availability['missing_materials'].append({
                        'code': material_code,
                        'needed': required_quantity - available_quantity
                    })
            else:
                availability['missing_materials'].append({
                    'code': material_code,
                    'needed': required_quantity
                })
        
        return availability

    def _calculate_stat_improvement(self, current_stats: Dict, new_stats: Dict) -> Dict:
        """Calculate the stat improvement from current weapon to new weapon"""
        improvement = {
            'total_improvement': 0,
            'stat_changes': {},
            'is_upgrade': False
        }
        
        # Calculate improvement for each stat
        all_stats = set(current_stats.keys()) | set(new_stats.keys())
        
        for stat in all_stats:
            current_value = current_stats.get(stat, 0)
            new_value = new_stats.get(stat, 0)
            change = new_value - current_value
            
            if change != 0:
                improvement['stat_changes'][stat] = {
                    'current': current_value,
                    'new': new_value,
                    'change': change
                }
                
                # Weight certain stats more heavily
                weight = self._get_stat_weight(stat)
                improvement['total_improvement'] += change * weight
        
        improvement['is_upgrade'] = improvement['total_improvement'] > 0
        
        return improvement

    def _get_stat_weight(self, stat: str) -> float:
        """Get the importance weight for a stat from configuration"""
        # Get weights from action configuration, with fallback
        action_config = self.kwargs.get('action_config', {})
        weights = action_config.get('weapon_stat_weights', {})
        
        # Return configured weight or default
        return weights.get(stat, weights.get('default', 1.0))

    def _calculate_craftability_score(self, stat_improvement: Dict, 
                                    material_availability: Dict,
                                    weapon_level: int, required_skill_level: int) -> float:
        """Calculate overall craftability score for ranking recipes"""
        score = 0.0
        
        # Stat improvement score (0-100)
        if stat_improvement['is_upgrade']:
            improvement_score = min(stat_improvement['total_improvement'] * 10, 100)
            score += improvement_score
        
        # Material availability score (0-50)
        if material_availability['total_materials'] > 0:
            availability_ratio = material_availability['sufficient_quantities'] / material_availability['total_materials']
            score += availability_ratio * 50
        
        # Level appropriateness score (0-25)
        level_diff = abs(weapon_level - self.character_level)
        if level_diff <= 2:
            score += (2 - level_diff) * 12.5
        
        # Skill requirement penalty
        if required_skill_level > self.character_level:
            score -= (required_skill_level - self.character_level) * 10
        
        return max(score, 0.0)

    def _select_best_recipe(self, recipe_evaluations: List[Dict]) -> Dict:
        """Select the best recipe from evaluated options"""
        # Sort by craftability score
        recipe_evaluations.sort(key=lambda x: x['craftability_score'], reverse=True)
        
        # Log top candidates
        self.logger.info("Top weapon recipe candidates:")
        for i, recipe in enumerate(recipe_evaluations[:3]):
            self.logger.info(f"{i+1}. {recipe['weapon_name']} (score: {recipe['craftability_score']:.1f})")
        
        return recipe_evaluations[0]

    def _check_skill_blocked_weapons(self, client, character_skills: Dict) -> List[Dict]:
        """Check for weapons that are blocked only by skill requirements (have materials but not skill)"""
        skill_blocked = []
        
        # Get basic weapons from configuration, with fallback
        basic_weapons = self._get_basic_weapons_from_config()
        
        for weapon_code in basic_weapons:
            try:
                weapon_response = get_item_api(code=weapon_code, client=client)
                if not weapon_response or not weapon_response.data:
                    continue
                    
                weapon_data = weapon_response.data
                craft_info = getattr(weapon_data, 'craft', None)
                if not craft_info:
                    continue
                    
                required_skill = getattr(craft_info, 'skill', 'weaponcrafting')
                required_skill_level = getattr(craft_info, 'level', 1)
                character_skill_level = character_skills.get(f"{required_skill}_level", 0)
                
                # Check if this weapon is blocked only by skill (not materials)
                if character_skill_level < required_skill_level:
                    skill_blocked.append({
                        'weapon_code': weapon_code,
                        'weapon_name': getattr(weapon_data, 'name', weapon_code),
                        'required_skill': required_skill,
                        'required_skill_level': required_skill_level,
                        'current_skill_level': character_skill_level
                    })
                    
            except Exception as e:
                self.logger.warning(f"Error checking skill requirements for {weapon_code}: {e}")
                continue
        
        return skill_blocked

    def _extract_character_skills_from_api(self, character_data) -> Dict:
        """Extract character skill levels from API character data"""
        skills = {}
        
        # Get skill types from knowledge base discovery
        skill_types = self._get_skill_types_from_knowledge_base()
        
        for skill in skill_types:
            level_attr = f"{skill}_level"
            if hasattr(character_data, level_attr):
                skills[level_attr] = getattr(character_data, level_attr, 0)
        
        self.logger.debug(f"Extracted character skills: {skills}")
        return skills

    def _extract_character_skills(self, character_data: Dict) -> Dict:
        """Extract character skill levels from character data"""
        skills = {}
        
        # Get skill types from knowledge base discovery
        skill_types = self._get_skill_types_from_knowledge_base()
        
        for skill in skill_types:
            level_key = f"{skill}_level"
            if level_key in character_data:
                skills[level_key] = character_data[level_key]
        
        return skills

    def _get_skill_types_from_knowledge_base(self) -> List[str]:
        """Get all skill types from knowledge base discovery"""
        skill_types = []
        
        # Get knowledge base from kwargs
        knowledge_base = self.kwargs.get('knowledge_base')
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # Scan knowledge base for skill types in item craft data
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {})
                if craft_data:
                    skill = craft_data.get('skill')
                    if skill and skill != 'unknown' and skill not in skill_types:
                        skill_types.append(skill)
        
        # Scan character data directly for all skill attributes to ensure we don't miss any
        # This avoids hardcoded skill lists and discovers skills dynamically
        if hasattr(self, 'character_data'):
            character_data = self.character_data
        else:
            # If we don't have character data stored, we'll get it when needed
            character_data = None
            
        if character_data:
            for attr_name in dir(character_data):
                if attr_name.endswith('_level') and not attr_name.startswith('_'):
                    skill_name = attr_name.replace('_level', '')
                    if skill_name not in skill_types:
                        skill_types.append(skill_name)
        
        self.logger.debug(f"Discovered skill types: {skill_types}")
        return skill_types

    def _get_stat_fields_from_knowledge_base(self) -> List[str]:
        """Get weapon stat field names by scanning knowledge base for all weapon data"""
        stat_fields = set()
        
        # Get knowledge base from kwargs
        knowledge_base = self.kwargs.get('knowledge_base')
        if knowledge_base and hasattr(knowledge_base, 'data'):
            # Scan all weapon items to discover stat fields
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                # Check if this is a weapon item
                item_type = item_data.get('type')
                if item_type == 'weapon':
                    # Extract all stat field names from this weapon
                    for field_name in item_data.keys():
                        # Include stat-like fields (attack_, dmg_, res_, hp, etc.)
                        if (field_name.startswith(('attack_', 'dmg_', 'res_')) or 
                            field_name in ['hp', 'haste', 'critical_strike', 'wisdom']):
                            stat_fields.add(field_name)
        
        # Convert to sorted list for consistency
        stat_fields_list = sorted(list(stat_fields))
        
        
        self.logger.debug(f"Discovered weapon stat fields: {stat_fields_list}")
        return stat_fields_list

    def _get_basic_weapons_from_config(self) -> List[str]:
        """Get basic weapon codes from configuration"""
        action_config = self.kwargs.get('action_config', {})
        basic_weapons = action_config.get('basic_weapon_codes', [])
        
        
        return basic_weapons

    def __repr__(self):
        return f"EvaluateWeaponRecipesAction({self.character_name}, current={self.current_weapon})"