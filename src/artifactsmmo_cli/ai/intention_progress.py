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

from collections.abc import Mapping
from dataclasses import replace

from artifactsmmo_cli.ai.arbiter_select import BAND_FALLBACK_STEP, BAND_STEP, Candidate
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
intention ends and its goal goes to the back of the turn order (`rotate`), so
every other plannable goal gets an intention before it runs again.
Replaces focus aging and the d'Hondt interleave."""

EXIT_CYCLES = 200
"""Committed cycles, across intentions, with no progress at all (no successful
leg, no XP) before the run stops (`recovery.StuckExit`, Phase 4-3c). Two full
budgets and ten stall windows: every intention in that span stalled or spent
its budget without one successful leg. The last resort, and the only exit."""

TURN_LOG_SIZE = 32
"""Spent budgets remembered per character. A walk offers a handful of step and
fallback goals (seven at most, live 2026-10-05); the log keeps far more, so a
goal still on offer is never forgotten while it waits."""

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


def _demote(candidates: list[Candidate], served: str) -> list[Candidate]:
    """The candidate list with `served` moved behind its peers: every candidate
    whose repr is `served` goes to the END of its band, and the objective step's
    band counts as the fallback chain's, so the next step or fallback is tried
    first. Nothing is removed — when no peer can plan, the served goal still
    runs, so a turn never empties."""
    out = list(candidates)
    for hit in [c for c in candidates if c.repr_ == served]:
        band = BAND_FALLBACK_STEP if hit.band == BAND_STEP else hit.band
        del out[next(i for i, c in enumerate(out) if c is hit)]
        at = max((i + 1 for i, c in enumerate(out) if c.band <= band), default=0)
        out.insert(at, replace(hit, band=band))
    return out


def rotate(candidates: list[Candidate], turns: Mapping[str, int]) -> list[Candidate]:
    """The candidate list in turn order (Phase 5-2c-iii-a): within each band —
    the objective step's counting as the fallback chain's — the goals that never
    had a turn keep the walk's order and come first, and the goals that did
    follow, least recently served first. A served step leaves the step band, so
    it cannot preempt the goal whose turn it is. Nothing is removed: a lone
    plannable goal still runs.

    `turns` maps a goal repr to the sequence number of its last spent budget
    (`record_turn`). Each served goal is demoted to the end of its band in
    increasing turn order, so the most recently served ends last.

    WHY A TURN ORDER, NOT ONE YIELD (2026-10-05). The yield (Phase 4-2b)
    remembered ONE goal and cleared when the next intention ended, so the root's
    step returned at once: A, B, A, B. A walk alternative third or later never
    had a turn while the first two could plan — the orphan skill roots and, in
    5-2c-iii, the task objective. Proved fair in `Formal.TurnRotation`: with k
    plannable goals, every one is picked within k - 1 turns
    (`rotation_fair`)."""
    out = candidates
    for served in sorted({c.repr_ for c in candidates if c.repr_ in turns},
                         key=turns.__getitem__):
        out = _demote(out, served)
    return out


def record_turn(turns: Mapping[str, int], goal: str) -> dict[str, int]:
    """`turns` with `goal`'s turn recorded as the newest, keeping the
    `TURN_LOG_SIZE` most recent. A goal dropped from the log counts as never
    served, which only moves it forward."""
    logged = {**turns, goal: max(turns.values(), default=0) + 1}
    kept = sorted(logged, key=logged.__getitem__)[-TURN_LOG_SIZE:]
    return {code: logged[code] for code in kept}
