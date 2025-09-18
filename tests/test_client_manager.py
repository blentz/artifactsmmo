"""Tests for client manager."""

from unittest.mock import patch

import pytest

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
        mock_client.assert_called_once_with(
            base_url="https://api.artifactsmmo.com",
            token="test-token",
            timeout=30,
            raise_on_unexpected_status=False,
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


def test_client_manager_is_initialized():
    """Test is_initialized method."""
    ClientManager._instance = None
    manager = ClientManager()

    assert not manager.is_initialized()

    config = Config(token="test-token")
    with patch("artifactsmmo_cli.client_manager.AuthenticatedClient"):
        manager.initialize(config)
        assert manager.is_initialized()
