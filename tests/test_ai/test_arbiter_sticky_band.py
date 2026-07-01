"""Regression: arbiter sticky commitment must not preempt a higher-priority
(lower band) candidate.

Trace play-trace-Robby.jsonl 2026-07-01: Robby committed to a band-3 fallback
grind `GatherMaterials(copper_ring)` (jewelrycrafting) after a transient window,
then froze at char level 4 for 35+ cycles because the sticky short-circuit kept
returning the committed goal AHEAD of the plannable band-2 objective step
`GrindCharacterXP(green_slime)` — which was never even tried. See
docs/PLAN_sticky_band_aware.md.

The fix: sticky may defend the committed goal within-or-below its band, but a
STRICTLY LOWER band candidate that precedes it blocks the sticky short-circuit,
so the ordered walk runs and the higher-priority step wins.
"""
from collections.abc import Callable

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.arbiter_select import BAND_DISCRETIONARY, Candidate, select_pure
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState


def test_discretionary_band_literal_matches_constant():
    """`select_pure` inlines the discretionary threshold as the literal `4` (the
    extractor's v1 subset can't resolve a module constant in the pure core). Guard
    against drift between that literal and BAND_DISCRETIONARY."""
    assert BAND_DISCRETIONARY == 4


class _StubGoal(Goal):
    """Pure-data Goal with a unique repr — a tagged candidate id."""

    def __init__(self, tag: str) -> None:
        self._tag = tag

    def __repr__(self) -> str:
        return self._tag

    def is_satisfied(self, state: WorldState) -> bool:  # pragma: no cover
        return False

    def value(self, *args, **kwargs) -> float:  # pragma: no cover
        return 0.0

    def desired_state(self, *args, **kwargs) -> dict[str, object]:  # pragma: no cover
        return {}


def _closures(
    plannable: set[str],
) -> tuple[Callable[[Goal], list[Action]], Callable[[Goal], bool], Callable[[Goal], bool]]:
    fake: list[Action] = []

    def try_plan(goal: Goal) -> list[Action]:
        return [fake] if repr(goal) in plannable else []  # type: ignore[list-item]

    def is_satisfied(goal: Goal) -> bool:
        return False

    def is_suppressed(goal: Goal) -> bool:
        return False

    return try_plan, is_satisfied, is_suppressed


def _cand(tag: str, is_means: bool, band: int) -> Candidate:
    return Candidate(goal=_StubGoal(tag), is_means=is_means, repr_=tag, band=band)


def test_committed_lower_band_grind_yields_to_higher_band_step():
    """The exact freeze: committed band-3 grind loses to a plannable band-2 step."""
    step = _cand("GrindCharacterXP(green_slime)", is_means=True, band=2)
    grind = _cand("GatherMaterials(copper_ring)", is_means=True, band=3)
    # Candidate order mirrors _build_candidates: top step (band 2) precedes the
    # fallback grind (band 3).
    candidates = [step, grind]
    try_plan, is_sat, is_sup = _closures(plannable={repr(step.goal), repr(grind.goal)})

    chosen, plan, new_committed = select_pure(
        candidates=candidates,
        committed_repr="GatherMaterials(copper_ring)",  # the stale commit
        try_plan=try_plan,
        is_satisfied=is_sat,
        is_suppressed=is_sup,
    )

    assert repr(chosen) == "GrindCharacterXP(green_slime)"
    assert len(plan) > 0
    assert new_committed == "GrindCharacterXP(green_slime)"


def test_committed_same_band_is_still_kept():
    """Within-band anti-thrash preserved: committed defends against an equal-band
    peer that precedes it (the sticky-idempotence contract)."""
    first = _cand("AcceptTask", is_means=True, band=4)
    committed = _cand("PursueTask", is_means=True, band=4)
    candidates = [first, committed]  # peer precedes committed, SAME band
    try_plan, is_sat, is_sup = _closures(plannable={"AcceptTask", "PursueTask"})

    chosen, _plan, new_committed = select_pure(
        candidates=candidates,
        committed_repr="PursueTask",
        try_plan=try_plan,
        is_satisfied=is_sat,
        is_suppressed=is_sup,
    )

    assert repr(chosen) == "PursueTask"
    assert new_committed == "PursueTask"


def test_committed_discretionary_task_exempt_from_band_preemption():
    """Narrow rule: a committed DISCRETIONARY task (band 4) is NOT preempted by a
    lower-band step — income tasks stay governed by the semantic worth gate, not
    this structural band rule (preserves the worth-gate epic's arbitration)."""
    step = _cand("GatherMaterials(copper_dagger)", is_means=True, band=2)
    task = _cand("PursueTask(cooked_gudgeon)", is_means=True, band=4)
    candidates = [step, task]  # band-2 step precedes the band-4 committed task
    try_plan, is_sat, is_sup = _closures(
        plannable={"GatherMaterials(copper_dagger)", "PursueTask(cooked_gudgeon)"})

    chosen, _plan, new_committed = select_pure(
        candidates=candidates,
        committed_repr="PursueTask(cooked_gudgeon)",
        try_plan=try_plan,
        is_satisfied=is_sat,
        is_suppressed=is_sup,
    )

    assert repr(chosen) == "PursueTask(cooked_gudgeon)"  # committed task kept
    assert new_committed == "PursueTask(cooked_gudgeon)"


def test_committed_higher_band_still_wins_over_lower_band_when_first():
    """A committed candidate that is itself the lowest band present is still
    defended (nothing lower precedes it)."""
    committed = _cand("GrindCharacterXP(green_slime)", is_means=True, band=2)
    grind = _cand("GatherMaterials(copper_ring)", is_means=True, band=3)
    candidates = [committed, grind]
    try_plan, is_sat, is_sup = _closures(plannable={repr(committed.goal), repr(grind.goal)})

    chosen, _plan, new_committed = select_pure(
        candidates=candidates,
        committed_repr="GrindCharacterXP(green_slime)",
        try_plan=try_plan,
        is_satisfied=is_sat,
        is_suppressed=is_sup,
    )

    assert repr(chosen) == "GrindCharacterXP(green_slime)"
    assert new_committed == "GrindCharacterXP(green_slime)"
