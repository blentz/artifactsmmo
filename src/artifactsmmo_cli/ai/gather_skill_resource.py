"""Gather-resource + first-craftable-level lookups for gatherable skills."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive


def best_gather_resource_drop(skill: str, current_level: int,
                              game_data: GameData) -> str | None:
    """Drop item of the highest-level resource gathered by `skill` at
    `level <= current_level`, or None when the skill has no gatherable resource
    that still pays XP. Highest level = best XP per gather; ties break on the
    smallest resource code (deterministic).

    XP-POSITIVE (live Robby 2026-08-05, 24 wasted `Gather(sunflower_field)`
    cycles at alchemy 17): the highest usable resource can itself sit in the
    server's zero-xp band — `sunflower_field` is alchemy level 1, and alchemy
    has nothing between it and the character's 17, so every gather paid nothing
    and the grind could never advance. Because this picks the HIGHEST resource
    in range, a grey best means every candidate is grey, so the honest answer is
    None: the caller (`next_grind_goal`) then reports "cannot grind from here"
    and the arbiter spends the cycle on a goal that can actually progress,
    instead of burning it on a gather with no xp behind it."""
    best_code: str | None = None
    best_level = -1
    for resource, (res_skill, res_level) in sorted(game_data.resource_skills.items()):
        if res_skill != skill or res_level > current_level:
            continue
        if res_level > best_level:
            best_level = res_level
            best_code = resource
    if best_code is None or not skill_xp_positive(best_level, current_level):
        return None
    return game_data.resource_drop_item(best_code)


def first_craftable_level(skill: str, game_data: GameData) -> int | None:
    """Lowest `crafting_level` among items whose `crafting_skill == skill`, or
    None when the skill crafts nothing."""
    levels = [stats.crafting_level
              for stats in game_data.all_item_stats.values()
              if stats.crafting_skill == skill]
    return min(levels) if levels else None
