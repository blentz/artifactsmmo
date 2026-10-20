"""The learned fight-seconds model (spec 2026-10-18 §2.9, rulings CA, CC): fitted
to the fleet's recorded fights and a `/my/logs` bootstrap, refitted only when
either changes, and fitted offline from the committed live capture."""

from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.learning import fight_seconds_model as mod
from artifactsmmo_cli.ai.learning.fight_seconds_model import (
    BOOTSTRAP_FIGHTS,
    BOOTSTRAP_PAGE,
    FleetBootstrap,
    fetch_fleet_bootstrap,
    fit_model,
    learned_action_seconds,
    learned_model,
    log_fights,
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


def _entry(character: str, kind: LogType, cooldown: int, turns: int | None = None) -> SimpleNamespace:
    content = {"fight": {"turns": turns}} if kind == LogType.FIGHT else {}
    return SimpleNamespace(character=character, type_=kind, cooldown=cooldown, content=content)


class _Api:
    """`/my/logs` (the account's, `pages` pages) and `/my/logs/{name}`."""

    def __init__(self, pages: list[list[SimpleNamespace]],
                 own: list[SimpleNamespace] | None = None) -> None:
        self.pages = pages
        self.own = own or []
        self.calls: list[tuple[int, int]] = []

    def get_all_characters_logs(self, page: int, size: int) -> SimpleNamespace:
        self.calls.append((page, size))
        return SimpleNamespace(data=self.pages[page - 1], pages=len(self.pages))

    def get_character_logs(self, name: str, page: int, size: int) -> SimpleNamespace:
        return SimpleNamespace(data=[e for e in self.own if e.character == name], pages=1)


def _fights(character: str, n: int) -> list[SimpleNamespace]:
    return [_entry(character, LogType.FIGHT, 10, 5) for _ in range(n)]


def test_a_character_without_fights_bootstraps_from_the_account_log() -> None:
    """Ruling ZD (live 2026-10-20: R2D2's and C3P0's newest 100 entries held
    no fight, and their `plan` raised "no fight with a positive cooldown").
    The bootstrap is the account's log, each fight at its character's sheet
    haste; a gathering character fits on its siblings' fights."""
    own = [_entry("R2D2", LogType.GATHERING, 25)]
    account = [_entry("R2D2", LogType.GATHERING, 25), _entry("Robby", LogType.FIGHT, 9, 5),
               _entry("Lor", LogType.FIGHT, 0, 4), _entry("Lor", LogType.FIGHT, 20, 10)]
    api = _Api([account], own)
    calls: list[str] = []
    bootstrap = fetch_fleet_bootstrap(api, {"R2D2": 0, "Robby": 8, "Lor": 2},  # type: ignore[arg-type]
                                      lambda: calls.append("acquire"))
    assert bootstrap == FleetBootstrap(fights=((5, 8, 9.0), (10, 2, 20.0)),
                                       cooldowns=(25, 9, 0, 20))
    assert calls == ["acquire"] and api.calls == [(1, BOOTSTRAP_PAGE)]
    model, seconds = timing_of(None, bootstrap)
    assert (model.samples, model.haste_identified, seconds) == (2, True, 18)


def test_paging_stops_once_the_fit_has_enough_fights_at_two_hastes() -> None:
    first = _fights("Robby", BOOTSTRAP_FIGHTS)
    second = _fights("Lor", 1)
    api = _Api([first, second, _fights("Lor", 3)])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 2}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE), (2, BOOTSTRAP_PAGE)]
    assert len(bootstrap.fights) == BOOTSTRAP_FIGHTS + 1


def test_one_haste_in_the_fleet_needs_no_spread() -> None:
    api = _Api([_fights("Robby", BOOTSTRAP_FIGHTS), _fights("Lor", 1)])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 8}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE)]
    assert not fit_model(bootstrap.fights).haste_identified


def test_a_log_that_runs_out_first_is_all_the_bootstrap() -> None:
    api = _Api([_fights("Robby", 2), [_entry("Lor", LogType.GATHERING, 25)]])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 2}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE), (2, BOOTSTRAP_PAGE)]
    assert len(bootstrap.fights) == 2
    empty = fetch_fleet_bootstrap(_Api([[_entry("Lor", LogType.GATHERING, 25)]]),  # type: ignore[arg-type]
                                  {"Lor": 2}, lambda: None)
    with pytest.raises(ValueError, match="no fight with a positive cooldown"):
        timing_of(None, empty)


def test_a_bootstrap_round_trips_through_json() -> None:
    bootstrap = FleetBootstrap(fights=((5, 8, 9.0),), cooldowns=(9, 25))
    assert FleetBootstrap.from_json(bootstrap.to_json()) == bootstrap


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


def test_timing_without_a_store_fits_the_bootstrap_alone(tmp_path: Path) -> None:
    bootstrap = FleetBootstrap(fights=((5, 0, 10.0), (10, 0, 20.0)), cooldowns=(10, 20, 30))
    model, seconds = timing_of(None, bootstrap)
    assert (model.s_turn, model.samples, seconds) == (Fraction(2), 2, Fraction(20))
    with pytest.raises(ValueError, match="the /my/logs bootstrap: no action with a cooldown"):
        timing_of(None, FleetBootstrap(fights=(), cooldowns=(0, 0)))


def test_timing_with_a_store_pools_the_fleet_and_the_bootstrap(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 15.0)
        model, seconds = timing_of(store, FleetBootstrap(fights=((5, 0, 10.0),), cooldowns=(10,)))
        assert (model.s_turn, model.samples, seconds) == (Fraction(5, 2), 2, Fraction(15))
    finally:
        store.close()
