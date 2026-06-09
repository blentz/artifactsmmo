"""Pick the in-skill item to craft NOW to gain XP toward a skill gate.

The shallowest material chain (prefer materials already in inventory/bank), then
the highest skill level (more XP), tie-broken by code for determinism. Returns
None only when no in-skill recipe is craftable at the current level — which, for a
craft skill the bot can be gated on, signals a violation of the documented
monotone skill-progression property (LIV-SKILL-2). Inclusion does NOT depend on
inventory/bank availability (only ordering does), so None is a pure recipe-table
fact, free of bank-freshness false positives.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def skill_grind_target(skill: str, state: WorldState, game_data: GameData) -> str | None:
    current = state.skills.get(skill, 0)
    bank = state.bank_items or {}
    best: tuple[int, int, str] | None = None  # maximized key
    for code, stats in game_data._item_stats.items():
        if stats.crafting_skill != skill or stats.crafting_level > current:
            continue
        recipe = game_data._crafting_recipes.get(code)
        if not recipe:
            continue
        mats_missing = sum(
            max(0, qty - state.inventory.get(mat, 0) - bank.get(mat, 0))
            for mat, qty in recipe.items()
        )
        key = (-mats_missing, stats.crafting_level, code)
        if best is None or key > best:
            best = key
    return best[2] if best is not None else None
