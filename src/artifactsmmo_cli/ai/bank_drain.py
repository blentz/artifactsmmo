# bank_drain

"""Detect over-cap junk stockpiled in the BANK that the bot should drain.

The bank is where deposit ladders park items that don't fit the bag. Nothing
inspected the bank against a useful-quantity cap, so a low-value far-need
byproduct (Robby's 228 `sap`, an L20-40 potion material with no near-term use)
sat in the bank forever. This is the bank-side counterpart to
`ai/recycle_surplus.recyclable_surplus` (which only inspects INVENTORY).

A code is BANK JUNK when the character holds it in the bank ABOVE its total
useful keep-cap:
  * `cap = useful_quantity_cap(code)` — the SAME value/need cap the inventory
    overstock logic uses (recipe demand × batch buffer, task demand, equippable
    swap-floor, consumable floor; 0 for a far-skill-gated material like sap);
  * the cap covers TOTAL holdings, so the inventory already holding some toward
    the cap shrinks the bank allowance:
      `bank_excess = bank_qty - max(0, cap - inv_qty)`;
  * it is NOT a committed objective code (`protected_codes` = the objective's
    target_gear/target_tools — never drain the gear you are building).

You cannot sell or delete straight from the bank — items must be WITHDRAWN
first. So the drain only WITHDRAWS the over-cap excess into the bag; the existing
`DiscardOverstock` guard (sell-if-buyer-active-else-delete, fixed 2026-06-24)
sheds it from inventory next cycle. Withdraw is bank→bag and the shed is
bag→gone, so the bank holding monotonically decreases — no withdraw/redeposit
cycle.

Pure: reads state/game_data only, no I/O.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.world_state import WorldState


def bank_drain_excess(
    state: WorldState, game_data: GameData, protected_codes: frozenset[str],
) -> dict[str, int]:
    """Map each over-cap bank code to the bank quantity beyond its useful cap.

    `bank_excess(code) = max(0, bank_qty - max(0, cap - inv_qty))` where
    `cap = useful_quantity_cap(code)` bounds TOTAL (inventory + bank) holdings.
    """
    bank = state.bank_items or {}
    out: dict[str, int] = {}
    for code, bank_qty in bank.items():
        if bank_qty <= 0 or code in protected_codes:
            continue
        cap = useful_quantity_cap(code, state, game_data)
        inv_qty = state.inventory.get(code, 0)
        room_under_cap = cap - inv_qty
        allowed_in_bank = room_under_cap if room_under_cap > 0 else 0
        excess = bank_qty - allowed_in_bank
        if excess > 0:
            out[code] = excess
    return out
