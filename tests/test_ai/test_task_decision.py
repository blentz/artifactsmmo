import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.scalarizer import DEFAULT_COIN_VALUE_GOLD
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import (
    DEFAULT_SKILL_XP_PER_CYCLE,
    LOW_CONFIDENCE_MARGIN,
    PIVOT,
    PURSUE,
    task_decision,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"small_health_potion": ItemStats(code="small_health_potion",
        level=1, type_="utility", crafting_skill="alchemy", crafting_level=5)}
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    return gd


def test_no_history_pivots() -> None:
    """history=None with a skill-gated task → PIVOT immediately."""
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=5, skills={"alchemy": 1})
    assert task_decision(state, _gd(), None) == PIVOT


def test_feasible_task_pursues(tmp_path: Path) -> None:
    """req is None (already feasible) → PURSUE immediately."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 9})  # >= 5, feasible
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()


def test_huge_skill_gap_low_confidence_pivots(tmp_path: Path) -> None:
    """alchemy 1→5, no observations, default reward — required_vpc is 4x baseline,
    default reward over task_total cycles can't clear it → PIVOT.

    Numbers:
      confidence = 0/4 = 0.0
      required_vpc = DEFAULT_COIN_VALUE_GOLD * (1 + LOW_CONFIDENCE_MARGIN * 1.0)
                   = 5.0 * 4.0 = 20.0
      skill_cycles = 0 (no observations → required_xp returns 0 for all levels)
      total_cycles = 0 + 29 = 29
      skill_up_vpc = DEFAULT_TASK_REWARD_VALUE / 29 ≈ 1.72 < 20.0
    """
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 1})  # no observations
    assert task_decision(state, _gd(), store) == PIVOT
    store.close()


def test_confident_cheap_high_reward_pursues(tmp_path: Path) -> None:
    """alchemy 4→5, gap fully observed (level 4 xp=10), very high reward → PURSUE.

    Numbers:
      confidence = 1/1 = 1.0
      required_vpc = 5.0 * (1 + 3.0 * 0.0) = 5.0
      skill_cycles = 10 / DEFAULT_SKILL_XP_PER_CYCLE = 10 / 10 = 1.0
      total_cycles = 1.0 + 1 = 2.0
      skill_up_vpc = 100000 / 2 = 50000 >> 5.0
    """
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    for lvl in (1, 2, 3, 4):
        store.record_skill_max_xp("alchemy", lvl, 10)  # cheap + observed
    store.record_task_reward_value(100000.0)            # high reward
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=1, skills={"alchemy": 4})  # gap of 1, observed
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()


def test_zero_confidence_high_reward_pursues(tmp_path: Path) -> None:
    """High reward + 1-level gap + zero confidence → PURSUE (PURSUE reachable without observations).

    This proves the hard-block bug is fixed: even with zero observations, a high
    enough reward/cycle clears the 4x confidence margin.

    Numbers:
      gap = 1 level (alchemy 4 → required 5), no observations for level 4
      confidence = 0/1 = 0.0
      required_vpc = 5.0 * (1 + 3.0 * 1.0) = 20.0
      skill_cycles = 0  (no observations → required_xp returns 0)
      total_cycles = 0 + 1 = 1  (task_total=1)
      skill_up_vpc = 10000 / 1 = 10000 >= 20.0
    """
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    store.record_task_reward_value(10000.0)  # high reward, no skill observations
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=1, skills={"alchemy": 4})
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()


def test_observed_rate_used_over_default(tmp_path: Path) -> None:
    """Observed skill-XP rate drives the decision, not the hardcoded default.

    Setup: alchemy 1→5, task_total=1, levels 1-4 each observed at max_xp=100,
    reward = DEFAULT_TASK_REWARD_VALUE = 50.0 (no seeded reward → uses default).

    With DEFAULT rate (10.0 xp/cycle):
      confidence = 1.0  →  required_vpc = 5.0
      total_xp = 4 * 100 = 400
      skill_cycles = 400 / 10 = 40
      total_cycles = 40 + 1 = 41
      skill_up_vpc = 50 / 41 ≈ 1.22 < 5.0  →  PIVOT

    With fast observed rate (100.0 xp/cycle, seeded via Cycle records):
      skill_cycles = 400 / 100 = 4
      total_cycles = 4 + 1 = 5
      skill_up_vpc = 50 / 5 = 10.0 >= 5.0  →  PURSUE

    We seed 1 Cycle row with delta_skill_xp = {"alchemy": 100} (positive, so it's
    counted) to make skill_xp_per_cycle return 100.0.
    """
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")

    # Seed XP observations for all gap levels so required_xp is well-defined
    for lvl in (1, 2, 3, 4):
        store.record_skill_max_xp("alchemy", lvl, 100)

    # Seed one cycle recording 100 alchemy XP so skill_xp_per_cycle("alchemy") → 100.0
    session_id = store.start_session()
    store.record_cycle(Cycle(
        ts="2026-01-01T00:00:00+00:00",
        session_id=session_id,
        cycle_index=0,
        character="hero",
        outcome="ok",
        delta_skill_xp_json=json.dumps({"alchemy": 100}),
    ))

    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=1, skills={"alchemy": 1})

    # Sanity: confirm observed rate is 100.0 (not the 10.0 default)
    assert store.skill_xp_per_cycle("alchemy") == 100.0

    result = task_decision(state, _gd(), store)
    assert result == PURSUE, (
        f"Expected PURSUE with fast observed rate (100 xp/cycle) but got {result!r}. "
        f"DEFAULT_SKILL_XP_PER_CYCLE={DEFAULT_SKILL_XP_PER_CYCLE}, "
        f"DEFAULT_COIN_VALUE_GOLD={DEFAULT_COIN_VALUE_GOLD}, "
        f"LOW_CONFIDENCE_MARGIN={LOW_CONFIDENCE_MARGIN}"
    )
    store.close()
