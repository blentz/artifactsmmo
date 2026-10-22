"""Drop observations from the fleet's cycles (spec 2026-10-18 §2.8): the
attempts and hits at a (source, item), pooled over the fleet, and the fleet's
prospecting slope `k`, read once per recorded cycle."""

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning import drop_observations as mod
from artifactsmmo_cli.ai.learning.drop_observations import fleet_k, learned_drops
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from tests.test_ai.shared_world import shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def _store(path: Path, character: str = "hero") -> LearningStore:
    store = LearningStore(db_path=str(path), character=character)
    store.start_session()
    return store


def _record(store: LearningStore, action_repr: str, action_class: str, drops: str | None,
            outcome: str = "ok", prospecting: int | None = None, count: int = 1,
            ts: str = "2026-10-21T00:00:00+00:00") -> None:
    for _ in range(count):
        store.record_cycle(Cycle(ts=ts, cycle_index=0,
                                 action_repr=action_repr, action_class=action_class,
                                 outcome=outcome, drops_json=drops, prospecting=prospecting))


def _world() -> GameData:
    return shared_world(BUNDLE)


def test_pearls_at_trout_spot_count_every_gather_of_the_spot(tmp_path: Path) -> None:
    """383 gathers at `trout_spot`, by both learning keys a gather writes, 2 of
    them with `small_pearls`: (383, 2). A failed gather rolled no drop, and a
    cycle at another source or of another class is no attempt here."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}', count=300)
    _record(store, "Gather(trout_spot->small_pearls)", "GatherAction", '{"trout": 1}', count=81)
    _record(store, "Gather(trout_spot->small_pearls)", "GatherAction",
            '{"trout": 1, "small_pearls": 1}', count=2)
    _record(store, "Gather(trout_spot)", "GatherAction", None, outcome="error:cooldown")
    _record(store, "Gather(shrimp_spot)", "GatherAction", '{"small_pearls": 1}')
    _record(store, "Gather(trout_spot)", "NoPlan", '{"small_pearls": 1}', prospecting=10)
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (383, 2)
    assert learned_drops(store, _world()).counts("trout_spot", "trout") == (383, 383)
    assert learned_drops(store, _world()).counts("copper_rocks", "copper_ore") == (0, 0)


def test_the_counts_pool_the_fleet(tmp_path: Path) -> None:
    hero = _store(tmp_path / "learn.db")
    other = _store(tmp_path / "learn.db", character="other")
    _record(hero, "Fight(chicken)", "FightAction", '{"feather": 1, "raw_chicken": 1}')
    _record(other, "Fight(chicken)", "FightAction", '{"raw_chicken": 2}')
    assert learned_drops(hero, _world()).counts("chicken", "feather") == (2, 1)
    assert learned_drops(hero, _world()).counts("chicken", "raw_chicken") == (2, 2)


def test_only_a_won_solo_fight_is_an_attempt(tmp_path: Path) -> None:
    """A lost fight drops nothing, and a party fight is not the solo roll."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Fight(chicken)", "FightAction", '{"feather": 1}')
    _record(store, "Fight(chicken)", "FightAction", None, outcome="error:fight_lost")
    _record(store, "Fight(chicken+HAL)", "FightAction", '{"feather": 1}')
    assert learned_drops(store, _world()).counts("chicken", "feather") == (1, 1)


def test_a_new_cycle_refreshes_the_counts(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}')
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (1, 0)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}')
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (2, 1)
    _record(store, "Wait", "WaitAction", None)
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (2, 1)


def test_the_cache_is_held_against_its_store(tmp_path: Path) -> None:
    """Two stores at the same last cycle id: the second is never served the
    first's counts."""
    first = _store(tmp_path / "a.db")
    second = _store(tmp_path / "b.db")
    _record(first, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}')
    _record(second, "Gather(trout_spot)", "GatherAction", '{"trout": 1}')
    assert learned_drops(first, _world()).counts("trout_spot", "small_pearls") == (1, 1)
    assert learned_drops(second, _world()).counts("trout_spot", "small_pearls") == (1, 0)
    assert mod._COUNTS[0][0] is second


def test_fleet_k_fits_every_drop_of_each_observed_source(tmp_path: Path) -> None:
    """100 gathers at `trout_spot` at prospecting 10: trout every time (rate 1),
    algae 10 times (rate 10) and pearls once (rate 300). Observed over API
    rate is 1 for the algae and 3 for the pearls, so only the pearls pull:
    `k = 100·10·2 / (2·100·10²) = 1/10`. The trout, at rate 1, is capped at
    chance 1 for any `k` and is no sample (with it, k would read 1/15). Rows
    without a recorded prospecting are no sample."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction",
            '{"trout": 1, "algae": 1, "small_pearls": 1}', prospecting=10)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1, "algae": 1}',
            prospecting=10, count=9)
    _record(store, "Gather(trout_spot->algae)", "GatherAction", '{"trout": 1}',
            prospecting=10, count=90)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', count=5)
    assert fleet_k(store, _world()) == Fraction(1, 10)
    # The cycle's evidence carries the same slope (ruling T16a).
    assert learned_drops(store, _world()).k == Fraction(1, 10)


def test_fleet_k_reads_a_fight_from_the_monster_drops(tmp_path: Path) -> None:
    """4 chicken kills at prospecting 5, every one with a feather (rate 8):
    observed over API rate is 8 for the feather, 0 for the egg, the golden egg
    and the raw chicken (rate 2). `k = 4·5·(7 − 1 − 1 − 1) / (4·4·5²) = 1/5`."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Fight(chicken)", "FightAction", '{"feather": 1}', prospecting=5, count=4)
    assert fleet_k(store, _world()) == Fraction(1, 5)


def test_no_recorded_prospecting_fits_no_bonus(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', count=3)
    assert fleet_k(store, _world()) == 0


@pytest.mark.parametrize(("action_repr", "action_class"),
                         [("Gather(nowhere_spot)", "GatherAction"),
                          ("Fight(no_such_monster)", "FightAction")])
def test_a_source_the_catalogue_lacks_raises(tmp_path: Path, action_repr: str,
                                             action_class: str) -> None:
    store = _store(tmp_path / "learn.db")
    _record(store, action_repr, action_class, None, prospecting=10)
    with pytest.raises(ValueError, match="no drop table"):
        fleet_k(store, _world())


@pytest.mark.parametrize(("action_repr", "action_class", "match"),
                         [("Gather()", "GatherAction", "no resource"),
                          ("Fight()", "FightAction", "no monster")])
def test_a_learning_key_without_its_source_raises(tmp_path: Path, action_repr: str,
                                                  action_class: str, match: str) -> None:
    store = _store(tmp_path / "learn.db")
    _record(store, action_repr, action_class, None)
    with pytest.raises(ValueError, match=match):
        learned_drops(store, _world()).counts("trout_spot", "trout")


def test_an_empty_store_has_no_attempts(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    assert store.last_cycle_id() == 0
    assert learned_drops(store, _world()).counts("trout_spot", "trout") == (0, 0)


def test_the_rows_read_are_the_ones_between_the_marks(tmp_path: Path) -> None:
    """Rows past `through_id` are left for the next read, so a cycle recorded
    between the mark and the read is never folded twice."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}', count=3)
    assert store.fleet_drop_rows(1, 2, _world().season_start) == [
        ("GatherAction", "Gather(trout_spot)", None, '{"trout": 1}')]


def test_a_gather_without_its_learning_key_raises(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    store.record_cycle(Cycle(ts="2026-10-21T00:00:00+00:00", cycle_index=0,
                             action_class="GatherAction", outcome="ok"))
    with pytest.raises(ValueError, match="a GatherAction cycle with no action_repr"):
        learned_drops(store, _world()).counts("trout_spot", "trout")


def test_a_shrunken_table_is_read_afresh(tmp_path: Path) -> None:
    """The cycles were pruned under a live store: the tally restarts instead
    of keeping the rows that are gone."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}', count=2)
    assert learned_drops(store, _world()).counts("trout_spot", "trout") == (2, 2)
    with sqlite3.connect(tmp_path / "learn.db") as conn:
        conn.execute("DELETE FROM cycles")
    conn.close()
    assert learned_drops(store, _world()).counts("trout_spot", "trout") == (0, 0)


def test_an_ok_cycle_without_drops_is_an_attempt_with_no_hit(tmp_path: Path) -> None:
    """A won gather whose `drops_json` is NULL (the bag gained nothing) rolled
    the table and missed: an attempt, with no hit."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", None)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}')
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (2, 1)


def test_a_search_episode_reads_each_answer_once(tmp_path: Path) -> None:
    """Inside `search_cache` the tally and the slope are memoised: a cycle
    recorded inside the episode is not seen until it closes."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', prospecting=10)
    with store.search_cache():
        assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (1, 1)
        assert learned_drops(store, _world()).counts("trout_spot", "trout") == (1, 0)
        assert fleet_k(store, _world()) == Fraction(149, 10)
        _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}', prospecting=10,
                count=9)
        assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (1, 1)
        assert fleet_k(store, _world()) == Fraction(149, 10)
    assert learned_drops(store, _world()).counts("trout_spot", "small_pearls") == (10, 1)
    assert fleet_k(store, _world()) == Fraction(7, 5)


def test_the_slope_is_fitted_once_per_episode_and_catalogue(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Inside one episode `fit_k` runs once for a catalogue, and a second
    catalogue is fitted on its own, never served the first one's slope."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', prospecting=10)
    fits: list[int] = []

    def counted(samples):  # type: ignore[no-untyped-def]
        fits.append(len(samples))
        return Fraction(len(fits))

    monkeypatch.setattr(mod, "fit_k", counted)
    other = load_bundle_game_data(BUNDLE)
    with store.search_cache():
        assert fleet_k(store, _world()) == 1
        assert fleet_k(store, _world()) == 1
        assert len(fits) == 1
        assert fleet_k(store, other) == 2
    assert len(fits) == 2


def test_only_this_season_is_evidence(tmp_path: Path) -> None:
    """The bundle's season began 2026-06-27 (`GET /`, `season.start_date`). A
    cycle before it is no attempt, even at a source this catalogue lacks; a
    cycle at the start is one."""
    world = _world()
    assert world.season_start.isoformat() == "2026-06-27T00:00:00+00:00"
    store = _store(tmp_path / "learn.db")
    _record(store, "Fight(retired_boss)", "FightAction", '{"relic": 1}', prospecting=5,
            ts="2026-06-26T23:59:59.999999+00:00")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', prospecting=10,
            ts="2026-06-26T23:59:59+00:00")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}',
            ts="2026-06-27T00:00:00+00:00")
    assert learned_drops(store, world).counts("trout_spot", "small_pearls") == (1, 0)
    assert learned_drops(store, world).counts("retired_boss", "relic") == (0, 0)
    assert fleet_k(store, world) == 0


def test_an_unknown_source_this_season_raises(tmp_path: Path) -> None:
    """Within the season, a fight at a monster the catalogue lacks has no
    drop table to learn against: a defect, raised."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Fight(retired_boss)", "FightAction", '{"relic": 1}', prospecting=5)
    with pytest.raises(ValueError, match="monster retired_boss has no drop table"):
        fleet_k(store, _world())


def test_a_catalogue_without_the_server_page_has_no_season(tmp_path: Path) -> None:
    """No season start is invented: a hand-built catalogue cannot count."""
    store = _store(tmp_path / "learn.db")
    with pytest.raises(ValueError, match="no season start"):
        learned_drops(store, GameData()).counts("trout_spot", "trout")


def test_a_new_season_start_reads_the_tally_afresh(tmp_path: Path) -> None:
    """The same store at a later season start is not served the earlier
    season's tally: the start is part of what the tally was read for."""
    world = _world()
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}',
            ts="2026-08-01T00:00:00+00:00")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}',
            ts="2026-10-21T00:00:00+00:00")
    assert learned_drops(store, world).counts("trout_spot", "small_pearls") == (2, 1)
    later = replace(world, _season_start=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert learned_drops(store, later).counts("trout_spot", "small_pearls") == (1, 0)
