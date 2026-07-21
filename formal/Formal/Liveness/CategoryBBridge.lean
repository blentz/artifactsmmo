import Formal.StuckDetector
-- These four arrived transitively via the retired LevelFiftyReachable import
-- (removed 2026-07-20 with the superseded capstone tower); named directly now.
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # CategoryBBridge — Item 2c

Documents the cross-reference between GlobalInvariants Category B
hypotheses (trajectory liveness — `hnowait`, `hfightFires`) and the
safety-side `Formal.StuckDetector`. These hypotheses are NOT
structurally provable on the Lean side; production monitors them
via the StuckDetector and escalates on violation.

This module ships no new theorems — it is a documentation anchor
making the safety/liveness boundary explicit, with explicit symbol
references the audit grep can verify.

NO new axioms.
-/

namespace Formal.Liveness.CategoryBBridge

open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.StuckDetector

/-! ## hnowait → noprog signal

  GlobalInvariants.hnowait asserts the production ladder NEVER picks
  `.wait` along the trajectory. If violated at cycle k, then at cycle
  k the bot's plan is `[.wait]` (cf. CycleStep.planFor .wait = [.wait])
  — production records this as a noPlan or wait-only cycle.

  After `noprogThreshold = 4` consecutive such cycles,
  `StuckDetector.checkNoProgress` returns true and `detect` raises
  `Signal.noprog`. The bot's outer loop escalates.

  REFERENCE SYMBOLS (audit-grep visible):
    Formal.StuckDetector.checkNoProgress
    Formal.StuckDetector.noprogThreshold
    Formal.StuckDetector.Signal.noprog
-/

/-- Anchor binding the Category B `hnowait` invariant to the
    safety-side noprog detector. Definitionally trivial — exists
    purely as a citation. -/
def hnowait_safety_anchor : Nat := noprogThreshold

/-! ## hfightFires → frozen signal

  GlobalInvariants.hfightFires asserts `.bankUnlock`/`.reachUnlockLevel`
  (which both apply `.fight`) fire infinitely often along the trajectory.
  If violated past a finite horizon, no further `.fight` events occur:
  - `s.level` stops advancing (proven in
    `Formal.Liveness.LifecycleBound6.cycleStepN_level_ge` + the
    contradiction in `LifecycleBound7`).
  - State fields read by `bankUnlockFires`/`reachUnlockLevelFires`
    stop changing.

  After `frozenThreshold = 10` cycles with unchanged state,
  `StuckDetector.checkStateFrozen` returns true and `detect` raises
  `Signal.frozen`. The bot's outer loop escalates.

  REFERENCE SYMBOLS (audit-grep visible):
    Formal.StuckDetector.checkStateFrozen
    Formal.StuckDetector.frozenThreshold
    Formal.StuckDetector.Signal.frozen
-/

/-- Anchor binding the Category B `hfightFires` invariant to the
    safety-side frozen detector. -/
def hfightFires_safety_anchor : Nat := frozenThreshold

end Formal.Liveness.CategoryBBridge
