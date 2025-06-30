"""
Base class for character-based actions

This module provides a base class for actions that operate on a specific character
but aren't necessarily movement-related.
"""

from typing import Dict, Optional, Any
from .base import ActionBase
from .mixins import CharacterDataMixin


class CharacterActionBase(ActionBase, CharacterDataMixin):
    """Base class for actions that operate on a specific character."""
    
    def __init__(self, character_name: str):
        """
        Initialize character action base.
        
        Args:
            character_name: Name of the character
        """
        super().__init__()
        self.character_name = character_name
    
    def validate_execution_context(self, client, **kwargs) -> bool:
        """
        Validate that the action can be executed with the given context.
        Extends base validation to check for character name.
        
        Args:
            client: API client
            **kwargs: Additional context
            
        Returns:
            True if context is valid, False otherwise
        """
        if not super().validate_execution_context(client, **kwargs):
            return False
            
        if not self.character_name:
            self.logger.error("No character name provided")
            return False
            
        return True
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.character_name})"