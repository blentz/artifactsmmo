"""
Select Optimal Slot Action

This action selects the optimal equipment slot for crafting based on:
- Equipment gap analysis from AnalyzeEquipmentGapsAction
- Target crafting skill from goal parameters
- Slot priority weights from configuration
"""

from typing import Dict, List

from src.controller.actions.base import ActionBase, ActionResult
from src.game.globals import CONFIG_PREFIX
from src.lib.action_context import ActionContext
from src.lib.yaml_data import YamlData


class SelectOptimalSlotAction(ActionBase):
    """
    Action to select the optimal equipment slot for crafting skill XP.
    
    This action combines equipment gap analysis with slot priority weights
    and crafting skill constraints to select the best slot for crafting.
    """
    
    # GOAP parameters
    conditions = {
            'equipment_status': {
                'gaps_analyzed': True,
                'has_target_slot': False
            },
            'character_status': {
                'alive': True,
            },
        }
    
    reactions = {
        'equipment_status': {
            'has_target_slot': True
        }
    }
    
    weight = 1.5
    
    def __init__(self):
        """Initialize the slot selection action."""
        super().__init__()
        self.config = None
        
    def _load_equipment_config(self) -> YamlData:
        """Load equipment analysis configuration from YAML."""
        if self.config is None:
            try:
                self.config = YamlData(f"{CONFIG_PREFIX}/equipment_analysis.yaml")
                self.logger.debug("Loaded equipment analysis configuration for slot selection")
            except Exception as e:
                self.logger.error(f"Failed to load equipment analysis config: {e}")
                # Provide fallback configuration
                self.config = self._get_fallback_config()
        return self.config
        
    def _get_fallback_config(self) -> YamlData:
        """Provide minimal fallback configuration if YAML loading fails."""
        # Only provide empty structure - actual mappings should come from config files
        fallback_data = {
            'skill_slot_mappings': {},
            'slot_priorities': {}
        }
        config = YamlData.__new__(YamlData)
        config.data = fallback_data
        self.logger.error("Using empty fallback config - equipment_analysis.yaml should be configured")
        return config
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute slot selection based on equipment gaps and target skill.
        
        Args:
            client: API client (not used for this selection)
            context: ActionContext containing gap analysis and target skill
            
        Returns:
            Action result with selected slot information
        """
        self._context = context
        
        # Get required data from context
        gap_analysis = context.get_parameter('equipment_gap_analysis')
        target_skill = context.get_parameter('target_craft_skill')
        
        # If no target skill specified, determine from character equipment priorities
        if not target_skill:
            try:
                target_skill = self._determine_default_craft_skill(context, gap_analysis)
                if not target_skill:
                    self.logger.error("_determine_default_craft_skill returned None despite fallbacks - using weaponcrafting")
                    target_skill = 'weaponcrafting'
                self.logger.info(f"🎯 No target_craft_skill specified, defaulting to {target_skill} based on equipment priorities")
            except Exception as e:
                self.logger.error(f"Exception in _determine_default_craft_skill: {e}")
                target_skill = 'weaponcrafting'
                self.logger.info(f"🎯 Exception occurred, defaulting to {target_skill}")
            
        if not gap_analysis:
            return self.create_error_result("Equipment gap analysis not available - run AnalyzeEquipmentGapsAction first")
            
        config = self._load_equipment_config()
        
        # Get applicable slots for the target crafting skill
        applicable_slots = config.data.get('skill_slot_mappings', {}).get(target_skill, [])
        
        if not applicable_slots:
            return self.create_error_result(f"No equipment slots mapped for skill '{target_skill}'")
            
        self.logger.info(f"🎯 Selecting optimal slot for {target_skill} from {len(applicable_slots)} options")
        
        # Filter applicable slots to only include those present in gap analysis
        available_slots = [slot for slot in applicable_slots if slot in gap_analysis]
        
        if not available_slots:
            # If we have no overlap between skill slots and gap analysis, try to find a skill that does
            available_gap_slots = list(gap_analysis.keys())
            skill_mappings = config.data.get('skill_slot_mappings', {})
            
            for skill, slots in skill_mappings.items():
                if any(slot in available_gap_slots for slot in slots):
                    self.logger.info(f"🔄 No available slots for {target_skill}, switching to {skill} which has available slots")
                    target_skill = skill
                    applicable_slots = slots
                    available_slots = [slot for slot in slots if slot in gap_analysis]
                    break
            
            if not available_slots:
                self.logger.warning(f"No applicable slots for {target_skill} found in gap analysis. "
                                   f"Applicable: {applicable_slots}, Available: {list(gap_analysis.keys())}")
                return self.create_error_result(f"No valid slots found for skill {target_skill}")
        
        self.logger.debug(f"Filtered to {len(available_slots)} available slots: {available_slots}")
        
        # Calculate combined scores for each available slot
        slot_scores = []
        for slot in available_slots:
            score_data = self._calculate_slot_score(slot, gap_analysis, config)
            if score_data:
                slot_scores.append(score_data)
                self.logger.debug(f"  {slot}: combined score {score_data['combined_score']:.2f} "
                                f"(gap: {score_data['gap_score']:.1f}, priority: {score_data['priority_weight']})")
        
        # Select the highest scoring slot
        if not slot_scores:
            return self.create_error_result(f"No valid slots found for skill {target_skill}")
            
        # Sort by combined score (highest first)
        slot_scores.sort(key=lambda x: x['combined_score'], reverse=True)
        best_slot_data = slot_scores[0]
        
        # Store results in context for next action
        context.set_result('target_equipment_slot', best_slot_data['slot_name'])
        context.set_result('target_craft_skill', target_skill)  # Pass the skill forward
        context.set_result('slot_selection_reasoning', {
            'selected_slot': best_slot_data['slot_name'],
            'target_skill': target_skill,
            'combined_score': best_slot_data['combined_score'],
            'gap_score': best_slot_data['gap_score'],
            'priority_weight': best_slot_data['priority_weight'],
            'urgency_reason': best_slot_data['urgency_reason'],
            'alternatives': [
                {
                    'slot': data['slot_name'],
                    'score': data['combined_score'],
                    'reason': data['urgency_reason']
                }
                for data in slot_scores[1:4]  # Top 3 alternatives
            ]
        })
        
        # Context results are already set above via 'target_equipment_slot'
        
        self.logger.info(f"✅ Selected '{best_slot_data['slot_name']}' for {target_skill} crafting "
                        f"(score: {best_slot_data['combined_score']:.2f}, reason: {best_slot_data['urgency_reason']})")
        
        return self.create_success_result(
            f"Selected slot '{best_slot_data['slot_name']}' for {target_skill} crafting",
            selected_slot=best_slot_data['slot_name'],
            target_skill=target_skill,
            combined_score=best_slot_data['combined_score'],
            gap_score=best_slot_data['gap_score'],
            priority_weight=best_slot_data['priority_weight'],
            alternatives_considered=len(slot_scores)
        )
        
    def _calculate_slot_score(self, slot_name: str, gap_analysis: Dict, 
                             config: YamlData) -> Dict:
        """
        Calculate combined score for a slot based on gap urgency and priority.
        
        Args:
            slot_name: Name of the equipment slot
            gap_analysis: Equipment gap analysis data
            config: Equipment analysis configuration
            
        Returns:
            Dictionary with slot scoring data, or None if slot not in analysis
        """
        if slot_name not in gap_analysis:
            self.logger.warning(f"Slot '{slot_name}' not found in gap analysis")
            return None
            
        slot_gap_data = gap_analysis[slot_name]
        gap_score = slot_gap_data.get('urgency_score', 0)
        urgency_reason = slot_gap_data.get('reason', 'unknown')
        
        # Get priority weight from configuration
        slot_priorities = config.data.get('slot_priorities', {})
        priority_weight = slot_priorities.get(slot_name, 50)  # Default weight of 50
        
        # Calculate combined score
        # Formula: gap_urgency * (priority_weight / 100)
        # This gives higher priority to urgent gaps in high-priority slots
        combined_score = gap_score * (priority_weight / 100)
        
        return {
            'slot_name': slot_name,
            'combined_score': combined_score,
            'gap_score': gap_score,
            'priority_weight': priority_weight,
            'urgency_reason': urgency_reason,
            'missing_equipment': slot_gap_data.get('missing', False),
            'level_difference': slot_gap_data.get('level_difference', 0)
        }
        
    def get_slot_selection_summary(self, context: ActionContext) -> Dict:
        """
        Get a summary of the slot selection process for debugging.
        
        Args:
            context: ActionContext containing selection results
            
        Returns:
            Summary dictionary with selection details
        """
        reasoning = context.get_parameter('slot_selection_reasoning', {})
        
        return {
            'selected_slot': reasoning.get('selected_slot'),
            'target_skill': reasoning.get('target_skill'),
            'selection_score': reasoning.get('combined_score'),
            'selection_reason': reasoning.get('urgency_reason'),
            'alternatives': reasoning.get('alternatives', [])
        }
    
    def _determine_default_craft_skill(self, context: ActionContext, gap_analysis: Dict) -> str:
        """
        Determine the default crafting skill based on craftable items for equipment slots.
        
        Uses knowledge base to find what items can be crafted for slots with gaps,
        then determines what skills are needed to craft those items.
        
        Args:
            context: ActionContext with character information and knowledge base
            gap_analysis: Equipment gap analysis data
            
        Returns:
            Default crafting skill name, always returns a valid skill (never None)
        """
        try:
            self.logger.debug(f"Determining default craft skill. Gap analysis: {bool(gap_analysis)}, slots: {list(gap_analysis.keys()) if gap_analysis else 'None'}")
            
            if not gap_analysis:
                self.logger.warning("No gap analysis provided, defaulting to weaponcrafting")
                return 'weaponcrafting'
                
            knowledge_base = context.knowledge_base
            if not knowledge_base:
                self.logger.warning("No knowledge base available for determining craft skill")
                return 'weaponcrafting'  # Safe fallback
                
            # Find the slot with the highest urgency score
            best_slot = None
            highest_urgency = 0
            
            for slot, gap_data in gap_analysis.items():
                urgency_score = gap_data.get('urgency_score', 0)
                if urgency_score > highest_urgency:
                    highest_urgency = urgency_score
                    best_slot = slot
                    
            if not best_slot:
                self.logger.warning("No equipment gaps found, defaulting to weaponcrafting")
                return 'weaponcrafting'
                
            self.logger.debug(f"Determining craft skill for slot '{best_slot}' with urgency {highest_urgency}")
            
            # Get craftable items that can be equipped in this slot
            craft_skills = self._get_craft_skills_for_slot(knowledge_base, best_slot)
            
            if not craft_skills:
                self.logger.warning(f"No craft skills found for slot '{best_slot}', defaulting to weaponcrafting")
                return 'weaponcrafting'
                
            if len(craft_skills) == 1:
                selected_skill = craft_skills[0]
                self.logger.info(f"Selected craft skill '{selected_skill}' for slot '{best_slot}'")
                return selected_skill
            else:
                # Multiple skills possible, select randomly from the list
                import random
                selected_skill = random.choice(craft_skills)
                self.logger.info(f"Multiple craft skills {craft_skills} found for slot '{best_slot}', randomly selected '{selected_skill}'")
                return selected_skill
                
        except Exception as e:
            self.logger.error(f"Error determining default craft skill: {e}")
            self.logger.error(f"Gap analysis type: {type(gap_analysis)}, Knowledge base type: {type(getattr(context, 'knowledge_base', None))}")
            return 'weaponcrafting'  # Safe fallback in case of any errors
    
    def _get_craft_skills_for_slot(self, knowledge_base, slot_name: str) -> List[str]:
        """
        Get list of crafting skills needed to craft items for a specific equipment slot.
        
        Args:
            knowledge_base: KnowledgeBase instance with item data
            slot_name: Equipment slot name (e.g., 'weapon', 'helmet')
            
        Returns:
            List of crafting skill names that can create items for this slot
        """
        craft_skills = set()
        
        try:
            # Get all items from knowledge base
            items_data = knowledge_base.data.get('items', {})
            
            if not items_data:
                self.logger.debug("No items data in knowledge base")
                return []
                
            # Look through all items to find ones that can be equipped in this slot
            for item_code, item_data in items_data.items():
                if not isinstance(item_data, dict):
                    continue
                    
                # Check if this item can be equipped in the target slot
                if self._item_fits_slot(item_data, slot_name):
                    # Check if this item has crafting information
                    craft_info = item_data.get('craft')
                    if craft_info and isinstance(craft_info, dict):
                        skill = craft_info.get('skill')
                        if skill:
                            craft_skills.add(skill)
                            self.logger.debug(f"Item '{item_code}' for slot '{slot_name}' requires skill '{skill}'")
                            
        except Exception as e:
            self.logger.warning(f"Error querying knowledge base for slot '{slot_name}': {e}")
            
        return list(craft_skills)
    
    def _item_fits_slot(self, item_data: Dict, slot_name: str) -> bool:
        """
        Check if an item can be equipped in a specific slot using knowledge base data.
        
        Examines item type, subtype, and effects to determine if it fits the slot.
        Uses string matching to avoid hardcoded mappings.
        
        Args:
            item_data: Item data dictionary from knowledge base
            slot_name: Equipment slot name
            
        Returns:
            True if the item fits the slot, False otherwise
        """
        # Get basic item information
        item_type = item_data.get('type', '').lower()
        item_subtype = item_data.get('subtype', '').lower()
        
        # Check if slot name appears in item type or subtype
        slot_lower = slot_name.lower()
        
        if slot_lower in item_type or slot_lower in item_subtype:
            self.logger.debug(f"Slot '{slot_name}' matches item type/subtype: {item_type}/{item_subtype}")
            return True
            
        # Check reverse - if item type appears in slot name
        if item_type and item_type in slot_lower:
            self.logger.debug(f"Item type '{item_type}' appears in slot name '{slot_name}'")
            return True
            
        if item_subtype and item_subtype in slot_lower:
            self.logger.debug(f"Item subtype '{item_subtype}' appears in slot name '{slot_name}'")
            return True
            
        # Check effects for slot indicators
        effects = item_data.get('effects', [])
        
        # For weapon slot, check if item name suggests it's a weapon
        if slot_lower == 'weapon':
            item_code = item_data.get('code', '').lower()
            # Check for weapon-related keywords in item code
            weapon_keywords = ['sword', 'bow', 'staff', 'axe', 'dagger', 'mace', 'spear', 'hammer', 'club', 'stick']
            if any(keyword in item_code for keyword in weapon_keywords):
                self.logger.debug(f"Item code '{item_code}' contains weapon keyword, matches weapon slot")
                return True
            
            # Also check for items that are explicitly NOT weapons (rings, armor, etc)
            non_weapon_keywords = ['ring', 'amulet', 'helmet', 'armor', 'boots', 'shield', 'gloves', 'legs']
            if any(keyword in item_code for keyword in non_weapon_keywords):
                return False
                
            # If no clear indication from name, check if it has primarily attack effects
            # but exclude items with many non-weapon effects
            attack_effects = ['attack_earth', 'attack_fire', 'attack_water', 'attack_air']
            has_attack = False
            non_weapon_effect_count = 0
            
            for effect in effects:
                if not isinstance(effect, dict):
                    continue
                effect_code = effect.get('code', '').lower()
                if effect_code in attack_effects:
                    has_attack = True
                # Count effects that suggest non-weapon items
                elif effect_code in ['haste', 'wisdom', 'prospecting', 'critical_strike']:
                    non_weapon_effect_count += 1
                    
            # Only consider it a weapon if it has attack effects and not too many non-weapon effects
            if has_attack and non_weapon_effect_count < 2:
                self.logger.debug(f"Item has weapon effects without many accessory effects, matches weapon slot")
                return True
        
        for effect in effects:
            if not isinstance(effect, dict):
                continue
                
            effect_name = effect.get('name', '').lower()
            
            # Check if slot name appears in effect name
            if slot_lower in effect_name:
                self.logger.debug(f"Slot '{slot_name}' found in effect name '{effect_name}'")
                return True
                
        # Special case handling for common patterns we can derive from the data
        return self._check_derived_slot_patterns(item_type, item_subtype, slot_name, item_data)
    
    def _check_derived_slot_patterns(self, item_type: str, item_subtype: str, slot_name: str, item_data: Dict) -> bool:
        """
        Check for slot patterns that can be derived without hardcoding.
        
        This handles cases where the relationship between item and slot
        isn't directly obvious from string matching.
        
        Args:
            item_type: Item type from knowledge base
            item_subtype: Item subtype from knowledge base  
            slot_name: Equipment slot name
            item_data: Complete item data dictionary
            
        Returns:
            True if patterns suggest the item fits the slot, False otherwise
        """
        # Handle ring slots - both ring1 and ring2 can accept ring items
        if item_type == 'ring' and slot_name.startswith('ring'):
            self.logger.debug(f"Ring item type matches ring slot '{slot_name}'")
            return True
            
        # Handle armor subtypes - if item_subtype contains armor-related words
        # and slot_name contains armor-related words, they might match
        armor_indicators = ['armor', 'helmet', 'boots', 'chest', 'leg']
        if (any(indicator in item_type for indicator in armor_indicators) and
            any(indicator in slot_name for indicator in armor_indicators)):
            # Check if both contain similar armor-type words
            type_words = set(item_type.replace('_', ' ').split())
            subtype_words = set(item_subtype.replace('_', ' ').split())
            slot_words = set(slot_name.replace('_', ' ').split())
            
            # If there's any overlap in words, consider it a match
            if type_words.intersection(slot_words) or subtype_words.intersection(slot_words):
                self.logger.debug(f"Armor-related word overlap: type={item_type}, subtype={item_subtype}, slot={slot_name}")
                return True
                
        return False