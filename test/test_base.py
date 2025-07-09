"""
Base test class for all tests that use ActionContext or UnifiedStateContext.

This ensures proper cleanup of singleton state between tests to prevent
test pollution.
"""

import unittest
from src.lib.unified_state_context import UnifiedStateContext
from src.lib.action_context import ActionContext


class UnifiedContextTestBase(unittest.TestCase):
    """
    Base test class that properly manages UnifiedStateContext singleton.
    
    All test classes that use ActionContext or UnifiedStateContext should
    inherit from this class to ensure proper state isolation between tests.
    """
    
    
    def setUp(self):
        """Reset the singleton state before each test."""
        super().setUp()
        # Get the singleton instance and reset it
        self.unified_state = UnifiedStateContext()
        self.unified_state.reset()
        
        # Create a fresh ActionContext that uses the reset state
        self.context = ActionContext()
        
    def tearDown(self):
        """Clean up after each test."""
        # Reset the singleton state again to ensure no pollution
        if hasattr(self, 'unified_state'):
            self.unified_state.reset()
            
        super().tearDown()
            
    def create_action_context(self, **kwargs):
        """
        Helper method to create an ActionContext with given attributes.
        
        Since ActionContext is a singleton wrapper, this ensures we're
        working with the reset state and sets any initial values needed.
        
        Args:
            **kwargs: Attributes to set on the context
            
        Returns:
            ActionContext instance with attributes set
        """
        context = ActionContext()
        for key, value in kwargs.items():
            setattr(context, key, value)
        return context