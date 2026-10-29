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
(`best_loadout`, the pick `best_loadout.loadout_for` gives against this fight:
the cycle's own when it was chosen against it), handed in by the caller, which
reads the same pick for the fight's bag-room verdict, so the pick is computed
once (ruling T14d-R m4); when that recovery eats nothing — Rest
is the cheaper recovery — nothing is stocked. The stock is the food's carry
(`chosen_loadout.food_carry`: one recovery's units × `CARRY_HORIZON_FIGHTS`),
the bag's units counting toward it. The grind's prep (`craft_plan_gen`) and
every fight step (`strategy_driver._fight_step_prep`) build the SAME goal (the
MAINTAIN_CONSUMABLES rung that also built it retired 2026-10-10).

THE POTIONS TOO (`potion_prep_goal`, 2026-10-10). The chosen loadout's utility
potions are carried the same way, ahead of its food: a potion it wears is what
WINS the fight. Live C3P0 2026-10-10: the band chose vampire on a
water_boost_potion loadout, the CRAFT_POTIONS ladder could not brew one (its
blue_slimeball is a drop, and the ladder emits no fight), and C3P0 fought
vampire with an empty slot — 17 of 34 lost.
"""

from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, food_carry, potion_carry
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.food_producer import may_make_food
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
                   loadout: ChosenLoadout) -> GatherMaterialsGoal | None:
    """The goal that carries `loadout`'s food into fights against its monster
    (the pick `loadout_for` gives for that fight), or None when its recovery eats nothing or every food it eats is
    carried (or cannot be supplied).

    The foods are taken in the loadout's order; the first one short of its
    carry in the bag is the goal. Its target is the full carry only when the
    food is in the loadout's `made_food` (worth making at replacement price),
    this character makes the fleet's food (`food_producer.may_make_food`) and
    the walk can supply it under `HEAL_PREP_POLICY`; otherwise the units already
    held (bag and bank: held stock is free, USER 2026-10-09 "free until used
    up") — a banked unit is withdrawn by the walk like any banked copy of its
    target (Phase 2c-2b). A food with neither is skipped for the next one."""
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    made = dict(loadout.made_food)
    for code, eaten in loadout.food:
        carry = food_carry(eaten)
        bag = state.inventory.get(code, 0)
        held = bag + (state.bank_items or {}).get(code, 0)
        # The bag takes only what it has room for (a new stack needs a free
        # slot): a carry past it plans a Withdraw the server refuses, and the
        # step waited (live HAL 2026-10-14, Withdraw(cooked_chicken×100) into
        # 67 units of room, 1.5 h of Wait).
        room = bag + state.inventory_free if bag or state.inventory_slots_free else 0
        carry = min(carry, room)
        # Spec 2026-10-13 §1/§4: units past the held ones are MADE only when
        # the food beats Rest at replacement price and this character makes
        # the fleet's food; otherwise only what is held is fetched.
        makes = made.get(code, 0) > 0 and may_make_food(code, ctx.role, ctx.fleet_roles, game_data)
        for target in ((carry, min(carry, held)) if makes else (min(carry, held),)):
            if target > bag and model.feasible(code, target, HEAL_PREP_POLICY):
                return GatherMaterialsGoal(target_item=code, needed={code: target}, carry=True)
    return None


def potion_prep_goal(state: WorldState, game_data: GameData, ctx: SelectionContext,
                     loadout: ChosenLoadout) -> GatherMaterialsGoal | None:
    """The goal that carries `loadout`'s utility potions into fights against
    its monster (the pick `loadout_for` gives for that fight): the first potion whose carry (`chosen_loadout.
    potion_carry`) is not on hand — worn or in the bag — and that the
    CRAFT_POTIONS guard cannot stock (`potion_supply.ladder_supplies`: its
    ladder brews without fights), as a bag carry of what is not worn, when the
    decomposition's walk can make it (`potion_supply.prep_supplies`: fights
    included — unlike food, the potion decides the fight, and the pick priced
    its drops' fights, USER 2026-10-09). None when every potion is on hand (the
    guard equips it from the bag), the guard's to stock, or cannot be
    supplied."""
    for code, used in loadout.potions:
        needed = potion_carry(used) - equipped_potion_qty(state, code)
        if (needed > state.inventory.get(code, 0)
                and not ladder_supplies(code, needed, state, game_data)
                and prep_supplies(code, needed, state, game_data, ctx)):
            return GatherMaterialsGoal(target_item=code, needed={code: needed}, carry=True)
    return None
