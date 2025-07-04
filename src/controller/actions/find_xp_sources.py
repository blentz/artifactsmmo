""" FindXpSourcesAction module """

import logging
from typing import Dict, List

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


class FindXpSourcesAction(ActionBase):
    """ 
    Action to find all sources that grant XP for a specific skill using effects analysis.
    
    This action searches the knowledge base for effects that grant XP in the target skill,
    then identifies what actions, items, or activities produce those effects.
    """

    def __init__(self):
        """
        Initialize the find XP sources action.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Find all XP sources for the target skill """
        # Get parameters from context
        skill = context.get('skill')
        if not skill:
            return self.create_error_result("No skill type provided")
            
        self._context = context
        
        try:
            # Get learning manager and knowledge base from context
            learning_manager = context.get('learning_manager')
            knowledge_base = context.knowledge_base
            
            if not learning_manager:
                return self.create_error_result("Learning manager not available")
            
            if not knowledge_base:
                return self.create_error_result("Knowledge base not available")
            
            # Check if effects data is available, if not learn it
            effects_available = self._check_effects_data_available(knowledge_base)
            if not effects_available:
                self.logger.info("🔍 Effects data not available, learning all effects...")
                effects_result = learning_manager.learn_all_effects_bulk(client)
                if not effects_result.get('success'):
                    return self.create_error_result(f"Failed to learn effects: {effects_result.get('error')}")
            
            # Find XP sources for the target skill
            xp_sources = learning_manager.find_xp_sources_for_skill(skill)
            
            if not xp_sources:
                # Analyze if we should look for alternative skill names
                alternative_skills = self._find_alternative_skill_names(skill, knowledge_base)
                for alt_skill in alternative_skills:
                    alt_sources = learning_manager.find_xp_sources_for_skill(alt_skill)
                    if alt_sources:
                        xp_sources = alt_sources
                        self.logger.info(f"Found XP sources using alternative skill name: {alt_skill}")
                        break
            
            if not xp_sources:
                return self.create_error_result(f"No XP sources found for skill '{skill}'")
            
            # Analyze XP sources to find actionable items
            actionable_sources = self._analyze_actionable_sources(xp_sources, knowledge_base, skill)
            
            result = self.create_success_result(
                skill=skill,
                xp_sources=xp_sources,
                actionable_sources=actionable_sources,
                total_sources_found=len(xp_sources),
                actionable_sources_count=len(actionable_sources),
                message=f"Found {len(xp_sources)} XP sources for {skill} skill"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"XP sources search failed: {str(e)}")
            return error_response

    def _check_effects_data_available(self, knowledge_base) -> bool:
        """Check if effects data is available in the knowledge base."""
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return False
            
            # Check if we have effects data
            effects = knowledge_base.data.get('effects', {})
            xp_effects = knowledge_base.data.get('xp_effects_analysis', {})
            
            # We need both effects data and XP analysis
            return len(effects) > 0 and len(xp_effects) > 0
            
        except Exception as e:
            self.logger.debug(f"Error checking effects data availability: {e}")
            return False

    def _find_alternative_skill_names(self, skill: str, knowledge_base) -> List[str]:
        """Find alternative skill names by analyzing patterns in the knowledge base."""
        alternatives = []
        
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return alternatives
            
            # Scan effects data for similar skill patterns
            effects = knowledge_base.data.get('effects', {})
            for effect_name, effect_data in effects.items():
                effect_name_lower = effect_name.lower()
                
                # Look for variations of the target skill in effect names
                if skill.lower() in effect_name_lower:
                    # Extract potential alternative names
                    words = effect_name_lower.replace('_', ' ').split()
                    for word in words:
                        if word != skill.lower() and len(word) > 3:
                            # Check if this could be a skill variant
                            if any(suffix in word for suffix in ['craft', 'ing', 'smith']):
                                if word not in alternatives:
                                    alternatives.append(word)
            
            # Also check items for craft skill variations
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {}) or item_data.get('craft', {})
                if craft_data:
                    craft_skill = craft_data.get('skill', '').lower()
                    if craft_skill and skill.lower() in craft_skill and craft_skill != skill.lower():
                        if craft_skill not in alternatives:
                            alternatives.append(craft_skill)
            
        except Exception as e:
            self.logger.debug(f"Error finding alternative skill names: {e}")
        
        return alternatives

    def _analyze_actionable_sources(self, xp_sources: List[Dict], knowledge_base, skill: str) -> List[Dict]:
        """
        Analyze XP sources to find actionable items/activities.
        
        This method examines the XP effects and tries to determine what specific
        actions the player can take to gain XP in the target skill.
        """
        actionable_sources = []
        
        try:
            for source in xp_sources:
                effect_name = source.get('effect_name', '').lower()
                effect_description = source.get('effect_description', '').lower()
                
                # Analyze effect to determine actionable items
                actionable_info = {
                    'effect_name': source.get('effect_name'),
                    'effect_value': source.get('effect_value', 0),
                    'suggested_actions': [],
                    'required_items': [],
                    'required_locations': []
                }
                
                # Look for crafting-related XP effects
                if 'craft' in effect_name or 'craft' in effect_description:
                    actionable_info['suggested_actions'].append('crafting_items')
                    self._find_craftable_items_for_skill(actionable_info, knowledge_base, skill)
                
                # Look for gathering-related XP effects
                if any(keyword in effect_name for keyword in ['gather', 'harvest', 'mine', 'chop', 'fish']):
                    actionable_info['suggested_actions'].append('gathering_resources')
                    self._find_gatherable_resources_for_skill(actionable_info, knowledge_base, skill)
                
                # Look for consumption-related XP effects (potions, food)
                if any(keyword in effect_name for keyword in ['consume', 'drink', 'eat', 'potion']):
                    actionable_info['suggested_actions'].append('consuming_items')
                    self._find_consumable_items_for_skill(actionable_info, knowledge_base, skill)
                
                if actionable_info['suggested_actions']:
                    actionable_sources.append(actionable_info)
                    
        except Exception as e:
            self.logger.debug(f"Error analyzing actionable sources: {e}")
        
        return actionable_sources

    def _find_craftable_items_for_skill(self, actionable_info: Dict, knowledge_base, skill: str) -> None:
        """Find items that can be crafted to gain XP in the target skill."""
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return
            
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {}) or item_data.get('craft', {})
                if craft_data:
                    craft_skill = craft_data.get('skill')
                    if craft_skill and craft_skill.lower() == skill.lower():
                        actionable_info['required_items'].append({
                            'item_code': item_code,
                            'item_name': item_data.get('name', item_code),
                            'action_type': 'craft',
                            'skill_required': craft_skill,
                            'level_required': craft_data.get('level', 1)
                        })
                        
        except Exception as e:
            self.logger.debug(f"Error finding craftable items: {e}")

    def _find_gatherable_resources_for_skill(self, actionable_info: Dict, knowledge_base, skill: str) -> None:
        """Find resources that can be gathered to gain XP in the target skill."""
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return
            
            resources = knowledge_base.data.get('resources', {})
            for resource_code, resource_data in resources.items():
                # Check if resource is directly associated with the skill
                resource_skill = resource_data.get('skill', '').lower()
                if resource_skill == skill.lower():
                    actionable_info['required_items'].append({
                        'item_code': resource_code,
                        'item_name': resource_data.get('name', resource_code),
                        'action_type': 'gather',
                        'skill_required': skill,
                        'drops': resource_data.get('drops', [])
                    })
                    continue
                
                # Also check resource drops to see if they produce skill-related items
                drops = resource_data.get('drops', [])
                for drop in drops:
                    if isinstance(drop, dict):
                        drop_code = drop.get('code', '')
                        # Check if this drop is used in crafting for our skill
                        if self._is_item_used_for_skill(drop_code, knowledge_base, skill):
                            actionable_info['required_items'].append({
                                'item_code': resource_code,
                                'item_name': resource_data.get('name', resource_code),
                                'action_type': 'gather',
                                'skill_required': skill,
                                'drops': drops,
                                'produces_skill_materials': True
                            })
                            break
                        
        except Exception as e:
            self.logger.debug(f"Error finding gatherable resources: {e}")

    def _is_item_used_for_skill(self, item_code: str, knowledge_base, skill: str) -> bool:
        """Check if an item is used in crafting recipes for the target skill."""
        try:
            items = knowledge_base.data.get('items', {})
            for check_item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {}) or item_data.get('craft', {})
                if craft_data:
                    craft_skill = craft_data.get('skill', '').lower()
                    if craft_skill == skill.lower():
                        # Check if item_code is in the required materials
                        craft_items = craft_data.get('items', [])
                        for craft_item in craft_items:
                            if isinstance(craft_item, dict):
                                required_code = craft_item.get('code', '')
                                if required_code == item_code:
                                    return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking if item is used for skill: {e}")
            return False

    def _find_consumable_items_for_skill(self, actionable_info: Dict, knowledge_base, skill: str) -> None:
        """Find consumable items that grant XP in the target skill."""
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return
            
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                item_type = item_data.get('type', '').lower()
                if item_type in ['consumable', 'potion', 'food']:
                    # Check if this consumable might grant skill XP
                    effects = item_data.get('effects', [])
                    for effect in effects:
                        if isinstance(effect, dict):
                            effect_name = effect.get('name', '').lower()
                            if skill.lower() in effect_name and 'xp' in effect_name:
                                actionable_info['required_items'].append({
                                    'item_code': item_code,
                                    'item_name': item_data.get('name', item_code),
                                    'action_type': 'consume',
                                    'effect_name': effect.get('name'),
                                    'effect_value': effect.get('value', 0)
                                })
                                break
                        
        except Exception as e:
            self.logger.debug(f"Error finding consumable items: {e}")

    def __repr__(self):
        return "FindXpSourcesAction()"