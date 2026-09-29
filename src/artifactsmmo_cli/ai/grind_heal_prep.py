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
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def heal_prep_goal(state: WorldState, game_data: GameData,
                   ctx: SelectionContext) -> GatherMaterialsGoal | None:
    """The goal that stocks heals before a grind fight, or None when the stock
    is met or no craftable heal can be supplied in the batch.

    The heal is the strongest craftable one whose batch the obtain model finds
    feasible under LEGACY, the readiness the grind's decomposition serves: the
    strongest heal on skill alone is often unsuppliable (live C3P0: `apple_pie`
    while holding milk for `cheese`), and a prep that cannot decompose would
    never run.

    The batch is the deficit to the stock target. It counts NEW copies beyond
    the bank's: `GatherMaterialsGoal` (and `feasible`) count bank copies as
    held, while the stock is what the bag carries into the fight. Asking for
    bank + bag + deficit makes the goal produce the deficit instead of reading a
    banked copy it would never withdraw as satisfied. The deposit keep-set holds
    the stock target in the bag, so only surplus above it reaches the bank."""
    deficit = heal_stock_target(HEAL_STOCK_FLOOR) - heal_stock(state, game_data)
    if deficit <= 0:
        return None
    heals = craftable_heals(state, game_data)
    if not heals:
        return None
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    bank = state.bank_items or {}
    for code in heals:
        want = bank.get(code, 0) + state.inventory.get(code, 0) + deficit
        if model.feasible(code, want, LEGACY).ok:
            return GatherMaterialsGoal(target_item=code, needed={code: want})
    return None
