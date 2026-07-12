"""Pick the in-skill item to craft NOW to gain XP toward a skill gate.

Among items that are same-skill, in-level, and OBTAINABLE (every recipe input
reachable by gather/craft/winnable-drop), prefer the shallowest material chain
(fewest missing on hand), then the highest skill level (more XP); a full tie keeps
the FIRST-SEEN candidate (insertion order) — there is no string/alphabetical
tie-break. Returns None when no such in-skill recipe exists — the caller falls back to
LevelSkillGoal on the SAME skill (never cross-skill). Inclusion is a recipe-table
+ reachability fact, free of bank-freshness false positives (only `mats_missing`
ordering reads holdings).

`reserved`: recipe-input codes of the COMMITTED objective that the grind must not
consume (Trace 2026-06-11 19:22: copper_helmet would have eaten the 5 bars held
for copper_legs_armor).

OBTAINABILITY (Trace 2026-06-13): `skill_grind_target("weaponcrafting")` used to
pick `wooden_staff` (needs un-gettable `wooden_stick`), whose GatherMaterials
GOAP-failed; the arbiter then fell CROSS-SKILL to a gearcrafting grind, abandoning
the committed weaponcrafting objective. The recursive `_obtainable` filter excludes
such items so the reachable `copper_dagger` wins.
"""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)
from artifactsmmo_cli.ai.world_state import WorldState


def is_obtainable(code: str, state: WorldState, game_data: GameData,
                  visited: frozenset[str]) -> bool:
    """Recursive reachability: an item is obtainable when it is a gatherable
    resource drop, a winnable+locatable monster drop, OR craftable with EVERY
    recipe input recursively obtainable. A craftable item whose chain bottoms out
    in an un-gettable leaf (e.g. wooden_stick) is NOT obtainable. Cycle-safe."""
    if code in visited:
        return False
    recipe = game_data.crafting_recipe(code)
    if recipe is None:
        if code in game_data.resource_drops.values():
            return True
        return any(is_winnable(state, game_data, monster_code)
                   and game_data.monster_spawn_known(monster_code)
                   for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))
    nxt = visited | {code}
    return all(is_obtainable(mat, state, game_data, nxt) for mat in recipe)


def build_grind_candidates(skill: str, state: WorldState,
                           game_data: GameData) -> list[GrindCandidate]:
    """Hoist every in-skill craftable into a `GrindCandidate` (mats_missing
    against inventory+bank, recursive obtainability). No reservation filter —
    the caller (`skill_grind_target`) applies its own single-set filter."""
    bank = state.bank_items or {}
    candidates: list[GrindCandidate] = []
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill != skill:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        mats_missing = sum(
            max(0, qty - state.inventory.get(mat, 0) - bank.get(mat, 0))
            for mat, qty in recipe.items()
        )
        candidates.append(GrindCandidate(
            code=code,
            craft_skill=stats.crafting_skill,
            craft_level=stats.crafting_level,
            mats_missing=mats_missing,
            obtainable=is_obtainable(code, state, game_data, frozenset()),
            # No objective context in this standalone path: the live grind goes
            # through the LevelSkill action (its is_applicable calls
            # skill_grind_target for the rung); wanted has no bearing there.
            wanted=False,
        ))
    return candidates


def skill_grind_target(skill: str, state: WorldState, game_data: GameData,
                       reserved: frozenset[str] = frozenset()) -> str | None:
    candidates = [
        c for c in build_grind_candidates(skill, state, game_data)
        if not any(mat in reserved for mat in (game_data.crafting_recipe(c.code) or {}))
    ]
    chosen = skill_grind_selection_pure(skill, state.skills.get(skill, 0), candidates)
    return chosen or None
