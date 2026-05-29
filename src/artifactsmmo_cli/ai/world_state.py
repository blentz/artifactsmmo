"""World state representation for GOAP planning."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_api_client.types import Unset

from artifactsmmo_cli.ai.missing_api_data import MissingApiData

_MISSING = object()


def _require(char: CharacterSchema, field_name: str) -> Any:
    """Return char.<field_name>, raising MissingApiData if absent or UNSET.

    The field may legitimately hold a falsy-but-present value (0, "") — that
    is returned as-is; only genuine absence/UNSET is a contract violation.
    """
    val = getattr(char, field_name, _MISSING)
    if val is _MISSING or isinstance(val, Unset):
        raise MissingApiData(f"CharacterSchema missing required field {field_name!r}")
    return val

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

ELEMENTS = ("fire", "earth", "water", "air")

TASKS_COIN_CODE = "tasks_coin"
"""The item code for task-reward coins (spent at the taskmaster exchange)."""


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
    bank_capacity: int | None = None
    """Bank slot capacity per the API; None means the bank hasn't been visited
    yet (we don't yet know capacity). Projected through
    BuyBankExpansionAction.apply (+BANK_EXPANSION_SLOTS per buy). OUTSIDE the
    Phase-4 ApplyBaseline 8-field stat contract — Action.apply may mutate it
    (only BuyBankExpansionAction does so today); every other apply preserves
    it automatically via `dataclasses.replace`."""
    skill_xp: dict[str, int] = field(default_factory=dict)
    projected_skill_xp_delta: dict[str, int] = field(default_factory=dict)
    """Per-plan-path projected skill XP delta accumulated by Gather/Craft.apply.
    This is NOT a server-snapshot baseline field — the planner mutates it
    locally so LevelSkillGoal.is_satisfied can register that the simulated plan
    has accumulated enough XP to plausibly cross a level boundary. It is OUTSIDE
    the 8-field ApplyBaseline contract (see ApplyBaseline.lean header) by
    design; the contract over `skill_xp` (server snapshot) is unaffected.
    Initialized to `{}` by `from_character_schema` — never seeded from the API
    schema."""
    wisdom: int = 0
    """Wisdom stat — factors into documented XP-per-kill formula
    (+0.1% XP per wisdom point). Defaults 0 so older WorldState
    constructions don't break."""
    active_events: dict[str, datetime] = field(default_factory=dict)
    """event code -> expiration (tz-aware). Per-cycle snapshot from
    GET /events/active. Defaults empty so constructions that don't supply it
    (and planner sims through actions that preserve it) keep working."""
    crafting_target: str | None = None
    """Item the bot is currently working to craft/upgrade toward (the committed
    UpgradeEquipment target). Set per cycle by the player. Lets
    active_gathering_skills count skills the bot gathers for self-directed
    crafting (e.g. mining copper ore for copper gear), not just the taskmaster
    task. Defaults None so other constructions keep working."""
    attack: dict[str, int] = field(default_factory=dict)
    """element -> attack value (server-computed total, base + gear). Empty by
    default so non-schema constructions keep working. From attack_{el}."""
    dmg: int = 0
    """Global damage % bonus. Applies to every element. From `dmg`."""
    dmg_elements: dict[str, int] = field(default_factory=dict)
    """element -> per-element damage % bonus. From dmg_{el}."""
    resistance: dict[str, int] = field(default_factory=dict)
    """element -> resistance %. From res_{el}."""
    critical_strike: int = 0
    """Critical-strike chance %. From `critical_strike`."""
    initiative: int = 0
    """Turn-order stat (higher acts first). From `initiative`."""

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
        bank_capacity: int | None = None,
        pending_items: "tuple[tuple[str, str], ...] | None" = None,
        active_events: dict[str, datetime] | None = None,
    ) -> "WorldState":
        """Build WorldState from a CharacterSchema API response."""
        inventory: dict[str, int] = {}
        if not isinstance(char.inventory, Unset) and char.inventory:
            for slot in char.inventory:
                if slot.code and slot.quantity > 0:
                    inventory[slot.code] = inventory.get(slot.code, 0) + slot.quantity

        equipment: dict[str, str | None] = {}
        for slot_name in EQUIPMENT_SLOTS:
            val = _require(char, slot_name)
            equipment[slot_name] = val if val else None

        skills: dict[str, int] = {}
        skill_xp: dict[str, int] = {}
        for skill in SKILL_NAMES:
            skills[skill] = _require(char, f"{skill}_level")
            skill_xp[skill] = _require(char, f"{skill}_xp")

        attack: dict[str, int] = {}
        dmg_elements: dict[str, int] = {}
        resistance: dict[str, int] = {}
        for elem in ELEMENTS:
            atk = _require(char, f"attack_{elem}")
            if atk != 0:
                attack[elem] = atk
            de = _require(char, f"dmg_{elem}")
            if de != 0:
                dmg_elements[elem] = de
            res = _require(char, f"res_{elem}")
            if res != 0:
                resistance[elem] = res

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
            wisdom=_require(char, "wisdom"),
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
            bank_capacity=bank_capacity,
            pending_items=pending_items,
            active_events=active_events or {},
            attack=attack,
            dmg=_require(char, "dmg"),
            dmg_elements=dmg_elements,
            resistance=resistance,
            critical_strike=_require(char, "critical_strike"),
            initiative=_require(char, "initiative"),
        )
