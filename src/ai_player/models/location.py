"""
Location and Map Data Models

Pydantic models for map/location data that align with MapSchema and related
models from the artifactsmmo-api-client. Provides type safety and validation
while maintaining exact field name compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class MapContent(BaseModel):
    """Map content data aligned with MapContentSchema"""
    model_config = ConfigDict(validate_assignment=True)

    type: str  # Content type (monster, resource, workshop, etc.)
    code: str  # Content code/identifier


class MapLocation(BaseModel):
    """Map location model aligned with artifactsmmo-api-client MapSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic location info - exact field names from API
    name: str
    skin: str
    x: int
    y: int
    content: MapContent | None = None

    @classmethod
    def from_api_map(cls, api_map: Any) -> "MapLocation":
        """Create MapLocation from API MapSchema

        Args:
            api_map: MapSchema instance from artifactsmmo-api-client

        Returns:
            MapLocation instance with all fields mapped from API response
        """
        # Map content if present
        content = None
        if hasattr(api_map, 'content') and api_map.content:
            content = MapContent(
                type=api_map.content.type,
                code=api_map.content.code
            )

        return cls(
            name=api_map.name,
            skin=api_map.skin,
            x=api_map.x,
            y=api_map.y,
            content=content,
        )

    @property
    def coordinates(self) -> tuple[int, int]:
        """Get location coordinates as tuple"""
        return (self.x, self.y)

    @property
    def has_content(self) -> bool:
        """Check if location has content"""
        return self.content is not None

    @property
    def content_type(self) -> str | None:
        """Get content type if present"""
        return self.content.type if self.content else None

    @property
    def content_code(self) -> str | None:
        """Get content code if present"""
        return self.content.code if self.content else None

    @property
    def is_monster_location(self) -> bool:
        """Check if location contains a monster"""
        return self.content_type == "monster"

    @property
    def is_resource_location(self) -> bool:
        """Check if location contains a resource"""
        return self.content_type == "resource"

    @property
    def is_workshop_location(self) -> bool:
        """Check if location contains a workshop"""
        return self.content_type == "workshop"

    @property
    def is_bank_location(self) -> bool:
        """Check if location contains a bank"""
        return self.content_type == "bank"

    @property
    def is_grand_exchange_location(self) -> bool:
        """Check if location contains grand exchange"""
        return self.content_type == "grand_exchange"

    def distance_to(self, x: int, y: int) -> int:
        """Calculate Manhattan distance to coordinates

        Args:
            x: Target x coordinate
            y: Target y coordinate

        Returns:
            Manhattan distance to target coordinates
        """
        return abs(self.x - x) + abs(self.y - y)
