import Formal.Liveness.CycleStepDC
import Formal.Liveness.CycleStepE

/-! # CycleStepEC — computable mirror of the GEARED cycle

E-tower follow-up (docs/PLAN_c2_composed_liveness.md): the oracle-evaluable
clone of `cycleStepE`, standing on the Phase-B2 `cycleStepC` clone. All four
E layers (`perceptionRefreshE`, `gearProgress`, `fightLoss`, `rearmE`) are
already computable; only the inner `cycleStep` needs the `xpNext` substitute.
`cycleStepEC_eq` is the anti-drift binding for the E trace-lockstep
differential: kernel-verified, so mirror and model cannot diverge silently.

Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.CycleStepEC

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepD
open Formal.Liveness.CycleStepDC
open Formal.Liveness.CycleStepE

/-- Computable clone of `cycleStepE`. -/
def cycleStepEC (xpNext : Nat) (s : State) : State :=
  match productionLadder (perceptionRefreshE s) with
  | some k =>
      rearmE k (perceptionRefreshE s)
        (gearProgress k
          (fightLoss k (perceptionRefreshE s)
            (partialClear k
              (pressureDeltaD k (perceptionRefreshE s)
                (cycleStepC xpNext (perceptionRefreshE s))))))
  | none => cycleStepC xpNext (perceptionRefreshE s)

/-- **The E-lockstep binding**: the computable geared cycle IS `cycleStepE`
    at the axiom's value. The oracle evaluates the left side; the capstone
    (`ai_reaches_fifty_geared`) speaks about the right side. -/
theorem cycleStepEC_eq (s : State) :
    cycleStepEC (xpToNextLevel s.level) s = cycleStepE s := by
  unfold cycleStepEC cycleStepE
  have hx : xpToNextLevel s.level = xpToNextLevel (perceptionRefreshE s).level := by
    rw [perceptionRefreshE_level]
  cases productionLadder (perceptionRefreshE s) with
  | none => dsimp only; rw [hx, cycleStepC_eq]
  | some k => dsimp only; rw [hx, cycleStepC_eq]

end Formal.Liveness.CycleStepEC
