"""Tests for LearningStore."""

import os
import tempfile

import pytest
from sqlalchemy import text
from sqlmodel import Session as SqlSession
from sqlmodel import create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.store import LearningStore, _parse_skill_xp_value


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
        row = list(s.exec(select(Cycle).where(Cycle.action_repr == "Fight(red_slime)")))[0]
    assert row.consumables_expended_json == '{"small_health_potion": 2}'
    store.close()


def test_cycle_consumables_expended_json_defaults_empty(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "c.db"), character="hero")
    store.start_session()
    store.record_cycle(Cycle(ts="2026-07-02T00:00:01+00:00", session_id="s",
        cycle_index=1, character="hero", outcome="ok", action_repr="Rest",
        action_class="RestAction"))
    with SqlSession(store._engine) as s:
        row = list(s.exec(select(Cycle).where(Cycle.action_repr == "Rest")))[0]
    assert row.consumables_expended_json == "{}"
    store.close()
