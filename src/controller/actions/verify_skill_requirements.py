"""
Verify Skill Requirements Action

This action verifies that the character has the required crafting skill level
to craft the selected item.
"""

from typing import Dict

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext


class VerifySkillRequirementsAction(ActionBase):
    """
    Action to verify crafting skill requirements for selected recipe.
    
    This action checks if the character has sufficient skill level
    to craft the selected item.
    """
    
    # GOAP parameters
    conditions = {
        'equipment_status': {
            'has_selected_item': True
        },
        'materials': {
            'status': 'sufficient'
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'skill_requirements': {
            'verified': True,
            'sufficient': True  # Will be overridden if skill is insufficient
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the skill verification action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute skill requirements verification.
        
        Args:
            client: API client for character data
            context: ActionContext containing selected item and recipe
            
        Returns:
            Action result with skill verification status
        """
        self._context = context
        
        character_name = context.character_name
        selected_item = context.get('selected_item')
        selected_recipe = context.get('selected_recipe', {})
        
        if not selected_item:
            return self.create_error_result("No selected item available")
            
        self.logger.info(f"🔍 Verifying skill requirements for {selected_item}")
        
        try:
            # Get current character data
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
                
            character_data = character_response.data
            
            # Determine required skill and level
            skill_info = self._get_skill_requirements(selected_recipe, selected_item, context)
            
            if not skill_info:
                return self.create_error_result(f"Could not determine skill requirements for {selected_item}")
            
            required_skill = skill_info['skill']
            required_level = skill_info['level']
            
            # Get character's current skill level
            current_level = self._get_character_skill_level(character_data, required_skill)
            
            # Check if skill is sufficient
            skill_sufficient = current_level >= required_level
            
            # Update reactions based on results
            if skill_sufficient:
                self.reactions = {
                    'skill_requirements': {
                        'verified': True,
                        'sufficient': True
                    }
                }
                self.logger.info(f"✅ Skill sufficient: {required_skill} {current_level}/{required_level}")
            else:
                self.reactions = {
                    'skill_requirements': {
                        'verified': True,
                        'sufficient': False
                    }
                }
                self.logger.info(f"❌ Skill insufficient: {required_skill} {current_level}/{required_level}")
            
            # Store results in context
            context.set_result('skill_verification', {
                'required_skill': required_skill,
                'required_level': required_level,
                'current_level': current_level,
                'sufficient': skill_sufficient,
                'shortfall': max(0, required_level - current_level)
            })
            
            return self.create_success_result(
                f"Skill verification completed: {required_skill} {current_level}/{required_level}",
                required_skill=required_skill,
                required_level=required_level,
                current_level=current_level,
                skill_sufficient=skill_sufficient,
                shortfall=max(0, required_level - current_level)
            )
            
        except Exception as e:
            return self.create_error_result(f"Skill verification failed: {str(e)}")
            
    def _get_skill_requirements(self, recipe: Dict, item_code: str, context: ActionContext) -> Dict:
        """Get skill requirements for the recipe."""
        try:
            # First try from the recipe data if available
            if recipe and 'workshop' in recipe:
                workshop_type = recipe['workshop']
                # Map workshop to skill
                skill_name = self._workshop_to_skill(workshop_type)
                # For now, assume level 1 requirement (can be enhanced later)
                return {'skill': skill_name, 'level': 1}
                
            # Fall back to knowledge base lookup
            knowledge_base = getattr(context, 'knowledge_base', None)
            if knowledge_base:
                item_data = knowledge_base.get_item_data(item_code)
                if item_data and isinstance(item_data, dict):
                    craft_info = item_data.get('craft', {})
                    if craft_info:
                        skill = craft_info.get('skill')
                        level = craft_info.get('level', 1)
                        if skill:
                            return {'skill': skill, 'level': level}
                            
            # No hardcoded fallbacks - API is the source of truth
            self.logger.warning(f"Could not determine skill requirements for {item_code} - API data required")
            return None
            
        except Exception as e:
            self.logger.warning(f"Error determining skill requirements for {item_code}: {e}")
            return None
            
    def _workshop_to_skill(self, workshop_type: str) -> str:
        """Map workshop type to crafting skill."""
        # Workshop type usually matches the skill name directly
        # If not, this should come from configuration or API
        return workshop_type.lower()
        
    def _get_fallback_skill(self, item_code: str) -> Dict:
        """Get fallback skill requirements - API data should be used instead."""
        # No hardcoded fallbacks - API is the source of truth
        self.logger.warning(f"No skill requirements found for {item_code} - API data required")
        return None
        
    def _get_character_skill_level(self, character_data, skill_name: str) -> int:
        """Get the character's current level in the specified skill."""
        try:
            # Check different possible skill attribute names
            skill_attrs = [
                f'{skill_name}_level',
                f'{skill_name}Level', 
                skill_name
            ]
            
            for attr in skill_attrs:
                if hasattr(character_data, attr):
                    level = getattr(character_data, attr)
                    if isinstance(level, int):
                        return level
                        
            # If no direct attribute, check if there's a skills dict
            if hasattr(character_data, 'skills'):
                skills = getattr(character_data, 'skills')
                if isinstance(skills, dict) and skill_name in skills:
                    return skills[skill_name]
                    
            # Default to 1 if skill not found (most characters start at level 1)
            self.logger.warning(f"Could not find {skill_name} skill level, defaulting to 1")
            return 1
            
        except Exception as e:
            self.logger.warning(f"Error getting skill level for {skill_name}: {e}")
            return 1
            
    def __repr__(self):
        return "VerifySkillRequirementsAction()"