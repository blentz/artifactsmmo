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

THAT LAST CLAIM WAS FALSE UNTIL 2026-08-05, and making it true is why this
module now reads `ai/keep_valuation`. The shed step routes through
`ai/disposal_route`, whose DEPOSIT arm asked a BOOLEAN ("does some recipe
anywhere consume this code") while the drain asked a QUANTITY. Every one of the
live bank piles satisfied the boolean, so the drain withdrew and the route
deposited the same copies straight back. Both sides now read one
`keep_valuation.worth_keeping`, and the anti-livelock invariant

    drained(code) > 0  ⇒  route(code) ≠ DEPOSIT

falls out of `bank_surplus_pure` being the same number on both sides (proved in
formal/Formal/DisposalRoute.lean: `drained_is_never_deposited`, and in the
post-withdraw state `withdrawn_is_never_redeposited`).

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

The surviving WORTH-HOARDING POLICY (the analogue of SELL's ratio gate — a policy,
not a protection) is `ai/keep_valuation.worth_keeping`, and the surplus it licenses
is `keep_valuation.bank_surplus_pure(keep, bank_qty)`. See that module for why the
valuation is quantity-typed, why "reachable consumer" is now a requirement-graph
question rather than the `level_distance_keep_ceiling` proxy, and why the cap is on
the BANK's own stock rather than inventory-credited.

Pure: reads state/game_data/ctx only, no I/O.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.keep_valuation import drain_licensed_pure, worth_keeping
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def bank_drain_excess(state: WorldState, game_data: GameData,
                      ctx: SelectionContext) -> dict[str, int]:
    """Map each over-cap bank code to the number of BANK copies that may be pulled
    out for shedding: `min(destroyable, bank_surplus)` — see the module docstring.

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
        # POLICY: THE valuation — the same number `disposal_route`'s DEPOSIT arm
        # reads, which is what makes the drain monotone (module docstring).
        excess = drain_licensed_pure(
            licensed, worth_keeping(code, state, game_data, ctx), bank_qty)
        if excess > 0:
            out[code] = excess
    return out
