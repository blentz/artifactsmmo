"""
Mixins for action functionality.

This module provides mixins that are shared across multiple actions.
These are not actions themselves, but provide common functionality.
"""

# Import all mixins for easy access
from .mixins import KnowledgeBaseSearchMixin, MapStateAccessMixin
from .coordinate_mixin import CoordinateStandardizationMixin
from .subgoal_mixins import MovementSubgoalMixin, WorkflowSubgoalMixin

# Note: CharacterDataMixin removed for architecture compliance
# Actions should read character data from UnifiedStateContext instead of making direct API calls

__all__ = [
    'KnowledgeBaseSearchMixin',
    'MapStateAccessMixin',
    'CoordinateStandardizationMixin', 
    'MovementSubgoalMixin',
    'WorkflowSubgoalMixin'
]