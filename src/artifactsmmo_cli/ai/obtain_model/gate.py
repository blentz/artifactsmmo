"""Gates: the named conditions a route must meet to be usable right now.

Phase 1 of `docs/PLAN_decision_architecture_redesign.md`. Seventeen models used
to answer "can I get X" and each checked a different subset of these conditions,
so they disagreed (D-A..D-R in the plan). The obtain model evaluates EVERY gate
on EVERY route and keeps the verdicts, so a caller that finds no usable route
can name what blocks it instead of re-deriving it.
"""

from dataclasses import dataclass
from enum import Enum

type Door = tuple[tuple[str, int], ...]
"""A door's shortfall from one state (`region_edges.door_reaches`):
`(code, units)` pairs, gold under `GOLD_CODE`, sorted by code. Two edges
asking the same shortfall are one door: holding it opens both."""


class GateKind(Enum):
    """What a gate tests. `subject` names the thing it tests (a skill, a
    monster, an NPC, an item)."""

    BANK_ACCESSIBLE = "bank_accessible"
    """The bank is unlocked (`ctx.bank_accessible`)."""
    CRAFT_SKILL = "craft_skill"
    """Crafting skill `subject` is at least `level`."""
    GATHER_SKILL = "gather_skill"
    """Gathering skill `subject` is at least `level`."""
    WORKSHOP_KNOWN = "workshop_known"
    """A workshop for skill `subject` has a known tile."""
    SPAWN_LIVE = "spawn_live"
    """Resource or monster `subject` has a currently-live tile."""
    SPAWN_KNOWN = "spawn_known"
    """Monster or resource `subject` has a tile, live or on any layer, in a
    region the walk reaches from here now (`region_edges.content_reached` over
    `reachable_regions_now`: rulings T14a-E, I-3, R3-M1)."""
    XP_POSITIVE = "xp_positive"
    """Monster `subject` pays experience at the character's level (not grey)."""
    WINNABLE = "winnable"
    """Monster `subject` is predicted beatable at restorable HP."""
    VENDOR_LOCATED = "vendor_located"
    """NPC `subject` has a known tile."""
    VENDOR_PERMANENT = "vendor_permanent"
    """NPC `subject` is not an event NPC."""
    VENDOR_TRADEABLE = "vendor_tradeable"
    """NPC `subject` can be traded with now (permanent, or its event is live)."""
    GE_LOCATED = "ge_located"
    """The Grand Exchange has a known tile."""
    LICENSED = "licensed"
    """The keep authority licenses destroying at least one copy of `subject`."""


@dataclass(frozen=True)
class Gate:
    """One evaluated condition on one route."""

    kind: GateKind
    subject: str
    satisfied: bool
    level: int | None = None
    doors: tuple[Door, ...] = ()
    """An unmet SPAWN_KNOWN gate only: the doors past which the content lies
    (`region_edges.doors_to`). The walk opens the gate by obtaining one door's
    shortfall (`ObtainModel.walk_graph`); the pricer charges it as the route's
    unlock (`acquisition_cost._door_options`). Empty: no door opens it."""
