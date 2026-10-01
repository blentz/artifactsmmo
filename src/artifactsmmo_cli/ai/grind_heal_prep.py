"""The heal stock a grind's fight leg needs before it fights.

A skill grind whose legs are fights (a crafting rung fed by monster drops) never
sets `ctx.combat_monster`, so the MaintainConsumables rung never fires for it,
and that rung sits below the objective step anyway (selected 8 times in two
months). Without a stock, each fight's damage was restored by RestoreHP buying
food one unit at a time: `Craft(cheese×1)` + eat before every fight, 3 requests
per fight instead of 2 (live C3P0, 2026-09-28: 186 crafts + 263 eats in 4.85 h).

The fix follows §3 of docs/PLAN_decision_architecture_redesign.md: the leaf task
builds what it needs, sized to that need. When the grind's next leg is a fight
and the heal stock is under target, the leg first obtains a batch of the
strongest heal the character can actually supply, through the same
decomposition every grind leg uses.
"""

from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.consumable_supply import (
    HEAL_STOCK_FLOOR,
    craftable_heals,
    heal_stock,
    heal_stock_target,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, Policy
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

HEAL_PREP_POLICY: Policy = replace(DECOMPOSE_POLICY, drop_routes=False)
"""What a heal stock may be made from: everything the walk serves except a
fight. The stock exists to spare hp in the grind's fights; fighting another
monster for its ingredients spends what it is meant to save (the potion ladder
excludes drops for the same reason, `POTION_POLICY`). Selection (`feasible`)
and decomposition both walk under it, so a stock judged suppliable is the stock
the walk plans (Phase 2d-F: it was LEGACY, whose GE routes the walk does not
serve, so a heal only a GE order could supply was chosen and then dropped)."""


def heal_prep_goal(state: WorldState, game_data: GameData,
                   ctx: SelectionContext) -> GatherMaterialsGoal | None:
    """The goal that stocks heals before a grind fight, or None when the stock
    is met or no craftable heal can be supplied in the batch.

    The heal is the strongest craftable one whose batch the obtain model finds
    feasible under `HEAL_PREP_POLICY` (no fights): the
    strongest heal on skill alone is often unsuppliable (live C3P0: `apple_pie`
    while holding milk for `cheese`), and a prep that cannot decompose would
    never run.

    The batch is the deficit to the stock target on top of the bag. A banked
    heal is withdrawn by the walk like any banked copy of its target (Phase
    2c-2b), so it counts toward the stock instead of being left in the bank."""
    deficit = heal_stock_target(HEAL_STOCK_FLOOR) - heal_stock(state, game_data)
    if deficit <= 0:
        return None
    heals = craftable_heals(state, game_data)
    if not heals:
        return None
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    for code in heals:
        want = state.inventory.get(code, 0) + deficit
        if model.feasible(code, want, HEAL_PREP_POLICY):
            return GatherMaterialsGoal(target_item=code, needed={code: want})
    return None
