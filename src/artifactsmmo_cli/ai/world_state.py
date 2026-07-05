"""World state representation for GOAP planning."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import attrs

from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill
from artifactsmmo_api_client.types import Unset

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.missing_api_data import MissingApiData
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_cli.ai.task_lifecycle import (
    TaskLifecyclePhase,
    derive_task_lifecycle_phase,
)

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

# Every equippable slot is a CharacterSchema `*_slot` field; derive the list
# from the schema (in field order) rather than hand-typing it, so a slot the
# server adds is tracked on client regen.
EQUIPMENT_SLOTS = [
    f.name for f in attrs.fields(CharacterSchema) if f.name.endswith("_slot")
]

# The character's trainable skills are the API schema's craft + gathering skills
# (CraftSkill ∪ GatheringSkill = the 8 today), derived from the enums rather than
# hand-typed so a skill the server adds is tracked on client regen. `combat` xp
# is handled separately (not a craft/gather skill). The order is the schema
# vocabulary sorted for determinism; every consumer keys by name / uses len, and
# the formal objective reductions (gapSum/targetSum) are permutation-invariant,
# so the order is not behaviourally load-bearing.
SKILL_NAMES = sorted(
    {s.value for s in CraftSkill} | {s.value for s in GatheringSkill}
)

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
    raids: list[RaidInfo] = field(default_factory=list)
    """Live raid snapshot. Per-cycle, from GET /raids. Defaults empty so
    constructions that don't supply it keep working (visibility only —
    no planner consumer in this task)."""
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
    task_lifecycle_phase: TaskLifecyclePhase = TaskLifecyclePhase.NONE
    """Phase of the taskmaster task pipeline (Phase 23c-1).

    DERIVED from (task_code, task_progress, task_total) via
    :func:`derive_task_lifecycle_phase` but STORED so it is a first-class
    field of State (Phase 23c-2 Lean will reference it). The invariant is
    enforced by :meth:`__post_init__` — direct construction with a phase
    that disagrees with the raw fields raises ``AssertionError``. Action
    ``apply`` methods that mutate task_code/task_progress/task_total MUST
    also pass an appropriate ``task_lifecycle_phase`` to
    ``dataclasses.replace`` (or it will keep the stale phase and trip the
    invariant on next replace through ``__post_init__``)."""
    utility1_slot_quantity: int = 0
    """Quantity of the consumable in utility slot 1 (from CharacterSchema)."""
    utility2_slot_quantity: int = 0
    layer: str = "overworld"
    """Map layer the character stands on (overworld/underground/interior) —
    P5b movement (docs/PLAN_multilayer_nav.md). Defaults overworld so older
    constructions keep working; access-REGION identity is derived at use time
    via GameData.region_of (restricted tiles partition further than layers)."""
    """Quantity of the consumable in utility slot 2 (from CharacterSchema)."""

    def __post_init__(self) -> None:
        """Derive ``task_lifecycle_phase`` from raw task fields.

        The stored phase is a CACHE of
        :func:`derive_task_lifecycle_phase` over (task_code, task_progress,
        task_total). It is RECOMPUTED on every construction — including
        via ``dataclasses.replace`` — so a caller that mutates the raw
        fields without passing a matching phase still ends up with a
        consistent State.

        Perimeter fix (post-Phase-24): the original Phase-23c-1 design
        asserted equality between the passed-in phase and the derived
        one. That broke direct-construction call sites (formal/diff
        tests + test fixtures) that always default-pass ``NONE`` even
        when raw fields imply ACCEPTED/IN_PROGRESS/COMPLETE. Deriving
        instead of asserting keeps the invariant enforced (stored value
        ALWAYS matches derive output) without forcing every callsite to
        thread the phase through.
        """
        derived = derive_task_lifecycle_phase(
            self.task_code, self.task_progress, self.task_total
        )
        if self.task_lifecycle_phase != derived:
            object.__setattr__(self, "task_lifecycle_phase", derived)

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

    @property
    def active_raids(self) -> list[RaidInfo]:
        """Raids currently running (visibility only — no planner consumer)."""
        return [r for r in self.raids if r.is_active()]

    @classmethod
    def from_character_schema(
        cls,
        char: CharacterSchema,
        bank_items: dict[str, int] | None = None,
        bank_gold: int | None = None,
        bank_capacity: int | None = None,
        pending_items: "tuple[tuple[str, str], ...] | None" = None,
        active_events: dict[str, datetime] | None = None,
        raids: list[RaidInfo] | None = None,
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

        task_code_norm = char.task if char.task else None
        layer_raw = getattr(char, "layer", None)
        layer = getattr(layer_raw, "value", layer_raw) or "overworld"
        return cls(
            character=char.name,
            layer=str(layer),
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
            task_code=task_code_norm,
            task_type=char.task_type if char.task_type else None,
            task_progress=char.task_progress,
            task_total=char.task_total,
            bank_items=bank_items,
            bank_gold=bank_gold,
            bank_capacity=bank_capacity,
            pending_items=pending_items,
            active_events=active_events or {},
            raids=raids or [],
            attack=attack,
            dmg=_require(char, "dmg"),
            dmg_elements=dmg_elements,
            resistance=resistance,
            critical_strike=_require(char, "critical_strike"),
            initiative=_require(char, "initiative"),
            task_lifecycle_phase=derive_task_lifecycle_phase(
                task_code_norm, char.task_progress, char.task_total
            ),
            utility1_slot_quantity=int(_require(char, "utility1_slot_quantity") or 0),
            utility2_slot_quantity=int(_require(char, "utility2_slot_quantity") or 0),
        )
