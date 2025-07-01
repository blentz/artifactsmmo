"""
Unified Action Context System

This module provides a unified context object that standardizes parameter passing
between actions, eliminating inconsistent context handling throughout the system.
"""

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union


@dataclass
class ActionContext:
    """
    Unified context object for action execution.
    
    Provides standardized access to all action execution dependencies and state,
    ensuring consistent parameter passing throughout the system.
    
    Implements dictionary interface for seamless integration with existing code.
    """
    
    # Core dependencies
    controller: Any = None
    client: Any = None
    character_state: Any = None
    world_state: Any = None
    map_state: Any = None
    knowledge_base: Any = None
    
    # Character information (using API-compatible names)
    character_name: str = ""
    character_x: int = 0
    character_y: int = 0
    character_level: int = 1
    character_hp: int = 0
    character_max_hp: int = 0
    
    # Equipment slots (dynamically populated from API)
    equipment: Dict[str, str] = field(default_factory=dict)
    
    # Action-specific parameters (flexible storage)
    action_data: Dict[str, Any] = field(default_factory=dict)
    
    # Action results and coordination data
    action_results: Dict[str, Any] = field(default_factory=dict)
    
    # Cached data for performance
    _cached_inventory: Optional[Dict[str, int]] = field(default=None, init=False)
    _logger: logging.Logger = field(default=None, init=False)
    
    def __post_init__(self):
        """Initialize logger and perform setup."""
        self._logger = logging.getLogger(__name__)
    
    @classmethod
    def from_controller(cls, controller, action_data: Dict[str, Any] = None) -> 'ActionContext':
        """
        Create ActionContext from controller state.
        
        Args:
            controller: AI controller instance
            action_data: Optional action-specific data
            
        Returns:
            Configured ActionContext instance
        """
        context = cls()
        
        # Set core dependencies
        context.controller = controller
        context.client = getattr(controller, 'client', None)
        context.character_state = getattr(controller, 'character_state', None)
        context.world_state = getattr(controller, 'world_state', None)
        context.map_state = getattr(controller, 'map_state', None)
        context.knowledge_base = getattr(controller, 'knowledge_base', None)
        
        # Extract character information using API-compatible names
        if context.character_state:
            if hasattr(context.character_state, 'name'):
                context.character_name = context.character_state.name
            if hasattr(context.character_state, 'data'):
                char_data = context.character_state.data
            else:
                char_data = {}
            
            context.character_x = char_data.get('x', 0)
            context.character_y = char_data.get('y', 0)
            context.character_level = char_data.get('level', 1)
            context.character_hp = char_data.get('hp', 0)
            context.character_max_hp = char_data.get('max_hp', 0)
            
            # Equipment is stored directly in character data with API names
            context.equipment = char_data
        
        # Include action context data from controller
        if hasattr(controller, 'action_context') and isinstance(controller.action_context, dict):
            context.action_results.update(controller.action_context)
        
        # Merge action-specific data
        if action_data:
            context.action_data.update(action_data)
            # Also extract params if present
            if 'params' in action_data:
                context.action_data.update(action_data['params'])
        
        return context
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get parameter from action_data with fallback to context attributes.
        
        Args:
            key: Parameter name
            default: Default value if not found
            
        Returns:
            Parameter value or default
        """
        # First check action_data
        if key in self.action_data:
            return self.action_data[key]
        
        # Then check action_results (from previous actions)
        if key in self.action_results:
            return self.action_results[key]
        
        # Finally check context attributes
        if hasattr(self, key):
            return getattr(self, key)
        
        return default
    
    def set_parameter(self, key: str, value: Any) -> None:
        """Set parameter in action_data."""
        self.action_data[key] = value
    
    def set_result(self, key: str, value: Any) -> None:
        """Set result data for use by subsequent actions."""
        self.action_results[key] = value
    
    def get_character_inventory(self, use_cache: bool = True) -> Dict[str, int]:
        """
        Get character inventory with caching for performance.
        
        Uses character state data instead of direct API calls.
        
        Args:
            use_cache: Whether to use cached inventory data
            
        Returns:
            Dictionary of item_code -> quantity
        """
        if use_cache and self._cached_inventory is not None:
            return self._cached_inventory
        
        inventory = {}
        
        if not self.character_state:
            return inventory
        
        try:
            char_data = self.character_state.data
            
            # Get inventory items
            inventory_items = char_data.get('inventory', [])
            for item in inventory_items:
                if isinstance(item, dict):
                    code = item.get('code')
                    quantity = item.get('quantity', 0)
                    if code and quantity > 0:
                        inventory[code] = quantity
            
            # Include equipped items dynamically
            for key, value in char_data.items():
                # If the value looks like an item code (non-empty string)
                # and isn't a known non-equipment field
                if (isinstance(value, str) and value and 
                    key not in ['name', 'skin', 'account', 'task', 'task_type']):
                    # This might be an equipped item
                    if value not in inventory:
                        inventory[value] = inventory.get(value, 0) + 1
            
            # Cache the result
            self._cached_inventory = inventory
            
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Could not get character inventory: {e}")
        
        return inventory
    
    def clear_inventory_cache(self) -> None:
        """Clear cached inventory data to force refresh on next access."""
        self._cached_inventory = None
    
    def get_equipped_item_in_slot(self, slot: str) -> Optional[str]:
        """
        Get item code equipped in specified slot.
        
        Args:
            slot: API slot name (e.g., 'weapon', 'shield')
            
        Returns:
            Item code or None if slot is empty
        """
        # Equipment is stored in the equipment dict (which is character data)
        if self.equipment and isinstance(self.equipment, dict):
            value = self.equipment.get(slot, '')
            return value if value else None
        return None
    
    def has_item(self, item_code: str, quantity: int = 1) -> bool:
        """
        Check if character has sufficient quantity of an item.
        
        Args:
            item_code: Item to check for
            quantity: Required quantity
            
        Returns:
            True if character has enough of the item
        """
        inventory = self.get_character_inventory()
        return inventory.get(item_code, 0) >= quantity
    
    def get_item_data(self, item_code: str) -> Optional[Dict]:
        """
        Get item data from knowledge base with API fallback.
        
        Args:
            item_code: Item code to look up
            
        Returns:
            Item data dictionary or None
        """
        if self.knowledge_base and hasattr(self.knowledge_base, 'get_item_data'):
            return self.knowledge_base.get_item_data(item_code, client=self.client)
        return None
    
    # Dictionary interface implementation
    
    def __getitem__(self, key: str) -> Any:
        """Get item using dictionary syntax."""
        value = self.get_parameter(key)
        if value is None and key not in self:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set item using dictionary syntax."""
        self.set_parameter(key, value)
    
    def __delitem__(self, key: str) -> None:
        """Delete item using dictionary syntax."""
        if key in self.action_data:
            del self.action_data[key]
        elif key in self.action_results:
            del self.action_results[key]
        else:
            raise KeyError(f"Key '{key}' not found")
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists using 'in' operator."""
        # Check action_data first
        if key in self.action_data:
            return True
        # Then check action_results
        if key in self.action_results:
            return True
        # Finally check if it's an attribute
        try:
            getattr(self, key)
            return True
        except AttributeError:
            return False
    
    def __iter__(self):
        """Iterate over keys."""
        # Yield from action_data
        yield from self.action_data
        # Yield from action_results (excluding duplicates)
        for key in self.action_results:
            if key not in self.action_data:
                yield key
        # Yield core attributes
        core_attrs = [
            'controller', 'client', 'character_state', 'world_state', 
            'map_state', 'knowledge_base', 'character_name', 'character_x',
            'character_y', 'character_level', 'character_hp', 'character_max_hp'
        ]
        for attr in core_attrs:
            if hasattr(self, attr) and attr not in self.action_data and attr not in self.action_results:
                yield attr
    
    def __len__(self) -> int:
        """Return number of keys."""
        return len(list(self.__iter__()))
    
    def keys(self):
        """Return keys view."""
        return list(self.__iter__())
    
    def values(self):
        """Return values view."""
        return [self[key] for key in self]
    
    def items(self):
        """Return items view."""
        return [(key, self[key]) for key in self]
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value with default."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def update(self, other: Union[Dict, 'ActionContext']) -> None:
        """Update from dictionary or another ActionContext."""
        if isinstance(other, ActionContext):
            # Update from another ActionContext
            self.action_data.update(other.action_data)
            self.action_results.update(other.action_results)
        elif isinstance(other, dict):
            # Update from dictionary
            for key, value in other.items():
                self[key] = value
    
    def copy(self) -> 'ActionContext':
        """Create a shallow copy."""
        return copy.copy(self)
    
    def pop(self, key: str, default: Any = None) -> Any:
        """Remove and return value."""
        try:
            value = self[key]
            del self[key]
            return value
        except KeyError:
            if default is not None:
                return default
            raise