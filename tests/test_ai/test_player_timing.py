"""The player's learned fight and action seconds (spec 2026-10-18 §2.9, rulings
CA/CC/ZD): the committed capture offline, else the fleet store's record pooled
with the account-log bootstrap, else the bootstrap alone."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.learning.fight_seconds_model import (
    FleetBootstrap,
    committed_timing,
    fit_model,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state

PAGE = FleetBootstrap(fights=((5, 0, 10.0), (10, 0, 20.0)), cooldowns=(10, 20, 30))
"""An account-log bootstrap: two fights at 2 s a turn and a 30 s gather."""


def test_an_offline_player_reads_the_committed_capture() -> None:
    player = GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    player._bootstrap = PAGE
    assert player._timing() == committed_timing()


def test_a_player_without_a_store_fits_its_page() -> None:
    player = GamePlayer(character="hero")
    player._bootstrap = PAGE
    model, seconds = player._timing()
    assert model == fit_model([(5, 0, 10.0), (10, 0, 20.0)])
    assert seconds == 20


def test_a_player_with_a_store_pools_the_fleet_record(tmp_path: Path) -> None:
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    store.start_session()
    try:
        store.record_cycle(Cycle(ts="2026-10-19T00:00:00+00:00", cycle_index=0, outcome="ok",
                                 actual_cooldown_seconds=15.0, fight_turns=5, fight_haste=0))
        player = GamePlayer(character="hero", history=store, fight_bootstrap=PAGE)
        model, seconds = player._timing()
        assert model.samples == 3 and model.s_turn == Fraction(5 * 15 + 50 + 200, 25 + 25 + 100)
        assert seconds == 15
    finally:
        store.close()


def test_a_player_with_no_observation_anywhere_raises() -> None:
    player = GamePlayer(character="hero", fight_bootstrap=FleetBootstrap((), ()))
    with pytest.raises(ValueError, match="the /my/logs bootstrap: no action with a cooldown"):
        player._timing()


def test_a_timed_context_carries_the_cycles_seconds() -> None:
    player = GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    timed = player._timed(replace(NO_PROFILE_CONTEXT, combat_monster="wolf"))
    model, seconds = committed_timing()
    assert (timed.fight_seconds, timed.action_seconds, timed.combat_monster) == (
        model, seconds, "wolf")


def test_seeding_offline_times_the_cycles_context() -> None:
    """`_last_ctx` is read before the first decide (a resumed plan); offline
    seeding gives it the committed capture's seconds."""
    gd = load_bundle_game_data(Path(__file__).parent / "scenarios" / "fixtures"
                               / "gamedata_bundle.json")
    player = GamePlayer(character="hero")
    player.seed_offline(make_state(), gd)
    assert player._last_ctx.fight_seconds == committed_timing()[0]


def test_a_gathering_character_fits_on_the_accounts_fights(tmp_path: Path) -> None:
    """Ruling ZD (live 2026-10-20: R2D2's and C3P0's `plan` raised "no fight
    with a positive cooldown", their own newest 100 log entries all gathers,
    on a store that had recorded no fight's length). The bootstrap is the
    account's log, each fight at its character's sheet haste, charged to the
    account bucket."""
    gather = SimpleNamespace(character="R2D2", type_=LogType.GATHERING, cooldown=25, content={})
    fight = SimpleNamespace(character="Robby", type_=LogType.FIGHT, cooldown=10,
                            content={"fight": {"turns": 5}})

    class Api:
        def get_my_characters(self) -> SimpleNamespace:
            return SimpleNamespace(data=[SimpleNamespace(name="R2D2", haste=0),
                                         SimpleNamespace(name="Robby", haste=8)])

        def get_character_logs(self, name: str, page: int, size: int) -> SimpleNamespace:
            return SimpleNamespace(data=[gather] if name == "R2D2" else [fight], pages=1)

        def get_all_characters_logs(self, page: int, size: int) -> SimpleNamespace:
            return SimpleNamespace(data=[gather, fight], pages=1)

    store = LearningStore(db_path=str(tmp_path / "t.db"), character="R2D2")
    store.start_session()
    try:
        player = GamePlayer(character="R2D2", history=store)
        acquired: list[str] = []
        player._acquire_account = lambda: acquired.append("account")  # type: ignore[method-assign]
        player._bootstrap = player._fetch_bootstrap(Api())  # type: ignore[arg-type]
        assert player._bootstrap == FleetBootstrap(fights=((5, 8, 10.0),), cooldowns=(25, 10))
        assert acquired == ["account", "account"]
        model, seconds = player._timing()
        assert (model.s_turn, model.samples, seconds) == (2, 1, Fraction(35, 2))
    finally:
        store.close()
