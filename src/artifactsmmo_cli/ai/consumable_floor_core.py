"""Pure core: one character's share of the fleet's consumable floor
(`docs/PLAN_consumable_utility.md` increment 4; proved model
`formal/Formal/ConsumableFloor.lean`, differential
`formal/diff/test_consumable_floor_diff.py`).

USER (2026-10-09), "From the chosen loadouts": the fleet's minimum BANKED
quantity of a consumable is Σ over the characters whose chosen loadout uses it
of (units used per fight × `REFILL_HORIZON_FIGHTS`).

USER (2026-10-09), "Need ledger + API order": the banked stock is assigned in
the account's `GET /my/characters` order, and each character publishes
`need − min(need, max(0, bank − needs ahead of it))`. Every character computes
its own share from the same needs and the same order, so the shares the demand
board sums are exactly the fleet's shortfall, `max(0, Σ needs − bank)`
(`Formal.ConsumableFloor.fleetShares_sum`, each share the per-character one by
`Formal.ConsumableFloor.fleetShares_getD`), no share exceeds its need
(`Formal.ConsumableFloor.share_le`) and more bank never raises one
(`Formal.ConsumableFloor.share_antitone_bank`)."""

from collections.abc import Mapping, Sequence

REFILL_HORIZON_FIGHTS = 20
"""Fights of a chosen loadout's use the fleet keeps banked (USER 2026-10-09,
"From the chosen loadouts")."""


def share(order: Sequence[str], needs: Mapping[str, int], me: str, bank: int) -> int:
    """`me`'s share of one consumable's shortfall. `order` is the fleet order,
    `needs` the per-character need (a character without a row needs nothing).
    `me` must be in `order`: a character outside the account has no place in
    the assignment (`ValueError`)."""
    ahead = sum(needs.get(name, 0) for name in order[:order.index(me)])
    need = needs.get(me, 0)
    return need - min(need, max(0, bank - ahead))
