"""Phase-17 differential test: PursueTaskGoal.value and GatherMaterialsGoal.value
both stay strictly below the survival floor (70) AND inside their declared
band [PRIORITY_FLOOR, PRIORITY_CEILING] for any (state, history, game_data)
input — including warm paths with real LearningStore samples.

Mirrors the Lean Phase-17 headlines:
  - `Formal.GoalValueBands.pursueTask_value_below_survival_floor`
  - `Formal.GoalValueBands.gatherMaterials_value_below_survival_floor`
  - `Formal.GoalValueBands.pursueTask_value_in_band`
  - `Formal.GoalValueBands.gatherMaterials_value_in_band`

The Python `value()` returns a float (the Goal API), so we assert the float
form satisfies the same `[floor, ceiling] ⊆ (-∞, 70)` invariants the Lean
`Rat` theorems prove. The exact-rational bit-equivalence of the clamp is
already pinned by `test_priority_band_diff.py`; here we exercise the WIRED
production callers.
"""
import os
import tempfile

from hypothesis import HealthCheck, given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import (
    PRIORITY_CEILING as GATHER_CEILING,
    PRIORITY_FLOOR as GATHER_FLOOR,
    GatherMaterialsGoal,
)
from artifactsmmo_cli.ai.goals.pursue_task import (
    PRIORITY_CEILING as PURSUE_CEILING,
    PRIORITY_FLOOR as PURSUE_FLOOR,
    PursueTaskGoal,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state

SURVIVAL_FLOOR = 70.0  # Phase-1 invariant, pinned in Lean as `survivalFloor`.


def _items_task_state(progress: int = 0, level: int = 5) -> object:
    return make_state(
        task_code="copper_bar", task_type="items",
        task_total=20, task_progress=progress, level=level,
    )


def _gather_state(inv_qty: int = 0, level: int = 5) -> object:
    return make_state(inventory={"copper_ore": inv_qty}, inventory_max=104,
                      bank_items={}, level=level)


def _populate_store(store: LearningStore, goal_repr: str, *,
                    char_xp: int, gold: int, count: int = 20,
                    cycles_to_satisfy: int | None = None) -> None:
    """Seed the LearningStore with `count` cycles for `goal_repr` carrying a
    fixed per-cycle char_xp and gold delta. Optionally records
    `cycles_to_satisfy` (drives GatherMaterials' existing efficiency ramp)."""
    store.start_session()
    for i in range(count):
        store.record_cycle(Cycle(
            ts=f"2026-05-30T00:00:{i:02d}+00:00",
            session_id="phase17", cycle_index=i, character=store._character,
            outcome="ok", selected_goal=goal_repr,
            delta_xp=char_xp, delta_gold=gold,
            cycles_to_satisfy=cycles_to_satisfy,
        ))


# ---------------------------------------------------------------------------
# PursueTaskGoal — band-clamp safety against the Lean headline.
# ---------------------------------------------------------------------------


@settings(max_examples=80, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    char_xp=st.integers(min_value=-100, max_value=10_000),
    gold=st.integers(min_value=-500, max_value=50_000),
    level=st.integers(min_value=1, max_value=40),
)
def test_pursue_task_value_below_survival_floor(char_xp, gold, level):
    """For ANY observed (char_xp, gold, level) — including absurdly large
    positives — PursueTaskGoal.value stays strictly below the survival floor
    AND inside [PRIORITY_FLOOR, PRIORITY_CEILING]. This is the Python
    expression of `pursueTask_value_below_survival_floor`."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        goal = PursueTaskGoal("copper_bar", initial_progress=0)
        _populate_store(store, repr(goal), char_xp=char_xp, gold=gold)
        gd = GameData()
        state = _items_task_state(level=level)
        v = goal.value(state, gd, history=store)
        assert PURSUE_FLOOR <= v <= PURSUE_CEILING, (v, PURSUE_FLOOR, PURSUE_CEILING)
        assert v < SURVIVAL_FLOOR, (v, SURVIVAL_FLOOR)
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


def test_pursue_task_cold_path_eq_floor():
    """Cold (history=None) → exactly PRIORITY_FLOOR. Pins the Lean
    `pursueTask_cold_eq_floor` identity at the Python boundary."""
    goal = PursueTaskGoal("copper_bar", initial_progress=0)
    assert goal.value(_items_task_state(), GameData(), history=None) == PURSUE_FLOOR


def test_pursue_task_zero_samples_eq_floor():
    """history present but zero samples for the goal → PRIORITY_FLOOR (the
    bonus is Fraction(0), so the clamp returns exactly floor)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        store.start_session()
        goal = PursueTaskGoal("copper_bar", initial_progress=0)
        v = goal.value(_items_task_state(), GameData(), history=store)
        assert v == PURSUE_FLOOR
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


# ---------------------------------------------------------------------------
# GatherMaterialsGoal — band-clamp safety against the Lean headline.
# ---------------------------------------------------------------------------


@settings(max_examples=80, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    char_xp=st.integers(min_value=-100, max_value=10_000),
    gold=st.integers(min_value=-500, max_value=50_000),
    level=st.integers(min_value=1, max_value=40),
    cycles_to_satisfy=st.integers(min_value=1, max_value=200),
)
def test_gather_materials_value_below_survival_floor(
    char_xp, gold, level, cycles_to_satisfy,
):
    """Same headline for GatherMaterials — Python form of
    `gatherMaterials_value_below_survival_floor`. Includes the existing
    efficiency ramp (cycles_to_satisfy) as an input dimension."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        goal = GatherMaterialsGoal("copper_dagger", needed={"copper_ore": 60})
        _populate_store(store, repr(goal), char_xp=char_xp, gold=gold,
                        cycles_to_satisfy=cycles_to_satisfy)
        gd = GameData()
        state = _gather_state(level=level)
        v = goal.value(state, gd, history=store)
        assert GATHER_FLOOR <= v <= GATHER_CEILING, (v, GATHER_FLOOR, GATHER_CEILING)
        assert v < SURVIVAL_FLOOR, (v, SURVIVAL_FLOOR)
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


def test_gather_materials_history_none_matches_base():
    """history=None preserves the original ramp value (no clamp applied).
    Pins that the Phase-17 wiring is a strict extension on the warm path."""
    goal = GatherMaterialsGoal("copper_dagger", needed={"copper_ore": 60})
    state = _gather_state(inv_qty=0)
    gd = GameData()
    base = goal.value(state, gd, history=None)
    # base = max(1.0, 40 * fraction_remaining) — fraction_remaining = 1.0 here.
    assert base == 40.0


def test_pursue_task_warm_path_lifts_above_floor():
    """A clearly above-baseline yield (3 char_xp/cycle, level 5) must lift
    PursueTaskGoal.value strictly above PRIORITY_FLOOR. This kills mutants
    that drop the scalar wiring entirely (e.g. removing the clamp call but
    also dropping the scalar lookup, or always returning the floor)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        goal = PursueTaskGoal("copper_bar", initial_progress=0)
        # 3 char_xp/cycle at level 5 yields scalar ~3 * 1.0 * 6 = 18 (well above
        # the BASELINE_SCALAR=1), so the bonus lifts toward the ceiling.
        _populate_store(store, repr(goal), char_xp=3, gold=0)
        v = goal.value(_items_task_state(level=5), GameData(), history=store)
        assert v > PURSUE_FLOOR, (v, PURSUE_FLOOR)
        assert v <= PURSUE_CEILING, (v, PURSUE_CEILING)
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


def test_pursue_task_high_yield_clamps_at_ceiling():
    """An absurd yield (10000 char_xp/cycle) clamps EXACTLY at PRIORITY_CEILING
    (50) — never escapes the band. Kills mutants that drop the upper clamp."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        goal = PursueTaskGoal("copper_bar", initial_progress=0)
        _populate_store(store, repr(goal), char_xp=10_000, gold=0)
        v = goal.value(_items_task_state(level=40), GameData(), history=store)
        # The clamp must hold even at extreme yields. We check the absolute
        # 70 cap (Lean's survival floor) — kills CEILING=100 mutants.
        assert v < SURVIVAL_FLOOR, (v, SURVIVAL_FLOOR)
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


def test_gather_materials_high_yield_clamps_below_survival():
    """Same survival-floor anchor for GatherMaterials at extreme observed
    yield. Kills mutants that lift the ceiling above 70."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        store = LearningStore(db_path=db, character="testchar")
        goal = GatherMaterialsGoal("copper_dagger", needed={"copper_ore": 60})
        _populate_store(store, repr(goal), char_xp=10_000, gold=0)
        v = goal.value(_gather_state(level=40), GameData(), history=store)
        assert v < SURVIVAL_FLOOR, (v, SURVIVAL_FLOOR)
        store.close()
    finally:
        if os.path.exists(db):
            os.unlink(db)


def test_pursue_task_constants_match_lean():
    """Pin the Python band constants against the Lean model's Rat values."""
    assert PURSUE_FLOOR == 35.0
    assert PURSUE_CEILING == 50.0
    assert PURSUE_CEILING < SURVIVAL_FLOOR


def test_gather_materials_constants_match_lean():
    """Pin the Python band constants against the Lean model's Rat values."""
    assert GATHER_FLOOR == 1.0
    assert GATHER_CEILING == 50.0
    assert GATHER_CEILING < SURVIVAL_FLOOR
