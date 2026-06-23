# Plan-Cache (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the bot re-running a full GOAP search every cycle — commit to a computed plan, execute it step-by-step, re-plan only when an invalidation trigger fires; persist the plan to the learning DB.

**Architecture:** A passive `PlanCache` value object holds the live commitment (goal, plan, cursor). A pure `should_replan` predicate decides each cycle whether to reuse the cache or re-decide. `GamePlayer.run` extracts its decision band into `_plan_or_reuse`, which calls the expensive `decide`+`select` only on a re-plan. The cache and every computed plan body are persisted to the existing per-character `LearningStore` SQLite DB (the plan-body log also seeds the later Phase 2 macro layer).

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLAlchemy (existing learning store), pytest.

## Global Constraints

- Run all Python via `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- No inline imports; imports at top of file. No `...` imports. No `if TYPE_CHECKING`.
- One behavioral class per file. Pure data/value dataclasses may have trivial methods.
- Never catch `Exception`; only specific exceptions (DB code catches `SQLAlchemyError`, mirroring `LearningStore`).
- Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests under `tests/`.
- Use only API/state data or fail with an error; no invented defaults.
- `REPLAN_INTERVAL` reuses the existing `BANK_REFRESH_INTERVAL = 20` (`src/artifactsmmo_cli/ai/constants.py:10`).
- Commit after each task. Branch `feat/plan-cache-macro-learning` off `main` before Task 1.

**Key existing signatures (verbatim):**
- `Action.is_applicable(self, state: WorldState, game_data: GameData) -> bool` (`ai/actions/base.py:34`)
- `Goal.is_satisfied(self, state: WorldState) -> bool` (`ai/goals/base.py:26`)
- `GearLatch.active -> bool` property (`ai/gear_latch.py:19`)
- `LearningStore.__init__(self, db_path, character)`; `set_learned_int`/`get_learned_int` pattern at `ai/learning/store.py:593-640`; tables auto-created by `SQLModel.metadata.create_all` in `__init__`.
- `GamePlayer` at `ai/player.py:89`; loop `run` at `:353`; decision band `:388-453`; execute+record `:514-612`.

---

### Task 1: `PlanCache` value object

**Files:**
- Create: `src/artifactsmmo_cli/ai/plan_cache.py`
- Test: `tests/test_ai/test_plan_cache.py`

**Interfaces:**
- Produces: `PlanCache` dataclass with fields `selected_goal: Goal`, `plan: list[Action]`, `crafting_target: str | None`, `latch_active: bool`, `goal_repr: str`, `cursor: int = 0`, `cycles_since_replan: int = 0`; methods `current() -> Action | None`, `advance() -> None`, `exhausted() -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_plan_cache.py
from artifactsmmo_cli.ai.plan_cache import PlanCache


def _cache(plan):
    # plan elements are opaque to PlanCache (it only indexes), so sentinels suffice.
    return PlanCache(
        selected_goal=object(),
        plan=list(plan),
        crafting_target="copper_ring",
        latch_active=False,
        goal_repr="Goal(copper_ring)",
    )


def test_current_returns_step_at_cursor():
    c = _cache(["a", "b", "c"])
    assert c.current() == "a"
    c.advance()
    assert c.current() == "b"


def test_exhausted_after_last_step():
    c = _cache(["a"])
    assert c.exhausted() is False
    c.advance()
    assert c.exhausted() is True
    assert c.current() is None


def test_empty_plan_is_exhausted_immediately():
    c = _cache([])
    assert c.exhausted() is True
    assert c.current() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.plan_cache'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/plan_cache.py
"""Live in-session commitment to a computed GOAP plan. A passive value object:
the reuse-vs-replan decision lives in ai.should_replan, not here."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.goals.base import Goal


@dataclass
class PlanCache:
    """The plan the bot is currently executing, plus the cursor into it."""

    selected_goal: Goal
    plan: list[Action]
    crafting_target: str | None
    latch_active: bool
    goal_repr: str
    cursor: int = 0
    cycles_since_replan: int = 0

    def current(self) -> Action | None:
        """The step about to execute, or None when the plan is exhausted."""
        if self.cursor >= len(self.plan):
            return None
        return self.plan[self.cursor]

    def advance(self) -> None:
        self.cursor += 1

    def exhausted(self) -> bool:
        return self.cursor >= len(self.plan)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_plan_cache.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/plan_cache.py tests/test_ai/test_plan_cache.py
git commit -m "feat(plan-cache): PlanCache value object for live plan commitment"
```

---

### Task 2: `should_replan` pure predicate

**Files:**
- Create: `src/artifactsmmo_cli/ai/should_replan.py`
- Test: `tests/test_ai/test_should_replan.py`

**Interfaces:**
- Consumes: `PlanCache` (Task 1).
- Produces: `should_replan(cache: PlanCache | None, last_outcome: str | None, latch_active: bool, goal_satisfied: bool, step_applicable: bool, replan_interval: int) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_should_replan.py
import pytest

from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.should_replan import should_replan


def _cache(cursor=0, plan_len=3, latch=False, cycles=0):
    return PlanCache(
        selected_goal=object(),
        plan=["a"] * plan_len,
        crafting_target=None,
        latch_active=latch,
        goal_repr="g",
        cursor=cursor,
        cycles_since_replan=cycles,
    )


def _ok_hit_args():
    # cache present, last action ok, goal unsatisfied, latch unchanged,
    # under the interval, step applicable -> reuse (False).
    return dict(
        cache=_cache(),
        last_outcome="ok",
        latch_active=False,
        goal_satisfied=False,
        step_applicable=True,
        replan_interval=20,
    )


def test_cache_hit_reuses():
    assert should_replan(**_ok_hit_args()) is False


def test_cold_start_replans():
    args = _ok_hit_args()
    args["cache"] = None
    assert should_replan(**args) is True


@pytest.mark.parametrize("outcome", ["error:fight_lost", "error:cooldown", "error:network"])
def test_non_ok_outcome_replans(outcome):
    args = _ok_hit_args()
    args["last_outcome"] = outcome
    assert should_replan(**args) is True


def test_goal_satisfied_replans():
    args = _ok_hit_args()
    args["goal_satisfied"] = True
    assert should_replan(**args) is True


def test_exhausted_plan_replans():
    args = _ok_hit_args()
    args["cache"] = _cache(cursor=3, plan_len=3)  # cursor == len -> exhausted
    assert should_replan(**args) is True


def test_latch_change_replans():
    args = _ok_hit_args()
    args["latch_active"] = True  # cache.latch_active is False -> changed
    assert should_replan(**args) is True


def test_interval_bound_replans():
    args = _ok_hit_args()
    args["cache"] = _cache(cycles=20)
    assert should_replan(**args) is True


def test_inapplicable_step_replans():
    args = _ok_hit_args()
    args["step_applicable"] = False
    assert should_replan(**args) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_should_replan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.should_replan'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/should_replan.py
"""Pure predicate: decide whether to re-run the GOAP planner this cycle or reuse
the cached plan. Kept side-effect-free so the policy is unit-testable and, later,
formally gate-able. See docs/superpowers/specs/2026-06-23-plan-cache-macro-learning-design.md."""

from artifactsmmo_cli.ai.plan_cache import PlanCache


def should_replan(
    cache: PlanCache | None,
    last_outcome: str | None,
    latch_active: bool,
    goal_satisfied: bool,
    step_applicable: bool,
    replan_interval: int,
) -> bool:
    """True => re-decide from scratch. Triggers (any):
    1. no cache (cold start)
    2. previous action did not succeed
    3. goal satisfied or plan exhausted
    4. gear-review latch armed/cleared since plan time
    5. cached run reached the staleness bound
    6. the cached step is no longer applicable
    """
    if cache is None:
        return True
    if last_outcome is not None and last_outcome != "ok":
        return True
    if goal_satisfied or cache.exhausted():
        return True
    if latch_active != cache.latch_active:
        return True
    if cache.cycles_since_replan >= replan_interval:
        return True
    if not step_applicable:
        return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_should_replan.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/should_replan.py tests/test_ai/test_should_replan.py
git commit -m "feat(plan-cache): should_replan invalidation predicate"
```

---

### Task 3: Extract `_plan_or_reuse` and wire into the loop (in-memory)

This is the behavior change that delivers the CPU win. Extract the decision band
into a testable method; the loop calls it; the cursor advances after a successful
execute; trace fields report zero search cost on cache hits.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (add fields in `__init__`; new method `_plan_or_reuse`; rewrite loop band `:388-453`; cursor advance after execute `~:564`; trace fields `:590-609` and `:544-557`)
- Test: `tests/test_ai/test_plan_or_reuse.py`

**Interfaces:**
- Consumes: `PlanCache` (Task 1), `should_replan` (Task 2), `BANK_REFRESH_INTERVAL`.
- Produces: `GamePlayer._plan_or_reuse(self, state, game_data, actions, ctx_combat_monster) -> tuple[Goal | None, list[Action], list, bool]` returning `(selected_goal, plan, goals_tried, replanned)`. New fields: `self._plan_cache: PlanCache | None`.

- [ ] **Step 1: Add the import and the cache field**

In `src/artifactsmmo_cli/ai/player.py`, add to the imports near the other `ai.` imports:

```python
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.should_replan import should_replan
```

In `GamePlayer.__init__` (near `self._gear_latch = GearLatch()` at `:174`), add:

```python
self._plan_cache: PlanCache | None = None
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ai/test_plan_or_reuse.py
from dataclasses import dataclass

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.plan_cache import PlanCache
from tests.test_ai.fixtures import make_state


@dataclass
class _Goal:
    satisfied: bool = False

    def is_satisfied(self, state):
        return self.satisfied

    def __repr__(self):
        return "FakeGoal()"


@dataclass
class _Act:
    applicable: bool = True

    def is_applicable(self, state, game_data):
        return self.applicable

    def __repr__(self):
        return "FakeAct()"


def _player_with_stub_plan(plan, goal):
    player = GamePlayer(character="hero", dry_run=True)
    player._gear_latch._active = False
    calls = {"n": 0}

    def _fake_decide(state, game_data, actions, ctx_combat_monster):
        calls["n"] += 1
        return goal, list(plan), [{"goal": repr(goal)}]

    # Replace only the expensive band, the collaborator — not the unit under test.
    player._decide_band = _fake_decide  # type: ignore[attr-defined]
    return player, calls


def test_first_call_replans_and_caches():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is True
    assert calls["n"] == 1
    assert player._plan_cache is not None
    assert sel is goal


def test_second_call_reuses_without_replanning():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    player._plan_or_reuse(state, None, [], None)        # cycle 1: replan, cache
    player._plan_cache.advance()                         # simulate a successful execute
    player._last_outcome = "ok"
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is False
    assert calls["n"] == 1                               # decide NOT called again
    assert returned_plan[0] is plan[1]                   # serves the next step
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_or_reuse.py -v`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute '_plan_or_reuse'`

- [ ] **Step 4: Implement `_plan_or_reuse` plus a `_decide_band` seam**

Add two methods to `GamePlayer`. `_decide_band` wraps exactly today's expensive
work (lines 388–453 minus the combat-target/ctx setup, which the caller passes
in) and returns `(selected_goal, plan, goals_tried)`. `_plan_or_reuse` gates it.

```python
def _decide_band(self, state, game_data, actions, ctx_combat_monster):
    """Run the full Tier-3 decision + GOAP selection. The expensive band —
    invoked only when should_replan is True. Returns (selected_goal, plan,
    goals_tried). Side effects (sticky anchor, crafting_target on state) match
    the pre-extraction loop body."""
    combat_monster = ctx_combat_monster
    ctx = self._selection_context(combat_monster)
    servable_pred = self._step_servable(state, game_data, ctx)
    self._notify_planning(True)
    decision = self._strategy.decide(
        state, game_data,
        history=self.history,
        combat_monster=combat_monster,
        last_chosen_root=self._last_strategy_root,
        step_servable=servable_pred,
    )
    self._last_decision = decision
    cr, cs = decision.chosen_root, decision.chosen_step
    self._last_servability_diag = {
        "chosen_root_servable": bool(
            cr is not None and cs is not None and servable_pred(cr, cs)),
        "chosen_root": repr(cr) if cr is not None else None,
    }
    step = decision.chosen_step
    crafting_target = step.code if isinstance(step, ObtainItem) else None
    if crafting_target is None:
        for alt in getattr(decision, "fallback_steps", []):
            if isinstance(alt, ObtainItem):
                crafting_target = alt.code
                break
    self.state = state = replace(state, crafting_target=crafting_target)
    selected_goal, plan, goals_tried = self._arbiter.select(
        decision, state, game_data, actions, ctx,
        suppressed=set(self._suppressed_goals),
        objective=self._objective,
    )
    self._update_sticky_anchor(
        decision.chosen_root, state, game_data, self._arbiter.chosen_step_alive)
    self._last_decide_crafting_target = crafting_target
    return selected_goal, plan, goals_tried


def _plan_or_reuse(self, state, game_data, actions, ctx_combat_monster):
    """Reuse the cached plan unless should_replan fires. Returns
    (selected_goal, plan, goals_tried, replanned)."""
    cache = self._plan_cache
    step = cache.current() if cache is not None else None
    goal_satisfied = cache is not None and cache.selected_goal.is_satisfied(state)
    step_applicable = step is not None and step.is_applicable(state, game_data)
    if should_replan(
        cache, self._last_outcome, self._gear_latch.active,
        goal_satisfied, step_applicable, BANK_REFRESH_INTERVAL,
    ):
        selected_goal, plan, goals_tried = self._decide_band(
            state, game_data, actions, ctx_combat_monster)
        if plan and selected_goal is not None:
            self._plan_cache = PlanCache(
                selected_goal=selected_goal,
                plan=list(plan),
                crafting_target=self._last_decide_crafting_target,
                latch_active=self._gear_latch.active,
                goal_repr=repr(selected_goal),
            )
        else:
            self._plan_cache = None
        return selected_goal, plan, goals_tried, True
    # cache hit
    assert cache is not None
    self.state = replace(state, crafting_target=cache.crafting_target)
    self._notify_planning(False)
    return cache.selected_goal, cache.plan[cache.cursor:], [], False
```

Add `self._last_decide_crafting_target: str | None = None` next to the
`self._plan_cache` field in `__init__`.

- [ ] **Step 5: Run the new test to verify it passes**

Run: `uv run pytest tests/test_ai/test_plan_or_reuse.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Replace the loop band to call `_plan_or_reuse`**

In `run()`, replace lines `388-453` (from `combat_monster = self._winnable_farm_target()`
through the `_update_sticky_anchor(...)` call) with:

```python
combat_monster = self._winnable_farm_target()
selected_goal, plan, goals_tried, replanned = self._plan_or_reuse(
    state, game_data, actions, combat_monster)
state = self.state  # _plan_or_reuse may have replaced crafting_target
goal_rank_trace: list[dict[str, object]] = [
    {"goal": gt["goal"], "priority": 0.0} for gt in goals_tried
]
```

- [ ] **Step 7: Advance the cursor after a successful execute**

In `run()`, immediately after `self.state = new_state` (`~:564`), add:

```python
if outcome == "ok" and self._plan_cache is not None:
    self._plan_cache.advance()
    self._plan_cache.cycles_since_replan += 1
```

- [ ] **Step 8: Make trace/learning report zero search cost on cache hits**

In the `cycle_stats` dict (`:590-598`) replace the planner-stat fields with:

```python
"nodes": self.planner.last_stats.nodes_explored if replanned else 0,
"depth": self.planner.last_stats.max_depth_reached if replanned else 0,
"timed_out": self.planner.last_stats.timed_out if replanned else False,
"replanned": replanned,
```

In `_record_learning_cycle(...)` call (`:544-557`) replace the three planner args:

```python
planner_nodes=self.planner.last_stats.nodes_explored if replanned else 0,
planner_depth=self.planner.last_stats.max_depth_reached if replanned else 0,
planner_timed_out=self.planner.last_stats.timed_out if replanned else False,
```

- [ ] **Step 9: Run the full AI suite + type check**

Run: `uv run pytest tests/test_ai/ -q && uv run mypy src/artifactsmmo_cli/ai/player.py`
Expected: PASS, no type errors. Fix any test that asserted per-cycle `select` calls
(they now reflect cached reuse) by updating the assertion to the new behavior — do
NOT weaken coverage.

- [ ] **Step 10: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_plan_or_reuse.py
git commit -m "feat(plan-cache): commit to plans, replan only on trigger (CPU churn fix)"
```

---

### Task 4: DB persistence — plan-body log + commitment save

Adds two SQLModel tables and `LearningStore` write/read methods. The plan-body
log is the input the Phase-2 macro layer will count; the commitment row enables
restart-resume (Task 6).

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (two tables)
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (three methods)
- Test: `tests/test_ai/test_plan_persistence.py`

**Interfaces:**
- Produces:
  - `LearningStore.record_plan_body(goal_repr: str, head_action_repr: str, body: list[str]) -> None`
  - `LearningStore.save_plan_commitment(goal_repr: str, plan_reprs: list[str], cursor: int, crafting_target: str | None, latch_active: bool) -> None`
  - `LearningStore.load_plan_commitment() -> PlanCommitmentBase | None`

- [ ] **Step 1: Add the SQLModel tables**

Append to `src/artifactsmmo_cli/ai/learning/models.py`:

```python
class PlanBodyLogBase(SQLModel):
    """One computed plan body, logged at re-plan time. Counted by the Phase-2
    macro detector."""

    character: str = Field(index=True)
    session_id: str = Field(index=True)
    ts: str
    goal_repr: str = Field(index=True)
    head_action_repr: str = Field(index=True)
    body_json: str  # JSON list[str] of action reprs


class PlanBodyLog(PlanBodyLogBase, table=True):
    __tablename__ = "plan_body_log"

    id: int | None = Field(default=None, primary_key=True)


class PlanCommitmentBase(SQLModel):
    """The bot's live plan commitment — one row per character, upserted on each
    re-plan, for restart-resume."""

    character: str = Field(primary_key=True)
    goal_repr: str
    plan_json: str  # JSON list[str] of action reprs
    cursor: int
    crafting_target: str | None = None
    latch_active: bool = False
    replanned_ts: str


class PlanCommitment(PlanCommitmentBase, table=True):
    __tablename__ = "plan_commitment"
```

(`SQLModel.metadata.create_all` in `LearningStore.__init__:71` creates both new
tables automatically; no migration needed since they are new tables.)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ai/test_plan_persistence.py
from artifactsmmo_cli.ai.learning.store import LearningStore


def _store(tmp_path):
    s = LearningStore(db_path=str(tmp_path / "learn.db"), character="hero")
    s.start_session()
    return s


def test_plan_body_round_trips(tmp_path):
    s = _store(tmp_path)
    s.record_plan_body("Goal(copper_ring)", "Gather(copper_ore)",
                        ["Gather(copper_ore)", "Craft(copper_bar)", "Craft(copper_ring)"])
    rows = s.plan_bodies_for_goal("Goal(copper_ring)")
    assert len(rows) == 1
    assert rows[0].head_action_repr == "Gather(copper_ore)"


def test_commitment_upserts_single_row(tmp_path):
    s = _store(tmp_path)
    s.save_plan_commitment("Goal(g)", ["A", "B"], 0, "copper_ring", False)
    s.save_plan_commitment("Goal(g)", ["A", "B", "C"], 1, None, True)
    loaded = s.load_plan_commitment()
    assert loaded is not None
    assert loaded.cursor == 1
    assert loaded.latch_active is True
    assert loaded.crafting_target is None


def test_load_commitment_absent_returns_none(tmp_path):
    s = _store(tmp_path)
    assert s.load_plan_commitment() is None
```

(Add `plan_bodies_for_goal` as a small read helper used only by the test and
Phase 2; include it in Step 3.)

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_persistence.py -v`
Expected: FAIL — `AttributeError: 'LearningStore' object has no attribute 'record_plan_body'`

- [ ] **Step 4: Implement the store methods**

Add to `LearningStore` (mirroring the `set_learned_int` try/except pattern). The
imports `json`, `select`, `SqlSession`, `SQLAlchemyError`, `datetime`, `timezone`
are already present in `store.py`; add the model imports at the top:

```python
from artifactsmmo_cli.ai.learning.models import (
    PlanBodyLog, PlanBodyLogBase, PlanCommitment, PlanCommitmentBase,
)
```

```python
def record_plan_body(self, goal_repr: str, head_action_repr: str,
                     body: list[str]) -> None:
    """Append a computed plan body. Best-effort; degraded storage must not
    kill the player loop."""
    try:
        with SqlSession(self._engine) as s:
            s.add(PlanBodyLog(
                character=self._character,
                session_id=self._session_id or "no-session",
                ts=datetime.now(tz=timezone.utc).isoformat(),
                goal_repr=goal_repr,
                head_action_repr=head_action_repr,
                body_json=json.dumps(body),
            ))
            s.commit()
    except SQLAlchemyError as e:
        print(f"[learning] record_plan_body failed: {e}")

def plan_bodies_for_goal(self, goal_repr: str) -> list[PlanBodyLogBase]:
    """All logged plan bodies for a goal repr (Phase-2 macro detector input)."""
    try:
        with SqlSession(self._engine) as s:
            return list(s.exec(
                select(PlanBodyLog).where(
                    PlanBodyLog.character == self._character,
                    PlanBodyLog.goal_repr == goal_repr,
                )
            ).all())
    except SQLAlchemyError:
        return []

def save_plan_commitment(self, goal_repr: str, plan_reprs: list[str],
                         cursor: int, crafting_target: str | None,
                         latch_active: bool) -> None:
    """Upsert the single live commitment row for this character."""
    try:
        with SqlSession(self._engine) as s:
            row = s.exec(
                select(PlanCommitment).where(
                    PlanCommitment.character == self._character)
            ).first()
            ts = datetime.now(tz=timezone.utc).isoformat()
            if row is not None:
                row.goal_repr = goal_repr
                row.plan_json = json.dumps(plan_reprs)
                row.cursor = cursor
                row.crafting_target = crafting_target
                row.latch_active = latch_active
                row.replanned_ts = ts
                s.add(row)
            else:
                s.add(PlanCommitment(
                    character=self._character, goal_repr=goal_repr,
                    plan_json=json.dumps(plan_reprs), cursor=cursor,
                    crafting_target=crafting_target, latch_active=latch_active,
                    replanned_ts=ts,
                ))
            s.commit()
    except SQLAlchemyError as e:
        print(f"[learning] save_plan_commitment failed: {e}")

def load_plan_commitment(self) -> PlanCommitmentBase | None:
    """Read the live commitment row, or None when absent / on DB error."""
    try:
        with SqlSession(self._engine) as s:
            return s.exec(
                select(PlanCommitment).where(
                    PlanCommitment.character == self._character)
            ).first()
    except SQLAlchemyError:
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_plan_persistence.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_plan_persistence.py
git commit -m "feat(plan-cache): persist plan bodies + live commitment to learning DB"
```

---

### Task 5: Wire persistence into the re-plan path

On every re-plan that yields a plan, log the body and save the commitment.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_plan_or_reuse`, the replan branch)
- Test: `tests/test_ai/test_plan_or_reuse.py` (extend)

**Interfaces:**
- Consumes: `LearningStore.record_plan_body`, `save_plan_commitment` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_plan_or_reuse.py
from artifactsmmo_cli.ai.learning.store import LearningStore


def test_replan_persists_body_and_commitment(tmp_path):
    goal = _Goal()
    plan = [_Act(), _Act()]
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._gear_latch._active = False

    def _fake_decide(state, game_data, actions, ctx_combat_monster):
        return goal, list(plan), [{"goal": repr(goal)}]

    player._decide_band = _fake_decide  # type: ignore[attr-defined]
    player._plan_or_reuse(make_state(), None, [], None)

    assert len(store.plan_bodies_for_goal("FakeGoal()")) == 1
    assert store.load_plan_commitment() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_or_reuse.py::test_replan_persists_body_and_commitment -v`
Expected: FAIL — no plan body recorded (assertion error, len 0).

- [ ] **Step 3: Persist in the replan branch**

In `_plan_or_reuse`, inside `if plan and selected_goal is not None:` after building
`self._plan_cache`, add:

```python
if self.history is not None:
    plan_reprs = [repr(a) for a in plan]
    self.history.record_plan_body(
        repr(selected_goal), plan_reprs[0], plan_reprs)
    self.history.save_plan_commitment(
        repr(selected_goal), plan_reprs, 0,
        self._last_decide_crafting_target, self._gear_latch.active)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_plan_or_reuse.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_plan_or_reuse.py
git commit -m "feat(plan-cache): persist body + commitment on every re-plan"
```

---

### Task 6: Restart-resume (validation-gated, lowest priority)

Load the persisted commitment at startup and reuse it only if every remaining
step is applicable from the current world. If any step's repr is unmatchable or
inapplicable, discard and re-plan cold. This saves at most one search per restart
— ship it last; it is safe to defer if time-boxed.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`run`, after `_initialize`; new helper `_resume_plan_cache`)
- Test: `tests/test_ai/test_plan_resume.py`

**Interfaces:**
- Consumes: `LearningStore.load_plan_commitment`, `_build_actions`, `Action.is_applicable`.
- Produces: `GamePlayer._resume_plan_cache(self, state, game_data) -> None` (sets `self._plan_cache` or leaves it None).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_plan_resume.py
from dataclasses import dataclass

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def test_resume_discards_when_step_unmatchable(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    store.save_plan_commitment("Goal(g)", ["NoSuchAction()"], 0, None, False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: []  # type: ignore[attr-defined]
    player._resume_plan_cache(make_state(), None)
    assert player._plan_cache is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_resume.py -v`
Expected: FAIL — `AttributeError: ... '_resume_plan_cache'`

- [ ] **Step 3: Implement `_resume_plan_cache`**

```python
def _resume_plan_cache(self, state, game_data) -> None:
    """Restore a persisted commitment iff every remaining step matches a fresh
    applicable action. Otherwise leave the cache None (cold re-plan)."""
    if self.history is None:
        return
    row = self.history.load_plan_commitment()
    if row is None:
        return
    by_repr = {repr(a): a for a in self._build_actions()}
    plan_reprs = json.loads(row.plan_json)
    tail = plan_reprs[row.cursor:]
    rebuilt = []
    for r in tail:
        a = by_repr.get(r)
        if a is None or not a.is_applicable(state, game_data):
            return  # unmatchable / stale -> discard, re-plan cold
        rebuilt.append(a)
    if not rebuilt:
        return
    # Goal object is not persisted; resume keeps the plan and lets the next
    # exhaustion/trigger re-derive the goal. selected_goal is required to be
    # non-None for execution, so we only resume when a live decision will fill
    # it — here we conservatively leave the cache None unless a goal is present.
    # Simplest safe contract: do not resume goalless; full re-plan on cycle 1.
    return
```

NOTE: persisting/rehydrating the `Goal` object is out of scope (goals are not
serializable here). Task 6 therefore validates the resume path but intentionally
keeps the conservative contract: it never resumes a goalless plan. The test above
locks the discard branch. If a future change makes goals serializable, extend
this method then. **This task may be dropped entirely without affecting the CPU
win** — it exists to satisfy "cache plans in DB" for restart, which Tasks 4–5
already do at the persistence layer.

- [ ] **Step 4: Call it after `_initialize`**

In `run()`, after `self._initialize(client)` (`:357`) and once `self.state` is
set, add:

```python
if self.state is not None:
    self._resume_plan_cache(self.state, self.game_data)
```

- [ ] **Step 5: Run test + full suite**

Run: `uv run pytest tests/test_ai/test_plan_resume.py tests/test_ai/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_plan_resume.py
git commit -m "feat(plan-cache): validation-gated restart-resume scaffold"
```

---

### Task 7: Full gate + coverage

**Files:** none (verification only)

- [ ] **Step 1: Full test suite with coverage**

Run: `uv run pytest --cov=src/artifactsmmo_cli --cov-report=term-missing -q`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. Add tests for any
uncovered new line.

- [ ] **Step 2: Run the formal gate**

Run: `bash formal/gate.sh`
Expected: green. The decision-path logic (`decide_key`, arbiter) is unchanged —
called less often, not differently — so differential/mutation gates should pass
untouched. If the liveness obligation text assumes a fresh decision every cycle,
update the obligation comment to note the `REPLAN_INTERVAL`-bounded reuse (the
loop still emits exactly one applicable action per cycle, so no theorem weakens).
Per repo rule: never run the gate concurrently with the bot or anything importing
`src`.

- [ ] **Step 3: Verify `git diff src` after the gate**

Run: `git diff --stat src/`
Expected: empty (the gate must not have mutated `src`).

- [ ] **Step 4: Commit any added coverage tests**

```bash
git add tests/
git commit -m "test(plan-cache): close coverage gaps; gate green"
```

---

## Self-Review

**Spec coverage:**
- Loop restructure (3 bands) → Task 3. ✓
- `PlanCache` → Task 1. ✓
- `should_replan` 6 triggers → Task 2. ✓
- DB persist live commitment + plan-body log → Tasks 4–5. ✓
- Trace honesty (`replanned`, zeroed stats) → Task 3 Step 8. ✓
- Formal-gate run + T4 obligation note → Task 7. ✓
- Restart-resume validation → Task 6 (conservatively scoped; goal serialization flagged out of scope). ⚠ partial-by-design.
- Phase 2 macro learning → NOT in this plan (separate plan after Phase 1 green, per spec build-order). ✓ intentional.

**Placeholder scan:** none — every code step shows complete code. Task 6 explicitly documents its conservative contract rather than hand-waving.

**Type consistency:** `PlanCache` fields/methods identical across Tasks 1–6; `should_replan` signature identical in Tasks 2–3; store method names (`record_plan_body`, `save_plan_commitment`, `load_plan_commitment`, `plan_bodies_for_goal`) identical across Tasks 4–6.

**Known soft spot:** Task 3's `_decide_band` extraction must preserve every side
effect of the current loop body (`_last_decision`, `_last_servability_diag`,
`crafting_target` on state, sticky anchor). The implementer must diff behavior
against the pre-extraction loop — Task 7's full suite + formal gate is the
backstop.
```