"""Tests for GamePlayer._plan_or_reuse (plan-cache gating of the expensive decide band)."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


@dataclass
class _Goal:
    satisfied: bool = False

    def is_satisfied(self, state):
        return self.satisfied

    def __repr__(self):
        return "FakeGoal()"


@dataclass
class _Act:
    applicable: bool = True

    def is_applicable(self, state, game_data):
        return self.applicable

    def __repr__(self):
        return "FakeAct()"


def _player_with_stub_plan(plan, goal):
    player = GamePlayer(character="hero", dry_run=True)
    player._gear_latch._active = False
    calls = {"n": 0}

    def _fake_decide(state, game_data, actions, ctx_combat_monster):
        calls["n"] += 1
        return goal, list(plan), [{"goal": repr(goal)}]

    # Replace only the expensive band, the collaborator — not the unit under test.
    player._decide_band = _fake_decide  # type: ignore[attr-defined]
    return player, calls


def test_first_call_replans_and_caches():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is True
    assert calls["n"] == 1
    assert player._plan_cache is not None
    assert sel is goal


def test_second_call_reuses_without_replanning():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    player._plan_or_reuse(state, None, [], None)        # cycle 1: replan, cache
    player._plan_cache.advance()                         # simulate a successful execute
    player._last_outcome = "ok"
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is False
    assert calls["n"] == 1                               # decide NOT called again
    assert returned_plan[0] is plan[1]                   # serves the next step
