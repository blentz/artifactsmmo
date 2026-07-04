# Level-50 reachability — the honest residual perimeter

**Status (2026-07-04): the reach-50 capstone is HYPOTHESIS-FREE.**

> `Formal.Liveness.UnconditionalDescent.ai_reaches_fifty_unconditional :`
> `∀ s, ∃ k, (cycleStepFN k s).level ≥ 50`

Kernel axioms: `{propext, Classical.choice, Quot.sound, xpToNextLevel}` — the
standard set plus LIV-001 only (`xpToNextLevel_pos` is no longer even consumed).
No `hquiet`, no `hspawn`, no fairness residual, no `GlobalInvariants` bundle.
Audited in `LivenessAudit.lean`; per-cycle engine and slot design in
`Formal/Liveness/FMeasure.lean`; per-means descent in `BlockerDescent.lean`;
case-analysis closure in `UnconditionalDescent.lean`; plan + design record in
`docs/PLAN_l50_unconditional_descent.md`.

## How the 2026-06-18 residuals were discharged (history)

The original perimeter (see git history of this file) named three residuals.
Their fates:

1. **LIV-001 (`xpToNextLevel`)** — RETAINED, unchanged. The server owns the xp
   curve; the measure is well-founded over it. The one accepted, openapi-cited
   server axiom (per-axiom signoff per the liveness axiom split).
2. **WinnableAcrossBand** — DISCHARGED 2026-06-20 (`WinnableGrounded.
   winnableAcrossBand_grounded`): kernel-`decide`d per-level witness table over
   the live catalog with production-projected scalars, differential-pinned by
   `formal/diff/test_winnable_witness_diff.py`.
3. **BlockersQuiet / `hquiet`** — DISCHARGED 2026-07-04 by the unconditional
   descent, WITHOUT the refused false-story. The 2026-06-18 refusal rejected
   proving "chores quiet forever" from the model's never-re-arm gap (the real
   bot re-arms chores; the in-model quiescence held for a reason false of the
   system). The descent argument makes no quiescence claim at all: every
   below-50-selectable means — chores included — strictly descends the 13-slot
   `FMeasure`, so the well-founded engine needs no scheduling assumption. The
   theorem is about the MODEL; the informal sketch of why the shape carries to
   the real bot (fight-loot re-arms ride slot-1/2 descents; multi-step deposits
   drain `bankPressure` with flags equal) has one disclosed counter-instance —
   a claim-minted item re-arming overstock on a pending-only descent cycle —
   where real chore-burst finiteness is covered only by the offline perimeter
   below, not by the kernel proof. `hspawn` (`1 ≤ level`) fell out too — the
   proof consumes only the refresh's set value, not the level-indexed witness
   table.

## The remaining faithfulness perimeter (named, differential where possible)

These are NOT Lean hypotheses — the theorem has none. They are the points where
the model's fidelity to production is established offline rather than in-kernel:

| # | Gap | Where established |
|---|-----|-------------------|
| 1 | LIV-001 server xp curve | accepted axiom, openapi-cited (`Measure.lean`) |
| 2 | Opaque chore Bools (`hasOverstockItems`, `selectBankDepositsNonempty`, `sellableInventoryNonempty`, `gearReviewFires`, `craftReliefFires`, `craftPotionsFires`, `recyclableSurplusNonempty`, `pendingItemsNonempty`) carry production's observed answers with conservative one-shot clearing | per-flag diff harnesses (ProductionLadder docstring roster); O5.4 SELECT differential pins the ladder walk itself |
| 3 | Items-task defer-case: `perceptionRefresh` arms unconditionally below 50; production returns no fight in the long-haul items-task defer branch | `formal/diff/test_perceive_arm_diff.py` / `test_objectivestep_arming_diff.py` CHARACTERIZE the over-approximation |
| 4 | Single-action chore semantics: the model clears a chore latch in one apply; production may need several (e.g. multiple deposits). Multi-step real chores still descend — via `bankPressure` (inventory drains) with flags equal — so the descent shape survives; the model just books the progress on a different slot | disclosure only (no offline differential can replay multi-step chore composition) |

If any of these is wrong (e.g. a production chore that neither clears its latch
nor drains inventory, or an unbounded chore burst between fights), the model and
the real trajectory diverge at that point and the reach-50 guarantee does not
transfer — that divergence, observable as a live stall the model calls
impossible, is exactly the falsifiable surface this proof exposes.

## What this does NOT prove

* Nothing about wall-clock time or xp RATE — only eventual reachability under
  the model's cycle semantics.
* Nothing about levels beyond 50, boss content, or achievements.
* The `.fight` apply's `xp += 10` is the deliberate abstract projection
  (FakeServer + Lean lockstep) — see `feedback_combat_xp_projection_is_abstract`.
