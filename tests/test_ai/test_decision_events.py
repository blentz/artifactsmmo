"""Phase 0b: every compensating mechanism notes its firing into the per-cycle
decision-events log, and the player persists the batch with the cycle row."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
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
    log.note(Mechanism.DOOMED_SKIP, "g")
    log.note(Mechanism.SEARCH, "h", "d")
    assert log.drain() == [(Mechanism.DOOMED_SKIP, "g", ""), (Mechanism.SEARCH, "h", "d")]
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

    def _goal(self, plannable: bool) -> MagicMock:
        goal = MagicMock(spec=Goal)
        goal.is_plannable.return_value = plannable
        goal.priority.return_value = 0.0
        goal.__repr__ = lambda self: "G"  # type: ignore[method-assign,assignment]
        return goal

    def test_a_goal_proven_unplannable_is_noted_without_a_search(self) -> None:
        arbiter = self._arbiter()
        arbiter._plans(self._goal(False), make_state(), GameData(), [], MagicMock())
        assert arbiter.events.drain() == [(Mechanism.NOT_PLANNABLE, "G", "")]

    def test_every_a_star_search_is_noted_with_its_created_nodes(self) -> None:
        arbiter = self._arbiter()
        arbiter._plans(self._goal(True), make_state(), GameData(), [], MagicMock())
        [(mechanism, subject, detail)] = arbiter.events.drain()
        assert (mechanism, subject) == (Mechanism.SEARCH, "G")
        assert detail.startswith("nodes_created=9 explored=3") and "timed_out=True" in detail

    def test_the_fast_path_is_noted(self) -> None:
        arbiter = self._arbiter()
        with patch("artifactsmmo_cli.ai.strategy_driver.generate_next_craft_action",
                   return_value=[MagicMock(), MagicMock()]):
            arbiter._plans(self._goal(True), make_state(), GameData(), [], MagicMock())
        assert arbiter.events.drain() == [(Mechanism.FAST_PATH, "G", "plan_len=2")]

    def test_a_mark_is_noted_and_a_clear_only_when_something_was_marked(self) -> None:
        arbiter = self._arbiter()
        goal, state = self._goal(True), make_state()
        arbiter._record_attempt(goal, [MagicMock()], False, state, set())  # nothing to clear
        arbiter._record_attempt(goal, [], True, state, set())
        arbiter._record_attempt(goal, [MagicMock()], False, state, set())
        assert arbiter.events.drain() == [
            (Mechanism.DOOMED_MARK, "G", "timed_out"), (Mechanism.DOOMED_CLEAR, "G", "")]


class TestPlayer:
    def test_decide_notes_promotion_and_aged_pick(self) -> None:
        player = GamePlayer(character="hero")
        player._strategy = MagicMock()
        decision = MagicMock(chosen_root="Root(b)", chosen_step=None, promoted_from="Root(a)",
                             aged_pick=True)
        player._strategy.decide.return_value = decision
        with (patch.object(player._arbiter, "select", return_value=(None, [], [])),
              patch.object(player, "_record_decision_targets", return_value=None),
              patch.object(player, "_selection_context", return_value=MagicMock())):
            player._decide_band(make_state(), GameData(), [], None)
        assert player._events.drain() == [
            (Mechanism.SERVABLE_PROMOTION, "'Root(b)'", "from='Root(a)'"),
            (Mechanism.AGED_PICK, "'Root(b)'", "")]

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

    def test_the_nested_grind_search_and_its_doom_are_noted(self) -> None:
        player = GamePlayer(character="hero")
        player.game_data = GameData()
        player.state = make_state()
        player._build_actions = lambda: []  # type: ignore[method-assign]
        player.planner = MagicMock()
        player.planner.plan.return_value = []
        player.planner.last_stats = _stats(nodes_created=233739, nodes_explored=13748, timed_out=True)
        player._plan_cache = PlanCache(selected_goal=MagicMock(), plan=[], crafting_target=None,
                                       latch_active=False, goal_repr="ReachSkill(x->21)")
        grind_goal = MagicMock()
        grind_goal.__repr__ = lambda self: "GatherMaterials(skull_staff)"  # type: ignore[method-assign,assignment]
        with (patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=grind_goal),
              pytest.raises(RuntimeError, match="EXHAUSTED")):
            player._execute_level_skill(LevelSkill(skill="weaponcrafting", target_level=21), MagicMock())
        [(search, subject, detail), doom] = player._events.drain()
        assert (search, subject) == (Mechanism.GRIND_SEARCH, "GatherMaterials(skull_staff)")
        assert detail.startswith("nodes_created=233739")
        assert doom == (Mechanism.GRIND_DOOM, "ReachSkill(x->21)", "")
