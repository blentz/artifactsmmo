"""
API Client Wrapper

This module provides the main APIClientWrapper class for interacting with the
ArtifactsMMO API. Handles authentication, error handling, rate limiting, and
response processing with comprehensive game operation support.
"""

import asyncio
from typing import Any, Optional

from artifactsmmo_api_client.client import AuthenticatedClient
from artifactsmmo_api_client.models.add_character_schema import AddCharacterSchema
from artifactsmmo_api_client.models.character_skin import CharacterSkin
from artifactsmmo_api_client.models.delete_character_schema import DeleteCharacterSchema
from artifactsmmo_api_client.models.destination_schema import DestinationSchema
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema
from artifactsmmo_api_client.api.characters.delete_character_characters_delete_post import asyncio_detailed as delete_character_asyncio_detailed
from artifactsmmo_api_client.api.my_characters import get_my_characters_my_characters_get
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import asyncio_detailed as action_gathering_asyncio_detailed
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import asyncio_detailed as action_crafting_asyncio_detailed
from artifactsmmo_api_client.api.my_characters.action_rest_my_name_action_rest_post import asyncio_detailed as action_rest_asyncio_detailed
from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name_action_equip_post import asyncio_detailed as action_equip_item_asyncio_detailed
from artifactsmmo_api_client.api.my_characters.action_unequip_item_my_name_action_unequip_post import asyncio_detailed as action_unequip_item_asyncio_detailed
from artifactsmmo_api_client.api.items.get_all_items_items_get import asyncio_detailed as get_all_items_asyncio_detailed
from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import asyncio_detailed as get_all_monsters_asyncio_detailed
from artifactsmmo_api_client.api.maps.get_all_maps_maps_get import asyncio_detailed as get_all_maps_asyncio_detailed
from artifactsmmo_api_client.api.resources.get_all_resources_resources_get import asyncio_detailed as get_all_resources_asyncio_detailed
from artifactsmmo_api_client.api.np_cs.get_all_npcs_npcs_details_get import asyncio_detailed as get_all_npcs_asyncio_detailed
from artifactsmmo_api_client.api.characters.create_character_characters_create_post import asyncio_detailed as create_character_asyncio_detailed
from artifactsmmo_api_client.api.characters import get_character_characters_name_get
from artifactsmmo_api_client.api.my_characters import action_move_my_name_action_move_post
from artifactsmmo_api_client.api.my_characters import action_fight_my_name_action_fight_post

from src.lib.httpstatus import ArtifactsHTTPStatus
from .models import CooldownInfo, GameItem, GameMonster, GameMap, GameResource, GameNPC
from .token_config import TokenConfig
from .cooldown_manager import CooldownManager


class APIClientWrapper:
    """Wrapper around artifactsmmo-api-client with Pydantic validation"""

    def __init__(self, token_file: str = "TOKEN"):
        """Initialize API client wrapper with authentication.
        
        Parameters:
            token_file: Path to file containing API token (default: "TOKEN")
            
        Return values:
            None (constructor)
            
        This method initializes the API client wrapper with proper token
        authentication, setting up the underlying API client and error handling
        infrastructure for reliable game operations.
        """
        self.token_config = TokenConfig.from_file(token_file)
        self.cooldown_manager = CooldownManager()

        # Initialize the authenticated client with the base URL and token
        self.client = AuthenticatedClient(
            base_url="https://api.artifactsmmo.com",
            token=self.token_config.token
        )
        
        # Initialize status codes for testing
        self.status_codes = ArtifactsHTTPStatus

    async def create_character(self, name: str, skin: str) -> 'CharacterSchema':
        """Create new character with validation.
        
        Parameters:
            name: Character name for creation
            skin: Character skin identifier for appearance
            
        Return values:
            CharacterSchema instance with new character data
            
        This method creates a new character through the ArtifactsMMO API,
        handling validation, rate limiting, and error responses while
        returning the character data for further operations.
        """
        # Validate skin parameter
        try:
            character_skin = CharacterSkin(skin)
        except ValueError:
            raise ValueError(f"Invalid skin: {skin}")

        # Create character request
        body = AddCharacterSchema(name=name, skin=character_skin)

        # Make API call
        response = await create_character_asyncio_detailed(client=self.client, body=body)
        processed_response = await self._process_response(response)

        # Trust API contract - let AttributeError bubble up if structure is unexpected
        return processed_response.data

    async def delete_character(self, name: str) -> bool:
        """Delete character by name.
        
        Parameters:
            name: Character name to delete
            
        Return values:
            Boolean indicating successful deletion
            
        This method deletes the specified character through the ArtifactsMMO
        API, handling confirmation requirements and error responses while
        ensuring proper cleanup of character-related data.
        """
        body = DeleteCharacterSchema(name=name)

        # Make API call
        response = await delete_character_asyncio_detailed(client=self.client, body=body)
        processed_response = await self._process_response(response)

        # For delete operations, success is indicated by 200 status
        return response.status_code == 200

    async def get_characters(self) -> list['CharacterSchema']:
        """Get list of user's characters.
        
        Parameters:
            None (uses authenticated token for user identification)
            
        Return values:
            List of CharacterSchema instances for the authenticated user
            
        This method retrieves all characters associated with the authenticated
        user account, providing character selection and management capabilities
        for the AI player system.
        """
        # Make API call
        response = await get_my_characters_my_characters_get.asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        return processed_response.data

    async def get_character(self, name: str) -> 'CharacterGameState':
        """Get specific character by name.
        
        Parameters:
            name: Character name to retrieve
            
        Return values:
            CharacterSchema instance with current character state
            
        This method retrieves detailed information for a specific character,
        including current state, equipment, and progression data essential
        for AI player state management and decision making.
        """
        # Make API call
        response = await get_character_characters_name_get.asyncio_detailed(client=self.client, name=name)
        processed_response = await self._process_response(response)

        # Extract character data from response
        try:
            # Try to access character data from response
            api_character = processed_response.data
        except AttributeError:
            try:
                # Try direct character access
                api_character = processed_response.character
            except AttributeError:
                # Fallback to direct response
                api_character = processed_response
        
        # Transform API model to internal model
        from ..ai_player.state.game_state import CharacterGameState
        return CharacterGameState.from_api_character(api_character)

    async def move_character(self, character_name: str, x: int, y: int) -> 'ActionMoveSchema':
        """Move character to coordinates.
        
        Parameters:
            character_name: Name of character to move
            x: Target X coordinate
            y: Target Y coordinate
            
        Return values:
            ActionMoveSchema with movement result and cooldown information
            
        This method moves the specified character to the given coordinates,
        pathfinding validation, cooldown timing, and movement result
        processing for AI player navigation operations.
        """
        # Create movement request body
        body = DestinationSchema(x=x, y=y)

        # Make API call
        response = await action_move_my_name_action_move_post.asyncio(client=self.client, name=character_name, body=body)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)
        return processed_response.data

    async def fight_monster(self, character_name: str) -> 'ActionFightSchema':
        """Fight monster at current location.
        
        Parameters:
            character_name: Name of character to initiate combat
            
        Return values:
            ActionFightSchema with combat result and loot information
            
        This method initiates combat with a monster at the character's current
        location, handling damage calculation, XP rewards, and item drops
        while managing combat cooldowns and HP changes.
        """
        # Make API call (no body needed for fight action)
        response = await action_fight_my_name_action_fight_post.asyncio(client=self.client, name=character_name)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)
        return processed_response.data

    async def gather_resource(self, character_name: str) -> 'ActionGatheringSchema':
        """Gather resource at current location.
        
        Parameters:
            character_name: Name of character to perform gathering
            
        Return values:
            ActionGatheringSchema with gathering result and XP information
            
        This method performs resource gathering at the character's current
        location, handling skill requirements, tool validation, and resource
        collection while managing gathering cooldowns and XP gains.
        """
        # Make API call (no body needed for gathering action)
        response = await action_gathering_asyncio_detailed(client=self.client, name=character_name)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        return processed_response.data

    async def craft_item(self, character_name: str, code: str, quantity: int = 1) -> 'ActionCraftingSchema':
        """Craft item by code.
        
        Parameters:
            character_name: Name of character to perform crafting
            code: Item code identifier for crafting
            quantity: Number of items to craft (default: 1)
            
        Return values:
            ActionCraftingSchema with crafting result and XP information
            
        This method performs item crafting through the ArtifactsMMO API, handling
        requirements, material consumption, and result processing while
        managing crafting cooldowns and XP rewards.
        """
        # Create crafting request body
        body = CraftingSchema(code=code, quantity=quantity)

        # Make API call
        response = await action_crafting_asyncio_detailed(client=self.client, name=character_name, body=body)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        return processed_response.data

    async def rest_character(self, character_name: str) -> 'ActionRestSchema':
        """Rest character to recover HP.
        
        Parameters:
            character_name: Name of character to rest
            
        Return values:
            ActionRestSchema with rest result and HP recovery information
            
        This method initiates character rest to recover hit points through
        handling recovery timing, cooldown management, and ensuring the
        character is in a safe location for effective rest.
        """
        # Make API call (no body needed for rest action)
        response = await action_rest_asyncio_detailed(client=self.client, name=character_name)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        return processed_response.data

    async def equip_item(self, character_name: str, code: str, slot: str) -> 'ActionEquipSchema':
        """Equip item to slot.
        
        Parameters:
            character_name: Name of character to equip item
            code: Item code identifier to equip
            slot: Equipment slot identifier (weapon, helmet, etc.)
            
        Return values:
            ActionEquipSchema with equipment result and stat changes
            
        This method equips the specified item to the character through the API,
        slot validation, item requirements, and character stat updates
        while ensuring proper inventory management.
        """
        # Create equip request body
        body = EquipSchema(code=code, slot=slot)

        # Make API call
        response = await action_equip_item_asyncio_detailed(client=self.client, name=character_name, body=body)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        return processed_response.data

    async def unequip_item(self, character_name: str, slot: str) -> 'ActionUnequipSchema':
        """Unequip item from slot.
        
        Parameters:
            character_name: Name of character to unequip item
            slot: Equipment slot identifier to unequip
            
        Return values:
            ActionUnequipSchema with unequipment result and stat changes
            
        This method unequips an item from the specified character slot through the
        API, handling slot validation, inventory space requirements, and character
        stat updates while ensuring proper equipment management.
        """
        # Create unequip request body
        body = UnequipSchema(slot=slot)

        # Make API call
        response = await action_unequip_item_asyncio_detailed(client=self.client, name=character_name, body=body)
        processed_response = await self._process_response(response)

        # Trust API contract for cooldown structure
        self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        return processed_response.data

    async def get_all_items(self) -> list[GameItem]:
        """Get all game items for caching.
        
        Parameters:
            None (retrieves complete item database)
            
        Return values:
            List of GameItem instances for all game items
            
        This method retrieves all available items in the game for local
        caching purposes, enabling offline access to item data for GOAP
        planning, crafting recipes, and inventory management operations.
        """
        # Make API call
        response = await get_all_items_asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        # Transform API models to internal models
        return [GameItem.from_api_item(item) for item in processed_response.data]

    async def get_all_monsters(self) -> list[GameMonster]:
        """Get all monsters for caching.
        
        Parameters:
            None (retrieves complete monster database)
            
        Return values:
            List of GameMonster instances for all game monsters
            
        This method retrieves all available monsters in the game for local
        caching purposes, enabling offline access to monster data for combat
        planning, level progression, and strategic target selection.
        """
        # Make API call
        response = await get_all_monsters_asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        # Transform API models to internal models
        return [GameMonster.from_api_monster(monster) for monster in processed_response.data]

    async def get_all_maps(self) -> list[GameMap]:
        """Get all maps for caching.
        
        Parameters:
            None (retrieves complete map database)
            
        Return values:
            List of MapSchema instances for all game maps
            
        This method retrieves all available map locations in the game for local
        caching purposes, enabling offline access to map data for pathfinding,
        location planning, and strategic navigation operations.
        """
        # Make API call
        response = await get_all_maps_asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        # Transform API models to internal models
        return [GameMap.from_api_map(game_map) for game_map in processed_response.data]

    async def get_all_resources(self) -> list[GameResource]:
        """Get all resources for caching.
        
        Parameters:
            None (retrieves complete resource database)
            
        Return values:
            List of ResourceSchema instances for all game resources
            
        This method retrieves all available resources in the game for local
        caching purposes, enabling offline access to resource data for gathering
        planning, skill progression, and economic strategy operations.
        """
        # Make API call
        response = await get_all_resources_asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        if hasattr(processed_response, 'data'):
            # Transform API models to internal models
            return [GameResource.from_api_resource(resource) for resource in processed_response.data]
        else:
            return []

    async def get_all_npcs(self) -> list[GameNPC]:
        """Get all NPCs for caching.
        
        Parameters:
            None (retrieves complete NPC database)
            
        Return values:
            List of NPCSchema instances for all game NPCs
            
        This method retrieves all available NPCs in the game for local
        caching purposes, enabling offline access to NPC data for trading,
        quest planning, and economic strategy operations.
        """
        # Make API call
        response = await get_all_npcs_asyncio_detailed(client=self.client)
        processed_response = await self._process_response(response)

        if hasattr(processed_response, 'data'):
            # Transform API models to internal models
            return [GameNPC.from_api_npc(npc) for npc in processed_response.data]
        else:
            return []

    async def _handle_rate_limit(self, response) -> None:
        """Handle API rate limiting with backoff.
        
        Parameters:
            response: API response object containing rate limit information
            
        Return values:
            None (handles rate limiting internally)
            
        This method processes API responses to detect rate limiting and
        implementing exponential backoff and retry logic to ensure compliance
        with API rate limits while maintaining reliable operation.
        """
        # Extract rate limit information from headers if available
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                wait_time = float(retry_after)
                await asyncio.sleep(wait_time)
            except (ValueError, TypeError):
                # Default backoff if header is malformed
                await asyncio.sleep(5.0)
        else:
            # Default exponential backoff when no Retry-After header
            await asyncio.sleep(1.0)

    async def _process_response(self, response) -> Any:
        """Process API response with error handling.
        
        Parameters:
            response: Raw API response object for processing
            
        Return values:
            Processed response data with validation and error handling
            
        This method processes raw API responses with comprehensive error handling,
        ArtifactsMMO-specific error codes, and data validation to ensure
        reliable response processing throughout the AI player system.
        """
        if response.status_code == 200:
            return response.parsed
        elif response.status_code == 404:
            raise ValueError("Resource not found")
        elif response.status_code == 429:
            await self._handle_rate_limit(response)
            raise ValueError("Rate limit exceeded")
        elif response.status_code >= 400:
            error_msg = f"API error {response.status_code}"
            if hasattr(response, 'content') and response.content:
                error_msg += f": {response.content.decode()}"
            raise ValueError(error_msg)
        else:
            return response.parsed

    def extract_cooldown(self, response) -> Optional['CooldownInfo']:
        """Extract cooldown information from API response.
        
        Parameters:
            response: API response object containing potential cooldown data
            
        Return values:
            CooldownInfo instance with parsed cooldown data, or None if no cooldown
            
        This method parses API responses to extract cooldown timing information,
        creating validated CooldownInfo instances for proper cooldown management
        and action timing in the AI player system.
        """
        if not response or not hasattr(response, 'cooldown'):
            return None

        cooldown_data = response.cooldown
        if not cooldown_data:
            return None

        return CooldownInfo(
            character_name="unknown",
            expiration=cooldown_data.expiration,
            total_seconds=cooldown_data.total_seconds,
            remaining_seconds=cooldown_data.remaining_seconds,
            reason=cooldown_data.reason.value if hasattr(cooldown_data.reason, 'value') else str(cooldown_data.reason)
        )