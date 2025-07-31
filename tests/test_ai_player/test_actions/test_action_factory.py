"""
Tests for Action Factory Abstract Base Class

This module tests the ActionFactory abstract base class for generating
parameterized action instances in the GOAP system.
"""

import pytest
from abc import ABC

from src.ai_player.actions.action_factory import ActionFactory
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.state.character_game_state import CharacterGameState


class TestActionFactory:
    """Test ActionFactory abstract base class"""
    
    def test_action_factory_is_abstract(self):
        """Test that ActionFactory cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ActionFactory()
    
    def test_action_factory_inheritance(self):
        """Test that ActionFactory inherits from ABC"""
        assert issubclass(ActionFactory, ABC)
    
    def test_create_instances_method_is_abstract(self):
        """Test that create_instances method is abstract"""
        # Try to create a class that doesn't implement create_instances
        class IncompleteFactory(ActionFactory):
            def get_action_type(self):
                return BaseAction
        
        with pytest.raises(TypeError):
            IncompleteFactory()
    
    def test_get_action_type_method_is_abstract(self):
        """Test that get_action_type method is abstract"""
        # Try to create a class that doesn't implement get_action_type
        class IncompleteFactory(ActionFactory):
            def create_instances(self, game_data, current_state):
                return []
        
        with pytest.raises(TypeError):
            IncompleteFactory()
    
    def test_concrete_implementation_works(self):
        """Test that a complete concrete implementation can be instantiated"""
        class ConcreteFactory(ActionFactory):
            def create_instances(self, game_data, current_state):
                return []
            
            def get_action_type(self):
                return BaseAction
        
        # Should not raise exception
        factory = ConcreteFactory()
        assert isinstance(factory, ActionFactory)
        assert factory.get_action_type() == BaseAction
        assert factory.create_instances(None, None) == []