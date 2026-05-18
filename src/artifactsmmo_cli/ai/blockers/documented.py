"""Seed the BlockerRegistry from documented game data (API).

Walks `GameData` and registers every prereq the character hasn't met yet
as a blocker. The registry becomes the full documented progression map —
combat, equip, craft, gather gates spanning the whole game.

Filtering (e.g. "near-future actionable" vs "long-term") is the *caller's*
concern: goals like ReachUnlockLevelGoal apply their own gap caps when
iterating the registry. Don't filter at seed time — that hides
information the strategic layer needs to plan multi-step paths.

Every blocker added here has `source="documented"`. Discovered blockers
(`source="discovered"`, like the bank 496) take precedence — `seed` only
adds entries whose code isn't already in the registry. Idempotent.

Optional `max_gap` parameter accepts a per-call cap if a caller wants a
filtered seed (tests use this). Default None = seed everything.
"""

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.blockers.registry import BlockerRegistry, BlockerState
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def seed_documented_blockers(
    registry: BlockerRegistry,
    game_data: GameData,
    state: WorldState,
    max_gap: int | None = None,
) -> int:
    """Populate `registry` with documented blockers from game_data.

    Args:
        max_gap: optional cap on level/skill distance. None = seed all.
            Callers wanting only near-future actionable blockers can pass
            a small int; the registry itself imposes no cap.

    Returns the number of blockers added. Idempotent.
    """
    added = 0

    def _within_gap(distance: int) -> bool:
        return max_gap is None or distance <= max_gap

    # === Combat gates ===
    for code, level in game_data._monster_level.items():
        if level <= 0:
            continue
        required_level = max(1, level - 1)
        if required_level <= state.level:
            continue
        if not _within_gap(required_level - state.level):
            continue
        blocker_code = f"fight:{code}"
        if registry.is_blocked(blocker_code):
            continue
        registry.blockers[blocker_code] = BlockerState(
            code=blocker_code,
            unlock_monster=code,
            required_level=required_level,
            source="documented",
        )
        added += 1

    # === Equip gates ===
    for code, stats in game_data._item_stats.items():
        if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
            continue
        if stats.level <= state.level:
            continue
        if not _within_gap(stats.level - state.level):
            continue
        blocker_code = f"equip:{code}"
        if registry.is_blocked(blocker_code):
            continue
        registry.blockers[blocker_code] = BlockerState(
            code=blocker_code,
            required_level=stats.level,
            source="documented",
        )
        added += 1

    # === Craft gates ===
    for code, stats in game_data._item_stats.items():
        if not stats.crafting_skill or stats.crafting_level <= 0:
            continue
        current = state.skills.get(stats.crafting_skill, 0)
        if stats.crafting_level <= current:
            continue
        if not _within_gap(stats.crafting_level - current):
            continue
        blocker_code = f"craft:{code}"
        if registry.is_blocked(blocker_code):
            continue
        registry.blockers[blocker_code] = BlockerState(
            code=blocker_code,
            required_skill=stats.crafting_skill,
            required_skill_level=stats.crafting_level,
            source="documented",
        )
        added += 1

    # === Gather gates ===
    for resource_code, (skill, req_level) in game_data._resource_skill.items():
        current = state.skills.get(skill, 0)
        if req_level <= current:
            continue
        if not _within_gap(req_level - current):
            continue
        blocker_code = f"gather:{resource_code}"
        if registry.is_blocked(blocker_code):
            continue
        registry.blockers[blocker_code] = BlockerState(
            code=blocker_code,
            required_skill=skill,
            required_skill_level=req_level,
            source="documented",
        )
        added += 1

    return added
