"""Phase 23d-2 witness: items task with unbridgeable skill gap.

A task whose `task_requirement` returns a 49-level skill gap (current=1,
required=50) must PIVOT — no character can plausibly skill from 1 to 50 to
complete a single items task. This test pins down what production currently
does so the Lean bridge proof (`taskInfeasible → taskCancelFires`) can rest on
a verified premise.
"""

from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PIVOT, task_decision
from tests.test_ai.fixtures import make_state


def _gd_huge_gap() -> GameData:
    """An item requiring weaponcrafting level 50 to craft (gap = 49 from level 1)."""
    gd = GameData()
    gd._item_stats = {"legendary_sword": ItemStats(
        code="legendary_sword", level=50, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=50)}
    gd._crafting_recipes = {"legendary_sword": {}}
    return gd


def test_unbridgeable_items_task_no_observations_no_reward_history_pivots(
        tmp_path: Path) -> None:
    """49-level gap, history present but EMPTY (no skill XP rows, no reward rows).

    With empty observations, required_xp returns 0 for every level → skill_cycles=0.
    With no reward history, reward = DEFAULT_TASK_REWARD_VALUE = 50.0.
    With task_total=1, total_cycles = 0 + 1 = 1, skill_up_vpc = 50/1 = 50.
    confidence = 0/49 = 0.0, required_vpc = 5.0 * (1 + 3.0) = 20.0.
    50 >= 20 → production would PURSUE.

    But this is an unbridgeable gap (1 → 50). Pursuing is incorrect.
    """
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(
        task_code="legendary_sword", task_type="items",
        task_total=1, level=1, skills={"weaponcrafting": 1})
    result = task_decision(state, _gd_huge_gap(), store)
    assert result == PIVOT, (
        f"Items task with 49-level skill gap (weaponcrafting 1→50) must PIVOT. "
        f"Got {result!r}. Production is pursuing an objectively infeasible task.")
    store.close()
