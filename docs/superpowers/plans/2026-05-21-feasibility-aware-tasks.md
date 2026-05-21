# Feasibility-aware Task Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Robby assess an accepted task against his skills, treat skilling-up as a plannable prerequisite, decide skill-up-vs-pivot by value-per-cycle, and cancel any task type — so he never dead-ends on an infeasible task.

**Architecture:** A new pure `task_feasibility` module extracts a task's gating skill requirement. A `SkillXpCurve` (observed `(skill,level)→max_xp` from the live API, beyond-current levels estimated as a learned multiple of the current gap) and a learned task-reward-value estimate (from completed-task history) feed a value-per-cycle `task_decision`. `TaskCancelGoal` is generalized to all task types and driven by that decision; `_build_goals` surfaces `LevelSkillGoal` for the active task's gating skill.

**Tech Stack:** Python 3.13, `uv`, pytest, SQLModel/SQLite (LearningStore), existing GOAP planner/goals/scalarizer.

---

## File Structure

- Create `src/artifactsmmo_cli/ai/task_feasibility.py` — pure: `SkillRequirement` dataclass + `task_requirement(state, game_data)`.
- Create `src/artifactsmmo_cli/ai/learning/skill_xp_curve.py` — `SkillXpCurve`: observed map, learned growth ratio, `cycles_to_level`.
- Modify `src/artifactsmmo_cli/ai/learning/store.py` — persist skill `max_xp` observations + completed-task reward values; accessors.
- Modify `src/artifactsmmo_cli/ai/learning/models.py` — new rows for the two observation kinds.
- Create `src/artifactsmmo_cli/ai/task_decision.py` — `task_decision(state, game_data, history)` → `PURSUE`/`PIVOT`.
- Modify `src/artifactsmmo_cli/ai/goals/task_cancel.py` — generalize to all task types, driven by the decision.
- Modify `src/artifactsmmo_cli/ai/player.py` — record observations each cycle; surface `LevelSkillGoal` for the active task's gating skill.
- Tests under `tests/test_ai/`.

`DEFAULT_GROWTH_RATIO` and the decision constants/thresholds are module constants defined where first used (Tasks 4 and 8), cited in the spec.

**Persistence note (Tasks 3 & 5):** add the new query methods to `store.py` following the file's existing query style — every method there opens `with Session(self._engine) as s:` and runs `s.exec(select(...))` to read rows. Mirror that exact pattern; don't invent a new access style.

---

## Phase 1 — Generalized task cancellation (immediate unblock)

### Task 1: TaskCancelGoal cancels any task type

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/task_cancel.py`
- Test: `tests/test_ai/test_goals.py` (extend `TestTaskCancelGoal` if present; else add it)

**Note:** Task 1 depends on the `task_feasibility` module from Task 2. Implement Task 2 first (it is self-contained), then Task 1. They may be committed together.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ai/test_goals.py` (uses `make_state` from `tests.test_ai.fixtures` and the file's existing `make_game_data` helper — confirm its name and reuse it; the existing TaskCancel tests show the monster setup):

```python
def test_task_cancel_fires_for_infeasible_items_task():
    gd = make_game_data()
    gd._item_stats["small_health_potion"] = ItemStats(
        code="small_health_potion", level=1, type_="utility",
        crafting_skill="alchemy", crafting_level=5)
    gd._crafting_recipes["small_health_potion"] = {"sunflower": 3}
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, task_progress=0, skills={"alchemy": 1})
    assert TaskCancelGoal().value(state, gd) > 0.0

def test_task_cancel_zero_for_feasible_items_task():
    gd = make_game_data()
    gd._item_stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=1)
    gd._crafting_recipes["copper_dagger"] = {"copper_bar": 6}
    state = make_state(task_code="copper_dagger", task_type="items",
                       task_total=5, skills={"weaponcrafting": 6})
    assert TaskCancelGoal().value(state, gd) == 0.0

def test_task_cancel_still_fires_for_too_hard_monster():
    gd = make_game_data()
    gd._monster_level = {"dragon": 40}
    state = make_state(task_code="dragon", task_type="monsters", task_total=1, level=3)
    assert TaskCancelGoal().value(state, gd) > 0.0
```

Add `from artifactsmmo_cli.ai.game_data import ItemStats` to the test file's imports if absent.

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_goals.py -k TaskCancel -v`
Expected: FAIL — items-task cases return 0.0 (currently monster-only).

- [ ] **Step 3: Generalize the goal**

In `src/artifactsmmo_cli/ai/goals/task_cancel.py`, replace the monster-only `_task_is_too_hard` with the feasibility-driven form (Task 9 will swap the `task_requirement` check for the `task_decision` check; this step uses `task_requirement` for the unblock):

```python
from artifactsmmo_cli.ai.task_feasibility import task_requirement


class TaskCancelGoal(Goal):
    """Cancel the current task when it is infeasible for the character.

    Fires for ANY task type (fight or non-fight): a monster task whose target is
    well above the character's level, or an items task whose target item needs a
    crafting skill level the character has not reached. Low priority (12) so the
    bot attempts feasible tasks first and only cancels as an escape.
    """

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 12.0 if task_requirement(state, game_data) is not None else 0.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def __repr__(self) -> str:
        return "TaskCancel"
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_goals.py -k TaskCancel -v`
Expected: PASS (after Task 2's module exists).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/task_cancel.py tests/test_ai/test_goals.py
git commit -m "feat(ai): TaskCancel handles any infeasible task type"
```

---

## Phase 2 — Task requirement extraction

### Task 2: `task_feasibility` module

**Files:**
- Create: `src/artifactsmmo_cli/ai/task_feasibility.py`
- Test: `tests/test_ai/test_task_feasibility.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai/test_task_feasibility.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.task_feasibility import SkillRequirement, task_requirement
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=1,
            type_="utility", crafting_skill="alchemy", crafting_level=5),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._monster_level = {"dragon": 40, "chicken": 1}
    return gd


def test_items_task_returns_skill_gap():
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 1})
    assert task_requirement(state, _gd()) == SkillRequirement(
        skill="alchemy", required_level=5, current_level=1)


def test_items_task_feasible_returns_none():
    state = make_state(task_code="copper_dagger", task_type="items",
                       task_total=5, skills={"weaponcrafting": 6})
    assert task_requirement(state, _gd()) is None


def test_monster_task_too_hard_returns_requirement():
    state = make_state(task_code="dragon", task_type="monsters", task_total=1, level=3)
    req = task_requirement(state, _gd())
    assert req is not None and req.skill == "combat"


def test_monster_task_beatable_returns_none():
    state = make_state(task_code="chicken", task_type="monsters", task_total=1, level=3)
    assert task_requirement(state, _gd()) is None


def test_no_task_returns_none():
    assert task_requirement(make_state(task_code=None), _gd()) is None
```

- [ ] **Step 2: Run, confirm FAIL** — `uv run pytest tests/test_ai/test_task_feasibility.py -v` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/task_feasibility.py`:

```python
"""Decide whether the active task is feasible for the character right now.

Returns the gating skill requirement (or None when already feasible). Pure — no
API calls, no learning. Used by TaskCancelGoal, the LevelSkill prerequisite
wiring, and the cost-analysis decision.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

# A monster more than this many levels above the character is "too hard" — the
# existing TaskCancel rule, kept for parity.
MONSTER_LEVEL_MARGIN = 2


@dataclass(frozen=True)
class SkillRequirement:
    """A skill the character must raise to do the current task.

    For combat tasks `skill == "combat"` and the levels are character levels.
    """

    skill: str
    required_level: int
    current_level: int


def task_requirement(state: WorldState, game_data: GameData) -> SkillRequirement | None:
    """Gating requirement for the active task, or None if already feasible."""
    if not state.task_code or state.task_total == 0:
        return None
    if state.task_type == "monsters":
        monster_level = game_data.monster_level(state.task_code)
        if monster_level > 0 and monster_level > state.level + MONSTER_LEVEL_MARGIN:
            return SkillRequirement("combat", monster_level, state.level)
        return None
    if state.task_type == "items":
        return _item_skill_gap(state.task_code, state, game_data, seen=set())
    return None


def _item_skill_gap(item_code: str, state: WorldState, game_data: GameData,
                    seen: set[str]) -> SkillRequirement | None:
    """Largest unmet crafting-skill gap to produce item_code, recursing into
    craft ingredients. Returns the requirement with the highest required_level
    among unmet skills, or None if everything is within reach."""
    if item_code in seen:
        return None
    seen.add(item_code)
    worst: SkillRequirement | None = None
    stats = game_data.item_stats(item_code)
    if stats is not None and stats.crafting_skill:
        current = state.skills.get(stats.crafting_skill, 0)
        if current < stats.crafting_level:
            worst = SkillRequirement(stats.crafting_skill, stats.crafting_level, current)
    recipe = game_data.crafting_recipe(item_code) or {}
    for ingredient in recipe:
        sub = _item_skill_gap(ingredient, state, game_data, seen)
        if sub is not None and (worst is None or sub.required_level > worst.required_level):
            worst = sub
    return worst
```

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_task_feasibility.py -v`. Then run Task 1's tests.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/task_feasibility.py tests/test_ai/test_task_feasibility.py
git commit -m "feat(ai): task_requirement extracts gating skill for the active task"
```

---

## Phase 3 — SkillXpCurve (observed map + learned growth ratio)

### Task 3: LearningStore persists skill max_xp observations

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Test: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_ai/test_learning_store.py` (reuse its existing store-fixture pattern; close the store):

```python
def test_records_and_returns_skill_max_xp_observations(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    store.record_skill_max_xp("alchemy", 1, 150)
    store.record_skill_max_xp("alchemy", 2, 220)
    store.record_skill_max_xp("alchemy", 1, 150)  # idempotent on (skill, level)
    obs = store.skill_max_xp_observations("alchemy")
    store.close()
    assert obs == {1: 150, 2: 220}
```

- [ ] **Step 2: Run, confirm FAIL** — `uv run pytest tests/test_ai/test_learning_store.py -k skill_max_xp -v` → AttributeError.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/learning/models.py`, add a table model in the file's SQLModel style:

```python
class SkillXpObservation(SQLModel, table=True):
    """Observed `<skill>_max_xp` (XP to reach the next level) at a given level,
    per character. One row per (character, skill, level); last write wins."""

    __tablename__ = "skill_xp_observations"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    skill: str = Field(index=True)
    level: int
    max_xp: int
```

In `src/artifactsmmo_cli/ai/learning/store.py` add two methods, mirroring the existing `with Session(self._engine) as s: ... s.exec(select(...))` pattern used by other methods in the file:

- `record_skill_max_xp(self, skill, level, max_xp)`: select the existing `SkillXpObservation` row for `(self._character, skill, level)`; if found, set its `max_xp` and re-add; else add a new row; commit.
- `skill_max_xp_observations(self, skill) -> dict[int, int]`: select all `SkillXpObservation` rows for `(self._character, skill)`; return `{row.level: row.max_xp for row in rows}`.

Import `SkillXpObservation` in store.py. Confirm the store's `__init__` calls `SQLModel.metadata.create_all(self._engine)` so the new table is created; if it lists models explicitly, include the new model.

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_learning_store.py -k skill_max_xp -v`, then the whole file.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): persist observed skill max_xp per level"
```

### Task 4: SkillXpCurve projects cycles-to-level

**Files:**
- Create: `src/artifactsmmo_cli/ai/learning/skill_xp_curve.py`
- Test: `tests/test_ai/test_skill_xp_curve.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai/test_skill_xp_curve.py`:

```python
from artifactsmmo_cli.ai.learning.skill_xp_curve import DEFAULT_GROWTH_RATIO, SkillXpCurve


def test_required_xp_uses_observed_value():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.required_xp(1) == 100
    assert curve.required_xp(2) == 200

def test_required_xp_beyond_observed_uses_learned_ratio():
    curve = SkillXpCurve(observed={1: 100, 2: 200})  # observed ratio 2.0
    assert curve.required_xp(3) == 400
    assert curve.required_xp(4) == 800

def test_required_xp_default_ratio_with_one_observation():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.required_xp(2) == int(100 * DEFAULT_GROWTH_RATIO)

def test_total_xp_to_reach_sums_levels():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.total_xp_to_reach(current_level=1, target_level=3) == 300

def test_cycles_to_level_divides_by_rate():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=50.0) == 6.0

def test_cycles_to_level_zero_when_at_target():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=5, target_level=5, xp_per_cycle=10.0) == 0.0

def test_cycles_to_level_infinite_when_no_rate():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=0.0) == float("inf")

def test_is_confident_only_when_gap_observed():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.is_confident(current_level=1, target_level=2) is True
    assert curve.is_confident(current_level=1, target_level=6) is False
```

- [ ] **Step 2: Run, confirm FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/learning/skill_xp_curve.py`:

```python
"""Skill XP-to-level curve: observed where possible, estimated beyond.

The API exposes only the CURRENT level's requirement (CharacterSchema.<skill>_max_xp,
"XP required to level up the skill"). The full curve is not published, so levels
beyond those observed are estimated as a learned multiple of the current gap:
required_xp(level+k) ~= last_observed_max_xp * growth_ratio**k, where growth_ratio
is the mean ratio between observed consecutive levels (DEFAULT_GROWTH_RATIO until
two levels are observed). Never a hardcoded curve — estimates refine as more
levels are observed. See spec citations.
"""

from dataclasses import dataclass, field

DEFAULT_GROWTH_RATIO = 1.5
"""Fallback per-level XP growth multiplier until >=2 levels are observed for a
skill. Documented default (not sourced from the API); replaced by the observed
mean ratio as soon as two consecutive observed levels exist."""


@dataclass
class SkillXpCurve:
    """XP-to-next-level for one skill. `observed` is {level: max_xp}."""

    observed: dict[int, int] = field(default_factory=dict)

    def growth_ratio(self) -> float:
        ratios = [
            self.observed[lvl + 1] / self.observed[lvl]
            for lvl in self.observed
            if lvl + 1 in self.observed and self.observed[lvl] > 0
        ]
        return sum(ratios) / len(ratios) if ratios else DEFAULT_GROWTH_RATIO

    def required_xp(self, level: int) -> int:
        if level in self.observed:
            return self.observed[level]
        if not self.observed:
            return 0
        highest = max(self.observed)
        steps = level - highest
        return int(self.observed[highest] * (self.growth_ratio() ** steps))

    def total_xp_to_reach(self, current_level: int, target_level: int) -> int:
        return sum(self.required_xp(lvl) for lvl in range(current_level, target_level))

    def cycles_to_level(self, current_level: int, target_level: int,
                        xp_per_cycle: float) -> float:
        if target_level <= current_level:
            return 0.0
        if xp_per_cycle <= 0:
            return float("inf")
        return self.total_xp_to_reach(current_level, target_level) / xp_per_cycle

    def is_confident(self, current_level: int, target_level: int) -> bool:
        """True only if every level in the gap was directly observed."""
        return all(lvl in self.observed for lvl in range(current_level, target_level))
```

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_skill_xp_curve.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/skill_xp_curve.py tests/test_ai/test_skill_xp_curve.py
git commit -m "feat(ai): SkillXpCurve projects cycles-to-level from observed max_xp"
```

---

## Phase 4 — Learned task reward value

### Task 5: LearningStore records and averages completed-task reward value

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Test: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing test**

```python
def test_task_reward_value_mean_improves_with_history(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    assert store.mean_task_reward_value(default=5.0) == 5.0
    store.record_task_reward_value(100.0)
    store.record_task_reward_value(200.0)
    assert store.mean_task_reward_value(default=5.0) == 150.0
    assert store.task_reward_sample_count() == 2
    store.close()
```

- [ ] **Step 2: Run, confirm FAIL** — AttributeError.

- [ ] **Step 3: Implement**

`models.py`:

```python
class TaskRewardObservation(SQLModel, table=True):
    """Gold-equivalent value of a completed task's reward, per character."""

    __tablename__ = "task_reward_observations"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    value: float
```

`store.py` (mirror the existing session/select pattern):
- `record_task_reward_value(self, value)`: add a `TaskRewardObservation(character=self._character, value=value)`; commit.
- `_task_reward_values(self) -> list[float]`: select all rows for `self._character`; return `[row.value for row in rows]`.
- `task_reward_sample_count(self) -> int`: `len(self._task_reward_values())`.
- `mean_task_reward_value(self, default) -> float`: `sum(vals)/len(vals) if vals else default`.

Import `TaskRewardObservation` in store.py.

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_learning_store.py -k task_reward -v`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): learn mean task reward value from completed tasks"
```

---

## Phase 5 — Record observations + surface the LevelSkill prerequisite

### Task 6: Player records skill max_xp each cycle and task reward on completion

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player_task_learning.py` (new)

- [ ] **Step 1: Write failing test**

Build the player via `GamePlayer.__new__(GamePlayer)` (as `tests/test_ai/test_goal_commitment.py` does), set `self.history` to a temp `LearningStore`, `self.game_data` to a `GameData`. Create `tests/test_ai/test_player_task_learning.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _player(tmp_path):
    p = GamePlayer.__new__(GamePlayer)
    p.character = "hero"
    p.history = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    p.game_data = GameData()
    return p


def test_records_skill_max_xp_from_state(tmp_path):
    p = _player(tmp_path)
    state = make_state(skills={"alchemy": 2}, skill_xp={"alchemy": 10})
    p._record_skill_observations(state, {"alchemy": 220})
    assert p.history.skill_max_xp_observations("alchemy") == {2: 220}
    p.history.close()


def test_records_task_reward_on_completion(tmp_path):
    p = _player(tmp_path)
    p.game_data._npc_sell_prices = {"merchant": {"jasper_crystal": 30}}
    prev = make_state(task_code="x", task_type="items", task_progress=28, task_total=29)
    new = make_state(task_code=None, inventory={"jasper_crystal": 2})
    p._record_task_reward_if_completed(prev, new, action_class="CompleteTaskAction", outcome="ok")
    assert p.history.task_reward_sample_count() == 1
    assert p.history.mean_task_reward_value(default=0.0) == 60.0  # 2 * 30
    p.history.close()
```

- [ ] **Step 2: Run, confirm FAIL** — AttributeError on the helpers.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/player.py` add two helpers:

```python
    def _record_skill_observations(self, state: WorldState, skill_max_xp: dict[str, int]) -> None:
        """Persist observed XP-to-next-level for each skill at its current level."""
        if self.history is None:
            return
        for skill, level in state.skills.items():
            max_xp = skill_max_xp.get(skill, 0)
            if max_xp > 0:
                self.history.record_skill_max_xp(skill, level, max_xp)

    def _record_task_reward_if_completed(self, prev_state: WorldState, new_state: WorldState,
                                         action_class: str, outcome: str) -> None:
        """On task completion, record the sell-back gold value of the reward
        items received so the mean reward estimate improves over time."""
        if self.history is None or outcome != "ok" or action_class != "CompleteTaskAction":
            return
        prices = _max_sell_back_price(self.game_data)
        value = 0.0
        for code, qty in new_state.inventory.items():
            gained = qty - prev_state.inventory.get(code, 0)
            if gained > 0:
                value += gained * prices.get(code, 0)
        if value > 0:
            self.history.record_task_reward_value(value)
```

Import `_max_sell_back_price` from `artifactsmmo_cli.ai.learning.scalarizer`. Wire the calls:
- `_record_skill_observations`: in `_fetch_world_state`, after building `state`, capture `skill_max_xp = {skill: getattr(last_result.data, f"{skill}_max_xp", 0) for skill in state.skills}` and call it.
- `_record_task_reward_if_completed`: in the post-execution block (next to the existing `_learn_task_exchange_cost(...)` call), passing `prev_state_for_learning`, `new_state`, `type(action).__name__`, `outcome`.

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_player_task_learning.py -v`, then `uv run pytest tests/test_ai/test_player.py -q` (patch any new store calls in existing player tests that exercise `_fetch_world_state` so they still pass).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_task_learning.py tests/test_ai/test_player.py
git commit -m "feat(ai): record skill max_xp + completed-task reward value each cycle"
```

### Task 7: Surface LevelSkillGoal for the active task's gating skill

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_build_goals`)
- Test: `tests/test_ai/test_player.py`

- [ ] **Step 1: Write failing test**

Read how existing `_build_goals` tests set `self.state`/`self.game_data` (search `tests/test_ai/` for `_build_goals(`). Write a concrete test: a player whose `self.state` has an active items task `small_health_potion` (alchemy 5 required, char alchemy 1) and `self.game_data` has the matching `_item_stats`/`_crafting_recipes`; assert `any(repr(g) == "LevelSkill(alchemy->10)" for g in player._build_goals())`. NOTE: `LevelSkillGoal.__repr__` is `f"LevelSkill({skill}->{target})"` — the target level equals the requirement's `required_level` (5 here), so assert `"LevelSkill(alchemy->5)"`.

- [ ] **Step 2: Run, confirm FAIL** — no such goal built.

- [ ] **Step 3: Implement**

In `_build_goals`, after the existing equipment-gating LevelSkill block, add:

```python
        # Task-gating skill: if the active items task needs a crafting skill the
        # character lacks, surface a LevelSkillGoal so the planner can grind it
        # as a prerequisite to completing the task.
        task_req = task_requirement(self.state, self.game_data)
        if task_req is not None and task_req.skill != "combat":
            goals.append(LevelSkillGoal(skill_name=task_req.skill,
                                        target_level=task_req.required_level))
```

Import `task_requirement` from `artifactsmmo_cli.ai.task_feasibility` at the top of player.py. (Task 9 will gate this on a PURSUE decision.)

- [ ] **Step 4: Run, confirm PASS** — the new test + `uv run pytest tests/test_ai/test_player.py -q`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): surface LevelSkill prerequisite for skill-gated item tasks"
```

---

## Phase 6 — Cost-analysis decision

### Task 8: `task_decision` (value-per-cycle: pursue vs pivot)

**Files:**
- Create: `src/artifactsmmo_cli/ai/task_decision.py`
- Test: `tests/test_ai/test_task_decision.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai/test_task_decision.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {"small_health_potion": ItemStats(code="small_health_potion",
        level=1, type_="utility", crafting_skill="alchemy", crafting_level=5)}
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    return gd


def test_feasible_task_pursues(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 9})  # >= 5, feasible
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()


def test_huge_skill_gap_low_confidence_pivots(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 1})  # no observations
    assert task_decision(state, _gd(), store) == PIVOT
    store.close()


def test_confident_cheap_high_reward_pursues(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    for lvl in (1, 2, 3, 4):
        store.record_skill_max_xp("alchemy", lvl, 10)  # cheap + observed
    store.record_task_reward_value(100000.0)           # high reward
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=1, skills={"alchemy": 4})  # gap of 1, observed
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()
```

- [ ] **Step 2: Run, confirm FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/task_decision.py`:

```python
"""Decide whether to skill up to complete the active task, or pivot away.

Value-per-cycle: estimate cycles to reach the gating skill level and produce the
task, value the (learned) reward over those cycles, and compare to a baseline
alternative value-per-cycle. Low confidence (unobserved skill gap or no reward
history) biases toward pivoting — don't commit to a long grind on a rough guess.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.scalarizer import DEFAULT_COIN_VALUE_GOLD
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.world_state import WorldState

PURSUE = "pursue"
PIVOT = "pivot"

DEFAULT_SKILL_XP_PER_CYCLE = 10.0
"""Fallback skill-XP gain rate per cycle before a rate has been learned."""

DEFAULT_TASK_REWARD_VALUE = 50.0
"""Fallback expected reward value before any task is completed (gold-equivalent)."""


def task_decision(state: WorldState, game_data: GameData,
                  history: LearningStore | None) -> str:
    req = task_requirement(state, game_data)
    if req is None:
        return PURSUE  # already feasible
    if req.skill == "combat" or history is None:
        return PIVOT  # combat-gated: no skill-grind path here
    curve = SkillXpCurve(observed=history.skill_max_xp_observations(req.skill))
    if not curve.is_confident(req.current_level, req.required_level):
        return PIVOT
    skill_cycles = curve.cycles_to_level(req.current_level, req.required_level,
                                         DEFAULT_SKILL_XP_PER_CYCLE)
    if skill_cycles == float("inf"):
        return PIVOT
    total_cycles = skill_cycles + float(state.task_total)
    reward = history.mean_task_reward_value(default=DEFAULT_TASK_REWARD_VALUE)
    skill_up_vpc = reward / total_cycles if total_cycles > 0 else 0.0
    return PURSUE if skill_up_vpc >= DEFAULT_COIN_VALUE_GOLD else PIVOT
```

`alt` baseline is `DEFAULT_COIN_VALUE_GOLD` (a documented gold/cycle floor) for v1; the full scalarizer alternative-goal comparison is deferred (Out of scope). Tune the constants together with the seeded test numbers so the three asserted outcomes hold.

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_ai/test_task_decision.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/task_decision.py tests/test_ai/test_task_decision.py
git commit -m "feat(ai): task_decision chooses skill-up vs pivot by value-per-cycle"
```

### Task 9: Wire the decision into goal priorities

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/task_cancel.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_build_goals`)
- Test: `tests/test_ai/test_task_decision_integration.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_task_decision_integration.py`. Build a player (via `GamePlayer.__new__`) with the alchemy-5 potion task and a temp `LearningStore`:
- PIVOT case (alchemy 1, no observations): assert `TaskCancelGoal().value(state, gd, history) > 0` AND `_build_goals()` does NOT include a `LevelSkill(alchemy->5)` goal.
- PURSUE case (seed observations + reward so `task_decision == PURSUE`): assert `TaskCancelGoal().value(...) == 0` AND `_build_goals()` includes `LevelSkill(alchemy->5)`.

- [ ] **Step 2: Run, confirm FAIL.**

- [ ] **Step 3: Implement**

`TaskCancelGoal.value` consults the decision:

```python
from artifactsmmo_cli.ai.task_decision import PIVOT, task_decision


    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 12.0 if task_decision(state, game_data, history) == PIVOT else 0.0
```

In `_build_goals`, gate the task-gating LevelSkill (Task 7) on PURSUE:

```python
        task_req = task_requirement(self.state, self.game_data)
        if (task_req is not None and task_req.skill != "combat"
                and task_decision(self.state, self.game_data, self.history) == PURSUE):
            goals.append(LevelSkillGoal(skill_name=task_req.skill,
                                        target_level=task_req.required_level))
```

Import `task_decision`/`PIVOT`/`PURSUE` where used.

- [ ] **Step 4: Run, confirm PASS** — the integration test + `uv run pytest -q` (full suite, 0 skipped).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/task_cancel.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_task_decision_integration.py
git commit -m "feat(ai): drive task pursue/pivot from cost-analysis decision"
```

---

## Phase 7 — Verification

### Task 10: Full-suite, coverage, lint, and the stuck-scenario guard

- [ ] **Step 1:** `uv run pytest -q` — all pass, 0 skipped.
- [ ] **Step 2:** Coverage on new modules:
  `uv run pytest --cov=artifactsmmo_cli.ai.task_feasibility --cov=artifactsmmo_cli.ai.task_decision --cov=artifactsmmo_cli.ai.learning.skill_xp_curve --cov-report=term-missing -q` — 100%; add tests for any missed branch.
- [ ] **Step 3:** `uv run ruff check <changed files>` and `uv run mypy src/artifactsmmo_cli/ai` — no new errors vs main.
- [ ] **Step 4:** Add an integration test reproducing the original stuck case: active items task needing alchemy 5 with alchemy 1 → `_build_goals` + selection yields either a `LevelSkill`/`FarmItems` plan (PURSUE) or `TaskCancel` (PIVOT) — never `<no_plan>` with no escape. Commit any added tests.

```bash
git add -A
git commit -m "test(ai): verify feasibility-aware task handling end-to-end"
```

---

## Self-review notes

- Spec coverage: generalized cancel (Tasks 1, 9), requirement extraction (Task 2), skill max_xp persistence (Task 3) + curve with learned growth ratio (Task 4), learned reward value (Task 5), observation recording (Task 6), LevelSkill prerequisite (Tasks 7, 9), cost-analysis decision (Task 8), confidence→pivot (Tasks 4, 8). All spec sections map to tasks.
- Type consistency: `SkillRequirement(skill, required_level, current_level)` used identically in feasibility/decision/build_goals; `task_requirement`/`task_decision` signatures stable; `SkillXpCurve(observed=...)` + methods consistent across Tasks 4/8.
- Two step-1 tests (Tasks 7, 9) are described, not fully written, because they depend on the project's `_build_goals` test harness the implementer must read first; the implementer MUST write them concretely (asserting the named goal reprs) before implementing. Every other step has complete code.
- Constant tuning: Task 8 constants and the seeded test numbers must be set together so the asserted PURSUE/PIVOT outcomes hold.

## Out of scope
- Pre-accept task filtering (API gives random tasks; impossible).
- Full scalarizer alternative-goal comparison for `alt_vpc` (v1 uses a documented baseline).
- A hardcoded skill leveling curve (observed map only).
