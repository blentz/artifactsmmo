"""Deterministic FULL craft-plan driver.

Iterates the single-step :func:`next_craft_target_pure` to completion, applying
each emitted action's effect to a simulated (inventory, bank) state, and
accumulates the whole ordered remaining plan (gather / withdraw / craft). This
lets a craftable obtain-goal be planned ONCE from the static recipe closure +
owned-netting instead of re-searched.

Mirrors the kernel-proved Lean `Formal.CraftPlanDriver.craftPlan` /
`applyState` (formal/Formal/CraftPlanDriver.lean):
  * CONSUMPTION — `craft` consumes its recipe inputs (sound on shared
    intermediates, not just linear chains); `gather`/`withdraw` add to
    inventory; `withdraw` also debits the bank.
  * `next_craft_target_pure` only returns `craft` when every input is on hand
    (ORDERING, proved), so consumption never underflows on a reachable plan.

Theorems backing this: `craftPlan_steps_valid` (no fabricated steps),
`craftPlan_reaches` (a complete plan, executed, reaches the target),
`craftPlan_head` (first action = the proved single step), `craftPlan_nil_iff`.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.next_craft_core import NextAction, next_craft_target_pure


def _apply_state(
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
    bank: dict[str, int],
    na: NextAction,
) -> tuple[dict[str, int], dict[str, int]]:
    """Return (owned', bank') after applying one action's effect (with consumption).

    Mirrors Lean `applyState`. Returns fresh dicts; inputs are not mutated.
    """
    new_owned = dict(owned)
    new_bank = dict(bank)
    if na.kind == "gather":
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
    elif na.kind == "withdraw":
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
        new_bank[na.item] = new_bank.get(na.item, 0) - na.qty
    else:  # craft: add the output, consume per*qty of each recipe input
        new_owned[na.item] = new_owned.get(na.item, 0) + na.qty
        recipe = recipes.get(na.item)
        if recipe is not None:
            for inp, per in recipe.items():
                new_owned[inp] = new_owned.get(inp, 0) - per * na.qty
    return new_owned, new_bank


def craft_plan_full(
    recipes: Mapping[str, dict[str, int]],
    owned: Mapping[str, int],
    bank: Mapping[str, int],
    target: str,
    qty: int,
) -> list[NextAction]:
    """The full ordered remaining plan to obtain ``qty`` of ``target``.

    Empty when already satisfied. Otherwise a list of gather/withdraw/craft
    actions which, executed in order from the given (inventory, bank), reaches
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
        na = next_craft_target_pure(recipes, cur_owned, cur_bank, target, qty)
        if na is None:
            return plan
        plan.append(na)
        cur_owned, cur_bank = _apply_state(recipes, cur_owned, cur_bank, na)
    return plan  # pragma: no cover
    # Unreachable via this API: `fuel` is the closure-bounded worst case and each
    # step reduces the total remaining deficit by >= 1 (qty_pos), so the loop
    # always exits early via the `na is None` (target satisfied) branch. The
    # post-loop return is the totality guard mirroring Lean `craftPlan`'s fuel=0
    # arm (proved: craftPlan_reaches holds whenever length < fuel).
