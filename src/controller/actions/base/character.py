"""
Base class for character-based actions

This module provides a base class for actions that operate on a specific character
but aren't necessarily movement-related.
"""


from . import ActionBase
class CharacterActionBase(ActionBase):
    """Base class for actions that operate on a specific character."""
    
    def __init__(self):
        """
        Initialize character action base.
        """
        super().__init__()
    
    def __repr__(self):
        return f"{self.__class__.__name__}()"
