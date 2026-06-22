# C2 — Task-Completion Coin Income Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make `CompleteTaskAction.apply` mint the active task's `tasks_coin` reward (floor ≥1) into inventory, via a kernel-proved pure core — so a funding plan ("accumulate ≥N tasks_coin") becomes plannable (no modeled action currently raises the coin count).

**Architecture:** Reuse C1's task-definition loading, extended to store per-task `tasks_coin` reward amounts (`task_coin_reward(code)`, conservative min floor for the unknown/`__pending__` task). Extract `complete_task_apply_pure(inventory, coin_reward)` (mirrors `npc_buy_currency_apply_pure`); prove the coin-count monotonicity in Lean (`Formal/CompleteTaskIncome.lean`, models the load-bearing coin count like `NpcBuyInventory` models slots); differential + mutation gate; wire `CompleteTaskAction.apply` to call the core.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (core-only, no mathlib), Hypothesis differential, `mutate.py`, pytest.

## Global Constraints

- ALWAYS prefix Python with `~/.local/bin/uv run`. `lake` is at `~/.elan/bin/lake` (NOT `~/.local/bin/lake`); use `export PATH="$HOME/.elan/bin:$PATH"` then `lake build`. The formal package + oracle are already built; builds are INCREMENTAL — do NOT clean `.lake`.
- Imports at TOP of file only; no inline imports; no `if TYPE_CHECKING`; absolute imports only.
- NEVER catch `Exception`. Use only API data or fail — no defaulting (the per-task coin reward comes from loaded task definitions; the conservative MIN floor is an API-derived value, NOT an invented constant).
- ONE behavioral class per file. Tests in `tests/`. Touched modules → 100% coverage.
- This builds ON the C1 branch (`worktree-c1-task-currency-producibility`) in the same worktree; C1's `_build_tasks`/`task_reward_item_codes` already exist.
- DEPLOY GATE unchanged: C1–C4 deploy together; do not run the live bot on this code until C4.
- Run `mutate.py` only with the bot stopped (it is). `git diff src` clean after.

---

### Task 1: Store per-task tasks_coin reward in GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (extend `_build_tasks`; add `task_coin_reward`, `min_task_coin_reward`, backing field `_task_coin_rewards`)
- Test: `tests/test_ai/test_game_data_task_rewards.py` (extend — file exists from C1)

**Interfaces:**
- Produces: `GameData.task_coin_reward(task_code: str) -> int` — the `tasks_coin` quantity a given task awards; for an unknown/`__pending__`/empty code returns `min_task_coin_reward()` (conservative floor, never over-credits).
- Produces: `GameData.min_task_coin_reward() -> int` — `min` of all loaded per-task coin rewards (≥1). Raises `ValueError` if no task data is loaded (fail, don't default).
- Backing field: `_task_coin_rewards: dict[str, int] = field(default_factory=dict)` (task_code → tasks_coin qty).

- [ ] **Step 1: Write the failing test (extend the C1 file)**

```python
# append to tests/test_ai/test_game_data_task_rewards.py
import pytest
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE


def _seed_rewards(rewards: dict[str, int]) -> GameData:
    gd = GameData()
    gd._task_coin_rewards = dict(rewards)
    return gd


def test_task_coin_reward_known_code():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.task_coin_reward("chicken") == 3


def test_task_coin_reward_unknown_code_returns_min_floor():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.task_coin_reward("__pending__") == 2  # conservative min


def test_min_task_coin_reward():
    gd = _seed_rewards({"chicken": 3, "copper_ore": 2})
    assert gd.min_task_coin_reward() == 2


def test_min_task_coin_reward_no_data_raises():
    with pytest.raises(ValueError):
        GameData().min_task_coin_reward()


def test_build_tasks_collects_coin_rewards():
    gd = GameData()
    gd._build_tasks(_fake_coin_tasks())
    assert gd.task_coin_reward("chicken") == 3


class _FakeCoinItem:
    def __init__(self, code: str, quantity: int) -> None:
        self.code = code
        self.quantity = quantity


class _FakeCoinRewards:
    def __init__(self, items: list[_FakeCoinItem]) -> None:
        self.items = items


class _FakeCoinTask:
    def __init__(self, code: str, coin_qty: int) -> None:
        self.code = code
        self.rewards = _FakeCoinRewards([_FakeCoinItem(TASKS_COIN_CODE, coin_qty)])


def _fake_coin_tasks() -> list[_FakeCoinTask]:
    return [_FakeCoinTask("chicken", 3), _FakeCoinTask("copper_ore", 2)]
```

- [ ] **Step 2: Run, verify failure**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_game_data_task_rewards.py -k "coin" -v`
Expected: FAIL — `AttributeError` on `task_coin_reward`/`min_task_coin_reward`/`_task_coin_rewards`.

- [ ] **Step 3: Add the field, accessors, and extend `_build_tasks`**

Add `from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE` to the imports if not present. Add the field near `_task_reward_item_codes` (from C1):
```python
    _task_coin_rewards: dict[str, int] = field(default_factory=dict)
```
Extend `_build_tasks` (C1 version collects codes; ADD per-task coin amount) — replace its body:
```python
    def _build_tasks(self, tasks: list[TaskFullSchema]) -> None:
        """Collect (a) the set of item codes any task awards [C1], and
        (b) per-task `tasks_coin` reward amounts [C2]."""
        self._task_reward_item_codes = frozenset(
            item.code for task in tasks for item in task.rewards.items
        )
        self._task_coin_rewards = {
            task.code: item.quantity
            for task in tasks
            for item in task.rewards.items
            if item.code == TASKS_COIN_CODE
        }
```
Add accessors near `is_task_earnable` (from C1):
```python
    def min_task_coin_reward(self) -> int:
        """Conservative floor: the smallest `tasks_coin` award across all loaded
        tasks. Used to project a not-yet-assigned (`__pending__`) task's reward
        without over-crediting. Raises if no task data is loaded (no defaulting)."""
        if not self._task_coin_rewards:
            raise ValueError("no task coin-reward data loaded")
        return min(self._task_coin_rewards.values())

    def task_coin_reward(self, task_code: str) -> int:
        """`tasks_coin` awarded by completing `task_code`. For a known task the
        exact API amount; for an unknown / `__pending__` / empty code the
        conservative `min_task_coin_reward()` floor (never over-credits)."""
        known = self._task_coin_rewards.get(task_code)
        return known if known is not None else self.min_task_coin_reward()
```

- [ ] **Step 4: Run, verify pass + no game_data regression**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_game_data_task_rewards.py tests/test_ai/test_game_data.py -q`
Expected: PASS (the new coin tests + C1 tests + game_data suite).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data_task_rewards.py
git commit -m "feat(game_data): store per-task tasks_coin reward; task_coin_reward + min floor (C2)"
```

---

### Task 2: Extract the coin-minting pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/complete_task_core.py`
- Test: `tests/test_ai/test_complete_task_core.py`

**Interfaces:**
- Produces: `complete_task_apply_pure(inventory: Mapping[str, int], coin_reward: int) -> dict[str, int]` — returns a new inventory with `tasks_coin += coin_reward`, all other entries preserved.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_complete_task_core.py
"""Pure core: completing a task mints `coin_reward` tasks_coin into inventory."""
from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure


def test_mints_coins_into_empty_inventory():
    assert complete_task_apply_pure({}, 3) == {"tasks_coin": 3}


def test_adds_to_existing_coin_stack():
    assert complete_task_apply_pure({"tasks_coin": 2}, 3) == {"tasks_coin": 5}


def test_preserves_other_items():
    out = complete_task_apply_pure({"copper_ore": 4, "tasks_coin": 1}, 2)
    assert out == {"copper_ore": 4, "tasks_coin": 3}


def test_does_not_mutate_input():
    inv = {"tasks_coin": 1}
    complete_task_apply_pure(inv, 2)
    assert inv == {"tasks_coin": 1}
```

- [ ] **Step 2: Run, verify failure**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_complete_task_core.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/actions/complete_task_core.py
"""Pure core of `CompleteTaskAction.apply`'s coin-minting bookkeeping.

Extracted so the formal differential test (`formal/diff/test_complete_task_income_diff.py`)
can exercise the exact tasks_coin-count change against the kernel-proved Lean
`Formal.CompleteTaskIncome.applyComplete` (`formal/Formal/CompleteTaskIncome.lean`),
whose `applyComplete_monotone` theorem proves: a reward of ≥1 strictly raises the
coin count — so a funding plan that completes tasks makes monotone progress toward
a `tasks_coin ≥ N` target.

Mirrors `npc_buy_currency_apply_pure`: mint into one key, preserve the rest.
"""
from collections.abc import Mapping

from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE


def complete_task_apply_pure(inventory: Mapping[str, int],
                             coin_reward: int) -> dict[str, int]:
    """Return a new inventory with `tasks_coin += coin_reward`; all other entries
    preserved. The coin count after equals the count before plus `coin_reward`
    (the quantity the Lean `applyComplete` models)."""
    new_inventory = dict(inventory)
    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward
    return new_inventory
```

- [ ] **Step 4: Run, verify pass**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_complete_task_core.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/complete_task_core.py tests/test_ai/test_complete_task_core.py
git commit -m "feat(actions): extract complete_task_apply_pure coin-minting core (C2)"
```

---

### Task 3: Lean model + role theorems (`Formal/CompleteTaskIncome.lean`)

**Files:**
- Create: `formal/Formal/CompleteTaskIncome.lean`
- Modify: `formal/Formal.lean` (add `import Formal.CompleteTaskIncome`)
- Modify: `formal/Formal/Manifest.lean` (import + role `#check`s)
- Modify: `formal/Formal/Contracts.lean` (import + anti-weakening pins)

**Interfaces:**
- Produces: `Formal.CompleteTaskIncome.applyComplete (coins reward : Nat) : Nat`
- Theorems: `applyComplete_adds` (validity: = coins + reward), `applyComplete_monotone` (reward ≥ 1 ⇒ coins < result).

- [ ] **Step 1: Write the Lean model**

```lean
-- formal/Formal/CompleteTaskIncome.lean
-- @concept: core, tasks @property: monotonicity
/-
Coin-income model for `CompleteTaskAction.apply`
(`src/artifactsmmo_cli/ai/actions/complete_task.py`) and its pure core
`src/artifactsmmo_cli/ai/actions/complete_task_core.py::complete_task_apply_pure`.

Completing a task mints the task's `tasks_coin` reward into inventory. Like
`NpcBuyInventory` (which models the load-bearing SLOT count and leaves per-key
bookkeeping to the differential test), this models the load-bearing TASKS_COIN
COUNT: `applyComplete coins reward = coins + reward`. The headline contract is
MONOTONICITY: a reward ≥ 1 strictly raises the coin count — so a funding plan
that repeatedly completes tasks makes monotone progress toward `tasks_coin ≥ N`
(the C3 termination argument rests on this).

The reward ≥ 1 floor is enforced on the Python side
(`GameData.task_coin_reward` returns the API per-task amount or the conservative
`min` ≥ 1); the differential test feeds rewards ≥ 1.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.CompleteTaskIncome

/-- Mint `reward` tasks_coin: the post-completion coin count. -/
def applyComplete (coins reward : Nat) : Nat := coins + reward

/-- **VALIDITY.** The coin count after completion is exactly before + reward. -/
theorem applyComplete_adds (coins reward : Nat) :
    applyComplete coins reward = coins + reward := rfl

/-- **MONOTONICITY.** A reward of at least 1 STRICTLY raises the coin count —
the load-bearing progress fact for funding-plan termination. -/
theorem applyComplete_monotone (coins reward : Nat) (h : 1 ≤ reward) :
    coins < applyComplete coins reward := by
  simp [applyComplete]; omega

/-! ### Non-vacuity witnesses. -/
-- A reward of 1 (the floor) already increases the count: monotonicity is not vacuous.
example : applyComplete 0 1 = 1 := by decide
example : applyComplete 5 3 = 8 := by decide
-- The monotonicity hypothesis is satisfiable (reward = 1).
example : (0 : Nat) < applyComplete 0 1 := by decide

end Formal.CompleteTaskIncome
```

- [ ] **Step 2: Add imports + manifest + contracts**

`formal/Formal.lean` (with the other component imports): `import Formal.CompleteTaskIncome`
`formal/Formal/Manifest.lean` import block: `import Formal.CompleteTaskIncome`
…and the roster (after the LeafAttainable block from C1):
```lean
-- CompleteTaskIncome required roles (CompleteTaskAction.apply coin minting;
-- src/artifactsmmo_cli/ai/actions/complete_task_core.py):
#check @Formal.CompleteTaskIncome.applyComplete_adds      -- validity: post = coins + reward
#check @Formal.CompleteTaskIncome.applyComplete_monotone  -- reward ≥ 1 ⇒ strict increase
```
`formal/Formal/Contracts.lean` import block: `import Formal.CompleteTaskIncome`
…and the pins (after the LeafAttainable pins from C1):
```lean
-- ─── CompleteTaskIncome (CompleteTaskAction.apply coin minting) anti-weakening pins ───
-- VALIDITY: post-completion coin count is EXACTLY coins + reward.
example : ∀ (coins reward : Nat),
    Formal.CompleteTaskIncome.applyComplete coins reward = coins + reward :=
  @Formal.CompleteTaskIncome.applyComplete_adds
-- MONOTONICITY: reward ≥ 1 ⇒ STRICT increase (weakening `<` to `≤` fails to elaborate).
example : ∀ (coins reward : Nat), 1 ≤ reward →
    coins < Formal.CompleteTaskIncome.applyComplete coins reward :=
  @Formal.CompleteTaskIncome.applyComplete_monotone
```

- [ ] **Step 3: Build + axiom check**

Run: `cd formal && export PATH="$HOME/.elan/bin:$PATH" && lake build`
Expected: success, no sorry/axiom warnings.
Run the axiom check for both theorems (`#print axioms`): each lists only `[propext, Classical.choice, Quot.sound]` (a `rfl` may list none). No `sorryAx`/`ofReduceBool`.

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/CompleteTaskIncome.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(formal): CompleteTaskIncome model + validity/monotonicity roles + pins (C2)"
```

---

### Task 4: Oracle handler + differential test

**Files:**
- Modify: `formal/Oracle.lean` (add `runCompleteTaskIncome`; route `"complete_task_income"`)
- Create: `formal/diff/test_complete_task_income_diff.py`

**Interfaces:**
- oracle `kind="complete_task_income"`, args `[coins, reward]`, result `{"coins_after": int}`.

- [ ] **Step 1: Add oracle handler + route**

In `formal/Oracle.lean`, after `runLeafAttainable` (from C1):
```lean
-- CompleteTaskIncome: post-completion tasks_coin count.
-- args = [coins, reward]
def runCompleteTaskIncome (args : Array Json) : Json :=
  let c := Formal.CompleteTaskIncome.applyComplete (intArg args 0).toNat (intArg args 1).toNat
  Json.mkObj [("coins_after", Json.num (Int.ofNat c))]
```
…and in `runOne` (after the `leaf_attainable` branch from C1):
```lean
  else if kind == "complete_task_income" then
    runCompleteTaskIncome args
```

- [ ] **Step 2: Write the differential test**

```python
# formal/diff/test_complete_task_income_diff.py
"""Differential: the tasks_coin count after `complete_task_apply_pure` must equal
the kernel-proved `Formal.CompleteTaskIncome.applyComplete(coins, reward)`.

The Lean side carries `applyComplete_monotone` (reward ≥ 1 ⇒ strict increase);
this pins the running Python coin-minting to that proved arithmetic."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from formal.diff.oracle_client import run_oracle

_coins = st.integers(min_value=0, max_value=500)
_reward = st.integers(min_value=1, max_value=50)  # API floor: every task awards ≥1


@given(coins=_coins, reward=_reward)
def test_coin_count_matches_oracle(coins, reward):
    py = complete_task_apply_pure({TASKS_COIN_CODE: coins}, reward)[TASKS_COIN_CODE]
    lean = run_oracle("complete_task_income", [[coins, reward]])[0]["coins_after"]
    assert py == lean, f"divergence at (coins={coins}, reward={reward}): py={py} lean={lean}"


def test_reward_strictly_increases_both_sides():
    """Monotonicity witness: a reward ≥1 raises the count on both sides."""
    py = complete_task_apply_pure({TASKS_COIN_CODE: 7}, 1)[TASKS_COIN_CODE]
    lean = run_oracle("complete_task_income", [[7, 1]])[0]["coins_after"]
    assert py == lean == 8
    assert py > 7
```

- [ ] **Step 3: Rebuild oracle + run differential**

Run: `cd formal && export PATH="$HOME/.elan/bin:$PATH" && lake build oracle`
Run: `~/.local/bin/uv run pytest formal/diff/test_complete_task_income_diff.py -v` (from worktree root)
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add formal/Oracle.lean formal/diff/test_complete_task_income_diff.py
git commit -m "feat(formal): complete_task_income oracle handler + differential (C2)"
```

---

### Task 5: Wire `CompleteTaskAction.apply` to mint coins via the core

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/complete_task.py` (`apply`)
- Test: `tests/test_ai/` — add to the existing CompleteTaskAction test file (find it: `grep -rl CompleteTaskAction tests/`)

**Interfaces:**
- Consumes: `complete_task_apply_pure` (Task 2), `GameData.task_coin_reward` (Task 1).

- [ ] **Step 1: Write the failing test**

Find the existing test file (`grep -rl "CompleteTaskAction" tests/`); add there, reusing its WorldState/GameData fixtures:
```python
def test_complete_task_mints_coin_reward(<existing fixtures>):
    # state with an active completed task whose code awards a known coin amount;
    # gd seeded so task_coin_reward(state.task_code) == 3.
    # after apply, inventory["tasks_coin"] increased by 3.
    new_state = CompleteTaskAction(taskmaster_location=(0, 0)).apply(state, gd)
    assert new_state.inventory.get("tasks_coin", 0) == before + 3
```
(Seed `gd._task_coin_rewards = {state.task_code: 3}`; assert the delta. Also assert task state still cleared as before — no regression to the existing clear-on-complete behavior.)

- [ ] **Step 2: Run, verify failure**

Expected: FAIL — coins not minted (apply currently leaves inventory untouched).

- [ ] **Step 3: Wire `apply`**

Add imports at top of `complete_task.py`:
```python
from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure
```
In `apply`, compute the reward and mint into inventory; add `inventory=` to the `dataclasses.replace`:
```python
    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
        coin_reward = game_data.task_coin_reward(state.task_code)
        inventory = complete_task_apply_pure(state.inventory, coin_reward)
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            cooldown_expires=None,
            task_code="",
            task_type="",
            task_progress=0,
            task_total=0,
            task_lifecycle_phase=TaskLifecyclePhase.NONE,
            xp=state.xp + TASK_COMPLETE_XP_ESTIMATE,
            inventory=inventory,
        )
```
Update the docstring/`TASK_COMPLETE_XP_ESTIMATE` comment note: completion now mints the task's `tasks_coin` reward (previously inventory was untouched; the API grants items+gold — coins are the planner-relevant reward for funding).

- [ ] **Step 4: Run, verify pass + no CompleteTask regression**

Run: `~/.local/bin/uv run pytest <the complete-task test file> -q`
Expected: PASS (new minting test + existing clear-on-complete tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/complete_task.py tests/test_ai/<file>
git commit -m "feat(actions): CompleteTaskAction.apply mints tasks_coin via proved core (C2)"
```

---

### Task 6: Mutation coverage

**Files:**
- Modify: `formal/diff/mutate.py` (add `COMPLETE_TASK_CORE_SRC`, `COMPLETE_TASK_MUTATIONS`, `_ALL_SRCS` entry, `run_group`)

- [ ] **Step 1: Add the mutation group**

Constant near the other `*_CORE_SRC` (and add to `_ALL_SRCS`):
```python
COMPLETE_TASK_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "complete_task_core.py"
```
Mutations (verify the `old` strings against the actual file text before running — match whitespace exactly):
```python
# Killed by formal/diff/test_complete_task_income_diff.py (binds complete_task_apply_pure
# to the proved Formal.CompleteTaskIncome.applyComplete).
COMPLETE_TASK_MUTATIONS = [
    ("complete_task: mint zero instead of coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0)"),
    ("complete_task: subtract instead of add the reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) - coin_reward"),
]
```
Register: `run_group(COMPLETE_TASK_CORE_SRC, COMPLETE_TASK_MUTATIONS, "formal/diff/test_complete_task_income_diff.py", survivors)`

- [ ] **Step 2: Confirm bot stopped, run the group**

```bash
ps aux | grep "artifactsmmo play" | grep -v grep   # must be empty
cd formal && export PATH="$HOME/.elan/bin:$PATH" && ~/.local/bin/uv run python diff/mutate.py --only complete_task_income
```
Expected: 0 survivors (both mutants killed by the differential). NOTE: `--only` matches by src/test path substring — use `complete_task` (matches `complete_task_core.py` and the test path). Confirm it selects only this group.

- [ ] **Step 3: Verify tree clean**

Run: `git diff --stat src` → empty.

- [ ] **Step 4: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(formal): mutation coverage for complete_task coin minting (C2)"
```

---

## Self-Review
- Coin income modeled + minted: Tasks 1,2,3,5. ✓
- Conservative floor for unknown/`__pending__` task (no defaulting; min is API-derived): Task 1. ✓
- Proved core LIVE (apply calls `complete_task_apply_pure`): Task 5 — verify `grep complete_task_apply_pure src/` shows the live caller in complete_task.py. ✓
- Monotonicity proof (the C3 progress fact): Task 3. ✓
- Differential + mutation give teeth: Tasks 4,6. ✓
- Placeholder note: Task 5 Steps 1/4 reference "the existing CompleteTaskAction test file" — the implementer must `grep -rl CompleteTaskAction tests/` and use the real file + its fixtures (do not hand-roll WorldState's 20 args).

## Out of scope (C3/C4)
- The `ReachCurrency` funding subgoal + termination liveness (C3).
- Demand routing + affordability fast-fail + deep-leaf buy emission (C4).
- Modeling the task GRIND cost (kept abstract per the spec's accepted cost-abstraction decision).
