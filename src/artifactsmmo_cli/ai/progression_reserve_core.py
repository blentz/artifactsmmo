"""Pure progression-reserve arithmetic with deduction accounting.

`reserved` maps each unmet near-term progression item to the gold it would cost
to BUY (already deduped and priced by the impure layer). The reserve is a
protective FLOOR on discretionary spending, but buying a RESERVED item fulfills
its own reservation — so that item's cost is deducted from the floor for THAT
purchase (it is never blocked by itself); a non-reserved (discretionary) buy
protects the full reserve. Mirrored by `formal/Formal/ProgressionReserve.lean`.

P4a: gold/prices are exact ints (>= 0); affordability is written `gold >= price
+ floor` (no signed subtraction) to match the Lean `Nat` model exactly.
"""
from collections.abc import Mapping


def reserve_total(reserved: Mapping[str, int]) -> int:
    """Total gold reserved for unmet near-term progression purchases."""
    return sum(reserved.values())


def effective_floor(reserved: Mapping[str, int], buying: str | None) -> int:
    """The reserve floor that applies while buying `buying`: the total minus the
    reservation credited to `buying` itself (0 when `buying` is None or not a
    reserved item)."""
    return reserve_total(reserved) - reserved.get(buying or "", 0)


def affordable(gold: int, price: int, reserved: Mapping[str, int],
               buying: str | None) -> bool:
    """Whether buying `buying` for `price` leaves gold at or above the effective
    reserve floor: `gold >= price + effective_floor(...)`."""
    return gold >= price + effective_floor(reserved, buying)
