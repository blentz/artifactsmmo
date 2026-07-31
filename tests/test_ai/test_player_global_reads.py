"""GamePlayer routes account-global reads through GlobalReadsCache."""

from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.player import GamePlayer


def _player() -> GamePlayer:
    return GamePlayer(character="hero")


def test_player_has_a_global_reads_cache():
    assert _player()._global_reads is not None


def test_events_and_raids_use_distinct_cache_keys():
    player = _player()
    calls = {"events": 0, "raids": 0}

    def fetch_events():
        calls["events"] += 1
        return {"dragon": datetime.now(timezone.utc) + timedelta(hours=1)}

    def fetch_raids():
        calls["raids"] += 1
        return []

    player._global_reads.get_or_fetch("active_events", fetch_events)
    player._global_reads.get_or_fetch("raids", fetch_raids)
    player._global_reads.get_or_fetch("active_events", fetch_events)
    player._global_reads.get_or_fetch("raids", fetch_raids)
    assert calls == {"events": 1, "raids": 1}


def test_expired_events_are_dropped_from_a_cached_view():
    player = _player()
    now = datetime.now(timezone.utc)
    cached = {
        "live_event": now + timedelta(minutes=30),
        "ended_event": now - timedelta(seconds=1),
    }
    assert player._unexpired(cached, now) == {"live_event": cached["live_event"]}
