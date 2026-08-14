"""Lower bound on PLAN length to obtain (and optionally equip) `item`:
`min_gather_steps + min_crafts + (1 if equip)`. One batched gather serves one
raw material's whole demand, one craft per produced node, one equip.

DO NOT re-add a "(proved: NOT-PROVED: Formal.PlanModel.min_plan_length_le_plan)"
citation
here. Task 2 REMOVED it: that theorem has never existed. Preserve whatever
citation Task 2 left in place — it names a theorem that does exist and states
its undischarged hypothesis honestly.

The mint term was `ceil_gathers(min_gathers(...))` — raw UNITS — which bounded
plan length only while one gather minted one unit. `GatherAction.quantity`
makes a real plan shorter than that, so the unit count stopped being a lower
bound and this predicate began rejecting reachable goals: live 2026-08-12,
`UpgradeEquipment(greater_wooden_staff)` needed 60 spruce_wood and was refused
admission against `max_depth 32` on 955 of 955 cycles.

PROOF STATUS (corrected 2026-08-13). This docstring used to claim "(proved:
NOT-PROVED: Formal.PlanModel.min_plan_length_le_plan)". That theorem does not exist and
never did — the name appears nowhere in formal/ outside the citations. What is
actually proved is narrower:

* the GATHER term only, `Formal.PlanModel.minGathers_le_gathers_of_corner3`,
  and CONDITIONALLY: it assumes `corner3`, a hypothesis explicitly RETIRED and
  not discharged (PlanModel.lean, "STATUS (2026-06-20)");
* nothing at all about the craft term, and nothing about the sum against a
  real plan's length.

Treat the sum as an A*-budget heuristic, not a proven bound. Its consumer
`is_plannable` is an optimization whose both failure modes the runtime guards
absorb (see that same PlanModel docstring for the necessity audit).
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gather_steps import min_gather_steps


def min_plan_length(item: str, qty: int,
                    recipes: Mapping[str, dict[str, int]],
                    owned: dict[str, int], max_gather_yield: int,
                    equip: bool) -> int:
    """`max_gather_yield` is retained for call-site compatibility and is no
    longer consulted: a batched gather covers the whole demand of one material
    regardless of per-gather yield, so the yield only affects how many CYCLES
    that one action occupies, never the plan's length."""
    mints = min_gather_steps(item, qty, recipes, owned)
    crafts = min_crafts(item, qty, recipes, owned)
    return mints + crafts + (1 if equip else 0)
