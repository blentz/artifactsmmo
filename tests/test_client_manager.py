"""Tests for client manager."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.fight_request_schema import FightRequestSchema

from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def test_client_manager_singleton():
    """Test that ClientManager is a singleton."""
    manager1 = ClientManager()
    manager2 = ClientManager()
    assert manager1 is manager2


def test_client_manager_initialization():
    """Test client manager initialization."""
    config = Config(token="test-token")
    manager = ClientManager()

    with patch("artifactsmmo_cli.client_manager.AuthenticatedClient") as mock_client:
        manager.initialize(config)

        # Verify API client was created with correct parameters
        from artifactsmmo_cli.maintenance_detector import detect_maintenance_response

        mock_client.assert_called_once_with(
            base_url="https://api.artifactsmmo.com",
            token="test-token",
            timeout=httpx.Timeout(30),
            raise_on_unexpected_status=False,
            httpx_args={"event_hooks": {"response": [detect_maintenance_response]}},
        )

        assert manager.is_initialized()
        assert manager.config == config


def test_client_manager_not_initialized():
    """Test accessing client before initialization raises error."""
    # Create a fresh instance
    ClientManager._instance = None
    manager = ClientManager()

    with pytest.raises(RuntimeError, match="Client not initialized"):
        _ = manager.client

    with pytest.raises(RuntimeError, match="Client not initialized"):
        _ = manager.config


def test_client_manager_api_not_initialized():
    """Test accessing api property before initialization raises error."""
    ClientManager._instance = None
    ClientManager._client = None
    ClientManager._api = None
    ClientManager._config = None
    manager = ClientManager()

    with pytest.raises(RuntimeError, match="Client not initialized"):
        _ = manager.api


def test_client_manager_api_property_returns_wrapper():
    """Test that api property returns the APIWrapper after initialization."""
    ClientManager._instance = None
    ClientManager._client = None
    ClientManager._api = None
    ClientManager._config = None
    manager = ClientManager()

    config = Config(token="test-token")
    with patch("artifactsmmo_cli.client_manager.AuthenticatedClient"):
        manager.initialize(config)
        api = manager.api
        assert isinstance(api, APIWrapper)


def test_client_manager_is_initialized():
    """Test is_initialized method."""
    ClientManager._instance = None
    manager = ClientManager()

    assert not manager.is_initialized()

    config = Config(token="test-token")
    with patch("artifactsmmo_cli.client_manager.AuthenticatedClient"):
        manager.initialize(config)
        assert manager.is_initialized()


def test_client_manager_client_property():
    """Test that client property returns the initialized client."""
    ClientManager._instance = None
    ClientManager._client = None
    ClientManager._api = None
    ClientManager._config = None
    manager = ClientManager()

    config = Config(token="test-token")
    with patch("artifactsmmo_cli.client_manager.AuthenticatedClient") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance
        manager.initialize(config)
        assert manager.client is mock_client_instance


def test_client_has_maintenance_response_hook():
    """Test that the maintenance response hook is installed on the API client."""
    from artifactsmmo_cli.maintenance_detector import detect_maintenance_response

    ClientManager._instance = None
    ClientManager._client = None
    ClientManager._api = None
    ClientManager._config = None
    manager = ClientManager()

    config = Config(token="test-token")
    manager.initialize(config)
    hooks = manager.client.get_httpx_client().event_hooks["response"]
    assert detect_maintenance_response in hooks


# ──────────────────────────────────────────────
# APIWrapper - simple pass-through methods
# ──────────────────────────────────────────────

def _make_wrapper() -> APIWrapper:
    """Create an APIWrapper with a mock AuthenticatedClient."""
    mock_client = MagicMock()
    mock_client._base_url = "https://api.artifactsmmo.com"
    mock_client.token = "test-token"
    return APIWrapper(mock_client)


def test_api_wrapper_get_server_details():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.get_server_details_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.get_server_details()
    mock_sync.assert_called_once_with(client=wrapper._client)
    assert result is sentinel


def test_api_wrapper_get_my_characters():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.get_my_characters_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.get_my_characters()
    mock_sync.assert_called_once_with(client=wrapper._client)
    assert result is sentinel


def test_api_wrapper_create_character():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.create_character_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.create_character(body)
    mock_sync.assert_called_once_with(client=wrapper._client, body=body)
    assert result is sentinel


def test_api_wrapper_delete_character():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.delete_character_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.delete_character(body)
    mock_sync.assert_called_once_with(client=wrapper._client, body=body)
    assert result is sentinel


def test_api_wrapper_get_character():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.get_character_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.get_character("Alice")
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice")
    assert result is sentinel


# ──────────────────────────────────────────────
# action_* methods - success path (no exception)
# ──────────────────────────────────────────────

def test_api_wrapper_action_move_success():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_move_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_move("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_fight_success():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_fight_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_fight("Alice")
    assert mock_sync.call_count == 1
    call_kwargs = mock_sync.call_args.kwargs
    assert call_kwargs["client"] is wrapper._client
    assert call_kwargs["name"] == "Alice"
    assert isinstance(call_kwargs["body"], FightRequestSchema)
    assert result is sentinel


def test_api_wrapper_action_gathering_success():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_gathering_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_gathering("Alice")
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice")
    assert result is sentinel


def test_api_wrapper_action_rest_success():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_rest_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_rest("Alice")
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice")
    assert result is sentinel


def test_api_wrapper_action_equip_item_success():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_equip_item_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_equip_item("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_unequip_item_success():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_unequip_item_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_unequip_item("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_use_item_success():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_use_item_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_use_item("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


# ──────────────────────────────────────────────
# action_* methods - non-standard status re-raises ValueError
# ──────────────────────────────────────────────

def _non_standard_error() -> ValueError:
    return ValueError("499 is not a valid HTTPStatus")


def _other_value_error() -> ValueError:
    return ValueError("some other error")


def test_api_wrapper_action_move_non_standard_status_reraises():
    """ValueError with 'is not a valid HTTPStatus' is forwarded to handler."""
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_move_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_move("Alice", body)
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/move")


def test_api_wrapper_action_move_other_value_error_reraises():
    """ValueError without the magic phrase is re-raised directly."""
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_move_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_move("Alice", body)


def test_api_wrapper_action_fight_non_standard_status_reraises():
    wrapper = _make_wrapper()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_fight_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_fight("Alice")
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/fight")


def test_api_wrapper_action_fight_other_value_error_reraises():
    wrapper = _make_wrapper()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_fight_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_fight("Alice")


def test_api_wrapper_action_gathering_non_standard_status_reraises():
    wrapper = _make_wrapper()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_gathering_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_gathering("Alice")
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/gathering")


def test_api_wrapper_action_gathering_other_value_error_reraises():
    wrapper = _make_wrapper()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_gathering_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_gathering("Alice")


def test_api_wrapper_action_rest_non_standard_status_reraises():
    wrapper = _make_wrapper()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_rest_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_rest("Alice")
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/rest")


def test_api_wrapper_action_rest_other_value_error_reraises():
    wrapper = _make_wrapper()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_rest_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_rest("Alice")


def test_api_wrapper_action_equip_non_standard_status_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_equip_item_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_equip_item("Alice", body)
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/equip")


def test_api_wrapper_action_equip_other_value_error_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_equip_item_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_equip_item("Alice", body)


def test_api_wrapper_action_unequip_non_standard_status_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_unequip_item_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_unequip_item("Alice", body)
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/unequip")


def test_api_wrapper_action_unequip_other_value_error_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_unequip_item_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_unequip_item("Alice", body)


def test_api_wrapper_action_use_item_non_standard_status_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _non_standard_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_use_item_sync",
        side_effect=err,
    ):
        with patch.object(wrapper, "_handle_non_standard_status_error", side_effect=err) as mock_handler:
            with pytest.raises(ValueError):
                wrapper.action_use_item("Alice", body)
            mock_handler.assert_called_once_with(err, "POST", "/my/Alice/action/use")


def test_api_wrapper_action_use_item_other_value_error_reraises():
    wrapper = _make_wrapper()
    body = MagicMock()
    err = _other_value_error()
    with patch(
        "artifactsmmo_cli.api_wrapper.action_use_item_sync",
        side_effect=err,
    ):
        with pytest.raises(ValueError, match="some other error"):
            wrapper.action_use_item("Alice", body)


# ──────────────────────────────────────────────
# Bank / account operations
# ──────────────────────────────────────────────

def test_api_wrapper_get_bank_items():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.get_bank_items_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.get_bank_items()
    mock_sync.assert_called_once_with(client=wrapper._client)
    assert result is sentinel


def test_api_wrapper_get_bank_details():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.get_bank_details_sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.get_bank_details()
    mock_sync.assert_called_once_with(client=wrapper._client)
    assert result is sentinel


def test_api_wrapper_action_deposit_bank_gold():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.deposit_gold_api.sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_deposit_bank_gold("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_withdraw_bank_gold():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.withdraw_gold_api.sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_withdraw_bank_gold("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_deposit_bank_item():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.deposit_item_api.sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_deposit_bank_item("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_withdraw_bank_item():
    wrapper = _make_wrapper()
    body = MagicMock()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.withdraw_item_api.sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_withdraw_bank_item("Alice", body)
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice", body=body)
    assert result is sentinel


def test_api_wrapper_action_buy_bank_expansion():
    wrapper = _make_wrapper()
    sentinel = object()
    with patch(
        "artifactsmmo_cli.api_wrapper.buy_expansion_api.sync",
        return_value=sentinel,
    ) as mock_sync:
        result = wrapper.action_buy_bank_expansion("Alice")
    mock_sync.assert_called_once_with(client=wrapper._client, name="Alice")
    assert result is sentinel


# ──────────────────────────────────────────────
# _handle_non_standard_status_error branches
# ──────────────────────────────────────────────

def test_handle_non_standard_no_match_reraises_original():
    """If no status code found in error message, raise original error."""
    wrapper = _make_wrapper()
    original = ValueError("no status code here")
    with pytest.raises(ValueError, match="no status code here"):
        wrapper._handle_non_standard_status_error(original, "POST", "/my/Alice/action/move")


def test_handle_non_standard_post_matching_status_raises_unexpected_status():
    """POST with matching non-standard status code raises UnexpectedStatus."""
    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_response = MagicMock()
    mock_response.status_code = 499
    mock_response.json.return_value = {"error": "cooldown"}
    mock_response.content = b'{"error": "cooldown"}'

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    mock_http_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(UnexpectedStatus) as exc_info:
            wrapper._handle_non_standard_status_error(original, "POST", "/my/Alice/action/move")

    assert exc_info.value.status_code == 499


def test_handle_non_standard_get_matching_status_raises_unexpected_status():
    """GET with matching non-standard status code raises UnexpectedStatus."""
    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_response = MagicMock()
    mock_response.status_code = 499
    mock_response.json.return_value = {"error": "cooldown"}
    mock_response.content = b'{"error": "cooldown"}'

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    mock_http_client.get.return_value = mock_response

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(UnexpectedStatus) as exc_info:
            wrapper._handle_non_standard_status_error(original, "GET", "/some/endpoint")

    assert exc_info.value.status_code == 499


def test_handle_non_standard_unknown_method_reraises_original():
    """Unknown HTTP method raises original error."""
    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(ValueError, match="499 is not a valid HTTPStatus"):
            wrapper._handle_non_standard_status_error(original, "DELETE", "/my/Alice/action/move")


def test_handle_non_standard_different_status_code_reraises_original():
    """If response has a different status code, raise original error."""
    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_response = MagicMock()
    mock_response.status_code = 200  # different from 499

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    mock_http_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(ValueError, match="499 is not a valid HTTPStatus"):
            wrapper._handle_non_standard_status_error(original, "POST", "/my/Alice/action/move")


def test_handle_non_standard_json_decode_error_reraises_original():
    """If JSON decode fails, raise original error."""
    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_response = MagicMock()
    mock_response.status_code = 499
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    mock_http_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(ValueError, match="499 is not a valid HTTPStatus"):
            wrapper._handle_non_standard_status_error(original, "POST", "/my/Alice/action/move")


def test_handle_non_standard_httpx_raises_reraises_original():
    """If httpx.Client raises an httpx.HTTPError, raise original error."""
    import httpx

    wrapper = _make_wrapper()
    original = ValueError("499 is not a valid HTTPStatus")

    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    mock_http_client.post.side_effect = httpx.ConnectError("network failure")

    with patch("httpx.Client", return_value=mock_http_client):
        with pytest.raises(ValueError, match="499 is not a valid HTTPStatus"):
            wrapper._handle_non_standard_status_error(original, "POST", "/my/Alice/action/move")
