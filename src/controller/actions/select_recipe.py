"""
Select Recipe Action

This action selects the optimal recipe for crafting based on current equipment analysis
and character status, setting the selected_item for subsequent crafting actions.
"""

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from .base import ActionBase, ActionResult

from src.lib.action_context import ActionContext

class SelectRecipeAction(ActionBase):
    """
    Action to select optimal recipe for equipment crafting.
    
    This action evaluates available recipes based on character level,
    current equipment status, and crafting capabilities to select
    the best item to craft next.
    """

    # GOAP parameters - consolidated state format
    conditions = {
        "equipment_status": {
            "upgrade_status": "analyzing",
            "has_target_slot": True
        }
    }
    reactions = {
        "equipment_status": {
            "upgrade_status": "ready",
            "has_selected_item": True
        }
    }
    weight = 2

    def __init__(self):
        """Initialize the recipe selection action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Select optimal recipe for current equipment needs."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        target_slot = context.get('target_slot', 'weapon')
        
        self._context = context
        
        try:
            # Get current character data
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
            
            character_data = character_response.data
            character_level = getattr(character_data, 'level', 1)
            
            # Select recipe based on target slot and character level
            selected_recipe = self._select_optimal_recipe(target_slot, character_level, character_data, client, context)
            
            if not selected_recipe:
                return self.create_error_result(f"No suitable recipe found for {target_slot}")
            
            # Create result with consolidated state updates
            result = self.create_success_result(
                equipment_status={
                    "upgrade_status": "ready",
                    "selected_item": selected_recipe['item_code'],
                    "target_slot": target_slot,
                    "recipe_selected": True
                },
                selected_recipe=selected_recipe,
                character_level=character_level,
                # Add top-level keys for template resolution
                selected_item=selected_recipe['item_code'],
                target_slot=target_slot
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Recipe selection failed: {str(e)}")
            return error_response

    def _select_optimal_recipe(self, target_slot: str, character_level: int, 
                              character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select the optimal recipe for the target slot and character level."""
        try:
            # First check if we have a skill passed from context (from select_optimal_slot)
            skill_name = context.get_parameter('target_craft_skill')
            
            if skill_name:
                self.logger.info(f"Using skill '{skill_name}' from context for slot '{target_slot}'")
            else:
                # Use knowledge base to determine which skill is needed for this slot
                knowledge_base = getattr(context, 'knowledge_base', None)
                if not knowledge_base:
                    self.logger.error("No knowledge base available for recipe selection")
                    return None
                    
                # Find which crafting skill is appropriate for this slot
                skill_name = self._determine_crafting_skill_for_slot(target_slot, knowledge_base)
                if not skill_name:
                    self.logger.error(f"Could not determine crafting skill for slot '{target_slot}'")
                    return None
                
            return self._select_recipe_by_skill(skill_name, target_slot, character_level, character_data, client, context)
                
        except Exception as e:
            self.logger.warning(f"Recipe selection failed: {e}")
            return None

    def _select_weapon_recipe(self, character_level: int, character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal weapon recipe for character level."""
        return self._select_optimal_recipe('weapon', character_level, character_data, client, context)

    def _select_armor_recipe(self, target_slot: str, character_level: int, 
                           character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal armor recipe for target slot and character level."""
        return self._select_optimal_recipe(target_slot, character_level, character_data, client, context)

    def _select_accessory_recipe(self, target_slot: str, character_level: int,
                               character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal accessory recipe for target slot and character level."""
        return self._select_optimal_recipe(target_slot, character_level, character_data, client, context)

    def _determine_crafting_skill_for_slot(self, target_slot: str, knowledge_base) -> Optional[str]:
        """
        Determine which crafting skill is needed for a given equipment slot.
        
        This examines items in the knowledge base to find what skill crafts items for this slot.
        """
        try:
            items_data = knowledge_base.data.get('items', {})
            if not items_data:
                return None
                
            # Track which skills can craft items for this slot
            skill_counts = {}
            
            for item_code, item_data in items_data.items():
                if not isinstance(item_data, dict):
                    continue
                    
                # Check if item fits the target slot
                if not self._item_matches_slot(item_data, target_slot):
                    continue
                    
                # Check if it has crafting information
                craft_info = item_data.get('craft')
                if craft_info and isinstance(craft_info, dict):
                    skill = craft_info.get('skill')
                    if skill:
                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
                        
            if not skill_counts:
                self.logger.warning(f"No crafting skills found for slot '{target_slot}'")
                return None
                
            # Return the most common skill for this slot
            most_common_skill = max(skill_counts.items(), key=lambda x: x[1])[0]
            self.logger.debug(f"Slot '{target_slot}' is primarily crafted with '{most_common_skill}' ({skill_counts[most_common_skill]} items)")
            
            return most_common_skill
            
        except Exception as e:
            self.logger.error(f"Error determining crafting skill for slot '{target_slot}': {e}")
            return None

    def _select_recipe_by_skill(self, skill_name: str, target_slot: str, character_level: int, 
                                  character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Select optimal recipe for a given crafting skill and target slot.
        
        Args:
            skill_name: Name of the crafting skill (e.g., 'weaponcrafting', 'gearcrafting', 'jewelrycrafting')
            target_slot: Target equipment slot or item type
            character_level: Character's current level
            character_data: Character data from API
            client: API client
            context: Action context
            
        Returns:
            Recipe information dictionary or None if no suitable recipe found
        """
        try:
            # Use knowledge base to find available recipes
            knowledge_base = getattr(context, 'knowledge_base', None)
            if not knowledge_base:
                self.logger.error("No knowledge base available for recipe selection")
                return None
            
            # Get character's skill level for the specified craft
            skill_level_attr = f"{skill_name}_level"
            character_skill_level = getattr(character_data, skill_level_attr, 1)
            
            self.logger.info(f"Searching for {target_slot} recipes for level {character_level} character ({skill_name} skill: {character_skill_level})")
            
            # Get all items from knowledge base
            items_data = knowledge_base.data.get('items', {})
            if not items_data:
                self.logger.error("No items data in knowledge base")
                return None
            
            # Find all craftable items for this skill and slot
            craftable_items = []
            for item_code, item_data in items_data.items():
                if not isinstance(item_data, dict):
                    continue
                    
                # Check if item fits the target slot/type
                if not self._item_matches_slot(item_data, target_slot):
                    continue
                    
                # Check if it has crafting information
                craft_info = item_data.get('craft')
                if not craft_info or not isinstance(craft_info, dict):
                    continue
                    
                # Check skill requirements
                required_skill = craft_info.get('skill')
                required_level = craft_info.get('level', 1)
                
                if required_skill != skill_name:
                    continue
                    
                if required_level > character_skill_level:
                    self.logger.debug(f"Skipping {item_code}: requires {skill_name} {required_level}, have {character_skill_level}")
                    continue
                    
                # Skill level can never exceed character level - additional constraint
                if required_level > character_level:
                    self.logger.debug(f"Skipping {item_code}: requires {skill_name} {required_level}, but character is only level {character_level}")
                    continue
                    
                # Check skill level appropriateness for progression
                item_level = item_data.get('level', 1)
                skill_level_diff = abs(required_level - character_skill_level)
                
                # Prioritize items that match current skill level for optimal progression
                # Allow items that are within 1 level of current skill level for progression
                max_skill_diff = 1
                if skill_level_diff > max_skill_diff:
                    self.logger.debug(f"Skipping {item_code}: requires {skill_name} {required_level}, too far from current {character_skill_level}")
                    continue
                    
                # Calculate item score based on effects
                item_score = self._calculate_item_score(item_data, target_slot)
                            
                craftable_items.append({
                    'item_code': item_code,
                    'item_level': item_level,
                    'required_skill_level': required_level,
                    'skill_level_diff': skill_level_diff,
                    'item_score': item_score,
                    'craft_info': craft_info,
                    'item_data': item_data
                })
                
            if not craftable_items:
                self.logger.warning(f"No craftable {target_slot} items found for level {character_level} with {skill_name} {character_skill_level}")
                return None
                
            # Sort by skill progression priority:
            # 1. Prioritize items that exactly match current skill level (skill_level_diff = 0)
            # 2. Then by item score (higher is better) for tiebreakers
            # 3. Then by required skill level (higher is better) to prefer progression items
            # This ensures optimal skill progression: craft at your current skill level
            def skill_progression_key(item):
                skill_diff = item['skill_level_diff']
                item_score = item['item_score']
                required_level = item['required_skill_level']
                
                # Prioritize exact skill level matches (skill_diff = 0)
                # Then prioritize higher-tier items for progression
                return (skill_diff, -item_score, -required_level)
            
            craftable_items.sort(key=skill_progression_key)
            
            # Log top candidates for debugging
            self.logger.debug(f"Top {min(3, len(craftable_items))} candidates (current {skill_name}: {character_skill_level}):")
            for i, item in enumerate(craftable_items[:3]):
                self.logger.debug(f"  {i+1}. {item['item_code']} (requires {skill_name} {item['required_skill_level']}, item level {item['item_level']}, score: {item['item_score']})")
            
            # Select the best item
            best_item = craftable_items[0]
            self.logger.info(f"Selected {target_slot} recipe: {best_item['item_code']} (requires {skill_name} {best_item['required_skill_level']}, item level {best_item['item_level']}, current skill: {character_skill_level})")
            
            return {
                'item_code': best_item['item_code'],
                'item_level': best_item['item_level'],
                'required_skill_level': best_item['required_skill_level'],
                'craft_info': best_item['craft_info'],
                'materials': self._extract_materials(best_item['craft_info'])
            }
            
        except Exception as e:
            self.logger.error(f"{skill_name} recipe selection failed: {e}")
            return None
            
    def _item_matches_slot(self, item_data: Dict, target_slot: str) -> bool:
        """
        Check if an item matches the target slot or type.
        
        Uses dynamic matching based on item data rather than hardcoded rules.
        Special handling for items with 'unknown' type that need to be classified by their name or craft info.
        """
        item_type = item_data.get('type', '').lower()
        item_subtype = item_data.get('subtype', '').lower()
        target_lower = target_slot.lower()
        item_code = item_data.get('code', '').lower()
        
        # Direct type match
        if item_type == target_lower:
            return True
            
        # Check if target slot appears in type or subtype
        if target_lower in item_type or target_lower in item_subtype:
            return True
            
        # Check if item type appears in target slot
        if item_type and item_type in target_lower:
            return True
            
        # For compound slot names (e.g., body_armor), check word overlap
        target_words = set(target_lower.replace('_', ' ').split())
        type_words = set(item_type.replace('_', ' ').split())
        subtype_words = set(item_subtype.replace('_', ' ').split())
        
        # If there's significant word overlap, consider it a match
        if target_words.intersection(type_words) or target_words.intersection(subtype_words):
            return True
            
        # Check if item has slot information in its data
        item_slot = item_data.get('slot', '').lower()
        if item_slot and (item_slot == target_lower or target_lower in item_slot or item_slot in target_lower):
            return True
            
        # For ring slots (ring1, ring2), both should accept 'ring' type items
        if target_lower.startswith('ring') and item_type == 'ring':
            return True
        
        # Special handling for items with 'unknown' type - classify by item name patterns
        if item_type == 'unknown' and target_lower == 'weapon':
            # Check if item name contains weapon-like keywords
            weapon_keywords = [
                'sword', 'dagger', 'axe', 'staff', 'bow', 'spear', 'hammer', 'mace',
                'blade', 'knife', 'wand', 'rod', 'club', 'pick', 'pickaxe'
            ]
            
            # Check item code/name for weapon keywords
            for keyword in weapon_keywords:
                if keyword in item_code:
                    self.logger.debug(f"Item {item_code} matches weapon slot by name pattern: {keyword}")
                    return True
        
        # Additional pattern matching for other equipment types
        if item_type == 'unknown':
            if target_lower == 'armor' or target_lower == 'body_armor':
                armor_keywords = ['armor', 'vest', 'shirt', 'tunic', 'robe', 'plate', 'mail']
                for keyword in armor_keywords:
                    if keyword in item_code:
                        self.logger.debug(f"Item {item_code} matches armor slot by name pattern: {keyword}")
                        return True
                        
            elif target_lower == 'helmet':
                helmet_keywords = ['helmet', 'hat', 'cap', 'crown', 'hood', 'mask']
                for keyword in helmet_keywords:
                    if keyword in item_code:
                        self.logger.debug(f"Item {item_code} matches helmet slot by name pattern: {keyword}")
                        return True
                        
            elif target_lower == 'boots':
                boots_keywords = ['boots', 'shoes', 'sandals', 'slippers']
                for keyword in boots_keywords:
                    if keyword in item_code:
                        self.logger.debug(f"Item {item_code} matches boots slot by name pattern: {keyword}")
                        return True
                        
            elif target_lower.startswith('ring'):
                ring_keywords = ['ring']
                for keyword in ring_keywords:
                    if keyword in item_code:
                        self.logger.debug(f"Item {item_code} matches ring slot by name pattern: {keyword}")
                        return True
                        
            elif target_lower == 'amulet':
                amulet_keywords = ['amulet', 'necklace', 'pendant']
                for keyword in amulet_keywords:
                    if keyword in item_code:
                        self.logger.debug(f"Item {item_code} matches amulet slot by name pattern: {keyword}")
                        return True
            
        return False
        
    def _calculate_item_score(self, item_data: Dict, target_slot: str) -> float:
        """
        Calculate a score for an item based on its effects.
        
        Dynamically determines appropriate weights based on item type rather than hardcoded slot names.
        """
        score = 0.0
        effects = item_data.get('effects', [])
        item_type = item_data.get('type', '').lower()
        
        # Determine effect weights based on item type
        if item_type == 'weapon':
            # For weapons, prioritize offensive stats
            primary_stats = ['attack', 'dmg', 'critical_strike']
            secondary_stats = ['haste', 'wisdom']
            tertiary_stats = ['hp', 'res']
        elif item_type in ['armor', 'shield']:
            # For defensive items, prioritize defensive stats
            primary_stats = ['armor', 'res', 'hp']
            secondary_stats = ['dmg', 'attack']
            tertiary_stats = ['haste', 'critical_strike']
        else:
            # For other items (accessories, etc.), balanced approach
            primary_stats = ['hp', 'dmg', 'attack']
            secondary_stats = ['res', 'armor', 'haste', 'critical_strike']
            tertiary_stats = ['wisdom']
            
        # Calculate score based on effects
        for effect in effects:
            if isinstance(effect, dict):
                name = effect.get('name', '').lower()
                value = effect.get('value', 0)
                
                # Determine weight based on stat category
                weight = 0.5  # Default weight
                
                # Check if effect name contains any primary stat keywords
                if any(stat in name for stat in primary_stats):
                    weight = 2.0
                elif any(stat in name for stat in secondary_stats):
                    weight = 1.5
                elif any(stat in name for stat in tertiary_stats):
                    weight = 1.0
                    
                score += value * weight
                    
        return score

    def _extract_materials(self, craft_info: Dict) -> List[str]:
        """Extract material codes from craft information."""
        materials = []
        
        if not craft_info or not isinstance(craft_info, dict):
            return materials
            
        items = craft_info.get('items', [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and 'code' in item:
                    materials.append(item['code'])
                    
        return materials

    def __repr__(self):
        return "SelectRecipeAction()"