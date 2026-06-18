# gather_step_target

"""Pick a budget-FEASIBLE gather target for a depth-unreachable equippable root.

When the strategy's chosen root is an equippable whose full craft chain is
depth-UNREACHABLE (`min_gathers(root) > equip_max_depth` — the proven
`UpgradeEquipmentGoal.is_plannable` gate), the arbiter cannot plan the
craft+equip directly. The prior fallback drove `GatherMaterials(root, root's
DIRECT recipe)` — e.g. `GatherMaterials(steel_boots, {steel_bar: 6})`. For a
from-scratch DEEP chain (no bank/inventory credit) that goal's plan must gather
`min_gathers(root)` raw units THROUGH the multi-level recipe, and the GOAP search
over the gather/deposit/craft interleavings EXPLODES (live: 1M+ nodes, 90s
timeout, plan_len 0 — the bot then falls through to unrelated discretionary work
and the gear chain never progresses).

The `actionable_step` the strategy already computed is the DEEPEST unmet node
whose direct prerequisites are satisfied — for a from-scratch chain that is the
RAW base material (e.g. `iron_ore`, qty 480). Gathering it is a FLAT goal
(`min_gathers == qty`, no recipe sub-tree to interleave), which the planner
solves within budget and which makes real incremental progress; once the raw
material accumulates, the next recipe level becomes the actionable step.

`gather_step_target` is the pure decision: given the root's gather cost and the
deepest step, return the (code, qty) the GatherMaterials goal should target.

SOUNDNESS (the Piece-C honesty bar — never abandon a feasible objective):
  * It routes to the deeper `step` ONLY when the root exceeds the equippable
    depth budget (`root_min_gathers > equip_max_depth`). When the root chain IS
    depth-reachable the caller never reaches here (UpgradeEquipment plans it).
  * The returned `step` is a genuine prerequisite ON the root's recipe path
    (it is the strategy's actionable_step), so routing to it never abandons the
    root — it is the next real unit of progress toward it.
  * The step's own gather cost `min_gathers(step) == step_qty` for a raw leaf is
    NOT larger than the root's (`step_qty <= root_min_gathers`), so we never pick
    a HARDER target than the one we declined. Mirrored + proved in
    `formal/Formal/StepDispatch.lean` (`gatherTarget_*`).

Kept pure (plain dicts, no GameData/WorldState) so the differential harness can
execute it against the Lean oracle, exactly like `min_gathers`/`shopping_list`.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_gathers import min_gathers


def gather_step_target(
    root_item: str,
    step_item: str,
    step_qty: int,
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
    equip_max_depth: int,
    max_yield: int = 1,
) -> tuple[str, int]:
    """Return the (item, qty) a depth-unreachable equippable root should gather.

    `equip_max_depth` is the equippable goal's `max_depth` (the
    `UpgradeEquipmentGoal.is_plannable` budget). When the root's from-holdings
    gather cost fits that budget the caller plans the root chain directly, so we
    keep targeting the root; otherwise we target the strategy's deepest
    actionable `step` — a shallower, budget-feasible sub-target on the same
    chain. Pure: never mutates its arguments (`min_gathers` copies `owned`).

    `max_yield` is the global per-gather drop maximum (`GameData.max_gather_yield`,
    >= 1); the root's raw-unit cost is divided into gather ACTIONS by it so a
    multi-yield chain is not over-counted into a false skip. Defaults to 1 (exact
    unit cost) for callers without game data in scope."""
    root_cost = ceil_gathers(min_gathers(root_item, 1, recipes, owned), max_yield)
    if root_cost <= equip_max_depth:
        return (root_item, 1)
    return (step_item, step_qty)
