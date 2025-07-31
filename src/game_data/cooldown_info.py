"""
Cooldown Information Model

This module defines the CooldownInfo Pydantic model for character cooldown
tracking throughout the AI player system.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class CooldownInfo(BaseModel):
    """Pydantic model for cooldown information"""
    character_name: str
    expiration: str  # datetime as string
    total_seconds: int = Field(ge=0)
    remaining_seconds: int = Field(ge=0)
    reason: str

    @property
    def is_ready(self) -> bool:
        """Check if cooldown has expired.

        Parameters:
            None (property operates on self)

        Return values:
            Boolean indicating whether the character cooldown has expired

        This property compares the current time with the cooldown expiration time
        to determine if the character is ready to perform actions, enabling
        cooldown-aware planning and execution.
        """
        try:
            expiration_time = datetime.fromisoformat(self.expiration.replace('Z', '+00:00'))
            return datetime.now(expiration_time.tzinfo) >= expiration_time
        except Exception:
            # If parsing fails, use remaining_seconds
            return self.remaining_seconds <= 0

    @property
    def time_remaining(self) -> float:
        """Get remaining cooldown time in seconds.

        Parameters:
            None (property operates on self)

        Return values:
            Float representing seconds remaining until cooldown expires (0.0 if ready)

        This property calculates the exact remaining cooldown time in seconds,
        providing precise timing information for action scheduling and wait
        optimization in the AI player system.
        """
        try:
            expiration_time = datetime.fromisoformat(self.expiration.replace('Z', '+00:00'))
            current_time = datetime.now(expiration_time.tzinfo)
            remaining = (expiration_time - current_time).total_seconds()
            return max(0.0, round(remaining, 6))
        except Exception:
            # If parsing fails, use remaining_seconds
            return max(0.0, float(self.remaining_seconds))
