# Lean 4 Formal Verification of AI Decision Logic (bug-finding expansion)

**Date:** 2026-05-27
**Status:** Approved direction. Extends the 14-component pure-logic suite (`docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md`) into the AI's decision/orchestration logic, with the explicit goal of **finding bugs** the team believes exist there.

## Goal

Prove **intent properties** of the AI's decision logic — the predicates, rankings, priority orderings, learning math, and state-transition decisions previously scoped out as "impure." Where a proof of an intent property **won't close** because the property is genuinely false of the (faithfully-modeled) code, that is a **bug located**; fix it (smallest correct change), re-prove green. The 14 pure components already proven establish the harness and gate.

## Why this finds bugs (vs the prior "confirm" work)

The 14 prior components proved intent properties that *held* — the code was correct. The decision logic is where complexity concentrates (multi-key rankings, priority lattices, learned-yield blending, commitment state). The bug-finding mechanism:

> Faithful Lean model of the real Python + an **independent intent theorem** the code *should* satisfy. If the code is buggy, the intent theorem **cannot be proved** (the faithful model violates it). The differential test (Lean def vs real Python over random inputs) guarantees the model is faithful, so an unprovable intent theorem is a real bug, not a modeling artifact.

This is the inverse of self-consistency: we do not prove "the code does what it does" (always true); we prove "the code does what it *should*," which fails on buggy code.

## Bug policy (decided)

**Fix Python, then prove.** When an intent theorem can't close because the property is false: confirm it's a genuine bug (not an unfaithful model) via the differential test / a concrete counterexample input, fix the Python with the smallest correct change, re-prove the intent theorem green, differential-test confirms. **Behavioral/tuning changes** (priority constants, thresholds, anything that alters intended strategy rather than fixing a clear correctness defect) are **flagged and confirmed before changing** — those are not unilateral fixes.

## Architecture

Extend `formal/` exactly as the 14 components did. Per decision-logic target:
1. **Extract the pure core** — minimal Python refactor to expose the decision as a pure function of its inputs (lift `LearningStore`/clock reads to parameters where they're queried inline; the I/O caller passes the fetched scalars). The refactor must preserve behavior (existing tests stay green); on tangled targets the extraction itself surfaces bugs.
2. **Faithful Lean model** (`formal/Formal/<C>.lean`) — computable `def` mirroring the extracted core. Order-preserving integer surrogates for float scoring/weights (comparison/argmax-only uses); exact integer arithmetic where reducible; disclose any abstracted float in the header.
3. **Intent theorem(s)** — the independent "should" property. Pin in `Contracts.lean` (statement-strength gate), list role in `Manifest.lean`, audit in `Audit.lean`.
4. **Differential test** (`formal/diff/test_<C>_diff.py`) — real Python core vs Lean oracle over ≥200 random inputs; guarantees model faithfulness (and re-confirms the fix).
5. **Mutations** — ≥3 per target in `mutate.py`; each killed.
6. Through `./formal/gate.sh` (kernel build · axiom lint · manifest · Contracts · differential · mutation). No `sorry`, axioms ⊆ {propext, Classical.choice, Quot.sound}.

## Out of scope (irreducibly impure — differential-test only, never "proven")

`actions/*.execute` (API calls), `learning/store` (SQLite), the `player` loop's I/O / clock / RNG, `game_data` loader, `event_availability` clock. Their pure decision islands are extracted and proven; the I/O shell is the small untrusted boundary, exercised only by differential tests.

## Phase 1 — the 4 suspected bugs (this cycle)

Ordered suspected-bugs-first to validate the thesis fast. Each: extract → model → intent theorem → (likely fix) → prove → differential.

### 1. `dynamic_priority.learned_priority_bonus` — survival-floor safety (STRONGLY suspected bug)
`bonus = scalar_yield · weight(5.0) · confidence(≤1)` — **unbounded above**. Docstring claims the base preserves the survival floor (RestoreHP=80, UnlockBank=70 must dominate), but the bonus is added on top with no cap.
**Intent theorem:** a discretionary goal's effective priority (base + bonus) stays **strictly below the survival floor (70)** — equivalently, the bonus is bounded so it can never reorder a discretionary goal above RestoreHP/UnlockBank.
**Expected outcome:** *unprovable as written* (unbounded bonus) → **fix**: cap the bonus (e.g. `min(bonus, FLOOR − MAX_DISCRETIONARY_BASE − 1)`) or exclude survival goals from the bonus / clamp discretionary effective priority below the floor. Re-prove the bound. (The exact cap value is a tuning decision — flag before committing the number; the *existence* of a bound is the correctness fix.)

### 2. `meta_goal.owned_count` — double-count (conditional bug)
`count = inventory.get(code) + bank.get(code) + (1 if equipped)`.
**Intent theorem:** `owned_count = |inventory[code]| + |bank[code]| + equipped(code)` is the true total **iff** inventory/bank/equipped are disjoint counts (the API keeps equipped items out of `inventory`). Model the three stores; prove the formula equals the true total **under the disjointness invariant**, and make the invariant explicit.
**Outcome:** if the differential test against real WorldState data shows an equipped code never appears in `inventory` → prove correct (invariant holds, document it). If it can → double-count **bug** → fix (don't add +1 when the code is already in inventory, or count equipment separately). The differential resolves it.

### 3. `progression._best_by_value` + craftable/inventory ranking keys — the tangle
**Intent theorems:**
- `_best_by_value(inv, craft)` returns the **strictly-higher-value** pick (`value(result) ≥ max(value(inv), value(craft))`), tie → inventory; never the strictly-worse item (fixes the documented wooden_stick regression).
- the craftable key `(relevant_tool, fills_empty, value, −craft_level, code)` and the inventory key `(relevant, value, level, code)` are each a **strict total order** ⇒ selection is deterministic, independent of dict iteration order.
- **commitment idempotence:** with `committed_target` set, `find_upgrade_target` returns *exactly* the commitment and never substitutes another equippable (the fishing_net-from-shield-materials bug class).
**Outcome:** extraction of this dense logic is itself the test; any non-total key or strictly-worse return = bug → fix.

### 4. `scalarizer.scalar_yield` + coin-inversion
**Intent theorems:**
- `scalar_yield` is **non-decreasing in each Yield component** (char_xp, each skill_xp, gold, tasks_coins) given non-negative weights/values — a learned signal must not *decrease* when a goal yields strictly more.
- **relevant-tool weight dominance:** an active-skill XP unit scores ≥ a baseline-skill XP unit (`2.0 ≥ 0.2`) — the scalar prefers the right skill.
- **coin-inversion identity:** `coins_spent = received − delta_inv_used` is the correct solution of the recorded `delta = received − coins_spent` (no sign error); and the `coins_spent ≤ 0 → skip` guard is sound.
**Outcome:** prove the algebra + monotonicity; a sign error or non-monotone weight = bug → fix.

Refactor note: `scalarizer`/`dynamic_priority`/`progression` query `store`/`game_data` for scalars (yield, coin-value, active-skills) — lift those to parameters so the core is a pure function; the differential test supplies them from the real objects.

## Later phases (out of scope for the Phase-1 plan)

Systematic sweep: `tiers/strategy.decide` ranking total-order + `_learned_blend` convexity; `guards`/`means` no-stall + non-contradiction; `discard_overstock` constant ordering; the **cross-goal priority lattice** (numeric goal priorities vs `GUARD_ORDER` vs means bands must agree); `task_decision` monotonicity + combat⇒PIVOT; `strategy_driver` map exhaustiveness; `personality.weighted_remaining`; `projections.low_yield_cancel_fires`. Each its own spec→plan→build cycle.

## Honest risks
- Some intent theorems will reveal **behavioral/tuning** questions, not clean bugs (e.g. the dynamic_priority cap *value*) — those are flagged, not auto-fixed.
- Extraction refactors touch production code; existing tests (100% coverage) must stay green — the refactor is behavior-preserving, the bug-fix is the only intended behavior change, called out per commit.
- `progression` is genuinely tangled; if extraction can't preserve behavior cleanly, that itself is a finding to report.
