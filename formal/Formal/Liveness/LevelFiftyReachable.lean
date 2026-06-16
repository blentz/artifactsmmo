import Formal.Liveness.CumulativeProgress
import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.LifecycleBound7
import Formal.Liveness.CycleStep
import Formal.Liveness.Measure
import Formal.Liveness.ProductionLadder
import Formal.Liveness.MeansKind
import Mathlib.Tactic

/-! # Tier 5 capstone — level-50 reachability from spawn (Phase 25)

User's meta-goal mandate:
> "given the artifactsmmo openapi.spec and our project design specs as
> inputs, we have built an AI bot as output capable of interfacing with
> the APIs in provably valid ways for all possible encounterable scenarios."

Tier 5 closure: starting from any state with `level < 50` and the
standard liveness invariants holding globally, the planner iterates
`cycleStep` finitely many times to reach `level ≥ 50`.

The proof iterates `cumulative_progress_under_no_wait` (Phase 23c-3c
unrestricted headline) up to 49 times, composing K's.

NO new axioms. Pure composition of:
- Phase 22a's cycleStep.
- Phase 23a's cycleStepN (iterated apply).
- Phase 23c-3c's cumulative_progress_under_no_wait headline.

Honest scope disclosure:
- `globalInvariants` bundles the no-wait + non-degeneracy + perception
  hypotheses across ALL iterations starting from s. Establishing this
  for a real spawn state is the runtime obligation; the proof is
  structural composition.
- The K bound is existential, not closed-form (each cumulative_progress
  invocation produces an unbounded ∃ k). A computable upper bound
  K_LEVEL_50_BOUND = 49 × max_per_cycle_K could be derived from LIV-003
  small axioms (lowYieldSampleThreshold + taskPoolFinite); deferred to
  a future phase. The existential here suffices for the structural
  reachability claim — the planner is PROVABLY CAPABLE OF reaching
  level 50, modulo planner-budget tuning.
-/

namespace Formal.Liveness.LevelFiftyReachable

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.LIV003Decomposition

/-! ## Global invariants -/

/-- Bundle of liveness hypotheses that must hold at EVERY state reachable
    from `s` via `cycleStepN`. Used to iterate `cumulative_progress_under_no_wait`
    without re-establishing hypotheses at each step. -/
structure GlobalInvariants (s : State) : Prop where
  hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait
  hex : ∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
              (cycleStepN k s).taskExchangeMinCoins > 0
  hbe : ∀ k, productionLadder (cycleStepN k s) = some .bankExpand →
              (cycleStepN k s).nextExpansionCost > 0
  -- NOTE (2026-06-15): the former `hperc` perception field was REMOVED — it was
  -- never consumed by the reachability proof (it reached `lifecycle_progress_
  -- from_bounds_proven` only as an underscore-bound, unused parameter) and is not
  -- unconditionally true (bankUnlock can fire at level ≥ 50). Dropping it
  -- STRENGTHENS the capstone (one fewer runtime obligation).
  -- Item 1g-B cascade: post-XP=0 fix, trajectory must contain
  -- unbounded .fight firings (via .bankUnlock or .reachUnlockLevel)
  -- for level advance to be possible at all. Production observes
  -- this: the planner ALWAYS pursues bank-unlock and skill-level
  -- goals when active.
  hfightFires : ∀ N, ∃ k ≥ N,
      productionLadder (cycleStepN k s) = some .bankUnlock
      ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel

/-! ## GlobalInvariants preservation -/

/-- If `GlobalInvariants` holds at `s`, it also holds at `cycleStepN k s`
    for any k. Proven by composing hypotheses via `cycleStepN_add`. -/
theorem globalInvariants_step (s : State) (m : Nat)
    (h : GlobalInvariants s) :
    GlobalInvariants (cycleStepN m s) := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro k
    -- productionLadder (cycleStepN k (cycleStepN m s)) ≠ some .wait
    rw [← cycleStepN_add m k s]
    exact h.hnowait (m + k)
  · intro k hk
    rw [← cycleStepN_add m k s] at hk
    rw [← cycleStepN_add m k s]
    exact h.hex (m + k) hk
  · intro k hk
    rw [← cycleStepN_add m k s] at hk
    rw [← cycleStepN_add m k s]
    exact h.hbe (m + k) hk
  · -- Item 1g-B cascade: re-establish hfightFires via prefix shift.
    -- ∀ N, ∃ k ≥ N, fight fires at cycleStepN k (cycleStepN m s).
    -- Use h.hfightFires (N + m) to get j ≥ N+m. Set k := j - m.
    intro N
    obtain ⟨j, hjN, hjFire⟩ := h.hfightFires (N + m)
    refine ⟨j - m, by omega, ?_⟩
    have hreindex : cycleStepN (j - m) (cycleStepN m s) = cycleStepN j s := by
      rw [← cycleStepN_add m (j - m) s]
      congr 1
      omega
    rw [hreindex]
    exact hjFire

/-! ## Single-step level advance -/

/-- Level strictly advances after some bounded number of cycles. Wraps
    `cumulative_progress_under_no_wait` against `GlobalInvariants`. -/
theorem level_advances_once (s : State)
    (hlvl : s.level < 50) (h : GlobalInvariants s) :
    ∃ k, (cycleStepN k s).level > s.level := by
  -- Item 1g-C: route through the PROVEN theorem in LifecycleBound7,
  -- bypassing the (now-deletable) cumulative_progress_under_no_wait
  -- wrapper that referenced the lifecycle_progress_from_bounds axiom.
  apply Formal.Liveness.LifecycleBound7.lifecycle_progress_from_bounds_proven
        s cycleStepN
  · intro n s'; exact cycleStepN_succ n s'
  · intro s'; exact cycleStepN_zero s'
  · exact hlvl
  · exact h.hnowait
  · exact h.hex
  · exact h.hbe
  · exact h.hfightFires

/-! ## Level-50 reachability -/

/-- **Tier 5 capstone**.

    Starting from any state with `level < 50` and `GlobalInvariants` holding,
    the planner iterates `cycleStep` finitely many times to reach
    `level ≥ 50`.

    Proof by strong induction on `50 - s.level`:
    - Base (level = 50): k = 0 trivially.
    - Step (level < 50): apply `level_advances_once` to get k₁ with new
      level > old level. By IH on the new state (preserved invariants),
      get k₂ reaching 50. Total k = k₁ + k₂.

    NO new axioms (uses LIV-001 + LIV-003 via cumulative_progress). -/
-- Helper: structural induction on gap with explicit state parameter.
theorem ai_reaches_level_fifty_aux :
    ∀ (gap : Nat) (s : State), 50 - s.level = gap →
      GlobalInvariants s → ∃ k, (cycleStepN k s).level ≥ 50 := by
  intro gap
  induction gap using Nat.strong_induction_on with
  | _ g ih =>
    intro s hgap h
    by_cases hlvl50 : s.level ≥ 50
    · exact ⟨0, by rw [cycleStepN_zero]; exact hlvl50⟩
    · push Not at hlvl50
      obtain ⟨k₁, hk₁⟩ := level_advances_once s hlvl50 h
      set s' := cycleStepN k₁ s with hsdef
      have hs'_inv : GlobalInvariants s' := by
        rw [hsdef]; exact globalInvariants_step s k₁ h
      have hs'_gap_lt : 50 - s'.level < g := by
        rw [← hgap]; omega
      obtain ⟨k₂, hk₂⟩ := ih (50 - s'.level) hs'_gap_lt s' rfl hs'_inv
      refine ⟨k₁ + k₂, ?_⟩
      rw [cycleStepN_add]
      rw [← hsdef]
      exact hk₂

theorem ai_reaches_level_fifty (s : State) (h : GlobalInvariants s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty_aux (50 - s.level) s rfl h

/-! ## Spawn-state corollary -/

/-- Spawn predicate: a fresh character at level 1 with no task. -/
def IsSpawn (s : State) : Prop :=
  s.level = 1 ∧ s.xp = 0 ∧ s.taskCode = none ∧ s.taskTotal = 0

/-- **Tier 5 corollary**: from any spawn state with `GlobalInvariants`,
    the planner reaches level 50 in finitely many cycles. -/
theorem ai_reaches_level_fifty_from_spawn (s : State)
    (_hspawn : IsSpawn s) (h : GlobalInvariants s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty s h

end Formal.Liveness.LevelFiftyReachable
