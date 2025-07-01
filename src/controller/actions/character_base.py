"""
Base class for character-based actions

This module provides a base class for actions that operate on a specific character
but aren't necessarily movement-related.
"""

from typing import TYPE_CHECKING

from .base import ActionBase
from .mixins import CharacterDataMixin

if TYPE_CHECKING:
    from src.lib.action_context import ActionContext


class CharacterActionBase(ActionBase, CharacterDataMixin):
    """Base class for actions that operate on a specific character."""
    
    def __init__(self):
        """
        Initialize character action base.
        """
        super().__init__()
    
    def validate_execution_context(self, client, context: 'ActionContext') -> bool:
        """
        Validate that the action can be executed with the given context.
        Extends base validation to check for character name.
        
        Args:
            client: API client
            context: ActionContext with parameters
            
        Returns:
            True if context is valid, False otherwise
        """
        if not super().validate_execution_context(client, context):
            return False
            
        if not context or not context.character_name:
            self.logger.error("No character name provided")
            return False
            
        return True
    
    def __repr__(self):
        return f"{self.__class__.__name__}()"