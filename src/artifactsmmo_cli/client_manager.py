"""Client manager for ArtifactsMMO API."""

from typing import Any, Optional

import httpx
from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.config import Config


class ClientManager:
    """Singleton manager for the ArtifactsMMO API client."""

    _instance: Optional["ClientManager"] = None
    _client: AuthenticatedClient | None = None
    _api: APIWrapper | None = None
    _config: Config | None = None
    _last_response_data: dict[str, Any] | None = None

    def __new__(cls) -> "ClientManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, config: Config) -> None:
        """Initialize the API client with configuration."""
        self._config = config

        # Create the API client with token
        # Set raise_on_unexpected_status=False because ArtifactsMMO uses non-standard HTTP codes
        self._client = AuthenticatedClient(
            base_url=config.api_base_url,
            token=config.token,
            # AuthenticatedClient declares `Timeout | None`; wrap the int config
            # value explicitly (httpx.Timeout(int) is the canonical form).
            timeout=httpx.Timeout(config.timeout),
            raise_on_unexpected_status=False,
        )

        # Create the API wrapper
        self._api = APIWrapper(self._client)

    @property
    def client(self) -> AuthenticatedClient:
        """Get the initialized API client."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return self._client

    @property
    def api(self) -> APIWrapper:
        """Get the API wrapper."""
        if self._api is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return self._api

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        return self._config

    def is_initialized(self) -> bool:
        """Check if the client is initialized."""
        return self._client is not None
