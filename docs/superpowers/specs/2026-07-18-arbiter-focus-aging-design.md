# Design: Arbiter anti-starvation via deterministic focus-aging

Date: 2026-07-18
Status: APPROVED (design) — pending spec review, then implementation plan
Author: investigation from `play-trace-Robby.jsonl` (level 15 run)

## Problem

The strategy arbiter commits to a single highest-gain gear root and pursues it
exclusively. When that root is drop-gated and stuck, achievable lower-value roots
starve indefinitely.

### Evidence (Robby, level 15)

- `#18863 cyc3268 Craft(iron_ring×1)` → `#18864 Equip(iron_ring->ring1_slot)`.
  One iron_ring crafted and equipped into `ring1_slot`. The second copy for the
  empty `ring2_slot` was never crafted.
- The `ObtainItem(iron_ring, slot='ring2_slot')` root is present in **7111
  cycles**, `score=2000`, and is **chosen 0 times**.
- The dual-ring carve-out is NOT the bug: the ring2 root is emitted, plannable,
  and scored correctly.
- Root cause: at cyc3270 the ranking is
  `wolf_ears->helmet_slot` = **18100**, `iron_ring->ring2_slot` = **2000**,
  `satchel->bag_slot` = 15. The arbiter picks the max-gain root.
- `wolf_ears->helmet_slot` is **stuck**: from the ring1 equip to end of trace
  (931 cycles) it is chosen **931/931 = 100%** of the time and **0 wolf_ears are
  ever obtained** (repeated `Fight(wolf)`, healing, resting, no drop). The helmet
  still wears `iron_helm` from cyc28.
- `select_pure` re-commits `wolf_ears` every cycle because a `Fight(wolf)` plan is
  always found — the stuck root never registers as failing. There is no
  progress counter and no stall-release in the arbiter today.

This is priority-inversion starvation: an unachievable high-value root
monopolizes the single-root arbiter and blocks an immediately-craftable
low-value root.

### Why current tests miss it

- `audit/craft_completeness.py:census_state` builds the census character by
  pre-filling BOTH ring slots from `near_term_gear` (`_slot_assignments` assigns
  the best code to `ring1_slot` AND `ring2_slot`) and equipping the whole loadout
  dict by fiat with `derive_combat_stats=True`. It never drives the sequential
  craft→equip→craft-again planner path, so "one ring crafted, second never" is
  invisible — the census starts from the answer.
- `test_progression_coverage_gaps.py::test_second_ring_is_a_craft_target_when_same_ring_worn`
  uses a single-item catalog → uncontested argmax → ring2 wins trivially.
- `test_strategy_driver.py::test_arbiter_equips_second_ring_into_empty_slot`
  pre-seeds a spare `copper_ring` in inventory → it tests EQUIP of an owned spare,
  not obtain-under-competition.
- No test exercises: ring1 filled + a competing higher-value (and stuck) gear
  root → assert the 2nd ring is still eventually realized. No coverage of arbiter
  starvation of an achievable low-value root.

## Goal

Let a stuck/drop-gated root farm hard for a bounded window, then gradually share
cycles with other reachable roots (other gear, task-pursuit for task-gated gear,
material pre-gathering), without ever permanently abandoning the drop root. Reset
to full-priority farming when real progress happens. Fully deterministic — the
arbiter is pinned by Lean models and differential oracles.

## Design

### §1 Focus ledger (new arbiter state)

Add `focus: dict[str, int]` to `StrategyArbiter`, persisted across cycles
alongside `_committed_repr` and `_cycle`. The key is the root repr.

- `+1` for the root that is the committed focus each cycle.
- Alternatives remain at low focus until they receive interleave cycles.
- Zeroed by the reset triggers in §4.

The ledger is part of arbiter state and MUST be reflected in the Lean model and
the differential oracle inputs so `select_pure` remains a pure function of state.

### §2 Falloff curve

`f(level)` multiplies a root's base gain before selection:

```
f(level) = 1.0                        level ≤ 10       # full-weight farm window
         = smooth decay 1.0 → FLOOR   10 < level ≤ 110 # decay over 100 iters
         = FLOOR (> 0)                level > 110       # never fully abandoned
```

Calibrated so that at `level = 60` the decayed drop-root score is approximately
equal to the next-best craftable-now root's score — the crossover where the
deterministic interleave (§3) splits cycles ~1:1. `FLOOR > 0` guarantees the
drop root keeps a nonzero share, so if the drop finally lands it resumes.

The curve is a pure function `f: int → rational` (exact arithmetic, no float in
the decision path, per the mechanical-extraction rule). Shape and constants are
tunable (see Open Constants).

### §3 Deterministic weighted interleave

Replace the single hard argmax in `gear_target_pick` / `select_pure` with a
deterministic ratio scheduler (Bresenham / error-diffusion) keyed off `_cycle`,
over the roots' effective weights `base × f(focus)`:

- Equal weights → strict alternation (`A,B,A,B,…`).
- Skewed weights → proportional interleave.
- Deterministic and reproducible: identical decisions on every replay for the
  same state sequence. No RNG, no wall-clock.

**Plan-leg atomicity.** The scheduler yields to a different root only at plan-leg
boundaries — never mid gather→craft chain. Sticky commitment already provides
these safe points; an in-flight multi-step craft is completed before the focus
can switch. This prevents thrash (abandoning a half-gathered craft).

### §4 Reset triggers

When either event occurs, zero the focus ledger so the drop root returns to full
weight (a fresh farm window):

- character `level` increased since the previous cycle, or
- a **non-consumable equippable** item was successfully crafted this cycle
  (consumables/potions disqualified).

Rationale: both events change the gear landscape (new gear unlocked; a slot just
progressed), so the "stuck" penalty should not persist across genuine progression.
This yields the intended rhythm: farm drop-root at full weight → decay →
interleave and craft other gear → that craft resets → farm again. Progress spirals.

### §5 Rotation pool

All reachable roots age together and may take interleave cycles as the stuck root
decays:

- other gear roots (the 2nd `iron_ring` for `ring2_slot`, shields, boots, …) —
  already ranked; the falloff lets the next-best surface;
- task-pursuit for task-gated gear (e.g. `satchel`) — may require promoting
  `PursueTask` to a first-class ageable root rather than discretionary-only;
- material pre-gathering toward other attainable items in other slots.

## Formal + test work (lockstep, mandatory)

Per the project's formal-development gate, behavior changes ship with Lean and
oracle updates in the same change.

- `formal/Formal/ArbiterSelect.lean`, `formal/Formal/ProgressionTree.lean`:
  argmax → weighted-interleave over `base × f(focus)`. New theorems:
  - falloff monotonicity (higher focus ⇒ weight non-increasing);
  - **no-permanent-starvation**: every reachable root receives a committed cycle
    within a bounded window;
  - determinism of the interleave scheduler;
  - reset correctness (the two triggers zero the ledger).
- Differential oracles extended with the focus-ledger state:
  `formal/diff/test_arbiter_select_diff.py`, `test_decide_key_diff.py`,
  `test_strategy_traversal_diff.py` (and `test_upgrade_selection_diff.py` if the
  gear pick surface changes). Refresh mutation anchors (`formal/diff/mutate.py`).
- **Repro test (the missing coverage):** filled `ring1_slot` + a stuck
  `wolf_ears` root (0 drops) + a craftable `iron_ring` → assert `ring2_slot` is
  built within the falloff window, and that building it fires a reset of the
  drop-root focus.
- **Census gap fix:** add a sequential-realization check that drives the planner
  to craft a duplicate ring, rather than `census_state` pre-filling both ring
  slots by fiat.

## Open constants (tunable; defaults proposed)

- Curve shape: linear vs smoothstep over `(10, 110]`. Default: smoothstep.
- `FLOOR`: the minimum multiplier (> 0). Default TBD during implementation
  (must leave the drop-root a nonzero interleave share).
- Iter anchors: full-weight ≤ 10, crossover ≈ 60, floor > 110 (as specified).
- Interleave granularity: yield at plan-leg boundaries (fixed, not tunable).

## Out of scope

- Re-valuing `wolf_ears` (whether 18100 vs 2000 is itself a mis-valuation). The
  falloff makes valuation errors non-fatal (they no longer cause permanent
  starvation) but does not correct them. Track separately if desired.
- Genuine randomness / seeded PRNG selection (rejected: breaks the argmax proofs
  and oracle replay for no behavioral gain over the deterministic interleave).
