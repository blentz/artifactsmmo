"""The intention's progress measure (Phase 4-2a of
docs/PLAN_decision_architecture_redesign.md).

An intention ends on a fact. One such fact is that its progress has not moved
for `STALL_CYCLES` of its own cycles; this module says what "moved" means.

A cycle progresses when the committed goal's action SUCCEEDED or the quantity
the goal exists to raise went up (character XP for a character grind, that
skill's XP for a skill grind). Its plan comes from decomposition, whose legs are
proved to deliver (`Formal.CommittedLoop.committed_loop_delivers`), so a
successful leg is progress even before it pays XP. A stall is therefore
`STALL_CYCLES` committed cycles with neither: a fight grind that keeps losing,
or a leg that keeps failing.

WITNESSED 2026-10-04 (restart 12:19Z): the first rule counted only XP for a
skill grind, and a crafting climb gathers for more than 20 cycles before its
craft pays — 90 false stalls in 6.5 h (HAL / Lor weaponcrafting, R2D2
gear/jewelry), each dropped and re-chosen at once. Only cycles that ran the committed goal count; a
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

BUDGET_CYCLES = 100
"""Committed cycles an intention may hold before goal choice re-ranks (Phase
4-2b). Fairness, not liveness: progress does not reset it. On exhaustion the
intention ends and its root YIELDS for one turn, so the next served root heads
the walk; the exhausted root competes again after that. Replaces focus aging
and the d'Hondt interleave."""

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
    """Did one committed cycle move the intention forward: its action
    succeeded, or its XP measure rose (a lost fight that still levelled up
    counts)?"""
    if ok:
        return True
    return before is not None and after is not None and after > before
