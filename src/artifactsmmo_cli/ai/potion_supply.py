"""Potion-supply guard predicate: shared target-selection and fire check
for the CRAFT_POTIONS guard tier (guards.py) and CraftPotionsGoal.

``target_potion_pure`` is the single source of truth for which potion to stock
— both the guard and the goal call it so they always agree on the target.
``craft_potions_fires`` is the guard predicate imported by guards.py."""

from artifactsmmo_cli.ai.boost_selection import best_boost_potion
from artifactsmmo_cli.ai.combat_targets import combat_target_monsters
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.potion_stock_target import (
    fight_is_marginal_pure,
    potion_stock_target_pure,
)
from artifactsmmo_cli.ai.thresholds import (
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.world_state import WorldState


def primary_combat_target(state: WorldState, game_data: GameData) -> str | None:
    """First winnable in-band monster from combat_target_monsters, or None when empty."""
    targets = combat_target_monsters(state, game_data)
    return targets[0] if targets else None


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


def _recipe_producible(recipe: dict[str, int], state: WorldState, game_data: GameData) -> bool:
    """True when EVERY ingredient is obtainable by some tier: available in
    inventory+bank, OR fully buyable from an NPC for gold, OR gatherable from a
    resource node. This is a ONE-LEVEL check — it does NOT recurse into an
    ingredient that is itself craftable from obtainables, so a recipe containing a
    crafted intermediate reads non-producible. That is a SAFE false-negative (the
    guard under-fires rather than spinning) and is exact for the real potion
    recipes, whose ingredients are all direct gathers. Serves the guard's
    exclusive-gating invariant (avoid firing when the goal has no plannable path).
    Previously used a per-tier any() on gatherable, which admitted recipes the
    planner could not complete (149-node no-plan spin)."""
    bank = state.bank_items or {}
    drop_items = set(game_data.gatherable_drop_items())
    def obtainable(mat: str, qty: int) -> bool:
        if state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty:
            return True
        if any(currency == "gold" for _npc, _price, currency in game_data.npc_purchases(mat)):
            return True
        return mat in drop_items
    return all(obtainable(mat, qty) for mat, qty in recipe.items())


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


def craft_potions_fires(state: WorldState, game_data: GameData,
                        history: LearningStore | None = None) -> bool:
    """True when the CRAFT_POTIONS guard should preempt the grind.

    Fires when:
    - A craftable unlock boost exists that would flip a bare-unwinnable in-band
      monster to winnable (stall-breaker path) AND the boost recipe is producible
      (each ingredient individually obtainable: in inventory+bank, NPC-buyable for gold,
      or gatherable), OR
    - A craftable utility heal exists at the character's current skill, AND
      the equipped quantity of that potion is below the level-scaled baseline, AND
      a batch is producible: each ingredient individually obtainable: in inventory+bank,
      NPC-buyable for gold, or gatherable.

    This predicate is the exclusive gating truth for CraftPotionsGoal — the
    guard never fires when the goal would have no plannable path (no target →
    ``relevant_actions`` returns ``[]``)."""
    pair = unlock_boost_target(state, game_data)
    if pair is not None:
        boost_code = pair[0]
        boost_recipe = dict(game_data.crafting_recipes.get(boost_code, {}))
        if boost_recipe and _recipe_producible(boost_recipe, state, game_data):
            return True
    target = target_potion_pure(state, game_data)
    if target is None:
        return False
    equipped = equipped_potion_qty(state, target)
    level_baseline = potion_baseline_pure(
        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY, POTION_HIGH_LEVEL, POTION_HIGH_QTY,
    )
    # Combat-justified target: projected in-combat consumption over the lead-time
    # window, CAPPED by the level ramp. Was the bare ramp, which fired on a stock
    # deficit with no HP or consumption term at all -- so a full-HP bot that wins
    # without drinking still routed to gather/craft, which since Rest went dynamic
    # is never a time saving. Same core the goal sizes from, so the two cannot
    # diverge (they used to: the goal already had a consumption term, the guard
    # did not).
    combat_monster = primary_combat_target(state, game_data)
    hp_need = projected_heal_need_per_fight(state, game_data, combat_monster, history) \
        if combat_monster is not None else 0
    baseline = potion_stock_target_pure(
        hp_need, game_data.hp_restore_of(target), level_baseline,
    )
    if equipped >= baseline:
        monster = primary_combat_target(state, game_data)
        if monster is not None:
            boost = best_boost_potion(state, game_data, monster)
            boost_baseline = potion_baseline_pure(
                state.level, POTION_LOW_LEVEL, POTION_LOW_QTY, POTION_HIGH_LEVEL, POTION_HIGH_QTY,
            )
            if boost is not None and equipped_potion_qty(state, boost) < boost_baseline:
                boost_recipe = dict(game_data.crafting_recipes.get(boost, {}))
                if boost_recipe and _recipe_producible(boost_recipe, state, game_data):
                    return True
        return False
    recipe = dict(game_data.crafting_recipes.get(target, {}))
    if not recipe:
        return False
    return _recipe_producible(recipe, state, game_data)
