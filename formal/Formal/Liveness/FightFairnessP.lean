import Formal.Liveness.CycleStepP
import Formal.Liveness.FightFairness

/-! # FightFairnessP — Brick 4: `hfightFires` for the perception-refreshed cycle

`LevelFiftyReachable.GlobalInvariants.hfightFires` is the fight-firing obligation
the level-50 capstone consumes: infinitely often the SELECTED means is a
bank-bootstrap fight (`bankUnlock` / `reachUnlockLevel`) or a committed combat
objective (`objectiveStep` with `objectiveStepIsFight`). `FightFairness` reduced
its third disjunct to two residuals:

* `CombatPersistent` — the planner keeps a combat objective committed
  (`objectiveStepFires ∧ objectiveStepIsFight` at every step). An HONEST
  hypothesis there, opaque to the pure `cycleStep` mechanics.
* `BlockersQuietInfinitelyOften` — the 14 higher-priority means are quiet
  infinitely often. The pure scheduling/transience core.

This module restates `hfightFires` over the **refreshed** trajectory — where the
cycle SELECTS on `perceptionRefresh (cycleStepPN k s)` — and discharges it. The
NET WIN over `FightFairness`:

> **`CombatPersistent` is now PROVEN IN-MODEL** (Brick 3,
> `CycleStepP.cycleStepP_objective_armed_overturns_frontier`): every refreshed
> selection state below the cap has `objectiveStepFires = true ∧
> objectiveStepIsFight = true`, because each cycle begins with `perceptionRefresh`
> arming them. So the discharge consumes only the scheduling residual
> (`BlockersQuietBelowCapInfinitelyOftenP`), NOT a combat-persistence assumption.

`BlockersQuietInfinitelyOften` stays an honest hypothesis (its faithfulness to the
refreshing bot is the documented perception-abstraction gap, FightFairness.lean).
We do NOT prove it here.

Additive only. Axioms of the discharge theorem ⊆ {propext, Classical.choice,
Quot.sound, xpToNextLevel, xpToNextLevel_pos}.

Liveness namespace — Mathlib allowed (inherited via the imports).
-/

namespace Formal.Liveness.FightFairnessP

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.FightFairness

/-! ## Aggregate blocker-quiet bridge

Brick 1 / the PerceptionRefresh extension proved the ten per-slot
`perceptionRefresh_fires_<b>` bridges (plus the four bootstrap-window ones). Here
is their aggregate over the `objectiveStepBlockers` list: `perceptionRefresh`
leaves EVERY higher-than-objectiveStep fire unchanged, because it touches only the
two objective Bools and no blocker reads them. Cased on list membership so the per
-slot `rfl`-bridges discharge each branch. -/

/-- `perceptionRefresh` preserves the firing of every `objectiveStepBlockers`
means. Cases the membership and applies the per-slot Brick-1 bridge. -/
theorem perceptionRefresh_fires_blocker (s : State) (b : MeansKind)
    (hb : b ∈ objectiveStepBlockers) :
    fires b (perceptionRefresh s) = fires b s := by
  simp only [objectiveStepBlockers, List.mem_cons,
    List.not_mem_nil, or_false] at hb
  rcases hb with h | h | h | h | h | h | h | h | h | h | h | h | h | h <;> subst h
  · exact perceptionRefresh_fires_hpCritical s
  · exact perceptionRefresh_fires_restForCombat s
  · exact perceptionRefresh_fires_bankUnlock s
  · exact perceptionRefresh_fires_reachUnlockLevel s
  · exact perceptionRefresh_fires_discardCritical s
  · exact perceptionRefresh_fires_craftRelief s
  · exact perceptionRefresh_fires_depositFull s
  · exact perceptionRefresh_fires_discardHigh s
  · exact perceptionRefresh_fires_gearReview s
  · exact perceptionRefresh_fires_claimPending s
  · exact perceptionRefresh_fires_completeTask s
  · exact perceptionRefresh_fires_sellPressured s
  · exact perceptionRefresh_fires_lowYieldCancel s
  · exact perceptionRefresh_fires_taskCancel s

/-! ## The combat objective fires on the refreshed selection state

`fires .objectiveStep = objectiveStepFires` definitionally (ProductionLadder),
and `objectiveStepFires s = s.objectiveStepFires`. Below the cap Brick 3 arms
`(perceptionRefresh (cycleStepPN k s)).objectiveStepFires = true`, so the ladder's
objectiveStep fire is `true` on that selection state — unfolded exactly as
`BlockerSettled.lean` does. -/

/-- Below the cap, the refreshed selection state fires `objectiveStep`. Bridges
Brick 3's `cycleStepP_objectiveStepFires_armed` through the definitional
`fires .objectiveStep = objectiveStepFires = ·.objectiveStepFires`. -/
theorem objectiveStepFires_refreshed (s : State) (k : Nat)
    (h : (cycleStepPN k s).level < 50) :
    fires .objectiveStep (perceptionRefresh (cycleStepPN k s)) = true := by
  simp only [fires, ProductionLadder.objectiveStepFires]
  exact cycleStepP_objectiveStepFires_armed s k h

/-! ## The residual scheduling hypothesis, over the refreshed selection states

The capstone reads `perceptionRefresh (cycleStepPN k s)`, so the honest residual
is the `BlockersQuietInfinitelyOften` analog stated over those selection states,
carrying `level < 50` (the leveling regime where the combat objective is live).
`CombatPersistent` is NOT part of this — it is now in-model (Brick 3). -/

/-- **The scheduling residual for the refreshed cycle.** Infinitely often, the
refreshed selection state `perceptionRefresh (cycleStepPN k s)` is below the cap
AND none of the 14 `objectiveStepBlockers` fires on it. This is the sole runtime
obligation of `hfightFiresP`'s third disjunct — the `BlockersQuietInfinitelyOften`
variant adapted to the refreshed trajectory. It does NOT assume combat
persistence: the arming is proven in-model.

The `level < 50` conjunct is a DELIBERATE self-restriction, not a vacuity bug: it
makes the residual unsatisfiable once the trajectory reaches 50 — which is exactly
HARMLESS, because the consumer (`LifecycleBound7.lifecycle_progress_from_bounds_
proven`) is a proof-by-contradiction that assumes `level` never advances, so it
only ever consumes the `∀N` witnesses in the constant-`< 50` world. Do NOT
"fix" this into a bounded form — it mirrors the original `GlobalInvariants.
hfightFires` (`∀N`) exactly and carries no less information the consumer can use. -/
def BlockersQuietBelowCapInfinitelyOftenP (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
    (cycleStepPN k s).level < 50
    ∧ (∀ b ∈ objectiveStepBlockers, fires b (perceptionRefresh (cycleStepPN k s)) = false)

/-! ## `hfightFiresP` — the fight-firing disjunct over the refreshed cycle -/

/-- **`hfightFiresP`** — the `hfightFires` obligation restated over the
perception-refreshed trajectory. Mirrors `GlobalInvariants.hfightFires` with
`cycleStepN k s` replaced by the state the refreshed cycle actually SELECTS on,
`perceptionRefresh (cycleStepPN k s)`. -/
def hfightFiresP (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
      productionLadder (perceptionRefresh (cycleStepPN k s)) = some .bankUnlock
    ∨ productionLadder (perceptionRefresh (cycleStepPN k s)) = some .reachUnlockLevel
    ∨ (productionLadder (perceptionRefresh (cycleStepPN k s)) = some .objectiveStep
        ∧ (perceptionRefresh (cycleStepPN k s)).objectiveStepIsFight = true)

/-! ## The discharge — the objective-committed third disjunct, IN-MODEL -/

/-- **Brick-4 capstone — `hfightFiresP` from the scheduling residual alone.**

Given `BlockersQuietBelowCapInfinitelyOftenP s` (the sole remaining runtime
obligation — the 14 higher means quiet infinitely often, in the leveling regime),
`hfightFiresP s` holds, discharging the THIRD disjunct
(`objectiveStep ∧ objectiveStepIsFight`) for every chosen position.

**The key in-model win.** Unlike `FightFairness.hfightFires_of_combat_scheduled`,
which assumed `CombatPersistent` (the planner keeps a combat objective committed),
this theorem PROVES the persistence in-model from Brick 3: at the chosen position
`k` (where `level < 50`),

* `fires .objectiveStep (perceptionRefresh (cycleStepPN k s)) = true` comes from
  `objectiveStepFires_refreshed` (i.e. `cycleStepP_objectiveStepFires_armed` —
  `perceptionRefresh` re-armed the objective at the head of the cycle); and
* `(perceptionRefresh (cycleStepPN k s)).objectiveStepIsFight = true` comes from
  `cycleStepP_objectiveStepIsFight_armed`.

Combined with the quiet blockers (the hypothesis) via
`FightFairness.productionLadder_eq_objectiveStep_of_unblocked`, the ladder SELECTS
`objectiveStep` on the refreshed selection state — so the cycle fights. The OLD
`CombatPersistent` / `hperc` obligation is GONE from the assumption set; only the
scheduling residual `BlockersQuietBelowCapInfinitelyOftenP` remains. -/
theorem hfightFiresP_of_blockers_quiet (s : State)
    (hq : BlockersQuietBelowCapInfinitelyOftenP s) :
    hfightFiresP s := by
  intro N
  obtain ⟨k, hkN, hlt, hquiet⟩ := hq N
  refine ⟨k, hkN, Or.inr (Or.inr ⟨?_, ?_⟩)⟩
  · -- The ladder selects objectiveStep: combat objective fires, all blockers quiet.
    exact productionLadder_eq_objectiveStep_of_unblocked (perceptionRefresh (cycleStepPN k s))
      (objectiveStepFires_refreshed s k hlt) hquiet
  · -- The committed objective is combat-typed — Brick-3 arming (in-model).
    exact cycleStepP_objectiveStepIsFight_armed s k hlt

/-! ## Convenience: the residual carried from the un-refreshed selection states

Sometimes the scheduling argument is easier to state over `cycleStepPN k s`
(pre-refresh). The blocker-fire bridge `perceptionRefresh_fires_blocker` carries
such a witness to the refreshed form, so `hfightFiresP` follows from the
un-refreshed variant too. -/

/-- The `BlockersQuietBelowCapInfinitelyOftenP` residual, stated over the
un-refreshed states `cycleStepPN k s`. Equivalent via the blocker-fire bridge. -/
def BlockersQuietBelowCapInfinitelyOften (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
    (cycleStepPN k s).level < 50
    ∧ (∀ b ∈ objectiveStepBlockers, fires b (cycleStepPN k s) = false)

/-- The un-refreshed residual implies the refreshed one (carry each blocker-quiet
fact across `perceptionRefresh` via `perceptionRefresh_fires_blocker`). -/
theorem blockersQuietP_of_blockersQuiet (s : State)
    (h : BlockersQuietBelowCapInfinitelyOften s) :
    BlockersQuietBelowCapInfinitelyOftenP s := by
  intro N
  obtain ⟨k, hkN, hlt, hquiet⟩ := h N
  refine ⟨k, hkN, hlt, ?_⟩
  intro b hb
  rw [perceptionRefresh_fires_blocker (cycleStepPN k s) b hb]
  exact hquiet b hb

/-- **`hfightFiresP` from the un-refreshed scheduling residual.** Convenience
composition: the un-refreshed `BlockersQuietBelowCapInfinitelyOften` carries to
the refreshed form and discharges `hfightFiresP`. Same in-model win — combat
persistence is Brick-3-proven, not assumed. -/
theorem hfightFiresP_of_blockers_quiet_unrefreshed (s : State)
    (h : BlockersQuietBelowCapInfinitelyOften s) :
    hfightFiresP s :=
  hfightFiresP_of_blockers_quiet s (blockersQuietP_of_blockersQuiet s h)

end Formal.Liveness.FightFairnessP
