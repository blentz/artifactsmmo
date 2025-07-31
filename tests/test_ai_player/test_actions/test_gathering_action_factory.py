"""
Tests for Gathering Action Factory Implementation

This module tests the GatheringActionFactory for creating GatheringAction instances
with proper resource targeting and API client injection for gathering operations.
"""

from unittest.mock import Mock

from src.ai_player.actions.gathering_action import GatheringAction
from src.ai_player.actions.gathering_action_factory import GatheringActionFactory
from src.ai_player.state.character_game_state import CharacterGameState


class TestGatheringActionFactory:
    """Test GatheringActionFactory class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.factory = GatheringActionFactory()
        self.mock_character_state = Mock(spec=CharacterGameState)

    def test_get_action_type(self):
        """Test get_action_type returns GatheringAction"""
        action_type = self.factory.get_action_type()
        assert action_type == GatheringAction

    def test_create_instances_no_resources(self):
        """Test creating instances when no resources are available"""
        game_data = Mock()
        game_data.resources = None
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create a generic gathering action
        assert len(instances) == 1
        assert isinstance(instances[0], GatheringAction)
        assert instances[0].resource_type is None
        assert instances[0].api_client == game_data.api_client

    def test_create_instances_empty_resources(self):
        """Test creating instances when resources list is empty"""
        game_data = Mock()
        game_data.resources = []
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only a generic gathering action
        assert len(instances) == 1
        assert isinstance(instances[0], GatheringAction)
        assert instances[0].resource_type is None

    def test_create_instances_with_resources(self):
        """Test creating instances when resources are available"""
        mock_resource1 = Mock()
        mock_resource1.code = "copper_ore"
        mock_resource2 = Mock()
        mock_resource2.code = "ash_wood"

        game_data = Mock()
        game_data.resources = [mock_resource1, mock_resource2]
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create generic action plus specific resource actions
        assert len(instances) == 3
        assert all(isinstance(action, GatheringAction) for action in instances)
        assert all(action.api_client == game_data.api_client for action in instances)

        # First should be generic
        assert instances[0].resource_type is None

        # Rest should be resource-specific
        resource_types = [instances[1].resource_type, instances[2].resource_type]
        assert "copper_ore" in resource_types
        assert "ash_wood" in resource_types

    def test_create_instances_resources_without_code(self):
        """Test creating instances when resources don't have code attribute"""
        mock_resource = Mock()
        del mock_resource.code  # Remove code attribute

        game_data = Mock()
        game_data.resources = [mock_resource]
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only generic action (resource without code is skipped)
        assert len(instances) == 1
        assert isinstance(instances[0], GatheringAction)
        assert instances[0].resource_type is None

    def test_create_instances_no_resources_attribute(self):
        """Test creating instances when game_data has no resources attribute"""
        game_data = Mock()
        if hasattr(game_data, 'resources'):
            delattr(game_data, 'resources')
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only generic action
        assert len(instances) == 1
        assert isinstance(instances[0], GatheringAction)
        assert instances[0].resource_type is None

    def test_create_instances_no_api_client(self):
        """Test creating instances when game_data has no api_client"""
        game_data = Mock()
        game_data.resources = []
        if hasattr(game_data, 'api_client'):
            delattr(game_data, 'api_client')

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create action with None api_client
        assert len(instances) == 1
        assert instances[0].api_client is None

    def test_create_instances_none_game_data(self):
        """Test creating instances when game_data is None"""
        instances = self.factory.create_instances(None, self.mock_character_state)

        # Should create action with None api_client
        assert len(instances) == 1
        assert instances[0].api_client is None
        assert instances[0].resource_type is None

    def test_create_instances_mixed_resources(self):
        """Test creating instances with mix of valid and invalid resources"""
        mock_resource_valid = Mock()
        mock_resource_valid.code = "copper_ore"

        mock_resource_invalid = Mock()
        del mock_resource_invalid.code  # No code attribute

        game_data = Mock()
        game_data.resources = [mock_resource_valid, mock_resource_invalid]
        game_data.api_client = Mock()

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create generic action plus one valid resource action
        assert len(instances) == 2
        assert instances[0].resource_type is None
        assert instances[1].resource_type == "copper_ore"
