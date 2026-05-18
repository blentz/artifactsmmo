"""Tests for Phase G-C scalarizer."""

import json

from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle, Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import Yield
from artifactsmmo_cli.ai.learning.scalarizer import (
    CHARACTER_XP_LEVEL_SCALAR,
    DEFAULT_COIN_VALUE_GOLD,
    GOLD_PER_XP_EQUIVALENT,
    SKILL_XP_BASELINE_WEIGHT,
    SKILL_XP_RELEVANT_TOOL_WEIGHT,
    expected_coin_value_with_prices,
    scalar_yield,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _gd_with_woodcutting_task() -> GameData:
    """GameData where the ash_plank task chains down to woodcutting."""
    gd = GameData()
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


class TestScalarYield:
    def test_char_xp_scales_with_level(self):
        gd = _gd_with_woodcutting_task()
        y = Yield(char_xp=5.0, sample_count=20)
        s1 = scalar_yield(y, make_state(level=1, task_code="ash_plank"), gd)
        s5 = scalar_yield(y, make_state(level=5, task_code="ash_plank"), gd)
        # (level+1) multiplier: 5 vs 2 → 2.5x
        assert s5 > s1
        assert abs(s5 / s1 - 3.0) < 0.01  # 6/2 = 3

    def test_relevant_skill_xp_beats_baseline(self):
        gd = _gd_with_woodcutting_task()
        # Woodcutting is active because the task chains through it.
        active = Yield(skill_xp={"woodcutting": 10.0}, sample_count=20)
        inactive = Yield(skill_xp={"mining": 10.0}, sample_count=20)
        state = make_state(level=1, task_code="ash_plank", task_type="items")
        s_active = scalar_yield(active, state, gd)
        s_inactive = scalar_yield(inactive, state, gd)
        assert s_active > s_inactive
        # Active uses SKILL_XP_RELEVANT_TOOL_WEIGHT=2.0; inactive uses 0.2.
        ratio = SKILL_XP_RELEVANT_TOOL_WEIGHT / SKILL_XP_BASELINE_WEIGHT
        assert abs(s_active / s_inactive - ratio) < 0.01

    def test_gold_contributes_proportionally(self):
        gd = _gd_with_woodcutting_task()
        y = Yield(gold=100.0, sample_count=20)
        s = scalar_yield(y, make_state(level=1, task_code=None), gd)
        # 100 gold / GOLD_PER_XP_EQUIVALENT(100) = 1.0 scalar units
        assert abs(s - 1.0) < 0.01

    def test_coins_use_default_value_without_store(self):
        gd = _gd_with_woodcutting_task()
        y = Yield(tasks_coins=2.0, sample_count=20)
        s = scalar_yield(y, make_state(level=1, task_code=None), gd, store=None)
        # 2 coins * DEFAULT_COIN_VALUE_GOLD(5) / GOLD_PER_XP_EQUIVALENT(100) = 0.10
        expected = 2.0 * DEFAULT_COIN_VALUE_GOLD / GOLD_PER_XP_EQUIVALENT
        assert abs(s - expected) < 0.01

    def test_empty_yield_returns_zero(self):
        gd = _gd_with_woodcutting_task()
        s = scalar_yield(Yield(), make_state(), gd)
        assert s == 0.0


class TestExpectedCoinValueWithPrices:
    def test_empty_history_returns_default(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD

    def test_aggregates_drop_value_per_coin(self, tmp_path):
        """One TaskExchange drops 6 apples worth 2 gold each. 12 gold / 3 coins = 4 gold/coin."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
            s.add(Cycle(
                ts="2026-05-18T00:00:01Z",
                session_id=store._session_id,
                cycle_index=0,
                character="hero",
                selected_goal="TaskExchange",
                action_repr="TaskExchange",
                action_class="TaskExchangeAction",
                outcome="ok",
                drops_json=json.dumps({"apple": 6}),
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert abs(v - 4.0) < 0.01

    def test_unknown_items_contribute_zero(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
            s.add(Cycle(
                ts="2026-05-18T00:00:01Z",
                session_id=store._session_id,
                cycle_index=0,
                character="hero",
                selected_goal="TaskExchange",
                action_repr="TaskExchange",
                action_class="TaskExchangeAction",
                outcome="ok",
                drops_json=json.dumps({"unknown_artifact": 1}),
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        # No known sell price → 0 gold / 3 coins = 0
        assert v == 0.0


class TestWeightConstants:
    """Document the weight relationships callers depend on."""

    def test_relevant_skill_outranks_baseline(self):
        assert SKILL_XP_RELEVANT_TOOL_WEIGHT > SKILL_XP_BASELINE_WEIGHT

    def test_char_xp_scalar_is_one(self):
        # If this changes, every absolute scalar in callers shifts. Make
        # the dependency explicit.
        assert CHARACTER_XP_LEVEL_SCALAR == 1.0
