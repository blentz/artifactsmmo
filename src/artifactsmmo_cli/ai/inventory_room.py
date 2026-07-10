"""Pure slot+quantity inventory-room core (spec 2026-07-09-slot-aware-inventory
-room). The single decision seam behind every stack-creating action's space
guard: the game enforces BOTH a per-slot cap and a total-quantity cap, so a
NEW distinct stack needs a free slot AND quantity headroom, while GROWING a
held stack needs only quantity headroom. Exact integer arithmetic — mirrored
in formal/Formal/InventoryRoom.lean."""


def has_room(new_stacks: int, added_qty: int,
             slots_free: int, qty_free: int) -> bool:
    """True iff an action adding `new_stacks` distinct stacks and `added_qty`
    total items fits: `new_stacks <= slots_free AND added_qty <= qty_free`.
    `new_stacks=0` (grow a held stack) ignores the slot cap; `added_qty` may be
    0 (quantity-neutral swap) which the qty term trivially passes."""
    return new_stacks <= slots_free and added_qty <= qty_free
