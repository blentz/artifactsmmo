"""Potion-supply guard predicate: shared target-selection and fire check
for the CRAFT_POTIONS guard tier (guards.py) and CraftPotionsGoal.

``target_potion_pure`` is the single source of truth for which potion to stock
— both the guard and the goal call it so they always agree on the target.
``craft_potions_fires`` is the guard predicate imported by guards.py."""

from datetime import UTC, datetime

from artifactsmmo_cli.ai.boost_selection import best_boost_potion
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.held_for_crafting import held_for_crafting
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.potion_stock_target import (
    fight_is_marginal_pure,
    potion_stock_target_pure,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.thresholds import (
    POTION_GATHER_BATCH,
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.world_state import WorldState


def target_potion_pure(
    state: WorldState, game_data: GameData, effect: str = "hp_restore",
    exclude: str | None = None,
) -> str | None:
    """Highest-``effect``, craftable-now (at the item's own skill/level),
    utility-slot-equippable heal (deterministic smallest-code tie-break); None
    when none qualifies. The crafting skill is read from item metadata, never
    assumed to be alchemy.

    ``exclude`` skips one code from consideration — the second-utility-slot
    caller passes the slot-1 target so it gets the catalog's SECOND-best heal
    (utility potions are not in DUPLICATE_SLOT_TYPES, so the same code can't
    occupy both utility slots; see equip.py's DUPLICATE_SLOT_TYPES comment).

    Single source of truth shared by ``CraftPotionsGoal._target_potion`` and
    ``craft_potions_fires`` so guard and goal always select the same target.
    Materials are NOT required on hand — the relevant-actions ladder
    gathers/buys/withdraws them."""
    best_code: str | None = None
    best_restore = 0
    for code in sorted(game_data.crafting_recipes):
        if code == exclude:
            continue
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "utility":
            continue
        restore = getattr(stats, effect, 0)
        if restore <= 0 or restore <= best_restore:
            continue
        # The crafting SKILL is item metadata (API), not an assumption: any
        # utility-slot heal qualifies, gated by ITS OWN skill/level — never a
        # hardcoded 'alchemy'. An item in crafting_recipes always names a skill.
        if stats.crafting_skill is None:
            continue
        if state.skills[stats.crafting_skill] < stats.crafting_level:
            continue
        best_code, best_restore = code, restore
    return best_code


def _cheapest_heal_potion(game_data: GameData, effect: str = "hp_restore") -> str | None:
    """The craftable utility heal with the smallest crafting_level (the next tier
    to ever unlock); deterministic smallest-code tie-break. None when none exists.

    Level-exempt bootstrap target: unlike target_potion_pure it does NOT require
    the skill to already meet the recipe gate, so the arbiter can drive the FIRST
    unlock. The crafting skill is item metadata, never assumed to be alchemy."""
    best_code: str | None = None
    best_level = 0
    for code in sorted(game_data.crafting_recipes):
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "utility":
            continue
        if getattr(stats, effect, 0) <= 0 or stats.crafting_skill is None:
            continue
        if best_code is None or stats.crafting_level < best_level:
            best_code, best_level = code, stats.crafting_level
    return best_code


def bootstrap_potion_target(
    state: WorldState, game_data: GameData, effect: str = "hp_restore",
) -> str | None:
    """The utility heal to pursue: the effect-best potion craftable NOW, or — when
    none is craftable yet — the cheapest-to-unlock heal so the arbiter can drive
    the first skill unlock. Level-exempt (a potion's item level never gates it;
    utility is judged by effect, not level). Single source of truth for the
    utility-slot root (`CharacterObjective.utility_potion_targets`).

    No ``exclude`` parameter here deliberately: the second-utility-slot caller
    (`utility_potion_targets`) uses `target_potion_pure` directly (not this
    function) for its second-best search — falling through to the
    cheapest-to-unlock branch a SECOND time (excluding slot 1's pick) would
    manufacture an aspirational grind target for an empty slot 2 whenever the
    catalog has no other potion craftable right now, exactly the
    already-guarded-against anti-pattern (see
    test_robby_scenario_stocked_small_does_not_force_enhanced_grind). Slot 2
    only ever gets a target when a second heal is ACTUALLY craftable now."""
    craftable = target_potion_pure(state, game_data, effect)
    if craftable is not None:
        return craftable
    return _cheapest_heal_potion(game_data, effect)


POTION_POLICY = Policy(all_gather_routes=True, gather_skill_gate=True, craft_skill_gate=True,
                       event_vendors=False, spawn_known=True, allow_grey=True,
                       vendor_routes=True, ge_routes=False, task_rewards=False,
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
    model = ObtainModel(state, game_data, NO_PROFILE_CONTEXT, datetime.now(UTC))
    potion = frozenset({code})
    held = model.in_bag(code)
    craft_yield = game_data.craft_yield(code)
    for candidate in range(runs, 0, -1):
        if model.feasible(code, held + candidate * craft_yield, POTION_POLICY,
                          produce=potion, keep=potion):
            return candidate
    return 0


def projected_heal_need_per_fight(state: WorldState, game_data: GameData,
                                  monster: str,
                                  history: LearningStore | None) -> int:
    """In-combat healing needed per fight against ``monster``, in HP.

    Learned consumption first: `hp_healed_per_fight` is what the character has
    ACTUALLY drunk in won fights. With no history, marginality decides whether
    there is any need at all -- a comfortably-winnable monster returns 0, because
    a fight won without drinking needs no stock.

    Deliberately NOT raw expected damage as the primary driver: resting refills to
    full between fights for `max(3, ceil(missing%))` seconds, so damage the bot
    simply rests off is not evidence that a potion was needed. Expected damage is
    used only to SIZE a need that marginality has already established.
    """
    learned = history.hp_healed_per_fight(monster, game_data.hp_restore_of) \
        if history is not None else None
    if learned is not None:
        return max(0, int(learned))
    # No history: only a fight that is NOT comfortably won justifies stock.
    damage = max(0, expected_damage_per_fight(state, game_data, monster))
    if not fight_is_marginal_pure(damage, state.max_hp):
        return 0
    return damage


def potion_batch(state: WorldState, game_data: GameData,
                 history: LearningStore | None = None,
                 combat_monster: str | None = None,
                 effect: str = "hp_restore") -> tuple[str, int, int] | None:
    """`(target_code, runs, equip_qty)`: the potion batch to craft this cycle,
    or None when there is nothing to craft that the ladder can supply.

    THE ONE PLACE this is decided: the CRAFT_POTIONS guard fires exactly when
    this returns a batch, and `CraftPotionsGoal` plans exactly this batch. They
    used to decide separately (the guard checked ONE batch, the goal sized up to
    five) and disagreed live for 821 cycles.

    In precedence order:
    - an unlock boost that would flip a bare-unwinnable in-band monster
      (stall-breaker): one run;
    - else the heal potion, while the equipped stack is below the
      combat-projected target (capped by the level ramp);
    - else, once the heal stack is met, the best boost potion for the primary
      combat monster while its stack is below the level ramp.
    Each batch is sized by the supply ladder (`_ladder_runs`: held first, then
    an affordable buy mix, then a gather batch) and then cut to the runs the
    ladder can actually supply (`feasible_runs`). `combat_monster` is the monster
    the committed intention fights next (`SelectionContext.fight_monster`); None
    — no fight ahead — means no heal or boost stock: there is no in-combat
    consumption to stock for."""
    pair = unlock_boost_target(state, game_data)
    if pair is not None and feasible_runs(pair[0], 1, state, game_data):
        boost = pair[0]
        return (boost, 1, game_data.craft_yield(boost))
    code = target_potion_pure(state, game_data, effect)
    if code is None:
        return None
    monster = combat_monster
    deficit = heal_stock_target(state, game_data, history, monster, code) \
        - equipped_potion_qty(state, code)
    if deficit > 0:
        return _sized(code, deficit, state, game_data)
    if monster is None:
        return None
    best_boost = best_boost_potion(state, game_data, monster)
    if best_boost is None:
        return None
    boost_deficit = potion_level_ramp(state.level) - equipped_potion_qty(state, best_boost)
    if boost_deficit <= 0 or not game_data.crafting_recipes.get(best_boost):
        return None
    return _sized(best_boost, boost_deficit, state, game_data)


def craft_potions_fires(state: WorldState, game_data: GameData,
                        history: LearningStore | None = None,
                        fight_monster: str | None = None) -> bool:
    """True when the CRAFT_POTIONS guard should preempt the grind: exactly when
    `potion_batch` names a batch the ladder can supply. The exclusive gating
    truth for `CraftPotionsGoal`, by construction rather than by a parallel
    re-derivation."""
    return potion_batch(state, game_data, history, fight_monster) is not None


def potion_level_ramp(level: int) -> int:
    """The potion stock the level ramp allows — the batch the potion guard
    stocks toward, capped by projected need (`heal_stock_target`)."""
    return potion_baseline_pure(level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                POTION_HIGH_LEVEL, POTION_HIGH_QTY)


def heal_stock_target(state: WorldState, game_data: GameData, history: LearningStore | None,
                       monster: str | None, code: str) -> int:
    """Combat-projected heal stock, capped by the level ramp; 0 with no combat
    monster (no in-combat consumption to stock for)."""
    if monster is None:
        return 0
    hp_need = projected_heal_need_per_fight(state, game_data, monster, history)
    return potion_stock_target_pure(hp_need, game_data.hp_restore_of(code), potion_level_ramp(state.level))


def _sized(code: str, deficit: int, state: WorldState,
           game_data: GameData) -> tuple[str, int, int] | None:
    """The ladder's batch for `deficit` more of `code`, cut to what can be
    supplied; None when not even one run can be."""
    recipe = dict(game_data.crafting_recipes.get(code, {}))
    craft_yield = game_data.craft_yield(code)
    runs_needed = -(-deficit // craft_yield)
    runs = feasible_runs(code, max(1, _ladder_runs(state, game_data, recipe, runs_needed, craft_yield)),
                         state, game_data)
    if runs == 0:
        return None
    return (code, runs, min(deficit, runs * craft_yield))


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
