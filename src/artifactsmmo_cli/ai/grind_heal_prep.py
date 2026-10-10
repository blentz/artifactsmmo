"""The recovery food a fight needs carried before it is fought.

A skill grind whose legs are fights (a crafting rung fed by monster drops)
fought with no food in the bag, and each fight's damage was restored by
RestoreHP buying food one unit at a time: `Craft(cheese×1)` + eat before every
fight, 3 requests per fight instead of 2 (live C3P0, 2026-09-28: 186 crafts +
263 eats in 4.85 h). The fix follows §3 of
docs/PLAN_decision_architecture_redesign.md: the leaf task builds what it
needs, sized to that need.

WHAT AND HOW MUCH — the chosen loadout (docs/PLAN_consumable_utility.md
increment 5). The food is the food the chosen loadout's recovery eats
(`best_loadout`, read through `best_loadout.loadout_for`: the cycle's own pick
when it was chosen against this fight); when that recovery eats nothing — Rest
is the cheaper recovery — nothing is stocked. The stock is the food's carry
(`chosen_loadout.food_carry`: one recovery's units × `CARRY_HORIZON_FIGHTS`),
the bag's units counting toward it. The grind's prep (`craft_plan_gen`) and the
MAINTAIN_CONSUMABLES rung (for the fight ahead) build the SAME goal.

THE POTIONS TOO (`potion_prep_goal`, 2026-10-10). The chosen loadout's utility
potions are carried the same way, ahead of its food: a potion it wears is what
WINS the fight. Live C3P0 2026-10-10: the band chose vampire on a
water_boost_potion loadout, the CRAFT_POTIONS ladder could not brew one (its
blue_slimeball is a drop, and the ladder emits no fight), and C3P0 fought
vampire with an empty slot — 17 of 34 lost.
"""

from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.best_loadout import loadout_for
from artifactsmmo_cli.ai.chosen_loadout import food_carry, potion_carry
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, Policy
from artifactsmmo_cli.ai.potion_supply import ladder_supplies, prep_supplies
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

HEAL_PREP_POLICY: Policy = replace(DECOMPOSE_POLICY, drop_routes=False)
"""What a food stock may be made from: everything the walk serves except a
fight. The stock exists to spare the grind's fights; fighting another monster
for its ingredients spends what it is meant to save (the potion ladder excludes
drops for the same reason, `POTION_POLICY`). Selection (`feasible`) and
decomposition both walk under it, so a stock judged suppliable is the stock the
walk plans (Phase 2d-F)."""


def heal_prep_goal(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   monster: str) -> GatherMaterialsGoal | None:
    """The goal that carries the chosen loadout's food into fights against
    `monster`, or None when its recovery eats nothing or every food it eats is
    carried (or cannot be supplied).

    The foods are taken in the loadout's order; the first one short of its
    carry in the bag is the goal. Its target is the full carry when the walk
    can supply it under `HEAL_PREP_POLICY`, else the units already held (bag
    and bank: held stock is free, USER 2026-10-09 "free until used up") — a
    banked unit is withdrawn by the walk like any banked copy of its target
    (Phase 2c-2b). A food with neither is skipped for the next one."""
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    for code, eaten in loadout_for(state, game_data, ctx, monster).food:
        carry = food_carry(eaten)
        bag = state.inventory.get(code, 0)
        held = bag + (state.bank_items or {}).get(code, 0)
        for target in (carry, min(carry, held)):
            if target > bag and model.feasible(code, target, HEAL_PREP_POLICY):
                return GatherMaterialsGoal(target_item=code, needed={code: target}, carry=True)
    return None


def potion_prep_goal(state: WorldState, game_data: GameData, ctx: SelectionContext,
                     monster: str) -> GatherMaterialsGoal | None:
    """The goal that carries the chosen loadout's utility potions into fights
    against `monster`: the first potion whose carry (`chosen_loadout.
    potion_carry`) is not on hand — worn or in the bag — and that the
    CRAFT_POTIONS guard cannot stock (`potion_supply.ladder_supplies`: its
    ladder brews without fights), as a bag carry of what is not worn, when the
    decomposition's walk can make it (`potion_supply.prep_supplies`: fights
    included — unlike food, the potion decides the fight, and the pick priced
    its drops' fights, USER 2026-10-09). None when every potion is on hand (the
    guard equips it from the bag), the guard's to stock, or cannot be
    supplied."""
    for code, used in loadout_for(state, game_data, ctx, monster).potions:
        needed = potion_carry(used) - equipped_potion_qty(state, code)
        if (needed > state.inventory.get(code, 0)
                and not ladder_supplies(code, needed, state, game_data)
                and prep_supplies(code, needed, state, game_data, ctx)):
            return GatherMaterialsGoal(target_item=code, needed={code: needed}, carry=True)
    return None


def maintain_consumables_goal(state: WorldState, game_data: GameData,
                              ctx: SelectionContext) -> GatherMaterialsGoal | None:
    """The MAINTAIN_CONSUMABLES rung's goal: heal prep for the fight ahead —
    the monster the cycle's loadout was chosen against — while combat is the
    active means (`ctx.combat_monster` set). None otherwise: the rung does not
    fire."""
    if ctx.combat_monster is None or ctx.loadout is None:
        return None
    return heal_prep_goal(state, game_data, ctx, ctx.loadout.monster)
