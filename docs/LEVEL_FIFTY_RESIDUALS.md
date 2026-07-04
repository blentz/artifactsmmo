# Level-50 reachability — the honest residual perimeter

**Status (2026-07-04, second pass): TWO hypothesis-free capstones.**

> `Formal.Liveness.UnconditionalDescent.ai_reaches_fifty_unconditional :`
> `∀ s, ∃ k, (cycleStepFN k s).level ≥ 50`
>
> `Formal.Liveness.DeferFaithful.ai_reaches_fifty_defer_faithful :`
> `∀ s, ∃ k, (cycleStepDN k s).level ≥ 50`

The second (`cycleStepD`, `docs/PLAN_residual_closure.md`) strengthens the
first on two of the perimeter rows below: the items-task defer-case is now
MODELLED (arming gated on the production-observed `itemsTaskDeferActive`;
inside the window the cycle pursues the items task and descends a `taskCycles`
slot) instead of over-approximated, and chore re-arming is WORST-CASED (every
fight re-arms ALL 8 chore latches — reach-50 still holds, because flags are
lex-dominated by the fight's level/xp descent).

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

| # | Gap | Where established | 2nd-pass status |
|---|-----|-------------------|-----------------|
| 1 | LIV-001 server xp curve | accepted axiom, openapi-cited (`Measure.lean`) | IRREDUCIBLE by design — the server owns the number; no offline data reproduces the curve. |
| 2 | Opaque chore Bools (`hasOverstockItems`, `selectBankDepositsNonempty`, `sellableInventoryNonempty`, `gearReviewFires`, `craftReliefFires`, `craftPotionsFires`, `recyclableSurplusNonempty`, `pendingItemsNonempty`, and now `itemsTaskDeferActive`) carry production's observed answers | AUDITED 2026-07-04: the O5.4 SELECT differential (`test_ladder_fires_diff.py`) DRIVES the production predicates behind the computable flags (overstock, deposit selection, sellable, pending, gear-review latch) against the oracle ladder, and pins the walk itself 23-slots-wide, mutation-enforced. The flags whose production computation reads live game data (`craftReliefFires`, `craftPotionsFires`, `itemsTaskDeferActive`) are observed inputs BY DESIGN — that is the model's interface, not a gap to close offline. |
| 3 | Items-task defer-case | `test_perceive_arm_diff.py` / `test_objectivestep_arming_diff.py` characterize | CLOSED IN-MODEL by `cycleStepD`: arming is gated on the defer window; inside it the cycle pursues the items task (`pursueTask` descends `taskCycles`; `acceptTask` remains unreachable — the gate implies an active phase, contradicting `acceptTaskFires`). |
| 4 | One-shot chore semantics | disclosure | SHARPENED twice: fight-direction re-arming WORST-CASED (`choreRearm`: every fight re-arms everything) AND mint-direction cross-arm MODELLED (Phase A1, `rearmOnMint`: the claim mint re-arms the 7 flags below `pendingFlag`, the completeTask reward mint re-arms everything — the formerly disclosed claim→overstock instance is now a theorem case, not a disclosure). Partial clears MODELLED too (Phase A2, `partialClear`): the three multi-batch chores (discard/deposit/sell) carry opaque DEBT counters — one apply either clears the latch (debt exhausted) or re-arms it and strictly decrements the debt, so production needing debt+1 batches is stepped through in-model; mints restore worst-case `DEBT_CAP`. Residual on this row is now only the OPAQUE debt/flag VALUES themselves (row 2's interface discipline) — no structural conservatism left. |

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
