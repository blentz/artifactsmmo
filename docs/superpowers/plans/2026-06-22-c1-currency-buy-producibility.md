# C1 — Task-Currency Producibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `is_attainable`/`_producible` recognize an item earned by completing tasks (`tasks_coin`) as an attainable acquisition leaf, so `jasper_crystal` (bought with `tasks_coin`) and therefore `satchel` rank as attainable instead of being filtered out.

**Architecture:** Add a task-reward data loader to `GameData` (so the code base knows, from API data, which items are task-earnable). Extract the acquisition-leaf decision into a proved pure core (`leaf_attainable_pure`) with a Lean mirror + differential + mutation gate. Wire `is_attainable.leaf_ok` and `_producible` to consult the core's new `task_earnable` disjunct.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (kernel proofs, no mathlib for this core), Hypothesis (differential), `formal/diff/mutate.py` (mutation), pytest (≥90% / 100% coverage).

## Global Constraints

- ALWAYS prefix Python with `uv run` (uv at `~/.local/bin/uv`). e.g. `~/.local/bin/uv run pytest`.
- Imports at top of file. No inline imports. No `if TYPE_CHECKING`. No `...` imports. Absolute imports only.
- ONE behavioral class per file. Pure-data/schema groups may share a module.
- NEVER catch `Exception`. Use only API data or fail with an error — no defaulting.
- Tests in `tests/`. Success = 0 errors, 0 warnings, 0 skipped, 100% coverage on touched modules.
- **SERIALIZATION:** the live bot imports `src`. `mutate.py`/`gate.sh` rewrite `src` and MUST NOT run while the bot is live (memory `feedback_serialize_gate_runs`). `lake build` + read-only differential pytest are safe meanwhile. Run the mutation step (Task 6) only after confirming the bot is stopped; `git diff src` after.
- **DEPLOY GATE:** C1 only unblocks RANKING. Do NOT let the live bot run C1's new behavior until C2–C4 land (else the still-unfundable satchel craft burns nodes — possibly worse). Build/prove C1 now; deployment waits.

---

### Task 1: Load task-reward item codes into GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (add `_fetch_tasks`, `_build_tasks`, `is_task_earnable`, `task_reward_item_codes`; wire into `load()` at lines 905-953)
- Modify: `src/artifactsmmo_cli/ai/game_data.py` import block (add `TaskFullSchema`, `get_all_tasks_tasks_list_get`)
- Test: `tests/test_ai/test_game_data_task_rewards.py`

**Interfaces:**
- Produces: `GameData.is_task_earnable(code: str) -> bool` — True iff `code` appears in some task definition's reward items.
- Produces: `GameData.task_reward_item_codes` (read-only `frozenset[str]`), backing field `self._task_reward_item_codes: frozenset[str]` (default empty).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_game_data_task_rewards.py
"""GameData task-reward loading: which item codes are earnable by completing tasks."""
from artifactsmmo_cli.ai.game_data import GameData


def _seed(codes: set[str]) -> GameData:
    gd = GameData()
    gd._task_reward_item_codes = frozenset(codes)
    return gd


def test_is_task_earnable_true_for_reward_item():
    gd = _seed({"tasks_coin"})
    assert gd.is_task_earnable("tasks_coin") is True


def test_is_task_earnable_false_for_non_reward_item():
    gd = _seed({"tasks_coin"})
    assert gd.is_task_earnable("copper_ore") is False


def test_task_reward_item_codes_empty_by_default():
    assert GameData().task_reward_item_codes == frozenset()


def test_build_tasks_collects_reward_item_codes():
    gd = GameData()
    gd._build_tasks(_fake_tasks())
    assert "tasks_coin" in gd.task_reward_item_codes


class _FakeItem:
    def __init__(self, code: str) -> None:
        self.code = code


class _FakeRewards:
    def __init__(self, items: list[_FakeItem]) -> None:
        self.items = items


class _FakeTask:
    def __init__(self, items: list[str]) -> None:
        self.rewards = _FakeRewards([_FakeItem(c) for c in items])


def _fake_tasks() -> list[_FakeTask]:
    return [_FakeTask(["tasks_coin"]), _FakeTask(["tasks_coin"])]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_game_data_task_rewards.py -v`
Expected: FAIL — `AttributeError: 'GameData' object has no attribute 'is_task_earnable'` / `_build_tasks`.

- [ ] **Step 3: Add the backing field + accessors + builder**

In `game_data.py`, add to the import block (top, with the other api imports):

```python
from artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get import sync as get_all_tasks
from artifactsmmo_api_client.models.task_full_schema import TaskFullSchema
```

Add the backing field near the other private fields (e.g. after the bank fields) — use a dataclass field default:

```python
_task_reward_item_codes: frozenset[str] = field(default_factory=frozenset)
```

Add the accessors + loaders as methods on `GameData` (place `_fetch_tasks`/`_build_tasks` next to `_fetch_bank`/`_build_bank` ~line 957; place `is_task_earnable`/`task_reward_item_codes` near the other public accessors):

```python
    @property
    def task_reward_item_codes(self) -> frozenset[str]:
        """Item codes granted by completing ANY task (API task-reward data).
        `tasks_coin` is the canonical member — it funds task-currency purchases
        (e.g. jasper_crystal @ tasks_trader)."""
        return self._task_reward_item_codes

    def is_task_earnable(self, code: str) -> bool:
        """True iff `code` is awarded by completing some task (so it is
        obtainable by the always-available task loop)."""
        return code in self._task_reward_item_codes

    def _fetch_tasks(self, client: AuthenticatedClient) -> list[TaskFullSchema]:
        """Page all task definitions; return the list of schema objects."""
        out: list[TaskFullSchema] = []
        page = 1
        while True:
            result = get_all_tasks(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_tasks(self, tasks: list[TaskFullSchema]) -> None:
        """Collect the set of item codes any task awards on completion."""
        self._task_reward_item_codes = frozenset(
            item.code for task in tasks for item in task.rewards.items
        )
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_game_data_task_rewards.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Wire the loader into `GameData.load()`**

In `load()` (game_data.py ~905-953) add `tasks` to all three places, mirroring `npcs`:
- `fetched` dict (cold branch, ~918): add `"tasks": data._fetch_tasks(client),`
- warm-branch `objs` (~943): add `"tasks": [TaskFullSchema.from_dict(d) for d in raw["tasks"]],`
- build calls (~951): add `data._build_tasks(objs["tasks"])`

- [ ] **Step 6: Verify the full existing suite still green (loader wiring)**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_game_data_task_rewards.py tests/test_ai/ -k "game_data or load" -v`
Expected: PASS, no regressions. (If a cache-shape test asserts the exact `raw`/`objs` key set, update it to include `"tasks"`.)

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data_task_rewards.py
git commit -m "feat(game_data): load task-reward item codes; is_task_earnable accessor"
```

---

### Task 2: Extract the acquisition-leaf pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py`
- Test: `tests/test_ai/test_leaf_attainable_core.py`

**Interfaces:**
- Produces: `leaf_attainable_pure(gatherable: bool, known_spawn_drop: bool, task_earnable: bool, buyable_with_attainable_currency: bool) -> bool` — the acquisition-leaf disjunction. The four flags are computed at the call site from `game_data`; the core is the pure decision.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_leaf_attainable_core.py
"""Pure core: an acquisition leaf is attainable iff at least one source applies."""
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure


def test_none_of_the_sources_not_attainable():
    assert leaf_attainable_pure(False, False, False, False) is False


def test_task_earnable_alone_is_attainable():
    # The C1 fix: tasks_coin is earnable even with no other source.
    assert leaf_attainable_pure(False, False, True, False) is True


def test_gatherable_alone_is_attainable():
    assert leaf_attainable_pure(True, False, False, False) is True


def test_known_spawn_drop_alone_is_attainable():
    assert leaf_attainable_pure(False, True, False, False) is True


def test_currency_buy_alone_is_attainable():
    assert leaf_attainable_pure(False, False, False, True) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_leaf_attainable_core.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py
"""Pure core of the acquisition-leaf attainability decision.

Extracted so the formal differential test (`formal/diff/test_leaf_attainable_diff.py`)
can exercise the exact decision against the kernel-proved Lean model
`Formal.LeafAttainable.leafAttainable` (`formal/Formal/LeafAttainable.lean`).

A recipe-closure LEAF (an item with no recipe of its own, bottoming out the
craft walk) is attainable iff at least one acquisition source applies. The
`task_earnable` disjunct is the C1 addition: an item awarded by completing tasks
(e.g. `tasks_coin`) is obtainable via the always-available task loop, which in
turn funds task-currency purchases (jasper_crystal @ tasks_trader -> satchel).
"""


def leaf_attainable_pure(gatherable: bool, known_spawn_drop: bool,
                         task_earnable: bool,
                         buyable_with_attainable_currency: bool) -> bool:
    """True ⇒ the leaf can be acquired by some known means; False ⇒ dead leaf.

    Mirrors `Formal.LeafAttainable.leafAttainable`:
    `gatherable || knownSpawnDrop || taskEarnable || buyableWithAttainableCurrency`.
    """
    return (gatherable or known_spawn_drop or task_earnable
            or buyable_with_attainable_currency)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_leaf_attainable_core.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py tests/test_ai/test_leaf_attainable_core.py
git commit -m "feat(tiers): extract leaf_attainable_pure acquisition-leaf core"
```

---

### Task 3: Lean model + role theorems (`Formal/LeafAttainable.lean`)

**Files:**
- Create: `formal/Formal/LeafAttainable.lean`
- Modify: `formal/Formal.lean` (add `import Formal.LeafAttainable` near line 205)
- Modify: `formal/Formal/Manifest.lean` (add `import Formal.LeafAttainable` near line 24; add role `#check`s near line 1094)
- Modify: `formal/Formal/Contracts.lean` (add `import Formal.LeafAttainable` near line 14; add anti-weakening pins near line 2828)

**Interfaces:**
- Produces: `Formal.LeafAttainable.leafAttainable (gatherable knownSpawnDrop taskEarnable buyable : Bool) : Bool`
- Produces theorems: `leafAttainable_iff_or` (validity), `leafAttainable_task_earnable` (the C1 source is load-bearing), `leafAttainable_monotone_task` (monotonicity).

- [ ] **Step 1: Write the Lean model + theorems**

```lean
-- formal/Formal/LeafAttainable.lean
-- @concept: core, planner @property: validity, monotonicity
/-
Acquisition-leaf attainability, mirroring
`src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py::leaf_attainable_pure`
and the `leaf_ok` disjunction in `tiers/objective.py::is_attainable`.

A recipe-closure LEAF is attainable iff some acquisition source applies:
gatherable, dropped by a known-spawn monster, EARNED BY COMPLETING TASKS
(the C1 addition — e.g. `tasks_coin`), or buyable with an attainable currency.

Lean core only — no mathlib.
-/

namespace Formal.LeafAttainable

/-- The leaf-attainability decision: a 4-way disjunction over acquisition sources. -/
def leafAttainable (gatherable knownSpawnDrop taskEarnable buyable : Bool) : Bool :=
  gatherable || knownSpawnDrop || taskEarnable || buyable

/-- **VALIDITY.** The decision is exactly the disjunction of its sources. -/
theorem leafAttainable_iff_or (g d t b : Bool) :
    leafAttainable g d t b = (g || d || t || b) := rfl

/-- **TASK-SOURCE LOAD-BEARING.** An item earned by completing tasks is
attainable even when NO other source applies (the C1 fix: `tasks_coin`). A
mutant that drops the `taskEarnable` disjunct fails this. -/
theorem leafAttainable_task_earnable (g d b : Bool) :
    leafAttainable g d true b = true := by
  simp [leafAttainable]

/-- **MONOTONICITY.** Gaining the task-earnable source never makes an attainable
leaf un-attainable (each disjunct is positive). -/
theorem leafAttainable_monotone_task (g d t b : Bool) :
    leafAttainable g d t b = true → leafAttainable g d true b = true := by
  intro _; simp [leafAttainable]

/-! ### Non-vacuity witnesses. -/
-- No source ⇒ dead leaf (the pruned case is genuinely reachable).
example : leafAttainable false false false false = false := by decide
-- Each source alone suffices.
example : leafAttainable true false false false = true := by decide
example : leafAttainable false true false false = true := by decide
example : leafAttainable false false true false = true := by decide
example : leafAttainable false false false true = true := by decide

end Formal.LeafAttainable
```

- [ ] **Step 2: Add imports to Formal.lean, Manifest.lean, Contracts.lean**

`formal/Formal.lean` (~205, with the other component imports):
```lean
import Formal.LeafAttainable
```

`formal/Formal/Manifest.lean` import block (~24):
```lean
import Formal.LeafAttainable
```
…and the role roster (after the SkillGateFastFail block ~1094):
```lean
-- LeafAttainable required roles (acquisition-leaf attainability;
-- src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py + tiers/objective.py is_attainable):
#check @Formal.LeafAttainable.leafAttainable_iff_or          -- validity: decision = disjunction
#check @Formal.LeafAttainable.leafAttainable_task_earnable   -- task source alone ⇒ attainable
#check @Formal.LeafAttainable.leafAttainable_monotone_task   -- monotone in the task source
```

`formal/Formal/Contracts.lean` import block (~14):
```lean
import Formal.LeafAttainable
```
…and the anti-weakening pins (after the SkillGateFastFail pins ~2828):
```lean
-- ─── LeafAttainable (acquisition-leaf attainability) anti-weakening pins ───
-- VALIDITY: the decision is EXACTLY the 4-way source disjunction (weakening any
-- term — e.g. dropping taskEarnable — fails to elaborate against this rfl).
example : ∀ (g d t b : Bool),
    Formal.LeafAttainable.leafAttainable g d t b = (g || d || t || b) :=
  @Formal.LeafAttainable.leafAttainable_iff_or
-- TASK SOURCE: earned-by-task ⇒ attainable regardless of other sources.
example : ∀ (g d b : Bool), Formal.LeafAttainable.leafAttainable g d true b = true :=
  @Formal.LeafAttainable.leafAttainable_task_earnable
```

- [ ] **Step 3: Build the Lean package (kernel-checks the proofs)**

Run: `cd formal && ~/.local/bin/lake build`
Expected: build succeeds; no `sorry`/axiom warnings. (Safe to run while the bot is live — Lean does not import `src`.)

- [ ] **Step 4: Verify axiom hygiene**

Run: `cd formal && ~/.local/bin/lake env lean --run /dev/stdin <<'EOF'
import Formal.LeafAttainable
open Formal.LeafAttainable
#print axioms leafAttainable_iff_or
#print axioms leafAttainable_task_earnable
#print axioms leafAttainable_monotone_task
EOF`
Expected: each lists only `[propext, Classical.choice, Quot.sound]` (no `sorryAx`, no `ofReduceBool`). If `check_axioms.sh` exists in `formal/`, run it instead.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/LeafAttainable.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(formal): LeafAttainable model + validity/monotonicity roles + pins"
```

---

### Task 4: Oracle handler + differential test (bind Python core to Lean)

**Files:**
- Modify: `formal/Oracle.lean` (add `runLeafAttainable`; route `"leaf_attainable"`)
- Create: `formal/diff/test_leaf_attainable_diff.py`

**Interfaces:**
- Consumes: `leaf_attainable_pure` (Task 2), `Formal.LeafAttainable.leafAttainable` (Task 3), `run_oracle` (`formal/diff/oracle_client.py`).
- Produces: oracle `kind="leaf_attainable"`, args `[gatherable, known_spawn_drop, task_earnable, buyable]` (0/1), result `{"attainable": bool}`.

- [ ] **Step 1: Add the oracle handler + route**

In `formal/Oracle.lean`, after `runGatherPlannable` (~1974):
```lean
-- LeafAttainable: acquisition-leaf attainability.
-- args = [gatherable(0/1), knownSpawnDrop(0/1), taskEarnable(0/1), buyable(0/1)]
def runLeafAttainable (args : Array Json) : Json :=
  let a := Formal.LeafAttainable.leafAttainable
    (intArg args 0 != 0) (intArg args 1 != 0) (intArg args 2 != 0) (intArg args 3 != 0)
  Json.mkObj [("attainable", Json.bool a)]
```
…and in `runOne` dispatch (after the `gather_plannable` branch ~2247):
```lean
  else if kind == "leaf_attainable" then
    runLeafAttainable args
```

- [ ] **Step 2: Write the differential test**

```python
# formal/diff/test_leaf_attainable_diff.py
"""Differential: real `leaf_attainable_pure` must agree with the kernel-proved
`Formal.LeafAttainable.leafAttainable` over ALL boolean tuples."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from formal.diff.oracle_client import run_oracle


@given(g=st.booleans(), d=st.booleans(), t=st.booleans(), b=st.booleans())
def test_leaf_attainable_matches_oracle(g, d, t, b):
    py = leaf_attainable_pure(g, d, t, b)
    lean = run_oracle("leaf_attainable", [[int(g), int(d), int(t), int(b)]])[0]["attainable"]
    assert py == lean, f"divergence at (g={g}, d={d}, t={t}, b={b}): py={py} lean={lean}"


def test_task_earnable_alone_attainable_both_sides():
    """The C1 case: task-earnable with no other source ⇒ attainable on both sides."""
    assert leaf_attainable_pure(False, False, True, False) is True
    assert run_oracle("leaf_attainable", [[0, 0, 1, 0]])[0]["attainable"] is True
```

- [ ] **Step 3: Rebuild the oracle**

Run: `cd formal && ~/.local/bin/lake build oracle`
Expected: builds the updated `oracle` binary.

- [ ] **Step 4: Run the differential test**

Run: `~/.local/bin/uv run pytest formal/diff/test_leaf_attainable_diff.py -v`
Expected: PASS (property + the task-earnable case).

- [ ] **Step 5: Commit**

```bash
git add formal/Oracle.lean formal/diff/test_leaf_attainable_diff.py
git commit -m "feat(formal): leaf_attainable oracle handler + differential test"
```

---

### Task 5: Wire `is_attainable` and `_producible` to the task-earnable leaf

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py` (`is_attainable.leaf_ok`, ~113-121)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`_producible`, 239-258)
- Test: `tests/test_ai/test_objective_attainable.py` (add cases), `tests/test_ai/test_strategy_producible.py` (add cases)

**Interfaces:**
- Consumes: `GameData.is_task_earnable` (Task 1), `leaf_attainable_pure` (Task 2).

- [ ] **Step 1: Write failing tests for the wiring**

```python
# tests/test_ai/test_objective_attainable.py  (add)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.objective import is_attainable


def _gd_with_task_currency_recipe() -> GameData:
    """satchel craftable from a task-earnable leaf; minimal seed."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    # satchel recipe -> needs jasper_crystal; jasper bought w/ tasks_coin.
    gd.recipes_catalog.recipes["satchel"] = {"jasper_crystal": 1}
    gd.world.npc_tiles["tasks_trader"] = (1, 2)
    gd.world.npc_stock.setdefault("tasks_trader", {})["jasper_crystal"] = 8
    gd.world.npc_buy_currency.setdefault("tasks_trader", {})["jasper_crystal"] = "tasks_coin"
    return gd


def test_jasper_crystal_attainable_via_task_currency():
    gd = _gd_with_task_currency_recipe()
    assert is_attainable("jasper_crystal", gd) is True


def test_satchel_attainable_via_task_currency_leaf():
    gd = _gd_with_task_currency_recipe()
    assert is_attainable("satchel", gd) is True
```

> NOTE: confirm the exact seeding helpers (`recipes_catalog.recipes`, `world.npc_*`)
> against the existing fixtures in `tests/test_ai/test_objective_attainable.py`;
> reuse that file's established builder if present rather than the minimal seed above.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_objective_attainable.py -k task_currency -v`
Expected: FAIL — `is_attainable` returns False (task-earnable leaf not recognized).

- [ ] **Step 3: Add the task-earnable disjunct in `is_attainable.leaf_ok`**

`objective.py` `leaf_ok` (currently ~113-121) — add `is_task_earnable` as an early-True source:
```python
    def leaf_ok(leaf: str, path: frozenset[str]) -> bool:
        if (_gatherable(leaf, game_data)
                or _drops_from_spawning_monster(leaf, game_data)
                or game_data.is_task_earnable(leaf)):
            return True
        if leaf in path:
            return False
        sub = path | {leaf}
        return any(currency == GOLD
                   or _attainable_closure(currency, game_data, leaf_ok, sub)
                   for _price, currency in _permanent_vendor_purchases(leaf, game_data))
```

- [ ] **Step 4: Add the task-earnable + currency-buy source to `_producible`**

`strategy.py` `_producible` (239-258). Make it consult the closure via `is_attainable` for the currency/task leaf-type while preserving its state-aware winnable-drop check. Minimal, consistent change — recognize task-earnable and permanent currency-buy:
```python
    if (game_data.crafting_recipe(code) is not None
            or code in game_data.resource_drops.values()
            or game_data.is_task_earnable(code)
            or is_attainable(code, game_data)):
        return True
    return any(is_winnable(state, game_data, monster_code)
               and game_data.monster_locations(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))
```
Add `from artifactsmmo_cli.ai.tiers.objective import is_attainable` to the top of `strategy.py` if not already imported. (If this introduces a circular import, instead inline the task-earnable + `_permanent_vendor_purchases` check rather than calling `is_attainable`; verify with the import test in Step 6.)

- [ ] **Step 5: Add `_producible` wiring tests**

```python
# tests/test_ai/test_strategy_producible.py  (add)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.strategy import _producible
from artifactsmmo_cli.ai.world_state import WorldState


def test_producible_recognizes_task_earnable_currency(seeded_state: WorldState):
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    assert _producible("tasks_coin", seeded_state, gd) is True
```

> NOTE: reuse the existing `WorldState` fixture from the test module/conftest;
> do not hand-roll a state if one exists.

- [ ] **Step 6: Run the wiring tests + import sanity**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_objective_attainable.py tests/test_ai/test_strategy_producible.py -v`
Run: `~/.local/bin/uv run python -c "import artifactsmmo_cli.ai.tiers.strategy"`  (no circular-import error)
Expected: PASS; clean import.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_objective_attainable.py tests/test_ai/test_strategy_producible.py
git commit -m "feat(tiers): recognize task-earnable currency as attainable leaf (C1)"
```

---

### Task 6: Mutation coverage (run only when the bot is stopped)

**Files:**
- Modify: `formal/diff/mutate.py` (add `LEAF_ATTAINABLE_CORE_SRC`, `LEAF_ATTAINABLE_MUTATIONS`, `run_group` call)

**Interfaces:**
- Consumes: `leaf_attainable_pure` (Task 2), `test_leaf_attainable_diff.py` (Task 4).

- [ ] **Step 1: Add the mutation group**

In `formal/diff/mutate.py`, near the other core SRC constants (~154):
```python
LEAF_ATTAINABLE_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "leaf_attainable_core.py"
```
Near the other mutation lists (~1642), define mutations that drop each disjunct — each must be killed by the differential test:
```python
# Killed by formal/diff/test_leaf_attainable_diff.py (binds leaf_attainable_pure
# to the proved Formal.LeafAttainable.leafAttainable).
LEAF_ATTAINABLE_MUTATIONS = [
    ("leaf_attainable: drop the task-earnable disjunct",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return (gatherable or known_spawn_drop\n            or buyable_with_attainable_currency)"),
    ("leaf_attainable: drop the currency-buy disjunct",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return (gatherable or known_spawn_drop or task_earnable)"),
    ("leaf_attainable: collapse to always-True",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return True"),
]
```
And register the group with the other `run_group` calls (~3602):
```python
    run_group(LEAF_ATTAINABLE_CORE_SRC, LEAF_ATTAINABLE_MUTATIONS,
              "formal/diff/test_leaf_attainable_diff.py", survivors)
```

- [ ] **Step 2: Confirm the bot is stopped, then run the mutation group**

```bash
ps aux | grep "artifactsmmo play" | grep -v grep   # must be empty
```
If empty, run the mutation runner (rewrites src transiently):
Run: `cd formal && ~/.local/bin/uv run python diff/mutate.py`  (or the project's documented mutation entrypoint)
Expected: 0 survivors for the LeafAttainable group (each dropped disjunct / always-True is killed).

- [ ] **Step 3: Verify src is clean after mutation**

Run: `git diff --stat src`
Expected: empty (mutation runner restores originals). If not, `git checkout -- src` and investigate.

- [ ] **Step 4: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(formal): mutation coverage for leaf_attainable disjuncts (C1)"
```

---

## Self-Review

**Spec coverage (C1 section):**
- Task-earnable leaf-type recognized → Tasks 1, 3, 5. ✓
- Data loading for task rewards (game_data) → Task 1. ✓
- Reconcile `_producible` with `is_attainable` → Task 5. ✓
- Permanent-vendor exclusion of event NPCs → already in `_permanent_vendor_purchases` (objective.py:88-96), unchanged by C1; no new task needed. ✓
- Full formal gate (Lean def, roles, Manifest, Contracts, Oracle, differential, mutation, unit tests) → Tasks 2-6. ✓
- Does-not-fix-burn-alone / deploy gate → Global Constraints. ✓

**Placeholder scan:** the two `> NOTE:` blocks (Task 5 Steps 1, 5) direct the implementer to reuse existing fixtures rather than the minimal seed — these are guidance, and both provide working fallback code. The mutation `old`/`new` strings must match the exact formatting written in Task 2 Step 3 (verify whitespace before running). No TBD/TODO remain.

**Type consistency:** `leaf_attainable_pure(gatherable, known_spawn_drop, task_earnable, buyable_with_attainable_currency)` / `leafAttainable (gatherable knownSpawnDrop taskEarnable buyable)` / oracle args `[g,d,t,b]` are consistent across Tasks 2-4-6. `is_task_earnable`/`task_reward_item_codes` consistent across Tasks 1-5.

## Out of scope (deferred to C2–C4)
- Minting `tasks_coin` on task completion (C2).
- `ReachCurrency` funding subgoal + termination liveness (C3).
- Deep-leaf buy emission + affordability fast-fail + demand routing (C4).
- The `copper_ring` ~52K-node churn (separate follow-up).
