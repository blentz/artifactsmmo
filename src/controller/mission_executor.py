"""
Mission Execution System

This module provides YAML-driven mission execution that replaces hardcoded
mission logic with configurable goal template-based execution.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.yaml_data import YamlData
from src.game.globals import CONFIG_PREFIX


class MissionExecutor:
    """
    YAML-configurable mission execution system.
    
    Replaces hardcoded mission loops with goal template-driven execution,
    allowing missions to be defined and modified through YAML configuration.
    """
    
    def __init__(self, goal_manager, controller, config_file: str = None):
        """Initialize mission executor with dependencies."""
        self.logger = logging.getLogger(__name__)
        self.goal_manager = goal_manager
        self.controller = controller
        
        # Load mission configuration
        if config_file is None:
            config_file = f"{CONFIG_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
    def _load_configuration(self) -> None:
        """Load mission execution configuration from YAML."""
        try:
            self.goal_templates = self.config_data.data.get('goal_templates', {})
            self.thresholds = self.config_data.data.get('thresholds', {})
            
            # Mission execution parameters
            self.max_mission_iterations = self.thresholds.get('max_goap_iterations', 25)
            self.max_goal_iterations = self.thresholds.get('max_goap_iterations', 5)
            
            self.logger.debug(f"Loaded mission configuration: max_iterations={self.max_mission_iterations}")
            
        except Exception as e:
            self.logger.error(f"Failed to load mission configuration: {e}")
            # Use defaults as fallback
            self.goal_templates = {}
            self.thresholds = {}
            self.max_mission_iterations = 25
            self.max_goal_iterations = 5
    
    def execute_progression_mission(self, mission_parameters: Dict[str, Any]) -> bool:
        """
        Execute a progression mission using goal template-driven approach.
        
        Replaces the hardcoded execute_autonomous_mission() method with
        configurable goal selection and execution.
        
        Args:
            mission_parameters: Parameters for the mission (e.g., target_level)
            
        Returns:
            True if mission objectives were achieved, False otherwise
        """
        if not self.controller.client or not self.controller.character_state:
            self.logger.error("Cannot execute mission without client and character state")
            return False
            
        self.logger.info("🚀 Starting goal-driven mission execution")
        self.logger.info(f"📋 Mission parameters: {mission_parameters}")
        
        target_level = mission_parameters.get('target_level')
        initial_level = self.controller.character_state.data.get('level', 1)
        mission_success = False
        
        for mission_iteration in range(1, self.max_mission_iterations + 1):
            current_level = self.controller.character_state.data.get('level', 1)
            
            self.logger.info(f"🔄 Mission iteration {mission_iteration}/{self.max_mission_iterations}")
            self.logger.info(f"📊 Current level: {current_level}, Target: {target_level}")
            
            # Check if mission objective is achieved
            if target_level and current_level >= target_level:
                self.logger.info(f"🎉 Mission objective achieved: Level {target_level} reached!")
                mission_success = True
                break
            
            # Use goal manager for intelligent goal selection
            goal_selection = self._select_mission_goal(mission_parameters)
            
            if not goal_selection:
                self.logger.warning("❌ No suitable goal found for current state")
                break
                
            goal_name, goal_config = goal_selection
            self.logger.info(f"🎯 Selected goal: '{goal_name}' - {goal_config.get('description', 'No description')}")
            
            # Execute goal using GOAP planning
            goal_success = self._execute_goal_template(goal_name, goal_config, mission_parameters)
            
            if goal_success:
                self.logger.info(f"✅ Goal '{goal_name}' achieved successfully")
            else:
                self.logger.warning(f"⚠️ Goal '{goal_name}' execution incomplete")
                
            # Check progress toward mission objective
            new_level = self.controller.character_state.data.get('level', 1)
            if new_level > current_level:
                self.logger.info(f"📈 Level progress: {current_level} → {new_level}")
                
        # Report mission results
        final_level = self.controller.character_state.data.get('level', 1)
        levels_gained = final_level - initial_level
        
        self.logger.info("=" * 50)
        self.logger.info("🏆 MISSION EXECUTION RESULTS")
        self.logger.info(f"🎯 Target level: {target_level}")
        self.logger.info(f"📈 Levels gained: {levels_gained} ({initial_level} → {final_level})")
        self.logger.info(f"🔄 Mission iterations: {mission_iteration}")
        self.logger.info(f"🎊 Mission success: {'✅ YES' if mission_success else '❌ NO'}")
        self.logger.info("=" * 50)
        
        return mission_success
    
    def execute_level_progression(self, target_level: int = None) -> bool:
        """
        Execute level progression using goal templates instead of hardcoded logic.
        
        Replaces the massive level_up_goal() method with template-driven execution.
        
        Args:
            target_level: The level to reach (defaults to current level + 1)
            
        Returns:
            True if target level was reached, False otherwise
        """
        if not self.controller.client or not self.controller.character_state:
            self.logger.error("Cannot execute level progression without client and character state")
            return False
        
        # Determine target level
        current_level = self.controller.character_state.data.get('level', 1)
        if target_level is None:
            target_level = current_level + 1
            
        self.logger.info(f"🎯 Starting level progression: {current_level} → {target_level}")
        
        # Use the reach_level goal template
        goal_template = self.goal_templates.get('reach_level')
        if not goal_template:
            self.logger.error("reach_level goal template not found in configuration")
            return False
        
        mission_parameters = {'target_level': target_level}
        return self._execute_goal_template('reach_level', goal_template, mission_parameters)
    
    def _select_mission_goal(self, mission_parameters: Dict[str, Any]) -> Optional[tuple]:
        """
        Select the most appropriate goal for current mission state.
        
        Args:
            mission_parameters: Current mission parameters
            
        Returns:
            Tuple of (goal_name, goal_config) or None if no suitable goal
        """
        try:
            # Get current world state for goal selection
            current_state = self.controller.get_current_world_state()
            
            # Use goal manager for intelligent goal selection
            return self.goal_manager.select_goal(current_state)
            
        except Exception as e:
            self.logger.error(f"Error selecting mission goal: {e}")
            return None
    
    def _execute_goal_template(self, goal_name: str, goal_config: Dict[str, Any], 
                              mission_parameters: Dict[str, Any]) -> bool:
        """
        Execute a goal template using GOAP planning.
        
        Args:
            goal_name: Name of the goal template
            goal_config: Goal configuration from YAML
            mission_parameters: Mission-specific parameters
            
        Returns:
            True if goal was achieved, False otherwise
        """
        try:
            # Get current state for goal state generation
            current_state = self.controller.get_current_world_state()
            
            # Generate goal state with mission parameters and current state
            goal_state = self.goal_manager.generate_goal_state(
                goal_name, goal_config, current_state, **mission_parameters
            )
            
            # Execute goal using GOAP planning with configured iteration limit
            goal_success = self.controller.goap_execution_manager.achieve_goal_with_goap(
                goal_state, 
                self.controller,
                config_file=f"{CONFIG_PREFIX}/actions.yaml",
                max_iterations=self.max_goal_iterations
            )
            
            return goal_success
            
        except Exception as e:
            self.logger.error(f"Error executing goal template '{goal_name}': {e}")
            return False