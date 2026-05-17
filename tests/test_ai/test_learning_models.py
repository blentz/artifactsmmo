"""Tests for SQLModel storage models."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.learning.models import Cycle, CycleBase


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
