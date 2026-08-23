"""Decision is a named branch point. It is never planned; it resolves to a Goal
or to another Decision."""
from artifactsmmo_cli.ai.decision import Decision, resolve_node
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from tests.test_ai.fixtures import make_state


class _Fixed(Decision):
    name = "Fixed"

    def __init__(self, child):
        self._child = child

    def resolve(self, state, game_data, ctx, history):
        return self._child


def test_resolve_node_returns_a_goal_unchanged():
    goal = WaitGoal()
    assert resolve_node(goal, make_state(), None, None, None) is goal


def test_resolve_node_walks_a_decision_to_its_goal():
    goal = WaitGoal()
    assert resolve_node(_Fixed(goal), make_state(), None, None, None) is goal


def test_resolve_node_walks_nested_decisions():
    goal = WaitGoal()
    nested = _Fixed(_Fixed(goal))
    assert resolve_node(nested, make_state(), None, None, None) is goal


def test_a_decision_resolving_to_none_yields_none():
    assert resolve_node(_Fixed(None), make_state(), None, None, None) is None


def test_a_cycle_raises_rather_than_hanging():
    """A Decision graph must be acyclic. A cycle is a programming error and
    must fail loudly, not spin."""
    class _Loop(Decision):
        name = "Loop"

        def resolve(self, state, game_data, ctx, history):
            return self

    try:
        resolve_node(_Loop(), make_state(), None, None, None)
    except RecursionError as exc:
        assert "Loop" in str(exc)
    else:
        raise AssertionError("expected RecursionError")
