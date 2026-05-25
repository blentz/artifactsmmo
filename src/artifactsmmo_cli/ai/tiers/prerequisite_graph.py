"""Pure prerequisite edges over Tier-2 meta-goals — the P3 search substrate.

`prerequisites(node, state, game_data)` returns a node's DIRECT prerequisites,
derived only from game data. Gathering and unknown-source items are leaves so
chains terminate; cycles (if any) are left for P3's visited-set traversal."""

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState


def combat_capable(state: WorldState, game_data: GameData) -> bool:
    """True when some monster is stat-beatable with the best on-hand loadout,
    using the shared `predict_win` verdict (gear + damage formula). Replaces the
    old `monster_level <= char_level + 1` proxy so the prerequisite graph agrees
    with FightAction / runtime target selection on what 'beatable' means."""
    return any(predict_win(state, game_data, code) for code in game_data._monster_level)


def best_attainable_weapon(game_data: GameData) -> str | None:
    """Highest equip_value weapon in the item table (ties broken by code), or
    None when there are no weapons."""
    best: tuple[float, str] | None = None
    for code, stats in game_data._item_stats.items():
        if stats.type_ != "weapon":
            continue
        value = equip_value(stats)
        if best is None or value > best[0] or (value == best[0] and code < best[1]):
            best = (value, code)
    return best[1] if best else None


def prerequisites(node: MetaGoal, state: WorldState, game_data: GameData) -> list[MetaGoal]:
    """Direct prerequisites of `node`, derived from game data."""
    if isinstance(node, ObtainItem):
        if node.is_satisfied(state, game_data):
            return []
        recipe = game_data.crafting_recipe(node.code)
        if recipe is not None:
            prereqs: list[MetaGoal] = []
            stats = game_data.item_stats(node.code)
            if stats is not None and stats.crafting_skill:
                prereqs.append(ReachSkillLevel(stats.crafting_skill, stats.crafting_level))
            prereqs.extend(ObtainItem(mat, qty) for mat, qty in recipe.items())
            return prereqs
        for res_code, drop in game_data._resource_drops.items():
            if drop == node.code:
                skill_level = game_data.resource_skill_level(res_code)
                if skill_level is not None:
                    return [ReachSkillLevel(skill_level[0], skill_level[1])]
        return []  # buyable / monster-drop / unknown → leaf
    if isinstance(node, ReachCharLevel):
        if combat_capable(state, game_data):
            return []
        weapon = best_attainable_weapon(game_data)
        return [ObtainItem(weapon)] if weapon is not None else []
    return []  # ReachSkillLevel → leaf (materials enter via ObtainItem chains)


def objective_roots(objective: CharacterObjective) -> list[MetaGoal]:
    """The Tier-1 objective expressed as root meta-goals for P3's search."""
    roots: list[MetaGoal] = [ReachCharLevel(objective.target_char_level)]
    roots.extend(ReachSkillLevel(skill, level)
                 for skill, level in objective.target_skill_levels.items())
    roots.extend(ObtainItem(code) for code in objective.target_gear.values())
    return roots
