"""Phase 0b: every compensating mechanism notes its firing into the per-cycle
decision-events log, and the player persists the batch with the cycle row."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.constants import BANK_REFRESH_INTERVAL
from artifactsmmo_cli.ai.decision_event_log import DecisionEventLog, search_detail
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.planner import PlanStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import StuckSignal
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_learning_store import _break_engine


def _stats(**kw: object) -> PlanStats:
    stats = PlanStats()
    for k, v in kw.items():
        setattr(stats, k, v)
    return stats


def test_the_log_drains_one_cycle_at_a_time() -> None:
    log = DecisionEventLog()
    log.note(Mechanism.WAIT_FALLBACK, "g")
    log.note(Mechanism.SEARCH, "h", "d")
    assert log.drain() == [(Mechanism.WAIT_FALLBACK, "g", ""), (Mechanism.SEARCH, "h", "d")]
    assert log.drain() == []


def test_search_detail_reports_created_not_just_explored_nodes() -> None:
    stats = _stats(nodes_created=233739, nodes_explored=13748, max_depth_reached=8,
                   timed_out=True, node_capped=False)
    assert search_detail(stats, 0) == (
        "nodes_created=233739 explored=13748 depth=8 timed_out=True node_capped=False plan_len=0")


class TestStore:
    def test_a_batch_round_trips_with_its_cycle_index(self, tmp_path: Path) -> None:
        store = LearningStore(str(tmp_path / "l.db"), character="Robby")
        store.start_session()
        store.record_decision_events(7, [("doomed_mark", "G", "timed_out"), ("search", "G", "")])
        rows = store.decision_events_between("2000", "3000")
        store.close()
        assert [(r.cycle_index, r.mechanism, r.subject, r.detail) for r in rows] == [
            (7, "doomed_mark", "G", "timed_out"), (7, "search", "G", "")]

    def test_nothing_is_written_without_events_or_a_session(self, tmp_path: Path) -> None:
        store = LearningStore(str(tmp_path / "l.db"), character="Robby")
        store.record_decision_events(1, [("search", "G", "")])  # no session
        store.start_session()
        store.record_decision_events(1, [])
        assert store.decision_events_between("2000", "3000") == []
        store.close()

    def test_a_db_fault_degrades_to_empty(self, tmp_path: Path) -> None:
        store = LearningStore(str(tmp_path / "l.db"), character="Robby")
        store.start_session()
        _break_engine(store)
        store.record_decision_events(1, [("search", "G", "")])
        assert store.decision_events_between("2000", "3000") == []


class TestArbiter:
    def _arbiter(self) -> StrategyArbiter:
        planner = MagicMock()
        planner.plan.return_value = []
        planner.last_stats = _stats(nodes_created=9, nodes_explored=3, timed_out=True)
        return StrategyArbiter(planner, history=None)

    def _goal(self) -> MagicMock:
        goal = MagicMock(spec=Goal)
        goal.priority.return_value = 0.0
        goal.__repr__ = lambda self: "G"  # type: ignore[method-assign,assignment]
        return goal

    def test_every_a_star_search_is_noted_with_its_created_nodes(self) -> None:
        arbiter = self._arbiter()
        arbiter._plans(self._goal(), make_state(), GameData(), [], MagicMock())
        [(mechanism, subject, detail)] = arbiter.events.drain()
        assert (mechanism, subject) == (Mechanism.SEARCH, "G")
        assert detail.startswith("nodes_created=9 explored=3") and "timed_out=True" in detail

    def test_the_fast_path_is_noted(self) -> None:
        arbiter = self._arbiter()
        with patch("artifactsmmo_cli.ai.strategy_driver.decompose",
                   return_value=[MagicMock(), MagicMock()]):
            arbiter._plans(self._goal(), make_state(), GameData(), [], MagicMock())
        assert arbiter.events.drain() == [(Mechanism.FAST_PATH, "G", "plan_len=2")]

    def test_a_decline_is_noted_and_is_the_goals_answer(self) -> None:
        """Phase 2c-2.0 named the decline; Phase 2e makes it final: the reason
        is noted and no search follows."""
        arbiter = self._arbiter()

        def declines(goal, state, game_data, actions, ctx, declined):
            declined.append("no_source:feather")

        with patch("artifactsmmo_cli.ai.strategy_driver.decompose", side_effect=declines):
            plan = arbiter._plans(self._goal(), make_state(), GameData(), [], MagicMock())
        assert plan == []
        assert arbiter.events.drain() == [(Mechanism.DECOMPOSE_DECLINE, "G", "no_source:feather")]
        # Phase 3-3: the attempt record names why, so a no-plan is never bare.
        assert arbiter.goals_tried[-1]["declined"] == "no_source:feather"

    def test_a_planned_goal_names_no_decline(self) -> None:
        arbiter = self._arbiter()
        with patch("artifactsmmo_cli.ai.strategy_driver.decompose",
                   return_value=[MagicMock()]):
            arbiter._plans(self._goal(), make_state(), GameData(), [], MagicMock())
        assert arbiter.goals_tried[-1]["declined"] is None

    def test_a_handoff_decline_is_noted_before_the_search(self) -> None:
        """`upgrade:ge_venue` hands the goal to the search on purpose."""
        arbiter = self._arbiter()

        def declines(goal, state, game_data, actions, ctx, declined):
            declined.append("upgrade:ge_venue:iron_boots")

        with patch("artifactsmmo_cli.ai.strategy_driver.decompose", side_effect=declines):
            arbiter._plans(self._goal(), make_state(), GameData(), [], MagicMock())
        [decline, (search, _subject, _detail)] = arbiter.events.drain()
        assert decline == (Mechanism.DECOMPOSE_DECLINE, "G", "upgrade:ge_venue:iron_boots")
        assert search is Mechanism.SEARCH
        assert arbiter.goals_tried[-1]["declined"] == "upgrade:ge_venue:iron_boots"


class TestPlayer:
    def test_decide_notes_each_root_decline(self) -> None:
        player = GamePlayer(character="hero")
        player._strategy = MagicMock()
        decision = MagicMock(chosen_root="Root(b)", chosen_step=None,
                             declined=(("Root(a)", "no_route:x"),))
        player._strategy.decide.return_value = decision
        with (patch.object(player._arbiter, "select", return_value=(None, [], [])),
              patch.object(player, "_record_decision_targets", return_value=None),
              patch.object(player, "_selection_context", return_value=MagicMock())):
            player._decide_band(make_state(), GameData(), [], None)
        assert player._events.drain() == [
            (Mechanism.ROOT_DECLINE, "Root(a)", "no_route:x")]

    def test_stuck_recovery_notes_every_suppression_it_sets(self) -> None:
        player = GamePlayer(character="hero")
        player._suppressed_goals = {"Old": 3}
        player._failed_action_backoff = {}

        def recover(signal: StuckSignal, client: object) -> None:
            player._suppressed_goals["Old"] = 3  # unchanged: not a new suppression
            player._suppressed_goals["Grind"] = 10
            player._failed_action_backoff["Gather(ash_tree)"] = 5

        with patch.object(player, "_apply_stuck_recovery", side_effect=recover):
            player._handle_stuck(StuckSignal.NO_PROGRESS, MagicMock())
        assert player._events.drain() == [
            (Mechanism.SUPPRESS, "Grind", "goal cycles=10 signal=NO_PROGRESS"),
            (Mechanism.SUPPRESS, "Gather(ash_tree)", "action cycles=5 signal=NO_PROGRESS")]

    def test_the_cycle_row_carries_its_events_into_the_store(self, tmp_path: Path) -> None:
        store = LearningStore(str(tmp_path / "l.db"), character="hero")
        store.start_session()
        player = GamePlayer(character="hero", history=store)
        player.game_data = GameData()
        player._events.note(Mechanism.REPLAN, "G")
        state = make_state()
        player._record_learning_cycle(
            prev_state=state, new_state=state, action_repr="<no_plan>", action_class="NoPlan",
            outcome="no_plan", selected_goal="<none>", predicted_cost=0.0,
            actual_cooldown_seconds=0.0, planner_nodes=0, planner_depth=0,
            planner_timed_out=False, plan_len=0)
        rows = store.decision_events_between("2000", "3000")
        cycle_index = store.recent_cycles(1)[0].cycle_index
        store.close()
        assert [(r.mechanism, r.subject, r.cycle_index) for r in rows] == [("replan", "G", cycle_index)]
        assert player._events.drain() == []

    def test_a_cycle_that_persists_nothing_still_empties_the_buffer(self) -> None:
        player = GamePlayer(character="hero", history=None)
        player._events.note(Mechanism.REPLAN, "G")
        state = make_state()
        player._record_learning_cycle(
            prev_state=state, new_state=state, action_repr="x", action_class="X",
            outcome="ok", selected_goal="G", predicted_cost=0.0,
            actual_cooldown_seconds=0.0, planner_nodes=0, planner_depth=0,
            planner_timed_out=False, plan_len=0)
        assert player._events.drain() == []

    def test_replan_and_cache_hit_are_noted(self) -> None:
        player = GamePlayer(character="hero")
        goal = MagicMock()
        goal.__repr__ = lambda self: "Goal(x)"  # type: ignore[method-assign,assignment]
        state = make_state()
        with patch.object(player, "_decide_band", return_value=(goal, [], [])):
            player._plan_or_reuse(state, GameData(), [], None)  # no cache: replan
        player._plan_cache = PlanCache(selected_goal=goal, plan=[MagicMock()], crafting_target=None,
                                       latch_active=player._regear_edge.active, goal_repr="Goal(x)")
        goal.is_satisfied.return_value = False
        player._last_outcome = "ok"
        with patch.object(player._plan_cache.plan[0], "is_applicable", return_value=True):
            player._plan_or_reuse(state, GameData(), [], None)
        assert player._events.drain() == [(Mechanism.REPLAN, "<none>", ""),
                                          (Mechanism.PLAN_CACHE_HIT, "Goal(x)", "")]

    def test_a_refresh_that_reselects_the_goal_keeps_the_commitment(self) -> None:
        """Phase 2d-L1c: at the staleness bound the goal is re-decided, and when
        the arbiter picks the same goal the committed plan stays (its cursor
        too); a different goal replaces it."""
        player = GamePlayer(character="hero")
        goal = MagicMock()
        goal.__repr__ = lambda self: "Goal(x)"  # type: ignore[method-assign,assignment]
        goal.is_satisfied.return_value = False
        state = make_state()
        first, second = MagicMock(), MagicMock()
        player._plan_cache = PlanCache(selected_goal=goal, plan=[first, second], crafting_target=None,
                                       latch_active=player._regear_edge.active, goal_repr="Goal(x)",
                                       cursor=1, cycles_since_replan=BANK_REFRESH_INTERVAL)
        player._last_outcome = "ok"
        fresh = MagicMock()
        with (patch.object(second, "is_applicable", return_value=True),
              patch.object(player, "_decide_band", return_value=(goal, [fresh], []))):
            chosen, plan, _tried, replanned = player._plan_or_reuse(state, GameData(), [], None)
        assert (chosen, plan, replanned) == (goal, [second], True)
        assert player._plan_cache.cycles_since_replan == 0
        assert player._events.drain() == [(Mechanism.REPLAN, "Goal(x)", ""),
                                          (Mechanism.COMMITMENT_KEPT, "Goal(x)", "")]
        other = MagicMock()
        other.__repr__ = lambda self: "Goal(y)"  # type: ignore[method-assign,assignment]
        player._plan_cache.cycles_since_replan = BANK_REFRESH_INTERVAL
        with (patch.object(second, "is_applicable", return_value=True),
              patch.object(player, "_decide_band", return_value=(other, [fresh], []))):
            chosen, plan, _tried, _replanned = player._plan_or_reuse(state, GameData(), [], None)
        assert (chosen, plan) == (other, [fresh])



