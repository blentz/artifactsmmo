"""Shared fixtures and API-boundary stub builders for command tests.

These helpers build small, real response objects at the artifactsmmo-api-client
boundary so the real internal helpers (handle_api_response / handle_api_error)
run in tests instead of being patched out.
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.models.error_schema import ErrorSchema
from typer.testing import CliRunner

from artifactsmmo_cli.client_manager import ClientManager


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def stub_api():
    """Install a mock client/api wrapper on the real ClientManager singleton.

    This stubs only the network boundary: every module-level ClientManager()
    lookup (commands and utils alike) sees the same stub, so the real internal
    helpers run unpatched.
    """
    manager = ClientManager()
    old_client, old_api = manager._client, manager._api
    manager._client = Mock(name="stub_client")
    manager._api = Mock(name="stub_api")
    yield manager._api
    manager._client, manager._api = old_client, old_api


def api_response(data, **extra) -> SimpleNamespace:
    """Build a successful API response envelope (generated clients expose `.data`)."""
    return SimpleNamespace(data=data, **extra)


def api_error(code: int, message: str) -> ErrorResponseSchema:
    """Build a real ErrorResponseSchema as returned by the generated client."""
    return ErrorResponseSchema(error=ErrorSchema(code=code, message=message))


def unexpected_status(code: int, message: str | None = None) -> UnexpectedStatus:
    """Build an UnexpectedStatus carrying a real JSON error body."""
    body: dict = {"error": {"code": code}}
    if message is not None:
        body["error"]["message"] = message
    return UnexpectedStatus(status_code=code, content=json.dumps(body).encode())


def cooldown_status(seconds: float) -> UnexpectedStatus:
    """Build the 499 cooldown error the API raises while on cooldown."""
    body = {
        "error": {
            "code": 499,
            "message": f"Character is on cooldown: {seconds} seconds remaining",
            "cooldown": {"remaining_seconds": seconds},
        }
    }
    return UnexpectedStatus(status_code=499, content=json.dumps(body).encode())
