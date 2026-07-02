"""Gather-resource + first-craftable-level lookups for gatherable skills."""

from artifactsmmo_cli.ai.game_data import GameData


def best_gather_resource_drop(skill: str, current_level: int,
                              game_data: GameData) -> str | None:
    """Drop item of the highest-level resource gathered by `skill` at
    `level <= current_level`, or None when the skill has no gatherable resource
    usable now. Highest level = best XP per gather; ties break on the smallest
    resource code (deterministic)."""
    best_code: str | None = None
    best_level = -1
    for resource, (res_skill, res_level) in sorted(game_data.resource_skills.items()):
        if res_skill != skill or res_level > current_level:
            continue
        if res_level > best_level:
            best_level = res_level
            best_code = resource
    if best_code is None:
        return None
    return game_data.resource_drop_item(best_code)


def first_craftable_level(skill: str, game_data: GameData) -> int | None:
    """Lowest `crafting_level` among items whose `crafting_skill == skill`, or
    None when the skill crafts nothing."""
    levels = [stats.crafting_level
              for stats in game_data.all_item_stats.values()
              if stats.crafting_skill == skill]
    return min(levels) if levels else None
