"""
Mission Execution System

This module provides YAML-driven mission execution that replaces hardcoded
mission logic with configurable goal template-based execution.
"""

import logging
from typing import Any, Dict, List, Optional

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


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
        
        # Track failed goals to prevent repeated failures
        self.failed_goals = set()
        self.goal_failure_counts = {}
        self.max_goal_failures = 3  # Allow 3 failures before permanent exclusion
        
        # Track goal progress and success history for persistence weighting
        self.goal_progress_history = {}  # goal_name -> list of progress scores
        self.last_goal_name = None
        self.last_goal_progress = 0.0
        self.goal_persistence_bonus = 0.5  # Weight bonus for recently progressed goals
        
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
    
    def _track_goal_failure(self, goal_name: str) -> None:
        """Track a goal failure and potentially exclude it from future selection."""
        if goal_name is None:
            return
            
        # Increment failure count
        self.goal_failure_counts[goal_name] = self.goal_failure_counts.get(goal_name, 0) + 1
        failure_count = self.goal_failure_counts[goal_name]
        
        self.logger.warning(f"🚫 Goal '{goal_name}' failed (attempt {failure_count}/{self.max_goal_failures})")
        
        # If goal has exceeded max failures, exclude it permanently
        if failure_count >= self.max_goal_failures:
            self.failed_goals.add(goal_name)
            self.logger.error(f"❌ Goal '{goal_name}' exceeded max failures - excluding from future selection")
    
    def _get_available_goals(self) -> List[str]:
        """Get list of goals available for selection, excluding failed goals."""
        all_goals = list(self.goal_templates.keys())
        available_goals = [goal for goal in all_goals if goal not in self.failed_goals]
        
        if len(available_goals) < len(all_goals):
            excluded_count = len(all_goals) - len(available_goals)
            self.logger.info(f"🚫 Excluding {excluded_count} failed goals from selection: {list(self.failed_goals)}")
        
        return available_goals
    
    def _reset_goal_failures_on_success(self, goal_name: str) -> None:
        """Reset failure tracking for a goal that succeeded."""
        if goal_name in self.goal_failure_counts:
            del self.goal_failure_counts[goal_name]
        if goal_name in self.failed_goals:
            self.failed_goals.remove(goal_name)
            self.logger.info(f"✅ Goal '{goal_name}' succeeded - removing from failed goals list")
    
    def _evaluate_goal_progress(self, goal_name: str, current_state: Dict[str, Any], 
                              goal_config: Dict[str, Any]) -> float:
        """
        Evaluate the progress made toward a goal based on current state.
        
        Args:
            goal_name: Name of the goal
            current_state: Current world state
            goal_config: Goal configuration
            
        Returns:
            Progress score between 0.0 (no progress) and 1.0 (complete)
        """
        try:
            # Generate the target state for this goal
            goal_state = self.goal_manager.generate_goal_state(goal_name, current_state)
            if not goal_state:
                return 0.0
            
            # Calculate how many goal conditions are already met
            total_conditions = len(goal_state)
            met_conditions = 0
            
            for condition, target_value in goal_state.items():
                current_value = current_state.get(condition, False)
                
                # Check if condition is met (handle different value types)
                if isinstance(target_value, bool) and current_value == target_value:
                    met_conditions += 1
                elif isinstance(target_value, (int, float)) and isinstance(current_value, (int, float)):
                    # For numeric values, consider partial progress
                    if current_value >= target_value:
                        met_conditions += 1
                    elif current_value > 0:
                        # Partial credit for numeric progress
                        met_conditions += min(current_value / target_value, 1.0)
            
            progress = met_conditions / total_conditions if total_conditions > 0 else 0.0
            return min(progress, 1.0)
            
        except Exception as e:
            self.logger.debug(f"Error evaluating progress for goal {goal_name}: {e}")
            return 0.0
    
    def _record_goal_progress(self, goal_name: str, progress: float) -> None:
        """Record progress for a goal in the history."""
        if goal_name not in self.goal_progress_history:
            self.goal_progress_history[goal_name] = []
        
        self.goal_progress_history[goal_name].append(progress)
        
        # Keep only recent progress (last 5 attempts)
        if len(self.goal_progress_history[goal_name]) > 5:
            self.goal_progress_history[goal_name] = self.goal_progress_history[goal_name][-5:]
        
        self.last_goal_name = goal_name
        self.last_goal_progress = progress
        
        if progress > 0.3:  # Consider 30%+ as meaningful progress
            self.logger.info(f"📈 Goal '{goal_name}' showing progress: {progress:.1%}")
    
    def _get_goal_persistence_weight(self, goal_name: str) -> float:
        """
        Get persistence weight bonus for a goal based on recent progress.
        
        Args:
            goal_name: Name of the goal
            
        Returns:
            Weight bonus (0.0 to goal_persistence_bonus)
        """
        # Strong bonus if this was the last goal and showed progress
        if (goal_name == self.last_goal_name and 
            self.last_goal_progress > 0.2):  # 20% progress threshold
            bonus = self.goal_persistence_bonus * self.last_goal_progress
            self.logger.debug(f"🎯 Persistence bonus for '{goal_name}': +{bonus:.2f} (last progress: {self.last_goal_progress:.1%})")
            return bonus
        
        # Moderate bonus if goal has shown progress recently
        if goal_name in self.goal_progress_history:
            recent_progress = self.goal_progress_history[goal_name]
            if recent_progress and max(recent_progress) > 0.2:
                avg_progress = sum(recent_progress) / len(recent_progress)
                bonus = self.goal_persistence_bonus * 0.5 * avg_progress
                self.logger.debug(f"📊 Historical bonus for '{goal_name}': +{bonus:.2f} (avg progress: {avg_progress:.1%})")
                return bonus
        
        return 0.0
    
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
            # Re-select if: no current goal, leveled up, HP dropped, or combat not viable
            current_hp = self.controller.character_state.data.get('hp', 100)
            max_hp = self.controller.character_state.data.get('max_hp', 100)
            hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
            
            # Get current world state to check combat viability
            current_state = self.controller.get_current_world_state()
            combat_not_viable = current_state.get('combat_not_viable', False)
            
            should_reselect_goal = (
                current_goal_name is None or 
                current_level > goal_start_level or
                (hp_percentage < 100 and current_goal_name != 'get_to_safety') or  # Combat loss
                (combat_not_viable and current_goal_name == 'hunt_monsters')  # Combat no longer viable
            )
            
            if should_reselect_goal:
                if current_level > goal_start_level:
                    self.logger.info("🎊 Level up detected! Selecting new XP-gaining goal...")
                elif hp_percentage < 100:
                    self.logger.info(f"💔 HP dropped to {hp_percentage:.1f}% - re-evaluating goals...")
                elif combat_not_viable and current_goal_name == 'hunt_monsters':
                    self.logger.info("⚔️ Combat no longer viable - switching from hunt_monsters to equipment upgrade goals...")
                
                # Use goal manager for intelligent goal selection
                goal_selection = self._select_mission_goal(mission_parameters)
                
                if not goal_selection:
                    self.logger.warning("❌ No suitable goal found for current state")
                    break
                    
                current_goal_name, current_goal_config = goal_selection
                goal_start_level = current_level
                self.logger.info(f"🎯 Selected goal: '{current_goal_name}' - {current_goal_config.get('description', 'No description')}")
                if current_goal_name == 'get_to_safety':
                    self.logger.info("🛡️ Prioritizing safety recovery before continuing mission")
                else:
                    self.logger.info(f"📌 Will pursue this goal until level-up (from level {goal_start_level})")
            else:
                self.logger.info(f"🔁 Continuing to pursue goal: '{current_goal_name}'")
            
            # Execute goal using GOAP planning
            goal_success = self._execute_goal_template(current_goal_name, current_goal_config, mission_parameters)
            
            if goal_success:
                self.logger.info(f"✅ Goal '{current_goal_name}' achieved successfully")
                # Reset failure tracking for successful goals
                self._reset_goal_failures_on_success(current_goal_name)
                
                # Clear current goal after successful completion to force re-selection
                # This applies to maintenance and emergency goals that shouldn't persist
                if current_goal_name in ['get_to_safety', 'wait_for_cooldown']:
                    self.logger.info(f"🔄 Clearing {current_goal_name} goal to allow new goal selection")
                    current_goal_name = None
                    current_goal_config = None
            else:
                self.logger.warning(f"⚠️ Goal '{current_goal_name}' execution incomplete")
                # Track the failure to prevent repeated attempts
                self._track_goal_failure(current_goal_name)
                
                # Force re-selection to try a different goal
                self.logger.info("🔄 Forcing goal re-selection due to failure")
                current_goal_name = None
                current_goal_config = None
                
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
        Select the most appropriate goal for current mission state with persistence weighting.
        
        Args:
            mission_parameters: Current mission parameters
            
        Returns:
            Tuple of (goal_name, goal_config) or None if no suitable goal
        """
        try:
            # Get current world state for goal selection
            current_state = self.controller.get_current_world_state()
            
            # Get available goals excluding failed ones
            available_goals = self._get_available_goals()
            
            # Calculate persistence weights for available goals
            persistence_weights = {}
            for goal_name in available_goals:
                weight = self._get_goal_persistence_weight(goal_name)
                if weight > 0:
                    persistence_weights[goal_name] = weight
            
            if persistence_weights:
                self.logger.info(f"🎯 Applying persistence weights: {persistence_weights}")
            
            # Use goal manager for intelligent goal selection with persistence weighting
            return self.goal_manager.select_goal(current_state, available_goals, 
                                               goal_weights=persistence_weights)
            
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
            
            # Track progress before execution
            progress_before = self._evaluate_goal_progress(goal_name, current_state, goal_config)
            
            # Execute goal using GOAP planning with configured iteration limit
            goal_success = self.controller.goap_execution_manager.achieve_goal_with_goap(
                goal_state, 
                self.controller,
                config_file=f"{CONFIG_PREFIX}/actions.yaml",
                max_iterations=self.max_goal_iterations
            )
            
            # Track progress after execution
            post_execution_state = self.controller.get_current_world_state()
            progress_after = self._evaluate_goal_progress(goal_name, post_execution_state, goal_config)
            
            # Record the progress for persistence weighting
            self._record_goal_progress(goal_name, progress_after)
            
            # Log progress change
            if progress_after > progress_before:
                self.logger.info(f"📈 Goal '{goal_name}' progress improved: {progress_before:.1%} → {progress_after:.1%}")
            elif progress_after < progress_before:
                self.logger.warning(f"📉 Goal '{goal_name}' progress decreased: {progress_before:.1%} → {progress_after:.1%}")
            else:
                self.logger.debug(f"📊 Goal '{goal_name}' progress unchanged: {progress_after:.1%}")
            
            return goal_success
            
        except Exception as e:
            self.logger.error(f"Error executing goal template '{goal_name}': {e}")
            return False