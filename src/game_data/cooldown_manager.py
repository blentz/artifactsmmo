"""
Cooldown Manager

This module manages character cooldowns with Pydantic validation for the
ArtifactsMMO AI player system. Handles timing validation and cooldown tracking.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from .cooldown_info import CooldownInfo


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

    def update_cooldown(self, character_name: str, cooldown_data: "CooldownSchema") -> None:
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
            expiration=cooldown_data.expiration.isoformat()
            if hasattr(cooldown_data.expiration, "isoformat")
            else str(cooldown_data.expiration),
            total_seconds=cooldown_data.total_seconds,
            remaining_seconds=cooldown_data.remaining_seconds,
            reason=cooldown_data.reason.value if hasattr(cooldown_data.reason, "value") else str(cooldown_data.reason),
        )
        self.character_cooldowns[character_name] = cooldown_info

    def update_from_character(self, character: Any) -> None:
        """Update cooldown from character API data.

        Parameters:
            character: CharacterSchema from API response with cooldown info

        Return values:
            None (updates internal state)
        """
        if hasattr(character, "cooldown_expiration") and character.cooldown_expiration:
            cooldown_info = CooldownInfo(
                character_name=character.name,
                expiration=character.cooldown_expiration.isoformat(),
                total_seconds=character.cooldown,
                remaining_seconds=character.cooldown,
                reason="unknown",
            )
            self.character_cooldowns[character.name] = cooldown_info
        elif character.cooldown > 0:
            # If no expiration timestamp but cooldown > 0, character is on cooldown
            expiration = datetime.now(UTC) + timedelta(seconds=character.cooldown)
            cooldown_info = CooldownInfo(
                character_name=character.name,
                expiration=expiration.isoformat(),
                total_seconds=character.cooldown,
                remaining_seconds=character.cooldown,
                reason="unknown",
            )
            self.character_cooldowns[character.name] = cooldown_info
        else:
            # Character is ready, remove any existing cooldown
            if character.name in self.character_cooldowns:
                del self.character_cooldowns[character.name]

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
            if hasattr(cooldown_info, "time_remaining"):
                remaining_time = cooldown_info.time_remaining
            else:
                remaining_time = self.get_remaining_time(character_name)
        else:
            remaining_time = self.get_remaining_time(character_name)

        if remaining_time > 0:
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
        current_time = datetime.now(UTC)  # Use UTC timezone for consistent comparison

        try:
            expiration = datetime.fromisoformat(cooldown_info.expiration.replace("Z", "+00:00"))
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

    def get_cooldown_info(self, character_name: str) -> Optional["CooldownInfo"]:
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
