# Threshold Constants DRY (Group A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the duplicated `CRITICAL_HP_FRACTION` and the inventory space-pressure ladder fractions (`0.70 / 0.85 / 0.90 / 0.95`) into one neutral leaf module so they cannot silently drift, with zero value or behavior change.

**Architecture:** A new stdlib-only leaf `src/artifactsmmo_cli/ai/thresholds.py` becomes the single source of truth. The HIGH watermark's `num/den` pair is mechanically extracted to Lean (`scripts/extract_lean.py` → `Formal/Extracted/Thresholds.lean`), replacing the copy currently extracted from `inventory_caps.py`. Every Python consumer imports from `thresholds`; existing public constant names are kept as aliases bound to the imports so external references and the differential harness stay stable.

**Tech Stack:** Python 3.13 (managed by `uv`), Lean 4 (`lake`), Hypothesis differential harness, mutation runner (`formal/diff/mutate.py`), `formal/gate.sh`.

## Global Constraints

- Run every Python command via `uv run` (e.g. `uv run pytest`, `uv run python scripts/extract_lean.py`).
- No inline imports — all imports at the top of the file (CLAUDE.md).
- One behavioral class per file. `thresholds.py` holds only module-level data constants (allowed — no behavioral class).
- No `if TYPE_CHECKING`. No `except Exception`. No multiple implementations — fix in place.
- **No value change and no behavior change anywhere.** This is a pure consolidation. The float views must equal the old literals exactly: `PRESSURE_HIGH_FRACTION == 0.85`, `CRAFT_RELIEF_FRACTION == 0.70`, `DEPOSIT_FULL_FRACTION == 0.90`, `PRESSURE_CRITICAL_FRACTION == 0.95`, `CRITICAL_HP_FRACTION == 0.25`.
- The pressure ladder is strictly ascending: `CRAFT_RELIEF < HIGH < DEPOSIT_FULL < CRITICAL`. A proven invariant (`Formal.Liveness.MeansFiring`) relies on `HIGH < DEPOSIT_FULL`.
- Test-suite success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage (`--cov-fail-under` is enforced).
- **Serialize gate runs:** before running `formal/gate.sh` or `formal/diff/mutate.py`, verify the bot is stopped — `pgrep -af "artifactsmmo play"` must be empty. Mutation rewrites `src/` in place; a running bot would import a poisoned predicate and crash.
- The extracted `thresholds.py` constants that Lean mirrors **must be single-name int-literal module-level assignments** (`PRESSURE_HIGH_NUM = 17`), NOT tuple assignments — `scripts/extract_lean.py:_extract_constants` only recognizes `ast.Assign` with a single `Name` target and an int-literal value.

---

### Task 1: Neutral `thresholds.py` leaf module

**Files:**
- Create: `src/artifactsmmo_cli/ai/thresholds.py`
- Test: `tests/test_ai/test_thresholds.py`

**Interfaces:**
- Consumes: nothing (stdlib-only leaf).
- Produces (module-level names later tasks import):
  - `CRITICAL_HP_FRACTION: float` (0.25)
  - `CRAFT_RELIEF_NUM:int=14`, `CRAFT_RELIEF_DEN:int=20`, `PRESSURE_HIGH_NUM:int=17`, `PRESSURE_HIGH_DEN:int=20`, `DEPOSIT_FULL_NUM:int=18`, `DEPOSIT_FULL_DEN:int=20`, `PRESSURE_CRITICAL_NUM:int=19`, `PRESSURE_CRITICAL_DEN:int=20`
  - `CRAFT_RELIEF_FRACTION`, `PRESSURE_HIGH_FRACTION`, `DEPOSIT_FULL_FRACTION`, `PRESSURE_CRITICAL_FRACTION` (floats = num/den)

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_thresholds.py`:

```python
from artifactsmmo_cli.ai import thresholds


def test_critical_hp_fraction_value():
    assert thresholds.CRITICAL_HP_FRACTION == 0.25


def test_float_views_equal_legacy_literals():
    # These MUST equal the old re-typed literals exactly (no behavior change).
    assert thresholds.CRAFT_RELIEF_FRACTION == 0.70
    assert thresholds.PRESSURE_HIGH_FRACTION == 0.85
    assert thresholds.DEPOSIT_FULL_FRACTION == 0.90
    assert thresholds.PRESSURE_CRITICAL_FRACTION == 0.95


def test_float_views_equal_their_rationals():
    assert thresholds.CRAFT_RELIEF_FRACTION == thresholds.CRAFT_RELIEF_NUM / thresholds.CRAFT_RELIEF_DEN
    assert thresholds.PRESSURE_HIGH_FRACTION == thresholds.PRESSURE_HIGH_NUM / thresholds.PRESSURE_HIGH_DEN
    assert thresholds.DEPOSIT_FULL_FRACTION == thresholds.DEPOSIT_FULL_NUM / thresholds.DEPOSIT_FULL_DEN
    assert thresholds.PRESSURE_CRITICAL_FRACTION == thresholds.PRESSURE_CRITICAL_NUM / thresholds.PRESSURE_CRITICAL_DEN


def test_ladder_strictly_ascending():
    assert (thresholds.CRAFT_RELIEF_FRACTION
            < thresholds.PRESSURE_HIGH_FRACTION
            < thresholds.DEPOSIT_FULL_FRACTION
            < thresholds.PRESSURE_CRITICAL_FRACTION)


def test_pressure_high_pair_is_the_extracted_watermark():
    # The pair Lean mirrors (was inventory_caps DISCARD_WATERMARK_NUM/DEN).
    assert (thresholds.PRESSURE_HIGH_NUM, thresholds.PRESSURE_HIGH_DEN) == (17, 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_thresholds.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.thresholds'`

- [ ] **Step 3: Write the module**

Create `src/artifactsmmo_cli/ai/thresholds.py`:

```python
"""Single source of truth for the HP-critical preempt threshold and the
inventory space-pressure ladder.

Stdlib-only leaf: imports nothing from the decision layers (goals/, tiers/) so
any module can depend on it without an import cycle — the very reason these
constants used to be re-typed in several places. Consolidating them here removes
that silent-drift risk (DRY backlog Group A, findings #2 and #3).

The pressure ladder is strictly ascending: CRAFT_RELIEF < HIGH < DEPOSIT_FULL <
CRITICAL. A proven liveness invariant (Formal.Liveness.MeansFiring) relies on
HIGH < DEPOSIT_FULL; keeping the rungs in one ascending block makes an inverting
edit obvious. The Lean model carries its OWN copies of these values; the
PRESSURE_HIGH num/den pair is additionally mirrored into Lean by mechanical
extraction (scripts/extract_lean.py -> Formal/Extracted/Thresholds.lean) so the
proven overstock core and this source cannot diverge.
"""

# HP-critical preempt threshold (hp / max_hp). Below this the HP-critical guard
# preempts every other means and RestoreHPGoal returns its ceiling value.
CRITICAL_HP_FRACTION = 0.25

# Inventory space-pressure ladder, as exact integer rationals (num/den). The
# proven overstock core cross-multiplies these ints (float-free at the boundary).
# NOTE: each must be a single-name int-literal assignment — the Lean extractor
# (scripts/extract_lean.py) recognizes only that form for the mirrored pair.
CRAFT_RELIEF_NUM = 14
CRAFT_RELIEF_DEN = 20
PRESSURE_HIGH_NUM = 17
PRESSURE_HIGH_DEN = 20
DEPOSIT_FULL_NUM = 18
DEPOSIT_FULL_DEN = 20
PRESSURE_CRITICAL_NUM = 19
PRESSURE_CRITICAL_DEN = 20

# Float views (human-facing); equal the legacy re-typed literals exactly:
# 0.70 / 0.85 / 0.90 / 0.95.
CRAFT_RELIEF_FRACTION = CRAFT_RELIEF_NUM / CRAFT_RELIEF_DEN
PRESSURE_HIGH_FRACTION = PRESSURE_HIGH_NUM / PRESSURE_HIGH_DEN
DEPOSIT_FULL_FRACTION = DEPOSIT_FULL_NUM / DEPOSIT_FULL_DEN
PRESSURE_CRITICAL_FRACTION = PRESSURE_CRITICAL_NUM / PRESSURE_CRITICAL_DEN
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_thresholds.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/thresholds.py tests/test_ai/test_thresholds.py
git commit -m "feat(thresholds): neutral leaf module for HP-critical + pressure ladder constants"
```

---

### Task 2: Re-point Lean extraction to `thresholds.py`; `inventory_caps` imports the watermark

**Files:**
- Modify: `scripts/extract_lean.py` (add a `Thresholds` ModuleSpec; drop the two watermark constants from the `InventoryCaps` ModuleSpec)
- Modify: `src/artifactsmmo_cli/ai/inventory_caps.py:74-77` (import the watermark pair; bind the local names to it)
- Modify: `formal/Formal.lean` (add `import Formal.Extracted.Thresholds`)
- Generated (do not hand-edit): `formal/Formal/Extracted/Thresholds.lean` (new), `formal/Formal/Extracted/InventoryCaps.lean` (regenerated — drops the two watermark defs)

**Interfaces:**
- Consumes: `thresholds.PRESSURE_HIGH_NUM`, `thresholds.PRESSURE_HIGH_DEN` (Task 1).
- Produces: `inventory_caps.DISCARD_WATERMARK_NUM`, `inventory_caps.DISCARD_WATERMARK_DEN`, `inventory_caps.DISCARD_WATERMARK` keep their names and values (17, 20, 0.85), now aliased to the import — so `overstock_excess`'s defaults (lines 91-92) and the module helpers (line 518) are unchanged. New extracted Lean namespace `Extracted.Thresholds` with `PRESSURE_HIGH_NUM : Int := 17`, `PRESSURE_HIGH_DEN : Int := 20`.

- [ ] **Step 1: Add the `Thresholds` ModuleSpec and trim `InventoryCaps` in `extract_lean.py`**

In `scripts/extract_lean.py`, in the `MODULES` list, insert a new spec immediately BEFORE the `InventoryCaps` spec (the one with `source="src/artifactsmmo_cli/ai/inventory_caps.py"`):

```python
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/thresholds.py",
        output=f"{GENERATED_DIR}/Thresholds.lean",
        core_name="Thresholds",
        functions=(),
        constants=("PRESSURE_HIGH_NUM", "PRESSURE_HIGH_DEN"),
    ),
```

In the SAME file, edit the `InventoryCaps` spec's `constants=` line to drop the two watermark names (keep `EQUIPPABLE_KEEP`, `CONSUMABLE_KEEP`). Change:

```python
        constants=("DISCARD_WATERMARK_NUM", "DISCARD_WATERMARK_DEN",
                   "EQUIPPABLE_KEEP", "CONSUMABLE_KEEP"),
```

to:

```python
        constants=("EQUIPPABLE_KEEP", "CONSUMABLE_KEEP"),
```

- [ ] **Step 2: Point `inventory_caps.py` at the canonical watermark**

In `src/artifactsmmo_cli/ai/inventory_caps.py`, add to the top-of-file import block (with the other `artifactsmmo_cli.ai.*` imports):

```python
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_DEN, PRESSURE_HIGH_NUM
```

Then replace the watermark definition (currently lines 75-77):

```python
DISCARD_WATERMARK_NUM = 17
DISCARD_WATERMARK_DEN = 20
DISCARD_WATERMARK = DISCARD_WATERMARK_NUM / DISCARD_WATERMARK_DEN
```

with (the explanatory docstring that follows on line 78+ stays unchanged):

```python
DISCARD_WATERMARK_NUM = PRESSURE_HIGH_NUM  # canonical value lives in thresholds.py
DISCARD_WATERMARK_DEN = PRESSURE_HIGH_DEN
DISCARD_WATERMARK = DISCARD_WATERMARK_NUM / DISCARD_WATERMARK_DEN
```

- [ ] **Step 3: Regenerate the extracted Lean and verify no unexpected drift**

Run: `uv run python scripts/extract_lean.py`
Expected output includes: `wrote formal/Formal/Extracted/Thresholds.lean` and `wrote formal/Formal/Extracted/InventoryCaps.lean`.

Then inspect the diff:

```bash
git diff --stat formal/Formal/Extracted/
git diff formal/Formal/Extracted/InventoryCaps.lean
```

Expected: `Thresholds.lean` is new and contains `def PRESSURE_HIGH_NUM : Int := 17` and `def PRESSURE_HIGH_DEN : Int := 20` inside `namespace Extracted.Thresholds`. `InventoryCaps.lean` loses the two `DISCARD_WATERMARK_*` def blocks and updates the `sha256:` header + remaining line-ref comments only — no `def` body of any function changes.

- [ ] **Step 4: Wire the new module into the manifest import root**

In `formal/Formal.lean`, add the import alongside the other `Formal.Extracted.*` imports (the block around `import Formal.Extracted.InventoryCaps`):

```lean
import Formal.Extracted.Thresholds
```

- [ ] **Step 5: Verify the drift gate and Lean build are clean**

Confirm the bot is stopped first:

Run: `pgrep -af "artifactsmmo play" || echo "BOT STOPPED — OK"`
Expected: `BOT STOPPED — OK`

Run: `uv run python scripts/extract_lean.py --check`
Expected: exit 0, no `DRIFT:` lines.

Run: `cd formal && lake build Formal.Extracted.Thresholds Formal.Extracted.InventoryCaps`
Expected: build succeeds (no errors).

- [ ] **Step 6: Verify the Python inventory-caps suite still passes**

Run: `uv run pytest tests/test_ai/test_overstock.py tests/test_ai/test_inventory_profile.py tests/test_ai/test_inventory_profile_scenario.py -v`
Expected: PASS (all green) — values unchanged, so every assertion holds.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_lean.py src/artifactsmmo_cli/ai/inventory_caps.py formal/Formal.lean formal/Formal/Extracted/Thresholds.lean formal/Formal/Extracted/InventoryCaps.lean
git commit -m "refactor(thresholds): extract HIGH watermark from thresholds.py; inventory_caps imports it"
```

---

### Task 3: Migrate the float-ladder consumers to `thresholds`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (imports + lines 25-36)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py:45-47`
- Modify: `src/artifactsmmo_cli/ai/goals/restore_hp.py:26` (+ import)
- Modify: `src/artifactsmmo_cli/ai/goals/deposit_inventory.py:33` (+ import)
- Modify: `src/artifactsmmo_cli/ai/goals/unlock_bank.py:32` (+ import)
- Modify: `src/artifactsmmo_cli/ai/craft_relief.py:40` (+ import)
- Test: existing suites under `tests/test_ai/` (no new tests — pure consolidation, covered by regression)

**Interfaces:**
- Consumes: `thresholds.CRITICAL_HP_FRACTION`, `thresholds.PRESSURE_HIGH_FRACTION`, `thresholds.DEPOSIT_FULL_FRACTION`, `thresholds.PRESSURE_CRITICAL_FRACTION`, `thresholds.CRAFT_RELIEF_FRACTION` (Task 1).
- Produces: every existing public name keeps its value — `guards.CRITICAL_HP_FRACTION`, `guards.DEPOSIT_FULL_FRACTION`, `guards.DISCARD_HIGH_FRACTION`, `guards.DISCARD_CRITICAL_FRACTION`, `strategy.CRITICAL_HP_FRACTION`, `RestoreHPGoal.CRITICAL_HP_FRACTION`, `DepositInventoryGoal._RAMP_START`, `craft_relief.CRAFT_RELIEF_FRACTION` (still re-importable by guards).

- [ ] **Step 1: Verify the bot is stopped, then run the targeted suites to capture green baseline**

Run: `pgrep -af "artifactsmmo play" || echo "BOT STOPPED — OK"`
Expected: `BOT STOPPED — OK`

Run: `uv run pytest tests/test_ai/test_tiers_guards.py tests/test_ai/test_goals.py tests/test_ai/test_craft_relief.py -v`
Expected: PASS (baseline green before edits).

- [ ] **Step 2: Migrate `craft_relief.py` (canonical re-export)**

In `src/artifactsmmo_cli/ai/craft_relief.py`, add to the top import block:

```python
from artifactsmmo_cli.ai.thresholds import CRAFT_RELIEF_FRACTION
```

Then delete the local definition (line 40):

```python
CRAFT_RELIEF_FRACTION = 0.70
```

(The name remains module-level via the import, so `guards.py`'s `from artifactsmmo_cli.ai.craft_relief import CRAFT_RELIEF_FRACTION` and the in-file uses at lines 57/93/96 keep working unchanged.)

- [ ] **Step 3: Migrate `guards.py` (import canonical names; alias the guards-local names)**

In `src/artifactsmmo_cli/ai/tiers/guards.py`, add to the top import block (with the other `artifactsmmo_cli.ai.*` imports):

```python
from artifactsmmo_cli.ai.thresholds import (
    CRITICAL_HP_FRACTION,
    DEPOSIT_FULL_FRACTION,
    PRESSURE_CRITICAL_FRACTION,
    PRESSURE_HIGH_FRACTION,
)
```

Then replace the local constant block (currently lines 25-36):

```python
CRITICAL_HP_FRACTION = 0.25
# CRAFT_RELIEF_FRACTION (0.70) lives in craft_relief.py (re-imported above)
# so the candidate batch sizing and the guard predicate share one threshold.
DEPOSIT_FULL_FRACTION = 0.90
"""Space-driven (spec 2026-06-07): deposit pressure only appears near-full so
the player uses most of the bag. Kept STRICTLY ABOVE
DepositInventoryGoal._RAMP_START (0.85) so the DEPOSIT_FULL guard only fires
where the deposit goal already has strictly-positive value — the proven
liveness invariant `fires(DEPOSIT_FULL) ⇒ depositInventoryValue > 0`
(Formal.Liveness.MeansFiring) requires DEPOSIT_FULL_FRACTION > _RAMP_START."""
DISCARD_HIGH_FRACTION = 0.85
DISCARD_CRITICAL_FRACTION = 0.95
MAX_ACHIEVABLE_GAP = 5
```

with (CRITICAL_HP_FRACTION and DEPOSIT_FULL_FRACTION now come from the import above; the two guards-local names become aliases; the invariant rationale is preserved as a comment):

```python
# CRITICAL_HP_FRACTION, DEPOSIT_FULL_FRACTION are imported from thresholds above.
# CRAFT_RELIEF_FRACTION (0.70) is re-imported from craft_relief.py (which now
# re-exports it from thresholds) so batch sizing and the guard share one value.
#
# DEPOSIT_FULL_FRACTION (0.90) is space-driven (spec 2026-06-07): deposit pressure
# only appears near-full so the player uses most of the bag. It is kept STRICTLY
# ABOVE DepositInventoryGoal._RAMP_START / PRESSURE_HIGH_FRACTION (0.85) so the
# DEPOSIT_FULL guard only fires where the deposit goal already has strictly-positive
# value — the proven liveness invariant `fires(DEPOSIT_FULL) ⇒ depositInventoryValue
# > 0` (Formal.Liveness.MeansFiring) requires DEPOSIT_FULL_FRACTION > PRESSURE_HIGH.
# The thresholds ladder enforces this ordering in one ascending block.
DISCARD_HIGH_FRACTION = PRESSURE_HIGH_FRACTION
DISCARD_CRITICAL_FRACTION = PRESSURE_CRITICAL_FRACTION
MAX_ACHIEVABLE_GAP = 5
```

(Usages at lines 159/203/224/237 reference `CRITICAL_HP_FRACTION`, `DISCARD_CRITICAL_FRACTION`, `DEPOSIT_FULL_FRACTION`, `DISCARD_HIGH_FRACTION` — all still defined, unchanged values.)

- [ ] **Step 4: Migrate `strategy.py`**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`, add to the top import block (with the other `artifactsmmo_cli.ai.*` imports):

```python
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION
```

Then delete the local definition and its now-obsolete mirror comment (lines 45-47):

```python
# Mirrors RestoreHPGoal.CRITICAL_HP_FRACTION. Kept local so the tiers layer does
# not depend on goals/ (which P3c retires); P3c unifies the source.
CRITICAL_HP_FRACTION = 0.25
```

(Usage at line 616 references the module-level `CRITICAL_HP_FRACTION`, now the import.)

- [ ] **Step 5: Migrate `restore_hp.py` (class attr aliased to the import)**

In `src/artifactsmmo_cli/ai/goals/restore_hp.py`, add to the top import block:

```python
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION
```

Then change the class attribute (line 26) from:

```python
    CRITICAL_HP_FRACTION = 0.25
```

to:

```python
    CRITICAL_HP_FRACTION = CRITICAL_HP_FRACTION  # from thresholds (module global)
```

(In a class body the right-hand `CRITICAL_HP_FRACTION` resolves to the module global just imported, binding the class attribute to it; `self.CRITICAL_HP_FRACTION` at lines 31-ish keeps working with the same value 0.25.)

- [ ] **Step 6: Migrate `deposit_inventory.py` (class attr aliased to the import)**

In `src/artifactsmmo_cli/ai/goals/deposit_inventory.py`, add to the top import block:

```python
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
```

Then change the class attribute (line 33) from:

```python
    _RAMP_START = 0.85  # fraction used below which the goal is inactive
```

to:

```python
    _RAMP_START = PRESSURE_HIGH_FRACTION  # fraction used below which the goal is inactive
```

(Usages at lines 49/52 reference `self._RAMP_START`, unchanged value 0.85.)

- [ ] **Step 7: Migrate `unlock_bank.py` (bare literal)**

In `src/artifactsmmo_cli/ai/goals/unlock_bank.py`, add to the top import block:

```python
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
```

Then change line 32 from:

```python
            if used_fraction >= 0.85:
```

to:

```python
            if used_fraction >= PRESSURE_HIGH_FRACTION:
```

- [ ] **Step 8: Run the targeted suites**

Run: `uv run pytest tests/test_ai/test_tiers_guards.py tests/test_ai/test_goals.py tests/test_ai/test_craft_relief.py tests/test_ai/test_overstock.py -v`
Expected: PASS — values are identical, so all assertions hold.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/tiers/strategy.py src/artifactsmmo_cli/ai/goals/restore_hp.py src/artifactsmmo_cli/ai/goals/deposit_inventory.py src/artifactsmmo_cli/ai/goals/unlock_bank.py src/artifactsmmo_cli/ai/craft_relief.py
git commit -m "refactor(thresholds): route HP-critical + pressure-ladder consumers through thresholds"
```

---

### Task 4: Full suite + formal gate verification

**Files:** none (verification only; a commit only if a stray reference needs fixing)

**Interfaces:**
- Consumes: all prior tasks' deliverables.

- [ ] **Step 1: Confirm the bot is stopped (mutation rewrites src in place)**

Run: `pgrep -af "artifactsmmo play" || echo "BOT STOPPED — OK"`
Expected: `BOT STOPPED — OK`. If a bot is running, STOP and ask the user to stop it before proceeding.

- [ ] **Step 2: Full Python suite with coverage**

Run: `uv run pytest`
Expected: 0 failures, 0 errors, 0 warnings, 0 skipped, 100% coverage (including `thresholds.py`, covered by Task 1's test importing the module).

If any test referenced an old literal location and now fails, fix the reference (the value is unchanged), re-run, and commit with message `test(thresholds): update reference to consolidated constant`.

- [ ] **Step 3: Confirm `src/` is clean before and after the formal gate**

Run: `git status --porcelain src/`
Expected: empty (all `src/` changes committed). Record this — after the mutation phase, re-run and confirm it is STILL empty (mutate.py must restore every file it perturbs).

- [ ] **Step 4: Run the full formal gate**

Run: `cd formal && ./gate.sh`
Expected: all parts green — `lake build`, no-sorry/orphan check (the new `Formal.Extracted.Thresholds` is imported via `Formal.lean`, so it is not an orphan), axiom lint, manifest, contracts, differential (same numbers → green), mutation (inventory_caps anchors unchanged → all mutants still killed).

- [ ] **Step 5: Confirm `src/` survived mutation untouched**

Run: `git status --porcelain src/ && git diff src/`
Expected: both empty — mutation restored every file.

- [ ] **Step 6: Final no-op commit guard (only if Step 2 produced a fix)**

If Step 2 required a test-reference fix, ensure it is committed. Otherwise nothing to commit — Task 4 is verification.

---

## Self-Review

**Spec coverage:**
- Finding #2 (`CRITICAL_HP_FRACTION` ×3): Task 3 migrates `guards.py`, `strategy.py`, `restore_hp.py`; canonical in Task 1. ✅
- Finding #3 (pressure ladder `0.70/0.85/0.90/0.95`): `craft_relief` (Task 3 step 2), `guards` HIGH/DEPOSIT_FULL/CRITICAL (Task 3 step 3), `deposit_inventory._RAMP_START` (step 6), `unlock_bank` bare 0.85 (step 7), `inventory_caps` watermark (Task 2). ✅
- Out-of-scope `SELL_PRESSURE_FRACTION` / `BANK_EXPAND_FILL`: not touched by any task. ✅
- Extraction-source decision (user-chosen "move extraction source to thresholds"): Task 2 adds the `Thresholds` ModuleSpec, drops the watermark from `InventoryCaps`, regenerates both, imports into `Formal.lean`. ✅ This supersedes the spec's "import alias in inventory_caps" sketch (infeasible: the extractor requires an int-literal module-level assign).
- Lean copies unchanged / no value change: Global Constraints + Task 4 differential/mutation gate. ✅

**Placeholder scan:** No TBD/TODO/"add error handling"/"write tests for the above". Every code step shows the exact code. ✅

**Type consistency:** Constant names are identical across tasks: `PRESSURE_HIGH_NUM/DEN`, `PRESSURE_HIGH_FRACTION`, `DEPOSIT_FULL_FRACTION`, `PRESSURE_CRITICAL_FRACTION`, `CRAFT_RELIEF_FRACTION`, `CRITICAL_HP_FRACTION`. Aliased local names (`DISCARD_HIGH_FRACTION`, `DISCARD_CRITICAL_FRACTION`, `DISCARD_WATERMARK_NUM/DEN`, `_RAMP_START`) preserved with unchanged values. ✅

**Deviation from spec noted:** The spec's `thresholds.py` sketch used tuple assignments (`PRESSURE_HIGH_NUM, PRESSURE_HIGH_DEN = 17, 20`); this plan uses single-name assignments because the Lean extractor's `_extract_constants` only recognizes single-`Name` int-literal `ast.Assign` nodes.
