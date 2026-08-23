"""Where a character stands on the derived ladder.

A rung is CLEARED when every normal monster in its band is winnable at
restorable HP. Boss, elite and raid content never gates it (see
`tier_ladder.NON_FARMABLE_TYPES`).

The GEAR TARGET is the rung being cleared, capped by character level — NOT the
character's level rung. Live 2026-08-22: Robby at level 30 had the level-20 rung
uncleared. Targeting level-30 gear demands `cyclops_eye`, `imp_tail` and
`demon_horn` from monsters he cannot beat, which is the same unreachable-target
failure the ladder exists to remove. Level-20 gear crafts from level-15 content,
which he has cleared by definition. Character level CAPS the target; it never
sets it.
"""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, normal_band, tier_of_level
from artifactsmmo_cli.ai.world_state import WorldState


def tier_cleared(state: WorldState, game_data: GameData, tier: int,
                 history: LearningStore | None) -> bool:
    """Is every normal monster in `tier`'s band winnable?"""
    return all(is_winnable(state, game_data, code, history)
               for code in normal_band(game_data, tier))


def next_uncleared_tier(state: WorldState, game_data: GameData,
                        history: LearningStore | None) -> int | None:
    """The lowest rung not yet cleared, or None when the ladder is finished."""
    for tier in ladder(game_data):
        if not tier_cleared(state, game_data, tier, history):
            return tier
    return None


def gear_target_tier(state: WorldState, game_data: GameData,
                     history: LearningStore | None) -> int:
    """The rung to gear for: the one being cleared, capped by character level."""
    level_rung = tier_of_level(game_data, state.level)
    clearing = next_uncleared_tier(state, game_data, history)
    if clearing is None:
        return level_rung
    return min(level_rung, clearing)
