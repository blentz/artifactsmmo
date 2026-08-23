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


def test_a_two_node_cycle_raises_with_full_walk():
    """A two-node cycle must report both nodes in traversal order."""
    class _CycleA(Decision):
        name = "CycleA"

        def resolve(self, state, game_data, ctx, history):
            return _cycle_b

    class _CycleB(Decision):
        name = "CycleB"

        def resolve(self, state, game_data, ctx, history):
            return _cycle_a

    _cycle_a = _CycleA()
    _cycle_b = _CycleB()

    try:
        resolve_node(_cycle_a, make_state(), None, None, None)
    except RecursionError as exc:
        # Must mention both names and show the walk order.
        assert "CycleA" in str(exc)
        assert "CycleB" in str(exc)
        assert "CycleA -> CycleB" in str(exc)
    else:
        raise AssertionError("expected RecursionError")


def test_missing_name_raises_at_class_definition():
    """A concrete Decision subclass that forgets 'name' is a programming error
    caught at class definition time, not at runtime."""
    try:
        class _NoName(Decision):
            def resolve(self, state, game_data, ctx, history):
                return None

        raise AssertionError("expected TypeError")
    except TypeError as exc:
        assert "_NoName" in str(exc)
        assert "name" in str(exc)
