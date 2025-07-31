"""
Item Data Models

Pydantic models for item data that align with ItemSchema and related models
from the artifactsmmo-api-client. Provides type safety and validation while
maintaining exact field name compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ItemEffect(BaseModel):
    """Item effect data aligned with SimpleEffectSchema"""
    model_config = ConfigDict(validate_assignment=True)

    name: str
    value: int


class ItemCondition(BaseModel):
    """Item condition data aligned with ConditionSchema"""
    model_config = ConfigDict(validate_assignment=True)

    type: str
    skill: str | None = None
    level: int | None = None


class CraftRequirement(BaseModel):
    """Craft requirement data aligned with CraftSchema"""
    model_config = ConfigDict(validate_assignment=True)

    skill: str | None = None
    level: int | None = None
    items: list[dict[str, Any]] | None = None
    quantity: int | None = None


class Item(BaseModel):
    """Item model aligned with artifactsmmo-api-client ItemSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic item info - exact field names from API
    name: str
    code: str  # Unique identifier
    level: int = Field(ge=1)
    type_: str = Field(alias="type")  # Pydantic alias for 'type' keyword
    subtype: str
    description: str
    tradeable: bool

    # Optional item data
    conditions: list[ItemCondition] | None = None
    effects: list[ItemEffect] | None = None
    craft: CraftRequirement | None = None

    @classmethod
    def from_api_item(cls, api_item: Any) -> "Item":
        """Create Item from API ItemSchema

        Args:
            api_item: ItemSchema instance from artifactsmmo-api-client

        Returns:
            Item instance with all fields mapped from API response
        """
        # Map conditions if present
        conditions = None
        if hasattr(api_item, 'conditions') and api_item.conditions:
            conditions = [
                ItemCondition(
                    type=condition.type,
                    skill=getattr(condition, 'skill', None),
                    level=getattr(condition, 'level', None)
                )
                for condition in api_item.conditions
            ]

        # Map effects if present
        effects = None
        if hasattr(api_item, 'effects') and api_item.effects:
            effects = [
                ItemEffect(
                    name=effect.name,
                    value=effect.value
                )
                for effect in api_item.effects
            ]

        # Map craft requirements if present
        craft = None
        if hasattr(api_item, 'craft') and api_item.craft:
            craft = CraftRequirement(
                skill=getattr(api_item.craft, 'skill', None),
                level=getattr(api_item.craft, 'level', None),
                items=getattr(api_item.craft, 'items', None),
                quantity=getattr(api_item.craft, 'quantity', None)
            )

        # Handle type field (Python keyword)
        item_type = api_item.type_ if hasattr(api_item, 'type_') else getattr(api_item, 'type', '')

        return cls(
            name=api_item.name,
            code=api_item.code,
            level=api_item.level,
            type=item_type,
            subtype=api_item.subtype,
            description=api_item.description,
            tradeable=api_item.tradeable,
            conditions=conditions,
            effects=effects,
            craft=craft,
        )

    @property
    def is_weapon(self) -> bool:
        """Check if item is a weapon"""
        return self.type_ == "weapon"

    @property
    def is_tool(self) -> bool:
        """Check if item is a tool"""
        return self.type_ == "tool"

    @property
    def is_equipment(self) -> bool:
        """Check if item is equipment (weapon, armor, etc.)"""
        equipment_types = {"weapon", "helmet", "body_armor", "leg_armor", "boots", "shield", "amulet", "ring"}
        return self.type_ in equipment_types

    @property
    def is_consumable(self) -> bool:
        """Check if item is consumable"""
        return self.type_ == "consumable"

    @property
    def is_resource(self) -> bool:
        """Check if item is a resource"""
        return self.type_ == "resource"
