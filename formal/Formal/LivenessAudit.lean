/-
  Formal.LivenessAudit

  Prints `#print axioms` for every theorem in `Formal/Liveness/`. Consumed by
  `formal/gate/check_axioms_liveness.sh`. Liveness theorems may depend on
  Mathlib's standard axiom set (see the gate script for the enumerated
  allow-list at the current Mathlib pin).

  Note: Phase 19b introduces the FIRST production-use liveness axiom,
  `Formal.Liveness.Measure.xpToNextLevel` (AXIOM-ID LIV-001 in
  `Formal/Liveness/Measure.lean`). The gate's allow-list explicitly permits
  this axiom; the manifest records it per theorem.
-/
import Formal.Liveness.Placeholder
import Formal.Liveness.Measure
import Formal.Liveness.FightProgress

open Formal.Liveness.Placeholder
open Formal.Liveness.Measure
open Formal.Liveness.FightProgress

-- Phase 19a sanity.
#print axioms mathlib_works

-- Phase 19b: Measure module.
#print axioms measureLt_wellFounded
#print axioms measureLt_of_levelDeficit_dec
#print axioms measureLt_of_xpDeficit_dec
#print axioms toLexQuint_lt_of_measureLt

-- Phase 19b: FightAction progress.
#print axioms fight_decreases_measure
