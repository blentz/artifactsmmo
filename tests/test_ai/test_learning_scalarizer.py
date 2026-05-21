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
        """One exchange received 6 apples worth 2 gold; coins spent derived from
        the inventory delta. received=6, delta_inv_used = 6 - 6 spent = 0, so
        spent=6 -> 12 gold / 6 coins = 2 gold/coin."""
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
                delta_inv_used=0,  # +6 apples, -6 coins
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert abs(v - 2.0) < 0.01

    def test_coin_cost_derived_not_hardcoded(self, tmp_path):
        """A different exchange spends 2 coins for 1 apple: received=1,
        delta_inv_used = 1 - 2 = -1, spent=2 -> 2 gold / 2 coins = 1 gold/coin.
        Proves the divisor comes from data, not a constant."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-18T00:00:00Z", character="hero"))
            s.add(Cycle(
                ts="2026-05-18T00:00:01Z", session_id=store._session_id, cycle_index=0,
                character="hero", selected_goal="TaskExchange", action_repr="TaskExchange",
                action_class="TaskExchangeAction", outcome="ok",
                drops_json=json.dumps({"apple": 1}), delta_inv_used=-1,
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert abs(v - 1.0) < 0.01

    def test_cycle_without_inventory_delta_falls_back_to_default(self, tmp_path):
        """delta_inv_used unknown -> can't derive coins spent -> default."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-18T00:00:00Z", character="hero"))
            s.add(Cycle(
                ts="2026-05-18T00:00:01Z", session_id=store._session_id, cycle_index=0,
                character="hero", selected_goal="TaskExchange", action_repr="TaskExchange",
                action_class="TaskExchangeAction", outcome="ok",
                drops_json=json.dumps({"apple": 6}), delta_inv_used=None,
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD

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
                delta_inv_used=-5,  # +1 item, -6 coins
            ))
            s.commit()
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        # No known sell price → 0 gold / 6 coins spent = 0
        assert v == 0.0

    @staticmethod
    def _store_one_cycle(tmp_path, *, drops_json, delta_inv_used, outcome="ok",
                         action_repr="TaskExchange"):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-18T00:00:00Z", character="hero"))
            s.add(Cycle(
                ts="2026-05-18T00:00:01Z", session_id=store._session_id, cycle_index=0,
                character="hero", selected_goal="TaskExchange", action_repr=action_repr,
                action_class="TaskExchangeAction", outcome=outcome,
                drops_json=drops_json, delta_inv_used=delta_inv_used,
            ))
            s.commit()
        return store

    def test_non_ok_cycle_is_skipped(self, tmp_path):
        store = self._store_one_cycle(
            tmp_path, drops_json=json.dumps({"apple": 6}), delta_inv_used=0,
            outcome="error:HTTP_478")
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD

    def test_drops_json_not_a_dict_is_skipped(self, tmp_path):
        store = self._store_one_cycle(tmp_path, drops_json="[]", delta_inv_used=-6)
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD

    def test_malformed_drops_json_is_skipped(self, tmp_path):
        store = self._store_one_cycle(tmp_path, drops_json="{not json", delta_inv_used=-6)
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD  # only cycle unusable -> default

    def test_non_integer_quantity_is_ignored(self, tmp_path):
        # apple qty is non-numeric -> not counted in received or value; the
        # numeric coin reward keeps received>0. received=0 here -> coins_spent
        # = 0 - (-6) = 6, value 0 -> 0 gold/coin.
        store = self._store_one_cycle(
            tmp_path, drops_json=json.dumps({"apple": "lots"}), delta_inv_used=-6)
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == 0.0

    def test_nonpositive_coins_spent_is_skipped(self, tmp_path):
        # received=2, delta_inv_used=5 -> coins_spent = 2-5 = -3 (implausible) -> skip.
        store = self._store_one_cycle(
            tmp_path, drops_json=json.dumps({"apple": 2}), delta_inv_used=5)
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert v == DEFAULT_COIN_VALUE_GOLD

    def test_received_coins_count_for_delta_not_value(self, tmp_path):
        # Reward of 1 apple + 2 tasks_coin: received=3, delta_inv_used = 3 - 6
        # spent = -3. coins_spent = 3-(-3)=6. Value counts only the apple.
        store = self._store_one_cycle(
            tmp_path, drops_json=json.dumps({"apple": 1, "tasks_coin": 2}), delta_inv_used=-3)
        v = expected_coin_value_with_prices(store, {"apple": 2})
        store.close()
        assert abs(v - (2.0 / 6.0)) < 0.01  # 1 apple * 2 gold / 6 coins


class TestWeightConstants:
    """Document the weight relationships callers depend on."""

    def test_relevant_skill_outranks_baseline(self):
        assert SKILL_XP_RELEVANT_TOOL_WEIGHT > SKILL_XP_BASELINE_WEIGHT

    def test_char_xp_scalar_is_one(self):
        # If this changes, every absolute scalar in callers shifts. Make
        # the dependency explicit.
        assert CHARACTER_XP_LEVEL_SCALAR == 1.0
