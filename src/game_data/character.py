"""
Character Data Model

Pydantic model for character data that aligns with CharacterSchema from
the artifactsmmo-api-client. This model provides type safety and validation
while maintaining exact field name compatibility.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InventorySlot(BaseModel):
    """Inventory slot item data"""
    model_config = ConfigDict(validate_assignment=True)

    slot: int = Field(ge=1)
    code: str
    quantity: int = Field(ge=0)  # Empty slots have quantity 0


class Character(BaseModel):
    """Character model aligned with artifactsmmo-api-client CharacterSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic character info
    name: str
    account: str
    skin: str = Field(default="men1")

    # Character progression
    level: int = Field(ge=1, le=45)
    xp: int = Field(ge=0)
    max_xp: int = Field(ge=0)
    gold: int = Field(ge=0)
    speed: int = Field(ge=0)

    # Health
    hp: int = Field(ge=0)
    max_hp: int = Field(ge=1)

    # Skills - exact field names from API
    mining_level: int = Field(ge=1, le=45)
    mining_xp: int = Field(ge=0)
    mining_max_xp: int = Field(ge=0)
    woodcutting_level: int = Field(ge=1, le=45)
    woodcutting_xp: int = Field(ge=0)
    woodcutting_max_xp: int = Field(ge=0)
    fishing_level: int = Field(ge=1, le=45)
    fishing_xp: int = Field(ge=0)
    fishing_max_xp: int = Field(ge=0)
    weaponcrafting_level: int = Field(ge=1, le=45)
    weaponcrafting_xp: int = Field(ge=0)
    weaponcrafting_max_xp: int = Field(ge=0)
    gearcrafting_level: int = Field(ge=1, le=45)
    gearcrafting_xp: int = Field(ge=0)
    gearcrafting_max_xp: int = Field(ge=0)
    jewelrycrafting_level: int = Field(ge=1, le=45)
    jewelrycrafting_xp: int = Field(ge=0)
    jewelrycrafting_max_xp: int = Field(ge=0)
    cooking_level: int = Field(ge=1, le=45)
    cooking_xp: int = Field(ge=0)
    cooking_max_xp: int = Field(ge=0)
    alchemy_level: int = Field(ge=1, le=45)
    alchemy_xp: int = Field(ge=0)
    alchemy_max_xp: int = Field(ge=0)

    # Combat stats - exact field names from API
    haste: int = Field(ge=0)
    critical_strike: int = Field(ge=0)
    wisdom: int = Field(ge=0)
    prospecting: int = Field(ge=0)
    attack_fire: int = Field(ge=0)
    attack_earth: int = Field(ge=0)
    attack_water: int = Field(ge=0)
    attack_air: int = Field(ge=0)
    dmg: int = Field(ge=0)
    dmg_fire: int = Field(ge=0)
    dmg_earth: int = Field(ge=0)
    dmg_water: int = Field(ge=0)
    dmg_air: int = Field(ge=0)
    res_fire: int = Field(ge=0)
    res_earth: int = Field(ge=0)
    res_water: int = Field(ge=0)
    res_air: int = Field(ge=0)

    # Position
    x: int
    y: int

    # Cooldown
    cooldown: int = Field(ge=0)
    cooldown_expiration: datetime | None = None

    # Equipment slots - exact field names from API
    weapon_slot: str = Field(default="")
    rune_slot: str = Field(default="")
    shield_slot: str = Field(default="")
    helmet_slot: str = Field(default="")
    body_armor_slot: str = Field(default="")
    leg_armor_slot: str = Field(default="")
    boots_slot: str = Field(default="")
    ring1_slot: str = Field(default="")
    ring2_slot: str = Field(default="")
    amulet_slot: str = Field(default="")
    artifact1_slot: str = Field(default="")
    artifact2_slot: str = Field(default="")
    artifact3_slot: str = Field(default="")
    utility1_slot: str = Field(default="")
    utility1_slot_quantity: int = Field(ge=0, default=0)
    utility2_slot: str = Field(default="")
    utility2_slot_quantity: int = Field(ge=0, default=0)
    bag_slot: str = Field(default="")

    # Task info - exact field names from API
    task: str = Field(default="")
    task_type: str = Field(default="")
    task_progress: int = Field(ge=0, default=0)
    task_total: int = Field(ge=0, default=0)

    # Inventory
    inventory_max_items: int = Field(ge=1)
    inventory: list[InventorySlot] | None = None

    @classmethod
    def from_api_character(cls, api_character: Any) -> "Character":
        """Create Character from API CharacterSchema

        Args:
            api_character: CharacterSchema instance from artifactsmmo-api-client

        Returns:
            Character instance with all fields mapped from API response
        """
        # Map inventory slots if present
        inventory_slots = None
        if hasattr(api_character, 'inventory') and api_character.inventory:
            inventory_slots = [
                InventorySlot(
                    slot=slot.slot,
                    code=slot.code,
                    quantity=slot.quantity
                )
                for slot in api_character.inventory
            ]

        # Create character with all API fields mapped
        return cls(
            name=api_character.name,
            account=api_character.account,
            skin=api_character.skin.value if hasattr(api_character.skin, 'value') else str(api_character.skin),
            level=api_character.level,
            xp=api_character.xp,
            max_xp=api_character.max_xp,
            gold=api_character.gold,
            speed=api_character.speed,
            hp=api_character.hp,
            max_hp=api_character.max_hp,
            mining_level=api_character.mining_level,
            mining_xp=api_character.mining_xp,
            mining_max_xp=api_character.mining_max_xp,
            woodcutting_level=api_character.woodcutting_level,
            woodcutting_xp=api_character.woodcutting_xp,
            woodcutting_max_xp=api_character.woodcutting_max_xp,
            fishing_level=api_character.fishing_level,
            fishing_xp=api_character.fishing_xp,
            fishing_max_xp=api_character.fishing_max_xp,
            weaponcrafting_level=api_character.weaponcrafting_level,
            weaponcrafting_xp=api_character.weaponcrafting_xp,
            weaponcrafting_max_xp=api_character.weaponcrafting_max_xp,
            gearcrafting_level=api_character.gearcrafting_level,
            gearcrafting_xp=api_character.gearcrafting_xp,
            gearcrafting_max_xp=api_character.gearcrafting_max_xp,
            jewelrycrafting_level=api_character.jewelrycrafting_level,
            jewelrycrafting_xp=api_character.jewelrycrafting_xp,
            jewelrycrafting_max_xp=api_character.jewelrycrafting_max_xp,
            cooking_level=api_character.cooking_level,
            cooking_xp=api_character.cooking_xp,
            cooking_max_xp=api_character.cooking_max_xp,
            alchemy_level=api_character.alchemy_level,
            alchemy_xp=api_character.alchemy_xp,
            alchemy_max_xp=api_character.alchemy_max_xp,
            haste=api_character.haste,
            critical_strike=api_character.critical_strike,
            wisdom=api_character.wisdom,
            prospecting=api_character.prospecting,
            attack_fire=api_character.attack_fire,
            attack_earth=api_character.attack_earth,
            attack_water=api_character.attack_water,
            attack_air=api_character.attack_air,
            dmg=api_character.dmg,
            dmg_fire=api_character.dmg_fire,
            dmg_earth=api_character.dmg_earth,
            dmg_water=api_character.dmg_water,
            dmg_air=api_character.dmg_air,
            res_fire=api_character.res_fire,
            res_earth=api_character.res_earth,
            res_water=api_character.res_water,
            res_air=api_character.res_air,
            x=api_character.x,
            y=api_character.y,
            cooldown=api_character.cooldown,
            cooldown_expiration=getattr(api_character, 'cooldown_expiration', None),
            weapon_slot=api_character.weapon_slot,
            rune_slot=api_character.rune_slot,
            shield_slot=api_character.shield_slot,
            helmet_slot=api_character.helmet_slot,
            body_armor_slot=api_character.body_armor_slot,
            leg_armor_slot=api_character.leg_armor_slot,
            boots_slot=api_character.boots_slot,
            ring1_slot=api_character.ring1_slot,
            ring2_slot=api_character.ring2_slot,
            amulet_slot=api_character.amulet_slot,
            artifact1_slot=api_character.artifact1_slot,
            artifact2_slot=api_character.artifact2_slot,
            artifact3_slot=api_character.artifact3_slot,
            utility1_slot=api_character.utility1_slot,
            utility1_slot_quantity=api_character.utility1_slot_quantity,
            utility2_slot=api_character.utility2_slot,
            utility2_slot_quantity=api_character.utility2_slot_quantity,
            bag_slot=api_character.bag_slot,
            task=api_character.task,
            task_type=api_character.task_type,
            task_progress=api_character.task_progress,
            task_total=api_character.task_total,
            inventory_max_items=api_character.inventory_max_items,
            inventory=inventory_slots,
        )

    @property
    def is_cooldown_ready(self) -> bool:
        """Check if character cooldown has expired"""
        return self.cooldown == 0

    @property
    def inventory_space_available(self) -> int:
        """Calculate available inventory space"""
        used_slots = len(self.inventory) if self.inventory else 0
        return self.inventory_max_items - used_slots

    @property
    def is_inventory_full(self) -> bool:
        """Check if inventory is full"""
        return self.inventory_space_available <= 0
