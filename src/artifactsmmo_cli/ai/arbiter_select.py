"""Pure core of `StrategyArbiter.select`: the interrupt pre-pass, then the
candidate walk with sticky commitment.

Extracted so the Lean model in `formal/Formal/ArbiterSelect.lean` can mirror the
EXACT decision logic without dragging Goal classes, the planner, or the world
state into the model. The production `StrategyArbiter.select` builds inputs
(interrupts + candidates + committed-repr + per-goal planning closure +
satisfaction predicate) then delegates here.

INTERRUPTS (Phase 5-2a of docs/PLAN_decision_architecture_redesign.md): the
guards — HP critical, bag/bank pressure, GE cancel, ... — are preconditions of
continuing whatever the character is doing. `select_interrupt` runs them FIRST,
in `GUARD_ORDER`: the first one that is not satisfied and plans wins, and the
commitment is untouched (the intention resumes after it). They used to be
candidates walked in band order against the objective, with a `guard_precedes`
rule blocking the sticky commitment whenever one was present.

The WALK (`select_pure`) then sees only means — collect-reward, objective step,
raids, fallback steps, discretionary — in that band order. Sticky commitment:
if `committed_repr` matches a candidate and no strictly-higher-priority band
precedes it (discretionary is exempt), try planning the committed candidate
first. Otherwise the walk returns the first plannable,
non-satisfied candidate, which becomes the new commitment.
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
BAND_RAID = 3
"""Open raid windows. RENUMBERED IN 2026-08-23 (wave 3a fix-round 1) from
BAND_DISCRETIONARY, which sat BELOW the fallback steps.

`_raid_candidates`' docstring says a raid should yield "to every guard and
objective step, which is the right priority for a timed bonus" — and that is
still exactly what this band does. What it stopped doing is yielding to a
FALLBACK step, which is by definition what the bot fell back to BECAUSE the
objective step produced nothing. `audit/liveness_completeness` had already
classified `ParticipateRaidGoal` as UNREACHABLE for this reason before the
wave-3a flip made it visible offline: "a timed bonus that yields to a step
present in 14,064 of 14,064 cycles is one that expires unused, so the
rationale defeats itself".

Not fixed by giving the raid scenario real combat stats instead: `scenario.py`
records that that was TRIED and rejected, because stats alone "unlocks
unrelated work (the pair first planned Gather(gold_rocks), not the boss)" —
i.e. it moves which candidate preempts the raid without changing that one
does."""
BAND_FALLBACK_STEP = 4
BAND_DISCRETIONARY = 5


@dataclass(frozen=True)
class Candidate:
    """A (goal, repr, band) triple — the unit the pure selectors walk.

    `band` is the priority tier the candidate was built in (0 guards, 1 collect,
    2 top objective step, 3 open raid windows, 4 fallback steps,
    5 discretionary). Band-0 candidates are interrupts (`select_interrupt`);
    every other band is a means walked by `select_pure`. Sticky commitment may
    defend the committed goal within-or-below its own band but must never
    preempt a STRICTLY LOWER band (higher-priority) candidate — see
    `lower_band_precedes` in `select_pure`.
    """
    goal: Goal
    repr_: str
    band: int


def _precedes(candidates: list[Candidate], a_repr: str, b_repr: str) -> bool:
    """True if the candidate with repr a_repr appears before b_repr."""
    a_idx = next((i for i, c in enumerate(candidates) if c.repr_ == a_repr), None)
    b_idx = next((i for i, c in enumerate(candidates) if c.repr_ == b_repr), None)
    if a_idx is None or b_idx is None:
        return False
    return a_idx < b_idx


def select_interrupt(
    interrupts: list[Candidate],
    try_plan: Callable[[Goal], list[Action]],
    is_satisfied: Callable[[Goal], bool],
) -> tuple[Goal | None, list[Action]]:
    """The interrupt pre-pass: the first interrupt, in order, that is not
    satisfied and plans. (None, []) when none does — the intention runs."""
    for cand in interrupts:
        if is_satisfied(cand.goal):
            continue
        plan = try_plan(cand.goal)
        if len(plan) > 0:
            return cand.goal, plan
    return None, []


def select_pure(
    candidates: list[Candidate],
    committed_repr: str | None,
    try_plan: Callable[[Goal], list[Action]],
    is_satisfied: Callable[[Goal], bool],
) -> tuple[Goal | None, list[Action], str | None]:
    """Sticky-then-walk selection over the means. Returns (chosen_goal, plan,
    new_committed_repr): the chosen goal becomes the commitment. On no-plan
    returns (None, [], None).

    Pure w.r.t. its closures: side effects (e.g. recording planning attempts)
    happen inside `try_plan`, not here. The selector calls `try_plan` AT MOST
    ONCE per distinct goal (the sticky-attempt's repr is recorded so the walk
    skips re-trying it).
    """
    tried_repr: str | None = None

    if committed_repr is not None:
        committed_cand = next(
            (c for c in candidates if c.repr_ == committed_repr),
            None,
        )
        if committed_cand is not None and not is_satisfied(committed_cand.goal):
            # A strictly-lower band (higher-priority) candidate that precedes the
            # committed one blocks the sticky short-circuit: the ordered walk must
            # get to try the higher-priority candidate first. Without this a stale
            # commitment to a fallback grind (band 4) preempts the plannable
            # objective step (band 2) forever — the copper_ring char-XP freeze,
            # trace 2026-07-01. Discretionary commits (band 5) are EXEMPT: committed
            # income tasks stay governed by the semantic worth gate, not this
            # structural rule, so their deliberate task-vs-step arbitration is
            # preserved.
            # `5` is BAND_DISCRETIONARY inlined: the extractor's v1 subset can't
            # resolve a module constant inside the pure core, and the band tiers
            # are a fixed 6-value enum. Keep in sync with BAND_DISCRETIONARY —
            # `test_discretionary_band_literal_matches_constant` is the guard,
            # and it CAUGHT this renumbering when BAND_RAID was inserted.
            lower_band_precedes = committed_cand.band < 5 and any(
                c.band < committed_cand.band and _precedes(candidates, c.repr_, committed_repr)
                for c in candidates
            )
            if not lower_band_precedes:
                plan = try_plan(committed_cand.goal)
                tried_repr = committed_repr
                if len(plan) > 0:
                    return committed_cand.goal, plan, committed_repr

    for cand in candidates:
        if cand.repr_ == tried_repr:
            continue
        if is_satisfied(cand.goal):
            continue
        plan = try_plan(cand.goal)
        if len(plan) > 0:
            return cand.goal, plan, cand.repr_

    return None, [], None


def arbitrate(
    interrupts: list[Candidate],
    candidates: list[Candidate],
    committed_repr: str | None,
    try_plan: Callable[[Goal], list[Action]],
    is_satisfied: Callable[[Goal], bool],
) -> tuple[Goal | None, list[Action], str | None]:
    """Interrupts first, then the means: a winning interrupt keeps the
    commitment (the intention resumes after it); otherwise `select_pure`."""
    interrupt = select_interrupt(interrupts, try_plan, is_satisfied)
    # A chosen interrupt always carries a non-empty plan, and only then.
    if len(interrupt[1]) > 0:
        return interrupt[0], interrupt[1], committed_repr
    return select_pure(candidates, committed_repr, try_plan, is_satisfied)
