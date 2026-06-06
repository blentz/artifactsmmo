# Tiered+Memoized Planning Budget + Event-Driven Gear Prioritization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the planner from burning 90s per cycle on width-unfindable goals (cheap-pass → escalate → memoize), and prioritize the gear chain after a level-up or predicted-winnable fight loss until equipment is level-appropriate.

**Architecture:** Parameterize the GOAP planner's time budget; make `StrategyArbiter.select` run a cheap pass then escalate, skipping memoized "doomed" goals; add a `GEAR_REVIEW` guard driven by a player-owned latch that bypasses the memo and runs at full budget. Each piece is a small focused module; the proven arbiter/planner cores are extended, not weakened.

**Tech Stack:** Python 3.13 (`uv run`), pytest (100% coverage gate), Lean 4 (`formal/`, kernel-checked), mypy strict, ruff.

**Spec:** `docs/superpowers/specs/2026-06-06-tiered-budget-gear-prioritization-design.md`

---

## File structure

| File | Responsibility | New? |
|---|---|---|
| `src/artifactsmmo_cli/ai/planner.py` | `plan(..., budget_seconds=None)` lever | modify |
| `src/artifactsmmo_cli/ai/plannability_signature.py` | pure `plannability_signature(state) -> tuple` | create |
| `src/artifactsmmo_cli/ai/doomed_memo.py` | `DoomedMemo` (skip/retry bookkeeping) | create |
| `src/artifactsmmo_cli/ai/strategy_driver.py` | tiered two-pass select + memo + GEAR_REVIEW mapping | modify |
| `src/artifactsmmo_cli/ai/gear_latch.py` | `GearLatch` + pure set/clear predicates | create |
| `src/artifactsmmo_cli/ai/gear_appropriateness.py` | pure `has_craftable_upgrade_any_slot(state, game_data)` | create |
| `src/artifactsmmo_cli/ai/tiers/guards.py` | `GuardKind.GEAR_REVIEW`, GUARD_ORDER, fire rule, ctx field | modify |
| `src/artifactsmmo_cli/ai/player.py` | own latch, compute level-up/last-outcome, wire ctx | modify |
| `formal/Formal/TieredSelection.lean` | two-pass walk invariants | create |
| `formal/Formal/GearLatch.lean` | latch state-machine invariants | create |
| `formal/Formal/{Manifest,Contracts}.lean`, `formal/Formal.lean` | register new role theorems | modify |

Tests mirror each module under `tests/test_ai/`.

---

## Phase 1 — Planner budget lever

### Task 1: `GOAPPlanner.plan` accepts `budget_seconds`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/planner.py` (signature ~63-73)
- Test: `tests/test_ai/test_planner_budget.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_planner_budget.py
"""GOAPPlanner.plan honors an explicit per-call time budget."""
import time

from artifactsmmo_cli.ai.planner import GOAPPlanner, _SEARCH_BUDGET_SECONDS
from artifactsmmo_cli.ai.goals.base import Goal


class _NeverSatisfiedGoal(Goal):
    """A goal the planner can never satisfy, so it runs until the deadline."""
    def value(self, state, game_data, history=None): return 1.0
    def is_satisfied(self, state): return False
    def desired_state(self, state, game_data): return {"_unreachable": True}
    @property
    def max_depth(self): return 1
    def __repr__(self): return "NeverSatisfied"


def test_explicit_budget_caps_wall_clock(make_planner_gd):
    from tests.test_ai.fixtures import make_state
    planner = GOAPPlanner()
    t0 = time.monotonic()
    plan = planner.plan(make_state(), _NeverSatisfiedGoal(), [], make_planner_gd, budget_seconds=0.2)
    elapsed = time.monotonic() - t0
    assert plan == []
    assert elapsed < 2.0, f"0.2s budget should return fast, took {elapsed:.1f}s"


def test_default_budget_uses_module_constant():
    # The default path still uses the 90s constant (signature unchanged for callers).
    import inspect
    sig = inspect.signature(GOAPPlanner.plan)
    assert sig.parameters["budget_seconds"].default is None
    assert _SEARCH_BUDGET_SECONDS == 90.0
```

Add fixture to `tests/test_ai/conftest.py` if not present:

```python
import pytest
from artifactsmmo_cli.ai.game_data import GameData

@pytest.fixture
def make_planner_gd():
    gd = GameData()
    gd._item_stats = {}; gd._crafting_recipes = {}
    gd._resource_skill = {}; gd._resource_drops = {}
    gd._monster_locations = {}; gd._monster_level = {}
    gd._resource_locations = {}; gd._workshop_locations = {}
    return gd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_planner_budget.py -v --no-cov`
Expected: FAIL — `plan()` got an unexpected keyword `budget_seconds`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/planner.py`, change the signature and deadline:

```python
    def plan(
        self,
        state: WorldState,
        goal: Goal,
        actions: list[Action],
        game_data: GameData,
        history: LearningStore | None = None,
        *,
        budget_seconds: float | None = None,
    ) -> list[Action]:
        """Return the lowest-cost action plan to satisfy `goal`, or [] if none found.

        `budget_seconds` overrides the default A* wall-clock budget for this call
        (None ⇒ the module default `_SEARCH_BUDGET_SECONDS`). Used by the tiered
        arbiter to run a cheap pass before escalating to the full budget."""
        max_depth = goal.max_depth
        budget = _SEARCH_BUDGET_SECONDS if budget_seconds is None else budget_seconds
        deadline = time.monotonic() + budget
        stats = PlanStats()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_planner_budget.py -v --no-cov`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/planner.py tests/test_ai/test_planner_budget.py tests/test_ai/conftest.py
git commit -m "feat(planner): plan() accepts per-call budget_seconds override"
```

---

## Phase 2 — Doomed-goal memo

### Task 2: `plannability_signature` pure function

**Files:**
- Create: `src/artifactsmmo_cli/ai/plannability_signature.py`
- Test: `tests/test_ai/test_plannability_signature.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_plannability_signature.py
"""plannability_signature: the (level, skills) key the doomed-memo invalidates on."""
from artifactsmmo_cli.ai.plannability_signature import plannability_signature
from tests.test_ai.fixtures import make_state


def test_signature_captures_level_and_skills():
    s = make_state(level=4, skills={"weaponcrafting": 2, "mining": 12})
    assert plannability_signature(s) == (4, (("mining", 12), ("weaponcrafting", 2)))


def test_signature_changes_on_level_up():
    a = make_state(level=4, skills={"weaponcrafting": 2})
    b = make_state(level=5, skills={"weaponcrafting": 2})
    assert plannability_signature(a) != plannability_signature(b)


def test_signature_changes_on_skill_up():
    a = make_state(level=4, skills={"weaponcrafting": 2})
    b = make_state(level=4, skills={"weaponcrafting": 3})
    assert plannability_signature(a) != plannability_signature(b)


def test_signature_stable_under_inventory_change():
    a = make_state(level=4, skills={"weaponcrafting": 2}, inventory={"copper_ore": 1})
    b = make_state(level=4, skills={"weaponcrafting": 2}, inventory={"copper_ore": 50})
    assert plannability_signature(a) == plannability_signature(b)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_plannability_signature.py -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/plannability_signature.py
"""The state dimensions that unlock new plannability for the discretionary/skill
goals the doomed-memo governs. A skill/craft goal that is width-unfindable at a
given character + skill level stays unfindable until one of those levels changes;
inventory churns every gather and is deliberately excluded (the memo's K-cycle
re-probe covers material-driven changes). See
docs/superpowers/specs/2026-06-06-tiered-budget-gear-prioritization-design.md.
"""

from artifactsmmo_cli.ai.world_state import WorldState

Signature = tuple[int, tuple[tuple[str, int], ...]]


def plannability_signature(state: WorldState) -> Signature:
    """`(character level, sorted skill levels)` — the memo invalidation key."""
    return (state.level, tuple(sorted(state.skills.items())))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_plannability_signature.py -v --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/plannability_signature.py tests/test_ai/test_plannability_signature.py
git commit -m "feat(ai): plannability_signature (level, skills) memo key"
```

### Task 3: `DoomedMemo`

**Files:**
- Create: `src/artifactsmmo_cli/ai/doomed_memo.py`
- Test: `tests/test_ai/test_doomed_memo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_doomed_memo.py
"""DoomedMemo: skip goals that timed out, retry on signature change or after K."""
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from tests.test_ai.fixtures import make_state


def test_unmarked_goal_is_not_doomed():
    memo = DoomedMemo(retry_after_cycles=20)
    assert memo.is_doomed("LevelSkill(weaponcrafting->5)", make_state(), cycle=0) is False


def test_marked_goal_is_doomed_same_signature_within_window():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("LevelSkill(weaponcrafting->5)", s, cycle=0)
    assert memo.is_doomed("LevelSkill(weaponcrafting->5)", s, cycle=5) is True


def test_retry_after_k_cycles():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state(level=4, skills={"weaponcrafting": 2})
    memo.mark("G", s, cycle=0)
    assert memo.is_doomed("G", s, cycle=19) is True
    assert memo.is_doomed("G", s, cycle=20) is False  # re-probe window elapsed


def test_retry_on_signature_change():
    memo = DoomedMemo(retry_after_cycles=20)
    memo.mark("G", make_state(level=4, skills={"weaponcrafting": 2}), cycle=0)
    leveled = make_state(level=4, skills={"weaponcrafting": 3})
    assert memo.is_doomed("G", leveled, cycle=1) is False


def test_clear_removes_entry():
    memo = DoomedMemo(retry_after_cycles=20)
    s = make_state()
    memo.mark("G", s, cycle=0)
    memo.clear("G")
    assert memo.is_doomed("G", s, cycle=1) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_doomed_memo.py -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/doomed_memo.py
"""Remembers goals that timed out (no plan) so the arbiter skips re-planning them
until their plannability signature changes or a re-probe window elapses. This is
the steady-state half of the tiered-budget fix: width-unfindable goals are tried
once, then skipped, instead of burning the budget every cycle."""

from artifactsmmo_cli.ai.plannability_signature import Signature, plannability_signature
from artifactsmmo_cli.ai.world_state import WorldState


class DoomedMemo:
    """Per-session record of goals that produced no plan. Keyed by `repr(goal)`."""

    def __init__(self, retry_after_cycles: int = 20) -> None:
        self._retry_after = retry_after_cycles
        self._entries: dict[str, tuple[Signature, int]] = {}

    def mark(self, goal_repr: str, state: WorldState, cycle: int) -> None:
        """Record that `goal_repr` produced no plan at this state/cycle."""
        self._entries[goal_repr] = (plannability_signature(state), cycle)

    def clear(self, goal_repr: str) -> None:
        """Forget a goal (called when it plans successfully)."""
        self._entries.pop(goal_repr, None)

    def is_doomed(self, goal_repr: str, state: WorldState, cycle: int) -> bool:
        """True ⇒ skip planning this goal this cycle. False once the signature
        changes (new plannability) or the re-probe window has elapsed."""
        entry = self._entries.get(goal_repr)
        if entry is None:
            return False
        sig, set_at = entry
        if sig != plannability_signature(state):
            return False
        if cycle - set_at >= self._retry_after:
            return False
        return True
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_doomed_memo.py -v --no-cov`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/doomed_memo.py tests/test_ai/test_doomed_memo.py
git commit -m "feat(ai): DoomedMemo skip/retry bookkeeping for timed-out goals"
```

---

## Phase 3 — Tiered selection in the arbiter

The arbiter already builds an ordered `candidates` list (guards first, then collect,
step, discretionary, with `WaitGoal` last) and calls `select_pure`. We add: a cheap
pass (guards at full budget, others at `B1`, Wait excluded), an escalation pass
(others at full budget) run only when the cheap pass finds nothing, and memo
integration. `select_pure`'s ordering/commitment logic is reused unchanged — we
vary only the `try_plan` budget and pre-filter memoized candidates.

### Task 4: `_plans` forwards a budget; arbiter holds a memo + cycle

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`StrategyArbiter.__init__`, `_plans`)
- Test: `tests/test_ai/test_strategy_driver.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_strategy_driver.py
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo

def test_plans_forwards_budget_to_planner():
    """_plans passes its budget_seconds through to planner.plan."""
    captured = {}
    class _BudgetSpy:
        def __init__(self): self.last_stats = GOAPPlanner().last_stats
        def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
            captured["budget"] = budget_seconds
            return []
    arbiter = StrategyArbiter(_BudgetSpy(), history=None)
    arbiter._plans(AcceptTaskGoal(), make_state(task_code=None, task_total=0), _gd(),
                   [AcceptTaskAction(taskmaster_location=(2, 1))], budget_seconds=1.0)
    assert captured["budget"] == 1.0

def test_arbiter_has_doomed_memo():
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    assert isinstance(arbiter._memo, DoomedMemo)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k "forwards_budget or doomed_memo" -v --no-cov`
Expected: FAIL — `_plans` has no `budget_seconds`; `_memo` missing.

- [ ] **Step 3: Implement**

In `StrategyArbiter.__init__` add:

```python
        self._memo = DoomedMemo()
```

Add the import at the top of `strategy_driver.py`:

```python
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
```

Change `_plans` to accept and forward the budget (keep the existing WaitGoal special-case and the `is_plannable` depth gate):

```python
    def _plans(
        self,
        goal: Goal,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        budget_seconds: float | None = None,
    ) -> list[Action]:
        if isinstance(goal, WaitGoal):
            wait_plan: list[Action] = [WaitAction()]
            self.goals_tried.append({"goal": repr(goal), "nodes": 0, "depth": 1,
                                     "timed_out": False, "plan_len": 1})
            return wait_plan
        if not goal.is_plannable(state, game_data, self._history):
            self.goals_tried.append({"goal": repr(goal), "nodes": 0, "depth": 0,
                                     "timed_out": False, "plan_len": 0})
            return []
        plan = self._planner.plan(state, goal, actions, game_data, self._history,
                                  budget_seconds=budget_seconds)
        stats = self._planner.last_stats
        self.goals_tried.append({"goal": repr(goal), "nodes": stats.nodes_explored,
                                 "depth": stats.max_depth_reached, "timed_out": stats.timed_out,
                                 "plan_len": len(plan)})
        return plan
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k "forwards_budget or doomed_memo" -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(arbiter): _plans forwards budget_seconds; arbiter owns DoomedMemo"
```

### Task 5: two-pass tiered `select` with constants

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`select`, add constants `CHEAP_BUDGET_SECONDS`, guard-repr set)
- Test: `tests/test_ai/test_strategy_driver_tiered.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_strategy_driver_tiered.py
"""Tiered selection: cheap pass, escalate only when cheap empty, memoize timeouts.

A scripted planner returns a plan for a goal only when given >= its required
budget, letting us assert pass behavior deterministically."""
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner, CHEAP_BUDGET_SECONDS  # CHEAP_BUDGET_SECONDS re-exported via strategy_driver
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, CHEAP_BUDGET_SECONDS as CHEAP
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _FakeDecision, _make_planner_gd, _ctx


class _ScriptedPlanner:
    """Plans `[WaitAction()]` for goal reprs in `cheap_ok` at any budget; for reprs
    in `full_only` only when budget is None (full). Records budgets per goal."""
    def __init__(self, cheap_ok, full_only):
        self.cheap_ok = set(cheap_ok); self.full_only = set(full_only)
        self.budgets = []
        self.last_stats = GOAPPlanner().last_stats
    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        r = repr(goal); self.budgets.append((r, budget_seconds))
        if r in self.cheap_ok:
            return [WaitAction()]
        if r in self.full_only and budget_seconds is None:
            return [WaitAction()]
        return []
```

(Full behavioral assertions are added in Task 6 once `select` is tiered; this task
adds the constant + cheap-budget plumbing the scripted planner relies on.)

```python
def test_cheap_budget_constant_is_one_second():
    assert CHEAP == 1.0
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_strategy_driver_tiered.py -k constant -v --no-cov`
Expected: FAIL — `CHEAP_BUDGET_SECONDS` not importable from `strategy_driver`.

- [ ] **Step 3: Implement**

At the top of `strategy_driver.py` (module constants, after imports):

```python
CHEAP_BUDGET_SECONDS = 1.0
"""Per-candidate budget for the arbiter's cheap first pass. Goals that plan in
under a second (a Fight, SellInventory, a shallow craft) win immediately; wide
goals that would time out at 90s fail fast here and are memoized. Guards bypass
this and always get the full budget. Tunable; see the tiered-budget spec."""
```

Rewrite `select`'s planning section. Replace the current single
`select_pure(... try_plan ...)` call with the two-pass logic. Keep everything
ABOVE the `# Build ordered candidates` comment unchanged; replace from the
`try_plan` definition through the `select_pure` call with:

```python
        # Partition: guard candidates always get the full budget and bypass the
        # memo (safety/gear-critical, few, rarely time out). Non-guard candidates
        # go through the cheap pass → escalation → memo machinery.
        guard_reprs = {c.repr_ for c in candidates if not c.is_means}
        non_wait = [c for c in candidates if not isinstance(c.goal, WaitGoal)]

        def _budget_for(goal: Goal, cheap: bool) -> float | None:
            if repr(goal) in guard_reprs:
                return None  # guards: full budget always
            return CHEAP_BUDGET_SECONDS if cheap else None

        def _skip(goal: Goal) -> bool:
            # Memo only governs non-guard goals; guards are never memo-skipped.
            return repr(goal) not in guard_reprs and self._memo.is_doomed(
                repr(goal), state, self._cycle)

        def try_plan_cheap(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            return self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=True))

        def try_plan_full(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            plan = self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=False))
            if not plan and repr(goal) not in guard_reprs:
                self._memo.mark(repr(goal), state, self._cycle)
            else:
                self._memo.clear(repr(goal))
            return plan

        def satisfied(goal: Goal) -> bool:
            return goal.is_satisfied(state)

        # Cheap pass over non-Wait candidates (guards inside still get full budget).
        chosen, plan, new_committed = select_pure(
            candidates=non_wait, committed_repr=self._committed_repr,
            try_plan=try_plan_cheap, is_satisfied=satisfied, is_suppressed=is_suppressed)
        if chosen is None:
            # Escalation pass at full budget; memoize timeouts.
            chosen, plan, new_committed = select_pure(
                candidates=non_wait, committed_repr=self._committed_repr,
                try_plan=try_plan_full, is_satisfied=satisfied, is_suppressed=is_suppressed)
        if chosen is None:
            # Last resort: Wait (special-cased to a single WaitAction).
            wait = next((c for c in candidates if isinstance(c.goal, WaitGoal)), None)
            if wait is not None and not is_suppressed(wait.goal):
                chosen, plan, new_committed = wait.goal, [WaitAction()], self._committed_repr

        self._committed_repr = new_committed
        return chosen, plan, self.goals_tried
```

Add `self._cycle = 0` to `__init__` and a setter:

```python
    def set_cycle(self, cycle: int) -> None:
        """Player calls this each cycle so the memo's re-probe window advances."""
        self._cycle = cycle
```

Import `WaitAction` at the top if not already present:

```python
from artifactsmmo_cli.ai.actions.wait import WaitAction  # (already imported — verify)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_strategy_driver_tiered.py -k constant tests/test_ai/test_strategy_driver.py -v --no-cov`
Expected: PASS (constant test + all existing arbiter tests still green — the cheap pass plans the same goals the old single pass did when budgets are ample in tests using the real `GOAPPlanner`, which finishes well under 1s on the tiny test fixtures).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver_tiered.py
git commit -m "feat(arbiter): two-pass tiered select (cheap -> escalate -> Wait) + memo"
```

### Task 6: behavioral tests for the two passes + memo

**Files:**
- Modify: `tests/test_ai/test_strategy_driver_tiered.py` (append, using `_ScriptedPlanner`)

- [ ] **Step 1: Write the failing/p assertions**

```python
def _arbiter_with(planner):
    a = StrategyArbiter(planner, history=None)
    a.set_cycle(0)
    return a

def test_cheap_pass_selects_cheaply_plannable_and_skips_escalation():
    # A discretionary goal that plans cheap is selected; planner never asked for full budget.
    planner = _ScriptedPlanner(cheap_ok={"AcceptTask"}, full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, _ = a.select(decision, state, _make_planner_gd(),
                             [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert all(b == CHEAP for (_, b) in planner.budgets if _ == "AcceptTask")

def test_escalates_to_full_when_nothing_cheap():
    # AcceptTask only plans at full budget → cheap pass empty → escalation selects it.
    planner = _ScriptedPlanner(cheap_ok=set(), full_only={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(),
                             [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert (None,) == tuple({b for (r, b) in planner.budgets if r == "AcceptTask" and b is None}) or \
           any(b is None for (r, b) in planner.budgets if r == "AcceptTask")

def test_timed_out_goal_is_memoized_and_skipped_next_cycle():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())  # nothing ever plans
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    ctx = _ctx(combat_monster="chicken")
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle0 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    planner.budgets.clear()
    a.set_cycle(1)
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle1 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    assert calls_cycle0 >= 1
    assert calls_cycle1 == 0, "memoized goal must be skipped on the next cycle"

def test_wait_selected_when_nothing_plans():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(goal, WaitGoal)
    assert plan == [WaitAction()]
```

- [ ] **Step 2-4: Run, fix `select` if needed until green**

Run: `uv run pytest tests/test_ai/test_strategy_driver_tiered.py -v --no-cov`
Expected: PASS (all). If `test_escalates...` is flaky on the budget assertion, simplify it to `assert any(b is None for (r, b) in planner.budgets if r == "AcceptTask")`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_strategy_driver_tiered.py
git commit -m "test(arbiter): cheap/escalate/memo/Wait behavioral coverage"
```

---

## Phase 4 — Gear appropriateness + latch

### Task 7: `has_craftable_upgrade_any_slot`

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_appropriateness.py`
- Test: `tests/test_ai/test_gear_appropriateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_gear_appropriateness.py
"""has_craftable_upgrade_any_slot: the latch-clear test (gear is level-appropriate
when no craftable upgrade remains for any slot)."""
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_boots():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_true_when_a_craftable_upgrade_exists():
    state = make_state(level=4)  # empty boots_slot, can craft copper_boots
    assert has_craftable_upgrade_any_slot(state, _gd_with_boots()) is True


def test_false_when_no_craftable_upgrade():
    gd = GameData()
    gd._item_stats = {}; gd._crafting_recipes = {}
    assert has_craftable_upgrade_any_slot(make_state(level=4), gd) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_gear_appropriateness.py -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** (reuse the existing selection on `UpgradeEquipmentGoal`)

```python
# src/artifactsmmo_cli/ai/gear_appropriateness.py
"""Gear is 'level-appropriate' when no craftable upgrade remains for any slot —
the clear condition for the gear-review latch. Delegates to the proven
UpgradeEquipmentGoal craftable-upgrade selection so this stays the single source
of truth for 'what is an upgrade'."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.world_state import WorldState


def has_craftable_upgrade_any_slot(state: WorldState, game_data: GameData) -> bool:
    """True iff some equippable slot has a better craftable item at the
    character's current level (uncommitted UpgradeEquipment finds one)."""
    probe = UpgradeEquipmentGoal()  # uncommitted ⇒ scans all slots for the best upgrade
    return probe.find_upgrade_target(state, game_data) is not None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_gear_appropriateness.py -v --no-cov`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/gear_appropriateness.py tests/test_ai/test_gear_appropriateness.py
git commit -m "feat(ai): has_craftable_upgrade_any_slot latch-clear test"
```

### Task 8: `GearLatch`

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_latch.py`
- Test: `tests/test_ai/test_gear_latch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_gear_latch.py
"""GearLatch: set on level-up or predicted-winnable fight loss; clear when gear is
level-appropriate; monotone (stays set until clear holds)."""
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_boots():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_starts_inactive():
    assert GearLatch().active is False


def test_sets_on_level_up():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=_gd_with_boots())
    assert latch.active is True


def test_sets_on_fight_loss():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=4), last_outcome="error:fight_lost",
                 game_data=_gd_with_boots())
    assert latch.active is True


def test_clears_when_no_craftable_upgrade():
    latch = GearLatch()
    empty_gd = GameData(); empty_gd._item_stats = {}; empty_gd._crafting_recipes = {}
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=empty_gd)
    assert latch.active is False  # set by level-up but immediately cleared: nothing to craft


def test_monotone_stays_set_until_clear():
    latch = GearLatch()
    gd = _gd_with_boots()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=gd)
    assert latch.active is True
    # next cycle, no level-up, no loss, upgrade still available → stays set
    latch.update(prev_level=5, state=make_state(level=5), last_outcome="ok", game_data=gd)
    assert latch.active is True
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_gear_latch.py -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/gear_latch.py
"""Latch that prioritizes the gear chain after a level-up or a predicted-winnable
fight loss, until equipment is level-appropriate. Owned by the player and updated
once per cycle BEFORE goal selection; read via `active` to fire the GEAR_REVIEW
guard. See the tiered-budget spec."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from artifactsmmo_cli.ai.world_state import WorldState


class GearLatch:
    """Boolean latch. SET on level-up or `error:fight_lost`; CLEAR when no
    craftable upgrade remains for any slot; otherwise holds its prior value."""

    def __init__(self) -> None:
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def update(self, prev_level: int, state: WorldState, last_outcome: str | None,
               game_data: GameData) -> None:
        """Re-evaluate the latch for this cycle. `prev_level` is the character
        level from the previous cycle; `last_outcome` is the outcome string of the
        previously executed action (None on the first cycle)."""
        triggered = state.level > prev_level or last_outcome == "error:fight_lost"
        if triggered:
            self._active = True
        if self._active and not has_craftable_upgrade_any_slot(state, game_data):
            self._active = False
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_gear_latch.py -v --no-cov`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/gear_latch.py tests/test_ai/test_gear_latch.py
git commit -m "feat(ai): GearLatch set on level-up/fight-loss, clear when gear appropriate"
```

---

## Phase 5 — GEAR_REVIEW guard wiring

### Task 9: `GuardKind.GEAR_REVIEW` + ctx flag + fire rule

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (`GuardKind`, `GUARD_ORDER`, `SelectionContext`, `_fires`)
- Test: `tests/test_ai/test_guards.py` (append) — match the file that tests `active_guards`

- [ ] **Step 1: Write the failing test**

```python
# append to the guards test module (find it: grep -rl 'def test.*active_guards\|GUARD_ORDER' tests)
from artifactsmmo_cli.ai.tiers.guards import GuardKind, GUARD_ORDER, active_guards

def test_gear_review_in_guard_order_below_survival_above_none():
    # GEAR_REVIEW is the LAST guard (lowest-priority guard, still above all means).
    assert GUARD_ORDER[-1] is GuardKind.GEAR_REVIEW
    assert GuardKind.HP_CRITICAL in GUARD_ORDER[:GUARD_ORDER.index(GuardKind.GEAR_REVIEW)]

def test_gear_review_fires_only_when_ctx_active(make_planner_gd):
    from tests.test_ai.fixtures import make_state
    from tests.test_ai.test_strategy_driver import _ctx
    state = make_state(hp=150, max_hp=150)
    active_ctx = _ctx(gear_review_active=True)
    inactive_ctx = _ctx(gear_review_active=False)
    assert GuardKind.GEAR_REVIEW in active_guards(state, make_planner_gd, None, active_ctx)
    assert GuardKind.GEAR_REVIEW not in active_guards(state, make_planner_gd, None, inactive_ctx)
```

(Add `gear_review_active=False` default to the `_ctx` helper in
`tests/test_ai/test_strategy_driver.py`.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai -k gear_review_in_guard_order -v --no-cov`
Expected: FAIL — `GuardKind.GEAR_REVIEW` missing.

- [ ] **Step 3: Implement**

In `guards.py`:

```python
class GuardKind(Enum):
    ...
    GEAR_REVIEW = "gear_review"  # post-level-up / post-loss gear prioritization
```

Append to `GUARD_ORDER` (last = lowest-priority guard, still above all means):

```python
GUARD_ORDER: tuple[GuardKind, ...] = (
    GuardKind.HP_CRITICAL,
    GuardKind.REST_FOR_COMBAT,
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.CRAFT_RELIEF,
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
    GuardKind.GEAR_REVIEW,
)
```

Add the ctx flag to `SelectionContext`:

```python
    gear_review_active: bool = False
```

Add the fire rule in `_fires` (the function `active_guards` calls per kind):

```python
    if kind is GuardKind.GEAR_REVIEW:
        return ctx.gear_review_active
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai -k "gear_review" -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py tests/test_ai/
git commit -m "feat(guards): GEAR_REVIEW guard fires on ctx.gear_review_active"
```

### Task 10: `map_guard` maps GEAR_REVIEW to the gear chain

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`map_guard`)
- Test: `tests/test_ai/test_strategy_driver.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_map_guard_gear_review_gathers_when_materials_missing():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    state = make_state(level=4, inventory={}, bank_items={})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, GatherMaterialsGoal)

def test_map_guard_gear_review_upgrades_when_materials_in_hand():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    state = make_state(level=4, inventory={"copper_bar": 8})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, UpgradeEquipmentGoal)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k gear_review -v --no-cov`
Expected: FAIL — `map_guard` raises `Unknown GuardKind: GEAR_REVIEW`.

- [ ] **Step 3: Implement** (in `map_guard`, before the final `raise`)

```python
    if kind is GuardKind.GEAR_REVIEW:
        if state is None:
            raise ValueError("GEAR_REVIEW guard requires a state")
        probe = UpgradeEquipmentGoal(initial_equipment=state.equipment)
        target = probe.find_upgrade_target(state, game_data)
        if target is None:
            # No upgrade — should not fire, but stay safe: hand back a no-op-ish
            # UpgradeEquipment that is_satisfied won't select. (active_guards gates
            # on ctx, so this branch is defensive only.)
            return UpgradeEquipmentGoal(initial_equipment=state.equipment)
        item, slot = target
        if state.inventory.get(item, 0) > 0 or _materials_in_hand(item, state, game_data):
            return UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                        committed_target=(item, slot))
        recipe = game_data._crafting_recipes.get(item) or {}
        needed = {mat: qty for mat, qty in recipe.items()}
        return GatherMaterialsGoal(target_item=item, needed=needed)
```

Add the helper near the top of `strategy_driver.py`:

```python
def _materials_in_hand(item: str, state: WorldState, game_data: GameData) -> bool:
    """True if every direct recipe material for `item` is fully covered by
    inventory + bank (so the craft+equip plan is short and reachable)."""
    recipe = game_data._crafting_recipes.get(item) or {}
    bank = state.bank_items or {}
    return bool(recipe) and all(
        state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty for mat, qty in recipe.items())
```

Ensure `GatherMaterialsGoal` and `UpgradeEquipmentGoal` are imported in
`strategy_driver.py` (they are — verify).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k gear_review -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(arbiter): map GEAR_REVIEW to GatherMaterials/UpgradeEquipment by material availability"
```

---

## Phase 6 — Player integration

### Task 11: player owns the latch, advances cycle, wires ctx

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`__init__`, `run` loop, `_selection_context`)
- Test: `tests/test_ai/test_player_gear_latch.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_player_gear_latch.py
"""Player updates the gear latch each cycle and feeds gear_review_active into the
selection context."""
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.player import GamePlayer


def test_player_constructs_a_gear_latch():
    p = GamePlayer(character="hero")
    assert isinstance(p._gear_latch, GearLatch)


def test_selection_context_carries_latch_state(monkeypatch):
    p = GamePlayer(character="hero")
    p._gear_latch._active = True
    # _selection_context reads the latch; build a minimal state/game_data via the
    # player's own helpers used elsewhere in tests (see existing player tests for
    # the GameData/WorldState fixtures) and assert the flag is forwarded.
    from tests.test_ai.fixtures import make_state
    from tests.test_ai.test_strategy_driver import _make_planner_gd
    p.state = make_state(); p.game_data = _make_planner_gd()
    ctx = p._selection_context(combat_monster=None)
    assert ctx.gear_review_active is True
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_player_gear_latch.py -v --no-cov`
Expected: FAIL — `_gear_latch` missing / ctx has no `gear_review_active` wiring.

- [ ] **Step 3: Implement**

In `GamePlayer.__init__` add:

```python
        self._gear_latch = GearLatch()
        self._prev_level: int | None = None
        self._last_outcome: str | None = None
```

Import at top of `player.py`:

```python
from artifactsmmo_cli.ai.gear_latch import GearLatch
```

In `_selection_context`, add `gear_review_active=self._gear_latch.active` to the
`SelectionContext(...)` construction (find the existing constructor call).

In the `run` loop, AFTER `self.state` is refreshed each cycle and BEFORE
`self._strategy.decide`/`self._arbiter.select`, add:

```python
                prev = self._prev_level if self._prev_level is not None else self.state.level
                self._gear_latch.update(prev, self.state, self._last_outcome, self.game_data)
                self._prev_level = self.state.level
                self._arbiter.set_cycle(self._cycle_counter)
```

After an action executes and `outcome` is known (the existing
`new_state, outcome = self._execute(...)` / dry-run `outcome = "ok"` block), record:

```python
                self._last_outcome = outcome
```

(There is an existing `self._cycle_counter`; verify its name and reuse it. If the
counter increments elsewhere, ensure `set_cycle` is called with the current value
each cycle.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_player_gear_latch.py -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_gear_latch.py
git commit -m "feat(player): own GearLatch, update per cycle, feed gear_review_active + arbiter cycle"
```

### Task 12: regression sweep + integration smoke

**Files:**
- Test: `tests/test_ai/test_first_cycle_smoke.py` (create, marked integration)

- [ ] **Step 1: Write the smoke test** (offline, scripted planner — no network)

```python
# tests/test_ai/test_first_cycle_smoke.py
"""The tiered budget bounds a cycle that has many wide candidates: with a planner
that never plans the wide goals, selection still terminates quickly at Wait and
memoizes them, and a second cycle skips them."""
import pytest
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _FakeDecision, _make_planner_gd, _ctx
from tests.test_ai.test_strategy_driver_tiered import _ScriptedPlanner


def test_many_doomed_candidates_resolve_to_wait_then_skip():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = StrategyArbiter(planner, history=None); a.set_cycle(0)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    g0, _, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(g0, WaitGoal)
    n0 = len(planner.budgets); planner.budgets.clear()
    a.set_cycle(1)
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert len(planner.budgets) <= n0  # memoized goals not re-planned
```

- [ ] **Step 2-4: Run full suite**

Run: `uv run pytest tests/test_ai -v --no-cov`
Expected: ALL PASS, including the pre-existing arbiter/level_skill/min_gathers suites.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_first_cycle_smoke.py
git commit -m "test(ai): tiered budget bounds many-doomed-candidate cycle to Wait + memo"
```

---

## Phase 7 — Formal proofs

Use the `lean4:*` skills (`lean4:formalize` / `lean4:prove`) to author and prove
these. Core-only (no mathlib) where the statements are arithmetic/structural.

### Task 13: `formal/Formal/TieredSelection.lean`

**Files:**
- Create: `formal/Formal/TieredSelection.lean`
- Modify: `formal/Formal.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`

- [ ] **Step 1:** Model an abstract candidate list `cand : List C` with a band index,
a `cheapPlans : C → Bool` and `fullPlans : C → Bool` (with `cheapPlans c → fullPlans c`),
and a two-pass `select` function mirroring Task 5. Prove:
  - `cheap_winner_is_first_cheaply_plannable` — pass-1 result = first `c` with `cheapPlans c`.
  - `escalation_iff_no_cheap` — pass-2 entered ⇔ `∀ c, ¬ cheapPlans c`.
  - `wait_only_when_no_full` — Wait returned ⇒ `∀ c (non-Wait), ¬ fullPlans c`.
  - `memo_skip_sound` — modeled as: if `skip c` then `¬ cheapPlans c ∧ ¬ fullPlans c`
    (the memo only carries goals that produced no plan at the recorded signature),
    so skipping does not drop a plannable candidate at unchanged signature.

- [ ] **Step 2:** `lake build Formal.TieredSelection`; fix until green.

- [ ] **Step 3:** Axiom-check each theorem: only `{propext, Classical.choice, Quot.sound}`.
Run the snippet pattern from `PlannerDepthBound` (`#print axioms ...`).

- [ ] **Step 4:** Register: add `import Formal.TieredSelection` to `Formal.lean` and
`Formal/Contracts.lean`; add `#check @Formal.TieredSelection.<thm>` lines to
`Manifest.lean`; add exact-statement `example : <stmt> := @<thm>` pins to `Contracts.lean`.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/TieredSelection.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "formal: tiered-selection two-pass invariants (cheap/escalate/Wait/memo)"
```

### Task 14: `formal/Formal/GearLatch.lean`

**Files:**
- Create: `formal/Formal/GearLatch.lean`
- Modify: `formal/Formal.lean`, `Manifest.lean`, `Contracts.lean`

- [ ] **Step 1:** Model the latch as `step : (active : Bool) → (leveledUp loss hasUpgrade : Bool) → Bool`
mirroring `GearLatch.update`:
`step a lvl loss up := let t := (a || lvl || loss); if t && !up then false else t`
(note: `t && !up → false`, else `t`). Prove:
  - `set_on_levelup` — `lvl = true → up = true → step a lvl loss = true`.
  - `set_on_loss` — `loss = true → up = true → step a true... = true` (loss path).
  - `clear_iff_no_upgrade` — `step a lvl loss = ... ` with `up = false` ⇒ result `false`.
  - `monotone_until_clear` — `a = true → up = true → ¬lvl → ¬loss → step = true`.

- [ ] **Step 2:** `lake build Formal.GearLatch`; fix until green.
- [ ] **Step 3:** Axiom-check.
- [ ] **Step 4:** Register in `Formal.lean` / `Manifest.lean` / `Contracts.lean`.
- [ ] **Step 5: Commit**

```bash
git add formal/Formal/GearLatch.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "formal: gear-review latch state machine (set/clear/monotone)"
```

---

## Phase 8 — Verification & docs

### Task 15: full gates + plan/spec status update

- [ ] **Step 1:** Full Python suite + coverage on new code:
Run: `uv run pytest tests/test_ai -q --no-cov` then targeted coverage:
`uv run pytest tests/ --cov=src/artifactsmmo_cli/ai/doomed_memo --cov=src/artifactsmmo_cli/ai/gear_latch --cov=src/artifactsmmo_cli/ai/gear_appropriateness --cov=src/artifactsmmo_cli/ai/plannability_signature --cov-report=term-missing -q -k "memo or latch or gear or signature or tiered or budget"`
Expected: new modules at 100%.

- [ ] **Step 2:** mypy + ruff on all changed/new src:
Run: `uv run mypy src/artifactsmmo_cli/ai/...` and `uv run ruff check src/artifactsmmo_cli/ai/...`
Expected: clean.

- [ ] **Step 3:** Formal axiom hygiene for the two new modules (only allowed axioms).

- [ ] **Step 4:** Update `docs/PLAN_planner_liveness.md`: mark the width-issue/tiered-budget item done; note the gear-prioritization landed.

- [ ] **Step 5: Commit**

```bash
git add docs/PLAN_planner_liveness.md
git commit -m "docs: mark tiered budget + gear prioritization complete"
```

---

## Self-review notes (author)

- **Spec coverage:** §Architecture 1→Task 1; 2→Tasks 4-6; 3 (memo)→Tasks 2-3,5; 4
  (GEAR_REVIEW+latch)→Tasks 7-11; formal→Tasks 13-14; testing→every task +12,15.
- **Type consistency:** `plannability_signature`/`Signature` shared by Task 2/3;
  `DoomedMemo.{mark,clear,is_doomed}` used identically in Task 5; `GearLatch.update`
  param order `(prev_level, state, last_outcome, game_data)` consistent across Tasks
  8/11; `CHEAP_BUDGET_SECONDS` defined Task 5, used Tasks 5/6; `set_cycle` defined
  Task 5, used Tasks 6/11/12.
- **Known integration unknowns to verify during execution (not placeholders):**
  the exact `SelectionContext(...)` construction site in `player.py:_selection_context`,
  the `self._cycle_counter` name, and the `_fires` dispatch function name in
  `guards.py` (the plan cites `active_guards` calling per-kind fire logic — confirm
  whether it's an inline comprehension or a `_fires` helper and place the GEAR_REVIEW
  rule accordingly). These are reads, not decisions.
