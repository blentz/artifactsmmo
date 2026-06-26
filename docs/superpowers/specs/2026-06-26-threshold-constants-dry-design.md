# Threshold Constants DRY (Group A) — Design

**Status:** approved-pending-review (brainstorm 2026-06-26)
**Scope:** DRY backlog Group A — hoist the duplicated `CRITICAL_HP_FRACTION` and the
inventory space-pressure ladder constants to ONE neutral source. No value changes,
no behavior changes. (Findings #2, #3 from project_dry_backlog. #1/B and #4,#6/C are
separate cycles; #5 is by-design, not fixed.)

## Problem

Two threshold concepts are re-typed across modules and can silently drift:

1. **`CRITICAL_HP_FRACTION = 0.25`** in `goals/restore_hp.py:26`, `tiers/guards.py:25`,
   `tiers/strategy.py:47`. `strategy.py:46` even comments *"P3c unifies the source"* —
   a known, deferred dup, kept separate only to avoid a `goals/ → tiers/` import. The
   HP-critical *preempt trigger* (guards/strategy) and the *goal that satisfies it*
   (restore_hp) own separate copies; one edit desyncs them.

2. **The inventory space-pressure ladder** — a coordinated set of fullness rungs with a
   **proven** ordering invariant (`Formal.Liveness.MeansFiring` requires
   `DEPOSIT_FULL_FRACTION (0.90) > _RAMP_START (0.85)`), but each rung is re-typed:
   - `0.70` craft-relief: `craft_relief.py` (already single-source, re-imported by guards).
   - `0.85` HIGH watermark: `guards.py:35 DISCARD_HIGH_FRACTION`, `deposit_inventory.py:33
     _RAMP_START`, `inventory_caps.py DISCARD_WATERMARK` (as the exact rational 17/20),
     and a bare literal `0.85` in `unlock_bank.py:32`.
   - `0.90` DEPOSIT_FULL: `guards.py:28`.
   - `0.95` CRITICAL: `guards.py:36 DISCARD_CRITICAL_FRACTION`.

## Out of scope (intentionally NOT unified)

- **`SELL_PRESSURE_FRACTION = 0.85`** (`means.py:20`) — the sell-pressured/sell-idle
  *mode boundary*, a conceptually distinct threshold that merely equals 0.85 today.
  Keep its own constant (user decision: avoid coupling sell tuning to discard tuning).
- **`BANK_EXPAND_FILL = 0.95`** (`means.py:21`) — *bank* fullness, a different resource
  than bag pressure. Not part of this ladder; leave it.
- All Lean / proof constants — the Lean ladder model carries its OWN copies of these
  fractions. Since this change does NOT alter any VALUE, the Python↔Lean differentials
  stay green and no proof changes.

## Design — one neutral constants module

Create `src/artifactsmmo_cli/ai/thresholds.py`: a leaf module that imports nothing
from `goals/` or `tiers/` (so no cycle — the reason these were duplicated). It owns:

```python
CRITICAL_HP_FRACTION = 0.25
"""Below this hp/max_hp the HP-critical guard preempts and RestoreHPGoal satisfies it."""

# Inventory space-pressure ladder — strictly ascending. The proven invariant
# (Formal.Liveness.MeansFiring) requires CRAFT_RELIEF < HIGH < DEPOSIT_FULL < CRITICAL.
# Exposed as exact integer rationals (num/den) for the proven overstock core's
# float-free cross-multiplication; PRESSURE_*_FRACTION are the float views.
CRAFT_RELIEF_NUM, CRAFT_RELIEF_DEN = 14, 20   # 0.70
PRESSURE_HIGH_NUM, PRESSURE_HIGH_DEN = 17, 20  # 0.85
DEPOSIT_FULL_NUM, DEPOSIT_FULL_DEN = 18, 20    # 0.90
PRESSURE_CRITICAL_NUM, PRESSURE_CRITICAL_DEN = 19, 20  # 0.95

CRAFT_RELIEF_FRACTION = CRAFT_RELIEF_NUM / CRAFT_RELIEF_DEN
PRESSURE_HIGH_FRACTION = PRESSURE_HIGH_NUM / PRESSURE_HIGH_DEN
DEPOSIT_FULL_FRACTION = DEPOSIT_FULL_NUM / DEPOSIT_FULL_DEN
PRESSURE_CRITICAL_FRACTION = PRESSURE_CRITICAL_NUM / PRESSURE_CRITICAL_DEN
```

Then each consumer imports from `thresholds` and deletes its local copy:
- `goals/restore_hp.py`, `tiers/guards.py`, `tiers/strategy.py`: `CRITICAL_HP_FRACTION`.
- `tiers/guards.py`: keep the EXISTING module-level names as aliases bound to the
  imports — `DISCARD_HIGH_FRACTION = PRESSURE_HIGH_FRACTION`,
  `DEPOSIT_FULL_FRACTION = thresholds.DEPOSIT_FULL_FRACTION`,
  `DISCARD_CRITICAL_FRACTION = PRESSURE_CRITICAL_FRACTION`. Aliasing (not renaming)
  is the chosen low-churn path: these names are referenced by other modules / the
  differential harness, so the public name stays stable while the VALUE has exactly
  one definition. Same aliasing pattern wherever an existing name is widely referenced.
- `goals/deposit_inventory.py`: `_RAMP_START → PRESSURE_HIGH_FRACTION`.
- `inventory_caps.py`: `DISCARD_WATERMARK_NUM/DEN → PRESSURE_HIGH_NUM/DEN` (keeps the exact
  rational the proven `overstock_excess` core cross-multiplies; the value 17/20 is unchanged).
- `goals/unlock_bank.py`: bare `0.85 → PRESSURE_HIGH_FRACTION`.
- `craft_relief.py`: its `CRAFT_RELIEF_FRACTION` re-exported from `thresholds`.

## Data flow / invariant

The ladder ordering invariant now lives in one ascending block, so a future edit
can't silently invert `HIGH < DEPOSIT_FULL`. The proven Lean invariant is unaffected
(Lean has its own copy; values unchanged).

## Error handling / safety

- No value changes → no behavior change anywhere. The full gate (build, differential,
  mutation) must stay green by construction — the differentials feed the SAME numbers.
- `inventory_caps.py` is an extraction source; moving its watermark constants regenerates
  `Formal/Formal/Extracted/InventoryCaps.lean` line-refs (comment + sha only, defs
  byte-identical) — run `scripts/extract_lean.py` and commit, as in prior such edits.
- No import cycle: `thresholds.py` is a leaf (stdlib only).

## Testing

- Unit (`tests/test_ai/test_thresholds.py`): the ladder is strictly ascending
  (`CRAFT_RELIEF < HIGH < DEPOSIT_FULL < CRITICAL`); each `*_FRACTION == num/den`;
  `CRITICAL_HP_FRACTION == 0.25`.
- Regression: existing tests that reference the old constant names still pass (via aliases
  or updated refs). Full AI suite green; 100% coverage of `thresholds.py`.
- Formal: full `formal/gate.sh` green (no proof/value change; extraction regen only).

## Known limits / explicit non-goals

- This does NOT change any threshold value or any decision behavior — it is a pure
  consolidation. If a behavior tune is wanted, that is a separate change on the new
  single source.
- `SELL_PRESSURE_FRACTION` and `BANK_EXPAND_FILL` deliberately remain their own constants
  (distinct concepts), as decided.
