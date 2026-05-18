"""Seed the BlockerRegistry from documented game data (API).

Walks `GameData` and registers near-future blockers — gates the character
hasn't met yet but is close enough to reach soon. Bounds the seed by
`NEAR_FUTURE_GAP` so the registry doesn't fill with hundreds of distant
prereqs that aren't actionable.

Every blocker added here has `source="documented"`. Discovered blockers
(`source="discovered"`, like the bank 496) take precedence — `seed` only
adds entries whose code isn't already in the registry.
"""

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.blockers.registry import BlockerRegistry, BlockerState
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


NEAR_FUTURE_GAP = 5
"""Don't seed blockers more than this many levels away from the character's
current level. ReachUnlockLevelGoal.MAX_ACHIEVABLE_GAP uses the same value
so anything seeded is potentially actionable by that goal."""


def seed_documented_blockers(
    registry: BlockerRegistry,
    game_data: GameData,
    state: WorldState,
    near_future_gap: int = NEAR_FUTURE_GAP,
) -> int:
    """Populate `registry` with near-future blockers from game_data.

    Returns the number of blockers added. Idempotent — re-running with the
    same state is safe (existing entries with the same code are skipped).
    """
    added = 0

    # === Combat gates: monsters within reach but currently over-level ===
    # Each monster's effective char-level prereq is `monster_level - 1`
    # (FightAction.is_applicable allows that margin).
    for code, level in game_data._monster_level.items():
        if level <= 0:
            continue
        required_level = max(1, level - 1)
        if required_level <= state.level:
            continue  # already beatable
        if required_level - state.level > near_future_gap:
            continue  # too far out — not actionable yet
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

    # === Equip gates: equippable items above char level but within reach ===
    for code, stats in game_data._item_stats.items():
        if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
            continue
        if stats.level <= state.level:
            continue
        if stats.level - state.level > near_future_gap:
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

    # === Craft gates: recipes whose crafting_skill_level is above the char's ===
    for code, stats in game_data._item_stats.items():
        if not stats.crafting_skill or stats.crafting_level <= 0:
            continue
        current = state.skills.get(stats.crafting_skill, 0)
        if stats.crafting_level <= current:
            continue
        if stats.crafting_level - current > near_future_gap:
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

    # === Gather gates: resources whose skill_level is above the char's ===
    for resource_code, (skill, req_level) in game_data._resource_skill.items():
        current = state.skills.get(skill, 0)
        if req_level <= current:
            continue
        if req_level - current > near_future_gap:
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
