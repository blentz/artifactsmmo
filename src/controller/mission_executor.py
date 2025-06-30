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
        
        # Initialize clean session state for XP-seeking goal achievement
        if hasattr(self.controller, 'goap_execution_manager'):
            self.controller.goap_execution_manager.initialize_session_state(self.controller)
        
        target_level = mission_parameters.get('target_level')
        initial_level = self.controller.character_state.data.get('level', 1)
        mission_success = False
        
        # Variables to track goal persistence
        current_goal_name = None
        current_goal_config = None
        goal_start_level = initial_level
        mission_iteration = 0
        
        for mission_iteration in range(1, self.max_mission_iterations + 1):
            current_level = self.controller.character_state.data.get('level', 1)
            
            self.logger.info(f"🔄 Mission iteration {mission_iteration}/{self.max_mission_iterations}")
            self.logger.info(f"📊 Current level: {current_level}, Target: {target_level}")
            
            # Check if mission objective is achieved
            if target_level and current_level >= target_level:
                self.logger.info(f"🎉 Mission objective achieved: Level {target_level} reached!")
                mission_success = True
                break
            
            # Check if we need to select a new goal
            # Re-select if: no current goal, leveled up, or HP dropped significantly
            current_hp = self.controller.character_state.data.get('hp', 100)
            max_hp = self.controller.character_state.data.get('max_hp', 100)
            hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
            
            should_reselect_goal = (
                current_goal_name is None or 
                current_level > goal_start_level or
                (hp_percentage < 100 and current_goal_name != 'get_to_safety')  # Combat loss
            )
            
            if should_reselect_goal:
                if current_level > goal_start_level:
                    self.logger.info(f"🎊 Level up detected! Selecting new XP-gaining goal...")
                elif hp_percentage < 100:
                    self.logger.info(f"💔 HP dropped to {hp_percentage:.1f}% - re-evaluating goals...")
                
                # Use goal manager for intelligent goal selection
                goal_selection = self._select_mission_goal(mission_parameters)
                
                if not goal_selection:
                    self.logger.warning("❌ No suitable goal found for current state")
                    break
                    
                current_goal_name, current_goal_config = goal_selection
                goal_start_level = current_level
                self.logger.info(f"🎯 Selected goal: '{current_goal_name}' - {current_goal_config.get('description', 'No description')}")
                if current_goal_name == 'get_to_safety':
                    self.logger.info(f"🛡️ Prioritizing safety recovery before continuing mission")
                else:
                    self.logger.info(f"📌 Will pursue this goal until level-up (from level {goal_start_level})")
            else:
                self.logger.info(f"🔁 Continuing to pursue goal: '{current_goal_name}'")
            
            # Execute goal using GOAP planning
            goal_success = self._execute_goal_template(current_goal_name, current_goal_config, mission_parameters)
            
            if goal_success:
                self.logger.info(f"✅ Goal '{current_goal_name}' achieved successfully")
                # Clear current goal after successful completion to force re-selection
                # This applies to maintenance and emergency goals that shouldn't persist
                if current_goal_name in ['get_to_safety', 'wait_for_cooldown']:
                    self.logger.info(f"🔄 Clearing {current_goal_name} goal to allow new goal selection")
                    current_goal_name = None
                    current_goal_config = None
            else:
                self.logger.warning(f"⚠️ Goal '{current_goal_name}' execution incomplete")
                
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