from typing import *

from pydantic import BaseModel, Field

from .InventorySlot import InventorySlot


class CharacterSchema(BaseModel):
    """
    CharacterSchema model

    """

    name: str = Field(alias="name")

    skin: str = Field(alias="skin")

    level: int = Field(alias="level")

    xp: int = Field(alias="xp")

    max_xp: int = Field(alias="max_xp")

    total_xp: int = Field(alias="total_xp")

    gold: int = Field(alias="gold")

    speed: int = Field(alias="speed")

    mining_level: int = Field(alias="mining_level")

    mining_xp: int = Field(alias="mining_xp")

    mining_max_xp: int = Field(alias="mining_max_xp")

    woodcutting_level: int = Field(alias="woodcutting_level")

    woodcutting_xp: int = Field(alias="woodcutting_xp")

    woodcutting_max_xp: int = Field(alias="woodcutting_max_xp")

    fishing_level: int = Field(alias="fishing_level")

    fishing_xp: int = Field(alias="fishing_xp")

    fishing_max_xp: int = Field(alias="fishing_max_xp")

    weaponcrafting_level: int = Field(alias="weaponcrafting_level")

    weaponcrafting_xp: int = Field(alias="weaponcrafting_xp")

    weaponcrafting_max_xp: int = Field(alias="weaponcrafting_max_xp")

    gearcrafting_level: int = Field(alias="gearcrafting_level")

    gearcrafting_xp: int = Field(alias="gearcrafting_xp")

    gearcrafting_max_xp: int = Field(alias="gearcrafting_max_xp")

    jewelrycrafting_level: int = Field(alias="jewelrycrafting_level")

    jewelrycrafting_xp: int = Field(alias="jewelrycrafting_xp")

    jewelrycrafting_max_xp: int = Field(alias="jewelrycrafting_max_xp")

    cooking_level: int = Field(alias="cooking_level")

    cooking_xp: int = Field(alias="cooking_xp")

    cooking_max_xp: int = Field(alias="cooking_max_xp")

    hp: int = Field(alias="hp")

    haste: int = Field(alias="haste")

    critical_strike: int = Field(alias="critical_strike")

    stamina: int = Field(alias="stamina")

    attack_fire: int = Field(alias="attack_fire")

    attack_earth: int = Field(alias="attack_earth")

    attack_water: int = Field(alias="attack_water")

    attack_air: int = Field(alias="attack_air")

    dmg_fire: int = Field(alias="dmg_fire")

    dmg_earth: int = Field(alias="dmg_earth")

    dmg_water: int = Field(alias="dmg_water")

    dmg_air: int = Field(alias="dmg_air")

    res_fire: int = Field(alias="res_fire")

    res_earth: int = Field(alias="res_earth")

    res_water: int = Field(alias="res_water")

    res_air: int = Field(alias="res_air")

    x: int = Field(alias="x")

    y: int = Field(alias="y")

    cooldown: int = Field(alias="cooldown")

    cooldown_expiration: Optional[str] = Field(
        alias="cooldown_expiration", default=None
    )

    weapon_slot: str = Field(alias="weapon_slot")

    shield_slot: str = Field(alias="shield_slot")

    helmet_slot: str = Field(alias="helmet_slot")

    body_armor_slot: str = Field(alias="body_armor_slot")

    leg_armor_slot: str = Field(alias="leg_armor_slot")

    boots_slot: str = Field(alias="boots_slot")

    ring1_slot: str = Field(alias="ring1_slot")

    ring2_slot: str = Field(alias="ring2_slot")

    amulet_slot: str = Field(alias="amulet_slot")

    artifact1_slot: str = Field(alias="artifact1_slot")

    artifact2_slot: str = Field(alias="artifact2_slot")

    artifact3_slot: str = Field(alias="artifact3_slot")

    consumable1_slot: str = Field(alias="consumable1_slot")

    consumable1_slot_quantity: int = Field(alias="consumable1_slot_quantity")

    consumable2_slot: str = Field(alias="consumable2_slot")

    consumable2_slot_quantity: int = Field(alias="consumable2_slot_quantity")

    task: str = Field(alias="task")

    task_type: str = Field(alias="task_type")

    task_progress: int = Field(alias="task_progress")

    task_total: int = Field(alias="task_total")

    inventory_max_items: int = Field(alias="inventory_max_items")

    inventory: Optional[List[Optional[InventorySlot]]] = Field(
        alias="inventory", default=None
    )
