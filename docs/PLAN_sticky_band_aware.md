# PLAN: band-aware arbiter sticky-commitment

## Problem (root cause, trace-confirmed)

`play-trace-Robby.jsonl` run 2026-07-01 12:01. Robby froze at char level 4,
grinding `GatherMaterials(copper_ring)` for 35+ cycles while `chosen_root` was
`ReachCharLevel(6)` and its step goal `GrindCharacterXP(green_slime)` was
plannable + servable every cycle.

Mechanism: `select_pure` (src/artifactsmmo_cli/ai/arbiter_select.py:69-85) sticky
short-circuit returns the committed candidate BEFORE the ordered walk whenever the
committed candidate is present + plannable + unsatisfied + unsuppressed + no guard
precedes. The commit `GatherMaterials(copper_ring)` was set at cyc2 during a
transient window (real `fight_lost` on green_slime → 2 cycles of ReachCharLevel
non-servability). From cyc3 on, green_slime was winnable again but the stale
lower-priority commit kept jumping ahead of the higher-priority objective step,
which was never even tried (absent from `goals_tried` despite being `memo_exempt`).

Only a **guard** preempts the sticky commit today. A plannable lower-priority
committed means wins indefinitely.

## Fix

Sticky commitment may defend the committed goal against equal-or-lower priority
competitors (anti-thrash, e.g. finish the PursueTask you started rather than flip
to AcceptTask) but must NEVER preempt a **higher-priority (lower band index)**
candidate. Generalize the existing `guardPrecedes` (guards = band 0) block to
`lowerBandPrecedes`: block the sticky short-circuit when any candidate of a
STRICTLY LOWER band precedes the committed candidate.

Candidate bands (from `_build_candidates` order):
0 guards · 1 collect-reward · 2 top objective step · 3 fallback steps ·
4 discretionary. Guards remain a special case of band 0, so `guardPrecedes`
theorems are preserved; `lowerBandPrecedes` adds the means-band ordering.

In the bug: committed copper_ring is a band-3 fallback step; the top step
`GrindCharacterXP` is band 2. Band-2 precedes band-3 committed → sticky blocked
→ walk runs → `GrindCharacterXP` wins. Frozen char un-freezes.

### Modeling choice — band is a Candidate FIELD (revised)

`select_pure` is mechanically EXTRACTED to `formal/Formal/Extracted/ArbiterSelect.lean`
by `scripts/extract_lean.py` and bridged to the hand model via
`arbiter_select_bridge` (Bridges2.lean). Adding `band: int` to the Python
`Candidate` dataclass auto-propagates a `band : Int` field to the extracted
`Candidate` structure on re-extraction. For the bridge (extracted ≡ hand) to stay
provable, the HAND model `Candidate` must mirror it → band is a **field**, not a
closure. Cost: every `⟨id, isMeans⟩` literal in ArbiterSelect.lean becomes
`⟨id, isMeans, band⟩` (mechanical proof repair). This keeps all three layers
(Python ≡ extracted ≡ hand) structurally identical, which is what makes the
bridge cheap.

Band values (set in `_build_candidates`): 0 guards · 1 collect · 2 top step ·
3 fallback steps · 4 discretionary. `guardPrecedes` (structural, isMeans-based)
is retained unchanged so guard theorems need no repair; `lowerBandPrecedes`
(band-based) is added and OR-ed into the sticky block.

### Full formal surface (do NOT miss any)

Python `arbiter_select.py` + `strategy_driver._build_candidates` →
re-extract → `Extracted/ArbiterSelect.lean` → repair `arbiter_select_bridge`
(Bridges2.lean) → hand model `ArbiterSelect.lean` (defs+theorems+witnesses) →
`Oracle.lean` (band input parse) → `oracle_client`/`test_arbiter_select_diff.py`
(band generation + freeze regression) → `Contracts.lean` + `Manifest.lean` →
unit regression test → `gate.sh`.

## Theorem roles (formal/Formal/ArbiterSelect.lean)

Keep all existing roles green. Add:

- `select_pure_no_sticky_preempt_lower_band` (NEW, safety): if a plannable,
  non-suppressed, non-satisfied candidate of strictly-lower band precedes the
  committed candidate, then `selectPure` does not return the committed candidate
  via the sticky path — it returns what the ordered walk returns. This is the
  anti-freeze contract with teeth (a mutant that keeps the old guard-only block
  must fail the differential/mutation).
- Preserve `select_pure_guard_wins`, `select_pure_any_plannable_guard_wins`,
  `select_pure_sticky_idempotent`, `select_pure_no_commitment_is_walk`.
- `Contracts.lean` pin for the new theorem; `Manifest.lean` roster entry.

## Work breakdown

1. [Phase 1] Lean: add `band` closure, `lowerBandPrecedes`, update `stickyOutcome`
   + `selectPure`; repair existing proofs; prove new safety role. Manifest +
   Contracts.
2. [Phase 2] Python: add `band: int` to `Candidate` (dataclass, prod-side only —
   NOT the Lean struct), thread band through `select_pure` sticky check; set bands
   in `_build_candidates`.
3. [Phase 3] Oracle + `test_arbiter_select_diff.py`: generate band per id; assert
   real `select_pure` ≡ oracle over random band-tagged candidate lists. Mutation:
   the old guard-only rule must be a killed mutant.
4. [Phase 4] Adversarial review: is the new theorem satisfiable + non-vacuous?
   does it fire on the actual reachable band layout? no rigged diff.
5. [Phase 5] Unit tests: regression test reproducing the copper_ring freeze
   (committed lower-band + plannable higher-band step ⇒ step wins). ≥ coverage gate.

## Status: NOT STARTED (2026-07-01)
