"""
Action Registry System with Dynamic Action Generation

This module provides automatic discovery and registration of all GOAP actions
through importlib, with support for dynamic generation of parameterized actions.
All action modules are discovered and validated to ensure they implement the
BaseAction interface and use GameState enum for type safety.

The registry enables the GOAP planner to access thousands of parameterized 
action instances generated dynamically based on game state and world data.
"""

from typing import Dict, List, Type, Any, Optional
from abc import ABC, abstractmethod
from .base_action import BaseAction
from ..state.game_state import GameState


class ActionFactory(ABC):
    """Abstract factory for generating parameterized action instances"""
    
    @abstractmethod
    def create_instances(self, game_data: Any, current_state: Dict[GameState, Any]) -> List[BaseAction]:
        """Generate all possible action instances for current game state.
        
        Parameters:
            game_data: Complete game data including maps, items, monsters, resources
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            List of BaseAction instances generated for current conditions
            
        This method generates all valid action instances that can be executed
        in the current game state, enabling dynamic GOAP planning with
        context-aware action availability.
        """
        pass
    
    @abstractmethod
    def get_action_type(self) -> Type[BaseAction]:
        """Return the action class this factory creates.
        
        Parameters:
            None
            
        Return values:
            Type object representing the BaseAction subclass this factory produces
            
        This method identifies the specific action type that this factory
        generates, enabling the registry to organize and categorize actions
        for efficient GOAP planning and execution.
        """
        pass


class ActionRegistry:
    """Registry for automatic action discovery and dynamic generation"""
    
    def __init__(self):
        """Initialize ActionRegistry with automatic action discovery.
        
        Parameters:
            None
            
        Return values:
            None (constructor)
            
        This constructor initializes the action registry system with automatic
        discovery of all action modules, factory registration, and validation
        of BaseAction interface compliance for type-safe GOAP integration.
        """
        pass
    
    def discover_actions(self) -> Dict[str, Type[BaseAction]]:
        """Auto-discover all action modules and validate BaseAction interface.
        
        Parameters:
            None
            
        Return values:
            Dictionary mapping action names to validated BaseAction subclasses
            
        This method uses importlib to automatically discover all action modules
        in the actions package, validates their BaseAction interface compliance,
        and ensures proper GameState enum usage for type-safe integration.
        """
        pass
    
    def register_factory(self, factory: ActionFactory) -> None:
        """Register an action factory for dynamic instance generation.
        
        Parameters:
            factory: ActionFactory instance for generating parameterized actions
            
        Return values:
            None (modifies internal registry)
            
        This method registers an action factory that can generate multiple
        parameterized instances of a specific action type, enabling dynamic
        action creation based on current game state and world conditions.
        """
        pass
    
    def generate_actions_for_state(self, current_state: Dict[GameState, Any], game_data: Any) -> List[BaseAction]:
        """Generate all possible action instances for current game state.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            game_data: Complete game data for parameterized action generation
            
        Return values:
            List of all available BaseAction instances for GOAP planning
            
        This method coordinates all registered factories to generate the complete
        set of available actions for the current state, providing the GOAP
        planner with dynamic action availability for optimal planning.
        """
        pass
    
    def get_all_action_types(self) -> List[Type[BaseAction]]:
        """Get all registered action classes.
        
        Parameters:
            None
            
        Return values:
            List of all BaseAction subclass types in the registry
            
        This method returns all discovered and validated action classes,
        enabling analysis of available action types for debugging, validation,
        and system introspection within the AI player architecture.
        """
        pass
    
    def validate_action(self, action_class: Type[BaseAction]) -> bool:
        """Ensure action uses GameState enum in preconditions/effects.
        
        Parameters:
            action_class: BaseAction subclass to validate for enum compliance
            
        Return values:
            Boolean indicating whether action properly uses GameState enum
            
        This method validates that an action class properly implements the
        BaseAction interface and uses GameState enum keys in all state
        references, ensuring type safety throughout the GOAP system.
        """
        pass
    
    def get_action_by_name(self, name: str, current_state: Dict[GameState, Any], game_data: Any) -> Optional[BaseAction]:
        """Get specific action instance by name, generating if needed.
        
        Parameters:
            name: Unique action name identifier
            current_state: Dictionary with GameState enum keys and current values
            game_data: Complete game data for parameterized action generation
            
        Return values:
            BaseAction instance matching the name, or None if not found
            
        This method retrieves a specific action instance by name, using
        factories to generate parameterized instances as needed for GOAP
        execution and action debugging workflows.
        """
        pass


class ParameterizedActionFactory(ActionFactory):
    """Base factory for actions requiring parameters (locations, targets, etc.)"""
    
    def __init__(self, action_class: Type[BaseAction]):
        self.action_class = action_class
    
    def get_action_type(self) -> Type[BaseAction]:
        return self.action_class
    
    @abstractmethod
    def generate_parameters(self, game_data: Any, current_state: Dict[GameState, Any]) -> List[Dict[str, Any]]:
        """Generate all valid parameter combinations for this action type.
        
        Parameters:
            game_data: Complete game data including maps, items, monsters, resources
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            List of parameter dictionaries for action instance creation
            
        This method analyzes the current game state and available data to
        generate all valid parameter combinations for creating instances
        of the parameterized action type.
        """
        pass
    
    def create_instances(self, game_data: Any, current_state: Dict[GameState, Any]) -> List[BaseAction]:
        """Create action instances for all valid parameter combinations"""
        instances = []
        for params in self.generate_parameters(game_data, current_state):
            instances.append(self.action_class(**params))
        return instances


def get_all_actions(current_state: Dict[GameState, Any], game_data: Any) -> List[BaseAction]:
    """Global function to get all available action instances for GOAP system.
    
    Parameters:
        current_state: Dictionary with GameState enum keys and current values
        game_data: Complete game data for action generation
        
    Return values:
        List of all available BaseAction instances for GOAP planning
        
    This function provides the main entry point for the GOAP planner to
    obtain all available actions for the current state, coordinating
    the action registry and factory system for dynamic action generation.
    """
    pass


def register_action_factory(factory: ActionFactory) -> None:
    """Register a new action factory with the registry.
    
    Parameters:
        factory: ActionFactory instance to add to the global registry
        
    Return values:
        None (modifies global registry)
        
    This function registers a new action factory with the global registry,
    enabling automatic discovery and generation of parameterized actions
    for the GOAP planning system.
    """
    pass