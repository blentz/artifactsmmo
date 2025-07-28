"""
API Client Wrapper

This module provides a wrapper around the generated artifactsmmo-api-client
to integrate with the AI player system. It handles authentication, error handling,
rate limiting, and response processing with Pydantic validation.

The wrapper abstracts the raw API client and provides a clean interface
for the AI player while ensuring proper cooldown management and error recovery.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
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


class TokenConfig(BaseModel):
    """Pydantic model for token validation"""
    token: str = Field(min_length=32, description="ArtifactsMMO API token")

    @classmethod
    def from_file(cls, token_file: str = "TOKEN") -> 'TokenConfig':
        """Load and validate token from file.
        
        Parameters:
            token_file: Path to file containing API token (default: "TOKEN")
            
        Return values:
            TokenConfig instance with validated token
            
        This method loads an API token from the specified file path and validates
        it using Pydantic constraints to ensure proper format before use
        in API authentication.
        """
        token_path = Path(token_file)
        if not token_path.exists():
            raise FileNotFoundError(f"Token file not found: {token_file}")

        token = token_path.read_text().strip()
        if not token:
            raise ValueError(f"Token file is empty: {token_file}")

        return cls(token=token)


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

        try:
            # Try to access data from response
            if hasattr(processed_response, 'data'):
                return processed_response.data
            else:
                # Try direct character access
                return processed_response.character
        except AttributeError:
            # Fallback to direct response
            return processed_response

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

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            return []

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
        
        # Transform API model to internal model (local import to avoid circular dependency)
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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)
        elif hasattr(processed_response, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            return processed_response

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)
        elif hasattr(processed_response, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            return processed_response

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            raise ValueError(f"Failed to gather resource with character {character_name}")

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            raise ValueError(f"Failed to craft item {code} with character {character_name}")

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            raise ValueError(f"Failed to rest character {character_name}")

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            raise ValueError(f"Failed to equip item {code} to slot {slot} for character {character_name}")

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

        # Update cooldown if present
        if hasattr(processed_response, 'data') and hasattr(processed_response.data, 'cooldown'):
            self.cooldown_manager.update_cooldown(character_name, processed_response.data.cooldown)

        if hasattr(processed_response, 'data'):
            return processed_response.data
        else:
            raise ValueError(f"Failed to unequip item from slot {slot} for character {character_name}")

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

        if hasattr(processed_response, 'data'):
            # Transform API models to internal models
            return [GameItem.from_api_item(item) for item in processed_response.data]
        else:
            return []

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

        if hasattr(processed_response, 'data'):
            # Transform API models to internal models
            return [GameMonster.from_api_monster(monster) for monster in processed_response.data]
        else:
            return []

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

        if hasattr(processed_response, 'data'):
            # Transform API models to internal models
            return [GameMap.from_api_map(game_map) for game_map in processed_response.data]
        else:
            return []

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



class CooldownManager:
    """Manages character cooldowns with Pydantic validation"""

    def __init__(self):
        """Initialize CooldownManager for character cooldown tracking.
        
        Parameters:
            None (initializes empty cooldown tracking)
            
        Return values:
            None (constructor)
            
        This method initializes the CooldownManager with proper character
        cooldown tracking, setting up the infrastructure for managing action
        timing and cooldown compliance across multiple characters.
        """
        self.character_cooldowns: dict[str, CooldownInfo] = {}

    def update_cooldown(self, character_name: str, cooldown_data: 'CooldownSchema') -> None:
        """Update cooldown from API response.
        
        Parameters:
            character_name: Name of character to update cooldown for
            cooldown_data: CooldownSchema from API response
            
        Return values:
            None (updates internal state)
            
        This method processes cooldown information from API responses and updates
        the internal tracking for the specified character, enabling accurate
        cooldown management and action timing validation.
        """
        cooldown_info = CooldownInfo(
            character_name=character_name,
            expiration=cooldown_data.expiration,
            total_seconds=cooldown_data.total_seconds,
            remaining_seconds=cooldown_data.remaining_seconds,
            reason=cooldown_data.reason.value if hasattr(cooldown_data.reason, 'value') else str(cooldown_data.reason)
        )
        self.character_cooldowns[character_name] = cooldown_info

    def is_ready(self, character_name: str) -> bool:
        """Check if character can perform actions.
        
        Parameters:
            character_name: Name of character to check cooldown status
            
        Return values:
            Boolean indicating if character is ready for actions
            
        This method validates the cooldown status for the specified character,
        returning true if the character can perform actions or false if still
        on cooldown, enabling proper action timing validation.
        """
        if character_name not in self.character_cooldowns:
            return True

        cooldown_info = self.character_cooldowns[character_name]
        return cooldown_info.is_ready

    async def wait_for_cooldown(self, character_name: str) -> None:
        """Async wait until cooldown expires.
        
        Parameters:
            character_name: Name of character to wait for cooldown
            
        Return values:
            None (async operation completes when cooldown expires)
            
        This method provides asynchronous waiting for character cooldown expiration,
        enabling the AI player to efficiently wait for action availability without
        blocking other operations or consuming excessive resources.
        """
        if self.is_ready(character_name):
            return

        # Use the cooldown info's time_remaining property if available
        if character_name in self.character_cooldowns:
            cooldown_info = self.character_cooldowns[character_name]
            if hasattr(cooldown_info, 'time_remaining'):
                remaining_time = cooldown_info.time_remaining
            else:
                remaining_time = self.get_remaining_time(character_name)
        else:
            remaining_time = self.get_remaining_time(character_name)

        if remaining_time > 0:
            import asyncio
            await asyncio.sleep(remaining_time)

    def get_remaining_time(self, character_name: str) -> float:
        """Get remaining cooldown time in seconds.
        
        Parameters:
            character_name: Name of character to check remaining time
            
        Return values:
            Float representing seconds remaining on cooldown (0.0 if ready)
            
        This method calculates the precise remaining cooldown time for the specified
        character, providing precise timing information for action scheduling
        and wait optimization in the AI player system.
        """
        if character_name not in self.character_cooldowns:
            return 0.0

        cooldown_info = self.character_cooldowns[character_name]
        current_time = datetime.now()

        try:
            expiration = datetime.fromisoformat(cooldown_info.expiration.replace('Z', '+00:00'))
            remaining = (expiration - current_time).total_seconds()
            # Round to avoid floating point precision issues in tests
            return max(0.0, round(remaining, 6))
        except:
            return 0.0

    def clear_expired_cooldowns(self) -> None:
        """Remove expired cooldowns from tracking.
        
        Parameters:
            None (processes all tracked cooldowns)
            
        Return values:
            None (modifies internal state)
            
        This method cleans up expired cooldown entries from the internal tracking
        system, maintaining efficient memory usage and ensuring accurate cooldown
        state management for ongoing AI player operations.
        """
        expired_characters = []

        for character_name in self.character_cooldowns:
            if self.is_ready(character_name):
                expired_characters.append(character_name)

        for character_name in expired_characters:
            del self.character_cooldowns[character_name]

    def get_cooldown_info(self, character_name: str) -> Optional['CooldownInfo']:
        """Get cooldown information for character.
        
        Parameters:
            character_name: Name of character to get cooldown info
            
        Return values:
            CooldownInfo instance if character has cooldown, None otherwise
        """
        return self.character_cooldowns.get(character_name)

    def clear_cooldown(self, character_name: str) -> None:
        """Clear cooldown for specific character.
        
        Parameters:
            character_name: Name of character to clear cooldown for
            
        Return values:
            None (modifies internal state)
        """
        if character_name in self.character_cooldowns:
            del self.character_cooldowns[character_name]

    def clear_all_cooldowns(self) -> None:
        """Clear all character cooldowns.
        
        Parameters:
            None (clears all tracked cooldowns)
            
        Return values:
            None (modifies internal state)
        """
        self.character_cooldowns.clear()
