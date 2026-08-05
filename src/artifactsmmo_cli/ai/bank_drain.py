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

CROSS-CHARACTER CONTENTION (2026-08-05, the disposal epic's own side-effect).
The bank is ACCOUNT-shared. Every `play --all` child holds the same
`state.bank_items` snapshot, so all five independently derive the SAME licence
for the SAME codes and race for the same stock; the losers spend an
action-bucket request on HTTP 478 "Missing required item(s)" (7 of 72 cycles on
the validation run, ~10% of that run's requests, against the per-IP rate budget
that is this bot's binding constraint). `ctx.sibling_bank_claims` — live claims
published by siblings via `CoordinationStore.claim_bank_stock` — is subtracted
from the bank's AVAILABLE quantity below, so the second character to look sees
what the first left.

WHY THE SUBTRACTION IS HERE AND NOT AT EVERY WITHDRAW. The claim is WRITTEN at
the general seam (`GamePlayer._execute`, for any `WithdrawItemAction`, so a
supply or currency-ferry withdraw is published too and this drain yields to it).
It is READ only here, because a claim that suppresses a withdraw is a liveness
hazard everywhere else: `SupplyBankGoal` and the currency ferry
(`Withdraw(event_ticket x100)`) withdraw to make FORWARD PROGRESS, and a sibling
claim that made those unplannable would convert an optimisation into a stall.
The drain is discretionary housekeeping (`DRAIN_BANK_JUNK_VALUE` = 15, below
every objective rung), so yielding a pile to a sibling costs exactly nothing —
it drains next cycle instead. It is also where the measured contention was: all
seven observed 478s were drain withdraws (`sap`, `egg`). The other candidate
read site, `WithdrawItemAction.is_applicable`, is a Lean-pinned planner
precondition; making plan admissibility depend on a mutable cross-character read
there would make the planner non-deterministic, which is materially harder AND
worse.

This stays an OPTIMISATION, never a correctness mechanism: the existing
`error:HTTP_478 -> _sync_bank -> replan` path remains the backstop, and a
coordination store that is absent or failing yields an empty claim map, which is
byte-identical to pre-coordination behaviour. No second layer of handling is
added around it.

Pure: reads state/game_data/ctx only, no I/O. The sibling claims arrive as DATA
on `ctx` (the same seam as `supply_target` / `role_skills`) — this module reads
no store and no clock.
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
    for code, banked in bank.items():
        # AVAILABILITY: the bank is ACCOUNT-shared, so every `play --all` child
        # reads the SAME `bank_items` and derives the SAME licence from it —
        # five characters concluding they may each take the same 17 eggs, four
        # of them paying HTTP 478 for it. `ctx.sibling_bank_claims` is what a
        # sibling has already committed to withdrawing (empty on every
        # single-character run, which makes this line inert). Applied to the
        # bank's QUANTITY, before both the emptiness test and the surplus, so a
        # claimed pile is neither drained nor half-drained.
        bank_qty = banked - ctx.sibling_bank_claims.get(code, 0)
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
