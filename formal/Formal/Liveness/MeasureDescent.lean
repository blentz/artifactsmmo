import Formal.Liveness.Measure
import Formal.Liveness.CycleStepFIteration

/-! # MeasureDescent — the NON-VACUOUS level-50 engine: per-cycle measure descent.

The removed i.o.-fairness capstones were vacuous (kernel-proved, `docs/REVIEW_levelfifty_vacuity.md`): their residual
(`level < 50` infinitely often) contradicts monotone level + the reach-50 goal. This
module supplies the honest replacement — a well-founded descent argument whose
hypothesis is a LOCAL per-cycle measure decrease, NOT an i.o. property.

`exists_level_ge_of_descent`: for ANY trajectory, if the lex `Measure` strictly
decreases on every step where `level < 50`, then the trajectory reaches `level ≥ 50`.

Why this is non-vacuous (unlike the i.o.-fairness residual):
* **Satisfiable for reaching-50 trajectories** — the hypothesis only constrains
  below-50 steps; once `level ≥ 50` the guard is false and the step is unconstrained.
  A trajectory that decreases the measure until 50 satisfies it. (Contrast the i.o.
  residual, satisfiable ONLY when the goal fails.)
* **Non-circular** — the hypothesis is a conjunction of LOCAL per-step facts, each
  independently checkable, not a statement about the trajectory's limit behaviour.
* **Surfaces the livelock honestly** — the per-cycle decrease FAILS exactly at a
  no-progress (livelock) cycle, so discharging the hypothesis from the model is real,
  falsifiable work that must confront where the bot does and does not progress.

The engine is `measureLt`-well-foundedness (`Measure.measureLt_wellFounded`): an
infinite strictly-`measureLt`-descending sequence is impossible, so the guard cannot
hold forever. Generic over the trajectory, so it serves `cycleStepF`, `cycleStepP`,
and the base `cycleStep` alike. The per-cycle descent itself (discharging the
hypothesis from the cycle dynamics) is the follow-on modelling work.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.MeasureDescent

open Formal.Liveness.Measure
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration

/-- No sequence is infinitely strictly-`measureLt`-descending (well-foundedness of the
    lex measure order). The standard accessibility induction: if every `seq n` could be
    hit, the value `seq (n+1)` strictly below `seq n` cannot exist. -/
theorem no_infinite_descent (seq : Nat → Measure)
    (h : ∀ n, measureLt (seq (n + 1)) (seq n)) : False := by
  have key : ∀ x : Measure, ∀ n, seq n ≠ x := by
    intro x
    induction x using measureLt_wellFounded.induction with
    | _ x ih =>
      intro n hn
      exact ih (seq (n + 1)) (hn ▸ h n) (n + 1) rfl
  exact key (seq 0) 0 rfl

/-- **The non-vacuous level-50 engine.** If the lex `Measure` strictly decreases on
    every step of `traj` where `level < 50`, the trajectory reaches `level ≥ 50`.
    Proof: if it never did, `level < 50` would hold at every step (by the contrapositive
    of the goal), so the measure would descend forever — impossible. -/
theorem exists_level_ge_of_descent (traj : Nat → State)
    (hdesc : ∀ k, (traj k).level < 50 →
        measureLt (measure (traj (k + 1))) (measure (traj k))) :
    ∃ k, (traj k).level ≥ 50 := by
  by_contra hcon
  push Not at hcon
  -- hcon : ∀ k, (traj k).level < 50.
  exact no_infinite_descent (fun k => measure (traj k))
    (fun k => hdesc k (by have := hcon k; omega))

/-- **Level-50 reachability for `cycleStepF`, non-vacuously.** Instantiates the engine
    at the faithful trajectory `cycleStepFN · s`. The hypothesis `measureDescentBelowCap`
    — "every below-50 faithful cycle strictly decreases the lex measure" — is the honest
    replacement for the vacuous i.o.-fairness residual: it is satisfiable for
    reaching-50 trajectories and fails exactly at a livelock. Discharging it from the
    cycle dynamics (fight decreases xp-deficit, chore decreases its measure slot, …) is
    the follow-on modelling obligation. -/
theorem cycleStepF_reaches_fifty_of_descent (s : State)
    (hdesc : ∀ k, (cycleStepFN k s).level < 50 →
        measureLt (measure (cycleStepFN (k + 1) s)) (measure (cycleStepFN k s))) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  exists_level_ge_of_descent (fun k => cycleStepFN k s) hdesc

/-! ## Non-vacuity check — the descent hypothesis is NOT self-defeating

The removed i.o.-fairness residual was UNSATISFIABLE (it implies `False`; `docs/REVIEW_levelfifty_vacuity.md`).
The descent hypothesis is fundamentally different: it is jointly satisfiable WITH the
conclusion. The witness below is the degenerate one (a state already at the cap, where
the hypothesis holds vacuously and the goal holds at `k = 0`); it suffices to
distinguish the descent formulation from the vacuous i.o. one — the descent hypothesis
CAN hold when the goal holds, which the i.o. residual provably never can. The
SUBSTANTIVE satisfiability (a below-50 start whose every cycle descends) is exactly the
follow-on discharge from the model. -/
theorem descent_hyp_satisfiable_with_goal (s : State) (h : s.level ≥ 50) :
    (∀ k, (cycleStepFN k s).level < 50 →
        measureLt (measure (cycleStepFN (k + 1) s)) (measure (cycleStepFN k s)))
    ∧ (∃ k, (cycleStepFN k s).level ≥ 50) := by
  refine ⟨fun k hk => absurd hk (by have := cycleStepFN_level_ge s k; omega), 0, ?_⟩
  rw [cycleStepFN_zero]; exact h

end Formal.Liveness.MeasureDescent
