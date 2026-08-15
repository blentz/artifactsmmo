"""Tests for `formal.diff.store_records.load_cycles` — the shared reader every
verification harness now reads through instead of hand-rolling a loader over
`play-trace-*.jsonl` files and differencing consecutive state snapshots.

`tmp_db_path` is defined locally (not a shared conftest fixture), matching the
four `tests/test_ai/*` files that already define it this way.
"""

import json
import os
import tempfile

import pytest

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from formal.diff.store_records import EmptyCorpusError, load_cycles


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _seed(db_path, character="hero"):
    store = LearningStore(db_path=db_path, character=character)
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
        action_repr="Gather(copper_rocks)", action_class="GatherAction",
        level=12, xp=340, hp=90, delta_xp=0, delta_hp=-5,
        delta_skill_xp_json=json.dumps({"mining": 17}),
        skill_levels_json=json.dumps({"mining": 11}),
    ))
    store.close()


def test_load_cycles_reads_rows_as_records(tmp_db_path):
    _seed(tmp_db_path)
    [rec] = load_cycles(tmp_db_path)
    assert rec.action_repr == "Gather(copper_rocks)"
    assert rec.level == 12
    assert rec.delta_skill_xp == {"mining": 17}
    assert rec.skill_levels == {"mining": 11}


def test_load_cycles_reads_the_rows_own_delta_not_a_difference(tmp_db_path):
    """The row's `delta_xp`/`delta_hp` come straight off the record that wrote
    them, not from subtracting a neighboring row's `xp`/`hp`. Seed two cycles
    whose ABSOLUTE xp/hp would produce a DIFFERENT number than the stored
    delta if a consumer (wrongly) differenced them, and confirm the record
    reports the stored delta."""
    store = LearningStore(db_path=tmp_db_path, character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
        action_repr="Craft(copper_dagger)", action_class="CraftAction",
        xp=100, hp=90, delta_xp=0, delta_hp=0,
    ))
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:01+00:00", cycle_index=1, outcome="ok",
        action_repr="Craft(copper_dagger)", action_class="CraftAction",
        xp=175, hp=90, delta_xp=75, delta_hp=0,
    ))
    store.close()
    recs = load_cycles(tmp_db_path)
    assert [r.cycle_index for r in recs] == [0, 1]
    # Differencing xp across rows would credit cycle 0 with 75 (the FOLLOWING
    # cycle's gain) -- the exact off-by-one this module exists to prevent.
    assert recs[0].delta_xp == 0
    assert recs[1].delta_xp == 75


def test_a_row_without_skill_levels_reads_as_none_not_empty(tmp_db_path):
    """None means "this row cannot answer a level question"; {} would mean
    "the character had no skills", and a consumer must be able to tell those
    apart to exclude the row rather than treat it as level 0."""
    store = LearningStore(db_path=tmp_db_path, character="hero")
    store.start_session()
    store.record_cycle(Cycle(ts="2026-08-15T00:00:00+00:00",
                             cycle_index=0, outcome="ok"))
    store.close()
    [rec] = load_cycles(tmp_db_path)
    assert rec.skill_levels is None


def test_a_row_with_malformed_skill_levels_json_reads_as_none(tmp_db_path):
    store = LearningStore(db_path=tmp_db_path, character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
        skill_levels_json="not-json",
    ))
    store.close()
    [rec] = load_cycles(tmp_db_path)
    assert rec.skill_levels is None


def test_a_row_with_malformed_delta_skill_xp_json_reads_as_empty_dict(tmp_db_path):
    """`delta_skill_xp` is never None -- Cycle.delta_skill_xp_json defaults to
    '{}' and is NOT NULL, so a consumer never needs to guard against a missing
    delta the way it must for `skill_levels`."""
    store = LearningStore(db_path=tmp_db_path, character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
        delta_skill_xp_json="not-json",
    ))
    store.close()
    [rec] = load_cycles(tmp_db_path)
    assert rec.delta_skill_xp == {}


def test_an_empty_corpus_raises_rather_than_returning_nothing(tmp_db_path):
    """A harness that silently finds nothing to check is indistinguishable
    from one that checked and found nothing wrong. Every consumer of this
    loader must fail loudly instead."""
    LearningStore(db_path=tmp_db_path, character="hero").close()
    with pytest.raises(EmptyCorpusError):
        load_cycles(tmp_db_path)


def test_character_filter_narrows_and_ordering_is_by_cycle_index(tmp_db_path):
    store_a = LearningStore(db_path=tmp_db_path, character="hal")
    store_a.start_session()
    store_a.record_cycle(Cycle(ts="2026-08-15T00:00:02+00:00", cycle_index=1,
                               outcome="ok"))
    store_a.record_cycle(Cycle(ts="2026-08-15T00:00:00+00:00", cycle_index=0,
                               outcome="ok"))
    store_a.close()

    store_b = LearningStore(db_path=tmp_db_path, character="robby")
    store_b.start_session()
    store_b.record_cycle(Cycle(ts="2026-08-15T00:00:01+00:00", cycle_index=0,
                               outcome="ok"))
    store_b.close()

    hal_only = load_cycles(tmp_db_path, character="hal")
    assert [r.character for r in hal_only] == ["hal", "hal"]
    assert [r.cycle_index for r in hal_only] == [0, 1]

    everyone = load_cycles(tmp_db_path)
    assert {r.character for r in everyone} == {"hal", "robby"}
