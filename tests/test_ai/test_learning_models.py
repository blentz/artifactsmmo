"""Tests for SQLModel storage models."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.learning.models import Cycle, CycleBase, Session
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats


class TestCycle:
    def test_minimal_construction_with_required_fields(self):
        c = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="session-1",
            cycle_index=0,
            character="testchar",
            outcome="ok",
        )
        assert c.session_id == "session-1"
        assert c.outcome == "ok"
        assert c.bank_accessible is True
        assert c.actual_cooldown_seconds is None

    def test_validation_rejects_non_numeric_cooldown(self):
        """CycleBase (non-table) validates at construction."""
        with pytest.raises(ValidationError):
            CycleBase(
                ts="2026-05-17T00:00:00+00:00",
                session_id="session-1",
                cycle_index=0,
                character="testchar",
                outcome="ok",
                actual_cooldown_seconds="not a number",  # type: ignore[arg-type]
            )

    def test_model_validate_on_table_model_also_validates(self):
        """Cycle.model_validate(data) routes through Pydantic; table=True direct construction does not."""
        with pytest.raises(ValidationError):
            Cycle.model_validate({
                "ts": "2026-05-17T00:00:00+00:00",
                "session_id": "session-1",
                "cycle_index": 0,
                "character": "testchar",
                "outcome": "ok",
                "actual_cooldown_seconds": "not a number",
            })

    def test_all_optional_state_fields_accept_none(self):
        c = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="session-1",
            cycle_index=0,
            character="testchar",
            outcome="no_plan",
            x=None, y=None, hp=None, gold=None, level=None,
        )
        assert c.x is None
        assert c.gold is None


class TestSession:
    def test_minimal_construction(self):
        s = Session(
            session_id="session-1",
            started_at="2026-05-17T00:00:00+00:00",
            character="testchar",
        )
        assert s.session_id == "session-1"
        assert s.cycle_count == 0
        assert s.ended_at is None
        assert s.exit_reason is None

    def test_with_exit_reason(self):
        s = Session(
            session_id="session-1",
            started_at="2026-05-17T00:00:00+00:00",
            character="testchar",
            ended_at="2026-05-17T01:00:00+00:00",
            cycle_count=42,
            exit_reason="normal",
        )
        assert s.cycle_count == 42
        assert s.exit_reason == "normal"


class TestActionStats:
    def test_construction_and_immutability(self):
        s = ActionStats(
            action_repr="Fight(yellow_slime)",
            sample_count=10,
            median_cost_seconds=12.3,
            success_rate=0.9,
            median_delta_xp=15.0,
            median_delta_gold=0.0,
        )
        assert s.action_repr == "Fight(yellow_slime)"
        with pytest.raises(ValidationError):
            s.action_repr = "changed"  # type: ignore[misc]


class TestGoalStats:
    def test_construction(self):
        s = GoalStats(
            goal_repr="FarmMonster(yellow_slime)",
            sample_count=3,
            avg_cycles_to_satisfy=12.5,
            satisfaction_rate=0.66,
        )
        assert s.sample_count == 3
        assert s.avg_cycles_to_satisfy == 12.5

    def test_avg_cycles_can_be_none(self):
        s = GoalStats(
            goal_repr="X",
            sample_count=0,
            avg_cycles_to_satisfy=None,
            satisfaction_rate=0.0,
        )
        assert s.avg_cycles_to_satisfy is None


def test_cycle_delta_skill_xp_json_default_is_empty_object():
    """G-A: Cycle.delta_skill_xp_json defaults to '{}' so rows constructed
    without an explicit value (older code paths) still validate."""
    cycle = Cycle(
        ts="2026-05-18T00:00:00Z", session_id="s1", cycle_index=0, character="hero",
        selected_goal="<none>", action_repr="<no_plan>", action_class="NoPlan",
        outcome="no_plan",
    )
    assert cycle.delta_skill_xp_json == "{}"


def test_cycle_delta_skill_xp_json_accepts_sparse_map():
    """G-A: callers pass a JSON-encoded sparse map of {skill: xp_delta}."""
    cycle = Cycle(
        ts="2026-05-18T00:00:00Z", session_id="s1", cycle_index=0, character="hero",
        selected_goal="X", action_repr="Y", action_class="Z", outcome="ok",
        delta_skill_xp_json='{"weaponcrafting": 4}',
    )
    assert cycle.delta_skill_xp_json == '{"weaponcrafting": 4}'
