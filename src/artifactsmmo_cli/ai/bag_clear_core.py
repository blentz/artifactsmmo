"""Pure core of the full-bag clear (Task 13e, USER 2026-10-25: "free up all
in-use inventory slots that aren't related to the current plan, then retry the
plan once the full inventory state is cleared").

Each held stack is routed on three executability-now facts the adapter
(`ai/bag_clear.py`) assembles:

    KEEP     iff  related                       (plan I/O, root closure, keep, equipped)
    DEPOSIT  iff  not related and the bank takes it      (non-destructive first)
    DISPOSE  iff  not related, the bank refuses it, and the junk policy can
                  remove the whole stack (`disposal_route`, bounded by `destroyable`)
    KEEP     otherwise                          (nothing can move it this cycle)

The clear frees one slot per stack that leaves (`slots_freed`); a clear that
frees none is the named verdict `BAG_FULL_ALL_RELATED`. Mirrored in
formal/Formal/BagClear.lean (`clearRoute`, `freed`)."""

from collections.abc import Iterable
from enum import Enum

BAG_FULL_ALL_RELATED = "bag_full_all_related"
"""The verdict when the bag is full and the clear can free no slot: every
stack is related to the plan, or nothing can move the unrelated ones."""


class ClearRoute(Enum):
    KEEP = "keep"
    DEPOSIT = "deposit"
    DISPOSE = "dispose"


def clear_route(related: bool, bank_takes: bool, disposable: bool) -> ClearRoute:
    """Where one held stack goes in the clear. A related stack never leaves."""
    if related:
        return ClearRoute.KEEP
    if bank_takes:
        return ClearRoute.DEPOSIT
    if disposable:
        return ClearRoute.DISPOSE
    return ClearRoute.KEEP


def slots_freed(routes: Iterable[ClearRoute]) -> int:
    """Slots the clear frees: one per stack whose route is not KEEP."""
    return sum(1 for route in routes if route is not ClearRoute.KEEP)
