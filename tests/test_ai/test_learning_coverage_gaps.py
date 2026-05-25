"""Behavior tests closing coverage gaps in learning projections parsers and
the scalarizer's coin-value branch."""

from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import (
    Yield,
    cycles_for_progress,
    expected_yield_per_cycle,
)
from artifactsmmo_cli.ai.learning.scalarizer import (
    DEFAULT_COIN_VALUE_GOLD,
    GOLD_PER_XP_EQUIVALENT,
    scalar_yield,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _cycle(idx, goal, *, delta_xp=0, cycles_to_satisfy=None,
           delta_skill_xp_json="{}", drops_json=None, task_progress=0):
    return dict(
        ts=f"2026-05-18T00:{idx:02d}:00Z",
        cycle_index=idx,
        character="hero",
        selected_goal=goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        delta_xp=delta_xp,
        delta_gold=0,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=task_progress,
        task_total=10,
        delta_skill_xp_json=delta_skill_xp_json,
        drops_json=drops_json,
        cycles_to_satisfy=cycles_to_satisfy,
    )


def _populate(store, cycles):
    store.start_session()
    with Session(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-18T00:00:00Z", character="hero"))
        for kw in cycles:
            kw2 = dict(kw)
            kw2["session_id"] = store._session_id
            s.add(Cycle(**kw2))
        s.commit()


class TestSkillXpParsing:
    def test_malformed_skill_xp_json_yields_no_skill_xp(self, tmp_path):
        """Non-JSON delta_skill_xp_json is swallowed (lines 78-79) so the
        cycle contributes char_xp but zero skill_xp."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _cycle(i, "FarmMonster(slime)", delta_xp=4,
                   delta_skill_xp_json="{not valid json")
            for i in range(3)
        ])
        y = expected_yield_per_cycle("FarmMonster(slime)", store)
        store.close()
        assert y.char_xp == 4.0
        assert y.skill_xp == {}

    def test_non_dict_skill_xp_json_yields_no_skill_xp(self, tmp_path):
        """A valid-JSON but non-dict payload (line 76) is treated as empty."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _cycle(i, "FarmMonster(slime)", delta_xp=2,
                   delta_skill_xp_json="[1, 2, 3]")
            for i in range(3)
        ])
        y = expected_yield_per_cycle("FarmMonster(slime)", store)
        store.close()
        assert y.skill_xp == {}


class TestDropsParsing:
    def test_malformed_drops_json_yields_no_coins(self, tmp_path):
        """Malformed drops_json is swallowed (lines 92-93) -> zero coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _cycle(i, "CompleteTask", drops_json="{broken")
            for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0

    def test_non_dict_drops_json_yields_no_coins(self, tmp_path):
        """Valid JSON but non-dict drops payload (line 90) -> zero coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _cycle(i, "CompleteTask", drops_json="[\"apple\"]")
            for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0


class TestCyclesForProgressViaSatisfyEvents:
    def test_uses_cycles_to_satisfy_markers(self, tmp_path):
        """When task_progress never advances but cycles_to_satisfy events are
        recorded, those become progress intervals (line 159) and the median is
        returned once enough samples exist."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _cycle(i, "GatherMaterials(x)", cycles_to_satisfy=4)
            for i in range(12)
        ])
        result = cycles_for_progress("GatherMaterials(x)", store)
        store.close()
        assert result == 4


class TestScalarCoinValueWithStore:
    def test_coins_use_store_derived_value(self, tmp_path):
        """With a store present AND tasks_coins > 0, the scalarizer derives the
        coin value from history (lines 148-149). With no TaskExchange history it
        falls back to the default, so the coin component matches the default
        formula."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = GameData()
        y = Yield(tasks_coins=3.0, sample_count=20)
        s = scalar_yield(y, make_state(level=1, task_code=None), gd, store=store)
        store.close()
        expected = 3.0 * DEFAULT_COIN_VALUE_GOLD / GOLD_PER_XP_EQUIVALENT
        assert abs(s - expected) < 1e-6
