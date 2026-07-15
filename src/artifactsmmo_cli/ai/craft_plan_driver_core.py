"""Deterministic FULL craft-plan driver.

Iterates the single-step :func:`next_craft_target_pure` to completion, applying
each emitted action's effect to a simulated (inventory, bank) state, and
accumulates the whole ordered remaining plan (gather / withdraw / craft /
recycle / buy / drop -- THE ONE OBTAIN MODEL, `ai/obtain_sources.Source`).
This lets a craftable obtain-goal be planned ONCE from the static recipe
closure + owned-netting instead of re-searched.

Mirrors the kernel-proved Lean `Formal.CraftPlanDriver.craftPlan` /
`applyState` (formal/Formal/CraftPlanDriver.lean) on the 3-kind
(gather/withdraw/craft) path:
  * CONSUMPTION — `craft` consumes its recipe inputs (sound on shared
    intermediates, not just linear chains); `gather`/`withdraw` add to
    inventory; `withdraw` also debits the bank.
  * `next_craft_target_pure` only returns `craft` when every input is on hand
    (ORDERING, proved), so consumption never underflows on a reachable plan.

`sources` is OPTIONAL and defaults to empty, which reduces this driver to the
original 3-kind walk byte-for-byte -- this is what keeps every pre-existing
caller and test (and the Lean differential, which does not yet exercise the
widened kinds) unchanged. When supplied, two more effects apply, each
mirroring its executor:
  * RECYCLE consumes the SOURCE item: `owned[item] += qty` AND
    `owned[src.code] -= ceil(qty / src.yield_per)` (mirrors `RecycleAction.apply`).
    The `ceil` (not a truncating `//`) is what avoids over-crediting recovery.
    This exact debit is NOT guarded by `craftPlan_reaches` (that theorem checks
    only the TARGET item, which is never the debited surplus source — it is
    structurally blind to the debit); it is pinned by the Lean ⌈·⌉ `decide`
    witnesses + the craft-plan differential's live-bound recycle revisit, and
    by the `tests/` unit that kills the floor mutant here.
  * BUY/DROP just add to inventory (`owned[item] += qty`). BUY's gold cost is
    NOT modelled here -- this core has no gold dimension; affordability is
    the action's own `is_applicable`, and a BUY source is only ever emitted
    by `obtain_sources` for a permanent, reachable vendor. DROP's stochastic
    drop rate is the same deliberate abstraction the existing Fight xp
    projection uses (see `feedback_combat_xp_projection_is_abstract`) --
    not "fixed" here either.

Theorems backing the 3-kind path: `craftPlan_steps_valid` (no fabricated
steps), `craftPlan_reaches` (a complete plan, executed, reaches the TARGET item
-- deliberately blind to source-item accounting, so it does NOT guard the
recycle debit above), `craftPlan_head` (first action = the proved single step),
`craftPlan_nil_iff`.
"""

import math
from collections.abc import Mapping

from artifactsmmo_cli.ai.next_craft_core import NextAction, next_craft_target_pure
from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind


def _apply_state(
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
    bank: dict[str, int],
    na: NextAction,
    sources: Mapping[str, list[Source]] | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    """Return (owned', bank') after applying one action's effect (with consumption).

    Mirrors Lean `applyState` on the 3-kind path. Returns fresh dicts; inputs
    are not mutated. `sources` is only consulted for a "recycle" `na` (to look
    up the consumed source item's `yield_per`); it is unused, and may be
    omitted, for every other kind.
    """
    new_owned = dict(owned)
    new_bank = dict(bank)
    if na.kind == "gather":
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
    elif na.kind == "withdraw":
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
        new_bank[na.item] = new_bank.get(na.item, 0) - na.qty
    elif na.kind == "craft":  # add the output, consume per*qty of each recipe input
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
        recipe = recipes.get(na.item)
        if recipe is not None:
            for inp, per in recipe.items():
                new_owned[inp] = new_owned.get(inp, 0) - per * na.qty
    elif na.kind == "recycle":
        # RECYCLE consumes the SOURCE item (na.code), not the target: mirrors
        # RecycleAction.apply. yield_per lives on the Source, not on
        # NextAction, so it is looked up here rather than carried on na.
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
        match = next(
            (s for s in (sources or {}).get(na.item, ()) if s.kind is SourceKind.RECYCLE and s.code == na.code),
            None,
        )
        if match is None:
            raise ValueError(
                f"recycle step for {na.item!r} names source {na.code!r} with no matching "
                "Source in `sources` -- caller must pass the same map used to plan the step"
            )
        consumed = math.ceil(na.qty / match.yield_per)
        new_owned[na.code] = new_owned.get(na.code, 0) - consumed
    else:  # "buy" / "drop": add to inventory. Gold (BUY) and drop-rate variance
        # (DROP) are NOT modelled here -- see module docstring.
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
    return new_owned, new_bank


def craft_plan_full(
    recipes: Mapping[str, dict[str, int]],
    owned: Mapping[str, int],
    bank: Mapping[str, int],
    target: str,
    qty: int,
    sources: Mapping[str, list[Source]] | None = None,
) -> list[NextAction]:
    """The full ordered remaining plan to obtain ``qty`` of ``target``.

    Empty when already satisfied. Otherwise a list of gather/withdraw/craft
    (and, when `sources` widens the model, recycle/buy/drop) actions which,
    executed in order from the given (inventory, bank), reaches
    ``owned[target] >= qty``. Mirrors Lean `craftPlan` with outer fuel sized to
    the closure-bounded worst case (each step satisfies ≥ 1 unit of progress).
    """
    plan: list[NextAction] = []
    cur_owned: dict[str, int] = dict(owned)
    cur_bank: dict[str, int] = dict(bank)
    # Each emitted action reduces the total remaining deficit by >= 1
    # (qty_pos), so the closure demand bounds the number of steps. A generous
    # bound keeps the loop total without ever truncating a reachable plan.
    fuel = (len(recipes) + 1) * (qty + 1) + 1
    for _ in range(fuel):
        na = next_craft_target_pure(recipes, cur_owned, cur_bank, target, qty, sources)
        if na is None:
            return plan
        plan.append(na)
        cur_owned, cur_bank = _apply_state(recipes, cur_owned, cur_bank, na, sources)
    return plan  # pragma: no cover
    # Unreachable via this API: `fuel` is the closure-bounded worst case and each
    # step reduces the total remaining deficit by >= 1 (qty_pos), so the loop
    # always exits early via the `na is None` (target satisfied) branch. The
    # post-loop return is the totality guard mirroring Lean `craftPlan`'s fuel=0
    # arm (proved: craftPlan_reaches holds whenever length < fuel).
