# Plannability Admission Soundness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Lean proof TACTICS are interactive — use the `lean4:prove` / `lean4:proof-repair` / `lean4:sorry-filler-deep` skills; this plan gives theorem statements, model definitions, and proof strategy, not tactic scripts.

**Goal:** Make `UpgradeEquipmentGoal.is_plannable` reject a from-scratch gear chain whose true plan exceeds `max_depth` (it currently over-admits feather_coat → empty plan → slime-leveling), and FORMALLY PROVE the admission estimate is a sound lower bound on plan length — discharging the previously-assumed `hsat_lb` hypothesis in `PlannerDepthBound.lean`.

**Architecture:** Production: a new `min_plan_length` = `ceil_gathers(min_gathers) + min_crafts + equip` used by `is_plannable`. Formal: a minimal plan-action model (gather/craft/equip), prove `min_plan_length ≤ |P|` for every satisfying plan `P`, and discharge `hsat_lb` so `min_plan_length > max_depth ⟹ no plan` holds with no assumed hypothesis. Differential + mutation bind production to the proved core.

**Tech Stack:** Python 3.13, Lean 4 + Mathlib (`formal/`), pytest + Hypothesis, uv, `formal/gate.sh`.

## Global Constraints

- ALWAYS prefix Python with `~/.local/bin/uv` (not on PATH): `~/.local/bin/uv run pytest`, `… mypy src`, `… ruff check src/artifactsmmo_cli/ai/`. Lean: `cd formal && lake build`.
- Imports at top; no inline imports; no `if TYPE_CHECKING`; never catch `Exception`; one behavioral class/file.
- Python success each task: pytest + mypy + ruff green, 100% coverage, no NEW ruff findings vs base.
- Formal success each task touching `formal/`: `cd formal && lake build` clean (0 sorry, 0 errors); then the FULL differential `~/.local/bin/uv run pytest formal/diff/ --no-cov -q -n auto` green (pre-commit's fast suite EXCLUDES formal/diff/ — run it explicitly).
- NEVER run `formal/gate.sh` / `mutate.py` concurrently with anything importing src or another formal run (serialize, foreground, alone). `git diff src formal/sim` after each formal run.
- HONESTY (non-negotiable, [[feedback_proofs_tell_false_stories]]): the final no-plan theorem must have NO assumed `hsat_lb`/`planLen ≥ lb` hypothesis. Every "not proven" boundary (A* completeness, movement, inventory) is named in a theorem docstring. No theorem/docstring may claim full planner completeness.
- `gate.sh` ALL GATE PARTS PASSED at the end.

## File structure

| File | Responsibility | Tasks |
|------|----------------|-------|
| `src/artifactsmmo_cli/ai/min_crafts.py` (NEW) | `min_crafts` lower bound on craft actions | 1 |
| `src/artifactsmmo_cli/ai/min_plan_length.py` (NEW) | `min_plan_length` = ceil_gathers(mints)+crafts+equip | 1 |
| `src/artifactsmmo_cli/ai/goals/progression.py` | `is_plannable` rewire | 2 |
| `formal/Formal/PlanModel.lean` (NEW) | Action/Plan/produces/SatisfiesEquip + minPlanLength + lower-bound proof | 4,5,6 |
| `formal/Formal/PlannerDepthBound.lean` | discharge `hsat_lb`; retire assumed copper_boots theorem | 7 |
| `formal/Formal/Extracted/MinCrafts.lean`, `MinPlanLength.lean` (NEW) | extracted cores | 8 |
| `scripts/extract_lean.py` registration | register the new extractions | 8 |
| `formal/diff/test_min_plan_length_diff.py` (NEW) | production↔oracle differential | 8 |
| `tests/test_ai/test_min_crafts.py`, `test_min_plan_length.py` (NEW), `test_progression.py`, `test_strategy_driver.py` | unit/behavior tests | 1,2,3 |

---

### Task 1: `min_crafts` + `min_plan_length` production cores

**Files:**
- Create: `src/artifactsmmo_cli/ai/min_crafts.py`, `src/artifactsmmo_cli/ai/min_plan_length.py`
- Test: `tests/test_ai/test_min_crafts.py`, `tests/test_ai/test_min_plan_length.py`

**Interfaces:**
- Produces: `min_crafts(item: str, qty: int, recipes: Mapping[str, dict[str,int]], owned: dict[str,int]) -> int`
- Produces: `min_plan_length(item: str, qty: int, recipes: Mapping[str, dict[str,int]], owned: dict[str,int], max_gather_yield: int, *, equip: bool) -> int`

- [ ] **Step 1: Write the failing tests for `min_crafts`**

Create `tests/test_ai/test_min_crafts.py`:

```python
"""min_crafts: lower bound on CRAFT actions to obtain qty of item, holdings-credited."""

from artifactsmmo_cli.ai.min_crafts import min_crafts

R = {"feather_coat": {"feather": 5, "ash_plank": 2}, "ash_plank": {"ash_wood": 10}}


def test_raw_leaf_zero_crafts():
    assert min_crafts("ash_wood", 5, R, {}) == 0
    assert min_crafts("feather", 5, R, {}) == 0  # monster drop, no recipe


def test_one_level_craft():
    assert min_crafts("ash_plank", 1, R, {}) == 1          # craft the plank
    assert min_crafts("ash_plank", 2, R, {}) == 1          # 1 craft action (batched lower bound)


def test_feather_coat_counts_planks_and_coat():
    # craft ash_plank (1) + craft feather_coat (1) = 2 craftable nodes to produce
    assert min_crafts("feather_coat", 1, R, {}) == 2


def test_held_craftable_credited():
    # 2 ash_plank already held -> only the coat craft remains
    assert min_crafts("feather_coat", 1, R, {"ash_plank": 2}) == 1
    # feather_coat itself held -> 0 crafts
    assert min_crafts("feather_coat", 1, R, {"feather_coat": 1}) == 0
```

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: min_crafts`.

Run: `~/.local/bin/uv run pytest tests/test_ai/test_min_crafts.py -v --no-cov`

- [ ] **Step 3: Implement `min_crafts`**

Create `src/artifactsmmo_cli/ai/min_crafts.py` (mirrors `min_gathers._min_gathers` fuel-bounded greedy-consume, but counts ONE craft per craftable node that must be produced — a valid lower bound regardless of craft batching):

```python
"""Lower bound on CRAFT actions to obtain `qty` of `item` given `owned`.

One craft per craftable closure node that must be produced (not covered by held
copies). A raw leaf (no recipe) contributes 0 — it is gathered, not crafted.
Counting one craft per produced node is a sound LOWER bound on craft actions
irrespective of per-action craft batching. Mirrors min_gathers' fuel-bounded
greedy-consume so it extracts to Lean cleanly."""

from collections.abc import Mapping


def min_crafts(item: str, qty: int, recipes: "Mapping[str, dict[str, int]]",
               owned: dict[str, int]) -> int:
    return _min_crafts(len(recipes) + 1, item, qty, recipes, (0, dict(owned)))[0]


def _min_crafts(fuel: int, item: str, qty: int,
                recipes: "Mapping[str, dict[str, int]]",
                state: tuple[int, dict[str, int]]) -> tuple[int, dict[str, int]]:
    if fuel <= 0:
        return state
    total, owned = state[0], state[1]
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return (total, owned)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        return (total, owned)  # raw leaf: gathered, not crafted
    # This craftable node must be produced: +1 craft, then recurse into inputs.
    state = (total + 1, owned)
    for material, per_unit in recipe.items():
        state = _min_crafts(fuel - 1, material, per_unit * remaining, recipes, state)
    return state
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Failing tests for `min_plan_length`**

Create `tests/test_ai/test_min_plan_length.py`:

```python
"""min_plan_length: ceil_gathers(mints) + crafts + equip — the is_plannable estimate."""

from artifactsmmo_cli.ai.min_plan_length import min_plan_length

R = {"feather_coat": {"feather": 5, "ash_plank": 2}, "ash_plank": {"ash_wood": 10}}


def test_feather_coat_from_scratch_exceeds_15():
    # mints: 5 feathers + 20 ash_wood... but owned ash_wood=10 -> 5 + 10 = 15 mints
    # (max_gather_yield=1 -> ceil_gathers=15); crafts: ash_plank + coat = 2; equip 1.
    n = min_plan_length("feather_coat", 1, R, {"ash_wood": 10}, 1, equip=True)
    assert n == 18          # 15 + 2 + 1
    assert n > 15           # > UpgradeEquipmentGoal.max_depth -> correctly rejected


def test_short_chain_when_materials_in_hand():
    # planks in hand, only 5 feathers left: mints 5, crafts 1 (coat), equip 1 = 7
    n = min_plan_length("feather_coat", 1, R, {"ash_plank": 2}, 1, equip=True)
    assert n == 7 and n <= 15


def test_equip_false_drops_one():
    a = min_plan_length("ash_plank", 1, R, {}, 1, equip=False)   # 10 mints + 1 craft
    assert a == 11
```

- [ ] **Step 6: Run, verify fail; implement `min_plan_length`**

Create `src/artifactsmmo_cli/ai/min_plan_length.py`:

```python
"""Lower bound on PLAN length to obtain (and optionally equip) `item`:
`ceil_gathers(min_gathers) + min_crafts + (1 if equip)`. The mint term is divided
by max_gather_yield (a gather yields up to that many units); craft and equip are
one action each. Sound lower bound on plan length over the gather/craft/equip
action model (proved: Formal.PlanModel.min_plan_length_le_plan)."""

from collections.abc import Mapping

from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers


def min_plan_length(item: str, qty: int,
                    recipes: "Mapping[str, dict[str, int]]",
                    owned: dict[str, int], max_gather_yield: int,
                    *, equip: bool) -> int:
    mints = ceil_gathers(min_gathers(item, qty, recipes, owned), max_gather_yield)
    crafts = min_crafts(item, qty, recipes, owned)
    return mints + crafts + (1 if equip else 0)
```

- [ ] **Step 7: Run pass; gate; commit**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_min_crafts.py tests/test_ai/test_min_plan_length.py --no-cov && ~/.local/bin/uv run mypy src && ~/.local/bin/uv run ruff check src/artifactsmmo_cli/ai/min_crafts.py src/artifactsmmo_cli/ai/min_plan_length.py`

```bash
git add src/artifactsmmo_cli/ai/min_crafts.py src/artifactsmmo_cli/ai/min_plan_length.py tests/test_ai/test_min_crafts.py tests/test_ai/test_min_plan_length.py
git commit -m "feat(ai): min_crafts + min_plan_length lower-bound cores"
```

---

### Task 2: Rewire `is_plannable` to `min_plan_length`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/progression.py:139-142`
- Test: `tests/test_ai/test_progression.py` (or wherever UpgradeEquipmentGoal is tested — grep)

**Interfaces:**
- Consumes: `min_plan_length` (Task 1).

- [ ] **Step 1: Failing test**

Add to the UpgradeEquipmentGoal test file (find via `grep -rln "is_plannable" tests/`):

```python
def test_is_plannable_rejects_from_scratch_feather_coat():
    """feather_coat from scratch: true plan ~18 > max_depth 15 -> is_plannable False
    (was wrongly True because min_gathers omitted crafts+equip)."""
    gd = GameData()
    gd._crafting_recipes = {"feather_coat": {"feather": 5, "ash_plank": 2},
                            "ash_plank": {"ash_wood": 10}}
    gd._item_stats = {"feather_coat": ItemStats(code="feather_coat", level=5,
                        type_="body_armor", crafting_skill="gearcrafting", crafting_level=5)}
    gd._max_gather_yield = 1
    state = make_state(skills={"gearcrafting": 5}, inventory={"ash_wood": 10},
                       equipment={"body_armor_slot": None})
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                committed_target=("feather_coat", "body_armor_slot"))
    assert goal.is_plannable(state, gd) is False


def test_is_plannable_admits_short_chain():
    """Same gear with planks in hand + few feathers: plan ~7 <= 15 -> True."""
    gd = GameData()
    gd._crafting_recipes = {"feather_coat": {"feather": 5, "ash_plank": 2},
                            "ash_plank": {"ash_wood": 10}}
    gd._item_stats = {"feather_coat": ItemStats(code="feather_coat", level=5,
                        type_="body_armor", crafting_skill="gearcrafting", crafting_level=5)}
    gd._max_gather_yield = 1
    state = make_state(skills={"gearcrafting": 5}, inventory={"ash_plank": 2},
                       equipment={"body_armor_slot": None})
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                committed_target=("feather_coat", "body_armor_slot"))
    assert goal.is_plannable(state, gd) is True
```

(Match the test file's existing `make_state`/`ItemStats`/`GameData` fixture idioms; confirm `gd.max_gather_yield` is set via `gd._max_gather_yield`.)

- [ ] **Step 2: Run, verify fail** (current code admits feather_coat → True, test wants False).

- [ ] **Step 3: Rewire `is_plannable`**

In `progression.py`, replace lines 139-142 (the `gathers = ceil_gathers(min_gathers(...))` / `return gathers <= self.max_depth`) with:

```python
        owned_eq: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned_eq[code] = owned_eq.get(code, 0) + qty
        return min_plan_length(
            item, 1, game_data.crafting_recipes, owned_eq,
            game_data.max_gather_yield, equip=True,
        ) <= self.max_depth
```

(Note `owned` is already built at lines 121-123 as `owned`; reuse that variable name instead of `owned_eq` if it is in scope at this point — read the function and use the existing `owned`.) Add the import at top: `from artifactsmmo_cli.ai.min_plan_length import min_plan_length`. Remove the now-unused `ceil_gathers`/`min_gathers` imports IF nothing else in the file uses them (grep first — `min_gathers`/`ceil_gathers` may be used elsewhere in progression.py; keep them if so).

- [ ] **Step 4: Run pass; full suite for regressions**

Run: `~/.local/bin/uv run pytest tests/test_ai/ --no-cov -q` (the is_plannable change affects objective-step routing — confirm no regressions; some existing UpgradeEquipment tests may shift from admit→reject for deep chains; update any whose intent is preserved, do NOT weaken).

- [ ] **Step 5: Gate + commit**

```bash
git add src/artifactsmmo_cli/ai/goals/progression.py tests/test_ai/test_progression.py
git commit -m "fix(ai): is_plannable uses min_plan_length (count crafts+equip) — reject over-deep gear"
```

---

### Task 3: Objective-step end-to-end behavior

**Files:**
- Test: `tests/test_ai/test_strategy_driver.py`

**Interfaces:** Consumes Task 2 (`is_plannable` now rejects deep feather_coat).

- [ ] **Step 1: Failing test** — committed feather_coat from scratch routes to a `GatherMaterials` step (branch-3 incremental), NOT an empty-plan `UpgradeEquipment`, and is non-None (no char-level fallthrough for an attainable objective).

```python
def test_deep_gear_routes_to_incremental_gather_not_empty_upgrade():
    """feather_coat from scratch: objective_step_goal returns a GatherMaterials
    step (incremental progress), not the over-deep UpgradeEquipment that planned
    to plan_len=0 and stalled on slime-leveling (trace 2026-06-19)."""
    gd = _gd_feather_coat()   # recipes + stats + gearcrafting-5 gate satisfied
    state = make_state(skills={"gearcrafting": 5, "woodcutting": 3},
                       inventory={"ash_wood": 10}, equipment={"body_armor_slot": None})
    step = ObtainItem("ash_plank", 2)
    root = ObtainItem("feather_coat", 1, slot="body_armor_slot")
    goal = objective_step_goal(step, state, gd, _ctx(), root=root, committed_root=root)
    assert goal is not None
    assert type(goal).__name__ == "GatherMaterialsGoal"
```

(Build `_gd_feather_coat` from the test file's fixture idioms; ObtainItem signature per the file's imports.)

- [ ] **Step 2: Run** — should PASS already if Task 2 made is_plannable reject feather_coat (branch-1 falls to branch-3). If it FAILS (returns UpgradeEquipment or None), the routing needs the depth-unreachable branch to fire — investigate `strategy_driver.py:483-531`; the `is_plannable=False` path should reach the `gather_step_target` branch (512-531). Fix routing only if needed; do not change branch semantics beyond making the rejected-deep case reach branch-3.

- [ ] **Step 3: Gate + commit**

```bash
git add tests/test_ai/test_strategy_driver.py
git commit -m "test(ai): deep gear objective routes to incremental gather, not empty upgrade"
```

---

### Task 4: Lean plan-action model + `minPlanLength` + extraction

**Files:**
- Create: `formal/Formal/PlanModel.lean`
- Modify: `formal/Formal.lean` (import), `scripts/extract_lean.py` (register MinCrafts + MinPlanLength)

**Interfaces:** Produces the Lean model + defs Tasks 5-7 prove over.

- [ ] **Step 1: Define the model** in `PlanModel.lean`:

```lean
import Formal.Extracted.MinGathers
import Formal.Extracted.MinCrafts
namespace Formal.PlanModel

inductive Action where
  | gather (code : String)
  | craft  (code : String)
  | equip  (code : String)

abbrev Plan := List Action

-- produces: multiset (assoc-list) of items a plan yields from `owned`, via an
-- apply semantics: gather code -> +1 code; craft code -> +1 code consuming its
-- recipe inputs; equip code -> requires code present.
-- SatisfiesEquip P item : the plan crafts+equips `item` (an equip code action
-- for item with item produced before it).
...
```

Define `produces`/`apply` and `SatisfiesEquip` precisely (the implementer designs the cleanest formulation — an assoc-list state threaded through `List.foldl`, mirroring `_min_gathers`). Add `minPlanLength` Lean def matching production (extracted form).

- [ ] **Step 2: Extract MinCrafts + MinPlanLength**

Register `min_crafts.py` and `min_plan_length.py` in `scripts/extract_lean.py`; `~/.local/bin/uv run python scripts/extract_lean.py`; confirm `Extracted/MinCrafts.lean`, `Extracted/MinPlanLength.lean` written and `--check` clean.

- [ ] **Step 3: `cd formal && lake build`** — model compiles (defs only, no proofs yet, 0 sorry). Commit.

```bash
git add formal/Formal/PlanModel.lean formal/Formal/Extracted/MinCrafts.lean formal/Formal/Extracted/MinPlanLength.lean scripts/extract_lean.py formal/Formal.lean
git commit -m "feat(formal): plan-action model + minPlanLength/minCrafts extraction"
```

---

### Task 5: Prove `minGathers_le_gathers` (mass-conservation)

The hardest lemma. Use `lean4:prove` / `lean4:sorry-filler-deep`.

**Files:** Modify `formal/Formal/PlanModel.lean`.

- [ ] **Step 1: State the lemma**

```lean
/-- Mass conservation: any plan that `produces` `item` (qty 1) from `owned` uses
at least `min_gathers item 1 recipes owned` GATHER actions. Every item unit is a
held copy, a gather (+1 raw), or a craft (consumes inputs); inducting over the
recipe DAG, the raw-gather count is ≥ min_gathers. NOT modeled: movement,
inventory limits (named here, out of the action set by construction). -/
theorem minGathers_le_gathers (recipes owned) (P : Plan) (item : String)
    (h : Produces P owned item 1) :
    (Extracted.MinGathers.min_gathers item 1 recipes owned)
      ≤ (P.countP (· matches .gather _)) := ...
```

- [ ] **Step 2: Prove it** (induction on recipe fuel / structural on the produces derivation). Build until `lake build` clean, 0 sorry. This may take several `lean4:proof-repair` iterations; if the chosen `produces` formulation makes the induction intractable, revise the model (Task 4) — that is expected proof-design iteration, not a blocker.

- [ ] **Step 3: Commit** `feat(formal): minGathers_le_gathers mass-conservation lemma`.

---

### Task 6: Craft/equip lower bounds → `min_plan_length_le_plan`

**Files:** Modify `formal/Formal/PlanModel.lean`.

- [ ] **Step 1: State + prove the remaining sub-lemmas**

```lean
theorem minCrafts_le_crafts (recipes owned) (P : Plan) (item : String)
    (h : Produces P owned item 1) :
    (Extracted.MinCrafts.min_crafts item 1 recipes owned)
      ≤ (P.countP (· matches .craft _)) := ...

theorem one_le_equips (P : Plan) (item : String) (h : SatisfiesEquip P item) :
    1 ≤ (P.countP (· matches .equip _)) := ...
```

- [ ] **Step 2: Compose** — gather/craft/equip `countP`s are disjoint and sum to `≤ P.length`:

```lean
/-- THE DISCHARGE TARGET: min_plan_length is a sound lower bound on the length of
any plan that crafts+equips `item`. (Action model = gather/craft/equip only;
movement + inventory NOT counted — see module docstring.) -/
theorem min_plan_length_le_plan (recipes owned maxYield) (P : Plan) (item : String)
    (h : SatisfiesEquip P item) :
    Extracted.MinPlanLength.min_plan_length item 1 recipes owned maxYield true
      ≤ P.length := ...
```

(The mint term uses `ceil_gathers`; relate `gather count * maxYield ≥ gathered units ≥ min_gathers ⟹ gather count ≥ ceil_gathers(min_gathers)`.)

- [ ] **Step 3: `lake build` clean; commit** `feat(formal): min_plan_length_le_plan — sound plan-length lower bound`.

---

### Task 7: Discharge `hsat_lb` in `PlannerDepthBound`

**Files:** Modify `formal/Formal/PlannerDepthBound.lean`.

- [ ] **Step 1: Prove the discharged no-plan theorem** — instantiate the existing `reachable_not_satisfying_when_lb_exceeds_depth` with `lb = min_plan_length`, `satisfyingLen = SatisfiesEquip`-on-the-node's-plan, hypothesis proved by `min_plan_length_le_plan` (NO assumed `hsat_lb`):

```lean
/-- DISCHARGED gate soundness: under a goal's `maxDepth`, if min_plan_length of
the target exceeds maxDepth, no reachable node carries a satisfying plan — the
planner provably returns no plan. The lower-bound hypothesis is DISCHARGED via
PlanModel.min_plan_length_le_plan; nothing is assumed. (Bounds gather/craft/equip
actions only; A* completeness within budget + movement/inventory are NOT proven.) -/
theorem min_plan_length_gt_maxDepth_imp_no_plan
    (maxDepth : Nat) (recipes owned maxYield) (item : String)
    (hexceed : maxDepth < Extracted.MinPlanLength.min_plan_length item 1 recipes owned maxYield true)
    (n : Node) (hreach : Reachable maxDepth n) :
    ¬ (NodePlanSatisfiesEquip n item) := ...
```

- [ ] **Step 2: Retire the assumed-hypothesis instance** — replace `copper_boots_unreachable_under_upgrade_depth` (which assumes `planLen ≥ 80`) with a version using the discharged theorem (or delete it if subsumed). Confirm: `grep -n "hsat_lb\|planLen ≥\|planLen >= " formal/Formal/PlannerDepthBound.lean` shows NO assumed lower-bound hypothesis remaining on the final no-plan theorem.

- [ ] **Step 3: `lake build` clean, 0 sorry; axiom-clean.** Commit `feat(formal): discharge hsat_lb — depth gate soundness with no assumed lower bound`.

---

### Task 8: Differential + mutation + full gate

**Files:**
- Create: `formal/diff/test_min_plan_length_diff.py`
- Read-only: `formal/gate.sh`

- [ ] **Step 1: Differential** — model on `formal/diff/test_gather_step_target_diff.py`: Hypothesis-generate DAG recipes + holdings, assert production `min_plan_length(...) ==` the Lean oracle (`run_oracle` for `minPlanLength`). Wire the oracle arg in `formal/Oracle.lean` if needed (mirror the `min_gathers` oracle entry).

Run: `~/.local/bin/uv run pytest formal/diff/test_min_plan_length_diff.py --no-cov -q` → green.

- [ ] **Step 2: Full differential + mutation** — `~/.local/bin/uv run pytest formal/diff/ --no-cov -q -n auto` (ALL green). Then `~/.local/bin/uv run python formal/diff/mutate.py` (ALONE) — add a mutation that DROPS the `+ min_crafts` term in `min_plan_length` and confirm it is KILLED (the differential or a production test catches it).

- [ ] **Step 3: Full gate (serialized, foreground, alone)**

Run: `cd formal && bash gate.sh 2>&1 | tail -40`
Expected: ALL GATE PARTS PASSED. If a red appears, determine pre-existing-vs-new (`git stash` + gate on base) and report.

- [ ] **Step 4: Behavior re-validation (optional, recommended)** — with the bot idle, reproduce the offline check from the spec: `min_plan_length("feather_coat", from-scratch) > 15` and `is_plannable False`; `GatherMaterials(feather)` plans to `Fight(chicken)`. Confirm the live Robby (after restart) commits feather_coat AND takes a gather/fight step, not green_slime.

- [ ] **Step 5: Memory + finish** — update memory ([[feedback_planner_depth]], a new `project_plannability_soundness` pointer noting the discharged `hsat_lb`). Invoke `superpowers:finishing-a-development-branch`.

---

## Self-Review

**Spec coverage:**
- `min_plan_length` core (mints+crafts+equip) → Task 1. ✓
- `is_plannable` rewire → Task 2. ✓
- Behavioral outcome (incremental route, no empty-plan stall) → Task 3. ✓
- Plan-action model + `min_plan_length_le_plan` → Tasks 4-6. ✓
- Discharge `hsat_lb` (no assumed hypothesis) → Task 7. ✓
- Extraction + differential + mutation + gate → Tasks 4,8. ✓
- Honest "NOT proven" boundaries in docstrings → Tasks 5-7 statements. ✓

**Placeholder scan:** production code + tests are complete; Lean steps give theorem STATEMENTS + model definitions + proof STRATEGY (tactics are interactive — lean4 skills), with the model-design-iteration caveat called out. No "TBD".

**Type consistency:** `min_crafts(item,qty,recipes,owned)→int`, `min_plan_length(item,qty,recipes,owned,max_gather_yield,*,equip)→int`, Lean `minPlanLength`/`minCrafts` extracted names, `min_plan_length_le_plan` / `min_plan_length_gt_maxDepth_imp_no_plan` consistent across Tasks 1→8.

**Risk note:** Tasks 5-6 (the mass-conservation + composition proofs) are genuine, uncertain proof work — the `produces`/`SatisfiesEquip` model formulation (Task 4) may need iteration to make the induction tractable. That is expected; budget for it. If after real effort the full discharge proves intractable, STOP and escalate (do NOT leave `sorry` or reintroduce an assumed `hsat_lb` — that would recreate the exact flattering-proof gap this work exists to close).
