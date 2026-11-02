"""Tests for Phase G-B projections module."""

import json

from sqlmodel import Session

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import (
    TASKS_COIN_CODE,
    Yield,
    expected_yield_per_cycle,
)
from artifactsmmo_cli.ai.learning.store import LearningStore


def _make_cycle(
    cycle_index: int,
    selected_goal: str,
    *,
    delta_xp: int = 0,
    delta_gold: int = 0,
    task_progress: int = 0,
    cycles_to_satisfy: int | None = None,
    delta_skill_xp_json: str = "{}",
    drops_json: str | None = None,
    level: int | None = 1,
) -> dict:
    """Kwargs for Cycle(...) — keep a single template so all tests stay consistent."""
    return dict(
        ts=f"2026-05-18T00:{cycle_index:02d}:00Z",
        session_id="s1",
        cycle_index=cycle_index,
        character="hero",
        selected_goal=selected_goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        level=level,
        delta_xp=delta_xp,
        delta_gold=delta_gold,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=task_progress,
        task_total=10,
        delta_skill_xp_json=delta_skill_xp_json,
        drops_json=drops_json,
        cycles_to_satisfy=cycles_to_satisfy,
    )


def _populate(store: LearningStore, cycles: list[dict]) -> None:
    """Insert raw Cycle rows directly (bypassing _ensure_session_row dance)."""
    store.start_session()
    with Session(store._engine) as s:
        # Force the session row to exist for FK-ish referential clarity.
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
        for kw in cycles:
            kw_with_session = dict(kw)
            kw_with_session["session_id"] = store._session_id
            s.add(Cycle(**kw_with_session))
        s.commit()


class TestParseHelpers:
    """Coverage for _parse_skill_xp and _parse_drops error/non-dict paths."""

    def test_non_dict_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 79: valid JSON but non-dict (e.g. list) → returns {}."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_skill_xp_json="[1, 2]") for i in range(3)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {}

    def test_malformed_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 81-82: invalid JSON in delta_skill_xp_json → swallowed → empty."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_skill_xp_json="{broken") for i in range(3)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {}

    def test_non_dict_drops_json_yields_zero_coins(self, tmp_path):
        """Line 93: valid JSON but non-dict drops_json → zero tasks_coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "CompleteTask", drops_json='["item"]') for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0

    def test_malformed_drops_json_yields_zero_coins(self, tmp_path):
        """Lines 95-96: invalid JSON in drops_json → swallowed → zero coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "CompleteTask", drops_json="{broken") for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0


class TestYieldType:
    def test_default_empty_yield(self):
        y = Yield()
        assert y.char_xp == 0.0
        assert y.skill_xp == {}
        assert y.gold == 0.0
        assert y.tasks_coins == 0.0
        assert y.sample_count == 0


class TestExpectedYieldPerCycle:
    def test_empty_store_returns_empty_yield(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 0
        assert y.char_xp == 0.0

    def test_aggregates_char_xp_and_gold(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_xp=10, delta_gold=2) for i in range(5)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 5
        assert y.char_xp == 10.0
        assert y.gold == 2.0

    def test_aggregates_skill_xp_from_json(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)",
                        delta_skill_xp_json=json.dumps({"woodcutting": 4}))
            for i in range(4)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {"woodcutting": 4.0}

    def test_parses_tasks_coin_from_drops_json(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # 2 cycles drop 3 coins, 2 drop none → avg = 1.5
        rows = [
            _make_cycle(0, "CompleteTask", drops_json=json.dumps({TASKS_COIN_CODE: 3})),
            _make_cycle(1, "CompleteTask", drops_json=json.dumps({TASKS_COIN_CODE: 3})),
            _make_cycle(2, "CompleteTask"),
            _make_cycle(3, "CompleteTask"),
        ]
        _populate(store, rows)
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 1.5

    def test_ignores_other_goals(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(0, "PursueTask(x)", delta_xp=10),
            _make_cycle(1, "FarmMonster", delta_xp=100),
            _make_cycle(2, "PursueTask(x)", delta_xp=10),
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 2
        assert y.char_xp == 10.0
