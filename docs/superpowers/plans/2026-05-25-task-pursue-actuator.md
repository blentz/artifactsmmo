# Task PURSUE Actuator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the strategy a working actuator for `PURSUE` tasks so an accepted task progresses to turn-in instead of stalling while the bot grinds discretionary XP.

**Architecture:** Monster-tasks reuse the existing objective-step grind, retargeted to the task monster. Items-tasks get a new `PursueTaskGoal` in the discretionary band, mapped via `task_requirement` so a skill-gated item first levels the gating crafting skill (`LevelSkillGoal`) then produces/trades. The `current+1` planning bound lifts to a tunable `LEVEL_LOOKAHEAD=3`.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), GOAP planner, pydantic/dataclass `WorldState`.

**Spec:** `docs/superpowers/specs/2026-05-25-task-pursue-actuator-design.md`

**Conventions:** All commands prefixed `uv run`. One class per file. Imports at top, absolute, no `if TYPE_CHECKING`, no inline imports. Never catch `Exception`. Tests live in `tests/`; use `tests/test_ai/fixtures.py::make_state`. Success: 0 errors, 0 warnings, 0 skipped, 100% on changed code. End commit messages with the `Co-Authored-By` trailer.

---

## File Structure

- **Create** `src/artifactsmmo_cli/ai/goals/pursue_task.py` — `PursueTaskGoal`: drives gather/craft→TaskTrade to advance an items-task by one unit; satisfied when full/advanced.
- **Modify** `src/artifactsmmo_cli/ai/strategy_driver.py` — `LEVEL_LOOKAHEAD` constant; `objective_step_goal` lifted bound + items stand-down; `map_means` `PURSUE_TASK` split; new imports.
- **Modify** `src/artifactsmmo_cli/ai/tiers/means.py` — `MeansKind.PURSUE_TASK`, `DISCRETIONARY_ORDER`, `_fires`, `PURSUE` import.
- **Modify** `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` — remove blanket `if state.task_code: return 0.0`.
- **Modify** `src/artifactsmmo_cli/ai/goals/level_skill.py` — refresh stale `current+1` comment.
- **Modify** `src/artifactsmmo_cli/ai/player.py` — `_task_aligned_monster`, `_winnable_farm_target` preference, `task_decision`/`PURSUE` import.
- **Tests** — `tests/test_ai/test_pursue_task_goal.py` (new), and additions to `test_tiers_means.py`, `test_strategy_driver.py`, `test_grind_character_xp.py`, plus a player retarget test.

---

### Task 1: Lift the `current+1` planning bound to `LEVEL_LOOKAHEAD`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (add constant; `objective_step_goal` line ~101)
- Modify: `src/artifactsmmo_cli/ai/goals/level_skill.py:44-47` (comment only)
- Test: `tests/test_ai/test_strategy_driver.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_strategy_driver.py` (imports: `from artifactsmmo_cli.ai.strategy_driver import LEVEL_LOOKAHEAD, objective_step_goal`; `from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel`; `from artifactsmmo_cli.ai.tiers.guards import SelectionContext`; `from artifactsmmo_cli.ai.game_data import GameData`; `from tests.test_ai.fixtures import make_state`):

```python
def _ctx(**kw):
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster="chicken")
    base.update(kw)
    return SelectionContext(**base)


class TestLevelLookahead:
    def test_constant_is_three(self):
        assert LEVEL_LOOKAHEAD == 3

    def test_skill_step_targets_current_plus_lookahead(self):
        state = make_state(skills={"weaponcrafting": 1})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        # LevelSkillGoal repr is "LevelSkill(<skill>-><target>)"
        assert repr(goal) == "LevelSkill(weaponcrafting->4)"   # min(50, 1+3)

    def test_skill_step_caps_at_step_level(self):
        state = make_state(skills={"weaponcrafting": 48})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        assert repr(goal) == "LevelSkill(weaponcrafting->50)"   # min(50, 48+3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::TestLevelLookahead -v`
Expected: FAIL — `ImportError: cannot import name 'LEVEL_LOOKAHEAD'`.

- [ ] **Step 3: Add the constant and lift the bound**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, add the constant just below the imports / above `map_guard` (after line ~35):

```python
LEVEL_LOOKAHEAD = 3
"""How many levels ahead the objective step / task skill-gate targets, replacing
the old hard current+1. The planner re-plans every cycle and executes only
plan[0], so this steers search reachability/direction, not commitment. Tunable:
raise toward 5 if traces show 90s-budget headroom; deeper risks a no_plan
timeout on a long recipe chain."""
```

In `objective_step_goal`, the `ReachSkillLevel` branch currently reads:

```python
    if isinstance(step, ReachSkillLevel):
        current = state.skills.get(step.skill, 0)
        target = min(step.level, current + 1)
        return LevelSkillGoal(skill_name=step.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(step.skill, 0))
```

Change `current + 1` to `current + LEVEL_LOOKAHEAD`:

```python
        target = min(step.level, current + LEVEL_LOOKAHEAD)
```

- [ ] **Step 4: Refresh the stale comment in `level_skill.py`**

In `src/artifactsmmo_cli/ai/goals/level_skill.py:44-47`, replace the `current+1` comment:

```python
        # NOTE: the strategy driver bounds target_level to current+LEVEL_LOOKAHEAD,
        # so with MAX_SKILL_GAP=5 this guard stays inert for the objective-step
        # path (gap <= 3). The "don't grind too far" intent is handled by the
        # bounded target + per-cycle replan. The guard still protects any other
        # (small-gap) caller.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::TestLevelLookahead -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/goals/level_skill.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(ai): lift the current+1 planning bound to LEVEL_LOOKAHEAD=3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `PursueTaskGoal` — items-task actuator

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/pursue_task.py`
- Test: `tests/test_ai/test_pursue_task_goal.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_pursue_task_goal.py`:

```python
"""Tests for PursueTaskGoal — the items-task PURSUE actuator."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.pursue_task import PRIORITY_WHEN_FIRING, PursueTaskGoal
from tests.test_ai.fixtures import make_state


def _items_task(progress=0, total=20):
    return make_state(task_code="copper_bar", task_type="items",
                      task_progress=progress, task_total=total)


class TestPursueTaskGoal:
    def test_repr(self):
        assert repr(PursueTaskGoal("copper_bar", 0)) == "PursueTask(copper_bar)"

    def test_value_fires_when_unsatisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=0), GameData()) == PRIORITY_WHEN_FIRING

    def test_value_zero_when_satisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=20), GameData()) == 0.0

    def test_desired_state_is_one_more_unit(self):
        g = PursueTaskGoal("copper_bar", 5)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 6}

    def test_satisfied_when_full(self):
        assert PursueTaskGoal("copper_bar", 0).is_satisfied(_items_task(progress=20))

    def test_satisfied_when_task_gone(self):
        assert PursueTaskGoal("copper_bar", 0).is_satisfied(make_state(task_code=None, task_total=0))

    def test_satisfied_when_progress_advanced(self):
        # committed at progress 5; now observed at 6 -> re-decide
        assert PursueTaskGoal("copper_bar", 5).is_satisfied(_items_task(progress=6))

    def test_not_satisfied_while_stalled(self):
        assert not PursueTaskGoal("copper_bar", 5).is_satisfied(_items_task(progress=5))

    def test_relevant_actions_keep_produce_and_trade_drop_combat(self):
        g = PursueTaskGoal("copper_bar", 0)
        actions = [
            GatherAction(code="copper_ore", x=0, y=0),
            CraftAction(code="copper_bar", x=0, y=0),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(1, 2)),
            RestAction(),
            FightAction(monster="chicken", x=0, y=0),
        ]
        kept = g.relevant_actions(actions, _items_task(), GameData())
        kept_types = {type(a).__name__ for a in kept}
        assert "GatherAction" in kept_types
        assert "CraftAction" in kept_types
        assert "TaskTradeAction" in kept_types
        assert "RestAction" in kept_types          # recovery is supporting
        assert "FightAction" not in kept_types      # combat excluded
```

> Note: if `GatherAction`/`CraftAction`/`FightAction`/`RestAction` constructor kwargs differ from the above, copy the exact signatures from an existing test in `tests/test_ai/` (e.g. `test_grind_character_xp.py`, `test_actions_task_trade.py`). The behavior asserted (which types are kept) is what matters.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_pursue_task_goal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.goals.pursue_task'`.

- [ ] **Step 3: Implement `PursueTaskGoal`**

Create `src/artifactsmmo_cli/ai/goals/pursue_task.py`:

```python
"""PursueTaskGoal: advance an items-type task by one unit via gather/craft -> TaskTrade.

The PURSUE actuator for items tasks. Re-plans each cycle (the arbiter executes
only plan[0]), so desired_state targets one more traded unit; satisfied the
moment progress advances or the task is full/gone, letting the arbiter re-decide
against fresh API-observed state.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Matches the retired FarmItems value (35) so task pursuit slots at the same
# weight as the behavior it restores.
PRIORITY_WHEN_FIRING = 35.0
"""Priority when an items task is being pursued. Mirrors retired FarmItems(35)."""


class PursueTaskGoal(Goal):
    """Drive gather/craft -> TaskTrade to advance an items-type task one unit."""

    def __init__(self, task_code: str, initial_progress: int) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_FIRING

    def is_satisfied(self, state: WorldState) -> bool:
        if not state.task_code or state.task_total == 0:
            return True
        if state.task_progress >= state.task_total:
            return True
        return state.task_progress > self._initial_progress

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + 1}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif isinstance(action, (GatherAction, CraftAction, TaskTradeAction)):
                result.append(action)
        return result

    @property
    def max_depth(self) -> int:
        # Deep recipe chains (gather -> craft sub-recipes -> craft -> trade).
        return 100

    def __repr__(self) -> str:
        return f"PursueTask({self._task_code})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_pursue_task_goal.py -v`
Expected: PASS (all green). If a fixture constructor kwarg mismatched, fix the test's action construction to match the real signatures, then re-run.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/pursue_task.py tests/test_ai/test_pursue_task_goal.py
git commit -m "feat(ai): add PursueTaskGoal items-task actuator

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `MeansKind.PURSUE_TASK` + `_fires` + band ordering

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py`
- Test: `tests/test_ai/test_tiers_means.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_tiers_means.py` (it already imports `MeansKind`, `active_means`, `DISCRETIONARY_ORDER`, `make_state`, `GameData`; add `from unittest.mock import patch` is already present). Use the module's `_ctx()` helper:

```python
class TestPursueTask:
    def test_in_discretionary_order(self):
        assert MeansKind.PURSUE_TASK in DISCRETIONARY_ORDER

    def test_fires_for_items_task_on_pursue(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        store = LearningStore(":memory:")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK in discretionary

    def test_does_not_fire_for_monster_task(self):
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0)
        store = LearningStore(":memory:")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_on_pivot(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        store = LearningStore(":memory:")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pivot"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_when_full(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=20)
        store = LearningStore(":memory:")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_without_history(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        _, discretionary = active_means(state, GameData(), None, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary
```

> `task_decision` returns the string constants `PURSUE = "pursue"` / `PIVOT = "pivot"`. Patch the name as imported into `means.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_tiers_means.py::TestPursueTask -v`
Expected: FAIL — `AttributeError: PURSUE_TASK` (enum member missing).

- [ ] **Step 3: Implement the means**

In `src/artifactsmmo_cli/ai/tiers/means.py`:

Add `PURSUE` to the existing `task_decision` import:

```python
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
```

Add the enum member to `MeansKind`:

```python
class MeansKind(Enum):
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    SELL_PRESSURED = "sell_pressured"
    LOW_YIELD_CANCEL = "low_yield_cancel"
    TASK_CANCEL = "task_cancel"
    PURSUE_TASK = "pursue_task"
    ACCEPT_TASK = "accept_task"
    TASK_EXCHANGE = "task_exchange"
    SELL_IDLE = "sell_idle"
    BANK_EXPAND = "bank_expand"
```

Put `PURSUE_TASK` first in the discretionary band:

```python
DISCRETIONARY_ORDER: tuple[MeansKind, ...] = (
    MeansKind.PURSUE_TASK,
    MeansKind.ACCEPT_TASK,
    MeansKind.TASK_EXCHANGE,
    MeansKind.SELL_IDLE,
    MeansKind.BANK_EXPAND,
)
```

Add the `_fires` branch (place it before the `ACCEPT_TASK` branch):

```python
    if kind is MeansKind.PURSUE_TASK:
        return (state.task_type == "items"
                and bool(state.task_code) and state.task_total > 0
                and state.task_progress < state.task_total
                and history is not None
                and task_decision(state, game_data, history) == PURSUE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_tiers_means.py::TestPursueTask -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/means.py tests/test_ai/test_tiers_means.py
git commit -m "feat(ai): add PURSUE_TASK discretionary means for items tasks

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `map_means` split + `objective_step_goal` items stand-down

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`map_means`, `objective_step_goal`, imports)
- Test: `tests/test_ai/test_strategy_driver.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_strategy_driver.py` (add imports: `from artifactsmmo_cli.ai.strategy_driver import map_means`; `from artifactsmmo_cli.ai.tiers.means import MeansKind`; `from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel`; `from artifactsmmo_cli.ai.game_data import GameData, ItemStats`):

```python
class TestPursueTaskMapping:
    def test_feasible_items_task_maps_to_pursue_task(self):
        # no crafting recipe known -> task_requirement returns None -> feasible
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        goal = map_means(MeansKind.PURSUE_TASK, GameData(), _ctx(), state)
        assert repr(goal) == "PursueTask(copper_bar)"

    def test_skill_gated_items_task_maps_to_level_skill(self):
        gd = GameData()
        gd._item_stats["copper_bar"] = ItemStats(
            code="copper_bar", type_="resource", level=1,
            crafting_skill="weaponcrafting", crafting_level=3, effects={},
        )
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 1})
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        assert repr(goal) == "LevelSkill(weaponcrafting->3)"   # min(gate=3, 1+LEVEL_LOOKAHEAD)


class TestItemsTaskStandDown:
    def test_char_step_stands_down_for_items_task(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        assert objective_step_goal(ReachCharLevel(50), state, GameData(), _ctx()) is None

    def test_char_step_grinds_for_monster_task(self):
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0)
        goal = objective_step_goal(ReachCharLevel(50), state, GameData(), _ctx())
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")

    def test_char_step_grinds_with_no_task(self):
        goal = objective_step_goal(ReachCharLevel(50), make_state(), GameData(), _ctx())
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")
```

> **Signature note:** `map_means` currently takes `(kind, game_data, ctx)`. The `PURSUE_TASK` split needs `state` (for `task_requirement` and current skill levels), so Step 3 adds a 4th `state` parameter — both tests above already pass it. Verify the exact `ItemStats` field names by reading `src/artifactsmmo_cli/ai/game_data.py` (the constructor used above mirrors `task_feasibility` usage: `crafting_skill`, `crafting_level`); adjust kwargs if the dataclass differs.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::TestPursueTaskMapping tests/test_ai/test_strategy_driver.py::TestItemsTaskStandDown -v`
Expected: FAIL — `map_means()` takes 3 positional args / `MeansKind.PURSUE_TASK` unhandled, and stand-down returns a goal not `None`.

- [ ] **Step 3: Implement the split + stand-down**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, add imports:

```python
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.task_feasibility import task_requirement
```

Change `map_means` to accept `state` and handle `PURSUE_TASK`. Update the signature and add the branch (before the `ACCEPT_TASK` branch). Also thread `state` to the one call site (see note):

```python
def map_means(kind: MeansKind, game_data: GameData, ctx: SelectionContext,
              state: WorldState) -> Goal:
    """Map a MeansKind to a parameterized Goal instance."""
    if kind is MeansKind.CLAIM_PENDING:
        return ClaimPendingGoal()
    if kind is MeansKind.COMPLETE_TASK:
        return CompleteTaskGoal()
    if kind is MeansKind.SELL_PRESSURED or kind is MeansKind.SELL_IDLE:
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible)
    if kind is MeansKind.LOW_YIELD_CANCEL:
        return LowYieldCancelGoal()
    if kind is MeansKind.TASK_CANCEL:
        return TaskCancelGoal()
    if kind is MeansKind.PURSUE_TASK:
        req = task_requirement(state, game_data)
        if req is not None and req.skill != "combat":
            current = state.skills.get(req.skill, 0)
            target = min(req.required_level, current + LEVEL_LOOKAHEAD)
            return LevelSkillGoal(skill_name=req.skill, target_level=target,
                                  initial_skill_xp=state.skill_xp.get(req.skill, 0))
        return PursueTaskGoal(task_code=state.task_code, initial_progress=state.task_progress)
    if kind is MeansKind.ACCEPT_TASK:
        return AcceptTaskGoal()
    if kind is MeansKind.TASK_EXCHANGE:
        return TaskExchangeGoal(min_coins=ctx.task_exchange_min_coins)
    if kind is MeansKind.BANK_EXPAND:
        return ExpandBankGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
    raise ValueError(f"Unknown MeansKind: {kind!r}")
```

In the `StrategyArbiter.select` method, update **both** `map_means(...)` call sites (the collect-reward loop and the discretionary loop, ~lines 193-198) to pass `state`:

```python
        for mk in collect_kinds:
            candidates.append((map_means(mk, game_data, ctx, state), True))
        if step_goal is not None:
            candidates.append((step_goal, True))
        for mk in discretionary_kinds:
            candidates.append((map_means(mk, game_data, ctx, state), True))
```

In `objective_step_goal`, update the `ReachCharLevel` branch to stand down for items tasks:

```python
    if isinstance(step, ReachCharLevel):
        if ctx.combat_monster is None:
            return None
        if (state.task_type == "items" and state.task_code
                and state.task_total > 0 and state.task_progress < state.task_total):
            return None        # grind can't advance an items task; let PURSUE_TASK run
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp,
                                    game_data=game_data)
```

> The `map_means` test in Step 1 calls `map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)`. Fix the first test (`test_feasible_items_task_maps_to_pursue_task`) to also pass `state` as the 4th arg — it was written before the signature was finalized:
> `goal = map_means(MeansKind.PURSUE_TASK, GameData(), _ctx(), state)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::TestPursueTaskMapping tests/test_ai/test_strategy_driver.py::TestItemsTaskStandDown -v`
Expected: PASS. Then run the whole driver file to catch call-site regressions:
Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q`
Expected: all green (fix any other `map_means` call sites in the test file to pass `state`).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(ai): wire PURSUE_TASK mapping + items-task grind stand-down

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Remove the stale `GrindCharacterXPGoal` task suppression

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` (lines ~50-55)
- Test: `tests/test_ai/test_grind_character_xp.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_grind_character_xp.py` (mirror the file's existing fixture style; `GrindCharacterXPGoal` is constructed with `target_monster`, `initial_xp`, `game_data`):

```python
class TestTaskAgnosticValue:
    def test_value_nonzero_under_monster_task(self):
        # Under a monster task the grind IS the (retargeted) actuator; it must
        # value normally rather than self-suppress to 0.
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0, xp=0)
        goal = GrindCharacterXPGoal(target_monster="chicken", initial_xp=0, game_data=GameData())
        assert goal.value(state, GameData(), None) > 0.0
```

> Confirm the import line and any loadout setup the existing tests use (some tests pass a `game_data` with monster/equipment data so `_loadout_optimal` behaves). Copy that setup from a passing test in the same file so `value` reaches the floor branch and returns `PRIORITY_FLOOR` (30.0) rather than 0 via `is_satisfied`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py::TestTaskAgnosticValue -v`
Expected: FAIL — value is `0.0` because of `if state.task_code: return 0.0`.

- [ ] **Step 3: Remove the blanket suppression**

In `src/artifactsmmo_cli/ai/goals/grind_character_xp.py`, the `value` method currently contains:

```python
        if self.is_satisfied(state):
            return 0.0
        # If there's an active task, FarmItems/CompleteTask own the cycle —
        # this goal stays out of the way until the task is resolved.
        if state.task_code:
            return 0.0
        if history is None:
            return PRIORITY_FLOOR
```

Delete the comment and the `if state.task_code: return 0.0` block, leaving:

```python
        if self.is_satisfied(state):
            return 0.0
        if history is None:
            return PRIORITY_FLOOR
```

> The items-task stand-down now lives solely in `objective_step_goal` (Task 4), the only constructor of this goal. This goal is task-agnostic again.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -q`
Expected: PASS. Some existing tests may have asserted the old "0 under task" behavior — update them to the new task-agnostic semantics (a monster-task grind now values normally).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/grind_character_xp.py tests/test_ai/test_grind_character_xp.py
git commit -m "fix(ai): drop stale blanket task suppression in GrindCharacterXP

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Monster-task grind retarget in the player

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_task_aligned_monster`, `_winnable_farm_target`, imports)
- Test: `tests/test_ai/test_player_task_learning.py` (or a new `tests/test_ai/test_player_retarget.py`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_player_retarget.py`. Construct an `AIPlayer` the way the existing player tests do (copy the construction/`state` assignment idiom from `tests/test_ai/test_player_task_learning.py` — it shows how to build a player with `self.state`, `self.game_data`, `self.history`). The behavior to assert:

```python
"""PURSUE monster-tasks retarget the winnable grind to the task monster."""

from unittest.mock import patch

# ... import AIPlayer + construction helpers mirroring test_player_task_learning.py


def test_pursue_monster_task_retargets_grind(player_factory):
    player = player_factory()      # builds AIPlayer with .state/.game_data/.history
    player.state = player.state.__class__(**{
        **_state_kwargs(player.state),
        "task_code": "yellow_slime", "task_type": "monsters",
        "task_total": 20, "task_progress": 0,
    })
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        assert player._winnable_farm_target() == "yellow_slime"


def test_pivot_monster_task_does_not_retarget(player_factory):
    player = player_factory()
    player.state = player.state.__class__(**{
        **_state_kwargs(player.state),
        "task_code": "yellow_slime", "task_type": "monsters",
        "task_total": 20, "task_progress": 0,
    })
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pivot"), \
         patch.object(player, "_path_aligned_monster", return_value=None), \
         patch.object(player, "_pick_winnable_monster", return_value="chicken"):
        assert player._winnable_farm_target() == "chicken"


def test_items_task_does_not_retarget(player_factory):
    player = player_factory()
    player.state = player.state.__class__(**{
        **_state_kwargs(player.state),
        "task_code": "copper_bar", "task_type": "items",
        "task_total": 20, "task_progress": 0,
    })
    with patch.object(player, "_path_aligned_monster", return_value=None), \
         patch.object(player, "_pick_winnable_monster", return_value="chicken"):
        assert player._winnable_farm_target() == "chicken"
```

> If the existing player tests have a simpler construction path (e.g. a fixture or a `make_player` helper), reuse it instead of inventing `player_factory`/`_state_kwargs`. The three assertions are the contract: PURSUE monster-task → task monster; PIVOT → generic; items → generic.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_retarget.py -v`
Expected: FAIL — `_winnable_farm_target` ignores the task (returns the generic winnable), and/or `task_decision` is not imported in `player.py`.

- [ ] **Step 3: Implement the retarget**

In `src/artifactsmmo_cli/ai/player.py`, add the import (near the other `ai.` imports):

```python
from artifactsmmo_cli.ai.task_decision import PURSUE, task_decision
```

Add the helper method (next to `_winnable_farm_target`):

```python
    def _task_aligned_monster(self) -> str | None:
        """The active task's monster when it's a PURSUE monster-task; else None.

        A PURSUE monster-task is winnable by definition (task_decision returns
        PIVOT for combat-gated tasks), so the objective-step grind can advance it
        directly once retargeted here.
        """
        s = self.state
        if s is None or s.task_type != "monsters" or not s.task_code:
            return None
        if s.task_total == 0 or s.task_progress >= s.task_total:
            return None
        if task_decision(s, self.game_data, self.history) != PURSUE:
            return None
        return s.task_code
```

Update `_winnable_farm_target` to prefer it:

```python
    def _winnable_farm_target(self) -> str | None:
        task_monster = self._task_aligned_monster()
        if task_monster is not None:
            return task_monster
        target = self._path_aligned_monster()
        if target is None or not self._is_winnable(target):
            target = self._pick_winnable_monster()
        return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_player_retarget.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_retarget.py
git commit -m "feat(ai): retarget the grind to the task monster for PURSUE monster-tasks

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: End-to-end arbiter test + full verification

**Files:**
- Test: `tests/test_ai/test_strategy_driver.py` (decisive end-to-end test)

- [ ] **Step 1: Write the decisive end-to-end test**

Add to `tests/test_ai/test_strategy_driver.py`. This reconstructs the observed stall: an items task `copper_bar 0/20`, feasible (no skill gap), and asserts the arbiter selects `PursueTask`, NOT `GrindCharacterXP`. Build the `StrategyArbiter` the way the file's existing arbiter tests do (copy the planner/actions/decision-stub setup from an existing `StrategyArbiter.select` test in this file):

```python
class TestPursueTaskEndToEnd:
    def test_items_task_selects_pursue_not_grind(self):
        # Reconstruct the observed stall: copper_bar 0/20, feasible.
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 5})
        # ... build arbiter + a decision whose chosen_step is ReachCharLevel(50)
        #     and an action list that lets PursueTask plan (gather/craft/trade stubs)
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            goal, plan, _ = arbiter.select(decision, state, game_data, actions, ctx)
        assert repr(goal) == "PursueTask(copper_bar)"
        assert not repr(goal).startswith("GrindCharacterXP")
```

> If wiring a full plannable action set is heavy, assert at the candidate-ordering level instead: with the items PURSUE task active, `objective_step_goal(decision.chosen_step, ...)` is `None` and `PURSUE_TASK` is in `active_means(...)[1]`, so the first discretionary candidate maps to `PursueTask`. Either proves the stall is fixed; prefer the full `select` if the file already has plannable stubs.

- [ ] **Step 2: Run the decisive test**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::TestPursueTaskEndToEnd -v`
Expected: PASS.

- [ ] **Step 3: Full verification gate**

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```
Expected: pytest all green, 0 skipped; ruff clean; mypy ≤ the 129-error pre-existing baseline with **zero new** errors in the changed files (`strategy_driver.py`, `means.py`, `pursue_task.py`, `grind_character_xp.py`, `level_skill.py`, `player.py`).

- [ ] **Step 4: Coverage on changed code**

```bash
uv run pytest tests/test_ai/test_pursue_task_goal.py tests/test_ai/test_tiers_means.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_grind_character_xp.py tests/test_ai/test_player_retarget.py \
  --cov=artifactsmmo_cli.ai.goals.pursue_task \
  --cov=artifactsmmo_cli.ai.tiers.means \
  --cov=artifactsmmo_cli.ai.strategy_driver \
  --cov-report=term-missing -q
```
Expected: 100% on `pursue_task.py`; new lines in `means.py` / `strategy_driver.py` covered. Add tests for any uncovered new line.

- [ ] **Step 5: Grep gate — stale references gone**

```bash
grep -rn "FarmItems/CompleteTask own the cycle" src && echo FAIL || echo "stale comment gone ✓"
grep -rn "current + 1" src/artifactsmmo_cli/ai/strategy_driver.py && echo FAIL || echo "current+1 lifted ✓"
```
Expected: both print the ✓ line.

- [ ] **Step 6: Commit**

```bash
git add tests/test_ai/test_strategy_driver.py
git commit -m "test(ai): end-to-end — items task selects PursueTask not grind

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- **`task_type` values:** the API uses `"items"` and `"monsters"` (the trace that prompted this work showed `task_type: "items"`). The stale docstring in `world_state.py` listing `"resources"/"crafting"` is wrong; ignore it.
- **`task_decision` constants:** `PURSUE = "pursue"`, `PIVOT = "pivot"` (strings). Patch `task_decision` where it is *imported* (`means.py`, `player.py`), not at its definition.
- **`map_means` signature change is breaking:** every call site must pass `state`. The only production call sites are in `StrategyArbiter.select`; update both. Search tests for `map_means(` and fix those too.
- **Verify constructor kwargs** for `ItemStats`, `GatherAction`, `CraftAction`, `FightAction`, `RestAction` against the real classes before finalizing test code — copy from a neighboring passing test rather than guessing.
- **Do not** add a second task-cancel path for unproducible items (Error handling in the spec): the existing `LowYieldCancel`/`TaskCancel` escape hatches cover a genuinely stuck task.
