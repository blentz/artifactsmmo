"""Pure core for `NpcBuyAction.is_applicable` / `.apply` inventory bookkeeping.

This module isolates the minimal slot-affecting transition `NpcBuyAction`
performs: the precondition `inventory_free >= quantity` (alongside the gold
gate) and the planner-side mint of `+quantity` of `item_code`.

The Lean module `formal/Formal/NpcBuyInventory.lean` proves three contracts on
these pure cores (mirroring the `GatherApply.lean` chain_safe pattern):

* `npc_buy_is_applicable_pure(inv_used, inv_max, quantity, gold, price)` returns
  True iff (`inv_max - inv_used >= quantity`) ∧ (`gold >= price * quantity`).
* `npc_buy_apply_pure(inventory, item_code, quantity)` produces an inventory
  whose `item_code` count is incremented by `quantity` (all other entries
  preserved bit-for-bit).
* SAFETY: `npc_buy_is_applicable_pure(...) and quantity >= 1` implies the
  post-state's `used' <= max` (the planner cannot mint past `inventory_max` in
  a single buy), and chaining N buys with total quantity <= initial free stays
  within the cap.

This mirrors the `gather_apply_core` chain_safe shape PRECISELY because the
production bug had the same shape: the apply blindly mints `+qty` without the
slot-floor precondition. The Phase-3 OptimizeLoadout fix shape (precondition +
apply assert) is applied here too: `NpcBuyAction.apply` now asserts the
precondition before mutating, so any precondition bypass crashes loudly.

The production methods delegate; behavior is identical (post-fix).
"""
from collections.abc import Mapping


def npc_buy_is_applicable_pure(
    inv_used: int,
    inv_max: int,
    quantity: int,
    gold: int,
    price: int,
) -> bool:
    """True iff inventory has `quantity` free slots AND gold covers `price * quantity`.

    Mirrors the slot+gold half of `NpcBuyAction.is_applicable` (the
    npc_location / event-tradeability halves are orthogonal and live in
    `is_applicable` itself).
    """
    free = inv_max - inv_used
    if free < quantity:
        return False
    return not gold < price * quantity


def npc_buy_apply_pure(
    inventory: Mapping[str, int],
    item_code: str,
    quantity: int,
) -> dict[str, int]:
    """Mint `+quantity` of `item_code` into the inventory dict.

    `item_code` count increases by exactly `quantity`; all other entries are
    preserved bit-for-bit. This function is the bookkeeping the planner uses
    for projected states; the production `NpcBuyAction.apply` asserts the
    `is_applicable` precondition before invoking it.
    """
    new_inventory = dict(inventory)
    new_inventory[item_code] = new_inventory.get(item_code, 0) + quantity
    return new_inventory
