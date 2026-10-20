"""The player's learned fight and action seconds (spec 2026-10-18 §2.9, rulings
CA/CC): the committed capture offline, else the fleet store's record pooled
with this character's `/my/logs` page, else the page alone."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing, fit_model
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state

PAGE = [("fight", 10, 5), ("fight", 20, 10), ("gathering", 30, None)]
"""A `/my/logs` page: two fights at 2 s a turn and a 30 s gather."""


def test_an_offline_player_reads_the_committed_capture() -> None:
    player = GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    player._log_entries = PAGE
    assert player._timing() == committed_timing()


def test_a_player_without_a_store_fits_its_page() -> None:
    player = GamePlayer(character="hero")
    player.state = make_state(haste=0)
    player._log_entries = PAGE
    model, seconds = player._timing()
    assert model == fit_model([(5, 0, 10.0), (10, 0, 20.0)])
    assert seconds == 20


def test_a_player_with_a_store_pools_the_fleet_record(tmp_path: Path) -> None:
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    store.start_session()
    try:
        store.record_cycle(Cycle(ts="2026-10-19T00:00:00+00:00", cycle_index=0, outcome="ok",
                                 actual_cooldown_seconds=15.0, fight_turns=5, fight_haste=0))
        player = GamePlayer(character="hero", history=store)
        player.state = make_state(haste=0)
        player._log_entries = PAGE
        model, seconds = player._timing()
        assert model.samples == 3 and model.s_turn == Fraction(5 * 15 + 50 + 200, 25 + 25 + 100)
        assert seconds == 15
    finally:
        store.close()


def test_a_player_with_no_observation_anywhere_raises() -> None:
    player = GamePlayer(character="hero")
    player.state = make_state(haste=0)
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
