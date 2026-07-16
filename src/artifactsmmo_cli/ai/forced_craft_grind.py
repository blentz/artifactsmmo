"""The (skill, level) of an UNAVOIDABLE craft-skill grind for a target item.

The admissibility guard for the skill-grind heuristic
(PlannerAdmissibility.lean / the skill-grind design): a craft-skill grind is a
LANDMARK — a valid heuristic term — only when crafting the target is the ONLY
way to obtain it. If the target is already owned, or a non-craft route exists
(bank withdraw, vendor, monster drop), the grind is avoidable and counting it
would make the heuristic OVER-estimate (h > true remaining) — inadmissible.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import SourceKind, obtain_sources
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState


def forced_craft_grind(target: str, needed: int, state: WorldState,
                       game_data: GameData) -> tuple[str, int] | None:
    """`(crafting_skill, crafting_level)` when crafting `target` is unavoidable
    AND the skill gate is unmet; `None` otherwise.

    Unavoidable = the target is not already owned (inventory + bank cover
    `needed`) AND `obtain_sources` yields NO non-CRAFT route (no WITHDRAW /
    RECYCLE / GATHER / BUY / DROP). Evaluated under NO_PROFILE_CONTEXT — the
    same minimal context next_grind_goal uses — which is conservative for the
    heuristic: a route it CANNOT see keeps the grind counted, but the explicit
    owned/bank check below covers the one route (banked stock) that context
    could hide."""
    stats = game_data.item_stats(target)
    if stats is None or not stats.crafting_skill:
        return None
    if game_data.crafting_recipe(target) is None:
        return None
    level = stats.crafting_level
    if state.skills.get(stats.crafting_skill, 1) >= level:
        return None
    bank = state.bank_items or {}
    if state.inventory.get(target, 0) + bank.get(target, 0) >= needed:
        return None
    sources = obtain_sources(target, state, game_data, NO_PROFILE_CONTEXT)
    if any(s.kind is not SourceKind.CRAFT for s in sources):
        return None
    return (stats.crafting_skill, level)
