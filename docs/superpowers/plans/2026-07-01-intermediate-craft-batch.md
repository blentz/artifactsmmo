# Intermediate-Craft Batching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Task 1 touches the formal perimeter — use the **formal-development** / **lean4** skills for its Lean/diff/mutation steps.

**Goal:** Batch intermediate crafts (bars, planks) to their inventory-bounded closure demand across all emitting goals, so `Craft(ash_plank×1)×56` collapses to a handful of batched crafts instead of one per cycle.

**Architecture:** Generalize the proven `task_batch_size_pure` inventory-bounded batch core into a code-agnostic `craft_batch_size_pure(code, demand, …)`; a shared `size_intermediate_craft` helper rebatches each intermediate `CraftAction` to `min(net_demand, inventory_fit, BATCH_CAP)`; every emitting goal calls the helper in its intermediate-craft branch. The change is planner-visible (the batched craft becomes applicable only once enough raws are held), sized so the raw footprint always fits inventory.

**Tech Stack:** Python 3.13, Lean 4 (formal core), pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run`.
- Imports at top of file only — no inline, no `...`, no `if TYPE_CHECKING`.
- One behavioral class per file; pure functions may share a module.
- Never catch `Exception`.
- Reuse `BATCH_CAP = 10`, `_MIN_FREE_SLOTS = 3` (task_batch.py) — do not introduce new constants.
- Formal perimeter: the differential gate (Python == Lean) and mutation gate must stay green; the extracted Lean is auto-generated (`scripts/extract_lean.py`) — never hand-edit `Extracted/*.lean`. Never run the formal gate concurrently with anything importing `src` ([[feedback_serialize_gate_runs]]).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

## Phase 1 — Generalize + prove the batch core

### Task 1: Extract `craft_batch_size_pure`; keep `task_batch_size_pure` as a wrapper; update the formal bridge

**Files:**
- Modify: `src/artifactsmmo_cli/ai/task_batch.py`
- Test: `tests/test_ai/test_task_batch.py` (existing) + new `craft_batch_size_pure` cases
- Formal: regenerate `formal/Formal/Extracted/TaskBatch.lean` (via extractor); `formal/Formal/TaskBatch.lean` (docstring/model note only — `batchSize` is already demand-generic); extend `formal/diff/test_task_batch_diff.py`; update `formal/diff/mutate.py` anchors.

**Interfaces:**
- Produces: `craft_batch_size_pure(code: str | None, demand: int, inventory: Mapping[str,int], inventory_free: int, recipes, drops) -> int`.
- `task_batch_size_pure` / `task_batch_size` keep their exact signatures + outputs (callers `strategy_driver.py:404`, `factory.py:271` unchanged).

- [ ] **Step 1: Write the failing pure-core tests**

Add to `tests/test_ai/test_task_batch.py` (follow its existing fixture style):

```python
from artifactsmmo_cli.ai.task_batch import (
    BATCH_CAP, craft_batch_size_pure, task_batch_size_pure,
)

_RECIPES = {"T": {"M": 2}}   # 2 raw M per unit of T
_DROPS = {"R": "M"}


def test_craft_batch_demand_bounded():
    # plenty of space, small demand -> demand wins
    assert craft_batch_size_pure("T", 3, {}, 100, _RECIPES, _DROPS) == 3


def test_craft_batch_inventory_bounded():
    # free=9, held=0, mats_per_unit=2 -> usable=(9-3)=6, fit=3 < demand 10
    assert craft_batch_size_pure("T", 10, {}, 9, _RECIPES, _DROPS) == 3


def test_craft_batch_cap_bounded():
    # huge demand + space -> capped at BATCH_CAP
    assert craft_batch_size_pure("T", 999, {}, 10_000, _RECIPES, _DROPS) == BATCH_CAP


def test_craft_batch_counts_held_drops_as_free():
    # held M reduces the space pressure: held=6 adds to usable
    # free=3, held=6 -> usable=(3+6-3)=6, fit=3
    assert craft_batch_size_pure("T", 10, {"M": 6}, 3, _RECIPES, _DROPS) == 3


def test_craft_batch_floors_at_one():
    # no space -> still 1 (never 0)
    assert craft_batch_size_pure("T", 5, {}, 0, _RECIPES, _DROPS) == 1


def test_craft_batch_base_item_no_raws():
    # code with no recipe -> mats_per_unit 0 -> demand/cap bounded, no div-by-zero
    assert craft_batch_size_pure("M", 4, {}, 100, _RECIPES, _DROPS) == 4


def test_task_batch_wrapper_matches_prior_outputs():
    # task path delegates: items task, total 8, progress 0, ample space -> min(8, cap)
    assert task_batch_size_pure("items", "T", 8, 0, {}, 100, _RECIPES, _DROPS) == 8
    # non-items task -> 1
    assert task_batch_size_pure("monsters", "T", 8, 0, {}, 100, _RECIPES, _DROPS) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_task_batch.py -k craft_batch -v`
Expected: FAIL — `ImportError: cannot import name 'craft_batch_size_pure'`.

- [ ] **Step 3: Implement the generalized core + wrapper**

Rewrite `src/artifactsmmo_cli/ai/task_batch.py` so the core is code-agnostic and the task function delegates. Keep `BATCH_CAP`, `_MIN_FREE_SLOTS`, and the module docstring intent:

```python
def craft_batch_size_pure(
    code: str | None,
    demand: int,
    inventory: Mapping[str, int],
    inventory_free: int,
    recipes: Mapping[str, dict[str, int]],
    drops: Mapping[str, str],
) -> int:
    """Runs to craft of `code` in one plan; >= 1 (pure core).

    Bounded by `demand` (units still needed), the inventory space the raws
    require (already-held closure drops count as free-equivalent so the batch
    stays stable as raws accumulate), and BATCH_CAP. `code` with no raw inputs
    (mats_per_unit == 0) is bounded by demand and the cap only."""
    if code is None or demand <= 0:
        return 1
    no_visited: dict[str, int] = {}
    mats_per_unit = _raw_units(len(recipes) + 1, code, recipes, {}, no_visited)
    if mats_per_unit == 0:
        return max(1, min(demand, BATCH_CAP))
    closure: dict[str, int] = {}
    closure = _closure_visited(len(recipes) + 1, code, recipes, closure)
    held_recipe = 0
    for _res, drop_item in drops.items():
        if closure.get(drop_item, 0) == 1:
            held_recipe = held_recipe + inventory.get(drop_item, 0)
    usable = (inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(demand, fit, BATCH_CAP))


def task_batch_size_pure(
    task_type, task_code, task_total, task_progress,
    inventory, inventory_free, recipes, drops,
) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1 (pure core)."""
    if task_code is None:
        return 1
    if task_type != "items" or task_code == "" or task_total <= 0:
        return 1
    remaining = task_total - task_progress
    if remaining <= 0:
        return 1
    return craft_batch_size_pure(task_code, remaining, inventory,
                                 inventory_free, recipes, drops)
```

Keep `task_batch_size(state, game_data)` as-is (forwards to `task_batch_size_pure`).

- [ ] **Step 4: Run the pure-core tests + existing task tests**

Run: `uv run pytest tests/test_ai/test_task_batch.py -v`
Expected: PASS (new craft_batch cases + all existing task_batch tests — the wrapper preserves prior outputs).

- [ ] **Step 5: Regenerate the extracted Lean + check drift**

Run: `uv run python scripts/extract_lean.py`
Then: `uv run python scripts/extract_lean.py --check`
Expected: `Extracted/TaskBatch.lean` regenerates to include `craft_batch_size_pure` and the delegating `task_batch_size_pure`; the sha256 drift header matches (`--check` passes). Do NOT hand-edit the generated file.

- [ ] **Step 6: Update the hand model note + extend the differential oracle**

`formal/Formal/TaskBatch.lean`: `batchSize` already models the clamp with a
generic `remaining` demand and its five theorems (`batch_ge_one`,
`batch_le_remaining`, `batch_le_cap`, `batch_fits`, `non_task_one`) hold for any
demand — update only the module docstring to note the core is now shared by
`craft_batch_size_pure` (task = the `demand = remaining` specialization). If the
extracted shape requires a companion definition, add it via the **lean4** skill,
compiler-guided, reusing the existing clamp lemmas.

Extend `formal/diff/test_task_batch_diff.py`: add a Hypothesis property that
`craft_batch_size_pure` (via a real one-recipe world realizing `(mats, held,
demand)`, exactly like `_make_state`/`_gd`) agrees with the Lean `batchSize true
demand mats free held`, plus an explicit `mats_per_unit == 0` case (a code with no
recipe → `max(1, min(demand, cap))`).

- [ ] **Step 7: Update mutation anchors**

`formal/diff/mutate.py` (~lines 308-317): the anchor strings
`"return max(1, min(remaining, fit, BATCH_CAP))"` now live in
`craft_batch_size_pure` as `"return max(1, min(demand, fit, BATCH_CAP))"`. Update
the matched strings and add anchors for the new `mats_per_unit == 0` guard
(mutate `return max(1, min(demand, BATCH_CAP))` → drop the floor / drop the cap)
so a weakened guard is killed.

- [ ] **Step 8: Run the formal gate (serialized — nothing else importing src)**

Run: `uv run pytest formal/diff/test_task_batch_diff.py -v` then the mutation
runner for task_batch and `lake build` per the formal gate (see `formal/` gate
script). Expected: differential green (Python == Lean over the sampled space),
all task_batch mutants killed, lake build clean, extractor drift check green.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/task_batch.py tests/test_ai/test_task_batch.py \
        formal/Formal/Extracted/TaskBatch.lean formal/Formal/TaskBatch.lean \
        formal/diff/test_task_batch_diff.py formal/diff/mutate.py
git commit -m "feat(task_batch): generalize inventory-bounded batch core to craft_batch_size_pure"
```

---

## Phase 2 — Shared helper + HIGH-impact goals

### Task 2: `size_intermediate_craft` shared helper

**Files:**
- Create: `src/artifactsmmo_cli/ai/intermediate_batch.py`
- Test: `tests/test_ai/test_intermediate_batch.py`

**Interfaces:**
- Consumes: `craft_batch_size_pure` (Task 1), `GameData.crafting_recipes`/`resource_drops`.
- Produces: `size_intermediate_craft(action: CraftAction, chain: Mapping[str,int], state: WorldState, game_data: GameData) -> CraftAction`.

- [ ] **Step 1: Write the failing test**

```python
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                              crafting_skill="mining", crafting_level=1),
                      "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    return gd


def test_intermediate_rebatched_to_demand():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    # demand 6 bars, ample inventory -> batched to 6 (< BATCH_CAP)
    state = make_state(inventory={"copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 6


def test_intermediate_subtracts_held():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    state = make_state(inventory={"copper_bar": 2, "copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 4   # 6 demand - 2 held


def test_intermediate_absent_from_chain_unchanged():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    out = size_intermediate_craft(a, {}, make_state(), gd)
    assert out.quantity == 1   # no demand -> floors at 1, action returned as-is
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_intermediate_batch.py -v`
Expected: FAIL — module/function not found.

- [ ] **Step 3: Implement**

```python
"""Rebatch an intermediate CraftAction to its inventory-bounded closure demand."""

import dataclasses
from collections.abc import Mapping

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import craft_batch_size_pure
from artifactsmmo_cli.ai.world_state import WorldState


def size_intermediate_craft(action: CraftAction, chain: Mapping[str, int],
                            state: WorldState, game_data: GameData) -> CraftAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its net closure demand (chain demand minus what is already held in
    inventory+bank). Unchanged when the sized quantity already matches."""
    held = state.inventory.get(action.code, 0) + (state.bank_items or {}).get(action.code, 0)
    demand = max(0, chain.get(action.code, 0) - held)
    qty = craft_batch_size_pure(action.code, demand, state.inventory,
                                state.inventory_free, game_data.crafting_recipes,
                                game_data.resource_drops)
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)
```

- [ ] **Step 4: Run to verify pass; mypy**

Run: `uv run pytest tests/test_ai/test_intermediate_batch.py -v && uv run mypy src/artifactsmmo_cli/ai/intermediate_batch.py`
Expected: PASS; mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/intermediate_batch.py tests/test_ai/test_intermediate_batch.py
git commit -m "feat: size_intermediate_craft rebatches intermediates to inventory-bounded demand"
```

---

### Task 3: Apply in GatherMaterials + the craft_plan_gen fast path

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py` (~line 181), `src/artifactsmmo_cli/ai/craft_plan_gen.py` (~line 186)
- Test: `tests/test_ai/test_gathering.py`, `tests/test_ai/test_craft_plan_gen.py`

**Interfaces:** Consumes `size_intermediate_craft` + the goal's existing `chain`.

- [ ] **Step 1: Write the failing test (gathering)**

Add to `tests/test_ai/test_gathering.py` (match its fixtures): construct a
`GatherMaterialsGoal` whose target needs ≥6 of a craftable intermediate with
ample held raws, call `relevant_actions`, and assert the emitted intermediate
`CraftAction.quantity > 1` (equals the inventory-bounded demand). Mirror the
existing `test_relevant_actions_*` setup in that file for the exact fixture shape.

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/test_ai/test_gathering.py -k intermediate -v`
Expected: FAIL — intermediate craft quantity is still 1.

- [ ] **Step 3: Implement (gathering.py)**

The `chain` is already built at `gathering.py:134-136`. In the action loop,
change the intermediate-craft arm so it rebatches. The current branch appends the
craft inside the combined `if (... or (isinstance(action, CraftAction) and
action.code in craftable_mats) or ...)`. Split the craftable-intermediate case out
so it can be sized:

```python
            if (isinstance(action, CraftAction) and action.code in craftable_mats):
                result.append(size_intermediate_craft(action, chain, state, game_data))
            elif (
                "recovery" in action.tags
                or "deposit" in action.tags
                or (isinstance(action, GatherAction) and action.resource_code in needed_resources)
                or (isinstance(action, WithdrawItemAction) and action.code in withdrawable)
            ):
                result.append(action)
```

Add `from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft`
at the top. (Preserve the surrounding gather-pruning / yield-narrowing logic.)

- [ ] **Step 4: Implement (craft_plan_gen.py:186) — same swap**

At `craft_plan_gen.py:186-187` the craft actions pass through unsized. Build/reuse
the `chain` (via `closure_demand` over the plan's target) and rebatch craftable
intermediates through `size_intermediate_craft`. If no `chain` exists there,
accumulate one with `closure_demand(target, qty, game_data, chain, frozenset())`.

- [ ] **Step 5: Run tests + mypy**

Run: `uv run pytest tests/test_ai/test_gathering.py tests/test_ai/test_craft_plan_gen.py -v && uv run mypy src/artifactsmmo_cli/ai/goals/gathering.py src/artifactsmmo_cli/ai/craft_plan_gen.py`
Expected: PASS; mypy clean. Existing gather/plan-gen tests stay green (single-unit demands still floor to 1).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py src/artifactsmmo_cli/ai/craft_plan_gen.py \
        tests/test_ai/test_gathering.py tests/test_ai/test_craft_plan_gen.py
git commit -m "feat(gather): batch intermediate crafts to inventory-bounded demand"
```

---

### Task 4: Apply in PursueTask

**Files:** Modify `src/artifactsmmo_cli/ai/goals/pursue_task.py` (~line 103); Test `tests/test_ai/test_pursue_task.py`.

- [ ] **Step 1: Write the failing test** — a PursueTask items-task whose target needs a multi-unit craftable intermediate; assert the emitted intermediate craft quantity > 1. Match the file's existing fixtures.
- [ ] **Step 2: Verify failure** — `uv run pytest tests/test_ai/test_pursue_task.py -k intermediate -v` → FAIL.
- [ ] **Step 3: Implement** — add the `size_intermediate_craft` import; ensure a `chain` exists (`closure_demand` over the task target — check whether pursue_task already builds one and reuse it); rebatch the intermediate-craft branch at line 103. Do NOT change the task-TARGET sizing (already `task_batch_size`).
- [ ] **Step 4: Run + mypy** — `uv run pytest tests/test_ai/test_pursue_task.py -v && uv run mypy src/artifactsmmo_cli/ai/goals/pursue_task.py` → PASS.
- [ ] **Step 5: Commit** — `feat(pursue_task): batch intermediate crafts to inventory-bounded demand`.

---

## Phase 3 — Remaining goals

### Task 5: craft_potions + maintain_consumables intermediates

**Files:** Modify `goals/craft_potions.py` (~line 159), `goals/maintain_consumables.py` (~line 82); Tests in the matching test files.

- [ ] **Step 1: Failing tests** — each goal, a target routed through a multi-unit craftable intermediate; assert the intermediate craft quantity > 1. (`craft_potions` already has `chain` at line 147-148; `maintain_consumables` builds one at line 69-71.)
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — import `size_intermediate_craft`; rebatch the `a.code in craftable_mats` branch in each, passing the goal's existing `chain`. Leave the target-craft rebatch (`runs`/`deficit`) and the buy sizing (already batched) untouched.
- [ ] **Step 4: Run + mypy** for both test modules → PASS.
- [ ] **Step 5: Commit** — `feat(potions,consumables): batch intermediate crafts`.

### Task 6: level_skill + progression intermediates

**Files:** Modify `goals/level_skill.py` (~line 146), `goals/progression.py` (~line 233); Tests in matching files.

- [ ] **Step 1: Failing tests** — each goal with a multi-unit craftable intermediate; assert quantity > 1. Build a `chain` via `closure_demand` where the goal lacks one.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — import + rebatch the intermediate branch; add the `chain` accumulation if absent.
- [ ] **Step 4: Run + mypy** → PASS.
- [ ] **Step 5: Commit** — `feat(level_skill,progression): batch intermediate crafts`.

---

## Phase 4 — Verification

### Task 7: Full-suite + formal gate + offline repro

**Files:** none (verification only).

- [ ] **Step 1: Full suite** — `uv run pytest` → 0 errors/warnings/skips, 100% coverage. (Live-API audit tests may flake under contention; re-run once.)
- [ ] **Step 2: Type check** — `uv run mypy src/artifactsmmo_cli/ai` → clean.
- [ ] **Step 3: Formal gate** — run the full `formal/` gate (lake build + differential + mutation + extractor drift), serialized. → green.
- [ ] **Step 4: Offline repro** — a throwaway script (scratchpad, delete after) building a GatherMaterials-style demand of ~56 of a 1-raw intermediate and asserting `size_intermediate_craft` (or the goal's `relevant_actions`) emits `quantity == min(56, inventory_fit, BATCH_CAP)` — i.e. batched, not 1. Print the collapsed craft count.
- [ ] **Step 5: If coverage < 100%** — add the missing-line test (likely a `craft_batch_size_pure` boundary or a goal branch), re-run. Do not lower the bar.

---

## Self-Review

- **Spec coverage:** Component 1 core generalization + formal (Task 1); Component 2 shared helper (Task 2); Component 3 all emitting goals (Tasks 3-6: gathering+fast-path, pursue_task, potions+consumables, level_skill+progression); phasing matches the spec; BATCH_CAP/MIN_FREE reused; net-demand-minus-held sizing (Task 2 Step 3); inventory-bounded via the proven core; testing incl. formal gate + repro (Task 7). All spec sections mapped.
- **Placeholder scan:** Python steps carry full code. The formal Lean-proof steps (Task 1 Step 6) intentionally defer proof text to the lean4/formal-development skill (compiler-guided) — the extracted Lean is auto-generated and the hand-model theorems are demand-generic and already proven, so no new hand proof is required beyond a possible companion def; the concrete files, diff-oracle shape, and mutation-anchor strings are specified. Per-goal application steps (Tasks 4-6) reference Task 3's fully-shown pattern rather than repeating identical code — the swap is one line plus ensuring `chain` exists, and each goal's `chain` source is named.
- **Type consistency:** `craft_batch_size_pure(code, demand, inventory, inventory_free, recipes, drops)` identical across Task 1 def/tests, Task 2 helper, Task 7 repro; `size_intermediate_craft(action, chain, state, game_data)` identical across Task 2 and Tasks 3-6; `task_batch_size` public API + callers unchanged.
- **Risk note:** Tasks 3-6 change planner-visible action quantities (the batched craft is applicable only once enough raws are held). Each task's test asserts the batched quantity; Task 7's full suite + any planner/integration tests guard against a plan becoming unsatisfiable — if an existing planner test regresses, that is a real interleave problem to investigate, not a test to edit.
