"""Potion-supply guard predicate: shared target-selection and fire check
for the CRAFT_POTIONS guard tier (guards.py) and CraftPotionsGoal.

``target_potion_pure`` is the single source of truth for which potion to stock
— both the guard and the goal call it so they always agree on the target.
``craft_potions_fires`` is the guard predicate imported by guards.py."""

from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.thresholds import (
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.world_state import WorldState


def target_potion_pure(
    state: WorldState, game_data: GameData, effect: str = "hp_restore"
) -> str | None:
    """Highest-``effect``, alchemy-craftable-now, utility-slot-equippable potion
    (deterministic smallest-code tie-break); None when none qualifies.

    Single source of truth shared by ``CraftPotionsGoal._target_potion`` and
    ``craft_potions_fires`` so guard and goal always select the same target.
    Materials are NOT required on hand — the relevant-actions ladder
    gathers/buys/withdraws them."""
    best_code: str | None = None
    best_restore = 0
    for code in sorted(game_data.crafting_recipes):
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "utility":
            continue
        restore = getattr(stats, effect, 0)
        if restore <= 0 or restore <= best_restore:
            continue
        if stats.crafting_skill != "alchemy":
            continue
        if state.skills.get("alchemy", 1) < stats.crafting_level:
            continue
        best_code, best_restore = code, restore
    return best_code


def craft_potions_fires(state: WorldState, game_data: GameData) -> bool:
    """True when the CRAFT_POTIONS guard should preempt the grind.

    Fires when:
    - An alchemy-craftable utility potion exists at current alchemy skill, AND
    - The equipped quantity of that potion is below the level-scaled baseline, AND
    - A batch is producible: ingredients craft-from-held OR all buyable OR any gatherable.

    This predicate is the exclusive gating truth for CraftPotionsGoal — the
    guard never fires when the goal would have no plannable path (no target →
    ``relevant_actions`` returns ``[]``)."""
    target = target_potion_pure(state, game_data)
    if target is None:
        return False
    equipped = equipped_potion_qty(state, target)
    baseline = potion_baseline_pure(
        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY, POTION_HIGH_LEVEL, POTION_HIGH_QTY,
    )
    if equipped >= baseline:
        return False
    recipe = dict(game_data.crafting_recipes.get(target, {}))
    if not recipe:
        return False
    bank = state.bank_items or {}
    # craft-from-held: all ingredients already available in inventory + bank
    if all(state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
           for mat, qty in recipe.items()):
        return True
    # buyable: every ingredient purchaseable from an NPC for gold
    if all(
        any(currency == "gold" for _npc, _price, currency in game_data.npc_purchases(mat))
        for mat in recipe
    ):
        return True
    # gatherable: at least one ingredient drops from a resource node
    drop_items = set(game_data.resource_drops.values())
    return any(mat in drop_items for mat in recipe)
