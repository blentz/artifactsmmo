"""
Resource Data Models

Pydantic models for resource data that align with ResourceSchema from
the artifactsmmo-api-client. Provides type safety and validation while
maintaining exact field name compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResourceDrop(BaseModel):
    """Resource drop data aligned with DropRateSchema"""
    model_config = ConfigDict(validate_assignment=True)

    code: str  # Item code
    rate: int = Field(ge=1, le=100000)  # Drop rate (per 100,000)
    min_quantity: int = Field(ge=1)
    max_quantity: int = Field(ge=1)


class Resource(BaseModel):
    """Resource model aligned with artifactsmmo-api-client ResourceSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic resource info - exact field names from API
    name: str
    code: str  # Unique identifier
    level: int = Field(ge=1, le=45)
    skill: str  # Required skill (mining, woodcutting, fishing)

    # Resource drops
    drops: list[ResourceDrop]

    @classmethod
    def from_api_resource(cls, api_resource: Any) -> "Resource":
        """Create Resource from API ResourceSchema

        Args:
            api_resource: ResourceSchema instance from artifactsmmo-api-client

        Returns:
            Resource instance with all fields mapped from API response
        """
        # Map drop rates
        drops = [
            ResourceDrop(
                code=drop.code,
                rate=drop.rate,
                min_quantity=drop.min_quantity,
                max_quantity=drop.max_quantity
            )
            for drop in api_resource.drops
        ]

        return cls(
            name=api_resource.name,
            code=api_resource.code,
            level=api_resource.level,
            skill=api_resource.skill,
            drops=drops,
        )

    @property
    def is_mining_resource(self) -> bool:
        """Check if resource requires mining skill"""
        return self.skill.lower() == "mining"

    @property
    def is_woodcutting_resource(self) -> bool:
        """Check if resource requires woodcutting skill"""
        return self.skill.lower() == "woodcutting"

    @property
    def is_fishing_resource(self) -> bool:
        """Check if resource requires fishing skill"""
        return self.skill.lower() == "fishing"

    @property
    def has_drops(self) -> bool:
        """Check if resource has drops"""
        return len(self.drops) > 0

    def get_drop_by_code(self, item_code: str) -> ResourceDrop | None:
        """Get drop rate for specific item code

        Args:
            item_code: Item code to search for

        Returns:
            ResourceDrop for the item, or None if not found
        """
        for drop in self.drops:
            if drop.code == item_code:
                return drop
        return None

    def can_gather_with_level(self, skill_level: int) -> bool:
        """Check if character can gather this resource

        Args:
            skill_level: Character's skill level for this resource type

        Returns:
            True if character has sufficient skill level
        """
        return skill_level >= self.level

    def get_primary_drop(self) -> ResourceDrop | None:
        """Get the primary (highest rate) drop for this resource

        Returns:
            ResourceDrop with highest drop rate, or None if no drops
        """
        if not self.drops:
            return None

        return max(self.drops, key=lambda drop: drop.rate)
