"""Bank expands when active-profile gear would overflow the bank (used-floor).

Three behaviours tested:
  (a) Expansion fires when bank_used is below trigger but active_bank_space_cost
      raises the used-floor above it (gold >= cost + reserve).
  (b) With no active-profile pressure the behaviour is identical to before the
      floor — a bank that is below the trigger does NOT fire.
  (c) The reserve gate still blocks when gold < cost + reserve even when the
      profile floor does push used over the trigger.
"""

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(**kwargs: object) -> WorldState:
    defaults: dict[str, object] = dict(
        character="Robby", level=5, xp=100, max_xp=500,
        hp=100, max_hp=100, gold=50, skills={}, x=0, y=0,
        inventory={}, inventory_max=20, equipment=dict(_ALL_SLOTS),
        cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )
    defaults.update(kwargs)
    if "task_lifecycle_phase" not in defaults:
        defaults["task_lifecycle_phase"] = derive_task_lifecycle_phase(
            defaults["task_code"], defaults["task_progress"], defaults["task_total"]  # type: ignore[arg-type]
        )
    return WorldState(**defaults)  # type: ignore[arg-type]

# Tiny bank so profile cost (10 distinct gear items) exceeds the 95% trigger.
# capacity=10, trigger at 10*95/100 = 9.5 → fires when used >= 10.
_CAPACITY = 10
_COST = 100


def _make_gd(capacity: int = _CAPACITY, cost: int = _COST) -> GameData:
    gd = GameData()
    gd._bank_capacity = capacity
    gd._next_expansion_cost = cost
    return gd


def _make_history_with_chicken_profile(tmp_path) -> LearningStore:
    """LearningStore that has a 'combat:chicken' profile with 10 distinct gear items."""
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="Robby")
    # 10 distinct gear slots → active_bank_space_cost == 10 when none are equipped.
    history.record_loadout_profile(
        "combat:chicken",
        {f"slot_{i}": f"gear_{i}" for i in range(10)},
    )
    return history


@pytest.fixture
def expand_fixture(tmp_path):
    gd = _make_gd()
    history = _make_history_with_chicken_profile(tmp_path)
    # 7 bank items = 70% fill (well below the 95% trigger when used alone).
    state = _make_state(gold=500, bank_items={f"item_{i}": 1 for i in range(7)})
    yield state, gd, history
    history.close()


class TestExpandBankProfileFloor:
    def test_expansion_fires_on_profile_overflow(self, expand_fixture):
        """(a) Profile floor raises used above trigger → expansion fires.

        Actual bank_used=7/10 (70%, below the 95% cross-multiply trigger).
        active_bank_space_cost=10 (10 distinct profile gear items, none equipped).
        used_floor = max(7, 10) = 10 → 10*100 >= 10*95 → should_expand_bank fires.
        Gold=500 >> cost(100), reserve=0 → no reserve block.
        """
        state, gd, history = expand_fixture
        goal = ExpandBankGoal(
            bank_accessible=True,
            game_data=gd,
            history=history,
            combat_monster="chicken",
            gather_skills=frozenset(),
        )
        assert goal.value(state, gd) > 0.0

    def test_no_profile_pressure_unchanged(self, expand_fixture):
        """(b) Without active-profile pressure, value() equals the history=None baseline.

        Same state (7/10 bank items), but combat_monster=None → no profile match
        → active_bank_space_cost=0 → used_floor=max(7,0)=7 → 70% < 95% → no fire.

        The assertion is explicit: goal-with-history must equal goal-without-history,
        which would FAIL if the floor were incorrectly applied even with no pressure
        (regression-proof: temporarily neutralise the floor and this test detects it).
        """
        state, gd, history = expand_fixture
        goal_with_history = ExpandBankGoal(
            bank_accessible=True,
            game_data=gd,
            history=history,
            combat_monster=None,
            gather_skills=frozenset(),
        )
        goal_no_history = ExpandBankGoal(
            bank_accessible=True,
            game_data=gd,
            history=None,
            combat_monster=None,
            gather_skills=frozenset(),
        )
        assert goal_with_history.value(state, gd) == goal_no_history.value(state, gd)
        assert goal_with_history.value(state, gd) == 0.0

    def test_reserve_gate_blocks_even_with_profile_pressure(self, tmp_path):
        """(c) Reserve gate still blocks when gold < cost + reserve.

        Profile cost=10 → used_floor=10 → expansion would fire on fill alone,
        BUT gold=450, cost=400, post-buy gold=50 < _MIN_SAFETY_FLOOR(100) →
        reserve_floor blocks → should_expand_bank returns False.
        """
        gd = GameData()
        gd._bank_capacity = 10
        gd._next_expansion_cost = 400

        history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
        history.record_loadout_profile(
            "combat:wolf",
            {f"slot_{i}": f"gear_{i}" for i in range(10)},
        )

        state = _make_state(
            level=5,
            gold=450,
            bank_items={f"item_{i}": 1 for i in range(7)},
        )
        goal = ExpandBankGoal(
            bank_accessible=True,
            game_data=gd,
            history=history,
            combat_monster="wolf",
            gather_skills=frozenset(),
        )
        # used_floor=10 → trigger fires, but reserve gate blocks (450-400=50 < _MIN_SAFETY_FLOOR=100).
        assert goal.value(state, gd) == 0.0
        history.close()
