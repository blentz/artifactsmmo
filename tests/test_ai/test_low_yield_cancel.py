"""Tests for LowYieldCancelGoal (Phase G-D)."""

from sqlmodel import Session

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import TaskCancelAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.low_yield_cancel import (
    ALTERNATIVE_MARGIN,
    CONFIDENCE_THRESHOLD,
    LowYieldCancelGoal,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priorities import LOW_YIELD_CANCEL
from tests.test_ai.fixtures import make_state


def _gd_with_woodcutting_task() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _seed_cycles(store: LearningStore, cycles: list[dict]) -> None:
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


def _cycle(idx: int, goal: str, *, delta_xp: int = 0, delta_gold: int = 0,
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
        delta_gold=delta_gold,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=task_progress,
        task_total=10,
    )


class TestPriorityGating:
    def test_zero_when_no_task(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        goal = LowYieldCancelGoal()
        state = make_state(task_code=None, task_total=0)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 0.0
        store.close()

    def test_zero_when_no_history(self):
        goal = LowYieldCancelGoal()
        state = make_state(task_code="x", task_type="items", task_total=10)
        assert goal.priority(state, _gd_with_woodcutting_task(), None) == 0.0

    def test_zero_below_confidence_threshold(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Few FarmItems cycles → confidence < 0.5 → no fire.
        cycles = [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(3)]
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="x", task_type="items",
                           task_total=20, task_progress=3)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 0.0
        store.close()

    def test_zero_when_no_alternative_history(self, tmp_path):
        """Plenty of FarmItems history but no FarmMonster data → can't compare → no fire."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(35)]
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="x", task_type="items",
                           task_total=50, task_progress=10)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 0.0
        store.close()

    def test_zero_when_alternative_not_above_margin(self, tmp_path):
        """Alternative slightly better but not by ALTERNATIVE_MARGIN → no fire."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # FarmItems: 1 xp/cycle. FarmMonster: 1.2 xp/cycle. Ratio 1.2 < 1.5 margin.
        cycles = (
            [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(30)] +
            [_cycle(30 + i, "FarmMonster(chicken)", delta_xp=1) for i in range(30)] +
            # bump 6 of them so avg is 1.2
            [_cycle(60 + i, "FarmMonster(chicken)", delta_xp=2) for i in range(6)]
        )
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="x", task_type="items",
                           task_total=50, task_progress=10)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 0.0
        store.close()

    def test_fires_when_alternative_clearly_better(self, tmp_path):
        """FarmItems 1 xp, FarmMonster 5 xp → 5x margin → fires."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(35)] +
            [_cycle(35 + i, "FarmMonster(chicken)", delta_xp=5) for i in range(35)]
        )
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="x", task_type="items",
                           task_total=50, task_progress=10)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 70.0
        store.close()


class TestIsSatisfied:
    def test_satisfied_with_no_task(self):
        goal = LowYieldCancelGoal()
        assert goal.is_satisfied(make_state(task_code=None, task_total=0)) is True

    def test_unsatisfied_with_active_task(self):
        goal = LowYieldCancelGoal()
        assert goal.is_satisfied(make_state(task_code="x", task_total=10)) is False


class TestRelevantActions:
    def test_only_task_cancel_action(self):
        goal = LowYieldCancelGoal()
        actions = [
            RestAction(),
            GatherAction(resource_code="ash_tree"),
            TaskCancelAction(taskmaster_location=(1, 2)),
        ]
        state = make_state()
        gd = _gd_with_woodcutting_task()
        relevant = goal.relevant_actions(actions, state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], TaskCancelAction)


class TestConstants:
    def test_confidence_threshold_is_documented(self):
        assert 0.0 < CONFIDENCE_THRESHOLD < 1.0

    def test_alternative_margin_above_one(self):
        # Cancel must require the alternative to be *strictly better* than
        # the current task, by at least this margin.
        assert ALTERNATIVE_MARGIN > 1.0


class TestGHCharXpFastCancel:
    """G-H: zero-char-XP task cancels immediately when ANY alt pays char_xp.

    Real-play scenario this fixes: Robby's 347-fish gudgeon task. FarmItems
    cycles drop 0 char_xp each (XP only at CompleteTask), so the average is
    near-zero. Any monster grind pays char_xp/cycle > 0. Old scalar-based
    comparison made this an opaque ratio that required ~30 cycles to flip.
    New char-XP-rate comparison cancels in 3-ish cycles (just enough to
    seed the alternative's yield)."""

    def test_zero_char_xp_task_cancels_when_alt_pays(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Seed FarmItems with 5 zero-char-xp cycles (gudgeon-style).
        cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
        # Alternative: FarmMonster(slime) pays 15 char_xp/cycle.
        cycles += [_cycle(5 + i, "FarmMonster(slime)", delta_xp=15) for i in range(3)]
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="gudgeon", task_type="items",
                           task_total=347, task_progress=5)
        # Should fire immediately — no need to wait for confidence threshold.
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == LOW_YIELD_CANCEL
        store.close()

    def test_zero_char_xp_no_alt_doesnt_fire(self, tmp_path):
        """If no alternative has char_xp data, can't justify cancel."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
        _seed_cycles(store, cycles)
        goal = LowYieldCancelGoal()
        state = make_state(task_code="gudgeon", task_type="items",
                           task_total=347, task_progress=5)
        assert goal.priority(state, _gd_with_woodcutting_task(), store) == 0.0
        store.close()
