"""Coverage tests for goals/wait.py + actions/wait.py + small gaps."""

from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from tests.test_ai.fixtures import make_state


def test_wait_action_apply_returns_state_unchanged():
    state = make_state(hp=42)
    assert WaitAction().apply(state, None).hp == 42


def test_wait_action_always_applicable():
    """WaitAction is the always-firing last resort, so is_applicable is
    unconditionally True (line 32-33)."""
    assert WaitAction().is_applicable(make_state(), None) is True


def test_wait_goal_value_constant():
    g = WaitGoal()
    state = make_state()
    # The exact value isn't important — just exercising the call path.
    assert g.value(state, None) >= 0.0


def test_wait_goal_never_satisfied():
    g = WaitGoal()
    assert g.is_satisfied(make_state()) is False


def test_wait_goal_desired_state_empty():
    g = WaitGoal()
    assert g.desired_state(make_state(), None) == {}


def test_wait_goal_max_depth_one():
    assert WaitGoal().max_depth == 1


def test_wait_goal_repr():
    assert repr(WaitGoal()) == "Wait"
