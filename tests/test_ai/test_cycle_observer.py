"""Tests for GamePlayer's cycle_observer hook (T-1)."""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


class TestCycleSnapshot:
    def test_construct_minimal(self):
        snap = CycleSnapshot(
            cycle_index=0, timestamp="2026-05-18T00:00:00Z", character="hero",
            x=0, y=0, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
            selected_goal="X", action="Y", outcome="ok",
        )
        assert snap.character == "hero"
        assert snap.goal_rank == []
        assert snap.inventory == {}
        # Planner-trace fields default when omitted.
        assert snap.planner_nodes == 0
        assert snap.planner_depth == 0
        assert snap.planner_timed_out is False
        assert snap.plan_len == 0
        assert snap.goals_tried == []
        assert snap.suppressed_goals == []
        assert snap.path_blocked is False


class TestObserverHook:
    def test_set_cycle_observer_attaches_later(self):
        player = GamePlayer(character="hero")
        assert player._cycle_observer is None
        cb = MagicMock()
        player.set_cycle_observer(cb)
        assert player._cycle_observer is cb

    def test_observer_passed_in_constructor(self):
        cb = MagicMock()
        player = GamePlayer(character="hero", cycle_observer=cb)
        assert player._cycle_observer is cb

    def test_notify_observer_builds_snapshot(self):
        """_notify_observer composes a CycleSnapshot and calls the observer."""
        calls: list[CycleSnapshot] = []
        player = GamePlayer(character="hero", cycle_observer=calls.append)
        player.state = make_state(level=3, xp=120, max_xp=600, hp=80, max_hp=130, gold=42,
                                   x=2, y=-1, inventory={"copper_ore": 5})
        player._cycle_counter = 7
        player._notify_observer(
            "FarmMonster(slime)", "Fight(slime)", "ok",
            goal_rank_trace=[{"goal": "FarmMonster(slime)", "priority": 36.0}],
        )
        assert len(calls) == 1
        snap = calls[0]
        assert snap.cycle_index == 7
        assert snap.character == "hero"
        assert snap.level == 3
        assert snap.xp == 120
        assert snap.hp == 80
        assert snap.gold == 42
        assert snap.x == 2 and snap.y == -1
        assert snap.inventory == {"copper_ore": 5}
        assert snap.selected_goal == "FarmMonster(slime)"
        assert snap.action == "Fight(slime)"
        assert snap.outcome == "ok"
        assert len(snap.goal_rank) == 1
        assert snap.goal_rank[0].priority == 36.0

    def test_notify_observer_carries_planner_trace(self):
        """planner_stats threads the trace internals onto the snapshot."""
        calls: list[CycleSnapshot] = []
        player = GamePlayer(character="hero", cycle_observer=calls.append)
        player.state = make_state(level=3)
        player._suppressed_goals = {"NpcSell": 4}
        player._notify_observer(
            "CraftEquipment", "MoveTo(1,2)", "ok",
            goal_rank_trace=[{"goal": "CraftEquipment", "priority": 88.0}],
            planner_stats={
                "nodes": 842, "depth": 7, "timed_out": False, "plan_len": 3,
                "goals_tried": [
                    {"goal": "CraftEquipment", "nodes": 842, "depth": 7,
                     "timed_out": False, "plan_len": 3},
                    {"goal": "FightMonster", "nodes": 120, "depth": 4,
                     "timed_out": True, "plan_len": 0},
                ],
                "goal_rank": [{"goal": "CraftEquipment", "priority": 88.0}],
                "path_blocked": True,
            },
        )
        snap = calls[0]
        assert snap.planner_nodes == 842
        assert snap.planner_depth == 7
        assert snap.planner_timed_out is False
        assert snap.plan_len == 3
        assert snap.path_blocked is True
        assert snap.suppressed_goals == ["NpcSell"]
        assert [g.goal for g in snap.goals_tried] == ["CraftEquipment", "FightMonster"]
        assert snap.goals_tried[1].timed_out is True
        assert snap.goals_tried[1].nodes == 120

    def test_notify_observer_noop_when_unset(self):
        """No observer = silent skip; no exception."""
        player = GamePlayer(character="hero")
        player.state = make_state()
        player._notify_observer("X", "Y", "ok", goal_rank_trace=[])
        # No assertion needed — just verifying no crash.

    def test_notify_observer_noop_when_state_none(self):
        cb = MagicMock()
        player = GamePlayer(character="hero", cycle_observer=cb)
        player.state = None
        player._notify_observer("X", "Y", "ok", goal_rank_trace=[])
        cb.assert_not_called()
