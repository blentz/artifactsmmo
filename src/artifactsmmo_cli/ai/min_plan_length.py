"""Lower bound on PLAN length to obtain (and optionally equip) `item`:
`ceil_gathers(min_gathers) + min_crafts + (1 if equip)`. The mint term is divided
by max_gather_yield (a gather yields up to that many units); craft and equip are
one action each.

PROOF STATUS (corrected 2026-08-13). This docstring used to claim "(proved:
Formal.PlanModel.min_plan_length_le_plan)". That theorem does not exist and
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

from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers


def min_plan_length(item: str, qty: int,
                    recipes: Mapping[str, dict[str, int]],
                    owned: dict[str, int], max_gather_yield: int,
                    equip: bool) -> int:
    mints = ceil_gathers(min_gathers(item, qty, recipes, owned), max_gather_yield)
    crafts = min_crafts(item, qty, recipes, owned)
    return mints + crafts + (1 if equip else 0)
