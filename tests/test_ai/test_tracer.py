"""Tests for Tracer / NullTracer / FileTracer."""

import json
import os
import tempfile

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tracer import Tracer
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
