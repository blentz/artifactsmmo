# Batch-Craft Output Quantity (Learned Yield) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 5–6 are formal-development tasks: drive the Lean proving with the `lean4:*` skills (`lean4:prove`, `lean4:proof-repair`) and treat `formal/gate.sh` as the oracle — proof bodies are discovered iteratively, not pre-written.

**Goal:** The planner reads each recipe's real output yield (`CraftSchema.quantity`, refined by live-observed amounts) so it no longer assumes 1 item per craft — fixing over-gather, over-craft, and apply/task/XP miscounts when a recipe yields >1.

**Architecture:** A `craft_yield` prior (from `CraftSchema.quantity`) plus a `LearningStore`-backed observed-yield recorder fed by real craft responses; `resolve_craft_yields(game_data, history)` produces a `{code: yield}` map (learned > prior > 1) that the impure wrappers pass into the proved-pure `RecipeClosure` cores, which gain ceil-division batch semantics (`⌈m/Y⌉`). `crafting.apply` credits `runs × Y`.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (`lake`), Hypothesis differential, mutation runner, SQLite (LearningStore).

## Global Constraints

- Run every Python command via `uv run`. All imports at top of file; no inline imports; no `except Exception`; no `if TYPE_CHECKING`; one behavioral class per file.
- **Use only API data:** yield prior = `CraftSchema.quantity`; learned yield = observed from real craft responses; default `1` only when there is no recipe and no observation.
- `record_craft_yield` is best-effort (log + swallow like the existing `record_*` methods) — a learning write must never abort a live craft.
- **Regression-safe:** all live v7.0.4 recipes are `Y=1` and the learning store is empty offline → the change must be a no-op against today's data. Existing tests stay green unchanged.
- **Formal lockstep:** any change to a proved core (`RecipeClosure`: `_raw_units`, `_closure_demand`) requires the Lean def + role theorems + `Contracts.lean` pin + extracted-image regen + differential + mutation to move together. The gate (`formal/gate.sh`) must be green.
- **Serialize gate runs:** before `formal/gate.sh` or `formal/diff/mutate.py`, verify `pgrep -af "artifactsmmo play"` is empty. Mutation rewrites `src/` in place.
- Test-suite success: 0 failures/warnings/skips, 100% coverage.

---

### Task 1: Yield prior — `GameData.craft_yield`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (`_build_items` ~1209-1220; add `_craft_yields` storage + `craft_yield` accessor)
- Test: `tests/test_ai/test_game_data.py` (or the existing game_data test module)

**Interfaces:**
- Produces: `GameData.craft_yield(code: str) -> int` — the recipe's `craft.quantity` (default `1` when no recipe / `UNSET`).

- [ ] **Step 1: Write the failing test**

```python
def test_craft_yield_reads_quantity_default_one(monkeypatch):
    # Build a GameData with two crafted items: one yield-2, one with quantity UNSET (→1).
    from artifactsmmo_cli.ai.game_data import GameData
    gd = GameData.__new__(GameData)
    gd._crafting_recipes = {"potion": {"herb": 1}, "bar": {"ore": 2}}
    gd._craft_yields = {"potion": 2}  # bar omitted → default 1
    assert gd.craft_yield("potion") == 2
    assert gd.craft_yield("bar") == 1      # present recipe, no yield → 1
    assert gd.craft_yield("ore") == 1      # raw, no recipe → 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data.py::test_craft_yield_reads_quantity_default_one -v`
Expected: FAIL — `AttributeError` (`_craft_yields` / `craft_yield` missing).

- [ ] **Step 3: Add storage + accessor**

In `game_data.py`, alongside the `_crafting_recipes` property/setter add a `_craft_yields: dict[str, int]` field (initialized `{}` wherever `_crafting_recipes` is initialized). In `_build_items`, inside the `if not isinstance(craft.items, Unset) and craft.items:` block, after building `recipe`, record the yield:

```python
                    self._crafting_recipes[item.code] = recipe
                    if not isinstance(craft.quantity, Unset) and craft.quantity:
                        self._craft_yields[item.code] = craft.quantity
```

Add the accessor:

```python
    def craft_yield(self, code: str) -> int:
        """Items produced per craft run of `code` (CraftSchema.quantity); 1 by default."""
        return self._craft_yields.get(code, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_game_data.py::test_craft_yield_reads_quantity_default_one -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(craft-yield): read CraftSchema.quantity into GameData.craft_yield prior"
```

---

### Task 2: Learning — record observed yield + XP from real craft responses

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (new table + `record_craft_yield` + `observed_craft_yield`, mirroring `record_skill_max_xp` at ~526-561)
- Modify: `src/artifactsmmo_cli/ai/actions/crafting.py` (`execute` ~98-110 reads `result.data.details`)
- Test: `tests/test_ai/test_learning_store.py` and `tests/test_ai/test_crafting_action.py` (existing modules)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `LearningStore.record_craft_yield(item_code: str, quantity: int, xp: int) -> None`
  - `LearningStore.observed_craft_yield(item_code: str) -> tuple[int, int] | None` (`(quantity, xp)` or None)

- [ ] **Step 1: Write the failing test (store round-trip)**

```python
def test_record_and_read_craft_yield(tmp_path):
    from artifactsmmo_cli.ai.learning.store import LearningStore
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="Robby")
    assert store.observed_craft_yield("potion") is None
    store.record_craft_yield("potion", quantity=2, xp=15)
    assert store.observed_craft_yield("potion") == (2, 15)
    store.record_craft_yield("potion", quantity=3, xp=20)   # last write wins
    assert store.observed_craft_yield("potion") == (3, 20)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_learning_store.py::test_record_and_read_craft_yield -v`
Expected: FAIL — methods missing.

- [ ] **Step 3: Add the table + methods**

In `store.py`'s schema init (where the other `CREATE TABLE` statements live in `__init__`), add:

```python
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS craft_yield ("
            "character TEXT NOT NULL, item_code TEXT NOT NULL, "
            "quantity INTEGER NOT NULL, xp INTEGER NOT NULL, "
            "PRIMARY KEY (character, item_code))"
        )
```

Add the methods (mirror `record_skill_max_xp`'s best-effort log-and-swallow style):

```python
    def record_craft_yield(self, item_code: str, quantity: int, xp: int) -> None:
        """Upsert observed (quantity, xp) for (character, item_code). Last write wins."""
        try:
            self._conn.execute(
                "INSERT INTO craft_yield (character, item_code, quantity, xp) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(character, item_code) "
                "DO UPDATE SET quantity=excluded.quantity, xp=excluded.xp",
                (self._character, item_code, quantity, xp),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"[learning] record_craft_yield failed: {e}")

    def observed_craft_yield(self, item_code: str) -> tuple[int, int] | None:
        """Observed (quantity, xp) for (character, item_code), or None."""
        row = self._conn.execute(
            "SELECT quantity, xp FROM craft_yield WHERE character=? AND item_code=?",
            (self._character, item_code),
        ).fetchone()
        return (row[0], row[1]) if row is not None else None
```

(Use the module's existing connection attribute name and `sqlite3` import — match the surrounding `record_*` methods exactly.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_learning_store.py::test_record_and_read_craft_yield -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test (execute records from details)**

In `tests/test_ai/test_crafting_action.py`, add a test that drives `CraftAction.execute` with a fake client whose craft response carries `details` (a `SkillInfoSchema` with `xp` and an `items` list containing a `DropSchema` for the crafted code) and a recorded `LearningStore`, asserting `observed_craft_yield(code)` reflects the produced quantity + xp. Mirror the existing crafting-action test's client/double pattern; construct the response with `details.items = [DropSchema(code=<crafted>, quantity=2)]`, `details.xp = 15`. The action must be given the store (see Step 6 for how `execute` reaches it).

- [ ] **Step 6: Wire `execute` to record**

`CraftAction.execute` currently ignores `result.data.details`. After `result = Action._raise_for_error(...)`, before building the returned `WorldState`, record the observed yield/xp when a history handle is available. `execute(self, state, client)` has no history param; thread it the same way other actions reach the store (inspect a neighbouring action that records to `LearningStore` — e.g. fight/gather outcome recording — and follow that exact mechanism; if actions receive history via the executor, use that). Record the quantity credited to `self.code` by summing `d.quantity for d in result.data.details.items if d.code == self.code` and `result.data.details.xp`:

```python
        details = result.data.details
        produced = sum(d.quantity for d in details.items if d.code == self.code)
        history.record_craft_yield(self.code, produced, details.xp)
```

Guard on a non-None history handle. Do NOT add `except Exception` — `record_craft_yield` already swallows DB errors.

- [ ] **Step 7: Run the crafting-action tests**

Run: `uv run pytest tests/test_ai/test_crafting_action.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py src/artifactsmmo_cli/ai/actions/crafting.py tests/test_ai/test_learning_store.py tests/test_ai/test_crafting_action.py
git commit -m "feat(craft-yield): learn observed craft yield + xp from real craft responses"
```

---

### Task 3: `resolve_craft_yields` + apply credits runs×Y

**Files:**
- Create: `src/artifactsmmo_cli/ai/craft_yield_resolution.py` (`resolve_craft_yields`)
- Modify: `src/artifactsmmo_cli/ai/actions/crafting.py` (`apply` ~48-90)
- Test: `tests/test_ai/test_craft_yield_resolution.py`, `tests/test_ai/test_crafting_action.py`

**Interfaces:**
- Consumes: `GameData.craft_yield` (Task 1), `LearningStore.observed_craft_yield` (Task 2).
- Produces: `resolve_craft_yields(game_data, history) -> dict[str, int]` — `{code: learned-or-prior}` for every code in `game_data.crafting_recipes` (learned quantity overrides the prior when observed). Codes absent from the map resolve to 1 at use sites.

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_craft_yields_learned_overrides_prior():
    from artifactsmmo_cli.ai.craft_yield_resolution import resolve_craft_yields

    class _GD:
        crafting_recipes = {"potion": {"herb": 1}, "bar": {"ore": 2}}
        def craft_yield(self, code): return {"potion": 2, "bar": 1}.get(code, 1)

    class _Hist:
        def observed_craft_yield(self, code):
            return (3, 99) if code == "potion" else None   # learned potion=3

    assert resolve_craft_yields(_GD(), _Hist()) == {"potion": 3, "bar": 1}
    assert resolve_craft_yields(_GD(), None) == {"potion": 2, "bar": 1}  # priors only
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_craft_yield_resolution.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `resolve_craft_yields`**

```python
"""Resolve each craftable item's effective output yield: learned > prior > 1."""

from collections.abc import Mapping


def resolve_craft_yields(game_data: object, history: object | None) -> dict[str, int]:
    """{item_code: effective yield} for every craftable item.

    Prior = game_data.craft_yield(code) (CraftSchema.quantity, default 1).
    Override with history.observed_craft_yield(code)[0] (the observed produced
    quantity) when present. Learning never reaches the proved cores — callers
    pass the returned map in.
    """
    recipes: Mapping[str, dict[str, int]] = game_data.crafting_recipes
    yields: dict[str, int] = {code: game_data.craft_yield(code) for code in recipes}
    if history is not None:
        for code in recipes:
            observed = history.observed_craft_yield(code)
            if observed is not None:
                yields[code] = observed[0]
    return yields
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_craft_yield_resolution.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing apply test**

In `tests/test_ai/test_crafting_action.py`, add a test asserting that `CraftAction(code="potion", quantity=runs).apply(state, gd)` (with `gd.craft_yield("potion") == 2`) credits `runs × 2` to inventory, advances `task_progress` by `runs × 2` for a matching crafting task, and advances `projected_skill_xp_delta` by `runs × 2` (prior path) — and that a `Y=1` item is unchanged from today's behavior.

- [ ] **Step 6: Update `apply` to use yield**

In `crafting.py` `apply`, read the yield and credit produced = runs × Y:

```python
        y = game_data.craft_yield(self.code)
        produced = self.quantity * y
        new_inventory[self.code] = new_inventory.get(self.code, 0) + produced
```

Update task progress and the xp-proxy delta to use `produced`:

```python
        new_progress = (
            state.task_progress + produced
            if state.task_type == "crafting" and state.task_code == self.code
            else state.task_progress
        )
        ...
            new_delta[stats.crafting_skill] = (
                new_delta.get(stats.crafting_skill, 0) + produced
            )
```

(Ingredient consumption `mat_qty * self.quantity` is per-run and stays unchanged. The learned-xp-per-craft refinement is recorded by Task 2 and can feed a future planner read; the prior path here uses `produced` per the per-item decision.)

- [ ] **Step 7: Run the crafting-action suite**

Run: `uv run pytest tests/test_ai/test_crafting_action.py -v`
Expected: PASS (new + existing; `Y=1` items unchanged).

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/craft_yield_resolution.py src/artifactsmmo_cli/ai/actions/crafting.py tests/test_ai/test_craft_yield_resolution.py tests/test_ai/test_crafting_action.py
git commit -m "feat(craft-yield): resolve learned>prior yield; apply credits runs×Y"
```

---

### Task 4: `_closure_demand` / `_raw_units` ceil-batch — Python cores + tests

**Files:**
- Modify: `src/artifactsmmo_cli/ai/recipe_closure.py` (`_raw_units` ~67-86, `_closure_demand` ~89-112, and the public wrappers)
- Modify: callers of `_closure_demand` / `recipe_closure` demand that must thread `yields` (e.g. `recipe_cost_memo.py`, the goals building gather targets, `craft_plan_gen.py`)
- Test: `tests/test_ai/test_recipe_closure.py`

**Interfaces:**
- Consumes: a `yields: Mapping[str, int]` map (Task 3's `resolve_craft_yields`).
- Produces: `_closure_demand` / `_raw_units` gain a `yields` parameter; demand of `m` of a yield-`Y` node scales children by `⌈m/Y⌉ × qty_per`. Public wrappers gain an optional `yields: Mapping[str,int] | None` (default = all-1 / prior map).

- [ ] **Step 1: Write the failing test**

```python
def test_closure_demand_ceil_batches_with_yield():
    from artifactsmmo_cli.ai.recipe_closure import _closure_demand
    recipes = {"potion": {"herb": 1}}        # potion needs 1 herb per CRAFT
    yields = {"potion": 2}                    # each craft yields 2 potions
    # Need 3 potions → ⌈3/2⌉ = 2 crafts → 2 herbs (not 3).
    out = _closure_demand(len(recipes) + 1, "potion", 3, recipes, yields, {}, {})
    assert out["potion"] == 3
    assert out["herb"] == 2

def test_closure_demand_yield_one_unchanged():
    from artifactsmmo_cli.ai.recipe_closure import _closure_demand
    recipes = {"bar": {"ore": 2}}
    out = _closure_demand(len(recipes) + 1, "bar", 3, recipes, {}, {}, {})  # Y default 1
    assert out["bar"] == 3 and out["ore"] == 6                              # today's behavior
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_recipe_closure.py -k ceil_batches -v`
Expected: FAIL — `_closure_demand` has no `yields` parameter.

- [ ] **Step 3: Add ceil-batch semantics**

Add a `yields` parameter to `_closure_demand` (and `_raw_units`). In `_closure_demand`, before recursing into children, convert the node's demanded item-count `multiplier` into craft-batches via ceil division by the node's yield, then scale inputs by batches:

```python
def _closure_demand(fuel: int, root: str, multiplier: int,
                    recipes: Mapping[str, dict[str, int]],
                    yields: Mapping[str, int],
                    visited: dict[str, int], out: dict[str, int]) -> dict[str, int]:
    if fuel <= 0:
        return out
    if visited.get(root, 0) == 1:
        return out
    sub_visited = dict(visited)
    sub_visited[root] = 1
    if multiplier > out.get(root, 0):
        out[root] = multiplier
    recipe = recipes.get(root, {})
    y = yields.get(root, 1)
    batches = (multiplier + y - 1) // y          # ⌈multiplier / y⌉
    for mat, qty_per in recipe.items():
        if qty_per <= 0:
            continue
        out = _closure_demand(fuel - 1, mat, batches * qty_per, recipes, yields, sub_visited, out)
    return out
```

Apply the matching ceil-batch change to `_raw_units` (per-item raw cost divides the recipe-input contribution by the node's yield with the same ceil semantics; keep it consistent with `_closure_demand` so the cost heuristic stays sound). Update the public wrappers (`recipe_closure`, the demand wrapper, `recipe_closure_pure` if it forwards demand) to accept an optional `yields` and default it to `{}` (→ all yields 1, today's behavior).

- [ ] **Step 4: Thread `yields` through callers**

Update every caller of the changed cores/wrappers to pass the resolved yields map (from `resolve_craft_yields(game_data, history)`), defaulting to the prior map when no history. Grep for `_closure_demand`, `_raw_units`, and the demand wrapper across `src/` and update each call site. Keep `_closure_visited` / closure-set callers unchanged (yield-independent).

- [ ] **Step 5: Run the recipe-closure suite**

Run: `uv run pytest tests/test_ai/test_recipe_closure.py -v`
Expected: PASS (new + existing; `Y=1` paths unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/recipe_closure.py src/artifactsmmo_cli/ai/recipe_cost_memo.py src/artifactsmmo_cli/ai/craft_plan_gen.py tests/test_ai/test_recipe_closure.py
git commit -m "feat(craft-yield): ceil-batch closure demand + raw_units over the yield map"
```

---

### Task 5: Lean lockstep — `RecipeClosure` core re-proof (FORMAL)

**Files:**
- Modify: `formal/Formal/RecipeClosure.lean` (the `rawUnits` / closure-demand `def`s + role theorems)
- Modify: `formal/Formal/Contracts.lean` (re-pin the now yield-parameterised statements)
- Modify: `scripts/extract_lean.py` (RecipeClosure ModuleSpec — function signatures) + regenerate `formal/Formal/Extracted/RecipeClosure.lean` (and any importer)
- Modify: `formal/Oracle.lean` (decode the new `yields` argument for the affected functions)

**Interfaces:**
- Consumes: the Python cores from Task 4 (the Lean defs must mirror them exactly).
- Produces: kernel-checked theorems for the yield-parameterised cores; byte-identical extracted image.

This is a `lean4`-driven task. Drive proving with `lean4:prove` / `lean4:proof-repair`; the gate parts are the success oracle. Proof bodies are not pre-written.

- [ ] **Step 1: Mirror the Python defs in Lean**

Add a `yields` input (a `Nat → Nat` or association-list lookup, default 1) to the Lean `rawUnits` and closure-demand `def`s so they compute `⌈m/y⌉` via `(m + y - 1) / y` exactly as the Python cores. Keep `closureVisited` / set-level defs unchanged.

- [ ] **Step 2: Re-prove the role theorems**

The affected theorems (`rawUnits_eq_cost`, `rawUnits_revisit`, `rawUnits_raw`, `rawUnits_fuel_stable`, `rawUnits_top_eq_cost`, and any closure-demand soundness theorem) must hold with the yield parameter. Re-establish each with `lean4:prove`; for `Y=1` the statements must reduce to the originals (a sanity check that the generalization is faithful). Add a satisfiability witness for any theorem that gains a yield hypothesis (avoid a vacuous generalization).

Run (per module): `cd formal && lake build Formal.RecipeClosure`
Expected: builds, no `sorry`.

- [ ] **Step 3: Regenerate the extracted image**

Update the `RecipeClosure` ModuleSpec in `scripts/extract_lean.py` for the new signatures, then:

Run: `uv run python scripts/extract_lean.py`
Then: `uv run python scripts/extract_lean.py --check`
Expected: `--check` exits 0 (no drift); the Python cores and `Extracted/RecipeClosure.lean` agree byte-for-byte.

- [ ] **Step 4: Re-pin contracts + manifest**

Update `Contracts.lean` so each role theorem's exact (yield-parameterised) statement is ascribed via `example : <stmt> := @theoremName`. Confirm `Manifest.lean` still lists every required RecipeClosure role.

Run: `cd formal && lake build Formal.Contracts Formal.Manifest`
Expected: builds (a weakened statement would fail to elaborate).

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/RecipeClosure.lean formal/Formal/Contracts.lean formal/Oracle.lean scripts/extract_lean.py formal/Formal/Extracted/RecipeClosure.lean
git commit -m "feat(craft-yield): Lean lockstep — yield-parameterised RecipeClosure, re-proved"
```

---

### Task 6: Differential + mutation for the yield logic (FORMAL)

**Files:**
- Modify: `formal/diff/` harness for RecipeClosure (feed yields)
- Modify: `formal/diff/mutate.py` (anchors for the ceil-batch / `× batches` logic)

**Interfaces:**
- Consumes: Task 4 Python cores + Task 5 oracle.

- [ ] **Step 1: Extend the differential harness**

In the RecipeClosure differential test, generate random recipes WITH random yields (1..4, including non-divisible `multiplier`), feed both the Python core and the oracle the same `yields`, and assert agreement on `_closure_demand` / `_raw_units`.

Run: `pgrep -af "artifactsmmo play" || echo OK` (must be empty), then
`cd formal && lake build oracle && uv run pytest formal/diff/ -q --no-cov -n auto -k recipe_closure`
Expected: PASS.

- [ ] **Step 2: Add mutation anchors**

Add anchors that perturb the yield logic — drop the ceil (`(m+y-1)//y` → `m//y`), drop the batch scaling (`batches * qty_per` → `multiplier * qty_per`), and off-by-one (`y-1` → `y`). Each must be killed by the Step 1 differential.

Run: `uv run python formal/diff/mutate.py --only recipe_closure`
Expected: `mutation gate OK`, all new anchors killed.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/
git commit -m "test(craft-yield): differential + mutation for ceil-batch yield demand"
```

---

### Task 7: Whole-feature verification

**Files:** none (verification; commit only on a fix)

- [ ] **Step 1: Confirm the bot is stopped**

Run: `pgrep -af "artifactsmmo play" | grep -v pgrep || echo "BOT STOPPED — OK"`
Expected: `BOT STOPPED — OK`.

- [ ] **Step 2: Full Python suite**

Run: `uv run pytest`
Expected: 0 failures/warnings/skips, 100% coverage including the new modules. Because all live recipes are `Y=1` and the store starts empty, every pre-existing planner test must still pass unchanged — a regression there means the generalization is not a faithful no-op at `Y=1`; fix and re-run.

- [ ] **Step 3: Full formal gate**

Run: `cd formal && ./gate.sh`
Expected: all parts green — build, no-sorry/orphan, axiom lint, manifest, contracts, differential (incl. yield cases), mutation (incl. new anchors). Confirm `git status --porcelain src/` is empty before AND after (mutation restores `src/`).

- [ ] **Step 4: Synthetic yield-2 end-to-end sanity**

Run a focused test (add under `tests/test_ai/`) that builds a `GameData` with a yield-2 recipe and asserts the planner's gather target for "need 3" is `⌈3/2⌉ × inputs` and `apply` reaches `owned >= 3` in 2 craft runs. Commit as `test(craft-yield): synthetic yield-2 end-to-end`.

---

## Self-Review

**Spec coverage:**
- Yield prior (`CraftSchema.quantity` → `craft_yield`) → Task 1. ✅
- Learned yield + XP from real craft responses → Task 2. ✅
- `resolve_craft_yields` (learned > prior > 1) → Task 3. ✅
- `apply` credits runs×Y (inventory/task/xp) → Task 3. ✅
- `_closure_demand`/`_raw_units` ceil-batch → Task 4 (Python) + Task 5 (Lean). ✅
- Generator threads yields → Task 4 Step 4 (callers). ✅
- `min_crafts` unchanged → not a task (documented no-op). ✅
- Formal lockstep (def/theorems/contracts/extract/differential/mutation) → Tasks 5–6. ✅
- Regression-safe no-op at Y=1 → Task 7 Step 2 + the `_yield_one_unchanged` tests. ✅
- Surplus → existing overstock machinery (no task, by design). ✅

**Placeholder scan:** Code steps carry concrete code. The Lean proof bodies (Task 5) are intentionally not pre-written — formal-development drives them via `lean4:*` with the gate as oracle; this is the methodology, not a placeholder. Task 2 Step 6 and Task 4 Step 4 say "inspect the neighbouring mechanism / grep the call sites" because the exact history-threading and caller list are read from the repo, not invented — the implementer follows existing patterns.

**Type consistency:** `craft_yield(code)->int`, `record_craft_yield(item_code, quantity, xp)`, `observed_craft_yield(code)->tuple[int,int]|None`, `resolve_craft_yields(game_data, history)->dict[str,int]`, `_closure_demand(..., yields, ...)` — names consistent across tasks. `produced = runs × Y` used identically in Task 3 inventory/task/xp.
