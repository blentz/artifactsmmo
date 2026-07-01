"""Pure core of `StrategyArbiter.select`: the candidate-walk with sticky
commitment.

Extracted so the Lean model in `formal/Formal/ArbiterSelect.lean` can mirror the
EXACT decision logic (band-ordered candidates, sticky-commitment, guard
preemption) without dragging Goal classes, the planner, or the world state into
the model. The production `StrategyArbiter.select` builds inputs (candidates +
committed-repr + per-goal planning closure + suppression set) then delegates
here. Behavior is identical.

Candidates are pre-ordered: guards in `GUARD_ORDER`, then collect-reward in
`COLLECT_REWARD_ORDER`, then optional objective step, then discretionary in
`DISCRETIONARY_ORDER`. Each candidate carries an `is_means` flag (False for
guards, True for collect/step/discretionary).

Sticky-commitment: if `committed_repr` matches an is_means candidate AND no
guard candidate precedes it (i.e. there is no guard candidate at all — guards
are always prepended), try planning the committed candidate first. If it plans
and is not satisfied / suppressed, return it. Otherwise fall through to the
ordered walk.

The walk returns the first plannable, non-suppressed, non-satisfied candidate.
On success, the new committed_repr is the chosen goal's repr (if is_means) or
None (if a guard won).
"""
from collections.abc import Callable
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.goals.base import Goal

# Candidate priority bands (set by StrategyArbiter._build_candidates). Lower =
# higher priority. Sticky commitment may defend the committed goal within-or-below
# its band but never preempts a strictly-lower band. Discretionary is the lowest
# tier and is EXEMPT from band preemption: committed income tasks stay governed
# by the semantic worth gate, not this structural rule (see the worth-gate epic).
BAND_GUARD = 0
BAND_COLLECT = 1
BAND_STEP = 2
BAND_FALLBACK_STEP = 3
BAND_DISCRETIONARY = 4


@dataclass(frozen=True)
class Candidate:
    """A (goal, is_means, repr, band) tuple — the unit the pure selector walks.

    `band` is the priority tier the candidate was built in (0 guards, 1 collect,
    2 top objective step, 3 fallback steps, 4 discretionary). Sticky commitment
    may defend the committed goal within-or-below its own band but must never
    preempt a STRICTLY LOWER band (higher-priority) candidate — see
    `lower_band_precedes` in `select_pure`.
    """
    goal: Goal
    is_means: bool
    repr_: str
    band: int


def _precedes(candidates: list[Candidate], a_repr: str, b_repr: str) -> bool:
    """True if the candidate with repr a_repr appears before b_repr."""
    a_idx = next((i for i, c in enumerate(candidates) if c.repr_ == a_repr), None)
    b_idx = next((i for i, c in enumerate(candidates) if c.repr_ == b_repr), None)
    if a_idx is None or b_idx is None:
        return False
    return a_idx < b_idx


def select_pure(
    candidates: list[Candidate],
    committed_repr: str | None,
    try_plan: Callable[[Goal], list[Action]],
    is_satisfied: Callable[[Goal], bool],
    is_suppressed: Callable[[Goal], bool],
) -> tuple[Goal | None, list[Action], str | None]:
    """Sticky-then-walk selection. Returns (chosen_goal, plan, new_committed_repr).

    new_committed_repr is the chosen goal's repr if it is a means, else None
    (a guard win clears commitment). On no-plan returns (None, [], None).

    Pure w.r.t. its closures: side effects (e.g. recording planning attempts)
    happen inside `try_plan`, not here. The selector calls `try_plan` AT MOST
    ONCE per distinct goal (the sticky-attempt's repr is recorded so the walk
    skips re-trying it).
    """
    tried_repr: str | None = None

    if committed_repr is not None:
        committed_cand = next(
            (c for c in candidates if c.is_means and c.repr_ == committed_repr),
            None,
        )
        if (committed_cand is not None
                and not is_satisfied(committed_cand.goal)
                and not is_suppressed(committed_cand.goal)):
            guard_reprs = [c.repr_ for c in candidates if not c.is_means]
            guard_precedes = any(
                _precedes(candidates, gr, committed_repr) for gr in guard_reprs
            )
            # A strictly-lower band (higher-priority) candidate that precedes the
            # committed one blocks the sticky short-circuit: the ordered walk must
            # get to try the higher-priority candidate first. Without this a stale
            # commitment to a fallback grind (band 3) preempts the plannable
            # objective step (band 2) forever — the copper_ring char-XP freeze,
            # trace 2026-07-01. Discretionary commits (band 4) are EXEMPT: committed
            # income tasks stay governed by the semantic worth gate, not this
            # structural rule, so their deliberate task-vs-step arbitration is
            # preserved.
            # `4` is BAND_DISCRETIONARY inlined: the extractor's v1 subset can't
            # resolve a module constant inside the pure core, and the band tiers
            # are a fixed 5-value enum. Keep in sync with BAND_DISCRETIONARY.
            lower_band_precedes = committed_cand.band < 4 and any(
                c.band < committed_cand.band and _precedes(candidates, c.repr_, committed_repr)
                for c in candidates
            )
            if not guard_precedes and not lower_band_precedes:
                plan = try_plan(committed_cand.goal)
                tried_repr = committed_repr
                if len(plan) > 0:
                    return committed_cand.goal, plan, committed_repr

    for cand in candidates:
        if cand.repr_ == tried_repr:
            continue
        if is_suppressed(cand.goal):
            continue
        if is_satisfied(cand.goal):
            continue
        plan = try_plan(cand.goal)
        if len(plan) > 0:
            new_committed = cand.repr_ if cand.is_means else None
            return cand.goal, plan, new_committed

    return None, [], None
