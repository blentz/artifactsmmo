"""
State Manager

This module manages game state synchronization between the API and the GOAP system.
It ensures that character state is always current and properly formatted using
the GameState enum for type safety.

The StateManager is responsible for fetching character state from the API,
converting it to the internal GameState format, and maintaining state consistency
throughout the AI player operation.
"""

from datetime import datetime
from typing import Any, Optional

from ...game_data.api_client import APIClientWrapper
from ...game_data.cache_manager import CacheManager
from ...lib.yaml_data import YamlData
from .game_state import ActionResult, CharacterGameState, GameState


class StateManager:
    """Manages character state synchronization with API using GameState enum"""

    def __init__(self, character_name: str, api_client: APIClientWrapper, cache_manager: Optional[CacheManager] = None):
        """Initialize StateManager for character state synchronization.
        
        Parameters:
            character_name: Name of the character to manage state for
            api_client: API client wrapper for game data operations
            cache_manager: Cache manager for centralized character data access
            
        Return values:
            None (constructor)
            
        This constructor initializes the StateManager with the specified character
        and API client, using the centralized characters.yaml file for state
        management instead of individual character files.
        """
        self.character_name = character_name
        self.api_client = api_client
        self._cached_state: CharacterGameState | None = None
        self._cache_manager = cache_manager
        # Use centralized characters.yaml file for state data
        self._characters_cache = YamlData("data/characters.yaml")

    async def get_current_state(self) -> CharacterGameState:
        """Fetch current character state from cache or API using GameState enum.
        
        Parameters:
            None
            
        Return values:
            CharacterGameState instance with current character state
            
        This method retrieves character state from cache if available, otherwise
        fetches from the API, converts it to the internal GameState enum format,
        and returns a type-safe state dictionary for GOAP planning operations.
        """
        # Get fresh state from API (cache can be optimized later)
        self._cached_state = await self.update_state_from_api()
        return self._cached_state

    async def update_state_from_api(self) -> CharacterGameState:
        """Sync character state from API with Pydantic validation.
        
        Parameters:
            None
            
        Return values:
            CharacterGameState instance with validated API data
            
        This method fetches the latest character data from the API and creates
        a validated CharacterGameState instance using Pydantic models, ensuring
        data integrity and type safety for state operations.
        """
        # Get raw API character schema
        api_character = await self.api_client.get_character(self.character_name)
        
        # Update cooldown manager with character data
        self.api_client.cooldown_manager.update_from_character(api_character)
        
        # Get map content for current location to set location flags correctly
        game_map = await self.api_client.get_map(api_character.x, api_character.y)
        
        # Load nearby maps dynamically based on character position
        if self._cache_manager:
            await self._cache_manager.load_nearby_maps(api_character.x, api_character.y, radius=5)
        
        # Transform to internal model at the boundary with location context
        character_state = CharacterGameState.from_api_character(api_character, game_map.content, self.api_client.cooldown_manager)
        return character_state

    def update_state_from_result(self, action_result: ActionResult) -> None:
        """Update local state from action execution result.
        
        Parameters:
            action_result: ActionResult containing state changes from executed action
            
        Return values:
            None (modifies internal state)
            
        This method applies the state changes from a completed action to the
        local state cache, keeping the state synchronized without requiring
        additional API calls after each action execution.
        """
        if self._cached_state is None:
            self._cached_state = {}

        # Check if position will change to update location flags
        position_changed = (
            GameState.CURRENT_X in action_result.state_changes or 
            GameState.CURRENT_Y in action_result.state_changes
        )

        # Apply all state changes from the action result
        for state_key, new_value in action_result.state_changes.items():
            self._cached_state[state_key] = new_value

        # Update location flags if position changed
        if position_changed:
            self._update_location_flags_async()

        # Update cooldown state if action result indicates a cooldown
        if action_result.cooldown_seconds > 0:
            self._cached_state[GameState.COOLDOWN_READY] = False
            # Update dependent action availability states
            self._cached_state[GameState.CAN_FIGHT] = False
            self._cached_state[GameState.CAN_GATHER] = False
            self._cached_state[GameState.CAN_CRAFT] = False
            self._cached_state[GameState.CAN_TRADE] = False
            self._cached_state[GameState.CAN_MOVE] = False
            self._cached_state[GameState.CAN_REST] = False
            self._cached_state[GameState.CAN_USE_ITEM] = False
            self._cached_state[GameState.CAN_BANK] = False

    def _update_location_flags_async(self) -> None:
        """Update location flags based on current position - schedules async update.
        
        This method schedules an async update of location flags based on the character's
        current position by checking map content. It's called after position changes
        to ensure location flags remain accurate for GOAP planning.
        """
        # Get current position from cached state
        current_x = self._cached_state.get(GameState.CURRENT_X, 0)
        current_y = self._cached_state.get(GameState.CURRENT_Y, 0)
        
        # Create a task to update location flags asynchronously
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # Schedule the async update
            loop.create_task(self._update_location_flags(current_x, current_y))
        except RuntimeError:
            # No event loop running, location flags will be updated on next API sync
            pass

    async def _update_location_flags(self, x: int, y: int) -> None:
        """Update location flags based on map content at specified coordinates.
        
        Parameters:
            x: X coordinate to check
            y: Y coordinate to check
            
        This method fetches map content at the specified coordinates and updates
        the cached state with appropriate location flags for GOAP planning.
        """
        try:
            # Get map content at the new position
            map_data = await self.api_client.get_map(x, y)
            
            # Reset all location flags
            self._cached_state[GameState.AT_MONSTER_LOCATION] = False
            self._cached_state[GameState.AT_RESOURCE_LOCATION] = False
            self._cached_state[GameState.AT_SAFE_LOCATION] = True
            self._cached_state[GameState.XP_SOURCE_AVAILABLE] = False
            
            # Set appropriate flags based on map content
            if map_data.content:
                if map_data.content.type == "monster":
                    self._cached_state[GameState.AT_MONSTER_LOCATION] = True
                    self._cached_state[GameState.AT_SAFE_LOCATION] = False
                    self._cached_state[GameState.XP_SOURCE_AVAILABLE] = True
                elif map_data.content.type == "resource":
                    self._cached_state[GameState.AT_RESOURCE_LOCATION] = True
                    self._cached_state[GameState.XP_SOURCE_AVAILABLE] = True
                elif map_data.content.type == "workshop":
                    self._cached_state[GameState.XP_SOURCE_AVAILABLE] = True
                    
        except Exception:
            # If map lookup fails, location flags will be updated on next API sync
            pass

    def get_cached_state(self) -> dict[GameState, Any]:
        """Get locally cached state using GameState enum.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys and cached state values
            
        This method retrieves the character state from local cache without
        making API calls, providing fast access to the most recently known
        state for GOAP planning and decision making.
        """
        if self._cached_state is None:
            # Try to load from file cache
            cached = self.load_state_from_cache()
            if cached is not None:
                self._cached_state = cached
            else:
                return {}
        return self._cached_state.copy()

    async def validate_state_consistency(self, state: dict[GameState, Any] | None = None) -> bool:
        """Verify state consistency - either validates provided state against rules, or compares cached vs API state.
        
        Parameters:
            state: Optional state dictionary to validate against rules; if None, compares cached vs API state
            
        Return values:
            Boolean indicating whether state is consistent and valid
            
        When state is provided: validates that state against game rules and constraints.
        When state is None: compares cached state with fresh API data for consistency.
        """
        if state is not None:
            # Validate provided state against game rules
            return self._validate_state_rules(state)
        else:
            # Compare cached state with fresh API state
            return await self._validate_cache_vs_api()

    def _validate_state_rules(self, target_state: dict[GameState, Any]) -> bool:
        """Validate state against game rules and constraints."""
        if target_state is None:
            return False

        try:
            # Validate HP consistency
            hp_current = target_state.get(GameState.HP_CURRENT)
            hp_max = target_state.get(GameState.HP_MAX)
            if hp_current is not None and hp_max is not None:
                if hp_current < 0 or hp_current > hp_max:
                    return False

            # Validate levels are non-negative
            level_keys = [
                GameState.CHARACTER_LEVEL,
                GameState.MINING_LEVEL,
                GameState.WOODCUTTING_LEVEL,
                GameState.FISHING_LEVEL,
                GameState.WEAPONCRAFTING_LEVEL,
                GameState.GEARCRAFTING_LEVEL,
                GameState.JEWELRYCRAFTING_LEVEL,
                GameState.COOKING_LEVEL,
                GameState.ALCHEMY_LEVEL,
            ]

            for level_key in level_keys:
                level_value = target_state.get(level_key)
                if level_value is not None and level_value < 0:
                    return False

            # Validate inventory consistency
            inv_available = target_state.get(GameState.INVENTORY_SPACE_AVAILABLE)
            inv_used = target_state.get(GameState.INVENTORY_SPACE_USED)
            if inv_available is not None and inv_used is not None:
                if inv_available < 0 or inv_used < 0:
                    return False

            # Validate skill levels aren't unreasonably high compared to character level
            char_level = target_state.get(GameState.CHARACTER_LEVEL)
            if char_level is not None:
                max_skill_level = char_level + 10  # Allow some buffer
                for level_key in level_keys[1:]:  # Skip CHARACTER_LEVEL
                    skill_level = target_state.get(level_key)
                    if skill_level is not None and skill_level > max_skill_level:
                        return False

            return True

        except Exception:
            # If validation fails, assume inconsistency
            return False

    async def _validate_cache_vs_api(self) -> bool:
        """Compare cached state with fresh API state for consistency."""
        if self._cached_state is None:
            return False

        try:
            # Save the current cached state
            saved_cache = self._cached_state.copy()

            # Clear cache temporarily to force API fetch
            self._cached_state = None

            # Get fresh state from API
            fresh_state = await self.get_current_state()

            # Restore the original cached state
            self._cached_state = saved_cache

            # Compare critical state values (not all, to avoid minor fluctuations)
            critical_keys = [
                GameState.CHARACTER_LEVEL,
                GameState.HP_CURRENT,
                GameState.CURRENT_X,
                GameState.CURRENT_Y,
                GameState.CHARACTER_GOLD,
                GameState.COOLDOWN_READY,
            ]

            for key in critical_keys:
                if self._cached_state.get(key) != fresh_state.get(key):
                    return False

            return True
        except Exception:
            # If API call fails, assume inconsistency
            return False

    async def force_refresh(self) -> dict[GameState, Any]:
        """Force refresh state from API.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys and refreshed state values
            
        This method bypasses any caching and forces a fresh state retrieval
        from the API, useful for error recovery or when state consistency
        issues are detected.
        """
        # Clear cached state to force fresh fetch
        self._cached_state = None

        # Fetch fresh data directly from API (bypass cache)
        character_state = await self.update_state_from_api()
        state_dict = character_state.to_goap_state()
        fresh_state = GameState.validate_state_dict(state_dict)

        # Update cached state with fresh data
        self._cached_state = fresh_state

        # Save the fresh state to cache
        self.save_state_to_cache(fresh_state)
        return fresh_state
    
    def update_cooldown_state(self) -> None:
        """Update action availability based on cooldown status.
        
        This method checks if the character's cooldown has expired and re-enables
        all action capabilities when the cooldown is ready, fixing the issue where
        actions remain permanently disabled after cooldown.
        """
        if self._cached_state is None:
            return
            
        # Check if cooldown is ready
        cooldown_ready = self._cached_state.get(GameState.COOLDOWN_READY, True)
        
        if cooldown_ready:
            # Re-enable all action capabilities when cooldown is ready
            self._cached_state[GameState.CAN_FIGHT] = True
            self._cached_state[GameState.CAN_GATHER] = True
            self._cached_state[GameState.CAN_CRAFT] = True
            self._cached_state[GameState.CAN_TRADE] = True
            self._cached_state[GameState.CAN_MOVE] = True
            self._cached_state[GameState.CAN_REST] = True
            self._cached_state[GameState.CAN_USE_ITEM] = True
            self._cached_state[GameState.CAN_BANK] = True

    def save_state_to_cache(self, state: dict[GameState, Any]) -> None:
        """Save state to centralized characters.yaml cache.
        
        Parameters:
            state: Dictionary with GameState enum keys and state values to cache
            
        Return values:
            None (writes to cache file)
            
        This method updates the character's data in the centralized characters.yaml
        file, maintaining consistency with the existing data structure used by
        the CLI and cache manager.
        """
        # Convert GameState enum keys to strings for YAML serialization
        serializable_state = {key.value: value for key, value in state.items()}

        # Find and update character in centralized data
        if self._characters_cache.data and 'data' in self._characters_cache.data:
            characters = self._characters_cache.data['data']
            for i, character in enumerate(characters):
                if character.get('name') == self.character_name:
                    # Update character data with new state
                    characters[i].update(serializable_state)
                    self._characters_cache.save()
                    return
        
        # If character not found, this is an error condition
        # The character should already exist in the centralized file

    def load_state_from_cache(self) -> dict[GameState, Any] | None:
        """Load state from centralized characters.yaml cache.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys and cached values, or None if no cache
            
        This method loads character state from the centralized characters.yaml file,
        finding the specific character's data and converting it to GameState enum
        format for use by the GOAP planning system.
        """
        # Load character data from centralized characters.yaml file
        if not self._characters_cache.data or 'data' not in self._characters_cache.data:
            return None
            
        characters = self._characters_cache.data['data']
        
        # Find the character by name
        character_data = None
        for character in characters:
            if character.get('name') == self.character_name:
                character_data = character
                break
                
        if not character_data:
            return None

        # Convert character data to GameState enum format
        try:
            return GameState.validate_state_dict(character_data)
        except ValueError:
            # Invalid character data, return None
            return None

    def convert_api_to_goap_state(self, character: Any) -> dict[GameState, Any]:
        """Convert API character data to GOAP state dict using GameState enum.
        
        Parameters:
            character: CharacterSchema object from API response
            
        Return values:
            Dictionary with GameState enum keys and converted character data
            
        This method transforms raw API character data into the internal
        GOAP-compatible state format using GameState enum keys, enabling
        seamless integration with the planning system.
        """
        # Create state dict using GameState enum keys
        state_dict = {
            # Character progression
            GameState.CHARACTER_LEVEL: character.level,
            GameState.CHARACTER_XP: character.xp,
            GameState.CHARACTER_GOLD: character.gold,
            GameState.HP_CURRENT: character.hp,
            GameState.HP_MAX: character.max_hp,

            # Position
            GameState.CURRENT_X: character.x,
            GameState.CURRENT_Y: character.y,

            # Skills
            GameState.MINING_LEVEL: character.mining_level,
            GameState.MINING_XP: character.mining_xp,
            GameState.WOODCUTTING_LEVEL: character.woodcutting_level,
            GameState.WOODCUTTING_XP: character.woodcutting_xp,
            GameState.FISHING_LEVEL: character.fishing_level,
            GameState.FISHING_XP: character.fishing_xp,
            GameState.WEAPONCRAFTING_LEVEL: character.weaponcrafting_level,
            GameState.WEAPONCRAFTING_XP: character.weaponcrafting_xp,
            GameState.GEARCRAFTING_LEVEL: character.gearcrafting_level,
            GameState.GEARCRAFTING_XP: character.gearcrafting_xp,
            GameState.JEWELRYCRAFTING_LEVEL: character.jewelrycrafting_level,
            GameState.JEWELRYCRAFTING_XP: character.jewelrycrafting_xp,
            GameState.COOKING_LEVEL: character.cooking_level,
            GameState.COOKING_XP: character.cooking_xp,
            GameState.ALCHEMY_LEVEL: character.alchemy_level,
            GameState.ALCHEMY_XP: character.alchemy_xp,

            # Equipment
            GameState.WEAPON_EQUIPPED: character.weapon_slot,
            GameState.HELMET_EQUIPPED: character.helmet_slot,
            GameState.BODY_ARMOR_EQUIPPED: character.body_armor_slot,
            GameState.LEG_ARMOR_EQUIPPED: character.leg_armor_slot,
            GameState.BOOTS_EQUIPPED: character.boots_slot,
            GameState.RING1_EQUIPPED: character.ring1_slot,
            GameState.RING2_EQUIPPED: character.ring2_slot,
            GameState.AMULET_EQUIPPED: character.amulet_slot,

            # Inventory and capacity
            GameState.INVENTORY_SPACE_AVAILABLE: character.inventory_max_items - len(getattr(character, 'inventory', [])),
            GameState.INVENTORY_SPACE_USED: len(getattr(character, 'inventory', [])),
            GameState.INVENTORY_FULL: len(getattr(character, 'inventory', [])) >= character.inventory_max_items,

            # Tasks
            GameState.ACTIVE_TASK: character.task if character.task else "",
            GameState.TASK_PROGRESS: character.task_progress,
            GameState.TASK_COMPLETED: character.task_progress >= character.task_total if character.task_total > 0 else False,

            # Action availability
            GameState.COOLDOWN_READY: character.cooldown == 0,
            GameState.CAN_FIGHT: character.cooldown == 0 and character.hp > 0,
            GameState.CAN_GATHER: character.cooldown == 0,
            GameState.CAN_CRAFT: character.cooldown == 0,
            GameState.CAN_TRADE: character.cooldown == 0,
            GameState.CAN_MOVE: character.cooldown == 0,
            GameState.CAN_REST: character.cooldown == 0,
            GameState.CAN_USE_ITEM: character.cooldown == 0,
            GameState.CAN_BANK: character.cooldown == 0,

            # Combat and safety
            GameState.HP_LOW: character.hp < (character.max_hp * 0.3),
            GameState.HP_CRITICAL: character.hp < (character.max_hp * 0.1),
            GameState.SAFE_TO_FIGHT: character.hp > (character.max_hp * 0.5),
            GameState.IN_COMBAT: False,  # This would be updated from action results
        }

        return state_dict

    async def get_state_value(self, state_key: GameState) -> Any:
        """Get specific state value by GameState enum key.
        
        Parameters:
            state_key: GameState enum key for the desired state value
            
        Return values:
            The current value associated with the specified state key
            
        This method provides type-safe access to individual state values
        using GameState enum keys, enabling precise state queries for
        action precondition checking and decision making.
        """
        # Ensure we have current state
        current_state = await self.get_current_state()
        return current_state.get(state_key)

    async def set_state_value(self, state_key: GameState, value: Any) -> None:
        """Set specific state value using GameState enum key.
        
        Parameters:
            state_key: GameState enum key for the state to modify
            value: New value to assign to the specified state key
            
        Return values:
            None (modifies internal state and saves to cache)
            
        This method provides type-safe modification of individual state values
        using GameState enum keys, enabling precise state updates from
        action results and API responses.
        """
        if self._cached_state is None:
            self._cached_state = {}
        self._cached_state[state_key] = value

        # Save updated state to cache
        self.save_state_to_cache(self._cached_state)

    async def update_state(self, state_changes: dict[GameState, Any]) -> None:
        """Update local state with specific changes and save to cache.
        
        Parameters:
            state_changes: Dictionary with GameState enum keys and new values
            
        Return values:
            None (modifies internal state and saves to cache)
            
        This method applies the provided state changes to the local cache,
        validates that all keys are valid GameState enum values, and persists
        the updated state to the YAML cache for future sessions.
        """
        # Validate that all keys are GameState enum values
        for key in state_changes.keys():
            if not isinstance(key, GameState):
                raise ValueError(f"Invalid state key: {key}. Must be GameState enum value.")

        # Initialize cached state if not present
        if self._cached_state is None:
            self._cached_state = {}

        # Apply state changes
        self._cached_state.update(state_changes)

        # Save updated state to cache
        self.save_state_to_cache(self._cached_state)

    async def sync_with_api(self) -> dict[GameState, Any]:
        """Synchronize local state with API data and save to cache.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys and synchronized state values
            
        This method fetches fresh character data from the API, updates the
        local cache with the new data, and persists the synchronized state
        to the YAML cache for consistent state management.
        """
        # Get fresh state from API (bypass cache)
        character_state = await self.update_state_from_api()
        state_dict = character_state.to_goap_state()
        fresh_state = GameState.validate_state_dict(state_dict)

        # Update cached state
        self._cached_state = fresh_state

        # Save synchronized state to cache
        self.save_state_to_cache(fresh_state)

        return fresh_state

    async def apply_action_result(self, action_result: ActionResult) -> None:
        """Apply action execution result to local state and save to cache.
        
        Parameters:
            action_result: ActionResult containing state changes and cooldown info
            
        Return values:
            None (modifies internal state and saves to cache)
            
        This method processes the results from an executed action, applying
        any state changes and cooldown effects to the local cache, then
        persists the updated state for continued AI player operation.
        """
        # Apply state changes from action result
        self.update_state_from_result(action_result)

        # Save updated state to cache
        if self._cached_state is not None:
            self.save_state_to_cache(self._cached_state)

    async def refresh_state_from_api(self) -> dict[GameState, Any]:
        """Force refresh state from API, bypassing cache.
        
        Parameters:
            None
            
        Return values:
            Dictionary with GameState enum keys and refreshed state values
            
        This method bypasses all caching mechanisms to fetch the most current
        character state directly from the API, useful for error recovery or
        when cache consistency issues are detected.
        """
        return await self.force_refresh()

    def get_state_diff(self, old_state: dict[GameState, Any], new_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Calculate differences between state snapshots.
        
        Parameters:
            old_state: Dictionary with GameState enum keys and previous values
            new_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Dictionary with GameState enum keys and changed values only
            
        This method compares two state snapshots to identify which values
        have changed, enabling efficient state change detection for logging,
        debugging, and incremental state updates in the AI player.
        """
        diff = {}

        # Check for changed values in new_state
        for key, new_value in new_state.items():
            old_value = old_state.get(key)
            if old_value != new_value:
                diff[key] = new_value

        # Check for removed keys (present in old but not in new)
        for key in old_state:
            if key not in new_state:
                diff[key] = None

        return diff

    # Synchronous wrapper methods for backwards compatibility
    def get_state_value_sync(self, state_key: GameState) -> Any:
        """Synchronous wrapper for get_state_value - gets from cached state only.
        
        Parameters:
            state_key: GameState enum key for the desired state value
            
        Return values:
            The current value associated with the specified state key from cache
            
        This method provides synchronous access to cached state values only,
        without triggering API calls. For the most current state, use the async
        version which can fetch from API if needed.
        """
        if self._cached_state is None:
            return None
        return self._cached_state.get(state_key)

    def set_state_value_sync(self, state_key: GameState, value: Any) -> None:
        """Synchronous wrapper for set_state_value - modifies cache only.
        
        Parameters:
            state_key: GameState enum key for the state to modify
            value: New value to assign to the specified state key
            
        Return values:
            None (modifies internal state only)
            
        This method provides synchronous modification of cached state values
        without triggering cache save operations. For persistent updates,
        use the async version which saves to cache.
        """
        if self._cached_state is None:
            self._cached_state = {}
        self._cached_state[state_key] = value
