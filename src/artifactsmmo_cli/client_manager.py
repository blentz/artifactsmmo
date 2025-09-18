"""Client manager for ArtifactsMMO API."""

from typing import Any, Optional
import json
import re

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.config import Config


class APIWrapper:
    """Wrapper to provide a convenient interface to the API client."""

    def __init__(self, client: AuthenticatedClient):
        self._client = client

    # Server details
    def get_server_details(self) -> Any:
        from artifactsmmo_api_client.api.server_details.get_server_details_get import sync

        return sync(client=self._client)

    # Character management
    def get_my_characters(self) -> Any:
        from artifactsmmo_api_client.api.my_characters.get_my_characters_my_characters_get import sync

        return sync(client=self._client)

    def create_character(self, body: Any) -> Any:
        from artifactsmmo_api_client.api.characters.create_character_characters_create_post import sync

        return sync(client=self._client, body=body)

    def delete_character(self, body: Any) -> Any:
        from artifactsmmo_api_client.api.characters.delete_character_characters_delete_post import sync

        return sync(client=self._client, body=body)

    def get_character(self, name: str) -> Any:
        from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync

        return sync(client=self._client, name=name)

    # Character actions
    def action_move(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_move_my_name_action_move_post import sync

        try:
            return sync(client=self._client, name=name, body=body)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/move")
            raise

    def action_fight(self, name: str) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync

        try:
            return sync(client=self._client, name=name)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/fight")
            raise

    def action_gathering(self, name: str) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import sync

        try:
            return sync(client=self._client, name=name)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/gathering")
            raise

    def action_rest(self, name: str) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_rest_my_name_action_rest_post import sync

        try:
            return sync(client=self._client, name=name)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/rest")
            raise

    def action_equip_item(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name_action_equip_post import sync

        try:
            return sync(client=self._client, name=name, body=body)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/equip")
            raise

    def action_unequip_item(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_unequip_item_my_name_action_unequip_post import sync

        try:
            return sync(client=self._client, name=name, body=body)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/unequip")
            raise

    def action_use_item(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import sync

        try:
            return sync(client=self._client, name=name, body=body)
        except ValueError as e:
            if "is not a valid HTTPStatus" in str(e):
                # Handle non-standard HTTP status codes by making a direct request
                return self._handle_non_standard_status_error(e, "POST", f"/my/{name}/action/use")
            raise

    # Bank operations
    def get_bank_items(self) -> Any:
        from artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get import sync

        return sync(client=self._client)

    def get_bank_details(self) -> Any:
        from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync

        return sync(client=self._client)

    def action_deposit_bank_gold(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters import (
            action_deposit_bank_gold_my_name_action_bank_deposit_gold_post as deposit_gold_api,
        )

        return deposit_gold_api.sync(client=self._client, name=name, body=body)

    def action_withdraw_bank_gold(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters import (
            action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post as withdraw_gold_api,
        )

        return withdraw_gold_api.sync(client=self._client, name=name, body=body)

    def action_deposit_bank_item(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters import (
            action_deposit_bank_item_my_name_action_bank_deposit_item_post as deposit_item_api,
        )

        return deposit_item_api.sync(client=self._client, name=name, body=body)

    def action_withdraw_bank_item(self, name: str, body: Any) -> Any:
        from artifactsmmo_api_client.api.my_characters import (
            action_withdraw_bank_item_my_name_action_bank_withdraw_item_post as withdraw_item_api,
        )

        return withdraw_item_api.sync(client=self._client, name=name, body=body)

    def action_buy_bank_expansion(self, name: str) -> Any:
        from artifactsmmo_api_client.api.my_characters import (
            action_buy_bank_expansion_my_name_action_bank_buy_expansion_post as buy_expansion_api,
        )

        return buy_expansion_api.sync(client=self._client, name=name)

    def _handle_non_standard_status_error(self, original_error: ValueError, method: str, endpoint: str) -> Any:
        """Handle non-standard HTTP status codes by making a direct request to get response data."""
        try:
            # Extract the status code from the error message
            match = re.search(r"(\d+) is not a valid HTTPStatus", str(original_error))
            if not match:
                raise original_error

            status_code = int(match.group(1))

            # Make a direct HTTP request to get the response data
            import httpx

            url = f"{self._client._base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self._client.token}"}

            with httpx.Client() as client:
                if method == "POST":
                    response = client.post(url, headers=headers)
                elif method == "GET":
                    response = client.get(url, headers=headers)
                else:
                    raise original_error

                # If we get the same status code, parse the response
                if response.status_code == status_code:
                    try:
                        response_data = response.json()
                        # Create an UnexpectedStatus error with the response data
                        raise UnexpectedStatus(status_code=status_code, content=response.content)
                    except json.JSONDecodeError:
                        # If we can't parse JSON, raise the original error
                        raise original_error
                else:
                    # If we get a different status code, raise the original error
                    raise original_error

        except UnexpectedStatus:
            # Re-raise UnexpectedStatus so it can be handled properly
            raise
        except Exception:
            # If anything goes wrong, raise the original error
            raise original_error


class ClientManager:
    """Singleton manager for the ArtifactsMMO API client."""

    _instance: Optional["ClientManager"] = None
    _client: AuthenticatedClient | None = None
    _api: APIWrapper | None = None
    _config: Config | None = None
    _last_response_data: Optional[dict] = None

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
            timeout=config.timeout,
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
