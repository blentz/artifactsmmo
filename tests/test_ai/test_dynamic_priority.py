"""Tests for the G-F dynamic priority helper."""

from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.dynamic_priority import (
    CONFIDENCE_CAP_SAMPLES,
    DEFAULT_BONUS_WEIGHT,
    learned_priority_bonus,
)
from artifactsmmo_cli.ai.learning.models import Cycle, Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _seed(store: LearningStore, cycles: list[dict]) -> None:
    store.start_session()
    with Session(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
        for kw in cycles:
            kw_with = dict(kw)
            kw_with["session_id"] = store._session_id
            s.add(Cycle(**kw_with))
        s.commit()


def _cycle(idx: int, goal: str, *, delta_xp: int = 0) -> dict:
    return dict(
        ts=f"2026-05-18T00:{idx:02d}:00Z",
        cycle_index=idx,
        character="hero",
        selected_goal=goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        delta_xp=delta_xp,
        delta_hp=0,
        delta_gold=0,
        delta_inv_used=0,
        task_progress=0,
        task_total=0,
    )


class TestLearnedPriorityBonus:
    def test_zero_when_history_is_none(self):
        bonus = learned_priority_bonus("FarmItems", make_state(), GameData(), None)
        assert bonus == 0.0

    def test_zero_when_no_samples(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        bonus = learned_priority_bonus("FarmItems", make_state(), GameData(), store)
        store.close()
        assert bonus == 0.0

    def test_scales_with_observed_xp(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # 30 cycles at 5 char-XP each → scalar = 5 * 1 * (1+1) = 10; confidence
        # = 30/30 = 1.0; bonus = 10 * DEFAULT_BONUS_WEIGHT * 1.0 = 50.
        cycles = [_cycle(i, "FarmItems", delta_xp=5) for i in range(CONFIDENCE_CAP_SAMPLES)]
        _seed(store, cycles)
        bonus = learned_priority_bonus("FarmItems", make_state(level=1), GameData(), store)
        store.close()
        expected = 5.0 * 2.0 * DEFAULT_BONUS_WEIGHT * 1.0
        assert abs(bonus - expected) < 0.5

    def test_confidence_scales_partial_samples(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        half = CONFIDENCE_CAP_SAMPLES // 2
        cycles = [_cycle(i, "FarmItems", delta_xp=5) for i in range(half)]
        _seed(store, cycles)
        bonus = learned_priority_bonus("FarmItems", make_state(level=1), GameData(), store)
        store.close()
        # Confidence ~0.5 → bonus ~ half of fully-warm.
        full = 5.0 * 2.0 * DEFAULT_BONUS_WEIGHT
        assert abs(bonus - full * 0.5) < full * 0.1

    def test_zero_when_yield_non_positive(self, tmp_path):
        """Even with samples, a yield of zero gives zero bonus (no floor)."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [_cycle(i, "FarmItems", delta_xp=0) for i in range(CONFIDENCE_CAP_SAMPLES)]
        _seed(store, cycles)
        bonus = learned_priority_bonus("FarmItems", make_state(), GameData(), store)
        store.close()
        assert bonus == 0.0
