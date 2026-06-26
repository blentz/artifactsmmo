"""Tests for Phase G-B projections module."""

import json

from sqlalchemy.exc import OperationalError
from sqlmodel import Session

import artifactsmmo_cli.ai.learning.projections as proj
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import (
    TASKS_COIN_CODE,
    WARMUP_MIN_SAMPLES,
    Yield,
    _best_alternative_repr,
    cheapest_path_to_level,
    cycles_for_progress,
    expected_yield_per_cycle,
    low_yield_cancel_fires,
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


class TestParseHelpers:
    """Coverage for _parse_skill_xp and _parse_drops error/non-dict paths."""

    def test_non_dict_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 79: valid JSON but non-dict (e.g. list) → returns {}."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "FarmItems", delta_skill_xp_json="[1, 2]") for i in range(3)
        ])
        y = expected_yield_per_cycle("FarmItems", store)
        store.close()
        assert y.skill_xp == {}

    def test_malformed_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 81-82: invalid JSON in delta_skill_xp_json → swallowed → empty."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "FarmItems", delta_skill_xp_json="{broken") for i in range(3)
        ])
        y = expected_yield_per_cycle("FarmItems", store)
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

    def test_returns_empty_path_when_already_at_target(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(level=10)
        plan = cheapest_path_to_level(10, state, store, self._gd_with_monsters({}))
        store.close()
        assert plan.total_cycles == 0.0
        assert plan.segments == []
        assert plan.blocked is False

    def test_uses_documented_xp_formula_when_no_observations(self, monkeypatch, tmp_path):
        """No store data → use game_data.xp_per_kill (documented formula)
        instead of magic constants."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
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

    def test_uses_observed_xp_when_available(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
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

    def test_blocked_when_no_beatable_monster(self, monkeypatch, tmp_path):
        # Level-gate blocks these high-level monsters (ogre L50 > L1+1, dragon L80
        # similarly), so is_winnable is never reached for them — monkeypatch is still
        # correct for completeness but the level gate fires first.
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"ogre": 50, "dragon": 80})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(50, state, store, gd)
        store.close()
        assert plan.blocked
        assert plan.total_cycles == float("inf")

    def test_picks_highest_xp_monster(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
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

    def test_extends_across_levels(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1, "wolf": 5})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(3, state, store, gd)
        store.close()
        # Should have 2 segments (level 1→2, level 2→3)
        assert len(plan.segments) == 2

    def test_next_action_monster_property(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        assert plan.next_action_monster == "chicken"
        # Empty path → None
        empty = cheapest_path_to_level(1, make_state(level=1), store, gd)
        assert empty.next_action_monster is None

    def test_blocked_when_all_beatable_yield_zero_xp(self, monkeypatch, tmp_path):
        """Line 253: beatable is non-empty but all candidates produce 0 XP per cycle.
        Char L20 vs L1 monster: diff=19 >= 10 → penalty=0.0 → xp_per_kill=0
        → xp_per_cycle=0 → best_code stays None → blocked."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 0}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=20, xp=0, max_xp=100)
        plan = cheapest_path_to_level(21, state, store, gd)
        store.close()
        assert plan.blocked is True
        assert plan.total_cycles == float("inf")


class TestPathSuccessRateFilter:
    """G-I post-fix: monsters with observed low win-rate excluded from path.

    The old bespoke win-rate filter is now replaced by is_winnable (the single
    combat-beatability verdict shared with the runtime). is_winnable's learned-loss
    veto (>= MIN_WIN_SAMPLES fights at < WIN_RATE_THRESHOLD) subsumes the old
    MIN_PATH_SUCCESS_RATE / MIN_PATH_SAMPLES filter. We monkeypatch is_winnable
    to model the verdict directly, since the test's intent is that a monster
    is_winnable deems unwinnable is excluded from the path.
    """

    def test_low_win_rate_monster_skipped(self, monkeypatch, tmp_path):
        # is_winnable returns False for yellow_slime (learned-loss veto fired),
        # True for chicken — identical to what the old MIN_PATH_SUCCESS_RATE
        # filter produced, but now routed through the shared runtime verdict.
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "chicken")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")

        gd = GameData()
        gd._monster_level = {"chicken": 1, "yellow_slime": 2}
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # yellow_slime excluded by is_winnable; chicken is the only option.
        assert plan.segments[0].monster_code == "chicken"


class TestIsWinnableFilter:
    """Task-1: cheapest_path uses is_winnable to filter candidates."""

    def test_unwinnable_high_xp_monster_excluded(self, monkeypatch, tmp_path):
        # cow: level 8 (==char), high XP; green_slime: level 4, lower XP. is_winnable
        # says only green_slime is winnable → path picks green_slime despite cow's XP.
        gd = GameData()
        gd._monster_level = {"cow": 8, "green_slime": 4}
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "green_slime")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        plan = cheapest_path_to_level(9, state, store, gd)
        store.close()
        assert plan.next_action_monster == "green_slime"
        assert plan.blocked is False

    def test_blocked_when_nothing_winnable(self, monkeypatch, tmp_path):
        gd = GameData()
        gd._monster_level = {"cow": 8}
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: False)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        plan = cheapest_path_to_level(9, state, store, gd)
        store.close()
        assert plan.blocked is True

    def test_next_monster_is_always_winnable(self, monkeypatch, tmp_path):
        # Regression lock: the projection's emitted next monster MUST pass
        # is_winnable, so the runtime cascade returns the SAME monster.
        gd = GameData()
        gd._monster_level = {"cow": 8, "green_slime": 4}
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "green_slime")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        nxt = cheapest_path_to_level(9, state, store, gd).next_action_monster
        store.close()
        assert nxt is not None
        assert proj.is_winnable(state, gd, nxt, store) is True


class TestLowYieldCancelFires:
    """Unit tests for the shared low_yield_cancel_fires predicate."""

    def _seed(self, store: LearningStore, cycles: list[dict]) -> None:
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

    def _cycle(self, idx: int, goal: str, *, delta_xp: int = 0,
               task_progress: int = 0) -> dict:
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
        )

    def test_returns_false_when_no_history(self):
        state = make_state(task_code="x", task_total=10, task_progress=5)
        assert low_yield_cancel_fires(state, None) is False

    def test_returns_false_when_no_task(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code=None, task_total=0)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_returns_false_when_task_total_zero(self, tmp_path):
        """task_total == 0 is treated as no active task (fixes means.py bug)."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="gudgeon", task_total=0, task_progress=0)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_zero_char_xp_fires_immediately(self, tmp_path):
        """FarmItems 0 xp/cycle + FarmMonster positive → fires without confidence gate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
        cycles += [self._cycle(5 + i, "FarmMonster(slime)", delta_xp=15) for i in range(3)]
        self._seed(store, cycles)
        state = make_state(task_code="gudgeon", task_total=347, task_progress=5)
        assert low_yield_cancel_fires(state, store) is True
        store.close()

    def test_no_fire_when_no_farmitems_history(self, tmp_path):
        """FarmMonster data but no FarmItems samples → cannot determine current rate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "FarmMonster(slime)", delta_xp=15) for i in range(5)]
        self._seed(store, cycles)
        state = make_state(task_code="gudgeon", task_total=50, task_progress=5)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_no_fire_when_no_alternative_history(self, tmp_path):
        """FarmItems data but no FarmMonster cycles → no alternative repr."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(35)]
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_positive_path_fires_above_margin_and_confidence(self, tmp_path):
        """FarmItems 1 xp, FarmMonster 5 xp → 5x margin, sufficient confidence → fires."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(35)] +
            [self._cycle(35 + i, "FarmMonster(chicken)", delta_xp=5) for i in range(35)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10)
        assert low_yield_cancel_fires(state, store) is True
        store.close()

    def test_no_fire_below_confidence_threshold(self, tmp_path):
        """3 FarmItems samples → confidence 0.1 < 0.5 → no fire on positive path."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(3)] +
            [self._cycle(3 + i, "FarmMonster(chicken)", delta_xp=5) for i in range(3)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=3)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_no_fire_below_margin(self, tmp_path):
        """Alt 1.2x better but below 1.5 margin → no fire."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(30)] +
            [self._cycle(30 + i, "FarmMonster(chicken)", delta_xp=1) for i in range(30)] +
            [self._cycle(60 + i, "FarmMonster(chicken)", delta_xp=2) for i in range(6)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10)
        assert low_yield_cancel_fires(state, store) is False
        store.close()

    def test_no_fire_when_alt_yield_has_zero_samples(self, monkeypatch, tmp_path):
        """Line 378: _best_alternative_repr returns a repr but expected_yield_per_cycle
        finds zero samples for it → returns False without firing."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(5)]
        self._seed(store, cycles)
        # Return a repr that has no cycles in the store for this character.
        monkeypatch.setattr(proj, "_best_alternative_repr",
                            lambda h: "FarmMonster(ghost_that_does_not_exist)")
        state = make_state(task_code="x", task_total=50, task_progress=5)
        assert low_yield_cancel_fires(state, store) is False
        store.close()


class TestBestAlternativeReprEdgeCases:
    """Coverage for _best_alternative_repr error/empty-counts paths."""

    def test_returns_none_on_sqlalchemy_error(self, monkeypatch, tmp_path):
        """Lines 337-338: SQLAlchemy error → returns None gracefully."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()

        def _raise(self, stmt):
            raise OperationalError("stmt", {}, Exception("closed"))

        monkeypatch.setattr(Session, "exec", _raise)
        result = _best_alternative_repr(store)
        assert result is None
        store.close()

    def test_returns_none_when_all_rows_none(self, monkeypatch, tmp_path):
        """Line 346: rows non-empty but all entries are None → counts empty → None."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        monkeypatch.setattr(Session, "exec", lambda self, stmt: iter([None]))
        result = _best_alternative_repr(store)
        assert result is None
        store.close()
