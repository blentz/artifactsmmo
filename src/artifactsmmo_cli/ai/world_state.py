"""World state representation for GOAP planning."""

from dataclasses import dataclass, field
from datetime import datetime

from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_api_client.types import Unset


EQUIPMENT_SLOTS = [
    "weapon_slot",
    "rune_slot",
    "shield_slot",
    "helmet_slot",
    "body_armor_slot",
    "leg_armor_slot",
    "boots_slot",
    "ring1_slot",
    "ring2_slot",
    "amulet_slot",
    "artifact1_slot",
    "artifact2_slot",
    "artifact3_slot",
    "utility1_slot",
    "utility2_slot",
    "bag_slot",
]

SKILL_NAMES = [
    "mining",
    "woodcutting",
    "fishing",
    "weaponcrafting",
    "gearcrafting",
    "jewelrycrafting",
    "cooking",
    "alchemy",
]


@dataclass(frozen=True)
class WorldState:
    """Frozen snapshot of game state used by the GOAP planner."""

    character: str
    level: int
    xp: int
    max_xp: int
    hp: int
    max_hp: int
    gold: int
    skills: dict[str, int]           # skill_name -> level
    x: int
    y: int
    inventory: dict[str, int]        # item_code -> quantity
    inventory_max: int               # max total item quantity (not unique stacks)
    equipment: dict[str, str | None] # slot -> item_code | None
    cooldown_expires: datetime | None
    task_code: str | None
    task_type: str | None            # "monsters", "resources", "crafting"
    task_progress: int
    task_total: int
    bank_items: dict[str, int] | None  # None = not yet visited
    bank_gold: int | None
    pending_items: tuple[tuple[str, str], ...] | None  # ((id, code), ...) | None = not yet fetched
    # skill_name -> current XP within level. Default empty so callers that don't
    # need skill-XP attribution (most action.apply paths) keep working. Filled
    # from `<skill>_xp` on the API schema by from_character_schema.
    skill_xp: dict[str, int] = field(default_factory=dict)

    @property
    def inventory_used(self) -> int:
        """Total item count across all stacks."""
        return sum(self.inventory.values())

    @property
    def inventory_free(self) -> int:
        """Remaining item capacity (inventory_max minus total item count)."""
        return self.inventory_max - self.inventory_used

    @property
    def hp_percent(self) -> float:
        """Current HP as a fraction of max HP."""
        if self.max_hp == 0:
            return 1.0
        return self.hp / self.max_hp

    @classmethod
    def from_character_schema(
        cls,
        char: CharacterSchema,
        bank_items: dict[str, int] | None = None,
        bank_gold: int | None = None,
        pending_items: "tuple[tuple[str, str], ...] | None" = None,
    ) -> "WorldState":
        """Build WorldState from a CharacterSchema API response."""
        inventory: dict[str, int] = {}
        if not isinstance(char.inventory, Unset) and char.inventory:
            for slot in char.inventory:
                if slot.code and slot.quantity > 0:
                    inventory[slot.code] = inventory.get(slot.code, 0) + slot.quantity

        equipment: dict[str, str | None] = {}
        for slot_name in EQUIPMENT_SLOTS:
            val = getattr(char, slot_name, "")
            equipment[slot_name] = val if val else None

        skills: dict[str, int] = {}
        skill_xp: dict[str, int] = {}
        for skill in SKILL_NAMES:
            skills[skill] = getattr(char, f"{skill}_level", 1)
            skill_xp[skill] = getattr(char, f"{skill}_xp", 0)

        cooldown_expires: datetime | None = None
        if not isinstance(char.cooldown_expiration, Unset) and char.cooldown_expiration:
            cooldown_expires = char.cooldown_expiration

        return cls(
            character=char.name,
            level=char.level,
            xp=char.xp,
            max_xp=char.max_xp,
            hp=char.hp,
            max_hp=char.max_hp,
            gold=char.gold,
            skills=skills,
            skill_xp=skill_xp,
            x=char.x,
            y=char.y,
            inventory=inventory,
            inventory_max=char.inventory_max_items,
            equipment=equipment,
            cooldown_expires=cooldown_expires,
            task_code=char.task if char.task else None,
            task_type=char.task_type if char.task_type else None,
            task_progress=char.task_progress,
            task_total=char.task_total,
            bank_items=bank_items,
            bank_gold=bank_gold,
            pending_items=pending_items,
        )
