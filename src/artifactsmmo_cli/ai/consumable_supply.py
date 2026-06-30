"""Heal-consumable supply helpers (PLAN #6a).

Pure functions over WorldState + GameData (no API, no RNG) shared by the
MaintainConsumables means predicate (`tiers/means.py`) and goal
(`goals/maintain_consumables.py`) — the same shape as `recycle_surplus.py`
backing both the RECYCLE_SURPLUS means and its goal.

Intent: when combat is the active means and the bot is under-stocked on heals,
cook/brew more rather than falling back to the slow Rest action. The bot already
EATS heals (UseConsumable); this keeps the cupboard stocked.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState

HEAL_STOCK_FLOOR = 5
"""Target minimum count of heal consumables to keep on hand when combat is the
active means. Below this, MaintainConsumables fires. Low on purpose — top up,
don't hoard — and heal items are in the discard keep-set (CONSUMABLE_KEEP), so
restocking never fights DiscardOverstock."""


def heal_stock(state: WorldState, game_data: GameData) -> int:
    """Total count of HP-restoring consumables currently held."""
    total = 0
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            total += qty
    return total


def best_held_heal_restore(state: WorldState, game_data: GameData) -> int:
    """Highest hp_restore among held heal consumables (0 if none held)."""
    best = 0
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > best:
            best = stats.hp_restore
    return best


def best_held_heal(state: WorldState, game_data: GameData) -> str | None:
    """Held item code with the highest hp_restore (None if no heal held).
    Deterministic: ties break on the lexically smallest code."""
    best_code: str | None = None
    best_restore = 0
    for code in sorted(state.inventory):
        if state.inventory[code] <= 0:
            continue
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > best_restore:
            best_code, best_restore = code, stats.hp_restore
    return best_code


def heal_stock_target(desired: int) -> int:
    """Stock target: at least the floor, at most a full utility stack."""
    return max(HEAL_STOCK_FLOOR, min(desired, UTILITY_SLOT_MAX_STACK))


def best_craftable_heal(state: WorldState, game_data: GameData) -> str | None:
    """The craftable-now heal consumable with the highest hp_restore that is at
    least as strong as the best heal already held (so restocking a good heal
    counts), or None when the bot's skills can make nothing worthwhile.

    "Craftable now" = the item has a recipe and the player meets the crafting
    skill level. Materials are NOT required on hand — the goal's recipe-closure
    actions let the planner gather/withdraw them. Selection is deterministic
    (highest restore, then lowest code) so the predicate and goal agree."""
    floor_restore = best_held_heal_restore(state, game_data)
    best_code: str | None = None
    best_restore = -1
    for code in sorted(game_data.crafting_recipes):
        stats = game_data.item_stats(code)
        if stats is None or stats.hp_restore <= 0:
            continue
        if stats.hp_restore < floor_restore:
            continue  # weaker than what we already carry — not "better"
        if not stats.crafting_skill:
            continue
        if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
            continue  # skill gate not met
        if stats.hp_restore > best_restore:
            best_code, best_restore = code, stats.hp_restore
    return best_code


def maintain_consumables_fires(state: WorldState, game_data: GameData,
                               desired_stock: int = HEAL_STOCK_FLOOR) -> bool:
    """Under the (possibly scaled) stock target AND able to craft a good heal now.

    The combat-active condition is applied by the means tier (it holds the
    SelectionContext); this captures the stock + craftability half so the means
    predicate and the goal share one source of truth.

    desired_stock defaults to HEAL_STOCK_FLOOR so existing callers keep working
    unchanged; Task 8 passes a higher target for marginal-fight scenarios."""
    if heal_stock(state, game_data) >= heal_stock_target(desired_stock):
        return False
    return best_craftable_heal(state, game_data) is not None
