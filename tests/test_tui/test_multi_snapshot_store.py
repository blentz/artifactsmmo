"""MultiSnapshotStore: per-character buffers, no cross-character eviction."""

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.multi_snapshot_store import MultiSnapshotStore


def _snap(character: str, cycle_index: int = 1, **overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=cycle_index, timestamp="2026-07-30T12:00:00Z", character=character,
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


_FIGHT = FightRecord(
    started_at="2026-07-30T12:00:00", result="win", turns=3, opponent="chicken",
    logs=(), hp_before=120, hp_after=110, xp=10, gold=2, drops=(),
)


def test_snapshots_are_routed_by_character():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1))
    store.record(_snap("bob", 2))
    assert store.last("alice").cycle_index == 1
    assert store.last("bob").cycle_index == 2


def test_last_is_none_before_the_first_cycle():
    assert MultiSnapshotStore(["alice"]).last("alice") is None


def test_a_busy_character_cannot_evict_another_characters_history():
    """Buffers are per-character, so 600 alice cycles must not touch bob."""
    store = MultiSnapshotStore(["alice", "bob"], log_buffer=500)
    store.record(_snap("bob", 1))
    for i in range(600):
        store.record(_snap("alice", i))
    assert len(store.recent("bob")) == 1
    assert len(store.recent("alice")) == 500


def test_fights_go_to_the_fighting_characters_buffer():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1, fight=_FIGHT))
    assert len(store.fights("alice")) == 1
    assert len(store.fights("bob")) == 0


def test_latest_all_omits_characters_with_no_cycle_yet():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1))
    assert set(store.latest_all()) == {"alice"}


def test_an_unknown_character_is_an_error_not_a_silent_drop():
    store = MultiSnapshotStore(["alice"])
    with pytest.raises(KeyError):
        store.record(_snap("mallory"))
