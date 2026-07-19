"""Tests for Tracer / NullTracer / FileTracer."""

import json
import os
import tempfile

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers import ObtainItem, StrategyDecision
from artifactsmmo_cli.ai.tracer import Tracer
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


class TestNullTracer:
    def test_write_is_no_op(self):
        t = NullTracer()
        t.write_cycle({"any": "data"})  # no exception
        t.close()


class TestFileTracer:
    def test_writes_jsonl_records(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.write_cycle({"cycle": 1, "action": "Fight"})
            t.write_cycle({"cycle": 2, "action": "Rest"})
            t.close()

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert json.loads(lines[0]) == {"cycle": 1, "action": "Fight"}
            assert json.loads(lines[1]) == {"cycle": 2, "action": "Rest"}
        finally:
            os.unlink(path)

    def test_close_is_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.close()
            t.close()  # no exception
        finally:
            os.unlink(path)

    def test_write_after_close_is_noop(self):
        """Writing once the file pointer is closed silently does nothing."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.write_cycle({"cycle": 1})
            t.close()
            t.write_cycle({"cycle": 2})  # fp is None -> no-op, no exception
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            assert json.loads(lines[0]) == {"cycle": 1}
        finally:
            os.unlink(path)


class TestPlayerTracer:
    def test_player_emits_cycle_record_to_tracer(self):
        """A direct call to _emit_trace should produce one tracer.write_cycle call."""
        captured: list[dict] = []

        class CapturingTracer(Tracer):
            def write_cycle(self, record: dict) -> None:
                captured.append(record)

            def close(self) -> None:
                pass

        player = GamePlayer(character="testchar", tracer=CapturingTracer())
        player.game_data = GameData()
        player.game_data._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(player.game_data)
        player.state = make_state()

        player._emit_trace(
            action_name="Fight(chicken)",
            goal_name="FarmMonster(chicken)",
            outcome="ok",
            planner_stats={"nodes": 5, "depth": 2, "timed_out": False, "plan_len": 1},
        )
        assert len(captured) == 1
        rec = captured[0]
        assert rec["action"] == "Fight(chicken)"
        assert rec["selected_goal"] == "FarmMonster(chicken)"
        assert rec["outcome"] == "ok"
        assert "state" in rec
        assert "ts" in rec
        assert "cycle" in rec
        assert "cooldown_remaining_at_cycle_start" in rec

    def test_player_defaults_to_null_tracer(self):
        """GamePlayer() without a tracer arg should use NullTracer (no-op)."""
        player = GamePlayer(character="testchar")
        assert isinstance(player.tracer, NullTracer)

    def test_trace_state_includes_xp_skill_xp_max_xp(self):
        """Item 13 / server-axiom replay needs xp + skill_xp + max_xp on
        every cycle. Without these, predict_win / xp-curve validation
        degrades to no-violation-observed (the report from the initial
        Item 13 harness)."""
        captured: list[dict] = []

        class CapturingTracer(Tracer):
            def write_cycle(self, record: dict) -> None:
                captured.append(record)

            def close(self) -> None:
                pass

        player = GamePlayer(character="testchar", tracer=CapturingTracer())
        player.game_data = GameData()
        player.game_data._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(player.game_data)
        player.state = make_state(xp=42, max_xp=100,
                                  skills={"mining": 3, "woodcutting": 2,
                                          "fishing": 1, "weaponcrafting": 1,
                                          "gearcrafting": 1, "jewelrycrafting": 1,
                                          "cooking": 1, "alchemy": 1},
                                  skill_xp={"mining": 50, "woodcutting": 10})

        player._emit_trace(
            action_name="Fight(chicken)",
            goal_name="FarmMonster(chicken)",
            outcome="ok",
            planner_stats={"nodes": 5, "depth": 2, "timed_out": False, "plan_len": 1},
        )
        assert len(captured) == 1
        state = captured[0]["state"]
        assert state["xp"] == 42
        assert state["max_xp"] == 100
        assert state["skill_xp"] == {"mining": 50, "woodcutting": 10}

    def test_trace_record_carries_gear_focus_ledger(self):
        """The `play-trace-*.jsonl` record — what's actually analyzed — must
        carry the gear-focus aging ledger too, string-key-encoded the same
        way as `CycleSnapshot.gear_focus` (`f"{slot}|{code}"`), so a level-up
        that PRESERVES a stuck root's fall-off (see
        tests/test_ai/test_player_focus_ledger.py) is visible on the surface
        the trace analysis actually reads. `CycleSnapshot` (cycle_observer/
        TUI) is a different, separate surface — this test targets the
        `_emit_trace`-written `record` dict directly."""
        captured: list[dict] = []

        class CapturingTracer(Tracer):
            def write_cycle(self, record: dict) -> None:
                captured.append(record)

            def close(self) -> None:
                pass

        player = GamePlayer(character="testchar", tracer=CapturingTracer())
        player.game_data = GameData()
        player.game_data._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(player.game_data)
        player.state = make_state()
        player._gear_focus = {
            ("helmet_slot", "wolf_ears"): 40,
            ("ring2_slot", "iron_ring"): 3,
        }
        player._interleave_seats = {"helmet_slot": 5}
        root = ObtainItem(code="wolf_ears", quantity=1, slot="helmet_slot")
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=root, chosen_step=root, desired_state={},
            aged_pick=True,
        )

        player._emit_trace(
            action_name="Fight(chicken)",
            goal_name="FarmMonster(chicken)",
            outcome="ok",
            planner_stats={"nodes": 5, "depth": 2, "timed_out": False, "plan_len": 1},
        )
        assert len(captured) == 1
        rec = captured[0]
        assert rec["gear_focus"] == {
            "helmet_slot|wolf_ears": 40, "ring2_slot|iron_ring": 3,
        }
        assert rec["interleave_seats"] == {"helmet_slot": 5}
        assert rec["aged_pick"] is True

    def test_trace_record_aged_pick_false_when_no_decision_yet(self):
        """No decide() has run this session (`_last_decision is None`) — the
        trace record's `aged_pick` defaults False rather than crashing, and
        an empty ledger serializes as empty dicts, not missing keys."""
        captured: list[dict] = []

        class CapturingTracer(Tracer):
            def write_cycle(self, record: dict) -> None:
                captured.append(record)

            def close(self) -> None:
                pass

        player = GamePlayer(character="testchar", tracer=CapturingTracer())
        player.game_data = GameData()
        player.game_data._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(player.game_data)
        player.state = make_state()
        assert player._last_decision is None

        player._emit_trace(
            action_name="Fight(chicken)",
            goal_name="FarmMonster(chicken)",
            outcome="ok",
            planner_stats={"nodes": 5, "depth": 2, "timed_out": False, "plan_len": 1},
        )
        rec = captured[0]
        assert rec["gear_focus"] == {}
        assert rec["interleave_seats"] == {}
        assert rec["aged_pick"] is False
