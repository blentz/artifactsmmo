"""Tests for SQLModel storage models."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.learning.models import Cycle


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
        with pytest.raises(ValidationError):
            Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id="session-1",
                cycle_index=0,
                character="testchar",
                outcome="ok",
                actual_cooldown_seconds="not a number",  # type: ignore[arg-type]
            )

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
