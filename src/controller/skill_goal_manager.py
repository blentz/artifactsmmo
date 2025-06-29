"""
Skill-Specific Goal Management System

This module provides YAML-configurable skill progression goals for crafting,
gathering, combat, and other skills, replacing hardcoded skill logic with
template-driven skill advancement.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from src.lib.yaml_data import YamlData
from src.lib.goap import World, Planner, Action_List
from src.lib.actions_data import ActionsData
from src.game.globals import CONFIG_PREFIX


class SkillType(Enum):
    """Enumeration of supported skill types."""
    COMBAT = "combat"
    WOODCUTTING = "woodcutting"
    MINING = "mining"
    FISHING = "fishing"
    WEAPONCRAFTING = "weaponcrafting"
    GEARCRAFTING = "gearcrafting"
    JEWELRYCRAFTING = "jewelrycrafting"
    COOKING = "cooking"
    ALCHEMY = "alchemy"


class SkillGoalManager:
    """
    YAML-configurable skill progression goal management system.
    
    Handles skill-specific goals for all crafting, gathering, and combat skills
    using template-driven goal generation and execution.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize skill goal manager with configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Load skill goal configuration
        if config_file is None:
            config_file = f"{CONFIG_PREFIX}/skill_goals.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
        # Initialize GOAP components
        self.current_world = None
        self.current_planner = None
        
    def _load_configuration(self) -> None:
        """Load skill goal templates and progression rules from YAML."""
        try:
            self.skill_templates = self.config_data.data.get('skill_templates', {})
            self.progression_rules = self.config_data.data.get('progression_rules', {})
            self.skill_thresholds = self.config_data.data.get('skill_thresholds', {})
            self.resource_requirements = self.config_data.data.get('resource_requirements', {})
            self.crafting_chains = self.config_data.data.get('crafting_chains', {})
            
            self.logger.info(f"Loaded {len(self.skill_templates)} skill templates")
            self.logger.info(f"Loaded progression rules for {len(self.progression_rules)} skills")
            
        except Exception as e:
            self.logger.error(f"Failed to load skill goal configuration: {e}")
            # Initialize with empty configs as fallback
            self.skill_templates = {}
            self.progression_rules = {}
            self.skill_thresholds = {}
            self.resource_requirements = {}
            self.crafting_chains = {}
    
    def create_skill_up_goal(self, skill_type: SkillType, target_level: int, 
                           current_level: int = None) -> Dict[str, Any]:
        """
        Create a skill progression goal for a specific skill.
        
        Args:
            skill_type: The skill to level up
            target_level: The target level to reach
            current_level: Current skill level (for optimization)
            
        Returns:
            GOAP goal state dictionary
        """
        skill_name = skill_type.value
        
        if skill_name not in self.skill_templates:
            self.logger.error(f"No skill template found for {skill_name}")
            return {}
        
        template = self.skill_templates[skill_name]
        
        # Generate skill-specific goal state
        goal_state = {
            f"{skill_name}_level": target_level,
            "character_alive": True,
            "character_safe": True
        }
        
        # Add skill-specific requirements
        if "requirements" in template:
            for req_key, req_value in template["requirements"].items():
                if isinstance(req_value, str) and "${target_level}" in req_value:
                    req_value = req_value.replace("${target_level}", str(target_level))
                goal_state[req_key] = req_value
        
        # Add resource requirements if this is a crafting skill
        if self._is_crafting_skill(skill_type):
            resource_needs = self._calculate_resource_needs(skill_type, current_level, target_level)
            goal_state.update(resource_needs)
        
        self.logger.info(f"Created {skill_name} skill-up goal: level {current_level} → {target_level}")
        return goal_state
    
    def _is_crafting_skill(self, skill_type: SkillType) -> bool:
        """Check if a skill is a crafting skill that requires resources."""
        crafting_skills = {
            SkillType.WEAPONCRAFTING,
            SkillType.GEARCRAFTING, 
            SkillType.JEWELRYCRAFTING,
            SkillType.COOKING,
            SkillType.ALCHEMY
        }
        return skill_type in crafting_skills
    
    def _calculate_resource_needs(self, skill_type: SkillType, current_level: int, 
                                target_level: int) -> Dict[str, Any]:
        """Calculate resource requirements for skill progression."""
        skill_name = skill_type.value
        resource_needs = {}
        
        if skill_name in self.resource_requirements:
            requirements = self.resource_requirements[skill_name]
            
            # Calculate levels to gain
            levels_to_gain = target_level - (current_level or 1)
            
            for resource, config in requirements.items():
                if isinstance(config, dict):
                    base_amount = config.get("base_amount", 10)
                    per_level = config.get("per_level", 5)
                    total_needed = base_amount + (levels_to_gain * per_level)
                    resource_needs[f"has_{resource}"] = total_needed
                else:
                    resource_needs[f"has_{resource}"] = config
        
        return resource_needs
    
    def get_skill_progression_strategy(self, skill_type: SkillType, 
                                     current_level: int) -> Dict[str, Any]:
        """
        Get the optimal progression strategy for a skill at a given level.
        
        Args:
            skill_type: The skill to get strategy for
            current_level: Current skill level
            
        Returns:
            Strategy dictionary with actions and priorities
        """
        skill_name = skill_type.value
        
        if skill_name not in self.progression_rules:
            return {"error": f"No progression rules for {skill_name}"}
        
        rules = self.progression_rules[skill_name]
        
        # Find the appropriate level range
        for level_range, strategy in rules.items():
            if self._level_in_range(current_level, level_range):
                return {
                    "skill": skill_name,
                    "level_range": level_range,
                    "strategy": strategy,
                    "current_level": current_level
                }
        
        # Fallback to highest level strategy
        highest_range = max(rules.keys(), key=lambda x: self._parse_level_range(x)[1])
        return {
            "skill": skill_name,
            "level_range": highest_range,
            "strategy": rules[highest_range],
            "current_level": current_level
        }
    
    def _level_in_range(self, level: int, level_range: str) -> bool:
        """Check if a level falls within a specified range."""
        min_level, max_level = self._parse_level_range(level_range)
        return min_level <= level <= max_level
    
    def _parse_level_range(self, level_range: str) -> Tuple[int, int]:
        """Parse level range string like '1-10' or '20-30'."""
        if '-' in level_range:
            parts = level_range.split('-')
            return int(parts[0]), int(parts[1])
        else:
            # Single level
            level = int(level_range)
            return level, level
    
    def create_world_with_planner(self, start_state: Dict[str, Any], 
                                goal_state: Dict[str, Any], 
                                actions_config: Dict[str, Dict]) -> World:
        """
        Create a GOAP world with planner for skill progression.
        
        Args:
            start_state: Current state
            goal_state: Desired skill progression state
            actions_config: Available actions
            
        Returns:
            World with planner configured for skill goals
        """
        world = World()
        
        # Get all keys from both start and goal states
        all_keys = set(start_state.keys()) | set(goal_state.keys())
        
        # Create planner with all required state keys
        planner = Planner(*all_keys)
        
        # Set start and goal states on the planner
        planner.set_start_state(**start_state)
        planner.set_goal_state(**goal_state)
        
        # Create and configure actions
        action_list = Action_List()
        
        for action_name, action_config in actions_config.items():
            if self._is_skill_relevant_action(action_name, goal_state):
                action_list.add_condition(
                    action_name,
                    **action_config.get('conditions', {})
                )
                action_list.add_reaction(
                    action_name,
                    **action_config.get('reactions', {})
                )
                weight = action_config.get('weight', 1.0)
                action_list.set_weight(action_name, weight)
        
        # Set action list on planner
        planner.set_action_list(action_list)
        
        # Add planner to world
        world.add_planner(planner)
        
        self.current_world = world
        self.current_planner = planner
        
        return world
    
    def _is_skill_relevant_action(self, action_name: str, goal_state: Dict[str, Any]) -> bool:
        """Check if an action is relevant for the current skill goals."""
        # All basic actions are relevant
        basic_actions = ['move', 'rest', 'wait']
        if action_name in basic_actions:
            return True
        
        # Check if action relates to any skill in the goal state
        for goal_key in goal_state.keys():
            if any(skill.value in goal_key for skill in SkillType):
                # This is a skill-related goal
                skill_name = next(skill.value for skill in SkillType if skill.value in goal_key)
                
                # Check if action is relevant for this skill
                if self._action_relevant_for_skill(action_name, skill_name):
                    return True
        
        return True  # Include by default for now
    
    def _action_relevant_for_skill(self, action_name: str, skill_name: str) -> bool:
        """Check if an action is relevant for a specific skill."""
        skill_action_map = {
            "combat": ["attack", "find_monsters", "hunt"],
            "woodcutting": ["gather_resources", "find_resources"],
            "mining": ["gather_resources", "find_resources"],
            "fishing": ["gather_resources", "find_resources"],
            "weaponcrafting": ["craft_item", "gather_resources"],
            "gearcrafting": ["craft_item", "gather_resources"],
            "jewelrycrafting": ["craft_item", "gather_resources"],
            "cooking": ["craft_item", "gather_resources"],
            "alchemy": ["craft_item", "gather_resources"]
        }
        
        relevant_actions = skill_action_map.get(skill_name, [])
        return action_name in relevant_actions
    
    def achieve_skill_goal_with_goap(self, skill_type: SkillType, target_level: int,
                                   current_state: Dict[str, Any], 
                                   controller) -> bool:
        """
        Use GOAP planning to achieve a skill progression goal.
        
        Args:
            skill_type: The skill to level up
            target_level: Target skill level
            current_state: Current world state
            controller: AI controller for execution
            
        Returns:
            True if skill goal was achieved, False otherwise
        """
        # Create skill-specific goal
        current_skill_level = current_state.get(f"{skill_type.value}_level", 1)
        goal_state = self.create_skill_up_goal(skill_type, target_level, current_skill_level)
        
        if not goal_state:
            return False
        
        # Load skill-appropriate actions
        actions_config = self._load_skill_actions(skill_type)
        
        # Create world and plan
        world = self.create_world_with_planner(current_state, goal_state, actions_config)
        planner = self.current_planner
        plans = planner.calculate()
        
        if not plans:
            self.logger.warning(f"No plan found for {skill_type.value} skill progression")
            return False
        
        # Execute the plan using the controller
        best_plan = plans[0]
        self.logger.info(f"Executing {skill_type.value} skill plan with {len(best_plan)} actions")
        
        # Convert GOAP plan to controller plan format
        controller.current_plan = []
        for action in best_plan:
            if isinstance(action, dict):
                # Action is already a dictionary
                controller.current_plan.append(action)
            else:
                # Action is an object with name and reactions
                action_dict = {
                    "name": getattr(action, 'name', str(action)),
                    **getattr(action, 'reactions', {})
                }
                controller.current_plan.append(action_dict)
        controller.current_action_index = 0
        
        # Execute the plan
        return controller.execute_plan()
    
    def _load_skill_actions(self, skill_type: SkillType) -> Dict[str, Dict]:
        """Load actions appropriate for a specific skill."""
        try:
            # Try skill-specific config first
            skill_config_file = f"{CONFIG_PREFIX}/{skill_type.value}_actions.yaml"
            skill_actions_data = ActionsData(skill_config_file)
            skill_actions = skill_actions_data.get_actions()
            
            if skill_actions:
                self.logger.info(f"Loaded {len(skill_actions)} {skill_type.value}-specific actions")
                return skill_actions
        except Exception as e:
            self.logger.debug(f"No specific actions for {skill_type.value}: {e}")
        
        # Fallback to default actions
        try:
            default_actions_data = ActionsData(f"{CONFIG_PREFIX}/default_actions.yaml")
            default_actions = default_actions_data.get_actions()
            self.logger.info(f"Using {len(default_actions)} default actions for {skill_type.value}")
            return default_actions
        except Exception as e:
            self.logger.error(f"Could not load actions for {skill_type.value}: {e}")
            return {}
    
    def get_available_skills(self) -> List[SkillType]:
        """Get list of skills that have goal templates defined."""
        available = []
        for skill in SkillType:
            if skill.value in self.skill_templates:
                available.append(skill)
        return available
    
    def reload_configuration(self) -> None:
        """Reload skill goal configuration from YAML."""
        self.config_data.data = self.config_data.load() or {}
        self._load_configuration()
        self.logger.info("Skill goal configuration reloaded")