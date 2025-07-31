"""
Inventory Data Models

This module contains all the data structures and enums used throughout
the inventory optimization system for the AI player.
"""

from dataclasses import dataclass
from enum import Enum


class ItemPriority(Enum):
    """Item priority levels for inventory management"""
    CRITICAL = "critical"      # Essential for immediate tasks
    HIGH = "high"             # Important for progression
    MEDIUM = "medium"         # Useful but not essential
    LOW = "low"              # Can be sold/stored
    JUNK = "junk"            # Should be disposed of


class InventoryAction(Enum):
    """Types of inventory management actions"""
    KEEP_INVENTORY = "keep_inventory"
    DEPOSIT_BANK = "deposit_bank"
    WITHDRAW_BANK = "withdraw_bank"
    SELL_NPC = "sell_npc"
    SELL_GE = "sell_ge"
    DELETE_ITEM = "delete_item"
    EQUIP_ITEM = "equip_item"
    UNEQUIP_ITEM = "unequip_item"
    USE_ITEM = "use_item"


@dataclass
class ItemInfo:
    """Comprehensive item information"""
    code: str
    name: str
    type: str
    level: int
    quantity: int
    slot: str | None  # inventory slot
    tradeable: bool
    craftable: bool
    consumable: bool
    stackable: bool
    value: int  # Base NPC value
    market_value: int | None = None  # Current market value

    @property
    def total_value(self) -> int:
        """Total value of item stack"""
        value = self.market_value or self.value
        return value * self.quantity


@dataclass
class InventoryState:
    """Current inventory state snapshot"""
    items: list[ItemInfo]
    max_slots: int
    used_slots: int
    total_value: int
    weight: int
    max_weight: int

    @property
    def free_slots(self) -> int:
        """Number of free inventory slots"""
        return self.max_slots - self.used_slots

    @property
    def is_full(self) -> bool:
        """Check if inventory is full"""
        return self.used_slots >= self.max_slots

    @property
    def space_utilization(self) -> float:
        """Inventory space utilization percentage"""
        return (self.used_slots / self.max_slots) * 100


@dataclass
class BankState:
    """Current bank state snapshot"""
    items: list[ItemInfo]
    max_slots: int
    used_slots: int
    total_value: int
    gold: int

    @property
    def free_slots(self) -> int:
        """Number of free bank slots"""
        return self.max_slots - self.used_slots


@dataclass
class OptimizationRecommendation:
    """Inventory optimization recommendation"""
    action: InventoryAction
    item_code: str
    quantity: int
    reasoning: str
    priority: ItemPriority
    estimated_benefit: float
    risk_level: float
