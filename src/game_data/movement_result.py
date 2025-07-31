"""
Movement Result Model

Internal Pydantic model for movement action results, enforcing model boundary
separation from API client schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from .cooldown_info import CooldownInfo


class MovementResult(BaseModel):
    """Internal model for movement action results."""
    
    x: int = Field(..., description="Final X coordinate after movement")
    y: int = Field(..., description="Final Y coordinate after movement") 
    cooldown: Optional[CooldownInfo] = Field(None, description="Cooldown information")
    character_name: str = Field(..., description="Name of character that moved")
    
    @classmethod
    def from_api_movement_response(cls, api_response, character_name: str) -> 'MovementResult':
        """Transform API movement response to internal model.
        
        Parameters:
            api_response: ActionMoveSchema from API client
            character_name: Name of the character
            
        Returns:
            MovementResult with extracted position and cooldown data
        """
        # Extract character position from API response
        character_data = api_response.character
        x = character_data.x
        y = character_data.y
        
        # Extract cooldown information
        cooldown_info = None
        if hasattr(api_response, 'cooldown') and api_response.cooldown:
            cooldown_info = CooldownInfo(
                character_name=character_name,
                expiration=api_response.cooldown.expiration.isoformat() if hasattr(api_response.cooldown.expiration, 'isoformat') else str(api_response.cooldown.expiration),
                total_seconds=api_response.cooldown.total_seconds,
                remaining_seconds=api_response.cooldown.remaining_seconds,
                reason=api_response.cooldown.reason.value if hasattr(api_response.cooldown.reason, 'value') else str(api_response.cooldown.reason)
            )
        
        return cls(
            x=x,
            y=y,
            cooldown=cooldown_info,
            character_name=character_name
        )