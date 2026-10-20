"""The learned fight-seconds model (spec 2026-10-18 §2.9, rulings CA, CC): fitted
to the fleet's recorded fights and a `/my/logs` bootstrap, refitted only when
either changes, and fitted offline from the committed live capture."""

import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.learning import fight_seconds_model as mod
from artifactsmmo_cli.ai.learning.fight_seconds_model import (
    fetch_log_entries,
    fit_model,
    learned_action_seconds,
    learned_model,
    log_fights,
    offline_timing,
    timing_of,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore


def _store(tmp_path: Path) -> LearningStore:
    store = LearningStore(db_path=str(tmp_path / "fit.db"), character="hero")
    store.start_session()
    return store


def _fight(store: LearningStore, index: int, turns: int, haste: int, seconds: float) -> None:
    store.record_cycle(Cycle(ts=f"2026-10-19T00:00:{index:02d}+00:00", cycle_index=index,
                             outcome="ok", actual_cooldown_seconds=seconds,
                             fight_turns=turns, fight_haste=haste))


def test_the_model_prices_a_fight_from_its_turns_and_haste() -> None:
    model = FightSecondsModel(Fraction(2), Fraction(1, 100), Fraction(5), True, 3)
    assert model.seconds(Fraction(5), 8) == Fraction(46, 5)
    assert model.seconds(Fraction(1), 8) == 5


def test_one_haste_leaves_its_effect_unidentified() -> None:
    assert not fit_model([(5, 8, 9.0), (7, 8, 13.0), (4, 0, 0.0)]).haste_identified
    model = fit_model([(5, 0, 10.0), (5, 10, 9.0)])
    assert (model.haste_identified, model.samples) == (True, 2)


def test_log_fights_keep_the_fights_at_the_sheet_haste() -> None:
    assert log_fights(8, [("fight", 9, 5), ("gathering", 25, None)]) == [(5, 8, 9.0)]


def test_a_log_page_is_read_as_typed_entries() -> None:
    entries = [SimpleNamespace(type_=LogType.FIGHT, cooldown=9, content={"fight": {"turns": 5}}),
               SimpleNamespace(type_=LogType.GATHERING, cooldown=25, content={})]
    calls: list[tuple[str, int, int]] = []

    class Api:
        def get_character_logs(self, name: str, page: int, size: int) -> SimpleNamespace:
            calls.append((name, page, size))
            return SimpleNamespace(data=entries)

    assert fetch_log_entries(Api(), "hero") == [("fight", 9, 5), ("gathering", 25, None)]  # type: ignore[arg-type]
    assert calls == [("hero", 1, 100)]


def test_the_learned_model_refits_only_when_its_observations_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 10.0)
        first = learned_model(store, [(10, 0, 20.0)])
        assert first.s_turn == 2
        assert learned_model(store, [(10, 0, 20.0)]) is first
        _fight(store, 1, 5, 0, 15.0)
        assert learned_model(store, [(10, 0, 20.0)]).s_turn == Fraction(10 * 5 + 15 * 5 + 200, 150)
        assert learned_model(store, []).s_turn == Fraction(5, 2)
    finally:
        store.close()


def test_the_cache_holds_its_store(tmp_path: Path) -> None:
    """A second store with the same counts is a different key: the cache pins
    the store object, never its id."""
    first, second = _store(tmp_path / "a"), _store(tmp_path / "b")
    try:
        _fight(first, 0, 5, 0, 10.0)
        _fight(second, 0, 5, 0, 15.0)
        assert learned_model(first, []).s_turn == 2
        assert learned_model(second, []).s_turn == 3
        assert mod._LEARNED[0][0] is second
    finally:
        first.close()
        second.close()


def test_no_fight_anywhere_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        with pytest.raises(ValueError, match="no fight with a positive cooldown"):
            learned_model(store, [])
    finally:
        store.close()


def test_the_action_seconds_are_learned_then_bootstrapped_or_raise(tmp_path: Path) -> None:
    """The store's mean once it has one; the bootstrap's (positive cooldowns
    only) until then; neither raises."""
    store = _store(tmp_path)
    try:
        with pytest.raises(ValueError, match="the bootstrap has: no action with a cooldown"):
            learned_action_seconds(store, [0])
        assert learned_action_seconds(store, [9, 0, 25]) == 17
        _fight(store, 0, 5, 0, 10.0)
        store.record_cycle(Cycle(ts="2026-10-19T00:01:00+00:00", cycle_index=1, outcome="ok",
                                 actual_cooldown_seconds=30.0))
        assert learned_action_seconds(store, [9, 25]) == 20
    finally:
        store.close()


def test_timing_without_a_store_fits_the_page_alone(tmp_path: Path) -> None:
    entries = [("fight", 10, 5), ("fight", 20, 10), ("gathering", 30, None)]
    model, seconds = timing_of(None, 0, entries)
    assert (model.s_turn, model.samples, seconds) == (Fraction(2), 2, Fraction(20))
    with pytest.raises(ValueError, match="the /my/logs bootstrap: no action with a cooldown"):
        timing_of(None, 0, [("gathering", 0, None), ("move", 0, None)])


def test_timing_with_a_store_pools_the_fleet_and_the_page(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 15.0)
        model, seconds = timing_of(store, 0, [("fight", 10, 5)])
        assert (model.s_turn, model.samples, seconds) == (Fraction(5, 2), 2, Fraction(15))
    finally:
        store.close()


def test_the_committed_capture_fits_two_seconds_a_turn_less_a_percent_a_haste() -> None:
    """The live capture (2026-10-19, five characters at haste 8 and 12, 1180
    fights): about 2 s a turn, about 1% less per point of haste, a 5 s floor."""
    model, action_seconds = offline_timing()
    assert model.samples == 1180 and model.haste_identified
    assert round(model.s_turn, 2) == Fraction(199, 100)
    assert round(model.h, 4) == Fraction(97, 10000)
    assert model.floor == 5
    assert round(action_seconds, 1) == Fraction(358, 10)


def test_a_capture_with_no_cooldown_raises(tmp_path: Path) -> None:
    path = tmp_path / "logs.json"
    path.write_text(json.dumps({"characters": {"hero": {"haste": 0, "entries": [
        ["fight", 0, 5]]}}}))
    with pytest.raises(ValueError, match="no action with a cooldown"):
        offline_timing(path)
