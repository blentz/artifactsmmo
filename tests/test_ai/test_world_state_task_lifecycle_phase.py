"""Tests for WorldState ↔ TaskLifecyclePhase invariant (Phase 23c-1)."""


from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_lifecycle import (
    TaskLifecyclePhase,
    derive_task_lifecycle_phase,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


class TestDeriveTaskLifecyclePhase:
    """Pure-function derivation of the four phases from raw task fields."""

    def test_none_when_task_code_is_none(self):
        assert derive_task_lifecycle_phase(None, 0, 0) is TaskLifecyclePhase.NONE

    def test_none_when_task_code_is_empty_string(self):
        # CompleteTaskAction leaves task_code="" after turn-in.
        assert derive_task_lifecycle_phase("", 0, 0) is TaskLifecyclePhase.NONE

    def test_none_when_task_code_set_but_total_zero(self):
        # Server-paired contract — real tasks always have total > 0;
        # task_code without a total is treated as phantom-task / NONE.
        assert derive_task_lifecycle_phase("monsters_chicken", 0, 0) is TaskLifecyclePhase.NONE

    def test_accepted_when_progress_zero_and_total_positive(self):
        assert (
            derive_task_lifecycle_phase("monsters_chicken", 0, 10)
            is TaskLifecyclePhase.ACCEPTED
        )

    def test_in_progress_when_progress_strictly_between_zero_and_total(self):
        assert (
            derive_task_lifecycle_phase("monsters_chicken", 3, 10)
            is TaskLifecyclePhase.IN_PROGRESS
        )

    def test_complete_when_progress_equals_total(self):
        assert (
            derive_task_lifecycle_phase("monsters_chicken", 10, 10)
            is TaskLifecyclePhase.COMPLETE
        )

    def test_complete_when_progress_exceeds_total(self):
        # FightAction may bump progress past total on a kill streak.
        assert (
            derive_task_lifecycle_phase("monsters_chicken", 11, 10)
            is TaskLifecyclePhase.COMPLETE
        )


class TestWorldStatePhaseInvariant:
    """``WorldState.__post_init__`` is the single source of truth — it must
    assert the stored phase matches the derivation, raising AssertionError
    on mismatch."""

    def test_make_state_default_is_none(self):
        state = make_state()
        assert state.task_lifecycle_phase is TaskLifecyclePhase.NONE

    def test_make_state_derives_accepted(self):
        state = make_state(task_code="monsters_chicken", task_progress=0, task_total=10)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.ACCEPTED

    def test_make_state_derives_in_progress(self):
        state = make_state(task_code="monsters_chicken", task_progress=4, task_total=10)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.IN_PROGRESS

    def test_make_state_derives_complete(self):
        state = make_state(task_code="monsters_chicken", task_progress=10, task_total=10)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.COMPLETE

    def test_direct_construction_with_mismatched_phase_is_corrected(self):
        """Constructing WorldState directly with a phase that disagrees with
        (task_code, task_progress, task_total) gets the phase CORRECTED via
        derive_task_lifecycle_phase in __post_init__. The stored value
        always matches the derive function — SINGLE SOURCE OF TRUTH at
        construction time.

        Perimeter fix (post-Phase-24): the original Phase-23c-1 design
        asserted equality and tripped AssertionError on mismatch. That
        broke formal/diff tests that default-pass NONE. Deriving instead
        of asserting keeps the invariant (stored == derived ∀ State)
        without forcing every callsite to thread the phase through.
        """
        base = make_state(task_code="monsters_chicken", task_progress=4, task_total=10)
        # base has phase IN_PROGRESS. Try to construct with ACCEPTED.
        constructed = WorldState(
            character=base.character,
            level=base.level,
            xp=base.xp,
            max_xp=base.max_xp,
            hp=base.hp,
            max_hp=base.max_hp,
            gold=base.gold,
            skills=base.skills,
            x=base.x,
            y=base.y,
            inventory=base.inventory,
            inventory_max=base.inventory_max,
            inventory_slots_max=base.inventory_slots_max,
            equipment=base.equipment,
            cooldown_expires=base.cooldown_expires,
            task_code=base.task_code,
            task_type=base.task_type,
            task_progress=base.task_progress,
            task_total=base.task_total,
            bank_items=base.bank_items,
            bank_gold=base.bank_gold,
            pending_items=base.pending_items,
            task_lifecycle_phase=TaskLifecyclePhase.ACCEPTED,  # WRONG (should be IN_PROGRESS)
        )
        # __post_init__ corrected the phase to match raw fields.
        assert constructed.task_lifecycle_phase == TaskLifecyclePhase.IN_PROGRESS


class TestApplyTransitions:
    """End-to-end phase transitions through production action.apply paths."""

    @staticmethod
    def _gd() -> GameData:
        gd = GameData()
        gd._taskmaster_location = (1, 2)
        # CompleteTaskAction.apply now calls task_coin_reward; seed a
        # conservative floor so apply doesn't raise "no task coin-reward data".
        gd._task_coin_rewards = {"monsters_chicken": 1, "copper_ore": 1}
        return gd

    def test_accept_task_action_transitions_none_to_accepted(self):
        game_data = self._gd()

        state = make_state(task_code=None, task_progress=0, task_total=0)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.NONE
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        new = action.apply(state, game_data)
        assert new.task_lifecycle_phase is TaskLifecyclePhase.ACCEPTED

    def test_task_trade_action_recomputes_phase(self):
        game_data = self._gd()
        state = make_state(
            task_code="items_copper_ore",
            task_progress=0,
            task_total=10,
            inventory={"copper_ore": 5},
        )
        action = TaskTradeAction(code="copper_ore", quantity=5, taskmaster_location=(1, 2))
        new = action.apply(state, game_data)
        # progress 0 → 5, total 10 ⇒ IN_PROGRESS
        assert new.task_progress == 5
        assert new.task_lifecycle_phase is TaskLifecyclePhase.IN_PROGRESS

    def test_task_trade_action_reaching_total_is_complete(self):
        game_data = self._gd()
        state = make_state(
            task_code="items_copper_ore",
            task_progress=5,
            task_total=10,
            inventory={"copper_ore": 5},
        )
        action = TaskTradeAction(code="copper_ore", quantity=5, taskmaster_location=(1, 2))
        new = action.apply(state, game_data)
        assert new.task_progress == 10
        assert new.task_lifecycle_phase is TaskLifecyclePhase.COMPLETE

    def test_complete_task_action_returns_to_none(self):
        game_data = self._gd()
        state = make_state(
            task_code="monsters_chicken",
            task_progress=10,
            task_total=10,
        )
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        new = action.apply(state, game_data)
        assert new.task_lifecycle_phase is TaskLifecyclePhase.NONE

    def test_task_cancel_action_returns_to_none(self):
        game_data = self._gd()
        state = make_state(
            task_code="monsters_chicken",
            task_progress=4,
            task_total=10,
            inventory={"tasks_coin": 5},
        )
        action = TaskCancelAction(taskmaster_location=(1, 2))
        new = action.apply(state, game_data)
        assert new.task_lifecycle_phase is TaskLifecyclePhase.NONE
