"""
Cooldown Management System

This module provides YAML-configurable cooldown detection and handling,
replacing hardcoded cooldown logic in the AI controller.
"""

import logging
import time
from datetime import datetime, timezone

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


class CooldownManager:
    """
    YAML-configurable cooldown management system.
    
    Handles cooldown detection, waiting, and character state refresh
    using configuration-driven thresholds and behavior.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize cooldown manager with configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Load configuration - using clean templates for testing
        if config_file is None:
            config_file = f"{CONFIG_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
        # Character state refresh tracking
        self._last_character_refresh = 0
        
    def _load_configuration(self) -> None:
        """Load cooldown configuration from YAML."""
        try:
            thresholds = self.config_data.data.get('thresholds', {})
            
            # Load cooldown configuration
            self.max_cooldown_wait = thresholds.get('max_cooldown_wait', 65)
            self.character_refresh_cache_duration = thresholds.get('character_refresh_cache_duration', 5.0)
            
            self.logger.debug(f"Loaded cooldown configuration: max_wait={self.max_cooldown_wait}")
            
        except Exception as e:
            self.logger.error(f"Failed to load cooldown configuration: {e}")
            # Use defaults
            self.max_cooldown_wait = 65
            self.character_refresh_cache_duration = 5.0
    
    def is_character_on_cooldown(self, character_state) -> bool:
        """
        Check if character is currently on cooldown based on API data.
        
        Args:
            character_state: Character state object
            
        Returns:
            True if character is on cooldown, False otherwise
        """
        if not character_state:
            return False
            
        try:
            char_data = character_state.data
            cooldown_expiration = char_data.get('cooldown_expiration')
            
            if not cooldown_expiration:
                return False
                
            if isinstance(cooldown_expiration, str):
                cooldown_end = datetime.fromisoformat(cooldown_expiration)
                current_time = datetime.now(timezone.utc)
                
                return current_time < cooldown_end
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking cooldown status: {e}")
            return False
    
    def calculate_wait_duration(self, character_state) -> float:
        """
        Calculate wait duration based on cooldown expiration from API.
        
        Args:
            character_state: Character state object
            
        Returns:
            Wait duration in seconds (0.0 if no wait needed)
        """
        if not character_state:
            self.logger.debug("calculate_wait_duration: No character_state provided")
            return 0.0
            
        try:
            char_data = character_state.data
            cooldown_expiration = char_data.get('cooldown_expiration')
            
            self.logger.debug(f"calculate_wait_duration: cooldown_expiration = {cooldown_expiration} (type: {type(cooldown_expiration)})")
            
            if not cooldown_expiration:
                self.logger.debug("calculate_wait_duration: No cooldown_expiration found, returning 0.0")
                return 0.0
                
            if isinstance(cooldown_expiration, str):
                cooldown_end = datetime.fromisoformat(cooldown_expiration)
                current_time = datetime.now(timezone.utc)
                
                self.logger.debug(f"calculate_wait_duration: cooldown_end = {cooldown_end}")
                self.logger.debug(f"calculate_wait_duration: current_time = {current_time}")
                
                if current_time < cooldown_end:
                    remaining_seconds = (cooldown_end - current_time).total_seconds()
                    wait_duration = min(remaining_seconds, self.max_cooldown_wait)
                    self.logger.debug(f"calculate_wait_duration: remaining_seconds = {remaining_seconds:.1f}, wait_duration = {wait_duration:.1f}")
                    return wait_duration
                else:
                    # Cooldown has expired
                    self.logger.debug(f"calculate_wait_duration: Cooldown expired, returning 0.0")
                    return 0.0
            elif isinstance(cooldown_expiration, datetime):
                # Handle datetime objects directly
                cooldown_end = cooldown_expiration
                current_time = datetime.now(timezone.utc)
                
                self.logger.debug(f"calculate_wait_duration: cooldown_end (datetime) = {cooldown_end}")
                self.logger.debug(f"calculate_wait_duration: current_time = {current_time}")
                
                if current_time < cooldown_end:
                    remaining_seconds = (cooldown_end - current_time).total_seconds()
                    wait_duration = min(remaining_seconds, self.max_cooldown_wait)
                    self.logger.debug(f"calculate_wait_duration: remaining_seconds = {remaining_seconds:.1f}, wait_duration = {wait_duration:.1f}")
                    return wait_duration
                else:
                    # Cooldown has expired
                    self.logger.debug(f"calculate_wait_duration: Cooldown expired, returning 0.0")
                    return 0.0
            
            self.logger.debug(f"calculate_wait_duration: cooldown_expiration is neither string nor datetime, returning 0.0")
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating cooldown wait duration: {e}")
            return 0.0
    
    def should_refresh_character_state(self) -> bool:
        """
        Determine if character state should be refreshed based on caching configuration.
        
        Returns:
            True if state should be refreshed, False if cached state is still valid
        """
        current_time = time.time()
        time_since_refresh = current_time - self._last_character_refresh
        
        # Use configured cache duration instead of hardcoded value
        return time_since_refresh >= self.character_refresh_cache_duration
    
    def mark_character_state_refreshed(self) -> None:
        """Mark that character state has been refreshed."""
        self._last_character_refresh = time.time()
    
    def handle_cooldown_with_wait(self, character_state, action_executor, controller=None) -> bool:
        """
        Handle active cooldown by executing a wait action with calculated duration.
        
        Args:
            character_state: Character state object
            action_executor: Action executor for running wait action
            controller: Optional controller reference for building context
            
        Returns:
            True if cooldown was handled successfully, False otherwise
        """
        try:
            wait_duration = self.calculate_wait_duration(character_state)
            
            # If cooldown has expired based on timestamp, consider it successful without waiting
            if wait_duration <= 0.0:
                self.logger.info("✅ Cooldown has already expired - no wait needed")
                return True
            
            self.logger.info(f"🕐 Executing wait action for {wait_duration:.1f} seconds")
            
            # Execute wait action with calculated duration
            wait_action_data = {'wait_duration': wait_duration}
            
            # Build proper context with character state
            context = {
                'character_state': character_state,
                'wait_duration': wait_duration
            }
            
            # Include controller if provided
            if controller:
                context['controller'] = controller
            
            result = action_executor.execute_action('wait', wait_action_data, None, context)
            
            if result.success:
                self.logger.info(f"✅ Successfully waited {wait_duration:.1f} seconds for cooldown")
                return True
            else:
                self.logger.warning(f"❌ Wait action failed: {result.error_message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling cooldown with wait: {e}")
            return False