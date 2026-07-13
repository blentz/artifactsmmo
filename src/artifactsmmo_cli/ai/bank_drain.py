# bank_drain

"""Detect over-cap junk stockpiled in the BANK that the bot should drain.

The bank is where deposit ladders park items that don't fit the bag. Nothing
inspected the bank against a useful-quantity cap, so a low-value far-need
byproduct (Robby's 228 `sap`, an L20-40 potion material with no near-term use)
sat in the bank forever. This is the bank-side counterpart to
`ai/recycle_surplus.recyclable_surplus` (which only inspects INVENTORY).

You cannot sell or delete straight from the bank — items must be WITHDRAWN first.
So the drain only WITHDRAWS the over-cap excess into the bag; the existing
`DiscardOverstock` guard (`ai/discard_surplus`) sheds it from inventory next
cycle. Withdraw is bank->bag and the shed is bag->gone, so the bank holding
monotonically decreases — no withdraw/redeposit cycle.

PROTECTION IS THE AUTHORITY'S (item-protection-authority epic, Task 9 — this was
the LAST code-set consumer). The drain used to exclude `guards._gear_protected`,
a frozenset whose profile-less arm was `target_gear | target_tools`: "keep ALL
copies of every BiS gear/tool code". A code-SET is the bug class this epic kills,
and here it failed in BOTH directions — it hoarded every copy of a protected code,
and it protected NOTHING at all once profiles were active (a `gear_keep` that
omits `copper_axe` left all 18 banked copies of the character's only woodcutting
tool drainable, hence deletable: live probe 2026-07-13).

    drainable(code) = min(destroyable(code), junk_excess(code))

**THE DRAIN IS BOUNDED BY `keep_owned` ALONE — not by `min(bankable, destroyable)`
like the BAG-side routes.** A withdraw destroys nothing; it moves a copy the other
way. What it exposes to destruction is a copy that is IN THE BANK, and `keep_in_bag`
does not speak about bank copies at all (a bag copy is not a bank copy, and
`bankable` for a code held 0-in-bag is 0 — the `min` would freeze the drain of the
very hoard it exists to clear). OWNERSHIP is the only cap that applies, and
`destroyable` is exactly it:

    destroyable = (bag + bank) - keep_owned

which is why `WORKING_KIT` / `COMBAT_WEAPON` had to be filed into `OWNED_REASONS`
(Task 7b): a tool whose every copy sits in the bank has NO bag copy for the in-bag
ladder to protect, so the ownership cap is the ONLY thing between it and the
withdraw->discard pipeline. 18 axes banked, 0 in bag: `keep_owned` 1 → at most 17
drain, never 18.

`junk_excess` is the surviving WORTH-HOARDING POLICY (the analogue of SELL's ratio
gate — a policy, not a protection):
  * `cap = max(useful_quantity_cap(code), max_recipe_demand(code))`. The
    `max_recipe_demand` term is what makes the BANK safe for far-future materials:
    the inventory cap is 0 for a skill-gated material (which is why it deposits here
    in the first place), but the bank must KEEP enough to craft with later — else a
    banked level-10 drop (gold_ore, jasper_crystal, magic_wood) would be withdrawn
    and destroyed before its recipe is ever reachable, or worse, withdrawn and
    re-deposited forever (`disposal_route` routes a recipe-demanded material back to
    DEPOSIT). An item with NO recipe consumer at any level, and not currency /
    consumable / equippable, has cap 0 — genuine junk that fully drains;
  * the level-distance ceiling clamps how much of a far-out-of-band material the
    bank hoards (re-gather it when in band);
  * the cap covers TOTAL holdings, so inventory already holding some toward it
    shrinks the bank allowance: `junk_excess = bank_qty - max(0, cap - inv_qty)`.

Pure: reads state/game_data/ctx only, no I/O.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import (
    level_distance_keep_ceiling,
    useful_quantity_cap,
)
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def bank_drain_excess(state: WorldState, game_data: GameData,
                      ctx: SelectionContext) -> dict[str, int]:
    """Map each over-cap bank code to the number of BANK copies that may be pulled
    out for shedding: `min(destroyable, junk_excess)` — see the module docstring.

    `ctx` is the per-cycle `SelectionContext` the keep authority reads (`gear_keep` =
    the active-profile gear demand, `step_profile` = the active goal's material
    needs). It REPLACES the `protected_codes` frozenset AND the `gear_keep` map.
    """
    bank = state.bank_items or {}
    out: dict[str, int] = {}
    for code, bank_qty in bank.items():
        if bank_qty <= 0:
            continue
        # PROTECTION: the keep authority's ownership cap. Never melt the last tool.
        licensed = destroyable(code, state, game_data, ctx)
        if licensed <= 0:
            continue
        # POLICY: is it worth hoarding at all? The near-term value/need cap OR the
        # item's full eventual recipe demand, whichever is larger, clamped by the
        # level-distance ceiling.
        cap = max(useful_quantity_cap(code, state, game_data,
                                      gear_keep=ctx.gear_keep or None),
                  game_data.max_recipe_demand(code))
        ceiling = level_distance_keep_ceiling(game_data.item_stats(code), state.level)
        if ceiling is not None and cap > ceiling:
            cap = ceiling
        inv_qty = state.inventory.get(code, 0)
        room_under_cap = cap - inv_qty
        allowed_in_bank = room_under_cap if room_under_cap > 0 else 0
        junk_excess = bank_qty - allowed_in_bank
        excess = junk_excess if junk_excess < licensed else licensed
        if excess > 0:
            out[code] = excess
    return out
