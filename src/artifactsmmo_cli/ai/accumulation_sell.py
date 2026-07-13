# accumulation_sell

"""What the SELL route may take, and how badly it wants to take it.

PROTECTION IS THE AUTHORITY'S, NOT OURS (item-protection-authority epic, Task 8).
This module used to source its surplus from `inventory_caps.useful_quantity_cap`
(`keep = cap; excess = held - keep`). That cap is a "how many are USEFUL" heuristic,
not a protection floor, and in profiles-aware mode it returns ZERO for an equippable
in no active profile — so the live 18-`copper_axe` bag offered ALL EIGHTEEN copies
for sale, the WORKING tool included (probe 2026-07-13). The keep authority
(`ai/inventory_keep.py`) answers the protection question with two integer caps, and
the sell route asks it:

    surplus = min(bankable, destroyable)

BOTH caps, because a sale is a BAG-side ALIENATION — the same composition RECYCLE
ships (`ai/recycle_surplus.py`):

  * `destroyable` (bag+bank beyond `keep_owned`) LICENSES it: a sale is
    IRREVERSIBLE, so it answers to OWNERSHIP, and bank copies count toward
    satisfying the cap because they are still owned.
  * `bankable` (bag beyond `keep_in_bag`) BOUNDS it to the copies that may leave
    the BAG at all. `KeepReason.WORKING_KIT` and `COMBAT_WEAPON` live in the in-bag
    ladder, so `destroyable` alone would sell the one tool the gather re-arm is
    about to equip: with 1 axe ferried into the bag and 17 in the bank,
    `keep_owned` is 1 → 17 destroyable, and the ONLY copy the seller can reach is
    the working one. `min(bankable, destroyable)` = min(0, 17) = 0.

THE RATIO GATE STAYS, and now runs over the AUTHORITY's keep rather than the
`useful_quantity_cap` heuristic. It is a POLICY, not a protection: while the bank
can still take the surplus, banking (reversible) is preferred to a sale
(irreversible), so only a genuine HOARD — `held >= ACCUM_MULT x keep` — is sold, with
urgency rising geometrically (one step per doubling of the ratio). Once the bank can
take nothing more (full, or locked) that preference has no object: the sale is the
bank-full cascade's SELL rung (craft > recycle > sell > discard) and the WHOLE
licensed surplus is offered. `SellInventoryGoal` passes `relief=True` there — it is
mapped from `GuardKind.SELL_RELIEF`, whose firing predicate IS `not bank_has_room`.

`accumulation_steps` / `accumulation_excess` are unchanged, integer-exact (no float)
pure cores — they mirror the Lean `Formal.AccumulationSell` defs byte-for-byte under
the differential gate.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

ACCUM_MULT = 5
"""Fire the accumulation sell when `held >= ACCUM_MULT * max(keep, 1)`."""

SEVERE_STEPS = 5
"""`accumulation_steps >= SEVERE_STEPS` (held >= keep*32) marks a SEVERE hoard:
`SellInventoryGoal.value` sends it straight to the top of the discretionary band
so it sheds first among housekeeping (still below progression — it never
preempts active leveling)."""


def accumulation_steps(held: int, cap: int) -> int:
    """Geometric severity: the largest `k >= 0` with `eff_cap * 2**k <= held`
    (= floor(log2(held / eff_cap))), `eff_cap = max(cap, 1)`. 0 when held is
    below `eff_cap`. Integer-exact doubling — no float."""
    eff_cap = cap if cap > 1 else 1
    if held < eff_cap:
        return 0
    k = 0
    bound = eff_cap
    while bound * 2 <= held:
        bound = bound * 2
        k = k + 1
    return k


def accumulation_excess(held: int, cap: int) -> int:
    """`held - max(cap, 0)` when `held >= ACCUM_MULT * max(cap, 1)`, else 0.
    The RATIO gate uses `eff_cap = max(cap, 1)`; the amount kept is the TRUE cap,
    so a dominated item (cap 0) past the gate sells down to 0, a kept item
    (cap 1) sells down to 1."""
    eff_cap = cap if cap > 1 else 1
    if held < ACCUM_MULT * eff_cap:
        return 0
    keep = cap if cap > 0 else 0
    return held - keep


def _is_sellable(code: str, game_data: GameData) -> bool:
    """An item with a REACHABLE NPC buyer that is tradeable — the per-item rule
    behind `tiers/guards._has_sellable`. A buyer in the price table whose
    `npc_location` is None (a dormant event merchant) does NOT count, matching
    `NpcSellAction.is_applicable`."""
    stats = game_data.item_stats(code)
    if stats is not None and not stats.tradeable:
        return False
    return any(game_data.npc_location(npc) is not None
               for npc, _price in game_data.npcs_buying_item(code))


def sellable_surplus(state: WorldState, game_data: GameData,
                     ctx: SelectionContext) -> dict[str, int]:
    """Map each SELLABLE held code to the number of BAG copies the keep authority
    licenses for SALE: `min(bankable, destroyable)` — see the module docstring.

    `ctx` is the per-cycle `SelectionContext` the keep authority reads
    (`gear_keep` = the active-profile gear demand, `step_profile` = the active
    goal's material needs). It REPLACES the old `gear_keep` map, which reached
    `useful_quantity_cap` and produced the zero-cap "sell the working tool" bug."""
    out: dict[str, int] = {}
    for code, held in state.inventory.items():
        if held <= 0 or not _is_sellable(code, game_data):
            continue
        surplus = min(bankable(code, state, game_data, ctx),
                      destroyable(code, state, game_data, ctx))
        if surplus > 0:
            out[code] = surplus
    return out


def sellable_accumulation(state: WorldState, game_data: GameData,
                          ctx: SelectionContext) -> dict[str, int]:
    """The RATIO-GATED subset of `sellable_surplus`: only the codes held at
    `ACCUM_MULT` times the authority's own keep or more.

    The quantity sold is still the AUTHORITY's licence (never the heuristic cap):
    the gate decides WHETHER to sell, the authority decides HOW MANY. `keep` is
    read back off the licence (`held - surplus`) so the two cannot drift, and the
    gate itself is the unchanged, Lean-proved `accumulation_excess`."""
    out: dict[str, int] = {}
    for code, surplus in sellable_surplus(state, game_data, ctx).items():
        held = state.inventory[code]
        if accumulation_excess(held, held - surplus) > 0:
            out[code] = surplus
    return out


def sell_targets(state: WorldState, game_data: GameData, ctx: SelectionContext,
                 relief: bool = False) -> dict[str, int]:
    """The copies the SELL route may take THIS cycle.

    `relief=True` is the bank-full cascade's SELL rung (`GuardKind.SELL_RELIEF`,
    which fires on `not bank_has_room`): the bank cannot absorb the surplus, so the
    ratio gate — whose whole point is "bank it instead" — has no object and the
    full licensed surplus is offered. Otherwise only the hoards past the gate."""
    if relief:
        return sellable_surplus(state, game_data, ctx)
    return sellable_accumulation(state, game_data, ctx)


def worst_accumulation_steps(state: WorldState, game_data: GameData,
                             ctx: SelectionContext) -> int:
    """Max `accumulation_steps` over the ratio-gated hoards (0 if none) — the
    severity signal driving `SellInventoryGoal.value` (a SEVERE hoard, steps
    >= SEVERE_STEPS, takes the top of the discretionary band). Measured against
    the AUTHORITY's keep, like the gate itself."""
    worst = 0
    for code, surplus in sellable_accumulation(state, game_data, ctx).items():
        steps = accumulation_steps(state.inventory[code], state.inventory[code] - surplus)
        if steps > worst:
            worst = steps
    return worst
