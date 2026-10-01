"""The most a committed plan ever holds in the bag (Phase 2d, bag capacity).

The one walk counts quantities and never the bag, so a plan it yields may need
more room than the bag has at some leg: a 50-ore withdraw into a bag with 20
free (live C3P0 2026-09-30). `plan_bag_peak` replays the plan's own `apply`
models on a copy of the state whose caps are lifted (each `apply` saturates at
`inventory_max`, so a capped replay could never show an overflow) and returns
the peak total quantity and the peak count of occupied slots. A fight leg that
repeats to a drop target (`FightAction.drop_target`) holds that many of the
drop by the leg's end, where its one-kill `apply` adds one.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

UNCAPPED = 10**9
"""A bag no plan can fill: the replay's capacity."""


def plan_bag_peak(legs: list[Action], state: WorldState,
                  game_data: GameData) -> tuple[int, int]:
    """(peak total quantity, peak occupied slots) over `state` and every leg
    of `legs` in turn."""
    current = dataclasses.replace(state, inventory_max=UNCAPPED, inventory_slots_max=UNCAPPED)
    peak_qty, peak_slots = current.inventory_used, current.inventory_slots_used
    for leg in legs:
        before = current.inventory
        current = leg.apply(current, game_data)
        if isinstance(leg, FightAction) and leg.drop_target is not None:
            item, amount = leg.drop_target
            held = max(current.inventory.get(item, 0), before.get(item, 0) + amount)
            current = dataclasses.replace(current, inventory={**current.inventory, item: held})
        peak_qty = max(peak_qty, current.inventory_used)
        peak_slots = max(peak_slots, current.inventory_slots_used)
    return peak_qty, peak_slots
