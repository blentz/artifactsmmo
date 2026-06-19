import Formal.Liveness.CycleStepFLeveling

/-! # LevelFiftyReachableF — Workstream A Phase-1 Brick 3d-b capstone: level-50
reachability for the FAITHFUL cycle `cycleStepF`.

The faithful-cycle analog of `LevelFiftyReachableP.ai_reaches_level_fiftyP`. From
`GlobalInvariantsF` — the non-degeneracy invariants over the faithful trajectory
plus `hfightFiresF` (the fight-firing residual) — the faithful cycle `cycleStepF`
iterates finitely many times to `level ≥ 50`. Strong induction on the gap to 50,
wrapping `CycleStepFLeveling.level_advances_onceF` exactly as
`ai_reaches_level_fiftyP_aux` wraps `level_advances_onceP`.

This is the faithful capstone MODULO `hfightFiresF`. Brick 3d-c discharges
`hfightFiresF` from the REDUCED residual (`PressureBurst.nonPressureBlockers`, the
10 non-pressure blockers quiet i.o. — the 4 pressure-gated chores proven transient)
plus `Drainability.RuntimeInvariant`, via the bounded-burst argument. The net win
over `ai_reaches_level_fiftyP`: the faithful cycle MODELS inventory pressure (fights
fill the bag, chores drain it), so its `BlockersQuiet` residual is honestly the
10-blocker reduced one, not the unfaithful 14-blocker assumption the `cycleStepP`
capstone carried (which silently relied on chores never re-arming).

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.LevelFiftyReachableF

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration
open Formal.Liveness.CycleStepFLeveling

/-- Bundle of liveness hypotheses for the FAITHFUL cycle, holding at every state
    reachable from `s` via `cycleStepFN`. Mirrors `GlobalInvariantsP` with
    `cycleStepPN ↦ cycleStepFN`. The non-degeneracy fields are stated over the
    refreshed selection states `perceptionRefresh (cycleStepFN k s)` — the states
    the faithful cycle actually selects on. `hfightFiresF` is the fight-firing
    residual (Brick 3d-c reduces it to the 10-blocker residual + RuntimeInvariant). -/
structure GlobalInvariantsF (s : State) : Prop where
  hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) ≠ some .wait
  hex : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .taskExchange →
              (perceptionRefresh (cycleStepFN k s)).taskExchangeMinCoins > 0
  hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankExpand →
              (perceptionRefresh (cycleStepFN k s)).nextExpansionCost > 0
  hfightFiresF : hfightFiresF s

/-- If `GlobalInvariantsF` holds at `s`, it holds at `cycleStepFN m s` for any `m`.
    Mirrors `globalInvariants_stepP`, using the `cycleStepFN_add` prefix-shift. -/
theorem globalInvariants_stepF (s : State) (m : Nat)
    (h : GlobalInvariantsF s) :
    GlobalInvariantsF (cycleStepFN m s) := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro k
    rw [← cycleStepFN_add m k s]
    exact h.hnowait (m + k)
  · intro k hk
    rw [← cycleStepFN_add m k s] at hk
    rw [← cycleStepFN_add m k s]
    exact h.hex (m + k) hk
  · intro k hk
    rw [← cycleStepFN_add m k s] at hk
    rw [← cycleStepFN_add m k s]
    exact h.hbe (m + k) hk
  · intro N
    obtain ⟨j, hjN, hjFire⟩ := h.hfightFiresF (N + m)
    refine ⟨j - m, by omega, ?_⟩
    have hreindex : cycleStepFN (j - m) (cycleStepFN m s) = cycleStepFN j s := by
      rw [← cycleStepFN_add m (j - m) s]
      congr 1; omega
    rw [hreindex]
    exact hjFire

/-- Level strictly advances after some bounded number of faithful cycles. Wraps
    `level_advances_onceF` against `GlobalInvariantsF`. -/
theorem level_advances_onceF_inv (s : State)
    (hlvl : s.level < 50) (h : GlobalInvariantsF s) :
    ∃ k, (cycleStepFN k s).level > s.level :=
  level_advances_onceF s hlvl h.hfightFiresF

/-- Structural induction on the gap to 50. Mirrors `ai_reaches_level_fiftyP_aux`. -/
theorem ai_reaches_level_fiftyF_aux :
    ∀ (gap : Nat) (s : State), 50 - s.level = gap →
      GlobalInvariantsF s → ∃ k, (cycleStepFN k s).level ≥ 50 := by
  intro gap
  induction gap using Nat.strong_induction_on with
  | _ g ih =>
    intro s hgap h
    by_cases hlvl50 : s.level ≥ 50
    · exact ⟨0, by rw [cycleStepFN_zero]; exact hlvl50⟩
    · push Not at hlvl50
      obtain ⟨k₁, hk₁⟩ := level_advances_onceF_inv s hlvl50 h
      set s' := cycleStepFN k₁ s with hsdef
      have hs'_inv : GlobalInvariantsF s' := by
        rw [hsdef]; exact globalInvariants_stepF s k₁ h
      have hs'_gap_lt : 50 - s'.level < g := by
        rw [← hgap]; omega
      obtain ⟨k₂, hk₂⟩ := ih (50 - s'.level) hs'_gap_lt s' rfl hs'_inv
      refine ⟨k₁ + k₂, ?_⟩
      rw [cycleStepFN_add, ← hsdef]
      exact hk₂

/-- **Faithful capstone — level-50 reachability for the faithful cycle `cycleStepF`.**

From `GlobalInvariantsF s`, the faithful cycle iterates finitely many times to reach
`level ≥ 50`. The structural mirror of `LevelFiftyReachableP.ai_reaches_level_fiftyP`,
re-derived for `cycleStepF` (the engine is not reusable — same reason it wasn't for
`cycleStepP`).

This rests on `hfightFiresF` (inside `GlobalInvariantsF`) — which Brick 3d-c
discharges from the REDUCED 10-blocker residual + `RuntimeInvariant`, the honest
faithful residual that REPLACES the `cycleStepP` capstone's unfaithful 14-blocker
assumption. -/
theorem ai_reaches_level_fiftyF (s : State) (h : GlobalInvariantsF s) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  ai_reaches_level_fiftyF_aux (50 - s.level) s rfl h

end Formal.Liveness.LevelFiftyReachableF
