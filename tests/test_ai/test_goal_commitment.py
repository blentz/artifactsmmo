"""Sticky goal commitment + safety preemption in AIPlayer._select_goal.

The player must persist a selected goal across cycles (stop thrashing) while
still letting an HP-critical preemptive goal interrupt when it outranks the
commitment.
"""

from artifactsmmo_cli.ai.player import GamePlayer


class _Stats:
    def __init__(self) -> None:
        self.nodes_explored = 1
        self.max_depth_reached = 1
        self.timed_out = False


class _FakePlanner:
    """Returns a one-action plan for goals whose repr is in `plannable`."""

    def __init__(self, plannable: set[str]) -> None:
        self._plannable = plannable
        self.last_stats = _Stats()

    def plan(self, state, goal, actions, game_data, history):
        return ["ACTION"] if repr(goal) in self._plannable else []


class _FakeGoal:
    def __init__(self, name: str, *, preemptive: bool = False, satisfied: bool = False) -> None:
        self._name = name
        self.preemptive = preemptive
        self._satisfied = satisfied

    def is_satisfied(self, state) -> bool:
        return self._satisfied

    def __repr__(self) -> str:
        return self._name


def _player(plannable: set[str], committed: str | None) -> GamePlayer:
    p = GamePlayer.__new__(GamePlayer)
    p.planner = _FakePlanner(plannable)
    p.history = None
    p.verbose = False
    p._committed_goal_name = committed
    return p


def _select(player, ranked):
    """ranked: list of (goal, priority). Returns (selected_repr, plan, committed)."""
    selected, plan, _tried = player._select_goal(
        state=None, game_data=None, actions=[], goal_priorities=ranked
    )
    return (repr(selected) if selected else None), plan, player._committed_goal_name


def test_sticky_keeps_committed_over_higher_nonpreemptive_rival():
    a = _FakeGoal("A")
    b = _FakeGoal("B")
    p = _player(plannable={"A", "B"}, committed="A")
    sel, plan, committed = _select(p, [(b, 100.0), (a, 50.0)])
    assert sel == "A"  # sticky: B is higher but not preemptive
    assert committed == "A"


def test_preemptive_goal_outranking_interrupts_commitment():
    a = _FakeGoal("A")
    hp = _FakeGoal("RestoreHP", preemptive=True)
    p = _player(plannable={"A", "RestoreHP"}, committed="A")
    sel, plan, committed = _select(p, [(hp, 999.0), (a, 50.0)])
    assert sel == "RestoreHP"
    assert committed == "RestoreHP"


def test_preemptive_goal_not_outranking_does_not_interrupt():
    a = _FakeGoal("A")
    hp = _FakeGoal("RestoreHP", preemptive=True)
    p = _player(plannable={"A", "RestoreHP"}, committed="A")
    sel, plan, committed = _select(p, [(a, 50.0), (hp, 10.0)])
    assert sel == "A"  # minor HP loss must not break the commitment
    assert committed == "A"


def test_reselect_when_committed_goal_cannot_plan():
    a = _FakeGoal("A")
    b = _FakeGoal("B")
    p = _player(plannable={"B"}, committed="A")  # A no longer plannable
    sel, plan, committed = _select(p, [(b, 100.0), (a, 50.0)])
    assert sel == "B"
    assert committed == "B"


def test_reselect_when_committed_goal_satisfied():
    a = _FakeGoal("A", satisfied=True)
    b = _FakeGoal("B")
    p = _player(plannable={"A", "B"}, committed="A")
    sel, plan, committed = _select(p, [(b, 100.0), (a, 50.0)])
    assert sel == "B"
    assert committed == "B"


def test_no_commitment_picks_highest_plannable_and_commits():
    a = _FakeGoal("A")
    b = _FakeGoal("B")
    p = _player(plannable={"A", "B"}, committed=None)
    sel, plan, committed = _select(p, [(b, 100.0), (a, 50.0)])
    assert sel == "B"
    assert committed == "B"


def test_preemption_scan_stops_at_zero_priority_then_sticks():
    """With a commitment, the preemption scan stops at the first <=0 priority and
    falls through to keep the committed goal."""
    a = _FakeGoal("A")
    b = _FakeGoal("B")
    p = _player(plannable={"A", "B"}, committed="A")
    sel, plan, committed = _select(p, [(a, 50.0), (b, 0.0)])
    assert sel == "A"
    assert committed == "A"


def test_returns_none_when_nothing_plannable():
    a = _FakeGoal("A")
    p = _player(plannable=set(), committed="A")
    sel, plan, committed = _select(p, [(a, 50.0)])
    assert sel is None
    assert plan == []
    assert committed is None


def test_zero_priority_goals_are_skipped():
    a = _FakeGoal("A")
    b = _FakeGoal("B")
    p = _player(plannable={"A", "B"}, committed=None)
    # Caller passes goal_priorities sorted descending; B has priority 0 so the
    # selector must skip it and commit to A.
    sel, plan, committed = _select(p, [(a, 50.0), (b, 0.0)])
    assert sel == "A"
    assert committed == "A"
