"""Unit tests for CharacterActionBase class."""

import unittest
from typing import Dict, Optional
from unittest.mock import Mock

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.base.character import CharacterActionBase
from src.controller.actions.base import ActionResult

from test.fixtures import MockActionContext


class TestCharacterImplementation(CharacterActionBase):
    """Test implementation of CharacterActionBase."""
    
    def __init__(self, return_data: Dict = None):
        """Initialize with optional return data for testing."""
        super().__init__()
        self.return_data = return_data or {}
    
    def execute(self, client, context) -> ActionResult:
        """Simple implementation for testing."""
        self._context = context
        return self.create_success_result(
            "Test action executed",
            test_action_executed=True,
            character_name=context.character_name,
            **self.return_data
        )


class TestCharacterActionBase(unittest.TestCase):
    """Test cases for CharacterActionBase class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.char_name = "test_character"
        self.action = TestCharacterImplementation()
        self.client = Mock(spec=AuthenticatedClient)
        self.context = MockActionContext(character_name=self.char_name)
    
    
    
    def test_multiple_character_actions(self):
        """Test creating multiple character actions with different names."""
        action1 = TestCharacterImplementation()
        action2 = TestCharacterImplementation()
        
        # Actions no longer store character names
        # They would get character names from context during execution
        self.assertIsInstance(action1, CharacterActionBase)
        self.assertIsInstance(action2, CharacterActionBase)
    
    def test_repr(self):
        """Test string representation of CharacterActionBase."""
        action = TestCharacterImplementation()
        repr_str = repr(action)
        self.assertEqual(repr_str, "TestCharacterImplementation()")


if __name__ == '__main__':
    unittest.main()