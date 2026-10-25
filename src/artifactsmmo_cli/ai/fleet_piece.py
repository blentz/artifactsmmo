"""A fleet piece a crafter serves (spec 2026-10-18 §2.5), as plain data.

Its own module so `SelectionContext` can carry the cycle's fleet pieces without
importing the role catalogue `fleet_pieces` reads them through.
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class FleetPiece:
    """A sibling's missing `L*` piece this crafter's role skill makes: its
    `code`, the craft `skill` and `level` that gate it (API data,
    `GameData.producing_requirement`), and its `gain` summed over every
    sibling that publishes it (`CoordinationStore.sibling_demand_values`)."""

    code: str
    skill: str
    level: int
    gain: Fraction
