"""Tests for Phase G-B projections module."""

import json

from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import (
    TASKS_COIN_CODE,
    WARMUP_MIN_SAMPLES,
    Yield,
    cycles_for_progress,
    expected_yield_per_cycle,
    project_task_completion,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


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
        y = expected_yield_per_cycle("FarmItems", store)
        store.close()
        assert y.sample_count == 0
        assert y.char_xp == 0.0

    def test_aggregates_char_xp_and_gold(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "FarmItems", delta_xp=10, delta_gold=2) for i in range(5)
        ])
        y = expected_yield_per_cycle("FarmItems", store)
        store.close()
        assert y.sample_count == 5
        assert y.char_xp == 10.0
        assert y.gold == 2.0

    def test_aggregates_skill_xp_from_json(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "FarmItems",
                        delta_skill_xp_json=json.dumps({"woodcutting": 4}))
            for i in range(4)
        ])
        y = expected_yield_per_cycle("FarmItems", store)
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
            _make_cycle(0, "FarmItems", delta_xp=10),
            _make_cycle(1, "FarmMonster", delta_xp=100),
            _make_cycle(2, "FarmItems", delta_xp=10),
        ])
        y = expected_yield_per_cycle("FarmItems", store)
        store.close()
        assert y.sample_count == 2
        assert y.char_xp == 10.0


class TestCyclesForProgress:
    def test_returns_none_below_warmup(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(0, "FarmItems", task_progress=0),
            _make_cycle(1, "FarmItems", task_progress=1),
        ])
        assert cycles_for_progress("FarmItems", store) is None
        store.close()

    def test_median_progress_interval(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Need at least WARMUP_MIN_SAMPLES intervals between progress events.
        # Bumping progress every 5 cycles gives one interval per 5 cycles, so
        # use ~5 * (WARMUP_MIN_SAMPLES + 2) cycles to get enough intervals.
        cycles = []
        for i in range((WARMUP_MIN_SAMPLES + 2) * 5):
            tp = i // 5
            cycles.append(_make_cycle(i, "FarmItems", task_progress=tp))
        _populate(store, cycles)
        result = cycles_for_progress("FarmItems", store)
        store.close()
        assert result is not None
        assert 4.0 <= result <= 6.0


class TestProjectTaskCompletion:
    def test_no_task_returns_none(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code=None, task_total=0, task_progress=0)
        assert project_task_completion(state, store) is None
        store.close()

    def test_satisfied_task_returns_none(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="x", task_total=10, task_progress=10)
        assert project_task_completion(state, store) is None
        store.close()

    def test_empty_store_uses_defaults(self, tmp_path):
        """With no history, falls back to 15 cycles/progress and 150 gold bonus."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="gudgeon", task_type="items",
                           task_total=20, task_progress=5)
        proj = project_task_completion(state, store)
        store.close()
        assert proj is not None
        # 15 remaining * 15 cycles/progress = 225 cycles
        assert proj.cycles_remaining == 225.0
        # No yield data → expected_char_xp = 0
        assert proj.expected_char_xp == 0.0
        # No yield data → expected_gold = 0 + 150 bonus
        assert proj.expected_gold == 150.0
        # No history → confidence = 0
        assert proj.confidence == 0.0

    def test_confidence_scales_with_sample_count(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # 15 cycles → confidence = 15 / (10*3) = 0.5
        _populate(store, [
            _make_cycle(i, "FarmItems", delta_xp=5, delta_gold=1, task_progress=i)
            for i in range(15)
        ])
        state = make_state(task_code="x", task_type="items",
                           task_total=20, task_progress=5)
        proj = project_task_completion(state, store)
        store.close()
        assert proj is not None
        assert 0.4 < proj.confidence < 0.6


class TestCheapestPathToLevel:
    def _gd_with_monsters(self, monsters: dict[str, int]) -> GameData:
        gd = GameData()
        gd._monster_level = monsters
        return gd

    def test_returns_empty_path_when_already_at_target(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(level=10)
        plan = cheapest_path_to_level(10, state, store, self._gd_with_monsters({}))
        store.close()
        assert plan.total_cycles == 0.0
        assert plan.segments == []
        assert plan.blocked is False

    def test_uses_documented_xp_formula_when_no_observations(self, tmp_path):
        """No store data → use game_data.xp_per_kill (documented formula)
        instead of magic constants."""
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # xp_per_kill(chicken, L1) = 22 per documented formula.
        # cycle cost = DEFAULT_FIGHT_CYCLES (30) since no observations.
        # xp_per_cycle = 22/30 ≈ 0.733; cycles to gain 100 XP = ~136.
        assert not plan.blocked
        assert plan.segments[0].monster_code == "chicken"
        assert plan.segments[0].xp_per_cycle > 0
        # Within reasonable bounds (formula-derived, not magic)
        assert 100 < plan.total_cycles < 200

    def test_uses_observed_xp_when_available(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Seed 5 FarmMonster(chicken) cycles at 20 char-xp each
        _populate(store, [
            _make_cycle(i, "FarmMonster(chicken)", delta_xp=20) for i in range(5)
        ])
        gd = self._gd_with_monsters({"chicken": 1})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # 100 xp at 20/cycle = 5 cycles
        assert plan.segments[0].xp_per_cycle == 20.0
        assert plan.total_cycles == 5.0

    def test_blocked_when_no_beatable_monster(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"ogre": 50, "dragon": 80})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(50, state, store, gd)
        store.close()
        assert plan.blocked
        assert plan.total_cycles == float("inf")

    def test_picks_highest_xp_monster(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, (
            [_make_cycle(i, "FarmMonster(chicken)", delta_xp=2) for i in range(5)] +
            [_make_cycle(5 + i, "FarmMonster(yellow_slime)", delta_xp=15) for i in range(5)]
        ))
        gd = self._gd_with_monsters({"chicken": 1, "yellow_slime": 2})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # yellow_slime (lvl 2, char L1) is beatable due to +1 margin, gives 15xp/cyc
        assert plan.segments[0].monster_code == "yellow_slime"

    def test_extends_across_levels(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1, "wolf": 5})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(3, state, store, gd)
        store.close()
        # Should have 2 segments (level 1→2, level 2→3)
        assert len(plan.segments) == 2

    def test_next_action_monster_property(self, tmp_path):
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        assert plan.next_action_monster == "chicken"
        # Empty path → None
        empty = cheapest_path_to_level(1, make_state(level=1), store, gd)
        assert empty.next_action_monster is None


class TestPathSuccessRateFilter:
    """G-I post-fix: monsters with observed low win-rate excluded from path."""

    def test_low_win_rate_monster_skipped(self, tmp_path):
        from artifactsmmo_cli.ai.learning.models import Cycle
        from artifactsmmo_cli.ai.learning.models import Session as SessionModel
        from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level

        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id,
                                started_at="2026-05-18T00:00:00Z", character="hero"))
            # 6 yellow_slime fights all lost → success_rate = 0
            for i in range(6):
                s.add(Cycle(
                    ts=f"2026-05-18T00:{i:02d}:00Z",
                    session_id=store._session_id,
                    cycle_index=i, character="hero",
                    selected_goal="FarmMonster(yellow_slime)",
                    action_repr="Fight(yellow_slime)",
                    action_class="FightAction",
                    outcome="error:fight_lost",
                ))
            s.commit()

        gd = GameData()
        gd._monster_level = {"chicken": 1, "yellow_slime": 2}
        gd._monster_hp = {"chicken": 60, "yellow_slime": 70}
        gd._monster_type = {"chicken": "normal", "yellow_slime": "normal"}
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # yellow_slime would normally win by XP/cycle, but losses eliminate it.
        # chicken takes over as the only viable option.
        assert plan.segments[0].monster_code == "chicken"
