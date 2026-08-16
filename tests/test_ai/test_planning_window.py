"""The cooldown IS the planning window.

The loop used to sleep out the whole cooldown and only then start the A* search,
so every replan cycle cost `cooldown + search` wall-clock and the cooldown itself
was pure idling. Two facts pin the fix:

* the search runs BEFORE `_wait_for_cooldown`, so only the unspent remainder of
  the cooldown is idled; and
* the per-cycle planning budget is the cooldown window, FLOORED at the default
  `planner._SEARCH_BUDGET_SECONDS`. The floor is load-bearing: without it a 3s
  cooldown would hand a late-ranked candidate a near-zero budget, and a no-plan
  produced under a shortened budget would be marked doomed by `_record_attempt`
  on evidence the goal never had a fair chance to refute.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.planner import _SEARCH_BUDGET_SECONDS
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_player_run import _patch_game_data_load
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd
from tests.test_ai.test_strategy_driver_tiered import _arbiter_with, _ScriptedPlanner


def _budgets_for(deadline: float | None) -> list[float | None]:
    """Run one arbiter walk with `deadline` set and return the DISTINCT budgets
    handed to the planner (a walk consults it once per candidate attempt)."""
    planner = _ScriptedPlanner(plannable={"AcceptTask"})
    arbiter = _arbiter_with(planner)
    arbiter.set_planning_deadline(deadline)
    arbiter.select(_FakeDecision(chosen_step=None),
                   make_state(task_code=None, task_total=0),
                   _make_planner_gd(),
                   [AcceptTaskAction(taskmaster_location=(2, 1))],
                   _ctx(combat_monster="chicken"))
    assert planner.budgets, "the planner must actually have been consulted"
    return sorted({b for (_r, b) in planner.budgets}, key=lambda b: (b is not None, b))


class TestCycleBudget:
    def test_no_deadline_keeps_the_default_budget(self):
        """No cooldown to spend (first cycle, an error cycle) — the planner is
        handed None and falls back to its own 15s default."""
        assert _budgets_for(None) == [None]

    def test_long_cooldown_funds_a_longer_search(self):
        """A 40s cooldown is 40s the bot cannot act in; the search may use all
        of it instead of idling 25s of it."""
        budgets = _budgets_for(time.monotonic() + 40.0)
        assert all(b is not None and 39.0 <= b <= 40.0 for b in budgets), budgets

    def test_short_cooldown_floors_at_the_default_budget(self):
        """A 3s cooldown does NOT shrink the search to 3s — the default budget is
        a floor, so no attempt is ever judged on less evidence than before."""
        assert _budgets_for(time.monotonic() + 3.0) == [_SEARCH_BUDGET_SECONDS]

    def test_expired_deadline_floors_at_the_default_budget(self):
        """The deadline passing mid-walk (an earlier candidate ate the window)
        leaves later candidates the full default budget, not a negative one."""
        assert _budgets_for(time.monotonic() - 5.0) == [_SEARCH_BUDGET_SECONDS]


class TestPlanningDeadline:
    def test_none_when_no_cooldown_is_recorded(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        assert player._planning_deadline() is None

    def test_none_when_the_cooldown_has_already_expired(self):
        player = GamePlayer(character="hero")
        player.state = make_state(
            cooldown_expires=datetime.now(tz=timezone.utc) - timedelta(seconds=5))
        assert player._planning_deadline() is None

    def test_tracks_the_remaining_cooldown(self):
        player = GamePlayer(character="hero")
        player.state = make_state(
            cooldown_expires=datetime.now(tz=timezone.utc) + timedelta(seconds=40))
        deadline = player._planning_deadline()
        assert deadline is not None
        assert 39.0 <= deadline - time.monotonic() <= 40.0


class TestRunLoopOrder:
    def test_run_hands_the_arbiter_the_cooldown_window(self):
        """The window the arbiter searches in comes from the live cooldown, not
        from a constant."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        seen: list[float | None] = []

        def fake_plan(state, game_data, actions, combat_monster):
            seen.append(player._arbiter._planning_deadline)
            raise KeyboardInterrupt

        initial_state = make_state(
            hp=100, max_hp=150,
            cooldown_expires=datetime.now(tz=timezone.utc) + timedelta(seconds=25))
        with patch.object(mgr := MagicMock(), "client", client), \
                patch("artifactsmmo_cli.ai.player.ClientManager", return_value=mgr), \
                _patch_game_data_load(), \
                patch.object(player, "_fetch_world_state", return_value=initial_state), \
                patch.object(player, "_wait_for_cooldown"), \
                patch.object(player, "_maybe_periodic_refresh"), \
                patch.object(player, "_reconcile_open_orders"), \
                patch.object(player, "_plan_or_reuse", side_effect=fake_plan), \
                patch.object(player, "_build_actions", return_value=[]), \
                patch("artifactsmmo_cli.ai.player.time.sleep"), \
                pytest.raises(KeyboardInterrupt):
            player.run()

        assert seen and seen[0] is not None
        assert 24.0 <= seen[0] - time.monotonic() <= 25.0

    def test_plans_inside_the_cooldown_then_waits_then_executes(self):
        """The whole point: search first, idle only the remainder, act after.
        Pre-fix `_wait_for_cooldown` ran before `_plan_or_reuse`, so this
        recorded ["wait", "plan", "execute"]."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        order: list[str] = []
        action = WaitAction()
        goal = MagicMock()
        goal.is_satisfied.return_value = False

        def fake_plan(state, game_data, actions, combat_monster):
            order.append("plan")
            return goal, [action], [], True

        def fake_wait():
            order.append("wait")

        def fake_execute(act, cl):
            order.append("execute")
            raise KeyboardInterrupt

        initial_state = make_state(hp=100, max_hp=150)
        with patch.object(mgr := MagicMock(), "client", client), \
                patch("artifactsmmo_cli.ai.player.ClientManager", return_value=mgr), \
                _patch_game_data_load(), \
                patch.object(player, "_fetch_world_state", return_value=initial_state), \
                patch.object(player, "_wait_for_cooldown", side_effect=fake_wait), \
                patch.object(player, "_maybe_periodic_refresh"), \
                patch.object(player, "_reconcile_open_orders"), \
                patch.object(player, "_plan_or_reuse", side_effect=fake_plan), \
                patch.object(player, "_execute", side_effect=fake_execute), \
                patch.object(player, "_build_actions", return_value=[]), \
                patch("artifactsmmo_cli.ai.player.time.sleep"), \
                pytest.raises(KeyboardInterrupt):
            player.run()

        assert order == ["plan", "wait", "execute"], order
