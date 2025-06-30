"""
Analyze Equipment Action

This action performs comprehensive equipment analysis for the character,
determining upgrade needs and equipment priorities for GOAP planning.
"""

from typing import Dict, Optional, List
import logging
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from .base import ActionBase


class AnalyzeEquipmentAction(ActionBase):
    """
    Action to analyze character equipment and determine upgrade needs.
    
    This action consolidates all equipment analysis functionality that was
    previously scattered across StateEngine methods, providing a comprehensive
    equipment analysis that integrates with the GOAP planning system.
    """

    # GOAP parameters
    conditions = {"character_alive": True}
    reactions = {
        "equipment_analysis_available": True,
        "need_equipment": True,
        "has_better_weapon": True,
        "has_better_armor": True,
        "has_complete_equipment_set": True,
        "equipment_info_known": True
    }
    weights = {"equipment_analysis_available": 15}

    def __init__(self, character_name: str, analysis_type: str = "comprehensive"):
        """
        Initialize the equipment analysis action.

        Args:
            character_name: Name of the character to analyze
            analysis_type: Type of analysis (comprehensive, weapon, armor, complete_set)
        """
        super().__init__()
        self.character_name = character_name
        self.analysis_type = analysis_type
        self.logger = logging.getLogger(__name__)

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """Perform comprehensive equipment analysis."""
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_name=self.character_name,
            analysis_type=self.analysis_type
        )
        
        try:
            # Get current character data
            character_response = get_character_api(name=self.character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            
            # Perform comprehensive equipment analysis
            analysis_results = self._analyze_equipment(character_data, client, **kwargs)
            
            # Determine equipment needs and priorities
            equipment_needs = self._determine_equipment_needs(analysis_results, character_data)
            
            # Create result with GOAP state updates
            result = self.get_success_response(
                equipment_analysis_available=True,
                equipment_info_known=True,
                analysis_type=self.analysis_type,
                character_level=getattr(character_data, 'level', 1),
                **equipment_needs,
                **analysis_results
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Equipment analysis failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _analyze_equipment(self, character_data, client, **kwargs) -> Dict:
        """Perform detailed equipment analysis."""
        try:
            # Extract current equipment
            current_equipment = self._extract_current_equipment(character_data)
            
            # Analyze each equipment category
            weapon_analysis = self._analyze_weapon_equipment(current_equipment, character_data, client)
            armor_analysis = self._analyze_armor_equipment(current_equipment, character_data, client)
            accessory_analysis = self._analyze_accessory_equipment(current_equipment, character_data)
            
            # Calculate overall equipment coverage
            equipment_coverage = self._calculate_equipment_coverage(current_equipment)
            
            # Determine upgrade priorities
            upgrade_priorities = self._determine_upgrade_priorities(
                weapon_analysis, armor_analysis, accessory_analysis, character_data
            )
            
            return {
                'current_equipment': current_equipment,
                'weapon_analysis': weapon_analysis,
                'armor_analysis': armor_analysis,
                'accessory_analysis': accessory_analysis,
                'equipment_coverage': equipment_coverage,
                'upgrade_priorities': upgrade_priorities
            }
            
        except Exception as e:
            self.logger.warning(f"Equipment analysis failed: {e}")
            return {}

    def _extract_current_equipment(self, character_data) -> Dict:
        """Extract current equipment from character data."""
        equipment_slots = [
            'weapon_slot', 'shield_slot', 'helmet_slot', 'body_armor_slot',
            'leg_armor_slot', 'boots_slot', 'ring1_slot', 'ring2_slot',
            'amulet_slot', 'artifact1_slot', 'artifact2_slot', 'artifact3_slot'
        ]
        
        current_equipment = {}
        for slot in equipment_slots:
            item_code = getattr(character_data, slot, '')
            current_equipment[slot] = item_code if item_code else None
            
        return current_equipment

    def _analyze_weapon_equipment(self, current_equipment: Dict, character_data, client) -> Dict:
        """Analyze weapon equipment and upgrade needs."""
        try:
            weapon_code = current_equipment.get('weapon_slot')
            character_level = getattr(character_data, 'level', 1)
            
            analysis = {
                'current_weapon': weapon_code,
                'weapon_equipped': weapon_code is not None and weapon_code != '',
                'is_starter_weapon': weapon_code in ['wooden_stick', '', None],
                'needs_upgrade': False,
                'upgrade_priority': 'low',
                'weapon_tier': 'starter'
            }
            
            # Determine if weapon upgrade is needed
            if analysis['is_starter_weapon'] and character_level >= 2:
                analysis['needs_upgrade'] = True
                analysis['upgrade_priority'] = 'high'
                analysis['recommended_action'] = 'Get basic weapon (copper dagger or wooden staff)'
            elif weapon_code and character_level >= 5:
                # For higher levels, check if weapon is appropriate for level
                analysis['needs_upgrade'] = True
                analysis['upgrade_priority'] = 'medium'
                analysis['recommended_action'] = f'Consider upgrading from {weapon_code}'
                
            # Try to get weapon details from API if equipped
            if weapon_code and weapon_code != 'wooden_stick':
                try:
                    weapon_response = get_item_api(code=weapon_code, client=client)
                    if weapon_response and weapon_response.data:
                        weapon_data = weapon_response.data
                        analysis['weapon_level'] = getattr(weapon_data, 'level', 1)
                        analysis['weapon_type'] = getattr(weapon_data, 'type', 'unknown')
                        analysis['weapon_tier'] = self._determine_item_tier(weapon_data)
                except Exception as e:
                    self.logger.debug(f"Could not get weapon details for {weapon_code}: {e}")
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Weapon analysis failed: {e}")
            return {'needs_upgrade': True, 'upgrade_priority': 'high'}

    def _analyze_armor_equipment(self, current_equipment: Dict, character_data, client) -> Dict:
        """Analyze armor equipment and upgrade needs."""
        try:
            armor_slots = ['helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
            character_level = getattr(character_data, 'level', 1)
            
            equipped_armor_count = 0
            armor_items = {}
            
            for slot in armor_slots:
                item_code = current_equipment.get(slot)
                if item_code:
                    equipped_armor_count += 1
                    armor_items[slot] = item_code
            
            armor_coverage = equipped_armor_count / len(armor_slots)
            
            analysis = {
                'equipped_armor_count': equipped_armor_count,
                'total_armor_slots': len(armor_slots),
                'armor_coverage': armor_coverage,
                'armor_items': armor_items,
                'needs_upgrade': False,
                'upgrade_priority': 'low'
            }
            
            # Determine armor upgrade needs
            if character_level >= 2 and equipped_armor_count < 2:
                analysis['needs_upgrade'] = True
                analysis['upgrade_priority'] = 'high'
                analysis['recommended_action'] = 'Get basic armor pieces'
            elif character_level >= 4 and armor_coverage < 0.75:
                analysis['needs_upgrade'] = True
                analysis['upgrade_priority'] = 'medium'
                analysis['recommended_action'] = 'Complete armor set'
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Armor analysis failed: {e}")
            return {'needs_upgrade': True, 'upgrade_priority': 'medium'}

    def _analyze_accessory_equipment(self, current_equipment: Dict, character_data) -> Dict:
        """Analyze accessory equipment (rings, amulets, artifacts)."""
        try:
            accessory_slots = ['ring1_slot', 'ring2_slot', 'amulet_slot', 
                             'artifact1_slot', 'artifact2_slot', 'artifact3_slot']
            character_level = getattr(character_data, 'level', 1)
            
            equipped_accessories = 0
            accessory_items = {}
            
            for slot in accessory_slots:
                item_code = current_equipment.get(slot)
                if item_code:
                    equipped_accessories += 1
                    accessory_items[slot] = item_code
            
            accessory_coverage = equipped_accessories / len(accessory_slots)
            
            analysis = {
                'equipped_accessories_count': equipped_accessories,
                'total_accessory_slots': len(accessory_slots),
                'accessory_coverage': accessory_coverage,
                'accessory_items': accessory_items,
                'needs_upgrade': False,
                'upgrade_priority': 'low'
            }
            
            # Accessories are lower priority than weapons/armor
            if character_level >= 5 and equipped_accessories == 0:
                analysis['needs_upgrade'] = True
                analysis['upgrade_priority'] = 'low'
                analysis['recommended_action'] = 'Consider getting basic accessories'
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Accessory analysis failed: {e}")
            return {'needs_upgrade': False}

    def _calculate_equipment_coverage(self, current_equipment: Dict) -> Dict:
        """Calculate overall equipment coverage statistics."""
        try:
            # Define equipment categories
            essential_slots = ['weapon_slot', 'helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
            optional_slots = ['shield_slot', 'ring1_slot', 'ring2_slot', 'amulet_slot']
            artifact_slots = ['artifact1_slot', 'artifact2_slot', 'artifact3_slot']
            
            # Count equipped items
            essential_equipped = sum(1 for slot in essential_slots if current_equipment.get(slot))
            optional_equipped = sum(1 for slot in optional_slots if current_equipment.get(slot))
            artifact_equipped = sum(1 for slot in artifact_slots if current_equipment.get(slot))
            
            total_equipped = essential_equipped + optional_equipped + artifact_equipped
            total_slots = len(essential_slots) + len(optional_slots) + len(artifact_slots)
            
            return {
                'essential_coverage': essential_equipped / len(essential_slots),
                'optional_coverage': optional_equipped / len(optional_slots),
                'artifact_coverage': artifact_equipped / len(artifact_slots),
                'total_coverage': total_equipped / total_slots,
                'essential_equipped': essential_equipped,
                'total_equipped': total_equipped,
                'total_slots': total_slots
            }
            
        except Exception as e:
            self.logger.warning(f"Equipment coverage calculation failed: {e}")
            return {'total_coverage': 0, 'essential_coverage': 0}

    def _determine_upgrade_priorities(self, weapon_analysis: Dict, armor_analysis: Dict, 
                                    accessory_analysis: Dict, character_data) -> List[Dict]:
        """Determine equipment upgrade priorities."""
        try:
            priorities = []
            character_level = getattr(character_data, 'level', 1)
            
            # Weapon priority
            if weapon_analysis.get('needs_upgrade'):
                priority_level = weapon_analysis.get('upgrade_priority', 'medium')
                priorities.append({
                    'category': 'weapon',
                    'priority': priority_level,
                    'action': weapon_analysis.get('recommended_action', 'Upgrade weapon'),
                    'urgency_score': self._calculate_urgency_score('weapon', priority_level, character_level)
                })
            
            # Armor priority
            if armor_analysis.get('needs_upgrade'):
                priority_level = armor_analysis.get('upgrade_priority', 'medium')
                priorities.append({
                    'category': 'armor',
                    'priority': priority_level,
                    'action': armor_analysis.get('recommended_action', 'Upgrade armor'),
                    'urgency_score': self._calculate_urgency_score('armor', priority_level, character_level)
                })
            
            # Accessory priority
            if accessory_analysis.get('needs_upgrade'):
                priority_level = accessory_analysis.get('upgrade_priority', 'low')
                priorities.append({
                    'category': 'accessories',
                    'priority': priority_level,
                    'action': accessory_analysis.get('recommended_action', 'Get accessories'),
                    'urgency_score': self._calculate_urgency_score('accessories', priority_level, character_level)
                })
            
            # Sort by urgency score (highest first)
            priorities.sort(key=lambda x: x['urgency_score'], reverse=True)
            
            return priorities
            
        except Exception as e:
            self.logger.warning(f"Priority determination failed: {e}")
            return []

    def _calculate_urgency_score(self, category: str, priority: str, character_level: int) -> int:
        """Calculate urgency score for equipment upgrade."""
        # Base scores by priority
        priority_scores = {'high': 100, 'medium': 50, 'low': 20}
        base_score = priority_scores.get(priority, 20)
        
        # Category modifiers
        category_modifiers = {'weapon': 1.5, 'armor': 1.2, 'accessories': 0.8}
        modifier = category_modifiers.get(category, 1.0)
        
        # Level urgency (higher level = more urgent upgrades)
        level_bonus = min(character_level * 5, 50)
        
        return int((base_score * modifier) + level_bonus)

    def _determine_equipment_needs(self, analysis_results: Dict, character_data) -> Dict:
        """Determine GOAP state variables for equipment needs."""
        try:
            weapon_analysis = analysis_results.get('weapon_analysis', {})
            armor_analysis = analysis_results.get('armor_analysis', {})
            coverage = analysis_results.get('equipment_coverage', {})
            priorities = analysis_results.get('upgrade_priorities', [])
            
            # Determine GOAP state flags
            needs_equipment = any([
                weapon_analysis.get('needs_upgrade', False),
                armor_analysis.get('needs_upgrade', False),
                coverage.get('essential_coverage', 0) < 0.8
            ])
            
            has_better_weapon = not weapon_analysis.get('is_starter_weapon', True)
            has_better_armor = armor_analysis.get('equipped_armor_count', 0) >= 2
            has_complete_equipment_set = coverage.get('essential_coverage', 0) >= 0.8
            
            # Determine highest priority need
            highest_priority = None
            if priorities:
                highest_priority = priorities[0]['category']
            
            return {
                'need_equipment': needs_equipment,
                'has_better_weapon': has_better_weapon,
                'has_better_armor': has_better_armor,
                'has_complete_equipment_set': has_complete_equipment_set,
                'equipment_upgrade_priority': highest_priority,
                'equipment_coverage_percentage': int(coverage.get('total_coverage', 0) * 100),
                'equipment_needs_summary': self._create_needs_summary(priorities)
            }
            
        except Exception as e:
            self.logger.warning(f"Equipment needs determination failed: {e}")
            return {'need_equipment': True}

    def _create_needs_summary(self, priorities: List[Dict]) -> str:
        """Create a human-readable summary of equipment needs."""
        if not priorities:
            return "No immediate equipment upgrades needed"
        
        primary_need = priorities[0]
        summary = f"Primary need: {primary_need['action']}"
        
        if len(priorities) > 1:
            summary += f" (+ {len(priorities) - 1} other upgrades)"
        
        return summary

    def _determine_item_tier(self, item_data) -> str:
        """Determine the tier of an item based on its properties."""
        try:
            item_level = getattr(item_data, 'level', 1)
            item_type = getattr(item_data, 'type', '')
            
            if item_level <= 1:
                return 'starter'
            elif item_level <= 10:
                return 'basic'
            elif item_level <= 20:
                return 'intermediate'
            else:
                return 'advanced'
                
        except Exception:
            return 'unknown'

    def __repr__(self):
        return f"AnalyzeEquipmentAction({self.character_name}, {self.analysis_type})"