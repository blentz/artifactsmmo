"""Drop observations from the fleet's cycles (spec 2026-10-18 §2.8): the
attempts and hits at a (source, item), pooled over the fleet, and the fleet's
prospecting slope `k`, read once per recorded cycle."""

from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning import drop_observations as mod
from artifactsmmo_cli.ai.learning.drop_observations import drop_counts, fleet_k
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.shared_world import shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def _store(path: Path, character: str = "hero") -> LearningStore:
    store = LearningStore(db_path=str(path), character=character)
    store.start_session()
    return store


def _record(store: LearningStore, action_repr: str, action_class: str, drops: str | None,
            outcome: str = "ok", prospecting: int | None = None, count: int = 1) -> None:
    for _ in range(count):
        store.record_cycle(Cycle(ts="2026-10-21T00:00:00+00:00", cycle_index=0,
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
    assert drop_counts(store, "trout_spot", "small_pearls") == (383, 2)
    assert drop_counts(store, "trout_spot", "trout") == (383, 383)
    assert drop_counts(store, "copper_rocks", "copper_ore") == (0, 0)


def test_the_counts_pool_the_fleet(tmp_path: Path) -> None:
    hero = _store(tmp_path / "learn.db")
    other = _store(tmp_path / "learn.db", character="other")
    _record(hero, "Fight(chicken)", "FightAction", '{"feather": 1, "raw_chicken": 1}')
    _record(other, "Fight(chicken)", "FightAction", '{"raw_chicken": 2}')
    assert drop_counts(hero, "chicken", "feather") == (2, 1)
    assert drop_counts(hero, "chicken", "raw_chicken") == (2, 2)


def test_only_a_won_solo_fight_is_an_attempt(tmp_path: Path) -> None:
    """A lost fight drops nothing, and a party fight is not the solo roll."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Fight(chicken)", "FightAction", '{"feather": 1}')
    _record(store, "Fight(chicken)", "FightAction", None, outcome="error:fight_lost")
    _record(store, "Fight(chicken+HAL)", "FightAction", '{"feather": 1}')
    assert drop_counts(store, "chicken", "feather") == (1, 1)


def test_a_new_cycle_refreshes_the_counts(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}')
    assert drop_counts(store, "trout_spot", "small_pearls") == (1, 0)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}')
    assert drop_counts(store, "trout_spot", "small_pearls") == (2, 1)
    _record(store, "Wait", "WaitAction", None)
    assert drop_counts(store, "trout_spot", "small_pearls") == (2, 1)


def test_the_cache_is_held_against_its_store(tmp_path: Path) -> None:
    """Two stores at the same last cycle id: the second is never served the
    first's counts."""
    first = _store(tmp_path / "a.db")
    second = _store(tmp_path / "b.db")
    _record(first, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}')
    _record(second, "Gather(trout_spot)", "GatherAction", '{"trout": 1}')
    assert drop_counts(first, "trout_spot", "small_pearls") == (1, 1)
    assert drop_counts(second, "trout_spot", "small_pearls") == (1, 0)
    assert mod._COUNTS[0][0] is second


def test_fleet_k_fits_every_drop_of_each_observed_source(tmp_path: Path) -> None:
    """100 gathers at `trout_spot` at prospecting 10: trout every time (rate 1),
    algae 10 times (rate 10) and pearls once (rate 300). Observed over API
    rate is 1, 1 and 3, so only the pearls pull: `k = 100·10·2 / (3·100·10²)
    = 1/15`. Rows without a recorded prospecting are no sample."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction",
            '{"trout": 1, "algae": 1, "small_pearls": 1}', prospecting=10)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1, "algae": 1}',
            prospecting=10, count=9)
    _record(store, "Gather(trout_spot->algae)", "GatherAction", '{"trout": 1}',
            prospecting=10, count=90)
    _record(store, "Gather(trout_spot)", "GatherAction", '{"small_pearls": 1}', count=5)
    assert fleet_k(store, _world()) == Fraction(1, 15)


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
        drop_counts(store, "trout_spot", "trout")


def test_an_empty_store_has_no_attempts(tmp_path: Path) -> None:
    store = _store(tmp_path / "learn.db")
    assert store.last_cycle_id() == 0
    assert drop_counts(store, "trout_spot", "trout") == (0, 0)


def test_the_rows_read_are_the_ones_between_the_marks(tmp_path: Path) -> None:
    """Rows past `through_id` are left for the next read, so a cycle recorded
    between the mark and the read is never folded twice."""
    store = _store(tmp_path / "learn.db")
    _record(store, "Gather(trout_spot)", "GatherAction", '{"trout": 1}', count=3)
    assert store.fleet_drop_rows(1, 2) == [("GatherAction", "Gather(trout_spot)", None,
                                            '{"trout": 1}')]
