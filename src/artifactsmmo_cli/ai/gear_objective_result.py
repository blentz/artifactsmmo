"""The global gear objective's answer as plain data (spec 2026-10-18 §2.2, §2.4).

`GearObjective` is `(L*, m*)`: the loadout of achievable, level-legal gear and
the monster it farms best, with the pieces of `L*` the character does not yet
hold, in the order they are pursued. `gear_objective.gear_objective` builds it.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.gear_objective_core import objective_held
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class GearPiece:
    """One missing `L*` piece: the `code` for `slot`, the fixed-point `layer`
    it first became achievable in, its `gain` in advancement rate on `m*` over
    what the character owns, its acquisition `price` (`route_price`), and the
    `route` that price takes (`acquisition_cost.cheapest_route`), the one the
    piece is served by: only a CRAFT is classified behind its crafting gate.
    None only for a piece with no route at all."""

    slot: str
    code: str
    layer: int
    gain: Fraction
    price: Fraction
    route: SourceKind | None

    @property
    def crafted(self) -> bool:
        """The route that priced the piece is its CRAFT, so its crafting gate
        and recipe stand in front of it; any other route serves the piece
        itself. Read here, beside the pricer's answer, so a `Decision`
        follows the price's own argmin and never branches on a route kind
        (`audit/one_cost_model` O8)."""
        return self.route is SourceKind.CRAFT

    def awaits_delivery(self, state: WorldState) -> bool:
        """The route that priced the piece is a bank WITHDRAW and the bank
        holds no copy yet. That is the sibling route (spec 2026-10-18 §2.5,
        "Delivery"): the fleet's crafter makes the piece and banks it, and this
        character's own step is the withdraw, so until a copy is banked the
        piece has no step of its own — least of all the crafting climb the
        sibling route exists to spare it. Read here beside `crafted`, for the
        same reason (O8). A bank never visited (`bank_items is None`) holds no
        copy the character knows of."""
        return self.route is SourceKind.WITHDRAW and (state.bank_items or {}).get(self.code, 0) <= 0


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
