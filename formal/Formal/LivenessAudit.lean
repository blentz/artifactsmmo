/-
  Formal.LivenessAudit

  Prints `#print axioms` for every theorem in `Formal/Liveness/`. Consumed by
  `formal/gate/check_axioms_liveness.sh`. Liveness theorems may depend on
  Mathlib's standard axiom set (see the gate script for the enumerated
  allow-list at the current Mathlib pin).
-/
import Formal.Liveness.Placeholder

open Formal.Liveness.Placeholder

#print axioms mathlib_works
