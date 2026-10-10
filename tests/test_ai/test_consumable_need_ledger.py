"""The fleet's consumable NEED board — `ConsumableNeed` and its two store
methods (`docs/PLAN_consumable_utility.md` increment 4; USER 2026-10-09 "Need
ledger + API order"). Each character publishes what its chosen loadout uses
over the refill horizon; a sibling reads every other character's need PER
CHARACTER, because its share of the bank depends on who is ahead of it."""

import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import create_engine

from artifactsmmo_cli.ai.learning.coordination_store import (
    DEMAND_TTL_SECONDS,
    CoordinationStore,
)

NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    return str(tmp_path / "coord.db")


def _store(db: str, character: str) -> CoordinationStore:
    return CoordinationStore(db_path=db, character=character)


def test_siblings_needs_are_read_per_character(db: str) -> None:
    _store(db, "Robby").publish_consumable_need({"small_health_potion": 40, "cooked_bass": 20}, NOW)
    _store(db, "HAL").publish_consumable_need({"small_health_potion": 60}, NOW)

    assert _store(db, "C3P0").sibling_consumable_needs(NOW) == {
        "Robby": {"small_health_potion": 40, "cooked_bass": 20},
        "HAL": {"small_health_potion": 60},
    }


def test_a_characters_own_need_is_excluded(db: str) -> None:
    c3p0 = _store(db, "C3P0")
    c3p0.publish_consumable_need({"small_health_potion": 40}, NOW)

    assert c3p0.sibling_consumable_needs(NOW) == {}
    assert _store(db, "HAL").sibling_consumable_needs(NOW) == {"C3P0": {"small_health_potion": 40}}


def test_an_expired_need_stops_claiming_the_bank(db: str) -> None:
    """The one liveness rule: a character that stopped playing stops counting
    ahead of its siblings on the same clock that frees its role."""
    _store(db, "Robby").publish_consumable_need({"small_health_potion": 40}, NOW)
    later = NOW + timedelta(seconds=DEMAND_TTL_SECONDS + 1)

    assert _store(db, "C3P0").sibling_consumable_needs(later) == {}


def test_republishing_replaces_wholesale(db: str) -> None:
    """A consumable the loadout dropped must stop claiming bank stock at once;
    a same-code republish must not collide on UNIQUE(character, item_code)."""
    robby = _store(db, "Robby")
    robby.publish_consumable_need({"small_health_potion": 40, "cooked_bass": 20}, NOW)
    robby.publish_consumable_need({"small_health_potion": 60}, NOW)

    assert _store(db, "C3P0").sibling_consumable_needs(NOW) == {"Robby": {"small_health_potion": 60}}


def test_a_zero_need_is_not_published(db: str) -> None:
    _store(db, "Robby").publish_consumable_need({"small_health_potion": 0, "cooked_bass": 20}, NOW)

    assert _store(db, "C3P0").sibling_consumable_needs(NOW) == {"Robby": {"cooked_bass": 20}}


def test_a_naive_datetime_is_refused(db: str) -> None:
    with pytest.raises(ValueError):
        _store(db, "Robby").publish_consumable_need({"cooked_bass": 1}, datetime(2026, 10, 9, 12))
    with pytest.raises(ValueError):
        _store(db, "Robby").sibling_consumable_needs(datetime(2026, 10, 9, 12))


def _break_engine(store: CoordinationStore) -> None:
    """A real engine whose SQLite URL is a directory: every query raises
    OperationalError (as `test_coordination_store._break_engine`)."""
    store._engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}")


def test_publish_swallows_a_db_error(db: str, capsys) -> None:  # type: ignore[no-untyped-def]
    robby = _store(db, "Robby")
    _break_engine(robby)
    robby.publish_consumable_need({"cooked_bass": 20}, NOW)
    assert "[coordination] publish_consumable_need failed" in capsys.readouterr().out


def test_read_swallows_a_db_error_and_returns_empty(db: str, capsys) -> None:  # type: ignore[no-untyped-def]
    robby = _store(db, "Robby")
    _break_engine(robby)
    assert robby.sibling_consumable_needs(NOW) == {}
    assert "[coordination] sibling_consumable_needs failed" in capsys.readouterr().out
