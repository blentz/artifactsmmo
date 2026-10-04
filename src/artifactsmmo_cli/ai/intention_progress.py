"""The intention's progress measure (Phase 4-2a of
docs/PLAN_decision_architecture_redesign.md).

An intention ends on a fact. One such fact is that its progress has not moved
for `STALL_CYCLES` of its own cycles; this module says what "moved" means.

A character grind is measured in character XP and a skill grind in that
skill's XP — the quantity the goal exists to raise. Every other goal has no XP
measure: its plan comes from decomposition, whose legs are proved to deliver
(`Formal.CommittedLoop.committed_loop_delivers`), so one of its actions
succeeding IS the progress. Only cycles that ran the committed goal count; a
guard that interrupts it (RestoreHP between fights) is neither progress nor
stall.

This replaces the stuck ladder's GOAL_OSCILLATION suppression, which read the
ordinary fight -> rest -> fight loop with two lost fights as a livelock and
suppressed the grind for 5 cycles (93 suppressions in 7 days to 2026-10-04,
66 of them HAL's vampire grind).
"""

from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.world_state import WorldState

STALL_CYCLES = 20
"""Committed cycles without progress before the intention is abandoned as
stalled. A grind's fight or craft lands well inside it; a plan leg that keeps
failing, or a fight that never pays, does not."""

Measure = tuple[int, int]


def progress_measure(goal: Goal, state: WorldState) -> Measure | None:
    """(level, xp) of what `goal` raises, or None for a goal with no XP
    measure. Level first, so a level-up that wraps `xp` still compares up."""
    if isinstance(goal, GrindCharacterXPGoal):
        return (state.level, state.xp)
    if isinstance(goal, ReachSkillGoal):
        return (state.skills.get(goal.skill, 1), state.skill_xp.get(goal.skill, 0))
    return None


def progressed(before: Measure | None, after: Measure | None, ok: bool) -> bool:
    """Did one committed cycle move the intention forward? With a measure, it
    must have risen; without one, the cycle's action must have succeeded."""
    if before is None or after is None:
        return ok
    return after > before
