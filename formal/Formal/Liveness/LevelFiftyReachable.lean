import Formal.Liveness.CumulativeProgress
import Formal.Liveness.LIV003Decomposition
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
  hperc : ∀ k k', productionLadder (cycleStepN k s) = some k' →
                    (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                    (cycleStepN k s).xp < xpToNextLevel (cycleStepN k s).level
                    ∧ (cycleStepN k s).level < 50

/-! ## cycleStepN composition -/

/-- Composition law for `cycleStepN`. Induction on `m` with `s` generalized
    is the natural direction for `cycleStepN_succ` (which unfolds from
    the outside). -/
theorem cycleStepN_add (m n : Nat) (s : State) :
    cycleStepN (m + n) s = cycleStepN n (cycleStepN m s) := by
  induction m generalizing s with
  | zero =>
    show cycleStepN (0 + n) s = cycleStepN n (cycleStepN 0 s)
    rw [cycleStepN_zero, Nat.zero_add]
  | succ j ih =>
    show cycleStepN ((j + 1) + n) s = cycleStepN n (cycleStepN (j + 1) s)
    rw [show (j + 1) + n = (j + n) + 1 from by omega]
    rw [cycleStepN_succ (j + n) s]
    rw [cycleStepN_succ j s]
    exact ih (cycleStep s)

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
  · intro k k' hk hk'
    rw [← cycleStepN_add m k s] at hk
    rw [← cycleStepN_add m k s]
    exact h.hperc (m + k) k' hk hk'

/-! ## Single-step level advance -/

/-- Level strictly advances after some bounded number of cycles. Wraps
    `cumulative_progress_under_no_wait` against `GlobalInvariants`. -/
theorem level_advances_once (s : State)
    (hlvl : s.level < 50) (h : GlobalInvariants s) :
    ∃ k, (cycleStepN k s).level > s.level := by
  exact cumulative_progress_under_no_wait s hlvl h.hnowait h.hex h.hbe h.hperc

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
    · push_neg at hlvl50
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
