from datetime import datetime, timezone

from artifactsmmo_cli.ai.raid_info import RaidInfo


def _dt(h: int) -> datetime:
    return datetime(2026, 6, 30, h, 0, 0, tzinfo=timezone.utc)


def test_active_raid_reports_active_and_carries_instance_fields():
    r = RaidInfo(code="slime_raid", name="Slime Raid", monster="giant_slime",
                 status="active", next_start_at=_dt(12),
                 remaining_hp=400, total_hp=1000, window_ends_at=_dt(13))
    assert r.is_active() is True
    assert (r.remaining_hp, r.total_hp) == (400, 1000)
    assert r.window_ends_at == _dt(13)


def test_upcoming_raid_is_not_active_and_has_no_instance():
    r = RaidInfo(code="slime_raid", name="Slime Raid", monster="giant_slime",
                 status="upcoming", next_start_at=_dt(18),
                 remaining_hp=None, total_hp=None, window_ends_at=None)
    assert r.is_active() is False
    assert r.remaining_hp is None
