"""Differential test: Python `select_pure` (the extracted pure core of
`StrategyArbiter.select`) must agree with the Lean oracle `selectPure`.

Inputs are generated as a list of `(id, is_means, plannable, satisfied, suppressed)`
quintuples plus an optional `committed_id`. We enforce the production
well-formedness assumption that ids are GLOBALLY unique across the list (the
Python `_precedes` compares by `repr`, and production guards/means have
disjoint Goal classes whose reprs never collide).

We test the sticky-safety property end-to-end: scenarios where a committed
means is active AND a guard fires AND is plannable — the guard MUST win.
"""
from collections.abc import Callable

from hypothesis import HealthCheck, given, settings, strategies as st

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.arbiter_select import Candidate, select_pure
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle


class _StubGoal(Goal):
    """A pure-data Goal with a unique repr — mirrors a tagged candidate id."""

    def __init__(self, tag: int) -> None:
        self._tag = tag

    def __repr__(self) -> str:
        return f"Stub<{self._tag}>"

    def is_satisfied(self, state: WorldState) -> bool:  # pragma: no cover
        # The pure selector calls is_satisfied via the `is_satisfied` closure
        # we pass in, not via this method. Method exists only so the abstract
        # base class is instantiable.
        return False

    def value(self, *args, **kwargs) -> float:  # pragma: no cover
        return 0.0

    def desired_state(self, *args, **kwargs) -> dict[str, object]:  # pragma: no cover
        return {}


def _build_candidates_and_closures(
    raw: list[tuple[int, bool, bool, bool, bool]],
) -> tuple[
    list[Candidate],
    Callable[[Goal], list[Action]],
    Callable[[Goal], bool],
    Callable[[Goal], bool],
]:
    """Build candidates + (try_plan, is_satisfied, is_suppressed) closures from
    a list of (id, is_means, plannable, satisfied, suppressed) quintuples."""
    tag_to_flags: dict[int, tuple[bool, bool, bool]] = {}
    candidates: list[Candidate] = []
    for tag, is_means, plannable, satisfied, suppressed in raw:
        goal = _StubGoal(tag)
        candidates.append(Candidate(goal=goal, is_means=is_means, repr_=repr(goal)))
        tag_to_flags[tag] = (plannable, satisfied, suppressed)

    fake_action_list: list[Action] = []

    def try_plan(goal: Goal) -> list[Action]:
        tag = int(repr(goal).removeprefix("Stub<").removesuffix(">"))
        return [fake_action_list] if tag_to_flags[tag][0] else []  # type: ignore[list-item]

    def is_satisfied(goal: Goal) -> bool:
        tag = int(repr(goal).removeprefix("Stub<").removesuffix(">"))
        return tag_to_flags[tag][1]

    def is_suppressed(goal: Goal) -> bool:
        tag = int(repr(goal).removeprefix("Stub<").removesuffix(">"))
        return tag_to_flags[tag][2]

    return candidates, try_plan, is_satisfied, is_suppressed


def _oracle_args(
    raw: list[tuple[int, bool, bool, bool, bool]],
    committed: int | None,
) -> list[int]:
    args: list[int] = [len(raw)]
    for tag, is_means, plannable, satisfied, suppressed in raw:
        args.extend([tag, int(is_means), int(plannable), int(satisfied), int(suppressed)])
    args.extend([1 if committed is not None else 0, committed if committed is not None else 0])
    return args


def _run_python(
    raw: list[tuple[int, bool, bool, bool, bool]],
    committed: int | None,
) -> tuple[int, bool, int]:
    """Run the Python pure selector; return (chosen_id, chosen_is_means, new_committed_id)
    with -1 sentinels for None."""
    candidates, try_plan, is_satisfied, is_suppressed = _build_candidates_and_closures(raw)
    committed_repr = f"Stub<{committed}>" if committed is not None else None
    chosen, _plan, new_committed = select_pure(
        candidates=candidates,
        committed_repr=committed_repr,
        try_plan=try_plan,
        is_satisfied=is_satisfied,
        is_suppressed=is_suppressed,
    )
    if chosen is None:
        return -1, False, -1 if new_committed is None else int(new_committed.removeprefix("Stub<").removesuffix(">"))
    chosen_tag = int(repr(chosen).removeprefix("Stub<").removesuffix(">"))
    chosen_is_means = next(c.is_means for c in candidates if c.repr_ == repr(chosen))
    new_id = -1 if new_committed is None else int(new_committed.removeprefix("Stub<").removesuffix(">"))
    return chosen_tag, chosen_is_means, new_id


def _run_lean(
    raw: list[tuple[int, bool, bool, bool, bool]],
    committed: int | None,
) -> tuple[int, bool, int]:
    res = run_oracle("arbiter_select", [_oracle_args(raw, committed)])[0]
    return res["chosen_id"], res["chosen_is_means"], res["new_committed_id"]


# Hypothesis strategy: a "well-formed" list of candidates.
# - ids are globally unique
# - guards come BEFORE means in list order (production build order)
@st.composite
def _wellformed_input(draw):
    n_guards = draw(st.integers(min_value=0, max_value=3))
    n_means = draw(st.integers(min_value=0, max_value=5))
    ids = draw(st.lists(st.integers(min_value=0, max_value=999),
                        min_size=n_guards + n_means, max_size=n_guards + n_means, unique=True))
    raw: list[tuple[int, bool, bool, bool, bool]] = []
    for i in range(n_guards):
        raw.append((
            ids[i], False,
            draw(st.booleans()), draw(st.booleans()), draw(st.booleans()),
        ))
    for j in range(n_means):
        raw.append((
            ids[n_guards + j], True,
            draw(st.booleans()), draw(st.booleans()), draw(st.booleans()),
        ))
    # Committed may target an existing means id, or be absent, or target an
    # arbitrary id (testing the no-match path).
    options: list[int | None] = [None]
    options.extend(t for t, m, *_ in raw if m)
    options.append(draw(st.integers(min_value=1000, max_value=2000)))  # non-existent
    committed = draw(st.sampled_from(options))
    return raw, committed


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_wellformed_input())
def test_python_matches_lean(input_):
    raw, committed = input_
    py = _run_python(raw, committed)
    lean = _run_lean(raw, committed)
    assert py == lean, f"divergence: input={raw} committed={committed} py={py} lean={lean}"


def test_sticky_safety_guard_wins_explicit():
    """The proven sticky-safety property end-to-end: a plannable firing guard
    wins over a sticky-committed means. Pins the Python against the Lean
    oracle on the exact scenario the safety theorem covers.

    Scenario: one guard candidate (id=0, plannable), one means candidate (id=1,
    plannable). committed = 1 (the means). Both implementations MUST return 0.
    """
    raw = [
        (0, False, True, False, False),  # guard 0, plannable
        (1, True, True, False, False),   # means 1, plannable
    ]
    py = _run_python(raw, committed=1)
    lean = _run_lean(raw, committed=1)
    assert py == (0, False, -1)  # guard wins; commitment cleared
    assert lean == (0, False, -1)
    assert py == lean


def test_sticky_idempotent_means_kept():
    """No guards in the list, committed means is plannable → committed is kept.
    Pins the Python against the Lean oracle on the sticky-idempotence path."""
    raw = [
        (1, True, True, False, False),
        (2, True, True, False, False),  # committed
    ]
    py = _run_python(raw, committed=2)
    lean = _run_lean(raw, committed=2)
    assert py == (2, True, 2)
    assert lean == (2, True, 2)


def test_no_commitment_walk_returns_first_plannable():
    """No committed, first plannable in list order wins."""
    raw = [
        (0, False, False, False, False),  # guard 0, NOT plannable
        (1, False, True, False, False),   # guard 1, plannable → wins
        (2, True, True, False, False),    # means 2, plannable (skipped)
    ]
    py = _run_python(raw, committed=None)
    lean = _run_lean(raw, committed=None)
    assert py == (1, False, -1)  # guard 1 wins, commitment cleared
    assert lean == (1, False, -1)


def test_sticky_falls_through_when_committed_unplannable():
    """Committed means is non-plannable; a guard is unplannable but a discretionary
    means is plannable — walk skips tried, returns the discretionary.

    Verifies the `tried_repr` is set so the committed isn't retried in the walk,
    AND that the next plannable means after the committed wins.
    """
    raw = [
        (0, True, False, False, False),  # committed means, NOT plannable
        (1, True, True, False, False),   # later means, plannable
    ]
    py = _run_python(raw, committed=0)
    lean = _run_lean(raw, committed=0)
    assert py == (1, True, 1)
    assert lean == (1, True, 1)
