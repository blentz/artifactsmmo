# Planner Gather Batching + Single Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `GatherAction` a `quantity` so deep recipe chains are reachable inside `max_depth`, then delete the two-pass planning budget that was silently hiding their unreachability.

**Architecture:** `GatherAction` becomes the last acquisition edge to gain a quantity, sized by the consuming goal from its own demand closure exactly as `size_intermediate_craft` already sizes crafts. The plan cursor holds on a batched gather until the drop item's holding reaches a plan-time target, mirroring the `LevelSkill` planner-abstraction/player-expansion idiom. With chains reachable, the cheap/full two-pass arbiter walk collapses to a single 15 s budget, and a rank-1 objective that still fails to plan emits a trace event instead of vanishing.

**Tech Stack:** Python 3.13, `uv`, pytest, SQLModel/SQLite (learning store), Lean 4 + Mathlib (`formal/`), differential + mutation gate (`formal/gate.sh`).

**Spec:** `docs/superpowers/specs/2026-08-13-planner-batching-and-macro-edges-design.md`

## EXECUTION ORDER — corrected 2026-08-13 mid-flight (ledger Ruling 17)

**Run the tasks in this order, NOT in numeric order:**

```
1, 2, 4, 5, 6, 7, 8, 3, 9, 10, 11, 12, 13
```

Task 3 switches `min_plan_length` to the batched gather count, which makes
`is_plannable` admit goals on the assumption that one gather action mints a
whole material's demand. `GatherAction` does not batch until Task 5. Landing 3
first opens a window where the admission gate is more permissive than the
planner is capable, and A* is handed goals it cannot plan.

This was verified, not theorised: with Task 3 applied and nothing else,
`tests/test_ai/test_upgrade_reachability_gate.py::test_is_plannable_rejects_from_scratch_feather_coat`
fails `assert True is False`, and 10 tests fail in total across
`test_strategy_driver.py` (6), `test_supply_bank_plannability.py` (2) and
`test_upgrade_reachability_gate.py` (2). Routing the `steel_boots` chain
straight to A* returns `plan == []`.

Those tests pin a real invariant — admission must not outrun capability — not a
stale boundary. Task 3's work is saved at
`.superpowers/sdd/2026-08-13-planner-gather-batching/task-3-staged.patch`;
re-apply it when Task 3 comes up. Expect the 10 failures to resolve once
gathers actually batch. **Any that do not are genuine regressions and must be
fixed, never rebaselined.**

## Global Constraints

- Run every Python command through `uv run` (e.g. `uv run pytest`, `uv run mypy`). Never bare `python`.
- One *behavioral* class per file. Module-level pure functions may share a module.
- No inline imports. All imports at the top of the file.
- No `if TYPE_CHECKING`, ever.
- Never `except Exception`. Catch the specific error or let it raise.
- No multiple implementations of the same thing — fix in place.
- Use only API data or fail with an error. No defaulting around missing game data.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100 % coverage.
- Never run `formal/gate.sh` or `formal/diff/mutate.py` concurrently with anything importing `src` — **including a running bot**. Check `pgrep -af artifactsmmo` first.
- Never pipe a gate run into `tail`: `bash formal/gate.sh | tail -3; echo $?` reports the tail's exit code. Redirect to a file, or use `${PIPESTATUS[0]}`.
- Mutation anchors must be refreshed in the **same commit** as the code they anchor to, and each must resolve to exactly one site (`--check-anchors`).
- No `sorry` in any Lean file. No vacuous theorems.
- This plan covers I1 and I3 only. I2 (macro composite edges) is a separate plan, written after this one lands.

---

### Task 1: `min_gather_steps` — batch-aware gather lower bound

`min_gathers` counts raw *units*. Under batching one action mints many units, so a plan can be shorter than that count and the "lower bound" stops being one. `min_crafts` already solves the identical problem for crafts by counting one craft per produced **node**, batch-agnostically. This task adds the gather twin.

`min_gathers` itself is NOT changed — `craft_vs_buy` and `gather_step_target` consume it as a count of real API actions, which is still per-unit and still correct for them.

**Files:**
- Create: `src/artifactsmmo_cli/ai/min_gather_steps.py`
- Test: `tests/test_ai/test_min_gather_steps.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `min_gather_steps(item: str, qty: int, recipes: Mapping[str, dict[str, int]], owned: dict[str, int]) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_min_gather_steps.py`:

```python
from artifactsmmo_cli.ai.min_gather_steps import min_gather_steps

RECIPES = {
    "greater_wooden_staff": {"spruce_plank": 6, "blue_slimeball": 2},
    "spruce_plank": {"spruce_wood": 10},
}


def test_raw_leaf_is_one_step_regardless_of_quantity():
    """A batched gather mints N units in one action, so 60 spruce_wood is ONE
    step, not 60. This is the whole point of the module."""
    assert min_gather_steps("spruce_wood", 60, RECIPES, {}) == 1


def test_one_step_per_distinct_raw_material():
    """staff <- 6 spruce_plank (<- spruce_wood) + 2 blue_slimeball.
    Two distinct raw leaves => two gather steps."""
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES, {}) == 2


def test_owned_covers_a_leaf_and_removes_its_step():
    owned = {"spruce_plank": 6}
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES, owned) == 1


def test_fully_owned_target_needs_no_gathers():
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES,
                            {"greater_wooden_staff": 1}) == 0


def test_owned_is_not_mutated():
    owned = {"spruce_plank": 6}
    min_gather_steps("greater_wooden_staff", 1, RECIPES, owned)
    assert owned == {"spruce_plank": 6}


def test_same_leaf_reached_twice_counts_once():
    """A leaf shared by two branches is one gather step, not two: one batched
    action covers the summed demand."""
    recipes = {"widget": {"left": 1, "right": 1},
               "left": {"ore": 4}, "right": {"ore": 7}}
    assert min_gather_steps("widget", 1, recipes, {}) == 1


def test_cyclic_recipe_terminates():
    """Fuel-bounded like min_gathers/min_crafts: a cycle must not RecursionError."""
    recipes = {"a": {"b": 1}, "b": {"a": 1}}
    assert min_gather_steps("a", 1, recipes, {}) >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_min_gather_steps.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.min_gather_steps'`

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/ai/min_gather_steps.py`:

```python
"""Pure lower bound on the GATHER ACTIONS a plan needs to obtain an item.

The twin of `min_crafts`, and the batch-aware replacement for
`ceil_gathers(min_gathers(...))` inside `min_plan_length`.

`min_gathers` counts raw UNITS, which was a sound lower bound on ACTIONS only
while one gather minted exactly one unit. `GatherAction` now carries a
`quantity`, so a single action mints the whole deficit of one material and a
real plan can be SHORTER than the unit count — at which point the unit count is
no longer a lower bound at all, and `is_plannable` (which consumes
`min_plan_length`) starts rejecting reachable goals.

One batched gather serves one raw material's entire demand, so the sound bound
is the number of DISTINCT raw leaves that must be gathered — exactly mirroring
`min_crafts`, which counts one craft per produced node irrespective of craft
batching.

`min_gathers` is deliberately left alone: `craft_vs_buy` and `gather_step_target`
consume it as a count of real API actions (units), which batching does not
change.

Kept pure (plain dicts, no GameData/WorldState) so the differential harness can
execute it against the Lean oracle. The recursion is FUEL-BOUNDED exactly as
`min_gathers`/`min_crafts` are: a cyclic recipe terminates instead of raising
RecursionError.
"""

from collections.abc import Mapping


def min_gather_steps(item: str, qty: int, recipes: Mapping[str, dict[str, int]],
                     owned: dict[str, int]) -> int:
    """Lower bound on batched gather ACTIONS to obtain `qty` of `item`.

    `recipes[code]` maps a craftable to its `{material: per_unit}` recipe; an
    item absent from `recipes` (or with an empty recipe) is raw. `owned` is
    consumed greedily on a private copy — the caller's dict is never mutated.
    """
    leaves: set[str] = set()
    _min_gather_steps(len(recipes) + 1, item, qty, recipes, dict(owned), leaves)
    return len(leaves)


def _min_gather_steps(fuel: int, item: str, qty: int,
                      recipes: Mapping[str, dict[str, int]],
                      owned: dict[str, int], leaves: set[str]) -> None:
    """Collect the raw leaves whose demand is not covered by `owned`.

    A leaf reached from two branches lands in the same set entry: one batched
    action covers the summed demand, so it is one step.
    """
    if fuel <= 0:
        leaves.add(item)
        return
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        leaves.add(item)
        return
    for material, per_unit in recipe.items():
        _min_gather_steps(fuel - 1, material, per_unit * remaining,
                          recipes, owned, leaves)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_min_gather_steps.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/min_gather_steps.py && uv run ruff check src/artifactsmmo_cli/ai/min_gather_steps.py`
Expected: no output from ruff, `Success` from mypy

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/min_gather_steps.py tests/test_ai/test_min_gather_steps.py
git commit -m "feat(ai): min_gather_steps counts gather ACTIONS, not raw units

min_gathers counts units, which bounded ACTIONS only while a gather minted
exactly one unit. Batched gathers break that, so min_plan_length needs a
node-counting twin — the same thing min_crafts already does for crafts.
min_gathers is untouched: craft_vs_buy and gather_step_target want units."
```

---

### Task 2: Lean — batched bound, and two false citations corrected

> **RESCOPED 2026-08-13 during execution (ledger Ruling 7).** This task
> originally said to re-prove `Formal.PlanModel.min_plan_length_le_plan` over a
> batched action model. **That theorem does not exist.**
> `grep -rn "min_plan_length_le_plan" --include=*.lean formal/` returns exactly
> one hit — line 4 of `PlanModel.lean`, inside a docstring — and
> `min_plan_length.py` cites it as "(proved: …)". The nearest real result is
> `minGathers_le_gathers_of_corner3` (`PlanModel.lean:3370`), whose `corner3`
> hypothesis is marked at line 3353 "RETIRED — intentionally not discharged".
> There is no craft lower bound at all. Nothing is falsified by batching
> because nothing was proved.

What this task does instead, in order of importance:

1. **Prove `minGatherSteps ≤ minGathersCount`.** The batched bound is never
   larger than the per-unit one, so `is_plannable` becomes strictly MORE
   permissive: no reachable goal is newly rejected. Wasted search is the only
   exposure. This is the property that actually protects the admission gate,
   and unlike the briefed theorem it is tractable.
2. **Correct the two false citations** — `PlanModel.lean:4` and
   `min_plan_length.py`'s docstring — to name what is actually proved and the
   hypothesis it rests on.
3. **Amend PlanModel's "NOT modelled" §4** to state plainly that the Python
   gather now batches while the model's `Action.gather` does not.

`Action.gather` is deliberately **NOT** widened with a quantity. Doing so makes
`plan_mass_invariant` false as stated unless `ExecState.gathers` switches from
counting actions to counting units, destabilising ~2900 lines of cost-mass
machinery — in service of plan-length results already conditional on a retired
hypothesis.

Do this **before** the Python switch so the oracle is never behind the
implementation.

**Files:**
- Modify: `formal/Formal/PlanModel.lean`
- Modify: `scripts/extract_lean.py` (register a `ModuleSpec`; the Extracted
  module is **generated**, never hand-written — every file under
  `formal/Formal/Extracted/` carries `-- GENERATED … DO NOT EDIT` and a sha256
  drift gate, `uv run python scripts/extract_lean.py --check`)
- Generate: `formal/Formal/Extracted/MinGatherSteps.lean`
- Modify: `src/artifactsmmo_cli/ai/min_plan_length.py` (citation only)
- Create: `formal/diff/test_min_gather_steps_diff.py`
- Modify: `formal/Formal/Manifest.lean`

**Interfaces:**
- Consumes: `min_gather_steps` from Task 1, in its extractor-compatible
  tuple-threaded form (Task 1 fix round 2).
- Produces: `Formal.PlanModel.minGatherSteps`; theorem
  `Formal.PlanModel.minGatherSteps_le_minGathers`.

- [ ] **Step 1: Read the existing model before touching it**

Run: `sed -n '1,200p' formal/Formal/PlanModel.lean`

Note in particular the `ValidPlan` predicate, the `foldl`-threaded `ExecState`, and the "NOT modelled" section — item 4 is the abstraction this task removes.

- [ ] **Step 2: Widen the gather action to carry a quantity**

In `formal/Formal/PlanModel.lean`, change the action type and its interpreter:

```lean
/-- The three action kinds in the plan model.
  * `gather code qty` — collect `qty` units of `code` in ONE action. The
    quantity is the batched-gather model (`GatherAction.quantity`); `qty = 1`
    recovers the pre-batching model exactly.
  * `craft  code` — produce one copy of `code` by consuming its recipe inputs.
  * `equip  code` — equip `code` from inventory (requires `code` in inventory). -/
inductive Action where
  | gather (code : String) (qty : Nat)
  | craft  (code : String)
  | equip  (code : String)
  deriving Repr, DecidableEq
```

Update `applyAction`'s `gather` arm to add `qty` (rather than `1`) to the holdings, and update `ValidPlan` and every `example` in the file to the new constructor arity. Update the "NOT modelled" section: item 4 no longer claims `gather` yields exactly one unit; it now claims only that `craft` produces exactly one copy.

- [ ] **Step 3: State the batched bound and prove it**

Add to `formal/Formal/PlanModel.lean`:

```lean
/-- Number of DISTINCT raw leaves a plan must gather — the batched-gather
lower bound on gather ACTIONS. Mirrors `min_gather_steps` in
`src/artifactsmmo_cli/ai/min_gather_steps.py`. -/
def minGatherSteps (recipes : Recipes) (owned : List (String × Int))
    (item : String) (qty : Int) : Nat := ...

/-- Soundness: no satisfying plan is shorter than the batched bound. -/
theorem min_gather_steps_le_plan
    (recipes : Recipes) (owned : List (String × Int))
    (item : String) (plan : Plan)
    (h : SatisfiesEquip recipes owned item plan) :
    minGatherSteps recipes owned item 1 + minCrafts recipes owned item 1 + 1
      ≤ plan.length := ...
```

Proof strategy — do not deviate without saying so:
1. Induct on `plan`, unfolding `List.foldl` one step.
2. Case-split on the action kind. The `gather code qty` arm is the only changed
   one: it contributes at most one to the action count while covering the whole
   of `code`'s demand, so the leaf-set measure drops by at most one element.
3. Use `ValidPlan` to obtain the recipe-input inequalities at each `craft`.
4. The `craft` and `equip` arms reuse the existing `min_plan_length_le_plan`
   argument verbatim — `minCrafts` is unchanged.

Keep `min_plan_length_le_plan` in the file, restated over `gather code 1`, so
the unbatched bound remains available and the two models are visibly related.

- [ ] **Step 4: Build**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: no errors, no `sorry` warnings, no `declaration uses 'sorry'`

- [ ] **Step 5: Verify no axioms leaked**

Run: `cd formal && grep -rn "sorry" Formal/PlanModel.lean Formal/Extracted/MinGatherSteps.lean`
Expected: no matches

- [ ] **Step 6: Add the differential harness**

Create `formal/diff/test_min_gather_steps_diff.py` following the shape of the
existing `formal/diff/test_*_diff.py` files — read one first:

Run: `sed -n '1,60p' formal/diff/test_action_cost_nonneg_diff.py`

The harness must drive the Python `min_gather_steps` and the Lean
`minGatherSteps` over the same generated `(recipes, owned, item, qty)` inputs
and assert equality, including the cyclic-recipe case.

- [ ] **Step 7: Run the differential harness**

Run: `uv run pytest formal/diff/test_min_gather_steps_diff.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add formal/Formal/PlanModel.lean formal/Formal/Extracted/MinGatherSteps.lean \
        formal/Formal/Manifest.lean formal/diff/test_min_gather_steps_diff.py
git commit -m "proof(formal): PlanModel's gather mints qty units, not one

min_plan_length_le_plan bounds plan length by RAW UNITS gathered. That was
sound only while Action.gather minted exactly one unit — the abstraction the
module's own NOT-modelled section 4 declared. Batched gathers make a real plan
shorter than the bound, so the theorem would still compile while no longer
describing the running planner, and is_plannable would reject reachable goals.

Widens Action.gather with a quantity and proves the batched bound. The
unbatched theorem is kept, restated over gather code 1."
```

---

### Task 3: `min_plan_length` switches to the batched bound

**Files:**
- Modify: `src/artifactsmmo_cli/ai/min_plan_length.py`
- Modify: `scripts/extract_lean.py` — this module IS extracted (spec at line 407). Its `imports=("ceil_gathers", "min_gathers", "min_crafts")` must become `("min_gather_steps", "min_crafts")`, and `Extracted/MinPlanLength.lean` regenerated, or `--check` fails.
- Test: `tests/test_ai/test_min_plan_length.py`

**Interfaces:**
- Consumes: `min_gather_steps` (Task 1).
- Produces: `min_plan_length(item, qty, recipes, owned, max_gather_yield, equip) -> int` — signature unchanged; `max_gather_yield` is now unused by the mint term and is retained only for call-site compatibility.

**Direction of the change — state it accurately in the commit message.** Task 2
proved `minGatherSteps ≤ minGathers`, so against the raw unit count the new
bound is never larger. But the term being REPLACED is
`ceil_gathers(min_gathers, max_gather_yield)`, not `min_gathers`. The two
coincide only at `max_gather_yield == 1`, which is the live value today (checked
2026-08-13: all 26 resources report `max_quantity` 1). Above 1 the leaf count
can EXCEED the ceiled unit count — 3 distinct materials vs `ceil(3/5) = 1` — and
admission would TIGHTEN for wide-shallow chains. Sound either way, but do not
write "strictly more permissive" without the `max_gather_yield == 1` qualifier.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_min_plan_length.py`:

```python
from artifactsmmo_cli.ai.min_plan_length import min_plan_length

_STAFF_RECIPES = {
    "greater_wooden_staff": {"spruce_plank": 6, "blue_slimeball": 2},
    "spruce_plank": {"spruce_wood": 10},
}


def test_deep_chain_is_admissible_under_batching():
    """Pre-batching this was ceil_gathers(60 spruce_wood + 2 slimeball) + 2
    crafts + equip = 65, well past UpgradeEquipmentGoal.max_depth 32, so
    is_plannable rejected the staff before A* ever ran. Batched: 2 gather
    steps + 2 crafts + 1 equip = 5."""
    assert min_plan_length("greater_wooden_staff", 1, _STAFF_RECIPES, {},
                           max_gather_yield=1, equip=True) == 5


def test_owned_materials_shorten_the_bound():
    owned = {"spruce_plank": 6, "blue_slimeball": 2}
    assert min_plan_length("greater_wooden_staff", 1, _STAFF_RECIPES, owned,
                           max_gather_yield=1, equip=True) == 2


def test_equip_flag_adds_exactly_one():
    args = ("greater_wooden_staff", 1, _STAFF_RECIPES, {})
    with_equip = min_plan_length(*args, max_gather_yield=1, equip=True)
    without = min_plan_length(*args, max_gather_yield=1, equip=False)
    assert with_equip - without == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_min_plan_length.py -v`
Expected: FAIL — `test_deep_chain_is_admissible_under_batching` asserts 5, gets 65

- [ ] **Step 3: Write minimal implementation**

Replace the body of `src/artifactsmmo_cli/ai/min_plan_length.py`:

```python
"""Lower bound on PLAN length to obtain (and optionally equip) `item`:
`min_gather_steps + min_crafts + (1 if equip)`. One batched gather serves one
raw material's whole demand, one craft per produced node, one equip.

DO NOT re-add a "(proved: Formal.PlanModel.min_plan_length_le_plan)" citation
here. Task 2 REMOVED it: that theorem has never existed. Preserve whatever
citation Task 2 left in place — it names a theorem that does exist and states
its undischarged hypothesis honestly.

The mint term was `ceil_gathers(min_gathers(...))` — raw UNITS — which bounded
plan length only while one gather minted one unit. `GatherAction.quantity`
makes a real plan shorter than that, so the unit count stopped being a lower
bound and this predicate began rejecting reachable goals: live 2026-08-12,
`UpgradeEquipment(greater_wooden_staff)` needed 60 spruce_wood and was refused
admission against `max_depth 32` on 955 of 955 cycles.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gather_steps import min_gather_steps


def min_plan_length(item: str, qty: int,
                    recipes: Mapping[str, dict[str, int]],
                    owned: dict[str, int], max_gather_yield: int,
                    equip: bool) -> int:
    """`max_gather_yield` is retained for call-site compatibility and is no
    longer consulted: a batched gather covers the whole demand of one material
    regardless of per-gather yield, so the yield only affects how many CYCLES
    that one action occupies, never the plan's length."""
    mints = min_gather_steps(item, qty, recipes, owned)
    crafts = min_crafts(item, qty, recipes, owned)
    return mints + crafts + (1 if equip else 0)
```

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/test_ai/test_min_plan_length.py -v`
Expected: PASS

- [ ] **Step 5: Run every consumer's tests — this predicate gates goal admission**

Run: `uv run pytest tests/test_ai/test_acquisition_cost_core.py tests/test_ai/test_acquisition_cost_baseline.py tests/test_ai/test_acquisition_cost_wrapper.py tests/test_ai/test_strategy_driver.py -q`
Expected: PASS. If an acquisition-cost baseline shifts, that is a **real** consequence — `acquisition_actions` prices through `min_plan_length` — so update the baseline and say so in the commit message rather than reverting the bound.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/min_plan_length.py tests/test_ai/test_min_plan_length.py
git commit -m "fix(ai): min_plan_length counts batched gather steps, not raw units

The mint term was ceil_gathers(min_gathers(...)) = raw units. With a batched
gather edge a real plan is shorter than that, so the value stopped being a
lower bound and is_plannable began rejecting reachable goals. Live 2026-08-12:
UpgradeEquipment(greater_wooden_staff) scored 65 against max_depth 32 and was
refused admission on 955 of 955 cycles while the bank held every material.

max_gather_yield is now unconsulted — yield decides how many CYCLES one batched
action occupies, never the plan's length."
```

---

### Task 4: batched mint in the gather pure core

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/gather_apply_core.py`
- Modify: `formal/Formal/GatherApply.lean`
- Test: `tests/test_ai/test_gather_apply_core.py`

**Interfaces:**
- Consumes: `GatherInv`, `gather_apply_pure` (existing).
- Produces:
  - `gather_batch_size_pure(inv: GatherInv, demand: int, drop_item: str) -> int`
  - `gather_apply_batch_pure(inv: GatherInv, drop_item: str, qty: int) -> GatherInv`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_gather_apply_core.py`:

```python
from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    gather_apply_batch_pure,
    gather_batch_size_pure,
)


def _inv(used=0, cap=100, counts=None, slots_used=0, slots_max=20):
    return GatherInv(used=used, cap=cap, item_count=counts or {},
                     slots_used=slots_used, slots_max=slots_max)


def test_batch_size_is_the_demand_when_it_fits():
    assert gather_batch_size_pure(_inv(), 60, "spruce_wood") == 60


def test_batch_size_is_clamped_to_quantity_headroom():
    assert gather_batch_size_pure(_inv(used=95, cap=100), 60, "spruce_wood") == 5


def test_batch_size_zero_when_a_new_stack_has_no_free_slot():
    inv = _inv(counts={"other": 1}, slots_used=20, slots_max=20)
    assert gather_batch_size_pure(inv, 60, "spruce_wood") == 0


def test_batch_size_nonzero_for_a_held_code_with_no_free_slot():
    """Growing an existing stack needs no new slot."""
    inv = _inv(counts={"spruce_wood": 1}, slots_used=20, slots_max=20)
    assert gather_batch_size_pure(inv, 60, "spruce_wood") == 60


def test_batch_size_zero_for_nonpositive_demand():
    assert gather_batch_size_pure(_inv(), 0, "spruce_wood") == 0
    assert gather_batch_size_pure(_inv(), -3, "spruce_wood") == 0


def test_apply_batch_mints_exactly_qty():
    post = gather_apply_batch_pure(_inv(), "spruce_wood", 10)
    assert post.item_count["spruce_wood"] == 10
    assert post.used == 10


def test_apply_batch_never_mints_past_cap():
    post = gather_apply_batch_pure(_inv(used=98, cap=100), "spruce_wood", 10)
    assert post.used == 100
    assert post.item_count["spruce_wood"] == 2


def test_apply_batch_preserves_other_entries():
    post = gather_apply_batch_pure(_inv(counts={"ash_wood": 4}), "spruce_wood", 3)
    assert post.item_count["ash_wood"] == 4


def test_apply_batch_of_one_matches_the_unbatched_core():
    from artifactsmmo_cli.ai.actions.gather_apply_core import gather_apply_pure
    assert gather_apply_batch_pure(_inv(), "spruce_wood", 1) == gather_apply_pure(
        _inv(), "spruce_wood")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_gather_apply_core.py -v`
Expected: FAIL — `ImportError: cannot import name 'gather_batch_size_pure'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/artifactsmmo_cli/ai/actions/gather_apply_core.py`:

```python
def gather_batch_size_pure(inv: GatherInv, demand: int, drop_item: str) -> int:
    """Units of `drop_item` one batched gather may mint NOW.

    `min(demand, quantity headroom)`, or 0 when the drop needs a NEW stack and
    no slot is free. The slot test matches `gather_is_applicable_pure`'s: a new
    code needs a free slot, growing a held code does not. Bounding by
    `cap - used` is what makes `gather_apply_batch_pure` unable to mint past
    `inventory_max`.
    """
    if demand <= 0:
        return 0
    if drop_item not in inv.item_count and (inv.slots_max - inv.slots_used) < 1:
        return 0
    return max(0, min(demand, inv.cap - inv.used))


def gather_apply_batch_pure(inv: GatherInv, drop_item: str, qty: int) -> GatherInv:
    """Mint `qty` of `drop_item`, BREAKING when full so the planner never mints
    past `cap` — the same fold-with-break shape as `apply_monster_drops_pure`.
    `qty = 1` is `gather_apply_pure` exactly."""
    for _ in range(max(0, qty)):
        if inv.used >= inv.cap:
            break
        inv = gather_apply_pure(inv, drop_item)
    return inv
```

Also extend the module docstring's contract list with a fourth bullet for the batched mint: `used' = min(used + qty, cap)`, `item_count[code]` rises by the same amount, all other entries preserved.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_gather_apply_core.py -v`
Expected: PASS

- [ ] **Step 5: Extend the Lean contract**

In `formal/Formal/GatherApply.lean`, add the batched theorems alongside the
existing three:

```lean
/-- Batched mint is capped: `used' = min (used + qty) cap`. -/
theorem gather_apply_batch_used ... := ...

/-- Batched mint is the unbatched mint iterated: `qty = 1` agrees exactly. -/
theorem gather_apply_batch_one ... := ...

/-- SAFETY: the batched mint never exceeds `cap`, for any `qty`. -/
theorem gather_apply_batch_le_cap ... := ...
```

Proof strategy: induct on `qty`; the break condition makes the step function
monotone and idempotent at `used = cap`, so `Nat.min` closes each arm.

- [ ] **Step 6: Build Lean**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: no errors, no `sorry`

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/gather_apply_core.py \
        formal/Formal/GatherApply.lean tests/test_ai/test_gather_apply_core.py
git commit -m "feat(ai): batched mint + batch sizing in the gather pure core

gather_apply_batch_pure folds the proved single mint with a break at cap, the
same shape apply_monster_drops_pure already uses, so the planner cannot mint
past inventory_max for any quantity. gather_batch_size_pure reuses
gather_is_applicable_pure's slot rule: a new code needs a free slot, growing a
held code does not."
```

---

### Task 5: `GatherAction.quantity`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/gathering.py`
- Test: `tests/test_ai/test_gathering.py`

**Interfaces:**
- Consumes: `gather_batch_size_pure`, `gather_apply_batch_pure` (Task 4).
- Produces: `GatherAction(resource_code=..., quantity: int = 1, ...)`;
  `GatherAction.effective_quantity(state, game_data) -> int`;
  `GatherAction.drop_item(game_data) -> str`;
  `repr` becomes `Gather(spruce_wood×60)` / `Gather(copper_rocks->emerald_stone×3)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_gathering.py` (reuse the module's existing state
and `game_data` fixtures — read the top of the file first to get their names):

```python
def test_default_quantity_is_one_and_repr_shows_it(game_data):
    a = GatherAction(resource_code="spruce_tree", locations=frozenset({(0, 0)}))
    assert a.quantity == 1
    assert repr(a) == "Gather(spruce_tree×1)"


def test_apply_mints_the_batch(state, game_data):
    a = GatherAction(resource_code="spruce_tree", quantity=10,
                     locations=frozenset({(0, 0)}))
    post = a.apply(state, game_data)
    drop = a.drop_item(game_data)
    assert post.inventory[drop] - state.inventory.get(drop, 0) == 10


def test_effective_quantity_clamps_to_headroom(state, game_data):
    full = dataclasses.replace(state, inventory_used=state.inventory_max - 4)
    a = GatherAction(resource_code="spruce_tree", quantity=10,
                     locations=frozenset({(0, 0)}))
    assert a.effective_quantity(full, game_data) == 4


def test_partial_batch_stays_applicable(state, game_data):
    """CraftAction's contract: a batch that does not fully fit degrades, it does
    not vanish. Without this a near-full bag removes the only edge to a real
    deficit."""
    full = dataclasses.replace(state, inventory_used=state.inventory_max - 4)
    a = GatherAction(resource_code="spruce_tree", quantity=10,
                     locations=frozenset({(0, 0)}))
    assert a.is_applicable(full, game_data) is True


def test_cost_scales_with_quantity(state, game_data):
    one = GatherAction(resource_code="spruce_tree", quantity=1,
                       locations=frozenset({(0, 0)}))
    ten = GatherAction(resource_code="spruce_tree", quantity=10,
                       locations=frozenset({(0, 0)}))
    assert ten.cost(state, game_data) > one.cost(state, game_data)


def test_banked_penalty_scales_with_covered_units_only(state, game_data):
    """The docstring has always claimed the penalty applies 'per banked unit's
    worth'; the flat +100 could not express it. 3 banked units against a batch
    of 10 penalizes 3 units, not 10 and not a flat one."""
    a = GatherAction(resource_code="spruce_tree", quantity=10,
                     locations=frozenset({(0, 0)}))
    drop = a.drop_item(game_data)
    banked = dataclasses.replace(state, bank_items={drop: 3})
    unbanked = dataclasses.replace(state, bank_items={})
    delta = a.cost(banked, game_data) - a.cost(unbanked, game_data)
    assert delta == pytest.approx(3 * GatherAction._BANKED_REGATHER_PENALTY)


def test_learned_cost_key_is_quantity_free(state, game_data):
    """Learned costs must not fragment per batch size or the learning signal is
    silently destroyed — every new quantity would be a fresh, empty key."""
    one = GatherAction(resource_code="spruce_tree", quantity=1,
                       locations=frozenset({(0, 0)}))
    sixty = GatherAction(resource_code="spruce_tree", quantity=60,
                         locations=frozenset({(0, 0)}))
    assert one.learning_key() == sixty.learning_key()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_gathering.py -v`
Expected: FAIL — `TypeError: GatherAction.__init__() got an unexpected keyword argument 'quantity'`

- [ ] **Step 3: Write the implementation**

In `src/artifactsmmo_cli/ai/actions/gathering.py`:

Add the field after `resource_code`:

```python
    resource_code: str
    quantity: int = 1
    """Units this edge mints in ONE planner node. A planner abstraction: the
    API gathers one unit per call with a cooldown, so N units are N cycles —
    the player holds the plan cursor until the batch lands (PlanCache
    .step_target), the same expansion idiom LevelSkill uses.

    Sized by the consuming goal from its own demand closure
    (`size_closure_gather`), never by the factory, which has no demand context.
    Default 1 reproduces the pre-batching edge exactly."""
```

Extract the drop-item expression, which is currently repeated four times in
this file, into a method and use it everywhere:

```python
    def drop_item(self, game_data: GameData) -> str:
        """The item this gather actually yields: the targeted secondary drop
        when overridden, else the resource's primary drop, else the resource
        code itself."""
        return (self.drop_item_override
                or game_data.resource_drop_item(self.resource_code)
                or self.resource_code)

    def effective_quantity(self, state: WorldState, game_data: GameData) -> int:
        """`min(self.quantity, inventory headroom in units)` — the largest
        feasible batch NOW. 0 when not even one unit fits. Mirrors
        `CraftAction.effective_quantity`."""
        inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                        item_count=state.inventory,
                        slots_used=state.inventory_slots_used,
                        slots_max=state.inventory_slots_max)
        return gather_batch_size_pure(inv, self.quantity, self.drop_item(game_data))

    def learning_key(self) -> str:
        """Learned-cost key, deliberately QUANTITY-FREE. `repr` carries the
        quantity for display and plan identity, but keying learned costs on it
        would make every batch size a fresh, empty key and silently disable
        `learned_cost_pure` for every batched gather. The learned figure is a
        per-unit cost, scaled by quantity in `cost`."""
        if self.drop_item_override is not None:
            return f"Gather({self.resource_code}->{self.drop_item_override})"
        return f"Gather({self.resource_code})"
```

`is_applicable` — keep the skill gate; the capacity arm gains the batch check:

```python
        return (state.skills.get(skill, 1) >= level
                and gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS, drop_item)
                and self.effective_quantity(state, game_data) >= 1)
```

(apply the same `and self.effective_quantity(...) >= 1` to the no-skill-requirement branch.)

`apply` — replace the single mint with the batch:

```python
        post = gather_apply_batch_pure(inv, drop_item,
                                       self.effective_quantity(state, game_data))
```

`cost` — scale the base and the banked penalty; leave the loadout penalty
per-action (one swap serves the whole batch):

```python
        static = (6.0 + dist) * self.quantity
        banked = (state.bank_items or {}).get(drop_item, 0)
        static += min(banked, self.quantity) * self._BANKED_REGATHER_PENALTY
        ...  # loadout penalty unchanged, added once
        if history is None:
            return learned_cost_pure(static, 0.0, 1.0, has_history=False)
        learned = history.action_cost(self.learning_key(), default=(6.0 + dist),
                                      window=50) * self.quantity
        rate = history.success_rate(self.learning_key(), window=50)
        return learned_cost_pure(static, learned, rate, has_history=True)
```

Update `_BANKED_REGATHER_PENALTY`'s comment: the flat form could not express
"per banked unit's worth" that the comment already claimed; with a quantity it
now does exactly that.

`__repr__`:

```python
    def __repr__(self) -> str:
        if self.drop_item_override is not None:
            return f"Gather({self.resource_code}->{self.drop_item_override}×{self.quantity})"
        return f"Gather({self.resource_code}×{self.quantity})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_gathering.py -v`
Expected: PASS

- [ ] **Step 5: Fix every repr assertion this breaks**

Run: `uv run pytest tests/test_ai/ -q 2>&1 | tail -40`

`Gather(x)` became `Gather(x×1)`, so plan-display and trace assertions across
the suite will fail. Update them — do **not** revert the repr: quantity is part
of plan identity, exactly as it is for `Craft(code×N)` and `Withdraw(code×N)`.

Also check the TUI, which renders plan legs and is outside the ruff gate:

Run: `grep -rn "Gather(" src/artifactsmmo_cli/tui/ tests/test_tui/ | head -20`

- [ ] **Step 6: Type-check and lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/actions/gathering.py && uv run ruff check src/artifactsmmo_cli/ai/actions/gathering.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/gathering.py tests/
git commit -m "feat(ai): GatherAction carries a quantity

Craft, Withdraw, Recycle and NpcBuy all carry one; Gather was the last
acquisition edge minting exactly one unit per node, which made 6 spruce_plank
<- 60 spruce_wood a 60-node chain at depth 60 against max_depth 32 —
unreachable by construction, not slow.

Partial-batch semantics copied from CraftAction: a batch that does not fully
fit degrades to the largest feasible one rather than becoming inapplicable.

The banked-regather penalty becomes min(banked, quantity) * PENALTY, which is
what its comment has claimed since 2026-06-07 and the flat form could not
express. Learned costs key on a quantity-FREE learning_key: keying on repr
would make every batch size a fresh empty key and silently disable
learned_cost_pure for every batched gather."
```

---

### Task 6: `GatherCost.lean` — cost stays sound under batching

A* optimality rests on every edge cost being non-negative
(`Formal/ActionCostNonneg.lean`). Multiplying by a quantity is where that could
break.

**Files:**
- Create: `formal/Formal/GatherCost.lean`
- Modify: `formal/Formal/Manifest.lean`
- Create: `formal/diff/test_gather_cost_diff.py`

**Interfaces:**
- Consumes: `GatherAction.cost` (Task 5).
- Produces: `Formal.GatherCost.gatherCost`; theorems `gather_cost_nonneg`, `gather_cost_monotone`, `gather_cost_one_is_base`.

- [ ] **Step 1: Read a neighbouring cost proof for the house style**

Run: `sed -n '1,80p' formal/Formal/ActionCostNonneg.lean`

- [ ] **Step 2: Write the model and theorems**

Create `formal/Formal/GatherCost.lean`:

```lean
-- @concept: planner, action, cost @property: monotonicity, safety
/-
Cost model for the BATCHED gather edge.

`GatherAction.cost` is `(base + dist) * qty + min(banked, qty) * penalty`
(+ a per-action loadout penalty, which is a constant and plays no part in these
theorems). A* optimality requires every edge cost to be non-negative
(`Formal.ActionCostNonneg`); multiplying by a planner-chosen quantity is where
that could break, so it is proved here rather than assumed.
-/
namespace Formal.GatherCost

def gatherCost (base dist penalty : Rat) (qty banked : Nat) : Rat :=
  (base + dist) * qty + (min banked qty) * penalty

/-- Non-negativity: the obligation `Formal.ActionCostNonneg` discharges for
every action kind, now for any planner-chosen quantity. -/
theorem gather_cost_nonneg (base dist penalty : Rat) (qty banked : Nat)
    (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ penalty) :
    0 ≤ gatherCost base dist penalty qty banked := ...

/-- Monotone in the batch size: a bigger batch is never cheaper, so the planner
cannot manufacture a cheaper plan by inflating a quantity. -/
theorem gather_cost_monotone (base dist penalty : Rat) (q₁ q₂ banked : Nat)
    (h : q₁ ≤ q₂) (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ penalty) :
    gatherCost base dist penalty q₁ banked
      ≤ gatherCost base dist penalty q₂ banked := ...

/-- `qty = 1` is the pre-batching edge cost exactly. -/
theorem gather_cost_one_is_base (base dist penalty : Rat) (banked : Nat)
    (h : 1 ≤ banked) :
    gatherCost base dist penalty 1 banked = (base + dist) + penalty := ...
```

Proof strategy: all three follow from `Rat` ordered-field lemmas plus
`Nat.cast_le` and `min_le_left` / `min_le_right`; no induction needed.

- [ ] **Step 3: Build**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: no errors, no `sorry`

- [ ] **Step 4: Add the differential harness**

Create `formal/diff/test_gather_cost_diff.py` driving Python `GatherAction.cost`
and Lean `gatherCost` over the same `(base, dist, penalty, qty, banked)` grid.
Follow `formal/diff/test_action_cost_nonneg_diff.py`'s structure.

- [ ] **Step 5: Run it**

Run: `uv run pytest formal/diff/test_gather_cost_diff.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add formal/Formal/GatherCost.lean formal/Formal/Manifest.lean \
        formal/diff/test_gather_cost_diff.py
git commit -m "proof(formal): batched gather cost is non-negative and monotone

A* optimality rests on non-negative edge costs (ActionCostNonneg). Multiplying
by a planner-chosen quantity is where that could break, and monotonicity in the
batch size is what stops the planner manufacturing a cheaper plan by inflating
a quantity."
```

---

### Task 7: `size_closure_gather`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/intermediate_batch.py`
- Test: `tests/test_ai/test_intermediate_batch.py`

**Interfaces:**
- Consumes: `GatherAction.drop_item`, `effective_quantity` (Task 5).
- Produces: `size_closure_gather(action: GatherAction, chain: Mapping[str, int], state: WorldState, game_data: GameData) -> GatherAction`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_intermediate_batch.py`:

```python
from artifactsmmo_cli.ai.intermediate_batch import size_closure_gather


def test_sizes_to_the_net_closure_deficit(state, game_data):
    a = GatherAction(resource_code="spruce_tree", locations=frozenset({(0, 0)}))
    drop = a.drop_item(game_data)
    sized = size_closure_gather(a, {drop: 60}, state, game_data)
    assert sized.quantity == 60


def test_holdings_reduce_the_deficit(state, game_data):
    a = GatherAction(resource_code="spruce_tree", locations=frozenset({(0, 0)}))
    drop = a.drop_item(game_data)
    held = dataclasses.replace(state, inventory={drop: 10}, bank_items={drop: 15})
    sized = size_closure_gather(a, {drop: 60}, held, game_data)
    assert sized.quantity == 35


def test_fully_covered_material_sizes_to_zero(state, game_data):
    a = GatherAction(resource_code="spruce_tree", locations=frozenset({(0, 0)}))
    drop = a.drop_item(game_data)
    held = dataclasses.replace(state, bank_items={drop: 60})
    assert size_closure_gather(a, {drop: 60}, held, game_data).quantity == 0


def test_material_absent_from_the_chain_sizes_to_zero(state, game_data):
    a = GatherAction(resource_code="spruce_tree", locations=frozenset({(0, 0)}))
    assert size_closure_gather(a, {}, state, game_data).quantity == 0


def test_returns_the_same_instance_when_quantity_already_matches(state, game_data):
    a = GatherAction(resource_code="spruce_tree", quantity=1,
                     locations=frozenset({(0, 0)}))
    drop = a.drop_item(game_data)
    assert size_closure_gather(a, {drop: 1}, state, game_data) is a
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_intermediate_batch.py -v`
Expected: FAIL — `ImportError: cannot import name 'size_closure_gather'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/artifactsmmo_cli/ai/intermediate_batch.py` (and widen its module
docstring to "Rebatch an intermediate CraftAction or a closure GatherAction to
its inventory-bounded closure demand."):

```python
def size_closure_gather(action: GatherAction, chain: Mapping[str, int],
                        state: WorldState, game_data: GameData) -> GatherAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its DROP ITEM's net closure demand (chain demand minus inventory+bank
    holdings). Unchanged when the sized quantity already matches.

    The twin of `size_intermediate_craft`, and sized by the goal for the same
    reason: the action factory has no demand context, so a factory-set quantity
    could only ever be a guess.

    Keyed on the drop item, not the resource code — a `drop_item_override`
    gather targets a secondary drop, and it is that item the closure demands.
    """
    drop = action.drop_item(game_data)
    held = state.inventory.get(drop, 0) + (state.bank_items or {}).get(drop, 0)
    demand = max(0, chain.get(drop, 0) - held)
    qty = action.effective_quantity(
        state, game_data) if demand else 0
    qty = min(demand, qty) if demand else 0
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)
```

Note: `effective_quantity` reads `action.quantity`, so compute the headroom
bound directly instead of round-tripping through it:

```python
    inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                    item_count=state.inventory,
                    slots_used=state.inventory_slots_used,
                    slots_max=state.inventory_slots_max)
    qty = gather_batch_size_pure(inv, demand, drop)
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)
```

Use the second form; delete the first. Add the `GatherInv` /
`gather_batch_size_pure` / `GatherAction` imports at the top of the module.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_intermediate_batch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/intermediate_batch.py tests/test_ai/test_intermediate_batch.py
git commit -m "feat(ai): size_closure_gather, the gather twin of size_intermediate_craft

Sized by the goal, not the factory, for the same reason crafts are: the factory
has no demand context. Keyed on the DROP item rather than the resource code so
a drop_item_override gather sizes against the secondary drop the closure
actually demands."
```

---

### Task 8: wire sizing into both consuming goals

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py:369-377` (the `GatherAction` arm of the big `elif` in `relevant_actions`)
- Modify: `src/artifactsmmo_cli/ai/goals/progression.py:291-305` (the `GatherAction` arm)
- Test: `tests/test_ai/test_gather_bank_prune.py`

**Interfaces:**
- Consumes: `size_closure_gather` (Task 7).
- Produces: no new symbols. Both `relevant_actions` now emit sized gathers.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_gather_bank_prune.py`:

```python
def test_gather_material_goal_emits_a_sized_gather(state, game_data, actions):
    goal = GatherMaterialsGoal(target_item="spruce_plank",
                               needed={"spruce_plank": 6})
    relevant = goal.relevant_actions(actions, state, game_data)
    gathers = [a for a in relevant if isinstance(a, GatherAction)]
    assert gathers, "expected at least one closure gather"
    assert all(a.quantity > 1 for a in gathers), \
        f"gathers not batched: {[repr(a) for a in gathers]}"


def test_upgrade_equipment_goal_emits_a_sized_gather(state, game_data, actions):
    goal = UpgradeEquipmentGoal(committed_target=("greater_wooden_staff",
                                                  "weapon_slot"))
    relevant = goal.relevant_actions(actions, state, game_data)
    gathers = [a for a in relevant if isinstance(a, GatherAction)]
    assert all(a.quantity >= 1 for a in gathers)
    assert any(a.quantity > 1 for a in gathers), \
        "the staff chain needs 60 spruce_wood; nothing was batched"
```

Read the top of `tests/test_ai/test_gather_bank_prune.py` first for the real
fixture names and goal constructor signatures, and match them.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_gather_bank_prune.py -v`
Expected: FAIL — every gather has `quantity == 1`

- [ ] **Step 3: Wire `goals/gathering.py`**

In the big `elif` chain, the `GatherAction` disjunct currently ends with
`result.append(action)` shared with several other kinds. Split the gather out so
it can be sized, leaving the other disjuncts untouched:

```python
            if isinstance(action, CraftAction) and action.code in craftable_mats:
                result.append(size_intermediate_craft(action, chain, state, game_data))
            elif (isinstance(action, GatherAction) and gather_serves_closure(
                    action.resource_code, action.drop_item_override,
                    game_data.resource_drops, chain)
                    and (skill_open(action.resource_code, state, game_data)
                         or action.resource_code in openable_locked_gathers)):
                sized = size_closure_gather(action, chain, state, game_data)
                if sized.quantity >= 1:
                    result.append(sized)
            elif (
                (isinstance(action, RecycleAction) and action.code in recycle_sources)
                or "recovery" in action.tags
                ...
            ):
                result.append(action)
```

The `sized.quantity >= 1` guard replaces nothing — a zero-deficit material was
already dropped by the `covered` prune above, and this is the same fact
recomputed from the chain. Keeping both is correct: `covered` is recipe-wise,
the deficit is chain-wise.

- [ ] **Step 4: Wire `goals/progression.py`**

```python
            elif isinstance(action, GatherAction):
                if not gather_serves_closure(action.resource_code,
                                             action.drop_item_override,
                                             game_data.resource_drops, chain):
                    continue
                drop = action.drop_item(game_data)
                if drop in covered:
                    continue
                sized = size_closure_gather(action, chain, state, game_data)
                if sized.quantity >= 1:
                    result.append(sized)
```

Note the `drop is not None` check is gone: `drop_item` falls back to the
resource code, so it is never `None`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_gather_bank_prune.py -v`
Expected: PASS

- [ ] **Step 6: Verify the yield-aware narrowing still works**

The `GatherSelection` narrowing after the loop dedupes by `id(a)` over `result`.
`dataclasses.replace` produces new instances, so the ids must be the sized ones.

Run: `uv run pytest tests/test_ai/test_gathering_yield_selection.py tests/test_ai/test_gather_selection.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py \
        src/artifactsmmo_cli/ai/goals/progression.py \
        tests/test_ai/test_gather_bank_prune.py
git commit -m "feat(ai): both goals emit gathers sized to their closure deficit

One edge per material at exactly the outstanding deficit, so the branching
factor is unchanged and only the depth collapses. GatherSelection's id()-keyed
narrowing runs on the sized instances."
```

---

### Task 9: plan cursor holds through a batch

**Files:**
- Modify: `src/artifactsmmo_cli/ai/plan_cache.py`
- Modify: `src/artifactsmmo_cli/ai/player.py:1213-1218`
- Test: `tests/test_ai/test_plan_cache.py`

**Interfaces:**
- Consumes: `GatherAction.drop_item`, `.quantity` (Task 5).
- Produces: `PlanCache.step_target: int | None`; `PlanCache.batch_satisfied(inventory: Mapping[str, int]) -> bool`; `PlanCache.arm_step(state_inventory, game_data)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_plan_cache.py`:

```python
def test_cursor_holds_until_the_batch_target_is_reached(game_data):
    gather = GatherAction(resource_code="spruce_tree", quantity=3,
                          locations=frozenset({(0, 0)}))
    cache = PlanCache(selected_goal=object(), plan=[gather, object()],
                      crafting_target=None, latch_active=False,
                      goal_repr="G")
    drop = gather.drop_item(game_data)
    cache.arm_step({drop: 5}, game_data)
    assert cache.step_target == 8
    assert cache.batch_satisfied({drop: 6}, game_data) is False
    assert cache.batch_satisfied({drop: 8}, game_data) is True


def test_a_lucky_multi_unit_drop_satisfies_early(game_data):
    """The target is a state predicate, not a counter, so overshoot advances
    instead of hanging."""
    gather = GatherAction(resource_code="spruce_tree", quantity=3,
                          locations=frozenset({(0, 0)}))
    cache = PlanCache(selected_goal=object(), plan=[gather],
                      crafting_target=None, latch_active=False, goal_repr="G")
    drop = gather.drop_item(game_data)
    cache.arm_step({drop: 0}, game_data)
    assert cache.batch_satisfied({drop: 12}, game_data) is True


def test_unbatched_steps_are_always_satisfied(game_data):
    cache = PlanCache(selected_goal=object(), plan=[object()],
                      crafting_target=None, latch_active=False, goal_repr="G")
    cache.arm_step({}, game_data)
    assert cache.step_target is None
    assert cache.batch_satisfied({}, game_data) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_plan_cache.py -v`
Expected: FAIL — `AttributeError: 'PlanCache' object has no attribute 'arm_step'`

- [ ] **Step 3: Implement in `plan_cache.py`**

```python
    step_target: int | None = None
    """Holding of the current step's drop item at which the cursor may advance.

    A batched gather is a planner abstraction: the API gathers one unit per
    call with a cooldown, so N units are N cycles (the LevelSkill
    planner-abstraction / player-expansion idiom). The advance condition is a
    STATE PREDICATE, not an execution counter, and that choice is load-bearing:
    a lucky multi-unit drop, another character draining the shared bank, or a
    bag that fills mid-batch all resolve without bookkeeping, and no mutable
    progress lives on the shared Action instance.

    None for every non-batched step, which is then trivially satisfied.
    """

    def arm_step(self, inventory: Mapping[str, int], game_data: GameData) -> None:
        """Snapshot the current step's completion target. Call on every advance
        and on plan install."""
        action = self.current()
        qty = getattr(action, "quantity", 1)
        if not isinstance(action, GatherAction) or qty <= 1:
            self.step_target = None
            return
        drop = action.drop_item(game_data)
        self.step_target = inventory.get(drop, 0) + qty

    def batch_satisfied(self, inventory: Mapping[str, int],
                        game_data: GameData) -> bool:
        """True when the armed step's target holding has been reached."""
        if self.step_target is None:
            return True
        action = self.current()
        if not isinstance(action, GatherAction):
            return True
        return inventory.get(action.drop_item(game_data), 0) >= self.step_target
```

- [ ] **Step 4: Gate the advance in `player.py`**

Replace lines 1213–1218:

```python
                if outcome == "ok" and self._plan_cache is not None:
                    if self._plan_cache.batch_satisfied(new_state.inventory,
                                                        self.game_data):
                        self._plan_cache.advance()
                        self._plan_cache.arm_step(new_state.inventory,
                                                  self.game_data)
                        if self.history is not None:
                            self.history.update_commitment_cursor(
                                self._plan_cache.cursor)
                    self._plan_cache.cycles_since_replan += 1
```

`cycles_since_replan` increments either way, so `should_replan`'s
`replan_interval` staleness bound still terminates a batch that cannot make
progress. Call `arm_step` at every site that installs a fresh plan into
`self._plan_cache` — find them:

Run: `grep -n "_plan_cache = PlanCache" src/artifactsmmo_cli/ai/player.py`

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_plan_cache.py tests/test_ai/test_should_replan.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/plan_cache.py src/artifactsmmo_cli/ai/player.py \
        tests/test_ai/test_plan_cache.py
git commit -m "feat(ai): plan cursor holds through a batched gather

A batched gather is a planner abstraction — the API mints one unit per call, so
N units are N cycles, the same expansion LevelSkill uses. Advance is a state
predicate (holding >= plan-time target) rather than an execution counter, so a
lucky multi-unit drop, a competing character draining the bank, or a bag that
fills mid-batch all resolve without bookkeeping. cycles_since_replan still
increments while held, so should_replan's staleness bound terminates a batch
that cannot progress."
```

---

### Task 10: live regression — the staff must plan

The one test that proves the bug is dead. Written from R2D2's real traced state.

**Files:**
- Create: `tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py`

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces: nothing.

- [ ] **Step 1: Read the scenario harness conventions**

Run: `ls tests/test_ai/scenarios/ && sed -n '1,50p' "$(ls tests/test_ai/scenarios/*.py | head -1)"`

- [ ] **Step 2: Write the failing test**

```python
"""Live regression: play-trace-R2D2-20260812-003250.jsonl.

UpgradeEquipment(greater_wooden_staff->weapon_slot) was the rank-1 objective on
every one of 955 cycles and produced a plan on ZERO of them — 3873 nodes, depth
8, timed_out, plan_len 0 — while the shared bank held 16 spruce_plank and 98
blue_slimeball against a recipe needing 6 and 2. The character then fell through
to GrindCharacterXP every cycle, which is why the fleet appeared to be choosing
to grind XP.
"""


def test_staff_plans_from_r2d2s_traced_state(game_data):
    state = _r2d2_traced_state()          # level 16, weaponcrafting 9,
                                          # woodcutting 13, empty inventory,
                                          # bank {spruce_plank: 16,
                                          #       blue_slimeball: 98}
    goal = UpgradeEquipmentGoal(
        committed_target=("greater_wooden_staff", "weapon_slot"))
    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _build_actions(game_data), game_data,
                        budget_seconds=15.0)
    assert plan, (
        "no plan; live trace: 3873 nodes, depth 8, timed_out, plan_len 0")
    assert not planner.last_stats.timed_out
    assert planner.last_stats.max_depth_reached <= goal.max_depth


def test_staff_plan_uses_the_banked_materials():
    """The materials were never missing. A plan that re-gathers 60 spruce_wood
    with 16 planks in the bank is the banked-regather bug, not a fix."""
    ...
    assert any(isinstance(a, WithdrawItemAction) and a.code == "spruce_plank"
               for a in plan)


def test_staff_goal_is_admitted_by_is_plannable():
    """is_plannable scored the chain at 65 against max_depth 32 and refused
    admission before A* ever ran."""
    goal = UpgradeEquipmentGoal(
        committed_target=("greater_wooden_staff", "weapon_slot"))
    assert goal.is_plannable(_r2d2_traced_state(), game_data) is True
```

Build `_r2d2_traced_state()` from the trace values above using the scenario
harness's existing state builder. Do **not** invent a simplified recipe — use
the real catalog, or the test proves nothing about the live failure.

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py -v`
Expected: PASS. If it fails, the earlier tasks are incomplete — do not weaken this test.

- [ ] **Step 4: Prove the test is not vacuous**

Temporarily revert `min_plan_length` to `ceil_gathers(min_gathers(...))` and
confirm the test FAILS. Restore it. Never `git checkout` the file to restore —
copy it aside first and copy it back, or the uncommitted work in it is lost.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py
git commit -m "test(ai): R2D2's traced staff state must produce a plan

0 of 955 cycles produced one. Materials were never missing — the bank held 16
spruce_plank and 98 blue_slimeball against a recipe needing 6 and 2."
```

---

### Task 11: one planning budget

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:1489-1562`, `:991-1007`
- Modify: `src/artifactsmmo_cli/ai/planner.py:14-21`
- Modify/Delete: `tests/test_ai/test_strategy_driver_tiered.py`
- Test: `tests/test_ai/test_planner_budget.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (but must land AFTER them — see below).
- Produces: `StrategyDriver._record_attempt(goal, plan, timed_out, state, guard_reprs) -> list[Action]` (the `mark_on_timeout` keyword is gone).

**This task must not land before Tasks 1–10.** A single 15 s budget against
unbatched gathers is strictly worse than the current two-pass behaviour.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_planner_budget.py`:

```python
def test_single_budget_is_fifteen_seconds():
    from artifactsmmo_cli.ai import planner
    assert planner._SEARCH_BUDGET_SECONDS == 15.0


def test_cheap_budget_is_gone():
    from artifactsmmo_cli.ai import strategy_driver
    assert not hasattr(strategy_driver, "CHEAP_BUDGET_SECONDS")


def test_a_timed_out_goal_is_marked_doomed_immediately():
    """try_plan_cheap passed mark_on_timeout=False and the full-budget pass that
    would have marked it was unreachable, so the staff search re-exploded on 955
    consecutive cycles."""
    driver = _driver()
    driver._record_attempt(_goal("Slow"), [], timed_out=True,
                           state=_state(), guard_reprs=set())
    assert driver._memo.is_doomed("Slow", _state(), cycle=0) is True


def test_guards_still_bypass_the_memo():
    driver = _driver()
    driver._record_attempt(_goal("Guard"), [], timed_out=True,
                           state=_state(), guard_reprs={"Guard"})
    assert driver._memo.is_doomed("Guard", _state(), cycle=0) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_planner_budget.py -v`
Expected: FAIL — budget is 300.0, `CHEAP_BUDGET_SECONDS` exists

- [ ] **Step 3: Collapse the two-pass walk**

In `strategy_driver.py`, delete `CHEAP_BUDGET_SECONDS` (and its
`ARTIFACTSMMO_CHEAP_BUDGET_SECONDS` env override), `_budget_for`,
`try_plan_cheap`, `try_plan_full`, and the second and third `select_pure` calls'
use of `try_plan_full`. One `try_plan` remains:

```python
        def try_plan(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            plan = self._plans(goal, state, game_data, actions, ctx, None)
            return self._record_attempt(goal, plan, self._last_timed_out,
                                        state, memo_bypass)
```

`_budget_for` disappears because there is now one budget: `None` means
`_SEARCH_BUDGET_SECONDS`. Guards keep `memo_bypass`; they no longer need a
distinct budget.

The worth-gate-bypass `select_pure` call keeps its `try_plan`.

Update `_record_attempt`:

```python
    def _record_attempt(self, goal: Goal, plan: list[Action], timed_out: bool,
                        state: WorldState, guard_reprs: set[str]) -> list[Action]:
        """Update the doomed-memo from one planning attempt and return `plan`.

        - A found plan (or a guard goal) CLEARS any prior doomed mark.
        - Any no-plan result MARKS the goal doomed, TIMEOUT INCLUDED.

        The timeout carve-out is deleted. It existed to keep a cheap-budget
        timeout available for a full-budget escalation that, in a fleet with an
        always-plannable fallback grind, was never reached: `select_pure` takes
        the first candidate that plans, `GrindCharacterXP` plans in 2 nodes, so
        `chosen` was never None and the escalation pass never ran. The carve-out
        therefore only ever meant "never mark", and the same 3873-node search
        re-ran on 955 consecutive cycles.
        """
        r = repr(goal)
        if r in guard_reprs or plan:
            self._memo.clear(r)
        else:
            self._memo.mark(r, state, self._cycle)
        return plan
```

Also delete `_dedupe_goals_tried`'s two-pass rationale and the call itself if
nothing probes a goal twice any more — verify by reading `select`'s body; if the
worth-gate bypass can still re-probe, keep the dedupe and correct its docstring.

- [ ] **Step 4: Retune the budget in `planner.py`**

```python
_SEARCH_BUDGET_SECONDS = 15.0
"""A* wall-clock budget — ONE budget for every goal.

Was 300 s behind a 10 s "cheap" first pass. That two-pass scheme is deleted: its
escalation ran only when NOTHING planned, and a fallback combat grind always
plans, so the escalation was unreachable and the cheap timeout was the real
budget for every objective.

15 s is generous for a healthy search now that gather edges carry a quantity —
the searches that were spending 10 s to reach 3873 nodes and no plan were
enumerating a 60-node singleton gather chain that no longer exists. A goal that
still cannot be planned costs 15 s once per DoomedMemo re-probe window, and
emits `objective_unplannable` when it is the rank-1 candidate.
"""
```

- [ ] **Step 5: Rewrite the tiered-budget tests**

`tests/test_ai/test_strategy_driver_tiered.py` tests the deleted scheme. Read it
and, for each test, either delete it (it asserts two-pass behaviour) or rewrite
it against the single walk. Do not leave it asserting a scheme that no longer
exists.

Run: `uv run pytest tests/test_ai/test_strategy_driver_tiered.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_doomed_memo.py -v`

- [ ] **Step 6: Check the arbiter's Lean model still matches**

`formal/Formal/ArbiterSelect.lean` models `select_pure`. The walk's shape is
unchanged (first candidate that plans wins); only the budget and the memo
marking changed, neither of which `select_pure` sees.

Run: `cd formal && lake build 2>&1 | tail -5 && cd .. && uv run pytest formal/diff/test_arbiter_select_diff.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/planner.py tests/
git commit -m "fix(ai): one 15s planning budget; a timeout marks the goal doomed

The cheap/full two-pass escalated only 'if chosen is None'. select_pure takes
the first candidate that plans and GrindCharacterXP plans in 2 nodes, so chosen
was never None and the full-budget pass was unreachable in practice — the 10s
cheap budget was the real budget for every objective. try_plan_cheap also passed
mark_on_timeout=False, so DoomedMemo never recorded the failure: R2D2 re-ran two
exploding searches on 955 consecutive cycles, about 5.3 CPU-hours.

One budget, and any no-plan marks the goal doomed."
```

---

### Task 12: an abandoned rank-1 objective is loud

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`select`)
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (trace assembly, ~line 1092 and ~1254)
- Test: `tests/test_ai/test_strategy_driver.py`

**Interfaces:**
- Consumes: `StrategyDriver.goals_tried` (existing).
- Produces: `StrategyDriver.objective_unplannable: dict[str, object] | None`; `CycleSnapshot.objective_unplannable: ObjectiveUnplannable | None`; trace key `"objective_unplannable"` inside the planner stats block.

- [ ] **Step 1: Write the failing test**

```python
def test_rank_one_failure_is_recorded_before_the_fallthrough():
    """31 hours of traces recorded nothing when the rank-1 objective was
    abandoned; the run read as 'the bot chose to grind XP'."""
    driver = _driver_with(candidates=[_unplannable("Objective"),
                                      _plannable("Grind")])
    goal, plan, _ = driver.select(...)
    assert repr(goal) == "Grind"          # fall-through is intended
    assert driver.objective_unplannable is not None
    assert driver.objective_unplannable["goal"] == "Objective"
    assert driver.objective_unplannable["timed_out"] is True


def test_no_event_when_the_top_candidate_plans():
    driver = _driver_with(candidates=[_plannable("Objective")])
    driver.select(...)
    assert driver.objective_unplannable is None


def test_no_event_when_the_top_candidate_is_satisfied_or_suppressed():
    """A satisfied or suppressed candidate was never attempted, so it was not
    abandoned."""
    driver = _driver_with(candidates=[_satisfied("Done"), _plannable("Grind")])
    driver.select(...)
    assert driver.objective_unplannable is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -v`
Expected: FAIL — `AttributeError: 'StrategyDriver' object has no attribute 'objective_unplannable'`

- [ ] **Step 3: Record it in `select`**

Reset `self.objective_unplannable = None` beside `self.goals_tried = []`. After
the walk, derive it from `goals_tried` rather than threading a flag through
`select_pure` (which stays pure):

```python
        # The rank-1 objective is the FIRST candidate actually attempted — a
        # satisfied or suppressed candidate was never tried, so it was not
        # abandoned. `goals_tried` is append-ordered by the walk, so its first
        # entry is exactly that candidate.
        first = self.goals_tried[0] if self.goals_tried else None
        if (first is not None and not first["plan_len"]
                and chosen is not None and repr(chosen) != first["goal"]):
            self.objective_unplannable = dict(first)
```

- [ ] **Step 4: Carry it on the snapshot**

In `cycle_snapshot.py`:

```python
class ObjectiveUnplannable(BaseModel):
    """The rank-1 objective the arbiter attempted and abandoned this cycle.

    Present only when a LOWER-ranked candidate was executed instead. The
    fall-through is intended; its silence was not — live traces 2026-08-12 show
    UpgradeEquipment(greater_wooden_staff) abandoned on 955 consecutive cycles
    with nothing recorded, so 31 hours of runtime read as a deliberate choice to
    grind XP."""

    goal: str
    nodes: int = 0
    depth: int = 0
    timed_out: bool = False
```

Add `objective_unplannable: ObjectiveUnplannable | None = None` to `CycleSnapshot`.

- [ ] **Step 5: Emit it into the trace**

At both planner-stats assembly sites in `player.py` (the no-plan block ~1092 and
the normal block ~1254), add:

```python
                    "objective_unplannable": self._arbiter.objective_unplannable,
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py tests/test_ai/test_cycle_snapshot.py -v`
Expected: PASS

- [ ] **Step 7: Confirm it appears in a real trace**

Run: `uv run artifactsmmo plan R2D2 2>&1 | tail -30`

Check `pgrep -af artifactsmmo` first — if the bot is running, stop it or accept
that this call consumes shared request budget.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py \
        src/artifactsmmo_cli/ai/cycle_snapshot.py \
        src/artifactsmmo_cli/ai/player.py tests/
git commit -m "feat(ai): trace the rank-1 objective when the arbiter abandons it

The fall-through to a lower-ranked goal is intended; its silence was not.
Nothing in 31 hours of traces recorded that UpgradeEquipment(greater_wooden_staff)
had been abandoned on 955 consecutive cycles, so the run read as a deliberate
choice to grind XP. Derived from goals_tried so select_pure stays pure."
```

---

### Task 13: mutation anchors, full gate, runtime activation

**Files:**
- Modify: mutation anchor config (find it: `grep -rn "anchor" formal/diff/mutation_anchor.py | head`)
- Modify: `docs/superpowers/specs/2026-08-13-planner-batching-and-macro-edges-design.md` (residuals)

**Interfaces:**
- Consumes: everything.
- Produces: a green gate and a runtime-verified change.

- [ ] **Step 1: Add mutation anchors for the new pure cores**

Anchor `min_gather_steps`, `gather_batch_size_pure`, `gather_apply_batch_pure`,
and `size_closure_gather`. Each anchor must resolve to exactly ONE site.

Run: `uv run python formal/diff/mutate.py --check-anchors`
Expected: every anchor resolves uniquely

- [ ] **Step 2: Run mutation testing on the new cores**

Run: `uv run python formal/diff/mutate.py --module min_gather_steps --module gather_apply_core 2>&1 | tail -20`
Expected: 0 survivors. A survivor means a test asserts nothing — fix the test,
never the anchor.

- [ ] **Step 3: Stop the bot, then run the full gate**

```bash
pgrep -af artifactsmmo   # must be empty before proceeding
bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=${PIPESTATUS[0]}"
tail -40 /tmp/gate.log
```
Expected: `rc=0`, 0 errors, 0 warnings, 0 skipped, 100 % coverage.
Never pipe the gate into `tail` directly — the pipeline reports the tail's exit code.

- [ ] **Step 4: Verify runtime activation, not just green tests**

Green tests have shipped inert changes in this repo before. Run the live planner
and confirm the batched edge actually fires:

```bash
uv run artifactsmmo plan R2D2 2>&1 | tee /tmp/plan-r2d2.txt
grep -E "Gather\([a-z_]+×[0-9]+\)|Withdraw\(spruce_plank" /tmp/plan-r2d2.txt
```
Expected: a plan for `greater_wooden_staff` containing a batched leg. A plan
with only `×1` gathers means sizing did not reach the emitted actions.

- [ ] **Step 5: Record the residuals honestly**

Append to the spec's Residuals section anything discovered during
implementation — in particular, whether `gather_step_target`'s depth-descent
(which still consumes per-unit `min_gathers`) now fires less often or has become
dead, and whether any `acquisition_actions` baseline moved.

- [ ] **Step 6: Commit and merge**

```bash
git add -A
git commit -m "chore(formal): anchors + gate green for gather batching

Runtime-verified: live plan R2D2 emits a batched staff plan."
git push origin HEAD:main   # user's workflow: merge to main directly, no PR
```

Confirm the gate was green BEFORE pushing.

---

## Self-Review

**Spec coverage.** I1 → Tasks 1, 3, 4, 5, 7, 8, 9. I3 → Tasks 11, 12. Formal
scope → Tasks 2, 6, and the `GatherApply.lean` amendment in Task 4. Live
regression → Task 10. Gate + runtime activation → Task 13. I2 is explicitly out
of scope for this plan, as stated in Global Constraints.

**One spec item has no task and is intentional:** `FightAction` batching is a
declared non-goal in the spec and remains a residual.

**Type consistency.** `min_gather_steps(item, qty, recipes, owned) -> int` is
defined in Task 1 and consumed with that exact signature in Tasks 2 and 3.
`GatherAction.drop_item(game_data)` is introduced in Task 5 and used in Tasks 7,
8 and 9. `gather_batch_size_pure(inv, demand, drop_item)` is defined in Task 4
and used in Tasks 5 and 7. `_record_attempt` loses `mark_on_timeout` in Task 11
and no later task passes it.

**Known gap the executor must close, not paper over:** Tasks 5, 7, 8, 9 and 10
reference fixture names (`state`, `game_data`, `actions`) and goal constructor
signatures from existing test modules. Each of those steps begins by reading the
target file for the real names. If a fixture does not exist, build it — do not
weaken the assertion to fit what is available.
