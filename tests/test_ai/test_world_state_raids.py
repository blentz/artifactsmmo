"""Tests for WorldState.raids field and active_raids property."""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.raid_info import RaidInfo
from tests.test_ai.fixtures import make_state


def _raid(status: str) -> RaidInfo:
    t = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)
    return RaidInfo(code="r", name="R", monster="giant_slime", status=status,
                    next_start_at=t, remaining_hp=1 if status == "active" else None,
                    total_hp=2 if status == "active" else None,
                    window_ends_at=t if status == "active" else None)


def test_worldstate_defaults_to_no_raids():
    assert make_state().raids == []
    assert make_state().active_raids == []


def test_active_raids_filters_to_active_only():
    st = make_state(raids=[_raid("active"), _raid("upcoming")])
    assert [r.status for r in st.active_raids] == ["active"]
