"""Lower bound on PLAN length to obtain (and optionally equip) `item`:
`ceil_gathers(min_gathers) + min_crafts + (1 if equip)`. The mint term is divided
by max_gather_yield (a gather yields up to that many units); craft and equip are
one action each. Sound lower bound on plan length over the gather/craft/equip
action model (proved: Formal.PlanModel.min_plan_length_le_plan)."""

from collections.abc import Mapping

from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers


def min_plan_length(item: str, qty: int,
                    recipes: "Mapping[str, dict[str, int]]",
                    owned: dict[str, int], max_gather_yield: int,
                    *, equip: bool) -> int:
    mints = ceil_gathers(min_gathers(item, qty, recipes, owned), max_gather_yield)
    crafts = min_crafts(item, qty, recipes, owned)
    return mints + crafts + (1 if equip else 0)
