"""
Unified State Context - Clean Implementation

Single source of truth for all application state using flat storage
with dotted parameter names. No backward compatibility.

Design Principles Applied:
- Single Responsibility: Manages application state only
- Open/Closed: Extensible through StateParameters registry
- Dependency Inversion: Depends on StateParameters abstraction
- KISS: Simple flat storage with validation
- DRY: No duplicate state storage mechanisms
"""

import logging
from typing import Any, Dict, Optional, Set
from src.lib.state_parameters import StateParameters


# Singleton instance storage
_unified_instance = None


class UnifiedStateContext:
    """
    Unified state management for entire application lifecycle.
    
    Provides single source of truth for all state using flat storage
    with dotted parameter names from StateParameters registry.
    
    Key Features:
    - Flat storage eliminates sync issues
    - Parameter validation prevents typos
    - Dotted names preserve semantic meaning
    - Singleton ensures consistency across application
    
    Risk Mitigation:
    - All parameter access validated against registry
    - Type hints and documentation for clarity
    - Comprehensive logging for debugging
    """
    
    def __init__(self):
        """Initialize with empty state and logger."""
        # Only initialize once (for singleton)
        if not hasattr(self, '_initialized'):
            self._state: Dict[str, Any] = {}
            self._logger = logging.getLogger(__name__)
            self._valid_parameters = StateParameters.get_all_parameters()
            
            # Initialize with default values for critical parameters
            self._initialize_defaults()
            
            # Mark as initialized
            self._initialized = True
    
    def __new__(cls):
        """Ensure only one instance exists (Singleton pattern)."""
        global _unified_instance
        if _unified_instance is None:
            _unified_instance = super().__new__(cls)
        return _unified_instance
    
    def _initialize_defaults(self) -> None:
        """Initialize critical parameters with safe defaults."""
        defaults = {
            StateParameters.CHARACTER_ALIVE: True,
            StateParameters.CHARACTER_LEVEL: 1,
            StateParameters.CHARACTER_HP: 0,
            StateParameters.CHARACTER_MAX_HP: 0,
            StateParameters.CHARACTER_PREVIOUS_HP: 0,
            StateParameters.CHARACTER_COOLDOWN_ACTIVE: False,
            StateParameters.CHARACTER_SAFE: True,
            StateParameters.CHARACTER_XP_PERCENTAGE: 0.0,
            StateParameters.CHARACTER_NAME: "",
            StateParameters.CHARACTER_X: 0,
            StateParameters.CHARACTER_Y: 0,
            
            # Target item parameters
            StateParameters.TARGET_ITEM: None,
            StateParameters.TARGET_SLOT: None,
            StateParameters.TARGET_RECIPE: None,
            
            # Equipment parameters
            StateParameters.EQUIPMENT_UPGRADE_STATUS: "needs_analysis",
            StateParameters.EQUIPMENT_GAPS_ANALYZED: False,
            StateParameters.EQUIPMENT_ITEM_CRAFTED: False,
            StateParameters.EQUIPMENT_EQUIPPED: False,
            StateParameters.MATERIALS_STATUS: "unknown",
            StateParameters.MATERIALS_GATHERED: False,
            StateParameters.COMBAT_STATUS: "idle",
            StateParameters.COMBAT_RECENT_WIN_RATE: 1.0,
            StateParameters.COMBAT_LOW_WIN_RATE: False,
            StateParameters.COMBAT_PRE_COMBAT_HP: 0,
            StateParameters.GOAL_PHASE: "planning",
            StateParameters.GOAL_STEPS_COMPLETED: 0,
            StateParameters.GOAL_TOTAL_STEPS: 0,
            StateParameters.GOAL_MONSTERS_HUNTED: 0,
            StateParameters.RESOURCE_AVAILABILITY_MONSTERS: False,
            StateParameters.RESOURCE_AVAILABILITY_RESOURCES: False,
            StateParameters.SKILL_REQUIREMENTS_VERIFIED: False,
            StateParameters.SKILL_REQUIREMENTS_SUFFICIENT: False,
            StateParameters.SKILL_STATUS_CHECKED: False,
            StateParameters.SKILL_STATUS_SUFFICIENT: False,
            StateParameters.SKILLS_DEFAULT_LEVEL: 1,
            StateParameters.SKILLS_DEFAULT_REQUIRED: 0,
            StateParameters.SKILLS_DEFAULT_XP: 0,
            StateParameters.WORKSHOP_DISCOVERED: False,
            StateParameters.WORKSHOP_LOCATIONS: {},
            StateParameters.INVENTORY_UPDATED: False,
            StateParameters.HEALING_NEEDED: False,
            StateParameters.HEALING_STATUS: "idle",
            StateParameters.WORKFLOW_STEP: "initial",
            
            # Action configuration defaults (flattened)
            StateParameters.ACTION_MAX_WEAPONS_TO_EVALUATE: 50,
            StateParameters.ACTION_MAX_WEAPON_LEVEL_ABOVE_CHARACTER: 1,
            StateParameters.ACTION_MAX_WEAPON_LEVEL_BELOW_CHARACTER: 1,
            StateParameters.ACTION_WEAPON_STAT_WEIGHTS: {},
            StateParameters.ACTION_CRAFTABILITY_SCORING: {},
            StateParameters.ACTION_MAX_SKILL_CHECK_WEAPON_LEVEL: 0,  # Will be set to character_level + 5
            StateParameters.ACTION_MAX_SKILL_BLOCKED_CHECKS: 20,
            StateParameters.ACTION_BASIC_WEAPON_CODES: [],
            StateParameters.ACTION_MAX_BASIC_WEAPON_LEVEL: 5,
        }
        
        for param, value in defaults.items():
            self._state[param] = value
    
    def get(self, param: str, default: Any = None) -> Any:
        """
        Get parameter value with validation.
        
        Args:
            param: Parameter name from StateParameters registry
            default: Default value if parameter not set
            
        Returns:
            Parameter value or default
            
        Raises:
            ValueError: If parameter not in registry
        """
        if param not in self._valid_parameters:
            raise ValueError(f"Parameter '{param}' not registered in StateParameters")
        
        return self._state.get(param, default)
    
    def set(self, param: str, value: Any) -> None:
        """
        Set parameter value with validation.
        
        Args:
            param: Parameter name from StateParameters registry
            value: Value to set
            
        Raises:
            ValueError: If parameter not in registry
        """
        if param not in self._valid_parameters:
            raise ValueError(f"Parameter '{param}' not registered in StateParameters")
        
        old_value = self._state.get(param)
        self._state[param] = value
        
        # Log significant state changes for debugging
        if old_value != value:
            self._logger.debug(f"State changed: {param} = {value} (was {old_value})")
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple parameters at once.
        
        Args:
            updates: Dictionary of parameter -> value mappings
            
        Raises:
            ValueError: If any parameter not in registry
        """
        # Validate all parameters first
        for param in updates.keys():
            if param not in self._valid_parameters:
                raise ValueError(f"Parameter '{param}' not registered in StateParameters")
        
        # Apply all updates
        for param, value in updates.items():
            self.set(param, value)
    
    def load_from_flat_dict(self, flat_data: Dict[str, Any]) -> None:
        """
        Load state from flat dictionary with dotted keys.
        
        Args:
            flat_data: Dictionary with dotted parameter keys
        """
        valid_data = {}
        invalid_keys = []
        
        for key, value in flat_data.items():
            if key in self._valid_parameters:
                valid_data[key] = value
            else:
                invalid_keys.append(key)
        
        if invalid_keys:
            self._logger.warning(f"Ignored invalid parameters: {invalid_keys}")
        
        self._state.update(valid_data)
        self._logger.info(f"Loaded {len(valid_data)} parameters from flat data")
    
    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Export state to flat dictionary format.
        
        Returns:
            Dictionary with dotted parameter keys
        """
        return self._state.copy()
    
    def get_all_parameters(self) -> Dict[str, Any]:
        """
        Get all parameters from unified state context.
        
        Returns:
            Dictionary with all current parameter values
        """
        return self._state.copy()
    
    def reset(self) -> None:
        """Reset state to defaults (useful for testing)."""
        self._state.clear()
        self._initialize_defaults()
        self._logger.info("State reset to defaults")
    
    def get_parameters_by_category(self, category: str) -> Dict[str, Any]:
        """
        Get all parameters for a specific category.
        
        Args:
            category: Category prefix (e.g., 'equipment_status')
            
        Returns:
            Dictionary of parameters matching the category
        """
        return {
            param: value for param, value in self._state.items()
            if param.startswith(f"{category}.")
        }
    
    def has_parameter(self, param: str) -> bool:
        """
        Check if parameter exists in state.
        
        Args:
            param: Parameter name to check
            
        Returns:
            True if parameter exists and has been set
        """
        return param in self._state
    
    def __getitem__(self, param: str) -> Any:
        """Dictionary-style access for getting parameters."""
        return self.get(param)
    
    def __setitem__(self, param: str, value: Any) -> None:
        """Dictionary-style access for setting parameters."""
        self.set(param, value)
    
    def __contains__(self, param: str) -> bool:
        """Support 'in' operator for parameter existence checks."""
        return self.has_parameter(param)
    
    def keys(self):
        """Return all parameter keys."""
        return self._state.keys()
    
    def values(self):
        """Return all parameter values."""
        return self._state.values()
    
    def items(self):
        """Return all parameter key-value pairs."""
        return self._state.items()
    
    def update_from_context(self, character_state=None, map_state=None, knowledge_base=None) -> None:
        """
        Update unified state directly from external context sources.
        
        This eliminates the need for separate world state creation/merging
        by updating the single source of truth directly.
        
        Args:
            character_state: Character state to extract data from
            map_state: Map state to extract data from
            knowledge_base: Knowledge base to extract data from
        """
        try:
            # Update character parameters directly
            if character_state and hasattr(character_state, 'data'):
                char_data = character_state.data
                self.update({
                    StateParameters.CHARACTER_LEVEL: char_data.get('level', 1),
                    StateParameters.CHARACTER_HP: char_data.get('hp', 0),
                    StateParameters.CHARACTER_MAX_HP: char_data.get('max_hp', 0),
                    StateParameters.CHARACTER_X: char_data.get('x', 0),
                    StateParameters.CHARACTER_Y: char_data.get('y', 0),
                    StateParameters.CHARACTER_ALIVE: char_data.get('hp', 0) > 0,
                    StateParameters.CHARACTER_SAFE: char_data.get('hp', 0) > (char_data.get('max_hp', 0) * 0.2),
                    StateParameters.CHARACTER_COOLDOWN_ACTIVE: char_data.get('cooldown_expiry', 0) > 0,
                })
            
            # Update map parameters directly
            if map_state and hasattr(map_state, 'data'):
                map_data = map_state.data
                self.update({
                    StateParameters.RESOURCE_AVAILABILITY_MONSTERS: len(map_data.get('monsters', [])) > 0,
                    StateParameters.RESOURCE_AVAILABILITY_RESOURCES: len(map_data.get('resources', [])) > 0,
                    StateParameters.WORKSHOP_LOCATIONS: map_data.get('workshops', {}),
                    StateParameters.WORKSHOP_DISCOVERED: len(map_data.get('workshops', {})) > 0,
                })
            
            # Update knowledge base parameters directly
            if knowledge_base and hasattr(knowledge_base, 'data'):
                kb_data = knowledge_base.data
                self.update({
                    StateParameters.MATERIALS_REQUIRED: kb_data.get('required_materials', {}),
                })
            
            # Ensure critical state is updated
            self.set(StateParameters.INVENTORY_UPDATED, True)
            
            self._logger.debug("Updated unified state from external context")
            
        except Exception as e:
            self._logger.error(f"Failed to update from context: {e}")


# Convenience function for getting the singleton instance
def get_unified_context() -> UnifiedStateContext:
    """Get the singleton UnifiedStateContext instance."""
    return UnifiedStateContext()