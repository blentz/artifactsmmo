"""Tests for configuration management."""

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


def test_config_from_environment(monkeypatch):
    """Test loading config from environment variable."""
    # monkeypatch restores the prior value after the test; a bare
    # set-then-del here would destroy an ambient ARTIFACTSMMO_TOKEN
    # (CI sets one) for every test that runs later in the session.
    monkeypatch.setenv("ARTIFACTSMMO_TOKEN", "env-token-456")
    # Use non-existent file path
    config = Config.from_token_file(Path("nonexistent"))
    assert config.token == "env-token-456"


def test_config_no_token_raises_error(monkeypatch):
    """Test that missing token raises ValueError."""
    # Clear the env fallback so the no-token path fires regardless of
    # the ambient environment.
    monkeypatch.delenv("ARTIFACTSMMO_TOKEN", raising=False)
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


def test_config_default_game_data_ttl_is_30():
    """The static-game-data cache TTL defaults to 30 minutes."""
    cfg = Config(token="t")
    assert cfg.game_data_ttl_minutes == 30
