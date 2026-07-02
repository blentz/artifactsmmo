# Intermediate-Craft Batching — Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Task 2 touches the formal perimeter — use the **formal-development** / **lean4** skills for its Lean/diff/mutation steps.

**Goal:** Close the two non-blocking follow-ups from the intermediate-craft-batching final review: (1) add a deep multi-level interleave test; (2) make `craft_batch_size_pure`'s inventory-fit yield-aware so it matches the yield-aware closure demand.

**Context:** intermediate-craft batching merged at `a5d115f6`. `craft_batch_size_pure` (`src/artifactsmmo_cli/ai/task_batch.py`) currently computes `mats_per_unit = _raw_units(..., yields={}, ...)` — yield-AGNOSTIC — while the `demand`/`chain` from `closure_demand` is yield-AWARE (`game_data.craft_yields`). No-op today (all yields=1); under yield>1 data the fit would under-batch. Fix threads yields through the core.

## Global Constraints

- All Python commands prefixed with `uv run`. Imports top only. Never catch Exception.
- Reuse `BATCH_CAP=10`, `_MIN_FREE_SLOTS=3`.
- NEVER hand-edit `formal/Formal/Extracted/*.lean` — regenerate via `uv run python scripts/extract_lean.py` and verify `--check`.
- Formal gate serialized; nothing else importing src concurrently.
- 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

### Task 1: Deep multi-level interleave test

**Files:** Test only — `tests/test_ai/test_intermediate_batch.py` (add a 3-level case).

This is verification hardening — the test should PASS against current code (proving the invariant on a deep chain), not drive a fix.

- [ ] **Step 1: Add the deep-chain test**

Add to `tests/test_ai/test_intermediate_batch.py`:

```python
from artifactsmmo_cli.ai.recipe_closure import closure_demand


def _gd_deep() -> GameData:
    """3-level chain: gem_ring <- gem_setting x2 <- gem_bar x3 <- gem_ore x4 (raw)."""
    gd = GameData()
    gd._item_stats = {
        "gem_ring": ItemStats(code="gem_ring", level=1, type_="ring",
                              crafting_skill="jewelrycrafting", crafting_level=1),
        "gem_setting": ItemStats(code="gem_setting", level=1, type_="resource",
                                 crafting_skill="jewelrycrafting", crafting_level=1),
        "gem_bar": ItemStats(code="gem_bar", level=1, type_="resource",
                             crafting_skill="mining", crafting_level=1),
        "gem_ore": ItemStats(code="gem_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "gem_ring": {"gem_setting": 2},
        "gem_setting": {"gem_bar": 3},
        "gem_bar": {"gem_ore": 4},
    }
    gd._resource_drops = {"gem_rocks": "gem_ore"}
    return gd


def test_deep_chain_each_intermediate_sized_by_raw_footprint():
    """Both intermediates in a 3-level chain size to their own closure demand,
    each bounded by its RAW-LEAF footprint (mats_per_unit), and each batch fits
    the usable space at craft time — the interleave-safety invariant."""
    gd = _gd_deep()
    chain: dict[str, int] = {}
    closure_demand("gem_ring", 1, gd, chain, frozenset())
    # closure demand for 1 ring: setting=2, bar=6, ore=24
    assert chain["gem_setting"] == 2 and chain["gem_bar"] == 6

    # ample space, nothing held
    state = make_state(inventory={}, inventory_max=1000)

    # gem_bar: raw footprint = 4 ore/bar; demand 6 -> min(6, fit, 10)=6
    bar = size_intermediate_craft(
        CraftAction(code="gem_bar", quantity=1, workshop_location=(0, 0)), chain, state, gd)
    assert bar.quantity == 6

    # gem_setting: raw footprint = 3 bar x 4 ore = 12 ore/setting; demand 2 -> 2
    setting = size_intermediate_craft(
        CraftAction(code="gem_setting", quantity=1, workshop_location=(0, 0)), chain, state, gd)
    assert setting.quantity == 2

    # interleave safety: each batch's RAW footprint fits usable at its own craft.
    # bar: 6 x 4 = 24 ore <= usable; setting after bars: 2 x 12 = 24 ore <= usable.
    # tight inventory that fits the larger single-batch footprint but not both stacked:
    tight = make_state(inventory={}, inventory_max=30)  # inventory_free 30
    bar_tight = size_intermediate_craft(
        CraftAction(code="gem_bar", quantity=1, workshop_location=(0, 0)), chain, tight, gd)
    # usable = 30 - 3 = 27; fit = 27 // 4 = 6; min(6, 6, 10) = 6
    assert bar_tight.quantity == 6
    assert bar_tight.quantity * 4 <= (30 - 3)   # raw footprint fits usable
```

- [ ] **Step 2: Run — should PASS immediately (hardening, not a fix)**

Run: `uv run pytest tests/test_ai/test_intermediate_batch.py -v`
Expected: PASS. If any assertion FAILS, that is a real deep-chain sizing bug — investigate `craft_batch_size_pure`/`_raw_units`, do not weaken the assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai/test_intermediate_batch.py
git commit -m "test(intermediate_batch): deep 3-level chain interleave-safety coverage"
```

---

### Task 2: Make `craft_batch_size_pure` yield-aware (formal core)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/task_batch.py`, `src/artifactsmmo_cli/ai/intermediate_batch.py`
- Test: `tests/test_ai/test_task_batch.py`, `tests/test_ai/test_intermediate_batch.py`
- Formal: regen `formal/Formal/Extracted/TaskBatch.lean`; update `formal/Formal/TaskBatch.lean` bridge if the extracted shape changes; extend `formal/diff/test_task_batch_diff.py`; update `formal/diff/mutate.py`.

**Interfaces:**
- `craft_batch_size_pure(code, demand, inventory, inventory_free, recipes, drops, yields) -> int` — new trailing `yields: Mapping[str,int]` param, passed to `_raw_units` (replacing the `{}`).
- `task_batch_size_pure(..., yields)` gains the same trailing param, forwards it. `task_batch_size(state, game_data)` passes `game_data.craft_yields`.
- `size_intermediate_craft` passes `game_data.craft_yields` to `craft_batch_size_pure`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ai/test_task_batch.py` a yield-aware case that DIFFERS from the yield-agnostic result — proving the param is threaded:

```python
def test_craft_batch_yield_aware_mats_per_unit():
    # recipe T <- M x4; yield 2 per craft run => raw units per RUN still 4,
    # but per OUTPUT UNIT 2. _raw_units(yields={T:2}) returns ceil-per-unit math:
    # assert the yield-aware fit differs from the yield-agnostic (yields={}) fit
    # for the same space, proving `yields` reaches _raw_units.
    recipes = {"T": {"M": 4}}
    drops = {"R": "M"}
    agnostic = craft_batch_size_pure("T", 100, {}, 50, recipes, drops, {})
    aware = craft_batch_size_pure("T", 100, {}, 50, recipes, drops, {"T": 2})
    assert aware != agnostic  # yield>1 lets more units fit per raw
```

(Compute the exact expected values from `_raw_units`'s yield formula and assert them exactly rather than just `!=`, once the yield semantics are confirmed by reading `recipe_closure._raw_units`.)

Add an `intermediate_batch` test that `size_intermediate_craft` threads `game_data.craft_yields` (set `gd._craft_yields = {code: 2}` and assert the batched quantity reflects the yield-aware footprint).

- [ ] **Step 2: Verify RED** — `uv run pytest tests/test_ai/test_task_batch.py -k yield -v` → FAIL (extra positional arg / wrong value).

- [ ] **Step 3: Implement**
- `craft_batch_size_pure`: add `yields: Mapping[str, int]` trailing param; `mats_per_unit = _raw_units(len(recipes)+1, code, recipes, yields, no_visited)`.
- `task_batch_size_pure`: add trailing `yields` param, forward to `craft_batch_size_pure`.
- `task_batch_size(state, game_data)`: pass `game_data.craft_yields`.
- `size_intermediate_craft`: pass `game_data.craft_yields` as the `yields` arg.
- Confirm the mats==0 guard and clamp are unchanged.

- [ ] **Step 4: Verify GREEN + existing tests** — `uv run pytest tests/test_ai/test_task_batch.py tests/test_ai/test_intermediate_batch.py -v`. Existing task/craft tests must still pass (with yields={} defaults they're unchanged).

- [ ] **Step 5: Regenerate extracted Lean + drift check** — `uv run python scripts/extract_lean.py` then `--check`. The extracted `craft_batch_size_pure`/`task_batch_size_pure` now carry the `yields` param.

- [ ] **Step 6: Update bridge + differential + mutation (lean4/formal-development skill)**
- `formal/Formal/TaskBatch.lean`: the `batchSize` clamp model is unchanged (it abstracts `mats` as an input); update `craft_batch_bridge`/`task_batch_bridge` if the extracted body's arity changed, compiler-guided, reusing the existing clamp lemmas. `mats_per_unit` is still an abstract `mats` input to the hand model, so the yield change is INSIDE the (already-abstracted) recipe math — the bridge likely only needs the new param plumbed, not new clamp proofs.
- `formal/diff/test_task_batch_diff.py`: extend the real-world realization so a yield>1 recipe is exercised (the oracle compares the clamp with the SAME mats input, so realize `(mats, held, demand)` with a yield-bearing recipe).
- `formal/diff/mutate.py`: refresh anchors for the new signature; add a mutant that drops the `yields` threading (passes `{}` instead) — it must be KILLED by the yield-aware differential/test (no longer an equivalent mutant, since yield>1 now diverges).

- [ ] **Step 7: Formal gate (serialized)** — differential green, mutants killed (incl. the new yields-drop mutant), `lake build` clean, extractor `--check` green.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/task_batch.py src/artifactsmmo_cli/ai/intermediate_batch.py \
        tests/test_ai/test_task_batch.py tests/test_ai/test_intermediate_batch.py \
        formal/Formal/Extracted/TaskBatch.lean formal/Formal/TaskBatch.lean \
        formal/diff/test_task_batch_diff.py formal/diff/mutate.py
git commit -m "feat(task_batch): thread craft_yields so batch fit is yield-aware"
```

---

### Task 3: Full-suite + formal-gate verification

- [ ] **Step 1:** `uv run pytest` → 0 errors/warnings/skips, 100% coverage.
- [ ] **Step 2:** `uv run mypy src/artifactsmmo_cli/ai` → clean.
- [ ] **Step 3:** task_batch differential + task_batch mutation subset + `lake build` + extractor `--check` → all green.
- [ ] **Step 4:** confirm all goal call sites (gathering, craft_plan_gen, pursue_task, craft_potions, maintain_consumables, level_skill, progression) still emit correct batched quantities — the full suite covers them; spot-check one via the existing tests.

---

## Self-Review

- **Coverage:** #1 deep-chain interleave test (Task 1); #2 yield-aware core + threading + formal re-gate (Task 2) + verification (Task 3). Both review follow-ups addressed.
- **Placeholder scan:** Task 1 + Task 2 Python steps carry code; Task 2's exact yield-aware expected values are to be pinned after reading `_raw_units`'s yield formula (noted, not left vague — the implementer computes them from the proven function). Formal proof steps defer to lean4/formal-development (compiler-guided), consistent with the merged Task-1 precedent.
- **Type consistency:** `yields` is the trailing param on both `craft_batch_size_pure` and `task_batch_size_pure`; `size_intermediate_craft`/`task_batch_size` pass `game_data.craft_yields`; goal call sites are unchanged (they call `size_intermediate_craft`, which now threads yields internally).
- **Safety:** yields defaults are never silently dropped — the yields-drop mutant becomes killable, proving the threading is load-bearing under yield>1.
