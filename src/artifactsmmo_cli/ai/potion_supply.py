"""Potion supply: the batch the CRAFT_POTIONS guard (guards.py) fires on and
CraftPotionsGoal plans (`potion_batch`), for the potions of the chosen
consumable loadout only (docs/PLAN_consumable_utility.md increment 5)."""

from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, potion_carry
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.grey_farm import grey_farm_allowed
from artifactsmmo_cli.ai.held_for_crafting import held_for_crafting
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, Policy
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.thresholds import (
    POTION_GATHER_BATCH,
)
from artifactsmmo_cli.ai.world_state import WorldState

POTION_POLICY = Policy(all_gather_routes=True, gather_skill_gate=True, craft_skill_gate=True,
                       event_vendors=False, spawn_known=True, allow_grey=True,
                       vendor_routes=True, ge_routes=False, task_rewards=False,
                       price_climbs=False,
                       fight_gold=False, drop_routes=False)
"""What the potion supply (the walk under this policy, Phase 2e) can serve, as an
obtain-model policy: the recipe's crafts, every gatherer of an ingredient (the
gather must be performable: skill and spawn), permanent vendors paid from the
pocket, and what the bag and bank already hold. NO drops: the ladder emits no
FightAction. NO GE-only route: the ladder adds a GE fill only beside an NPC buy.

This replaces `_recipe_producible`, a one-level private walk that counted any
gatherable ingredient (skill ignored), any gold vendor (price ignored) and ONE
batch against holdings while the goal sized FIVE: live Robby 2026-09-27,
`earth_boost_potion` x5 needed 5 `yellow_slimeball`, the bank held 1 and the
only other source was a drop, so the guard fired and the goal found no plan
821 times in 24 h (up to 98k nodes a search)."""


def feasible_runs(code: str, runs: int, state: WorldState, game_data: GameData) -> int:
    """The largest run count <= `runs` the one walk can supply under
    `POTION_POLICY`, or 0: the bag plus `candidate * yield` copies of `code`,
    with `code` MADE (`produce`: its craft route, whose own skill gate counts)
    and never recycled (`keep`). The walk fills the recipe jointly, so two
    ingredients that share stock share it (Phase 2d-F). Counting down returns
    the largest such count. A run is a craft, so an item with no recipe has
    none (`produce` alone would admit its gather)."""
    if not game_data.crafting_recipes.get(code):
        return 0
    # A store-less feasibility walk: every drop at its API prior, passed
    # explicitly (ruling T16b).
    model = ObtainModel(state, game_data,
                       replace(NO_PROFILE_CONTEXT, learned_drops=LearnedDrops.empty()),
                       datetime.now(UTC))
    potion = frozenset({code})
    held = model.in_bag(code)
    craft_yield = game_data.craft_yield(code)
    for candidate in range(runs, 0, -1):
        if model.feasible(code, held + candidate * craft_yield, POTION_POLICY,
                          produce=potion, keep=potion):
            return candidate
    return 0


def potion_batch(state: WorldState, game_data: GameData,
                 loadout: ChosenLoadout | None) -> tuple[str, int, int] | None:
    """`(target_code, runs, equip_qty)`: the potion batch to stock this cycle, or
    None when there is nothing to stock that the ladder can supply.

    THE ONE PLACE this is decided: the CRAFT_POTIONS guard fires exactly when
    this returns a batch, and `CraftPotionsGoal` plans exactly this batch.

    ONLY THE CHOSEN LOADOUT (docs/PLAN_consumable_utility.md increment 5). The
    potions are the ones `loadout` wears against its fight
    (`best_loadout.best_loadout`, read once per cycle as `ctx.loadout`), in its
    order; a potion it does not choose is never brewed or equipped here. Each
    is stocked to its carry, `chosen_loadout.potion_carry` (one fight's use ×
    `CARRY_HORIZON_FIGHTS`, at most a full slot), against the units already
    worn. The first chosen potion short of its carry is the batch: the units
    the bag and bank hold are equipped first (held stock is free, USER
    2026-10-09), and the rest is crafted in the runs the supply ladder sizes
    (`_ladder_runs`: held ingredients, then an affordable buy mix, then a
    gather batch), cut to what the walk can supply (`feasible_runs`). A potion
    with nothing held and no run supplyable is skipped for the next one.

    No loadout (no fight ahead) stocks nothing: there is no in-combat
    consumption to stock for."""
    if loadout is None:
        return None
    for code, used in loadout.potions:
        deficit = potion_carry(used) - equipped_potion_qty(state, code)
        if deficit > 0:
            batch = _sized(code, deficit, state, game_data)
            if batch is not None:
                return batch
    return None


def craft_potions_fires(state: WorldState, game_data: GameData,
                        loadout: ChosenLoadout | None) -> bool:
    """True when the CRAFT_POTIONS guard should preempt the grind: exactly when
    `potion_batch` names a batch for the chosen loadout. The exclusive gating
    truth for `CraftPotionsGoal`, by construction rather than by a parallel
    re-derivation."""
    return potion_batch(state, game_data, loadout) is not None


def guard_loadout(loadout: ChosenLoadout | None, fight_monster: str | None) -> ChosenLoadout | None:
    """The loadout the CRAFT_POTIONS guard stocks: the chosen one, only when it
    was chosen against the fight the committed intention fights next
    (`ctx.fight_monster`). Stocking for the grind target alone brewed potions
    for a fight never fought (live Lor 2026-10-06: ~258 sunflowers in three
    hours)."""
    if loadout is None or fight_monster is None or loadout.monster != fight_monster:
        return None
    return loadout


def prep_supplies(code: str, qty: int, state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> bool:
    """The fight step's prep can make `qty` of `code` from here: the
    decomposition's own walk (`DECOMPOSE_POLICY`, greys as the grey-farm
    directive admits them, no skill grind opened), so a potion judged
    suppliable is one `GatherMaterials` plans. Plain `feasible` under the
    policy disagreed with the walk on a grey ingredient: it refused C3P0's
    blue_slimeball that the decomposition fights for (2026-10-10)."""
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    return model.walk(code, qty, DECOMPOSE_POLICY, keep=frozenset({code}),
                      grey_ok=lambda item: grey_farm_allowed(item, state, game_data)).feasible


def potion_stockable(code: str, state: WorldState, game_data: GameData,
                     ctx: SelectionContext) -> bool:
    """A potion a loadout may wear because something will stock it: held, the
    CRAFT_POTIONS ladder brews it, or the fight step's prep makes it. A
    loadout's potion that nothing stocks is fought without (live C3P0
    2026-10-10: a GE-priced health_potion it could not brew at alchemy 17)."""
    return (held_count(code, state) > 0 or ladder_supplies(code, 1, state, game_data)
            or prep_supplies(code, 1, state, game_data, ctx))


def ladder_supplies(code: str, deficit: int, state: WorldState, game_data: GameData) -> bool:
    """The CRAFT_POTIONS guard can stock `deficit` more of `code` worn from
    here (`potion_batch`'s own sizing): held copies, or a run the ladder can
    supply. A loadout potion it cannot is the fight step's prep
    (`grind_heal_prep.potion_prep_goal`) — one stocker per potion."""
    return _sized(code, deficit, state, game_data) is not None


def _sized(code: str, deficit: int, state: WorldState,
           game_data: GameData) -> tuple[str, int, int] | None:
    """The batch for `deficit` more of `code` worn: the bag's and bank's copies
    first, then the runs the ladder sizes for the rest, cut to what can be
    supplied; None when nothing is held and not one run can be supplied."""
    have = state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)
    short = deficit - have
    if short <= 0:
        return (code, 0, deficit)
    recipe = dict(game_data.crafting_recipes.get(code, {}))
    craft_yield = game_data.craft_yield(code)
    runs_needed = -(-short // craft_yield)
    runs = feasible_runs(code, max(1, _ladder_runs(state, game_data, recipe, runs_needed, craft_yield)),
                         state, game_data)
    equip = min(deficit, have + runs * craft_yield)
    if equip == 0:
        return None
    return (code, runs, equip)


def _ladder_runs(state: WorldState, game_data: GameData, recipe: dict[str, int],
                 runs_needed: int, craft_yield: int) -> int:
    """Craft RUNS to attempt this cycle, chosen by the supply ladder:
    (1) the most this many craft-runs held ingredients already cover, else
    (2) the largest buyable batch affordable in gold, else
    (3) a single gather-and-replan batch bounded to POTION_GATHER_BATCH."""
    ingredients = list(recipe.items())
    needs = [qty for _code, qty in ingredients]
    held = [held_for_crafting(code, state) for code, _qty in ingredients]
    from_held = max_batch_from_held_pure(needs, held, craft_yield)
    if from_held > 0:
        return min(runs_needed, from_held // craft_yield)
    prices = [_gold_price(code, game_data) for code, _qty in ingredients]
    if all(p is not None for p in prices):
        bought = optimal_buy_mix_pure(needs, held, [p for p in prices if p is not None],
                                      state.gold, runs_needed)
        if bought > 0:
            return bought
    return min(runs_needed, POTION_GATHER_BATCH)


def _gold_price(code: str, game_data: GameData) -> int | None:
    """Cheapest gold buy price for `code`, or None when no NPC sells it for gold."""
    gold = [price for _npc, price, currency in game_data.npc_purchases(code)
            if currency == "gold"]
    return min(gold) if gold else None
