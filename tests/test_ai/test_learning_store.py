"""Tests for LearningStore."""

import json
import multiprocessing
import os
import sqlite3
import tempfile
from contextlib import closing

import pytest
from sqlalchemy import text
from sqlmodel import Session as SqlSession
from sqlmodel import create_engine, select

from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.store import (
    MIN_DROP_KILLS,
    LearningStore,
    _parse_skill_xp_value,
    grind_action_prefix,
)


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestLearningStoreInit:
    def test_creates_db_file(self, tmp_db_path):
        os.unlink(tmp_db_path)
        assert not os.path.exists(tmp_db_path)
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        assert os.path.exists(tmp_db_path)
        store.close()

    def test_creates_tables(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with SqlSession(store._engine) as s:
            result = s.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )).all()
        store.close()
        names = {row[0] for row in result}
        assert "cycles" in names
        assert "sessions" in names

    def test_wal_journal_mode_enabled(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with store._engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        store.close()
        assert mode == "wal"

    def test_idempotent_init(self, tmp_db_path):
        store1 = LearningStore(db_path=tmp_db_path, character="testchar")
        store1.close()
        store2 = LearningStore(db_path=tmp_db_path, character="testchar")
        store2.close()


class TestSessionLifecycle:
    def test_start_session_returns_id_and_inserts_row(self, tmp_db_path):
        """start_session allocates the id; row appears only after record_cycle."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        assert session_id.startswith("session-")

        # Record a cycle to trigger lazy row creation
        store.record_cycle(Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="x", cycle_index=0, character="x", outcome="ok",
        ))

        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character, exit_reason FROM sessions")).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == session_id
        assert rows[0][1] == "testchar"
        assert rows[0][2] is None

    def test_end_session_records_exit_reason_and_cycle_count(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        # Record 3 cycles so end_session has something to count
        for i in range(3):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
            ))
        store.end_session(exit_reason="keyboard_interrupt")
        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT exit_reason, ended_at, cycle_count FROM sessions WHERE session_id=:sid"
            ), {"sid": session_id}).all()
        store.close()
        assert rows[0][0] == "keyboard_interrupt"
        assert rows[0][1] is not None
        assert rows[0][2] == 3

    def test_win_count_counts_only_ok_outcomes(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        for i, o in enumerate(["ok", "ok", "error:fight_lost"]):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00", session_id="x", cycle_index=i,
                character="testchar", outcome=o, action_repr="Fight(chicken)"))
        assert store.win_count("Fight(chicken)") == 2
        assert store.sample_count("Fight(chicken)") == 3
        assert store.win_count("Fight(never)") == 0
        store.close()

    def test_win_count_is_memoised_inside_a_search(self, tmp_db_path):
        """`win_count` is the hottest read in the codebase and was the only member
        of its family issuing a fresh SELECT per call.

        `is_winnable` -> `_won_at_or_above_level` walks every monster at or above a
        level, so ONE `cheapest_path_to_level` walk fired 3,617 queries and took
        ~400ms, ~95% of it SQLite. Memoised it is ~23ms. This pins the memo so the
        query storm cannot come back silently."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        store.record_cycle(Cycle(
            ts="2026-05-17T00:00:00+00:00", session_id="x", cycle_index=0,
            character="testchar", outcome="ok", action_repr="Fight(chicken)"))

        calls: list[int] = []
        original = store._win_count_uncached

        def counting(action_repr: str) -> int:
            calls.append(1)
            return original(action_repr)

        store._win_count_uncached = counting  # type: ignore[method-assign]
        with store.search_cache():
            assert [store.win_count("Fight(chicken)") for _ in range(5)] == [1] * 5
        assert len(calls) == 1, "win_count hit the DB more than once inside a search"

        # ...and OUTSIDE a search there is no cache, so every call still reads the
        # DB — a later cycle must see a fight recorded since.
        calls.clear()
        assert store.win_count("Fight(chicken)") == 1
        assert store.win_count("Fight(chicken)") == 1
        assert len(calls) == 2
        store.close()

    def test_end_session_without_start_is_noop(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.end_session()
        store.close()

    def test_start_session_does_not_write_row_immediately(self, tmp_db_path):
        """Lazy session creation: row only written on first record_cycle."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        with SqlSession(store._engine) as s:
            rows = list(s.exec(select(Session)))
        store.close()
        assert len(rows) == 0

    def test_record_cycle_writes_session_row_lazily(self, tmp_db_path):
        """First record_cycle triggers the deferred Session row write."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        sid = store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="x", cycle_index=0, character="x", outcome="ok",
        )
        store.record_cycle(cycle)
        with SqlSession(store._engine) as s:
            rows = list(s.exec(select(Session)))
        store.close()
        assert len(rows) == 1
        assert rows[0].session_id == sid

    def test_end_session_noop_without_cycle(self, tmp_db_path):
        """end_session without any record_cycle is no-op (no row to mark)."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        store.end_session(exit_reason="crash")  # should not raise
        with SqlSession(store._engine) as s:
            rows = list(s.exec(select(Session)))
        store.close()
        assert len(rows) == 0


class TestRecordCycle:
    def test_round_trip(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="overridden",
            cycle_index=0,
            character="overridden",
            outcome="ok",
            action_repr="Fight(yellow_slime)",
            actual_cooldown_seconds=12.5,
        )
        store.record_cycle(cycle)

        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT action_repr, actual_cooldown_seconds, session_id, character FROM cycles"
            )).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == "Fight(yellow_slime)"
        assert rows[0][1] == 12.5

    def test_record_cycle_overrides_session_id_and_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="actual_char")
        session_id = store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="wrong",
            cycle_index=0,
            character="wrong",
            outcome="ok",
        )
        store.record_cycle(cycle)
        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character FROM cycles")).all()
        store.close()
        assert rows[0][0] == session_id
        assert rows[0][1] == "actual_char"

    def test_record_cycle_swallows_sqlalchemy_error(self, tmp_db_path, capsys):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()

        # Real triggering state: drop the pooled connections, then make the
        # db file read-only so the next commit raises a genuine
        # OperationalError (a SQLAlchemyError) straight from sqlite.
        store._engine.dispose()
        os.chmod(tmp_db_path, 0o444)
        try:
            cycle = Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id="x", cycle_index=0, character="testchar", outcome="ok",
            )
            store.record_cycle(cycle)  # must swallow, never raise
        finally:
            os.chmod(tmp_db_path, 0o644)
            store.close()
        assert "record_cycle failed" in capsys.readouterr().out


def test_package_reexport():
    from artifactsmmo_cli.ai.learning import LearningStore as RootImport
    from artifactsmmo_cli.ai.learning.store import LearningStore as ModuleImport
    assert RootImport is ModuleImport


def _insert_cycles(store, action_repr, cooldowns, outcomes=None, action_class=None):
    """Helper: insert N cycles with given cooldowns and outcomes."""
    outcomes = outcomes or ["ok"] * len(cooldowns)
    for i, (cd, oc) in enumerate(zip(cooldowns, outcomes, strict=False)):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome=oc,
            action_repr=action_repr,
            action_class=action_class,
            actual_cooldown_seconds=cd,
        ))


class TestActionClassCost:
    def test_returns_default_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0], action_class="FightAction")
        assert store.action_class_cost("FightAction", default=99.0) == 99.0
        store.close()

    def test_returns_median_over_the_whole_class(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        # Different reprs, same class — the per-class median spans both.
        _insert_cycles(store, "Fight(x)", [10.0, 12.0], action_class="FightAction")
        _insert_cycles(store, "Fight(y)", [14.0, 16.0, 18.0], action_class="FightAction")
        assert store.action_class_cost("FightAction", default=99.0) == 14.0
        store.close()

    def test_filters_by_action_class(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 5, action_class="FightAction")
        _insert_cycles(store, "Move(a,b)", [30.0] * 5, action_class="MovementAction")
        assert store.action_class_cost("FightAction", default=99.0) == 10.0
        assert store.action_class_cost("MovementAction", default=99.0) == 30.0
        store.close()

    def test_ignores_failed_actions(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)",
                       cooldowns=[10.0, 10.0, 10.0, 99.0, 99.0],
                       outcomes=["ok", "ok", "ok", "error:HTTP_497", "error:HTTP_497"],
                       action_class="FightAction")
        assert store.action_class_cost("FightAction", default=42.0) == 42.0
        store.close()


class TestActionClassFraction:
    def test_empty_returns_zero(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        assert store.action_class_fraction("FightAction") == 0.0
        store.close()

    def test_fraction_over_action_mix(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [1.0, 1.0, 1.0], action_class="FightAction")
        _insert_cycles(store, "Dep", [1.0], action_class="DepositAllAction")
        assert store.action_class_fraction("FightAction") == 0.75
        assert store.action_class_fraction("DepositAllAction") == 0.25
        store.close()

    def test_failed_cycles_excluded_from_denominator(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [1.0, 1.0], action_class="FightAction")
        _insert_cycles(store, "Fight(y)",
                       cooldowns=[1.0, 1.0],
                       outcomes=["error:HTTP_497", "error:HTTP_497"],
                       action_class="FightAction")
        # Only the 2 ok cycles count → fraction 1.0 (both ok cycles are FightAction).
        assert store.action_class_fraction("FightAction") == 1.0
        store.close()


class TestActionCost:
    def test_returns_default_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0])
        assert store.action_cost("Fight(x)", default=99.0) == 99.0
        store.close()

    def test_returns_median_when_at_least_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0, 13.0, 14.0])
        assert store.action_cost("Fight(x)", default=99.0) == 12.0
        store.close()

    def test_filters_by_action_repr(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 5)
        _insert_cycles(store, "Fight(y)", [20.0] * 5)
        assert store.action_cost("Fight(x)", default=99.0) == 10.0
        assert store.action_cost("Fight(y)", default=99.0) == 20.0
        store.close()

    def test_ignores_failed_actions(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)",
                       cooldowns=[10.0, 10.0, 10.0, 99.0, 99.0],
                       outcomes=["ok", "ok", "ok", "error:HTTP_497", "error:HTTP_497"])
        assert store.action_cost("Fight(x)", default=42.0) == 42.0
        store.close()


class TestSuccessRate:
    def test_returns_1_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 3, outcomes=["error:X"] * 3)
        assert store.success_rate("Fight(x)") == 1.0
        store.close()

    def test_all_ok_returns_1(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10, outcomes=["ok"] * 10)
        assert store.success_rate("Fight(x)") == 1.0
        store.close()

    def test_all_error_returns_0(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10, outcomes=["error:X"] * 10)
        assert store.success_rate("Fight(x)") == 0.0
        store.close()

    def test_mixed_returns_fraction(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10,
                       outcomes=["ok"] * 7 + ["error:X"] * 3)
        assert store.success_rate("Fight(x)") == 0.7
        store.close()


def _insert_cycles_with_deltas(store, action_repr, deltas):
    for i, d in enumerate(deltas):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome="ok",
            action_repr=action_repr,
            delta_xp=d.get("delta_xp"),
            delta_gold=d.get("delta_gold"),
            delta_hp=d.get("delta_hp"),
            delta_inv_used=d.get("delta_inv_used"),
        ))


class TestActionEffect:
    def test_returns_none_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Fight(x)", [{"delta_xp": 10}] * 3)
        assert store.action_effect("Fight(x)", "delta_xp") is None
        store.close()

    def test_returns_median_delta_xp(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Fight(x)",
            [{"delta_xp": v} for v in [10, 12, 14, 16, 18]])
        assert store.action_effect("Fight(x)", "delta_xp") == 14.0
        store.close()

    def test_returns_median_delta_gold(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Sell(x)",
            [{"delta_gold": v} for v in [5, 5, 10, 10, 10]])
        assert store.action_effect("Sell(x)", "delta_gold") == 10.0
        store.close()

    def test_unknown_field_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "X", [{"delta_xp": 10}] * 5)
        assert store.action_effect("X", "nonexistent_field") is None
        store.close()


def _insert_goal_satisfactions(store, goal_repr, cycle_deltas):
    for i, cd in enumerate(cycle_deltas):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome="ok",
            selected_goal=goal_repr,
            cycles_to_satisfy=cd,
        ))


class TestGoalAvgCyclesToSatisfy:
    def test_returns_none_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_goal_satisfactions(store, "FarmMonster(x)", [3, 5, 7])
        assert store.goal_avg_cycles_to_satisfy("FarmMonster(x)") is None
        store.close()

    def test_returns_median_when_enough_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_goal_satisfactions(store, "FarmMonster(x)", [4, 5, 6, 7, 8])
        assert store.goal_avg_cycles_to_satisfy("FarmMonster(x)") == 6.0
        store.close()


class TestSampleCount:
    def test_returns_zero_for_unknown_action(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        assert store.sample_count("Nothing(x)") == 0
        store.close()

    def test_counts_only_matching_action_and_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 7)
        _insert_cycles(store, "Fight(y)", [10.0] * 3)
        assert store.sample_count("Fight(x)") == 7
        assert store.sample_count("Fight(y)") == 3
        store.close()


class TestStatsRollups:
    def test_action_stats_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        stats = store.action_stats("Nothing(x)")
        store.close()
        assert stats.action_repr == "Nothing(x)"
        assert stats.sample_count == 0
        assert stats.median_cost_seconds is None
        assert stats.success_rate == 1.0

    def test_action_stats_populated(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        for i in range(10):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T01:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(x)", actual_cooldown_seconds=12.0,
                delta_xp=10, delta_gold=0,
            ))
        stats = store.action_stats("Fight(x)")
        store.close()
        assert stats.sample_count == 10
        assert stats.median_cost_seconds == 12.0
        assert stats.success_rate == 1.0
        assert stats.median_delta_xp == 10.0


class TestGoalStatsRollup:
    def test_goal_stats_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        stats = store.goal_stats("Nothing")
        store.close()
        assert stats.sample_count == 0
        assert stats.avg_cycles_to_satisfy is None
        assert stats.satisfaction_rate == 0.0


class TestSearchCache:
    def test_search_cache_memoizes_repeated_query(self, tmp_db_path):
        """Inside search_cache context, the same (repr, window) is computed only once."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "X", [10.0] * 5)

        calls: list[int] = []
        original = store._success_rate_uncached

        def counting_uncached(action_repr: str, window: int) -> float:
            calls.append(1)
            return original(action_repr, window)

        store._success_rate_uncached = counting_uncached  # type: ignore[method-assign]

        with store.search_cache():
            r1 = store.success_rate("X")
            r2 = store.success_rate("X")

        assert r1 == r2
        assert len(calls) == 1, "uncached called more than once inside context"

        # Outside the context cache is gone — two more calls → two more invocations
        r3 = store.success_rate("X")
        r4 = store.success_rate("X")
        assert r3 == r4
        assert len(calls) == 3, "expected 2 more uncached calls outside context"

        store.close()

    def test_action_cost_default_not_cached(self, tmp_db_path):
        """action_cost caches the median (None when <5 samples); default is applied after."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        # Only 3 samples — median will be None, default should vary per call
        _insert_cycles(store, "Y", [5.0, 5.0, 5.0])

        with store.search_cache():
            cost_3 = store.action_cost("Y", default=3.0)
            cost_9 = store.action_cost("Y", default=9.0)

        assert cost_3 == 3.0
        assert cost_9 == 9.0

        store.close()

    def test_search_cache_reentrant(self, tmp_db_path):
        """Nested search_cache contexts reuse the outer cache; after both exit, cache is None."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")

        with store.search_cache():
            inner_cache_ref = store._search_cache
            assert inner_cache_ref is not None
            with store.search_cache():
                # Inner context reuses the same dict object
                assert store._search_cache is inner_cache_ref
            # After inner exits, still the outer cache
            assert store._search_cache is inner_cache_ref

        # After outer exits, cache is None
        assert store._search_cache is None

        store.close()

    def test_no_cache_outside_context(self, tmp_db_path):
        """Without entering search_cache, _search_cache is None and calls recompute."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Z", [7.0] * 5)

        assert store._search_cache is None

        calls: list[int] = []
        original = store._action_cost_median

        def counting_median(action_repr: str, window: int) -> float | None:
            calls.append(1)
            return original(action_repr, window)

        store._action_cost_median = counting_median  # type: ignore[method-assign]

        store.action_cost("Z", default=1.0)
        store.action_cost("Z", default=1.0)

        assert len(calls) == 2, "expected two DB calls outside cache context"

        store.close()


class TestGAMigration:
    """Phase G-A migration: pre-existing DBs missing delta_skill_xp_json
    must be migrated on open."""

    def test_old_db_without_column_migrates_on_open(self, tmp_path):
        import sqlite3
        db_path = str(tmp_path / "old.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE cycles (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                session_id TEXT NOT NULL,
                cycle_index INTEGER NOT NULL,
                character TEXT NOT NULL,
                selected_goal TEXT, action_repr TEXT, action_class TEXT, outcome TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY, character TEXT, started_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Opening the store should add the column.
        store = LearningStore(db_path=db_path, character="hero")
        store.close()

        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
        conn.close()
        assert "delta_skill_xp_json" in cols

    def test_fresh_db_already_has_column(self, tmp_path):
        """No false alarm on a freshly-created DB."""
        import sqlite3
        db_path = str(tmp_path / "new.db")
        store = LearningStore(db_path=db_path, character="hero")
        store.close()
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
        conn.close()
        assert "delta_skill_xp_json" in cols


class TestSkillLevelsColumn:
    def test_a_cycle_records_the_skill_levels_held_before_its_action(self, tmp_db_path):
        """The gap that forced the craft-xp measurement onto play-traces:
        `cycles` recorded skill DELTAS and never skill LEVELS, so a replay
        could not compute `skill_level - content_level` from the store at all.
        """
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        store.record_cycle(Cycle(
            ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
            skill_levels_json=json.dumps({"mining": 11, "woodcutting": 4}),
        ))
        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT skill_levels_json FROM cycles")).all()
        store.close()
        assert json.loads(rows[0][0]) == {"mining": 11, "woodcutting": 4}

    def test_a_cycle_written_without_levels_reads_back_as_none(self, tmp_db_path):
        """Nullable on purpose: the 49,263 rows already in the wild were
        written before this column existed and cannot acquire levels. A
        consumer must exclude them, not read them as level 0."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        store.record_cycle(Cycle(ts="2026-08-15T00:00:00+00:00",
                                 cycle_index=0, outcome="ok"))
        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT skill_levels_json FROM cycles")).all()
        store.close()
        assert rows[0][0] is None

    def test_an_old_cycles_table_gains_the_column_on_open(self, tmp_path):
        """The `consumables_expended_json` incident is what this mirrors: a
        column that shipped in the model without a matching one-shot ALTER made
        every record_cycle INSERT fail on pre-existing DBs, and learning went
        silently dead on old caches."""
        db_path = str(tmp_path / "old_cycles.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE cycles (
                id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session_id TEXT NOT NULL,
                cycle_index INTEGER NOT NULL, character TEXT NOT NULL,
                selected_goal TEXT, action_repr TEXT, action_class TEXT, outcome TEXT,
                delta_skill_xp_json TEXT NOT NULL DEFAULT '{}',
                consumables_expended_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY, character TEXT, started_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        store = LearningStore(db_path=db_path, character="hero")
        check = sqlite3.connect(db_path)
        try:
            cols = {r[1] for r in check.execute("PRAGMA table_info(cycles)")}
        finally:
            check.close()   # unclosed connections surface as an unraisable
                            # warning blamed on a LATER test; close explicitly
        assert "skill_levels_json" in cols
        store.close()


def test_records_and_returns_skill_max_xp_observations(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    store.record_skill_max_xp("alchemy", 1, 150)
    store.record_skill_max_xp("alchemy", 2, 220)
    store.record_skill_max_xp("alchemy", 1, 150)  # idempotent on (skill, level)
    obs = store.skill_max_xp_observations("alchemy")
    store.close()
    assert obs == {1: 150, 2: 220}


def test_task_reward_value_mean_improves_with_history(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    assert store.mean_task_reward_value(default=5.0) == 5.0
    store.record_task_reward_value(100.0)
    store.record_task_reward_value(200.0)
    assert store.mean_task_reward_value(default=5.0) == 150.0
    assert store.task_reward_sample_count() == 2
    store.close()


class TestSkillXpPerCycle:
    def test_returns_none_when_no_cycles(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result is None

    def test_returns_none_when_no_positive_deltas_for_skill(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        # Insert cycles with only mining XP, not alchemy
        with SqlSession(store._engine) as s:
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"mining": 3}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result is None

    def test_returns_mean_positive_deltas_for_skill(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        # Insert 3 cycles: alchemy 5, alchemy 15, mining 3 (no alchemy)
        with SqlSession(store._engine) as s:
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 5}',
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:01+00:00",
                session_id=store._session_id, cycle_index=1,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 15}',
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:02+00:00",
                session_id=store._session_id, cycle_index=2,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"mining": 3}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result == 10.0  # mean of 5 and 15

    def test_returns_mean_for_mining(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        with SqlSession(store._engine) as s:
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 5}',
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:01+00:00",
                session_id=store._session_id, cycle_index=1,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"mining": 3}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("mining")
        store.close()
        assert result == 3.0

    def test_zero_delta_is_excluded(self, tmp_db_path):
        """Cycles with delta of 0 for the skill should not count."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        with SqlSession(store._engine) as s:
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 0}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result is None

    def test_window_limits_rows_considered(self, tmp_db_path):
        """Only the most recent `window` cycles are considered."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        with SqlSession(store._engine) as s:
            # Insert 3 old cycles with alchemy=100
            for i in range(3):
                s.add(Cycle(
                    ts=f"2026-05-17T00:00:{i:02d}+00:00",
                    session_id=store._session_id, cycle_index=i,
                    character="testchar", outcome="ok",
                    delta_skill_xp_json='{"alchemy": 100}',
                ))
            # Insert 2 recent cycles with alchemy=10
            for i in range(3, 5):
                s.add(Cycle(
                    ts=f"2026-05-17T00:01:{i:02d}+00:00",
                    session_id=store._session_id, cycle_index=i,
                    character="testchar", outcome="ok",
                    delta_skill_xp_json='{"alchemy": 10}',
                ))
            s.commit()
        # window=2 should only see the 2 most recent cycles (alchemy=10 each)
        result = store.skill_xp_per_cycle("alchemy", window=2)
        store.close()
        assert result == 10.0

    def test_filters_by_character(self, tmp_db_path):
        """skill_xp_per_cycle only considers cycles for the store's character."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        with SqlSession(store._engine) as s:
            # cycle for a different character
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="villain", outcome="ok",
                delta_skill_xp_json='{"alchemy": 50}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result is None

    def test_malformed_json_row_is_skipped(self, tmp_db_path):
        """A malformed `delta_skill_xp_json` row must NOT crash the average —
        json.loads inside skill_xp_per_cycle is guarded the same way as the
        parser in projections._parse_skill_xp. Insert several bad rows
        alongside valid alchemy=10 and alchemy=20 rows and assert the average
        is 15."""
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        with SqlSession(store._engine) as s:
            s.add(Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id=store._session_id, cycle_index=0,
                character="testchar", outcome="ok",
                delta_skill_xp_json="not-json-at-all",
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:01+00:00",
                session_id=store._session_id, cycle_index=1,
                character="testchar", outcome="ok",
                delta_skill_xp_json='[1, 2, 3]',  # valid JSON but not a dict
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:02+00:00",
                session_id=store._session_id, cycle_index=2,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": "not-a-number"}',
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:03+00:00",
                session_id=store._session_id, cycle_index=3,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 10}',
            ))
            s.add(Cycle(
                ts="2026-05-17T00:00:04+00:00",
                session_id=store._session_id, cycle_index=4,
                character="testchar", outcome="ok",
                delta_skill_xp_json='{"alchemy": 20}',
            ))
            s.commit()
        result = store.skill_xp_per_cycle("alchemy")
        store.close()
        assert result == 15.0


def _break_engine(store: LearningStore) -> None:
    """Swap in a real engine whose SQLite URL points at a directory, so every
    SqlSession query against it raises OperationalError (a SQLAlchemyError).

    This is a genuine DB-layer fault: the store's own query logic still runs;
    only the underlying connection fails. It exercises the documented
    best-effort degradation contract without mocking the unit under test.
    """
    bad_dir = tempfile.mkdtemp()
    store._engine = create_engine(f"sqlite:///{bad_dir}")


class TestDegradationOnDbError:
    """Every query method must return its documented default when the DB layer
    raises SQLAlchemyError, never propagate the exception (best-effort store)."""

    def test_end_session_swallows_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        # Force the session row to exist so end_session reaches the DB write.
        store.record_cycle(Cycle(ts="2026-05-17T00:00:00+00:00", cycle_index=0, outcome="ok"))
        _break_engine(store)
        # No exception; session id is cleared regardless.
        store.end_session()
        assert store._session_id is None

    def test_ensure_session_row_swallows_error(self, tmp_db_path, capsys):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        _break_engine(store)
        # record_cycle -> _ensure_session_row hits the broken engine first.
        store.record_cycle(Cycle(ts="2026-05-17T00:00:00+00:00", cycle_index=0, outcome="ok"))
        out = capsys.readouterr().out
        assert "_ensure_session_row failed" in out

    def test_record_cycle_swallows_error(self, tmp_db_path, capsys):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        store._session_row_written = True  # skip _ensure_session_row write
        _break_engine(store)
        store.record_cycle(Cycle(ts="2026-05-17T00:00:00+00:00", cycle_index=0, outcome="ok"))
        out = capsys.readouterr().out
        assert "record_cycle failed" in out

    def test_record_cycle_no_session_is_noop(self, tmp_db_path):
        """record_cycle returns early (no DB write) when no session was started."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        # start_session was never called -> _session_id is None.
        store.record_cycle(Cycle(ts="2026-05-17T00:00:00+00:00", cycle_index=0, outcome="ok"))
        with SqlSession(store._engine) as s:
            count = len(list(s.exec(select(Cycle))))
        store.close()
        assert count == 0

    def test_action_cost_returns_default(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.action_cost("FightAction(chicken)", default=3.5) == 3.5

    def test_action_class_cost_returns_default(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.action_class_cost("FightAction", default=3.5) == 3.5

    def test_action_class_fraction_returns_zero(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.action_class_fraction("FightAction") == 0.0

    def test_success_rate_returns_one(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.success_rate("FightAction(chicken)") == 1.0

    def test_action_effect_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.action_effect("FightAction(chicken)", "delta_gold") is None

    def test_goal_avg_cycles_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.goal_avg_cycles_to_satisfy("ReachCharLevel(5)") is None

    def test_recent_goal_cycles_returns_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.recent_goal_cycles("ReachCharLevel(5)") == []

    def test_observed_drop_rate_returns_none(self, tmp_db_path):
        """A DB fault yields no rate, so the caller keeps the static table."""
        store = LearningStore(db_path=tmp_db_path, character="x")
        _break_engine(store)
        assert store.observed_drop_rate("chicken", "feather") is None

    def test_skill_xp_per_cycle_all_returns_none(self, tmp_db_path):
        """The UNCONDITIONAL rate degrades like every other query: a DB fault
        returns None (no rate), which makes its caller decline to price a skill
        gate rather than invent one."""
        store = LearningStore(db_path=tmp_db_path, character="x")
        _break_engine(store)
        assert store.skill_xp_per_cycle_all("alchemy") is None

    def test_skill_grind_rate_returns_none(self, tmp_db_path):
        """Same contract for the estimator that replaced it at the pricing seam.
        Distinct from `0.0`: a DB fault is IGNORANCE, and the caller may fall
        back to the fleet on it, where a real `0.0` is evidence it must not."""
        store = LearningStore(db_path=tmp_db_path, character="x")
        _break_engine(store)
        assert store.skill_grind_rate("gearcrafting") is None
        assert store.fleet_skill_grind_rate("gearcrafting") is None

    def test_skill_xp_per_cycle_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.skill_xp_per_cycle("alchemy") is None

    def test_sample_count_returns_zero(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.sample_count("FightAction(chicken)") == 0

    def test_win_count_returns_zero(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.win_count("Fight(chicken)") == 0

    def test_goal_stats_returns_empty_rollup(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        stats = store.goal_stats("ReachCharLevel(5)")
        assert stats.goal_repr == "ReachCharLevel(5)"
        assert stats.sample_count == 0
        assert stats.avg_cycles_to_satisfy is None
        assert stats.satisfaction_rate == 0.0

    def test_set_blocker_swallows_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        # No exception raised; nothing persisted.
        store.set_blocker("bank", unlock_monster="skeleton", required_level=10)

    def test_get_blocker_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.get_blocker("bank") is None

    def test_delete_blocker_swallows_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        store.delete_blocker("bank")

    def test_record_skill_max_xp_swallows_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        store.record_skill_max_xp("alchemy", level=5, max_xp=1000)

    def test_skill_max_xp_observations_returns_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.skill_max_xp_observations("alchemy") == {}

    def test_record_task_reward_value_swallows_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        store.record_task_reward_value(42.0)

    def test_task_reward_values_return_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.task_reward_sample_count() == 0
        assert store.mean_task_reward_value(default=7.0) == 7.0

    def test_get_learned_int_returns_default_on_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.get_learned_int("task_exchange_min_coins", default=3) == 3

    def test_set_learned_int_swallows_error(self, tmp_db_path, capsys):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        # No exception; best-effort write degrades to a logged message.
        store.set_learned_int("task_exchange_min_coins", 9)
        assert "set_learned_int" in capsys.readouterr().out

    def test_hp_healed_per_fight_returns_none_on_db_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.hp_healed_per_fight("red_slime", lambda c: 0) is None


class TestLearnedInt:
    def test_round_trip_and_update(self, tmp_db_path):
        """First set inserts; a second set on the same key updates the existing
        row in place (lines 522-524) rather than inserting a duplicate."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        assert store.get_learned_int("min_coins", default=1) == 1  # absent -> default
        store.set_learned_int("min_coins", 4)
        assert store.get_learned_int("min_coins", default=1) == 4
        store.set_learned_int("min_coins", 9)  # update existing row
        assert store.get_learned_int("min_coins", default=1) == 9
        store.close()

    def test_learned_int_is_per_character(self, tmp_db_path):
        a = LearningStore(db_path=tmp_db_path, character="alice")
        a.set_learned_int("min_coins", 5)
        b = LearningStore(db_path=tmp_db_path, character="bob")
        # bob has no row for this key -> default.
        assert b.get_learned_int("min_coins", default=0) == 0
        assert a.get_learned_int("min_coins", default=0) == 5
        a.close()
        b.close()


def test_parse_skill_xp_value_none_returns_zero():
    """A None raw delta-json yields 0 without attempting to parse (line 40-41)."""
    assert _parse_skill_xp_value(None, "mining") == 0


class TestCraftYield:
    def test_record_and_read_craft_yield(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        assert store.observed_craft_yield("potion") is None
        store.record_craft_yield("potion", quantity=2, xp=15)
        assert store.observed_craft_yield("potion") == (2, 15)
        store.record_craft_yield("potion", quantity=3, xp=20)   # last write wins
        assert store.observed_craft_yield("potion") == (3, 20)
        store.close()

    def test_record_craft_yield_stores_the_skill_level_it_was_measured_at(
            self, tmp_db_path):
        """The XP a craft pays FALLS as the skill rises (the server's
        level_penalty term), so a yield row without the level it was measured
        at is "131 at some level" and goes stale silently. Recording the level
        is what makes the row usable as a fit input -- see
        docs/superpowers/specs/2026-08-15-observed-craft-xp-numerator-design.md.
        """
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        store.record_craft_yield("potion", quantity=2, xp=118, skill_level=7)
        assert store.observed_craft_xp("potion") == (118, 2, 7)
        store.close()

    def test_a_yield_recorded_without_a_level_reads_back_as_unknown(
            self, tmp_db_path):
        """`skill_level` is optional, and the 62 rows already in the wild have
        none. They must read back as None rather than as a level, so the fit
        can exclude them instead of treating them as measured at level 0."""
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        store.record_craft_yield("potion", quantity=1, xp=53)
        assert store.observed_craft_xp("potion") == (53, 1, None)
        store.close()

    def test_relevelling_the_same_item_overwrites_the_level_too(
            self, tmp_db_path):
        """Last write wins on the whole row. A stale level surviving a rewrite
        would be worse than no level: it would attribute a fresh XP figure to
        the level the character had the FIRST time it crafted the item."""
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        store.record_craft_yield("potion", quantity=1, xp=131, skill_level=5)
        store.record_craft_yield("potion", quantity=1, xp=118, skill_level=9)
        assert store.observed_craft_xp("potion") == (118, 1, 9)
        store.close()

    def test_observed_craft_xp_is_none_for_an_item_never_crafted(self, tmp_db_path):
        """Distinct from "crafted, but at an unknown level": None means no
        observation exists at all, and a fit must not confuse the two."""
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        assert store.observed_craft_xp("never_made") is None
        store.close()

    def test_observed_craft_xp_degrades_to_none_on_db_error(self, tmp_db_path):
        """Best-effort contract, same as every other query on this store: a
        DB-layer fault reads as "no observation", never as an exception."""
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        store.record_craft_yield("potion", quantity=1, xp=53, skill_level=5)
        _break_engine(store)
        assert store.observed_craft_xp("potion") is None
        store.close()

    def test_an_old_craft_yield_table_gains_the_level_column_on_open(self, tmp_path):
        """A pre-2026-08-15 cache has craft_yield WITHOUT skill_level. Opening
        the store must ALTER it in, preserving the rows already there — the
        `consumables_expended_json` incident is what this mirrors: a column
        that shipped in the model without a matching one-shot ALTER made every
        write fail on pre-existing DBs, and learning went silently dead."""
        import sqlite3
        db_path = str(tmp_path / "old_yield.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE craft_yield (
                character TEXT NOT NULL, item_code TEXT NOT NULL,
                quantity INTEGER NOT NULL, xp INTEGER NOT NULL,
                PRIMARY KEY (character, item_code)
            )
        """)
        conn.execute("INSERT INTO craft_yield VALUES ('Robby','life_ring',1,403)")
        conn.commit()
        conn.close()

        store = LearningStore(db_path=db_path, character="Robby")
        # Close this one explicitly: an unclosed sqlite3.Connection is GC'd
        # later and its unraisable warning is attributed to whatever test is
        # running THEN, not to this one. That misattribution has cost this
        # project real debugging time.
        check = sqlite3.connect(db_path)
        try:
            cols = {r[1] for r in check.execute("PRAGMA table_info(craft_yield)")}
        finally:
            check.close()
        assert "skill_level" in cols
        # The pre-existing row survives and reads back as level-unknown.
        assert store.observed_craft_xp("life_ring") == (403, 1, None)
        store.close()

    def test_craft_yield_is_per_character(self, tmp_db_path):
        a = LearningStore(db_path=tmp_db_path, character="alice")
        b = LearningStore(db_path=tmp_db_path, character="bob")
        a.record_craft_yield("bar", quantity=2, xp=10)
        assert a.observed_craft_yield("bar") == (2, 10)
        assert b.observed_craft_yield("bar") is None
        a.close()
        b.close()

    def test_record_craft_yield_swallows_error(self, tmp_db_path, capsys):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        store.record_craft_yield("potion", quantity=1, xp=5)
        assert "record_craft_yield" in capsys.readouterr().out

    def test_observed_craft_yield_returns_none_on_error(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.observed_craft_yield("potion") is None


def test_cycle_consumables_expended_json_roundtrips(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "c.db"), character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-07-02T00:00:00+00:00", session_id="s", cycle_index=0,
        character="hero", outcome="ok", action_repr="Fight(red_slime)",
        action_class="FightAction", consumables_expended_json='{"small_health_potion": 2}'))
    with SqlSession(store._engine) as s:
        row = next(iter(s.exec(select(Cycle).where(Cycle.action_repr == "Fight(red_slime)"))))
    assert row.consumables_expended_json == '{"small_health_potion": 2}'
    store.close()


def test_cycle_consumables_expended_json_defaults_empty(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "c.db"), character="hero")
    store.start_session()
    store.record_cycle(Cycle(ts="2026-07-02T00:00:01+00:00", session_id="s",
        cycle_index=1, character="hero", outcome="ok", action_repr="Rest",
        action_class="RestAction"))
    with SqlSession(store._engine) as s:
        row = next(iter(s.exec(select(Cycle).where(Cycle.action_repr == "Rest"))))
    assert row.consumables_expended_json == "{}"
    store.close()


def _restore_of(code: str) -> int:
    return {"small_health_potion": 30}.get(code, 0)


def test_hp_healed_per_fight_none_below_warmup(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "h.db"), character="hero")
    store.start_session()
    for i in range(4):  # < WARMUP_MIN_SAMPLES
        store.record_cycle(Cycle(ts=f"2026-07-02T00:00:0{i}+00:00", session_id="s",
            cycle_index=i, character="hero", outcome="ok", action_repr="Fight(red_slime)",
            action_class="FightAction", consumables_expended_json='{"small_health_potion": 2}'))
    assert store.hp_healed_per_fight("red_slime", _restore_of) is None
    store.close()


def test_hp_healed_per_fight_means_over_wins(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "h.db"), character="hero")
    store.start_session()
    # 5 wins: three consumed 2 potions (60 HP), two consumed 0 (0 HP) -> mean 36.0
    exps = ['{"small_health_potion": 2}'] * 3 + ["{}"] * 2
    for i, e in enumerate(exps):
        store.record_cycle(Cycle(ts=f"2026-07-02T00:00:1{i}+00:00", session_id="s",
            cycle_index=i, character="hero", outcome="ok", action_repr="Fight(red_slime)",
            action_class="FightAction", consumables_expended_json=e))
    # a loss must be ignored
    store.record_cycle(Cycle(ts="2026-07-02T00:00:20+00:00", session_id="s",
        cycle_index=9, character="hero", outcome="error:fight_lost",
        action_repr="Fight(red_slime)", action_class="FightAction",
        consumables_expended_json='{"small_health_potion": 5}'))
    assert store.hp_healed_per_fight("red_slime", _restore_of) == 36.0
    store.close()


# --- concurrent first open: the `play --all --learn` shape -------------------


def _open_worker(db_path: str, character: str, barrier: object, out: object) -> None:
    """Module-level so it is picklable by multiprocessing's spawn start method.

    Waits on `barrier` BEFORE constructing the store, so every child runs
    `LearningStore.__init__`'s schema work against the same file at the same
    moment. Nothing is caught: a store that cannot survive a concurrent
    sibling must surface as a non-zero exit code, exactly as it did in
    production on the coordination DB.
    """
    barrier.wait()
    store = LearningStore(db_path=db_path, character=character)
    try:
        out.put(character)
    finally:
        store.close()


def _race_open(db_path: str) -> None:
    """Open `db_path` from five processes at once; every one must survive."""
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    names = ["HAL", "C3P0", "R2D2", "Robby", "KITT"]
    barrier = ctx.Barrier(len(names))
    procs = [ctx.Process(target=_open_worker, args=(db_path, n, barrier, queue)) for n in names]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"a child died opening the learning DB: {p.exitcode}"
    assert sorted(queue.get() for _ in names) == sorted(names)


def test_concurrent_first_open_of_a_new_learning_db_creates_the_schema_once(tmp_path):
    """`play --all --learn` hands every child the SAME learning DB path, so the
    coordination DB's `create_all` race applies here verbatim. It was invisible
    for as long as this store shipped only because, before the multi-character
    supervisor existed, exactly ONE process ever opened this file."""
    db_path = str(tmp_path / "fresh.db")
    assert not os.path.exists(db_path)
    _race_open(db_path)
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "cycles" in tables


def test_concurrent_open_of_a_legacy_db_migrates_the_column_once(tmp_path):
    """The second half of the same defect: the column migrations are also a
    probe-then-write pair (`PRAGMA table_info` then `ALTER TABLE`), so five
    children on a pre-migration DB would all decide to ALTER and the losers
    would die on "duplicate column name".

    The fixture is a COMPLETE modern schema with only the two migrated columns
    dropped, so `create_all` finds every table present and issues nothing —
    which leaves the migration as the only thing the children can race on."""
    db_path = str(tmp_path / "legacy.db")
    LearningStore(db_path=db_path, character="setup").close()
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE cycles DROP COLUMN delta_skill_xp_json")
    conn.execute("ALTER TABLE cycles DROP COLUMN consumables_expended_json")
    conn.commit()
    conn.close()

    _race_open(db_path)

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cycles)")]
    conn.close()
    assert cols.count("delta_skill_xp_json") == 1
    assert cols.count("consumables_expended_json") == 1


def test_observed_drop_rate_survives_unusable_rows(tmp_db_path):
    """Rows that carry no usable drop record must count as a KILL WITH NO DROP,
    not be skipped.

    Skipping them is the same error `skill_xp_per_cycle` makes with zero-xp
    cycles: it shrinks the denominator to the population that succeeded and
    reports a rate far above the truth. A null, a malformed blob, and a
    non-object payload are all evidence of a kill that dropped nothing here."""
    store = LearningStore(db_path=tmp_db_path, character="x")
    store.start_session()
    payloads = [None, "not json at all", "[1, 2, 3]", json.dumps({"feather": 1})]
    for i in range(MIN_DROP_KILLS):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i % 60:02d}+00:00", session_id="s",
            cycle_index=i, character="x", outcome="ok",
            action_repr="Fight(chicken)",
            drops_json=payloads[i % len(payloads)],
        ))
    rate = store.observed_drop_rate("chicken", "feather")
    store.end_session(exit_reason="normal")
    store.close()
    # Only the rows carrying a real feather count in the numerator; the null, the
    # malformed blob and the non-object payload are kills that dropped nothing
    # and stay in the DENOMINATOR. Computed rather than hardcoded, so the
    # expectation follows MIN_DROP_KILLS instead of drifting when it changes.
    feathers = sum(1 for i in range(MIN_DROP_KILLS) if i % 4 == 3)
    assert rate == pytest.approx(feathers / MIN_DROP_KILLS)
    assert 0 < rate < 1


class TestForcedRecoveryAttribution:
    """A grind's Rests are filed under `RestoreHP`, not under the grind.

    Measured on 36455 live cycles: `GrindCharacterXP(green_slime)` is 100.0%
    FightAction and 0% Rest, while `RestoreHP` holds 5668 Rests. So a rate averaged
    over the grind's own rows is XP per FIGHT, while the predicted branch it is
    ranked against is XP per LOOP ACTION -- and every monster with observations beat
    every monster without by the whole loop factor.
    """

    @staticmethod
    def _cycle(store, idx, goal, action, xp=0):
        store.record_cycle(Cycle(
            ts=f"2026-08-11T00:00:{idx:02d}+00:00", session_id="x", cycle_index=idx,
            character="hero", selected_goal=goal, action_class=action, delta_xp=xp,
            level=5, outcome="ok",
        ))

    def test_a_grind_owns_the_rests_its_own_fighting_forced(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        grind = "GrindCharacterXP(slime)"
        for i, (goal, act, xp) in enumerate([
                (grind, "FightAction", 10), (grind, "FightAction", 10),
                ("RestoreHP", "RestAction", 0),
                (grind, "FightAction", 10), ("RestoreHP", "RestAction", 0)]):
            self._cycle(store, i, goal, act, xp)
        rows = store.recent_goal_cycles(grind, window=100)
        store.close()
        assert len(rows) == 5, [(r.selected_goal, r.action_class) for r in rows]
        assert sum(r.delta_xp or 0 for r in rows) == 30
        # 30 XP over 5 cycles = 6 per LOOP ACTION, not 10 per FIGHT. That factor is
        # the whole defect: it is what the predicted branch is compared against.
        assert sum(r.delta_xp or 0 for r in rows) / len(rows) == 6.0

    def test_a_rest_forced_by_another_goal_is_not_claimed(self, tmp_db_path):
        """The attribution must not sweep up recovery it did not cause, or the fix
        becomes the same error pointed the other way."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        grind = "GrindCharacterXP(slime)"
        self._cycle(store, 0, grind, "FightAction", 10)
        self._cycle(store, 1, "GatherMaterials(wool)", "GatherAction", 0)
        self._cycle(store, 2, "RestoreHP", "RestAction", 0)
        rows = store.recent_goal_cycles(grind, window=100)
        store.close()
        assert [r.selected_goal for r in rows] == [grind]

    def test_recovery_asked_about_itself_owns_only_its_own(self, tmp_db_path):
        """Without this the same cycle counts into two rates at once."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._cycle(store, 0, "GrindCharacterXP(slime)", "FightAction", 10)
        self._cycle(store, 1, "RestoreHP", "RestAction", 0)
        rows = store.recent_goal_cycles("RestoreHP", window=100)
        store.close()
        assert [r.selected_goal for r in rows] == ["RestoreHP"]


class TestSkillGrindRate:
    """The rate that prices a skill-gated craft, measured over the grind's OWN
    cycles rather than over the last 100 cycles of whatever the character
    happened to be doing."""

    @staticmethod
    def _grind_cycle(i: int, char: str, skill: str, xp: int) -> Cycle:
        return Cycle(
            ts=f"2026-08-18T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character=char, outcome="ok",
            action_repr=f"LevelSkill({skill}->10)",
            delta_skill_xp_json=json.dumps({skill: xp}),
        )

    @staticmethod
    def _other_cycle(i: int, char: str) -> Cycle:
        return Cycle(
            ts=f"2026-08-18T01:00:{i % 60:02d}+00:00", session_id="s",
            cycle_index=i, character=char, outcome="ok",
            action_repr="Fight(pig)", delta_skill_xp_json=json.dumps({}),
        )

    def test_an_empty_store_has_no_rate_under_either_estimator(self, tmp_db_path):
        """No cycles at all is IGNORANCE, not a rate of zero — under both the
        retired estimator and its replacement. `_gated_craft_option` reads the
        difference: None may fall back to the fleet, 0.0 may not."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            assert store.skill_xp_per_cycle_all("gearcrafting") is None
            assert store.skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_window_of_other_work_does_not_dilute_the_rate(self, tmp_db_path):
        """THE LIVE BUG, pinned. Every character in the live DB reads 0.0 from
        `skill_xp_per_cycle_all` for every crafting skill, because their last 100
        cycles are all fights. The grind's own cycles still say 5.0, and they were
        in the same table the whole time."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(10):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting",
                                                     50 if i == 0 else 0))
            for i in range(10, 210):
                store.record_cycle(self._other_cycle(i, "c"))
            assert store.skill_xp_per_cycle_all("gearcrafting") == 0.0
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_conditional_mean_and_the_grind_rate_must_differ(self, tmp_db_path):
        """THE 41x TRAP, pinned on one fixture.

        `skill_xp_per_cycle` drops the zero-xp gathering cycles a grind is mostly
        made of and reports the paying cycle's figure as if it were the rate — 54.0
        against a true 1.08 on R2D2, the 50x under-pricing that committed the bot
        to 207 LevelSkill actions over 4.5 hours for +270 skill xp and ZERO
        character xp (2026-08-08). The grind rate keeps those cycles in the
        denominator. If these two ever agree, this fix has become the bug it was
        written next to."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(10):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting",
                                                     50 if i == 0 else 0))
            assert store.skill_xp_per_cycle("gearcrafting") == 50.0
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_grind_that_gained_nothing_reports_zero_not_none(self, tmp_db_path):
        """EVIDENCE, and it must be distinguishable from ignorance: the caller
        declines on 0.0 and may fall back to the fleet on None."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 0))
            assert store.skill_grind_rate("gearcrafting") == 0.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_skill_never_ground_reports_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "c", "mining", 40))
            assert store.skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_different_skills_grind_is_not_evidence_about_this_one(self, tmp_db_path):
        """A mining grind gains woodcutting xp as a side effect — measured live,
        1,491 woodcutting xp inside the gearcrafting grind. Those cycles say
        nothing about how fast a WOODCUTTING grind goes."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(Cycle(
                    ts=f"2026-08-18T00:00:{i:02d}+00:00", session_id="s",
                    cycle_index=i, character="c", outcome="ok",
                    action_repr="LevelSkill(mining->10)",
                    delta_skill_xp_json=json.dumps({"woodcutting": 60})))
            assert store.skill_grind_rate("woodcutting") is None
            assert store.skill_grind_rate("mining") == 0.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_window_counts_grind_cycles_not_all_cycles(self, tmp_db_path):
        """THE ENTIRE DIFFERENCE from `skill_xp_per_cycle_all`: the LIMIT falls on
        rows that already matched the grind, so a grind in progress feeds the
        estimate that prices it and cannot be emptied by other work."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(2):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 100))
            for i in range(2, 12):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting", window=10) == 10.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_target_level_other_than_ten_is_the_same_evidence(self, tmp_db_path):
        """`LevelSkill.__repr__` renders `LevelSkill(<skill>-><target>)`, so only
        the target varies. A `->5` grind and a `->10` grind are the same evidence
        about how fast this character gains xp in this skill, and matching the
        exact string would silently drop half of it."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i, target in enumerate((5, 10, 15, 20)):
                store.record_cycle(Cycle(
                    ts=f"2026-08-18T00:00:{i:02d}+00:00", session_id="s",
                    cycle_index=i, character="c", outcome="ok",
                    action_repr=f"LevelSkill(gearcrafting->{target})",
                    delta_skill_xp_json=json.dumps({"gearcrafting": 8})))
            assert store.skill_grind_rate("gearcrafting") == 8.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    @staticmethod
    def _seed_sibling(db_path: str, skill: str, xp: int, n: int = 5) -> None:
        """Write a sibling's grind cycles through the sibling's OWN store.

        `record_cycle` stamps `cycle.character` with the store's character, so a
        row cannot be attributed to another name through this store — which is
        the invariant that makes the per-character scoping below meaningful."""
        other = LearningStore(db_path=db_path, character="other")
        other.start_session()
        try:
            for i in range(n):
                other.record_cycle(Cycle(
                    ts=f"2026-08-18T02:00:{i:02d}+00:00", session_id="s",
                    cycle_index=i, character="other", outcome="ok",
                    action_repr=f"LevelSkill({skill}->10)",
                    delta_skill_xp_json=json.dumps({skill: xp})))
        finally:
            other.end_session(exit_reason="normal")
            other.close()

    def test_the_rate_is_scoped_to_this_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            self._seed_sibling(tmp_db_path, "gearcrafting", 80)
            assert store.skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_fleet_rate_pools_every_character(self, tmp_db_path):
        """A character that has never ground a skill can still be told what the
        grind costs, by the siblings who have — same server, same recipes, same
        workshops."""
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            self._seed_sibling(tmp_db_path, "gearcrafting", 80)
            assert store.skill_grind_rate("gearcrafting") is None
            assert store.fleet_skill_grind_rate("gearcrafting") == 80.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_fleet_rate_is_none_when_nobody_has_ground_it(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            assert store.fleet_skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_malformed_delta_row_counts_as_zero_not_as_absent(self, tmp_db_path):
        """One bad row must never crash the average, and it stays in the
        DENOMINATOR — that is precisely the population the conditional mean
        drops."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            store.record_cycle(Cycle(
                ts="2026-08-18T00:00:00+00:00", session_id="s", cycle_index=0,
                character="c", outcome="ok",
                action_repr="LevelSkill(gearcrafting->10)",
                delta_skill_xp_json="not json"))
            store.record_cycle(self._grind_cycle(1, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_negative_delta_does_not_credit_the_rate(self, tmp_db_path):
        """A level reset writes a negative delta — measured live, -2,185 mining xp
        inside the gearcrafting grind. Clamped to 0, matching
        `skill_xp_per_cycle_all`."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            store.record_cycle(self._grind_cycle(0, "c", "gearcrafting", -100))
            store.record_cycle(self._grind_cycle(1, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()


def test_grind_action_prefix_is_the_repr_LevelSkill_writes():
    """Matching on the prefix is only sound if it is the prefix the action
    actually renders. `LevelSkill.__repr__` is `LevelSkill({skill}->{target})`."""
    assert grind_action_prefix("gearcrafting") == "LevelSkill(gearcrafting->"
    assert repr(LevelSkill(skill="gearcrafting", target_level=10)).startswith(
        grind_action_prefix("gearcrafting"))


class TestFleetSupplyRequestCycles:
    """The MEASURED price of the `sibling:` unlock in `acquisition_cost`.

    It is read off history rather than chosen because the alternative was a
    constant, and a modelling constant nothing pins is proof-inert however green
    the gate (`feedback_gate_green_does_not_pin_a_constant`).
    """

    @staticmethod
    def _supply_cycles(db: str, goal: str, character: str, n: int) -> None:
        """`record_cycle` stamps the STORE's character onto every row, so a
        producer is a store — which is also how it works live: one `play --all`
        child, one `LearningStore`, one character."""
        store = LearningStore(db_path=db, character=character)
        store.start_session()
        for i in range(n):
            store.record_cycle(Cycle(
                ts=f"2026-08-20T00:00:{i:02d}+00:00", session_id="s",
                cycle_index=i, character=character, outcome="ok",
                selected_goal=goal))
        store.close()

    def test_median_producer_cycles_per_request(self, tmp_db_path):
        """Grouped per (request, producer) pair — the same shape `_grind_rate`
        reads `LevelSkill(<skill>-><level>)` cycles."""
        self._supply_cycles(tmp_db_path, "SupplyBank(iron_orex80)", "HAL", 10)
        self._supply_cycles(tmp_db_path, "SupplyBank(spruce_woodx60)", "R2D2", 20)
        self._supply_cycles(tmp_db_path, "SupplyBank(copper_orex10)", "Lor", 30)
        store = LearningStore(db_path=tmp_db_path, character="Robby")

        assert store.fleet_supply_request_cycles() == 20.0
        store.close()

    def test_median_not_mean_so_one_pathological_request_cannot_price_the_rest(
            self, tmp_db_path):
        """Measured live: a 239-cycle request against a median of 15. A mean would
        let that single request price every future one."""
        self._supply_cycles(tmp_db_path, "SupplyBank(ax1)", "HAL", 5)
        self._supply_cycles(tmp_db_path, "SupplyBank(bx1)", "R2D2", 6)
        self._supply_cycles(tmp_db_path, "SupplyBank(cx1)", "Lor", 239)
        store = LearningStore(db_path=tmp_db_path, character="Robby")

        assert store.fleet_supply_request_cycles() == 6.0, "mean would be ~83"
        store.close()

    def test_the_same_request_served_by_two_producers_counts_twice(
            self, tmp_db_path):
        """Live 2026-08-08, before `SupplyClaim`: `SupplyBank(spruce_woodx60)` was
        served SIMULTANEOUSLY by R2D2 (225 gathers) and Robby (231). Each is a
        real producer cost, so the PAIR — not the request — is the unit."""
        self._supply_cycles(tmp_db_path, "SupplyBank(spruce_woodx60)", "R2D2", 4)
        self._supply_cycles(tmp_db_path, "SupplyBank(spruce_woodx60)", "Robby", 8)
        store = LearningStore(db_path=tmp_db_path, character="X")

        assert store.fleet_supply_request_cycles() == 6.0, "median of [4, 8]"
        store.close()

    def test_only_supply_requests_count(self, tmp_db_path):
        """No observation, no honest price — and `_sibling_craft_option` withholds
        the route rather than defaulting."""
        self._supply_cycles(tmp_db_path, "GatherMaterials(iron_ore, {iron_ore:8})",
                            "HAL", 10)
        store = LearningStore(db_path=tmp_db_path, character="Robby")

        assert store.fleet_supply_request_cycles() is None
        store.close()

    def test_swallows_db_error_and_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="Robby")
        _break_engine(store)
        assert store.fleet_supply_request_cycles() is None
        store.close()


class TestTheHottestReadIsIndexed:
    """`win_count` / `sample_count` are the hottest reads in the codebase, and
    they went quadratic-ish as the store grew.

    Measured 2026-08-21 on the live 66,359-row store: `is_winnable`'s
    learned-loss veto and monotonic-win inference issued 64,738 `win_count` calls
    in ONE `plan_from_state`, 5,902 of them cache misses, at ~6.5ms each — 40 of
    the plan's 86 seconds. Planner timeouts went from 0.0% of cycles in early
    August to 14.1%, purely because the table got bigger.

    Two causes, both here: SQLite could only use `ix_cycles_character`, so every
    call scanned one character's ENTIRE history and filtered `action_repr`
    row-by-row; and the count was `len(list(...))`, which ships every matching row
    id to Python to measure its length. Composite index + `COUNT(*)`: 6.47ms ->
    0.29ms, a 22x cut.
    """

    @staticmethod
    def _seed(store: LearningStore, n: int) -> None:
        store.start_session()
        for i in range(n):
            store.record_cycle(Cycle(
                ts=f"2026-08-21T00:00:{i % 60:02d}+00:00", session_id="s",
                cycle_index=i, character="hero",
                outcome="ok" if i % 2 else "error:fight_lost",
                action_repr="Fight(pig)" if i % 3 else "Fight(cow)"))

    def test_the_composite_index_exists(self, tmp_db_path):
        """Without `(character, action_repr)` SQLite falls back to the
        character-only index and scans the whole history for that character."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        with SqlSession(store._engine) as s:
            names = {r[0] for r in s.execute(text(
                "select name from sqlite_master where type='index' "
                "and tbl_name='cycles'")).all()}
        store.close()
        assert "ix_cycles_char_action" in names

    def test_the_query_plan_actually_uses_it(self, tmp_db_path):
        """The index existing is not the same as the planner choosing it — this
        asserts the thing that was actually slow."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        with SqlSession(store._engine) as s:
            plan = " ".join(str(r) for r in s.execute(text(
                "explain query plan select count(*) from cycles "
                "where character='hero' and action_repr='Fight(pig)'")).all())
        store.close()
        assert "ix_cycles_char_action" in plan, plan

    def test_a_PRE_EXISTING_db_gains_the_index(self, tmp_path):
        """THE ONE THAT MATTERS. `SQLModel.metadata.create_all` adds missing
        TABLES and their indexes; it does not add an index to a table that
        already exists. Without a one-shot migration the fix would be inert on
        every store that has rows — which is the only place the 66,359 rows are,
        and the only place the slowness was.

        Verified before writing the migration: opening the live store's copy with
        the model change alone left the index absent.
        """
        db = str(tmp_path / "legacy.db")
        first = LearningStore(db_path=db, character="hero")
        self._seed(first, 5)
        first.close()
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("drop index if exists ix_cycles_char_action")
            conn.commit()
            gone = {r[0] for r in conn.execute(
                "select name from sqlite_master where type='index' "
                "and tbl_name='cycles'")}
        assert "ix_cycles_char_action" not in gone, "precondition: index removed"

        reopened = LearningStore(db_path=db, character="hero")
        with SqlSession(reopened._engine) as s:
            names = {r[0] for r in s.execute(text(
                "select name from sqlite_master where type='index' "
                "and tbl_name='cycles'")).all()}
        reopened.close()

        assert "ix_cycles_char_action" in names

    def test_win_count_and_sample_count_still_answer_correctly(self, tmp_db_path):
        """The speedup must not change the numbers. 30 rows: 20 `Fight(pig)`
        (i % 3 != 0), of which the odd-i ones are wins."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        self._seed(store, 30)

        assert store.sample_count("Fight(pig)") == sum(
            1 for i in range(30) if i % 3)
        assert store.win_count("Fight(pig)") == sum(
            1 for i in range(30) if i % 3 and i % 2)
        assert store.sample_count("Fight(never)") == 0
        assert store.win_count("Fight(never)") == 0
        store.close()

    def test_they_count_only_this_characters_rows(self, tmp_db_path):
        """The character predicate is half the index and half the meaning: a
        sibling's losses must not veto this character's fight."""
        hero = LearningStore(db_path=tmp_db_path, character="hero")
        self._seed(hero, 30)
        other = LearningStore(db_path=tmp_db_path, character="other")
        self._seed(other, 30)

        assert other.sample_count("Fight(pig)") == sum(1 for i in range(30) if i % 3)
        assert hero.sample_count("Fight(pig)") == sum(1 for i in range(30) if i % 3)
        hero.close()
        other.close()
