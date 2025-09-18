"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest

from artifactsmmo_cli.config import Config


def test_config_from_token_file():
    """Test loading config from token file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token-123")
        token_file = Path(f.name)

    try:
        config = Config.from_token_file(token_file)
        assert config.token == "test-token-123"
        assert config.api_base_url == "https://api.artifactsmmo.com"
        assert config.timeout == 30
        assert config.debug is False
    finally:
        token_file.unlink()


def test_config_from_environment():
    """Test loading config from environment variable."""
    # Set environment variable
    os.environ["ARTIFACTSMMO_TOKEN"] = "env-token-456"

    try:
        # Use non-existent file path
        config = Config.from_token_file(Path("nonexistent"))
        assert config.token == "env-token-456"
    finally:
        # Clean up
        del os.environ["ARTIFACTSMMO_TOKEN"]


def test_config_no_token_raises_error():
    """Test that missing token raises ValueError."""
    with pytest.raises(ValueError, match="No authentication token found"):
        Config.from_token_file(Path("nonexistent"))


def test_config_auth_headers():
    """Test authentication headers generation."""
    config = Config(token="test-token")
    headers = config.get_auth_headers()
    assert headers == {"Authorization": "Bearer test-token"}


def test_config_custom_values():
    """Test config with custom values."""
    config = Config(token="custom-token", api_base_url="https://custom.api.com", timeout=60, debug=True)
    assert config.token == "custom-token"
    assert config.api_base_url == "https://custom.api.com"
    assert config.timeout == 60
    assert config.debug is True
