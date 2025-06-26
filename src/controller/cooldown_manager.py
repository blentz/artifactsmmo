"""
Cooldown Management System

This module provides YAML-configurable cooldown detection and handling,
replacing hardcoded cooldown logic in the AI controller.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.lib.yaml_data import YamlData
from src.game.globals import DATA_PREFIX


class CooldownManager:
    """
    YAML-configurable cooldown management system.
    
    Handles cooldown detection, waiting, and character state refresh
    using configuration-driven thresholds and behavior.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize cooldown manager with configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        if config_file is None:
            config_file = f"{DATA_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
        # Character state refresh tracking
        self._last_character_refresh = 0
        
    def _load_configuration(self) -> None:
        """Load cooldown configuration from YAML."""
        try:
            thresholds = self.config_data.data.get('thresholds', {})
            
            # Load cooldown thresholds with defaults
            self.cooldown_detection_threshold = thresholds.get('cooldown_detection_threshold', 0.5)
            self.max_cooldown_wait = thresholds.get('max_cooldown_wait', 65)
            self.min_cooldown_wait = thresholds.get('min_cooldown_wait', 0.5)
            self.character_refresh_cache_duration = thresholds.get('character_refresh_cache_duration', 5.0)
            
            self.logger.debug(f"Loaded cooldown configuration: detection_threshold={self.cooldown_detection_threshold}, "
                            f"max_wait={self.max_cooldown_wait}, min_wait={self.min_cooldown_wait}")
            
        except Exception as e:
            self.logger.error(f"Failed to load cooldown configuration: {e}")
            # Use hardcoded defaults as fallback
            self.cooldown_detection_threshold = 0.5
            self.max_cooldown_wait = 65
            self.min_cooldown_wait = 0.5
            self.character_refresh_cache_duration = 5.0
    
    def is_character_on_cooldown(self, character_state) -> bool:
        """
        Check if character is currently on cooldown using configuration-driven thresholds.
        
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
            
            if cooldown_expiration:
                if isinstance(cooldown_expiration, str):
                    cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
                    current_time = datetime.now(timezone.utc)
                    
                    if current_time < cooldown_end:
                        remaining = (cooldown_end - current_time).total_seconds()
                        # Use configured threshold instead of hardcoded value
                        if remaining > self.cooldown_detection_threshold:
                            return True
                    else:
                        # Cooldown has expired - ignore legacy cooldown field
                        return False
            
            # Only check legacy cooldown field if no expiration time is available
            if cooldown_expiration is None:
                cooldown = char_data.get('cooldown', 0)
                return cooldown > self.cooldown_detection_threshold
            
            # If we have expiration time but it's expired, cooldown is not active
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking cooldown status: {e}")
            return False
    
    def calculate_wait_duration(self, character_state) -> float:
        """
        Calculate optimal wait duration based on cooldown and configuration.
        
        Args:
            character_state: Character state object
            
        Returns:
            Wait duration in seconds (0.0 if no wait needed)
        """
        if not character_state:
            return 0.0
            
        try:
            char_data = character_state.data
            cooldown_expiration = char_data.get('cooldown_expiration')
            wait_duration = self.min_cooldown_wait  # Default wait time
            
            if cooldown_expiration:
                try:
                    if isinstance(cooldown_expiration, str):
                        cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
                        current_time = datetime.now(timezone.utc)
                        if current_time < cooldown_end:
                            remaining_seconds = (cooldown_end - current_time).total_seconds()
                            # Wait for the remaining time, using configured bounds
                            wait_duration = max(self.min_cooldown_wait, min(remaining_seconds, self.max_cooldown_wait))
                        else:
                            # Cooldown has expired, no need to wait
                            wait_duration = 0.0
                except Exception as e:
                    self.logger.warning(f"Error calculating wait duration: {e}")
                    wait_duration = min(char_data.get('cooldown', 1), self.max_cooldown_wait)
            
            return wait_duration
            
        except Exception as e:
            self.logger.error(f"Error calculating cooldown wait duration: {e}")
            return self.min_cooldown_wait
    
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
    
    def handle_cooldown_with_wait(self, character_state, action_executor) -> bool:
        """
        Handle active cooldown by executing a wait action with calculated duration.
        
        Args:
            character_state: Character state object
            action_executor: Action executor for running wait action
            
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
            result = action_executor.execute_action('wait', wait_action_data, None, {})
            
            if result.success:
                self.logger.info(f"✅ Successfully waited {wait_duration:.1f} seconds for cooldown")
                return True
            else:
                self.logger.warning(f"❌ Wait action failed: {result.error_message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling cooldown with wait: {e}")
            return False