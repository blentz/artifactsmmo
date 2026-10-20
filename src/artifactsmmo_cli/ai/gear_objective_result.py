"""The global gear objective's answer as plain data (spec 2026-10-18 §2.2, §2.4).

`GearObjective` is `(L*, m*)`: the loadout of achievable, level-legal gear and
the monster it farms best, with the pieces of `L*` the character does not yet
hold, in the order they are pursued. `gear_objective.gear_objective` builds it.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.gear_objective_core import objective_held
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class GearPiece:
    """One missing `L*` piece: the `code` for `slot`, the fixed-point `layer`
    it first became achievable in, its `gain` in advancement rate on `m*` over
    what the character owns, and its acquisition `price` (`route_price`)."""

    slot: str
    code: str
    layer: int
    gain: Fraction
    price: Fraction


@dataclass(frozen=True)
class GearObjective:
    """`monster` is `m*`, `loadout` is `L*` (slot -> code) and `rate` is
    `R(L*, m*)`, the XP per second of farming `m*` in it. `missing` holds the
    pieces not yet held, ordered by `gear_objective_core.piece_order_key`.
    `fighter` is the character owning the achievable set and wearing `L*`, the
    fighter `rate` is read on (None only on an objective built by hand); it is
    not part of the answer's identity."""

    monster: str
    loadout: dict[str, str]
    rate: Fraction
    missing: tuple[GearPiece, ...]
    fighter: WorldState | None = field(default=None, compare=False, repr=False)

    @property
    def held(self) -> bool:
        """Every slot holds its `L*` item or one the picker ranks equal (§2.4.1)."""
        return objective_held(frozenset(piece.slot for piece in self.missing))
