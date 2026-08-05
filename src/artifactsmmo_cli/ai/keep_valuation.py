# keep_valuation

"""The ONE quantity-typed "worth keeping" valuation, shared by the bank drain
and the overstock disposal route.

WHY THIS MODULE EXISTS. Two gates used to answer "is this worth keeping" and
they answered DIFFERENT KINDS OF QUESTION (live diagnosis 2026-08-05,
`.superpowers/sdd/2026-08-01-emergent-specialization/currency-and-piles-report.md`):

  * `disposal_route._future_value` was a BOOLEAN — "does some recipe anywhere
    consume this code, or is it equippable". True for nearly every gatherable,
    so the route banked everything;
  * `bank_drain.junk_excess` was a QUANTITY — a keep cap clamped by
    `level_distance_keep_ceiling`. It licensed draining the very piles the
    route was banking.

They contradicted each other on all seven of the live bank piles (703 sap, 510
raw_wolf_meat, 277 raw_chicken, 162 raw_beef, 148 gudgeon, 129 wolf_hair, 104
raw_porkchop): `bank_drain_excess` licensed the whole pile while
`disposal_route` routed it straight back to DEPOSIT. `bank_drain.py`'s own
docstring claimed "no withdraw/redeposit cycle" — a claim that was FALSE for
any material with a nonzero `max_recipe_demand`, which is nearly every
gatherable. This module makes it true by construction: both sides now read
`worth_keeping`, and the anti-livelock invariant

    drained(code) > 0  ⇒  route(code) ≠ DEPOSIT

is a one-line arithmetic consequence of that (proved over the pure cores in
formal/Formal/DisposalRoute.lean — `drained_is_never_deposited`, plus the
post-withdraw form `withdrawn_is_never_redeposited`).

A BOOLEAN CANNOT EXPRESS THE ANSWER. "Is sap worth keeping" has no yes/no
answer: one sap is worth keeping (a level-20 alchemy recipe consumes exactly
one), 703 are not. The answer is a NUMBER, and it is the number both callers
already needed.

THE BANK-SIDE CAP IS NOT INVENTORY-CREDITED (verdict change, stated). The old
`junk_excess` subtracted the bag holding from the cap ("the cap covers TOTAL
holdings"). That is incompatible with the invariant: with the credit, a code
held 10-in-bag / 3-in-bank against a keep of 5 is simultaneously drainable
(bank 3 > headroom 0) and deposit-eligible (bank 3 < keep 5) — exactly the
contradiction this module exists to kill. `worth_keeping` is therefore the cap
on the BANK's own stock; the BAG has its own, separate space cap
(`inventory_caps.overstocked_items` / `inventory_keep.keep_in_bag`), and
DESTRUCTION is bounded by `inventory_keep.destroyable` on both sides regardless.

REACHABLE CONSUMER, GROUNDED IN THE REQUIREMENT GRAPH. The eventual-demand term
used to be `max_recipe_demand` clamped by `level_distance_keep_ceiling` — a
level-distance proxy that cannot see whether a consumer EXISTS at all, let
alone whether it is attainable. It is replaced here by
`reachable_consumer_demand`, which reads `RequirementGraph.edges` (who consumes
this) and `RequirementGraph.craft_skill` (the ONE skill-gate derivation, D3 of
the requirement-model-unification epic) instead of re-deriving both from
`crafting_recipes` + `item_stats` a fourth time. The ceiling itself is
untouched where it belongs — on the BAG space gates.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.requirement_graph import RequirementGraph
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

MAX_ATTAINABLE_SKILL_LEVEL = GameData.MAX_CHARACTER_LEVEL
"""The highest crafting-skill level a character can ever reach — the API's
documented progression cap (`GameData.MAX_CHARACTER_LEVEL`, sourced from
https://docs.artifactsmmo.com/concepts/stats_and_fights/), which crafting
skills share with the character level. Derived, not invented: the live catalog's
highest `crafting_level` is exactly this value, so a recipe gated ABOVE it is a
recipe no character can ever craft, and the material it consumes has no
reachable consumer through that recipe."""


def consumer_reachable(consumer: str, graph: RequirementGraph) -> bool:
    """Can a character ever craft `consumer`?

    Reads the requirement graph's `craft_skill` — its SINGLE skill-gate
    derivation — rather than re-deriving the gate from `item_stats`. A recipe
    with no craft-skill gate is always reachable; a gated one is reachable iff
    its level is inside the progression cap."""
    gate = graph.craft_skill.get(consumer)
    return gate is None or gate[1] <= MAX_ATTAINABLE_SKILL_LEVEL


def reachable_consumer_demand(code: str, game_data: GameData) -> int:
    """The eventual recipe demand for `code`, or 0 when NOTHING that can ever
    be crafted consumes it.

    The QUANTITY is `max_recipe_demand` — the existing transitive walk, reused
    rather than re-implemented (there is one demand walk in this codebase and
    it stays that way). The REACHABILITY question is the graph's: `edges` names
    the direct consumers and `consumer_reachable` gates them. An item consumed
    by no recipe at all, or only by recipes off the top of the progression
    ladder, returns 0 — genuine junk the bank must not hoard.

    There is deliberately NO `max_recipe_demand(code) <= 0` fast path in front of
    the scan: it would be an equivalent guard (the quantity is positive exactly
    when some recipe consumes the code, which is what the scan tests), and an
    inversion-equivalent conditional is dead logic, not a decision."""
    graph = game_data.requirement_graph.graph()
    for consumer, ingredients in graph.edges.items():
        if ingredients.get(code, 0) > 0 and consumer_reachable(consumer, graph):
            return game_data.max_recipe_demand(code)
    return 0


def worth_keeping(code: str, state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> int:
    """How many copies of `code` are worth keeping — THE valuation.

    The larger of:
      * `useful_quantity_cap` — the near-term value/need cap (recipe demand the
        character can craft NOW, active task chain, equippable/profile keep,
        currency and consumable floors), already level-distance clamped;
      * `reachable_consumer_demand` — the full eventual demand of a consumer
        that can ever be reached. This is what keeps a far-skill-gated material
        (a level-20 gemstone mined at level 11) out of the withdraw→discard
        pipeline: the near-term cap is 0 for it precisely because it is gated.

    `ctx.gear_keep` (the active loadout profiles' per-code demand) reroutes the
    equippable component exactly as it does for every other keep consumer; an
    empty map means "no profile info" and keeps the legacy blanket behaviour."""
    near = useful_quantity_cap(code, state, game_data,
                               gear_keep=ctx.gear_keep or None)
    eventual = reachable_consumer_demand(code, game_data)
    return near if near > eventual else eventual


def bank_surplus_pure(keep: int, bank_qty: int) -> int:
    """Bank copies beyond the keep quantity. THE shared number.

    `> 0` — banked junk the drain may withdraw for shedding.
    `< 0` — the bank is still under this code's cap, so DEPOSIT is honest.
    `= 0` — exactly at cap: nothing to drain, and nothing more to bank.

    Mirrored as `Formal.DisposalRoute.bankSurplus`."""
    return bank_qty - keep


def drain_licensed_pure(destroyable: int, keep: int, bank_qty: int) -> int:
    """How many BANK copies the drain may withdraw: the surplus, bounded by the
    keep authority's ownership licence. Mirrored as
    `Formal.DisposalRoute.drainLicensed`."""
    surplus = bank_surplus_pure(keep, bank_qty)
    return surplus if surplus < destroyable else destroyable


def bank_under_cap_pure(keep: int, bank_qty: int) -> bool:
    """The disposal route's DEPOSIT gate: is the bank still under this code's
    cap? Mirrored as `Formal.DisposalRoute.bankUnderCap`. Reading the SAME
    `bank_surplus_pure` as `drain_licensed_pure` is what makes
    `drained > 0 ⇒ route ≠ DEPOSIT` hold."""
    return bank_surplus_pure(keep, bank_qty) < 0


def bank_quantity(code: str, state: WorldState) -> int:
    """Banked copies of `code`; 0 when the bank has never been visited this
    session (`bank_items is None` — an unknown bank is not a full one)."""
    bank = state.bank_items or {}
    return bank.get(code, 0)
