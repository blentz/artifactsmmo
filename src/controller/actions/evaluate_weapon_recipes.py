""" EvaluateWeaponRecipesAction module """

import logging
from typing import Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items_api
from artifactsmmo_api_client.models.item_type import ItemType

from src.lib.action_context import ActionContext

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

    def __init__(self):
        """
        Initialize the weapon recipe evaluation action.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Evaluate all weapon recipes and select the best craftable option """
        # Call superclass to set self._context
        super().execute(client, context)
        
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_name = context.character_name
        current_weapon = context.get('current_weapon')
        character_level = context.get('character_level', 1)
        action_config = context.get('action_config', {})
        knowledge_base = context.knowledge_base
        
        # Store character level as instance variable for use in helper methods
        self.character_level = character_level
        
        # Get default weapon from configuration or knowledge base if not provided
        if not current_weapon:
            default_weapon = action_config.get('default_weapon')
            
            # If no default in config, try to get starting weapon from knowledge base
            if not default_weapon and knowledge_base and hasattr(knowledge_base, 'data'):
                starting_equipment = knowledge_base.data.get('starting_equipment', {})
                default_weapon = starting_equipment.get('weapon', None)
                
            current_weapon = default_weapon
            
        self.log_execution_start(
            character_name=character_name,
            current_weapon=current_weapon,
            character_level=character_level
        )
        
        try:
            # Get current character data to extract skills and inventory
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            # Store character data for skill discovery
            self.character_data = character_data
            inventory = getattr(character_data, 'inventory', [])
            character_skills = self._extract_character_skills_from_api(character_data)
            
            # Extract equipped items for material availability check
            equipped_items = self._extract_equipped_items(character_data)
            self.logger.info(f"Character has equipped items: {equipped_items}")
            
            # Update current_weapon from actual equipped weapon if not already set
            if current_weapon is None and 'weapon_slot' in equipped_items:
                current_weapon = equipped_items['weapon_slot']
                self.logger.info(f"Updated current_weapon from equipped items: {current_weapon}")
            
            # Step 1: Fetch all weapon recipes
            weapon_recipes = self._fetch_weapon_recipes(client, context)
            if not weapon_recipes:
                return self.get_error_response("No weapon recipes found")
            
            self.logger.info(f"Found {len(weapon_recipes)} weapon recipes to evaluate")
            
            # Step 2: Get current weapon stats for comparison
            current_weapon_stats = self._get_weapon_stats(client, current_weapon)
            
            # Step 3: Evaluate each weapon recipe
            recipe_evaluations = []
            for weapon_code, recipe_data in weapon_recipes.items():
                evaluation = self._evaluate_weapon_recipe(
                    client, weapon_code, recipe_data, current_weapon_stats, context
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
                target_item=best_recipe['weapon_code'],  # For analyze_crafting_chain compatibility
                weapon_name=best_recipe['weapon_name'],
                current_weapon=current_weapon,  # Include actual current weapon
                stat_improvement=best_recipe['stat_improvement'],
                required_materials=best_recipe['required_materials'],
                workshop_type=best_recipe['workshop_type'],
                craftability_score=best_recipe['craftability_score'],
                recipe_evaluation=best_recipe
            )
            
            # Update action context to preserve target_item for subsequent actions
            if hasattr(self, '_context') and self._context:
                self._context.set_result('target_item', best_recipe['weapon_code'])
                self._context.set_result('item_code', best_recipe['weapon_code'])
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Weapon recipe evaluation failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _fetch_weapon_recipes(self, client, context: ActionContext) -> Dict[str, Dict]:
        """Fetch weapon recipes from knowledge base"""
        try:
            # Get knowledge base from kwargs
            knowledge_base = self._context.get('knowledge_base')
            if not knowledge_base:
                self.logger.warning("No knowledge base available, cannot fetch weapon recipes")
                return {}
            
            # Get configuration
            action_config = self._context.get('action_config', {})
            max_weapons = action_config.get('max_weapons_to_evaluate', 50)
            max_level_above = action_config.get('max_weapon_level_above_character', 1)
            max_level_below = action_config.get('max_weapon_level_below_character', 1)
            
            # Get character level for filtering
            character_level = self.character_level if hasattr(self, 'character_level') else 1
            min_level = max(1, character_level - max_level_below)
            max_level = character_level + max_level_above
            
            weapon_recipes = {}
            processed = 0
            
            # Simply access items from knowledge base data - no duplication of search
            items = knowledge_base.data.get('items', {})
            
            # Filter for weapons with craft data
            for item_code, item_data in items.items():
                if processed >= max_weapons:
                    break
                
                # Check if it's a weapon with craft data
                # The knowledge base should have proper item categorization
                # For now, check if it has weaponcrafting skill requirement
                craft_data = item_data.get('craft_data')
                if not craft_data or not craft_data.get('items'):
                    continue
                
                # Check if it's a weaponcrafting item
                craft_skill = craft_data.get('skill', '')
                if craft_skill != 'weaponcrafting':
                    continue
                
                # Filter by level range
                item_level = item_data.get('level', 1)
                if item_level < min_level or item_level > max_level:
                    continue
                
                # Convert knowledge base format to expected format for compatibility
                craft_obj = type('CraftData', (), {
                    'skill': craft_data.get('skill', 'weaponcrafting'),
                    'level': craft_data.get('level', 1),
                    'items': [type('CraftItem', (), {
                        'code': item.get('code'),
                        'quantity': item.get('quantity', 1)
                    })() for item in craft_data.get('items', [])]
                })()
                
                weapon_recipes[item_code] = {
                    'name': item_data.get('name', item_code),
                    'level': item_data.get('level', 1),
                    'type': 'weapon',
                    'craft': craft_obj,
                    'effects': item_data.get('effects', []),
                    'stats': self._extract_weapon_stats_from_kb(item_data)
                }
                
                self.logger.debug(f"Found craftable weapon: {item_code} (level {weapon_recipes[item_code]['level']})")
                processed += 1
                
                # Log wooden_staff specifically if found
                if item_code == 'wooden_staff':
                    self.logger.info(f"Found wooden_staff in weapon recipes with level {weapon_recipes[item_code]['level']}")
            
            if len(weapon_recipes) == 0:
                self.logger.warning("No craftable weapons found in knowledge base. Knowledge base may need to be populated.")
            else:
                self.logger.info(f"Successfully loaded {len(weapon_recipes)} weapon recipes from knowledge base")
            
            return weapon_recipes
            
        except Exception as e:
            self.logger.error(f"Error fetching weapon recipes from knowledge base: {e}")
            return {}

    def _get_weapon_stats(self, client, weapon_code: str) -> Dict:
        """Get stats for a specific weapon from knowledge base"""
        # Handle special case of being unarmed
        if not weapon_code or weapon_code == 'unarmed':
            self.logger.info("Character is unarmed - returning empty stats")
            return {}
            
        try:
            # Use knowledge base's get_item_data method with API fallback
            knowledge_base = self._context.knowledge_base
            if knowledge_base:
                weapon_data = knowledge_base.get_item_data(weapon_code, client=client)
                if weapon_data:
                    return self._extract_weapon_stats_from_kb(weapon_data)
            
            self.logger.warning(f"Could not get data for weapon {weapon_code}")
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

    def _extract_weapon_stats_from_kb(self, weapon_data: Dict) -> Dict:
        """Extract weapon statistics from knowledge base data"""
        stats = {}
        
        # Get stat fields from knowledge base discovery
        stat_fields = self._get_stat_fields_from_knowledge_base()
        
        # Direct stat fields
        for field in stat_fields:
            if field in weapon_data:
                value = weapon_data.get(field, 0)
                if value and value > 0:
                    stats[field] = value
        
        # Extract from effects array
        effects = weapon_data.get('effects', [])
        for effect in effects:
            if isinstance(effect, dict):
                effect_code = effect.get('code', '')
                effect_value = effect.get('value', 0)
                if effect_code and effect_value:
                    # Map effect codes to stat names
                    if effect_code.startswith('attack_'):
                        stats[effect_code] = effect_value
                    elif effect_code in ['hp', 'critical_strike', 'haste', 'wisdom']:
                        stats[effect_code] = effect_value
                    elif effect_code.startswith('dmg'):
                        stats[effect_code] = effect_value
        
        return stats

    def _evaluate_weapon_recipe(self, client, weapon_code: str, recipe_data: Dict,
                               current_stats: Dict, context: 'ActionContext') -> Optional[Dict]:
        """Evaluate a single weapon recipe for craftability and improvement"""
        
        # Get required data from character_state in context
        character_state = context.character_state
        if not character_state or not hasattr(character_state, 'data'):
            return None
            
        char_data = character_state.data
        inventory = char_data.get('inventory', [])
        
        # Extract character skills from character data dict
        character_skills = self._extract_character_skills(char_data)
        
        # Extract equipped items from character data dict
        equipped_items = self._extract_equipped_items_from_dict(char_data)
        
        # Check character level requirement
        weapon_level = recipe_data.get('level', 1)
        action_config = self._context.get('action_config', {})
        max_level_above = action_config.get('max_weapon_level_above_character', 2)
        max_level_below = action_config.get('max_weapon_level_below_character', 1)
        
        # Filter weapons that are too high level
        if weapon_level > self.character_level + max_level_above:
            return None
            
        # Filter weapons that are too low level (optional)
        if weapon_level < self.character_level - max_level_below:
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
        
        # Evaluate material availability (including equipped items)
        material_availability = self._evaluate_material_availability(required_materials, inventory, equipped_items)
        
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
                                      inventory: List, equipped_items: Dict = None) -> Dict:
        """Evaluate how many required materials are available (including equipped items)"""
        inventory_lookup = {}
        
        # First, add items from inventory
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
        
        # Also count equipped items as available materials
        if equipped_items:
            for slot, item_code in equipped_items.items():
                if item_code:
                    # Equipped items count as 1 available (add to existing quantity if any)
                    inventory_lookup[item_code] = inventory_lookup.get(item_code, 0) + 1
                    self.logger.info(f"Including equipped item {item_code} from {slot} as available material")
        
        # Store inventory lookup for display purposes
        self._last_inventory_lookup = inventory_lookup
        
        availability = {
            'available_materials': 0,
            'total_materials': len(required_materials),
            'missing_materials': [],
            'sufficient_quantities': 0,
            'partial_materials': [],  # New: materials we have some but not enough of
            'completion_ratio': 0.0,  # New: overall completion ratio (0.0 to 1.0)
            'inventory_score': 0.0    # New: weighted score based on quantities
        }
        
        total_completion_score = 0.0
        max_possible_score = 0.0
        
        for material in required_materials:
            material_code = material['code']
            required_quantity = material['quantity']
            available_quantity = inventory_lookup.get(material_code, 0)
            max_possible_score += required_quantity
            
            if available_quantity > 0:
                availability['available_materials'] += 1
                total_completion_score += min(available_quantity, required_quantity)
                
                if available_quantity >= required_quantity:
                    availability['sufficient_quantities'] += 1
                else:
                    # We have some but not enough
                    availability['partial_materials'].append({
                        'code': material_code,
                        'have': available_quantity,
                        'need': required_quantity,
                        'missing': required_quantity - available_quantity,
                        'completion_ratio': available_quantity / required_quantity
                    })
                    availability['missing_materials'].append({
                        'code': material_code,
                        'needed': required_quantity - available_quantity
                    })
            else:
                # We have none of this material
                availability['missing_materials'].append({
                    'code': material_code,
                    'needed': required_quantity
                })
        
        # Calculate overall completion metrics
        if max_possible_score > 0:
            availability['completion_ratio'] = total_completion_score / max_possible_score
            availability['inventory_score'] = total_completion_score
        
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
        action_config = self._context.get('action_config', {})
        weights = action_config.get('weapon_stat_weights', {})
        
        # Return configured weight or get from knowledge base
        configured_weight = weights.get(stat)
        if configured_weight is not None:
            return configured_weight
            
        # Try to determine weight from knowledge base stat importance
        knowledge_base = self._context.get('knowledge_base')
        if knowledge_base and hasattr(knowledge_base, 'data'):
            stat_importance = knowledge_base.data.get('stat_importance', {})
            kb_weight = stat_importance.get(stat)
            if kb_weight is not None:
                return kb_weight
        
        # Default weight from config or 1.0
        return weights.get('default', 1.0)

    def _calculate_craftability_score(self, stat_improvement: Dict, 
                                    material_availability: Dict,
                                    weapon_level: int, required_skill_level: int) -> float:
        """Calculate overall craftability score for ranking recipes"""
        # Get scoring configuration
        action_config = self._context.get('action_config', {})
        scoring = action_config.get('craftability_scoring', {})
        
        score = 0.0
        
        # INVENTORY PROXIMITY SCORE - Primary factor for recipe selection
        # Prioritize recipes where we're closest to completion based on current inventory
        inventory_proximity_weight = scoring.get('inventory_proximity_weight', 1000)  # Very high weight
        
        if material_availability['total_materials'] > 0:
            # Use the new completion ratio for more accurate proximity scoring
            completion_ratio = material_availability['completion_ratio']
            total_required = material_availability['total_materials']
            available_count = material_availability['available_materials']
            sufficient_count = material_availability['sufficient_quantities']
            
            # Primary score based on actual quantity completion (0.0 to 1.0)
            quantity_completion_score = completion_ratio
            
            # Bonus for having any materials at all (encourages partial matches)
            material_availability_bonus = available_count / total_required * 0.5
            
            # Extra bonus for complete materials (encourages nearly-complete recipes)
            complete_materials_bonus = sufficient_count / total_required * 0.5
            
            # Combined proximity score (0.0 to 2.0 range)
            proximity_score = quantity_completion_score + material_availability_bonus + complete_materials_bonus
            
            # Apply high weight to inventory proximity
            score += proximity_score * inventory_proximity_weight
            
            self.logger.debug(f"Inventory proximity: {completion_ratio:.2f} completion ratio, "
                            f"{available_count}/{total_required} materials available, "
                            f"{sufficient_count}/{total_required} sufficient, proximity score: {proximity_score:.2f}")
        
        # Stat improvement score (lower weight than inventory proximity)
        stat_weight = scoring.get('stat_improvement_weight', 50)  # Reduced from 100
        stat_multiplier = scoring.get('stat_improvement_multiplier', 5)  # Reduced from 10
        if stat_improvement['is_upgrade']:
            improvement_score = min(stat_improvement['total_improvement'] * stat_multiplier, stat_weight)
            score += improvement_score
        
        # Level appropriateness score
        level_weight = scoring.get('level_appropriateness_weight', 25)
        max_level_diff = scoring.get('max_level_difference', 2)
        level_diff = abs(weapon_level - self.character_level)
        if level_diff <= max_level_diff:
            score += (max_level_diff - level_diff) * (level_weight / max_level_diff)
        
        # Skill requirement penalty
        skill_penalty_multiplier = scoring.get('skill_penalty_multiplier', 10)
        if required_skill_level > self.character_level:
            score -= (required_skill_level - self.character_level) * skill_penalty_multiplier
        
        return max(score, 0.0)

    def _select_best_recipe(self, recipe_evaluations: List[Dict]) -> Dict:
        """Select the best recipe from evaluated options"""
        # Sort by craftability score
        recipe_evaluations.sort(key=lambda x: x['craftability_score'], reverse=True)
        
        # Log top candidates with detailed material information
        self.logger.info("Top weapon recipe candidates:")
        for i, recipe in enumerate(recipe_evaluations[:3]):
            availability = recipe['material_availability']
            completion_ratio = availability.get('completion_ratio', 0.0)
            
            # Show material details for top candidates
            material_details = []
            # Get the inventory lookup to show actual quantities
            inventory_lookup = getattr(self, '_last_inventory_lookup', {})
            
            for material in recipe['required_materials']:
                material_code = material['code']
                required_qty = material['quantity']
                
                # Get actual quantity from inventory lookup
                have_qty = inventory_lookup.get(material_code, 0)
                
                # Check if we have any of this material in partial_materials
                for partial in availability.get('partial_materials', []):
                    if partial['code'] == material_code:
                        have_qty = partial['have']
                        break
                
                # Format the material details
                if have_qty >= required_qty:
                    material_details.append(f"{material_code}: {have_qty}/{required_qty} ✓")
                else:
                    material_details.append(f"{material_code}: {have_qty}/{required_qty}")
            
            materials_str = ", ".join(material_details)
            self.logger.info(f"{i+1}. {recipe['weapon_name']} (score: {recipe['craftability_score']:.1f}, "
                           f"completion: {completion_ratio:.1%}) - [{materials_str}]")
        
        return recipe_evaluations[0]

    def _check_skill_blocked_weapons(self, client, character_skills: Dict) -> List[Dict]:
        """Check for weapons that are blocked only by skill requirements"""
        skill_blocked = []
        
        # Get knowledge base and configuration
        knowledge_base = self._context.get('knowledge_base')
        action_config = self._context.get('action_config', {})
        max_check_level = action_config.get('max_skill_check_weapon_level', self.character_level + 5)
        max_checks = action_config.get('max_skill_blocked_checks', 20)
        
        weapons_to_check = []
        
        # Get weapons from knowledge base
        if knowledge_base:
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                if item_data.get('type') == 'weapon':
                    weapon_level = item_data.get('level', 1)
                    if weapon_level <= max_check_level:
                        weapons_to_check.append((item_code, item_data))
        
        # If no weapons in knowledge base, try API as fallback
        if not weapons_to_check:
            try:
                weapons_response = get_all_items_api(client=client, type_=ItemType.WEAPON, page=1, size=50)
                if weapons_response and weapons_response.data:
                    for weapon in weapons_response.data:
                        if hasattr(weapon, 'code') and hasattr(weapon, 'level'):
                            if weapon.level <= max_check_level:
                                weapons_to_check.append((weapon.code, None))
            except Exception as e:
                self.logger.warning(f"Error fetching weapons from API: {e}")
        
        # Check each weapon for skill requirements
        checked_count = 0
        
        for weapon_code, kb_data in weapons_to_check:
            if checked_count >= max_checks:
                break
                
            try:
                # Use knowledge base data if available, otherwise get from API
                if kb_data and 'craft_data' in kb_data:
                    craft_data = kb_data['craft_data']
                    required_skill = craft_data.get('skill', 'weaponcrafting')
                    required_skill_level = craft_data.get('level', 1)
                    weapon_name = kb_data.get('name', weapon_code)
                else:
                    # Use get_item_data for API fallback
                    weapon_data = knowledge_base.get_item_data(weapon_code, client=client) if knowledge_base else None
                    if not weapon_data:
                        continue
                    
                    craft_data = weapon_data.get('craft_data')
                    if not craft_data:
                        continue
                    
                    required_skill = craft_data.get('skill', 'weaponcrafting')
                    required_skill_level = craft_data.get('level', 1)
                    weapon_name = weapon_data.get('name', weapon_code)
                
                character_skill_level = character_skills.get(f"{required_skill}_level", 0)
                
                # Check if this weapon is blocked only by skill
                if character_skill_level < required_skill_level:
                    skill_blocked.append({
                        'weapon_code': weapon_code,
                        'weapon_name': weapon_name,
                        'required_skill': required_skill,
                        'required_skill_level': required_skill_level,
                        'current_skill_level': character_skill_level
                    })
                
                checked_count += 1
                    
            except Exception as e:
                self.logger.warning(f"Error checking skill requirements for {weapon_code}: {e}")
                continue
        
        # Sort by required skill level (ascending) to find easiest upgrade path
        skill_blocked.sort(key=lambda x: x['required_skill_level'])
        
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
        knowledge_base = self._context.get('knowledge_base')
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
        knowledge_base = self._context.get('knowledge_base')
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
        action_config = self._context.get('action_config', {})
        basic_weapons = action_config.get('basic_weapon_codes', [])
        return basic_weapons
    
    def _get_basic_weapons_from_knowledge_base(self) -> List[str]:
        """Get weapon codes from knowledge base based on level range"""
        basic_weapons = []
        
        knowledge_base = self._context.get('knowledge_base')
        if knowledge_base and hasattr(knowledge_base, 'data'):
            items = knowledge_base.data.get('items', {})
            
            # Get max level for "basic" weapons from config
            action_config = self._context.get('action_config', {})
            max_basic_level = action_config.get('max_basic_weapon_level', 5)
            
            # Find all weapons within level range
            for item_code, item_data in items.items():
                if item_data.get('type') == 'weapon':
                    level = item_data.get('level', 1)
                    if level <= max_basic_level:
                        basic_weapons.append(item_code)
            
            # Sort by level for consistency
            basic_weapons.sort(key=lambda code: items.get(code, {}).get('level', 1))
        
        return basic_weapons

    def _extract_equipped_items(self, character_data) -> Dict[str, str]:
        """Extract equipped items from character data API object"""
        equipped_items = {}
        
        # Dynamically discover equipment slots by checking attributes ending with '_slot'
        for attr in dir(character_data):
            if attr.endswith('_slot') and not attr.startswith('_'):
                item_code = getattr(character_data, attr, '')
                if item_code:
                    equipped_items[attr] = item_code
                
        self.logger.debug(f"Extracted equipped items: {equipped_items}")
        return equipped_items
    
    def _extract_equipped_items_from_dict(self, char_data: Dict) -> Dict[str, str]:
        """Extract equipped items from character data dict"""
        equipped_items = {}
        
        # Dynamically discover equipment slots by looking for keys ending with '_slot'
        for key, value in char_data.items():
            if key.endswith('_slot') and value:
                equipped_items[key] = value
                
        self.logger.debug(f"Extracted equipped items from dict: {equipped_items}")
        return equipped_items

    def __repr__(self):
        return "EvaluateWeaponRecipesAction()"