"""
Check Skill Requirement Action

This action checks if the character meets skill requirements for a specific task 
(like crafting a weapon) and sets appropriate state variables to trigger skill upgrades.
"""

from typing import Dict, Optional
import logging
from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from .base import ActionBase


class CheckSkillRequirementAction(ActionBase):
    """
    Action to check skill requirements for a specific task and set state variables.
    
    This action analyzes character skills vs required skills for a task and communicates
    the requirements to the GOAP system through state updates.
    """

    # GOAP parameters
    conditions = {"character_alive": True}
    reactions = {
        "skill_requirements_checked": True,
        "need_skill_upgrade": True,
        "skill_level_sufficient": True,
        "required_skill_level_known": True
    }
    weights = {"skill_requirements_checked": 10}

    def __init__(self, character_name: str, task_type: str = "crafting", target_item: str = None):
        """
        Initialize the skill requirement check action.

        Args:
            character_name: Name of the character
            task_type: Type of task to check requirements for (crafting, combat, etc.)
            target_item: Specific item to check requirements for (e.g., weapon code)
        """
        super().__init__()
        self.character_name = character_name
        self.task_type = task_type
        self.target_item = target_item
        self.logger = logging.getLogger(__name__)

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """Check skill requirements and update state accordingly."""
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        # Store kwargs for use in skill extraction
        self.kwargs = kwargs
            
        self.log_execution_start(
            character_name=self.character_name,
            task_type=self.task_type,
            target_item=self.target_item
        )
        
        try:
            # Get current character data to check skill levels
            character_response = get_character_api(name=self.character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            # Store character data for skill discovery
            self.character_data = character_data
            character_skills = self._extract_character_skills(character_data)
            
            # Get task requirements based on task type and target
            requirements = self._get_task_requirements(client, character_skills)
            if not requirements:
                return self.get_error_response(f"Could not determine skill requirements for {self.task_type}")
            
            # Check if requirements are met
            skill_check_results = self._check_skill_requirements(character_skills, requirements)
            
            # Prepare result with detailed skill information
            result = self.get_success_response(
                skill_requirements_checked=True,
                task_type=self.task_type,
                target_item=self.target_item,
                **skill_check_results
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Skill requirement check failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _extract_character_skills(self, character_data) -> Dict[str, int]:
        """Extract character skill levels from character data using knowledge base discovery."""
        skills = {}
        
        # Get skill types from knowledge base discovery
        knowledge_base = self.kwargs.get('knowledge_base') if hasattr(self, 'kwargs') else None
        skill_types = self._get_skill_types_from_knowledge_base(knowledge_base)
        
        # Scan character data directly for all skill attributes to ensure we don't miss any
        # This avoids hardcoded skill lists and discovers skills dynamically
        if hasattr(self, 'character_data'):
            character_data = self.character_data
            for attr_name in dir(character_data):
                if attr_name.endswith('_level') and not attr_name.startswith('_'):
                    skill_name = attr_name.replace('_level', '')
                    if skill_name not in skill_types:
                        skill_types.append(skill_name)
        
        for skill in skill_types:
            level_key = f"{skill}_level"
            if hasattr(character_data, level_key):
                skills[skill] = getattr(character_data, level_key, 0)
        
        return skills

    def _get_skill_types_from_knowledge_base(self, knowledge_base=None) -> list:
        """
        Get skill types by scanning knowledge base for all known skills.
        
        Args:
            knowledge_base: Knowledge base to scan for skill types
            
        Returns:
            List of skill types discovered from knowledge base
        """
        skill_types = []
        
        # Scan knowledge base for skill types in item craft data
        if knowledge_base and hasattr(knowledge_base, 'data'):
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data', {})
                if craft_data:
                    skill = craft_data.get('skill')
                    if skill and skill != 'unknown' and skill not in skill_types:
                        skill_types.append(skill)
        
        return skill_types

    def _get_task_requirements(self, client, character_skills: Dict[str, int]) -> Optional[Dict]:
        """Get skill requirements for the specified task."""
        try:
            if self.task_type == "crafting" and self.target_item:
                return self._get_crafting_requirements(client, self.target_item)
            elif self.task_type == "weaponcrafting" and self.target_item:
                return self._get_weaponcrafting_requirements(client, self.target_item)
            elif self.task_type == "general_weaponcrafting":
                # Check general weaponcrafting requirements for basic weapons
                return self._get_general_weaponcrafting_requirements(client)
            else:
                self.logger.warning(f"Unknown task type: {self.task_type}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Error getting task requirements: {e}")
            return None

    def _get_crafting_requirements(self, client, item_code: str) -> Optional[Dict]:
        """Get skill requirements for crafting a specific item."""
        try:
            item_response = get_item_api(code=item_code, client=client)
            if not item_response or not item_response.data:
                return None
            
            item_data = item_response.data
            craft_info = getattr(item_data, 'craft', None)
            if not craft_info:
                return None
            
            required_skill = getattr(craft_info, 'skill', 'unknown')
            required_level = getattr(craft_info, 'level', 1)
            
            return {
                'primary_skill': required_skill,
                'primary_level': required_level,
                'item_name': getattr(item_data, 'name', item_code)
            }
            
        except Exception as e:
            self.logger.warning(f"Error getting crafting requirements for {item_code}: {e}")
            return None

    def _get_weaponcrafting_requirements(self, client, weapon_code: str) -> Optional[Dict]:
        """Get weaponcrafting requirements for a specific weapon."""
        requirements = self._get_crafting_requirements(client, weapon_code)
        if requirements and requirements['primary_skill'] == 'weaponcrafting':
            return requirements
        return None

    def _get_general_weaponcrafting_requirements(self, client) -> Optional[Dict]:
        """Get general weaponcrafting requirements for basic weapons."""
        # Check basic weapons to find the lowest level requirement
        basic_weapons = ['copper_dagger', 'wooden_staff']
        lowest_requirement = None
        
        for weapon_code in basic_weapons:
            requirements = self._get_weaponcrafting_requirements(client, weapon_code)
            if requirements:
                if not lowest_requirement or requirements['primary_level'] < lowest_requirement['primary_level']:
                    lowest_requirement = requirements
                    lowest_requirement['weapon_code'] = weapon_code
        
        return lowest_requirement

    def _check_skill_requirements(self, character_skills: Dict[str, int], 
                                 requirements: Dict) -> Dict:
        """Check if character meets skill requirements."""
        primary_skill = requirements.get('primary_skill', 'unknown')
        required_level = requirements.get('primary_level', 1)
        current_level = character_skills.get(primary_skill, 0)
        
        skill_sufficient = current_level >= required_level
        needs_upgrade = not skill_sufficient
        
        result = {
            'skill_level_sufficient': skill_sufficient,
            'need_skill_upgrade': needs_upgrade,
            'required_skill': primary_skill,
            'required_skill_level': required_level,
            'current_skill_level': current_level,
            'skill_gap': max(0, required_level - current_level),
            'target_item_name': requirements.get('item_name', self.target_item),
            'requirements_details': requirements
        }
        
        # Add specific weaponcrafting flags
        if primary_skill == 'weaponcrafting':
            result['need_weaponcrafting_upgrade'] = needs_upgrade
            result['weaponcrafting_level_sufficient'] = skill_sufficient
            result['required_weaponcrafting_level'] = required_level
            result['current_weaponcrafting_level'] = current_level
        
        # Log the skill check results
        if needs_upgrade:
            self.logger.info(f"🔧 Skill upgrade needed: {primary_skill} level {current_level} < {required_level} "
                           f"for {requirements.get('item_name', self.target_item)}")
        else:
            self.logger.info(f"✅ Skill requirements met: {primary_skill} level {current_level} >= {required_level}")
        
        return result

    def __repr__(self):
        return f"CheckSkillRequirementAction({self.character_name}, {self.task_type}, {self.target_item})"