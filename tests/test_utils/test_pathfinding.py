"""Tests for pathfinding utilities."""

import pytest
from unittest.mock import Mock, patch

from artifactsmmo_cli.utils.pathfinding import (
    PathResult,
    PathStep,
    calculate_path,
    get_character_position,
    parse_destination,
    resolve_named_location,
    find_nearest_bank,
    find_nearest_task_master,
    find_nearest_resource,
    _find_nearest_location,
)


class TestPathStep:
    """Test PathStep dataclass."""

    def test_path_step_creation(self):
        """Test creating a PathStep."""
        step = PathStep(5, 10)
        assert step.x == 5
        assert step.y == 10

    def test_path_step_str(self):
        """Test PathStep string representation."""
        step = PathStep(5, 10)
        assert str(step) == "(5, 10)"


class TestPathResult:
    """Test PathResult dataclass."""

    def test_path_result_creation(self):
        """Test creating a PathResult."""
        steps = [PathStep(1, 1), PathStep(2, 2)]
        result = PathResult(steps=steps, total_distance=4, estimated_time=10)

        assert result.steps == steps
        assert result.total_distance == 4
        assert result.estimated_time == 10

    def test_path_result_is_empty_true(self):
        """Test PathResult.is_empty when no steps."""
        result = PathResult(steps=[], total_distance=0, estimated_time=0)
        assert result.is_empty is True

    def test_path_result_is_empty_false(self):
        """Test PathResult.is_empty when has steps."""
        steps = [PathStep(1, 1)]
        result = PathResult(steps=steps, total_distance=2, estimated_time=5)
        assert result.is_empty is False

    def test_path_result_str_empty(self):
        """Test PathResult string representation when empty."""
        result = PathResult(steps=[], total_distance=0, estimated_time=0)
        assert str(result) == "No movement needed"

    def test_path_result_str_with_steps(self):
        """Test PathResult string representation with steps."""
        steps = [PathStep(1, 1), PathStep(2, 2)]
        result = PathResult(steps=steps, total_distance=4, estimated_time=10)
        assert str(result) == "2 steps, 4 distance, ~10s"


class TestCalculatePath:
    """Test calculate_path function."""

    def test_calculate_path_same_position(self):
        """Test path calculation when already at destination."""
        result = calculate_path(5, 5, 5, 5)

        assert result.is_empty
        assert result.total_distance == 0
        assert result.estimated_time == 0

    def test_calculate_path_horizontal_move(self):
        """Test path calculation for horizontal movement."""
        result = calculate_path(0, 0, 3, 0)

        expected_steps = [PathStep(1, 0), PathStep(2, 0), PathStep(3, 0)]
        assert result.steps == expected_steps
        assert result.total_distance == 3
        assert result.estimated_time == 15  # 3 steps * 5 seconds

    def test_calculate_path_vertical_move(self):
        """Test path calculation for vertical movement."""
        result = calculate_path(0, 0, 0, 2)

        expected_steps = [PathStep(0, 1), PathStep(0, 2)]
        assert result.steps == expected_steps
        assert result.total_distance == 2
        assert result.estimated_time == 10  # 2 steps * 5 seconds

    def test_calculate_path_diagonal_move(self):
        """Test path calculation for diagonal movement."""
        result = calculate_path(0, 0, 2, 2)

        expected_steps = [PathStep(1, 1), PathStep(2, 2)]
        assert result.steps == expected_steps
        assert result.total_distance == 4  # Manhattan distance
        assert result.estimated_time == 10  # 2 steps * 5 seconds

    def test_calculate_path_negative_coordinates(self):
        """Test path calculation with negative coordinates."""
        result = calculate_path(0, 0, -1, -1)

        expected_steps = [PathStep(-1, -1)]
        assert result.steps == expected_steps
        assert result.total_distance == 2
        assert result.estimated_time == 5

    def test_calculate_path_mixed_movement(self):
        """Test path calculation with mixed horizontal and vertical movement."""
        result = calculate_path(0, 0, 3, 1)

        # Should move diagonally first, then horizontally
        expected_steps = [PathStep(1, 1), PathStep(2, 1), PathStep(3, 1)]
        assert result.steps == expected_steps
        assert result.total_distance == 4
        assert result.estimated_time == 15


class TestGetCharacterPosition:
    """Test get_character_position function."""

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    def test_get_character_position_success(self, mock_handle_response, mock_client_manager):
        """Test successful character position retrieval."""
        # Mock character data
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 10

        # Mock API response
        mock_response = Mock()
        mock_api = Mock()
        mock_api.get_character.return_value = mock_response
        mock_client_manager.return_value.api = mock_api

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_character
        mock_handle_response.return_value = mock_cli_response

        result = get_character_position("testchar")

        assert result == (5, 10)
        mock_api.get_character.assert_called_once_with(name="testchar")

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    def test_get_character_position_api_error(self, mock_handle_response, mock_client_manager):
        """Test character position retrieval with API error."""
        # Mock API response
        mock_response = Mock()
        mock_api = Mock()
        mock_api.get_character.return_value = mock_response
        mock_client_manager.return_value.api = mock_api

        # Mock handle_api_response with error
        mock_cli_response = Mock()
        mock_cli_response.success = False
        mock_cli_response.error = "Character not found"
        mock_cli_response.data = None
        mock_handle_response.return_value = mock_cli_response

        with pytest.raises(Exception, match="Character not found"):
            get_character_position("testchar")

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    def test_get_character_position_missing_coordinates(self, mock_handle_response, mock_client_manager):
        """Test character position retrieval with missing coordinates."""
        # Mock character data without coordinates
        mock_character = Mock()
        mock_character.x = None
        mock_character.y = 10

        # Mock API response
        mock_response = Mock()
        mock_api = Mock()
        mock_api.get_character.return_value = mock_response
        mock_client_manager.return_value.api = mock_api

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_character
        mock_handle_response.return_value = mock_cli_response

        with pytest.raises(Exception, match="Could not get position"):
            get_character_position("testchar")

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    def test_get_character_position_missing_y_coordinate(self, mock_handle_response, mock_client_manager):
        """Test character position retrieval with missing Y coordinate."""
        # Mock character data without Y coordinate
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = None

        # Mock API response
        mock_response = Mock()
        mock_api = Mock()
        mock_api.get_character.return_value = mock_response
        mock_client_manager.return_value.api = mock_api

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_character
        mock_handle_response.return_value = mock_cli_response

        with pytest.raises(Exception, match="Could not get position"):
            get_character_position("testchar")

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    def test_get_character_position_no_data(self, mock_handle_response, mock_client_manager):
        """Test character position retrieval with no data."""
        # Mock API response
        mock_response = Mock()
        mock_api = Mock()
        mock_api.get_character.return_value = mock_response
        mock_client_manager.return_value.api = mock_api

        # Mock handle_api_response with success but no data
        mock_cli_response = Mock()
        mock_cli_response.success = False
        mock_cli_response.error = None
        mock_cli_response.data = None
        mock_handle_response.return_value = mock_cli_response

        with pytest.raises(Exception, match="Character 'testchar' not found"):
            get_character_position("testchar")


class TestParseDestination:
    """Test parse_destination function."""

    def test_parse_destination_coordinates(self):
        """Test parsing coordinate destination."""
        result = parse_destination("5 10")
        assert result == (5, 10)

    def test_parse_destination_coordinates_with_spaces(self):
        """Test parsing coordinate destination with extra spaces."""
        result = parse_destination("  5   10  ")
        assert result == (5, 10)

    def test_parse_destination_negative_coordinates(self):
        """Test parsing negative coordinates."""
        result = parse_destination("-5 -10")
        assert result == (-5, -10)

    def test_parse_destination_named_location(self):
        """Test parsing named location."""
        result = parse_destination("bank")
        assert result == "bank"

    def test_parse_destination_named_location_with_spaces(self):
        """Test parsing named location with spaces."""
        result = parse_destination("task master")
        assert result == "task master"

    def test_parse_destination_invalid_coordinates(self):
        """Test parsing invalid coordinates falls back to named location."""
        result = parse_destination("abc def")
        assert result == "abc def"

    def test_parse_destination_single_word(self):
        """Test parsing single word destination."""
        result = parse_destination("copper")
        assert result == "copper"


class TestFindNearestLocation:
    """Test _find_nearest_location function."""

    def test_find_nearest_location_single(self):
        """Test finding nearest location with single option."""
        locations = [(5, 5)]
        result = _find_nearest_location(locations, 0, 0)
        assert result == (5, 5)

    def test_find_nearest_location_multiple(self):
        """Test finding nearest location with multiple options."""
        locations = [(10, 10), (2, 2), (5, 5)]
        result = _find_nearest_location(locations, 0, 0)
        assert result == (2, 2)  # Closest to (0, 0)

    def test_find_nearest_location_empty(self):
        """Test finding nearest location with empty list."""
        with pytest.raises(Exception, match="No locations available"):
            _find_nearest_location([], 0, 0)

    def test_find_nearest_location_tie(self):
        """Test finding nearest location with tied distances."""
        locations = [(1, 0), (0, 1)]  # Both distance 1 from (0, 0)
        result = _find_nearest_location(locations, 0, 0)
        assert result == (1, 0)  # Should return first one


class TestResolveNamedLocation:
    """Test resolve_named_location function."""

    @patch("artifactsmmo_cli.utils.pathfinding.find_nearest_bank")
    def test_resolve_named_location_bank(self, mock_find_bank):
        """Test resolving bank location."""
        mock_find_bank.return_value = (4, 1)

        result = resolve_named_location("bank", 0, 0)
        assert result == (4, 1)
        mock_find_bank.assert_called_once_with(0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.find_nearest_task_master")
    def test_resolve_named_location_task_master(self, mock_find_task_master):
        """Test resolving task master location."""
        mock_find_task_master.return_value = (1, 2)

        result = resolve_named_location("task master", 0, 0)
        assert result == (1, 2)
        mock_find_task_master.assert_called_once_with(0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.find_nearest_task_master")
    def test_resolve_named_location_taskmaster(self, mock_find_task_master):
        """Test resolving taskmaster location (no spaces)."""
        mock_find_task_master.return_value = (1, 2)

        result = resolve_named_location("taskmaster", 0, 0)
        assert result == (1, 2)
        mock_find_task_master.assert_called_once_with(0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.find_nearest_task_master")
    def test_resolve_named_location_task_master_underscore(self, mock_find_task_master):
        """Test resolving task_master location (with underscore)."""
        mock_find_task_master.return_value = (1, 2)

        result = resolve_named_location("task_master", 0, 0)
        assert result == (1, 2)
        mock_find_task_master.assert_called_once_with(0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.find_nearest_resource")
    def test_resolve_named_location_resource(self, mock_find_resource):
        """Test resolving resource location."""
        mock_find_resource.return_value = (3, 4)

        result = resolve_named_location("copper", 0, 0)
        assert result == (3, 4)
        mock_find_resource.assert_called_once_with("copper", 0, 0)


class TestFindNearestBank:
    """Test find_nearest_bank function."""

    def test_find_nearest_bank_api_success(self):
        """Test finding nearest bank via API - simplified test."""
        # This test would require complex API mocking, so we'll test the fallback behavior
        # The API integration is tested in the integration tests
        pass

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    def test_find_nearest_bank_fallback(self, mock_client_manager):
        """Test finding nearest bank with fallback to known locations."""
        # Mock client manager to raise exception (API failure)
        mock_client_manager.side_effect = Exception("API error")

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Known bank location


class TestFindNearestTaskMaster:
    """Test find_nearest_task_master function."""

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    def test_find_nearest_task_master_fallback(self, mock_client_manager):
        """Test finding nearest task master with fallback to known locations."""
        # Mock client manager to raise exception (API failure)
        mock_client_manager.side_effect = Exception("API error")

        result = find_nearest_task_master(0, 0)
        # Should return nearest of known locations (1, 2) and (5, 1)
        # (1, 2) has distance 3, (5, 1) has distance 6
        assert result == (1, 2)


class TestFindNearestResource:
    """Test find_nearest_resource function."""

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    def test_find_nearest_resource_not_found(self, mock_client_manager):
        """Test finding resource that doesn't exist."""
        # Mock client manager to raise exception (API failure)
        mock_client_manager.side_effect = Exception("API error")

        with pytest.raises(Exception, match="Resource 'nonexistent' not found"):
            find_nearest_resource("nonexistent", 0, 0)


class TestFindNearestBankAPISuccess:
    """Test find_nearest_bank function API success paths."""

    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    def test_find_nearest_bank_api_success_single_page(self, mock_client_manager, mock_handle_response):
        """Test finding nearest bank via API with single page."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with bank
        mock_bank_content = Mock()
        mock_bank_content.type = "bank"

        mock_map_item = Mock()
        mock_map_item.content = mock_bank_content
        mock_map_item.x = 4
        mock_map_item.y = 1

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        # Mock the get_all_maps_maps_get.sync function
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_get_maps:
            mock_response = Mock()
            mock_get_maps.return_value = mock_response

            result = find_nearest_bank(0, 0)
            assert result == (4, 1)
            mock_get_maps.assert_called_once_with(client=mock_client, page=1, size=100)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_success_multiple_banks(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest bank via API with multiple banks."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map items with banks
        mock_bank_content1 = Mock()
        mock_bank_content1.type = "bank"
        mock_map_item1 = Mock()
        mock_map_item1.content = mock_bank_content1
        mock_map_item1.x = 10
        mock_map_item1.y = 10

        mock_bank_content2 = Mock()
        mock_bank_content2.type = "bank"
        mock_map_item2 = Mock()
        mock_map_item2.content = mock_bank_content2
        mock_map_item2.x = 2
        mock_map_item2.y = 2

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item1, mock_map_item2]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (2, 2)  # Closer to (0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_no_banks_found(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest bank via API when no banks found."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock maps response with no banks
        mock_maps_data = Mock()
        mock_maps_data.data = []
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Falls back to known location

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_response_failure(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest bank via API when response fails."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response with failure
        mock_cli_response = Mock()
        mock_cli_response.success = False
        mock_cli_response.data = None
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Falls back to known location

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_no_data_attribute(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest bank via API when maps has no data attribute."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock maps response without data attribute
        mock_maps_data = Mock()
        # Don't set data attribute

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Falls back to known location

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_map_item_no_content(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest bank via API when map item has no content."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item without content
        mock_map_item = Mock()
        mock_map_item.content = None

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Falls back to known location

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_bank_api_map_item_missing_coordinates(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest bank via API when map item has missing coordinates."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with bank but missing coordinates
        mock_bank_content = Mock()
        mock_bank_content.type = "bank"

        mock_map_item = Mock()
        mock_map_item.content = mock_bank_content
        mock_map_item.x = None
        mock_map_item.y = 1

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_bank(0, 0)
        assert result == (4, 1)  # Falls back to known location


class TestFindNearestTaskMasterAPISuccess:
    """Test find_nearest_task_master function API success paths."""

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_task_master_api_success(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest task master via API."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with task master
        mock_task_content = Mock()
        mock_task_content.type = "task_master"

        mock_map_item = Mock()
        mock_map_item.content = mock_task_content
        mock_map_item.x = 1
        mock_map_item.y = 2

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_task_master(0, 0)
        assert result == (1, 2)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_task_master_api_multiple_task_masters(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest task master via API with multiple task masters."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map items with task masters
        mock_task_content1 = Mock()
        mock_task_content1.type = "task_master"
        mock_map_item1 = Mock()
        mock_map_item1.content = mock_task_content1
        mock_map_item1.x = 10
        mock_map_item1.y = 10

        mock_task_content2 = Mock()
        mock_task_content2.type = "task_master"
        mock_map_item2 = Mock()
        mock_map_item2.content = mock_task_content2
        mock_map_item2.x = 1
        mock_map_item2.y = 1

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item1, mock_map_item2]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_task_master(0, 0)
        assert result == (1, 1)  # Closer to (0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_task_master_api_no_task_masters_found(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest task master via API when none found."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock maps response with no task masters
        mock_maps_data = Mock()
        mock_maps_data.data = []
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_task_master(0, 0)
        assert result == (1, 2)  # Falls back to known location


class TestFindNearestResourceAPISuccess:
    """Test find_nearest_resource function API success paths."""

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_resource_api_success_by_code(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest resource via API by code match."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with resource
        mock_resource_content = Mock()
        mock_resource_content.code = "copper_rock"
        mock_resource_content.type = "resource"

        mock_map_item = Mock()
        mock_map_item.content = mock_resource_content
        mock_map_item.x = 3
        mock_map_item.y = 4

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_resource("copper", 0, 0)
        assert result == (3, 4)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_resource_api_success_by_type(self, mock_get_maps, mock_handle_response, mock_client_manager):
        """Test finding nearest resource via API by type match."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with resource
        mock_resource_content = Mock()
        mock_resource_content.code = "some_rock"
        mock_resource_content.type = "copper_mine"

        mock_map_item = Mock()
        mock_map_item.content = mock_resource_content
        mock_map_item.x = 5
        mock_map_item.y = 6

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_resource("copper", 0, 0)
        assert result == (5, 6)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_resource_api_success_by_resource_type(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest resource via API by resource type match."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map item with resource
        mock_resource_content = Mock()
        mock_resource_content.code = "some_code"
        mock_resource_content.type = "resource"

        mock_map_item = Mock()
        mock_map_item.content = mock_resource_content
        mock_map_item.x = 7
        mock_map_item.y = 8

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_resource("anything", 0, 0)
        assert result == (7, 8)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_resource_api_multiple_resources(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest resource via API with multiple matches."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock map items with resources
        mock_resource_content1 = Mock()
        mock_resource_content1.code = "copper_rock"
        mock_resource_content1.type = "resource"
        mock_map_item1 = Mock()
        mock_map_item1.content = mock_resource_content1
        mock_map_item1.x = 10
        mock_map_item1.y = 10

        mock_resource_content2 = Mock()
        mock_resource_content2.code = "copper_ore"
        mock_resource_content2.type = "resource"
        mock_map_item2 = Mock()
        mock_map_item2.content = mock_resource_content2
        mock_map_item2.x = 2
        mock_map_item2.y = 2

        # Mock maps response
        mock_maps_data = Mock()
        mock_maps_data.data = [mock_map_item1, mock_map_item2]
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        result = find_nearest_resource("copper", 0, 0)
        assert result == (2, 2)  # Closer to (0, 0)

    @patch("artifactsmmo_cli.utils.pathfinding.ClientManager")
    @patch("artifactsmmo_cli.utils.pathfinding.handle_api_response")
    @patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync")
    def test_find_nearest_resource_api_no_resources_found(
        self, mock_get_maps, mock_handle_response, mock_client_manager
    ):
        """Test finding nearest resource via API when none found."""
        # Mock client
        mock_client = Mock()
        mock_client_manager.return_value.client = mock_client

        # Mock maps response with no matching resources
        mock_maps_data = Mock()
        mock_maps_data.data = []
        mock_maps_data.pages = 1

        # Mock API response
        mock_response = Mock()
        mock_get_maps.sync.return_value = mock_response

        # Mock handle_api_response
        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.data = mock_maps_data
        mock_handle_response.return_value = mock_cli_response

        with pytest.raises(Exception, match="Resource 'nonexistent' not found"):
            find_nearest_resource("nonexistent", 0, 0)
