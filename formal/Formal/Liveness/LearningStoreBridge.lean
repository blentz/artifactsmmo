import Formal.TaskDecision
import Formal.Liveness.Plan
import Formal.Liveness.Measure
import Formal.Liveness.ProductionLadder
import Mathlib.Tactic

/-! # LearningStoreBridge — Item 6a/6b

Bridges the safety-side `Formal.TaskDecision.taskDecisionPure` model
(Phase 13: PURSUE/PIVOT decision over learning-store observations)
into the Liveness side's opaque firing predicates
(`taskCancelFires`, `pursueTaskFires`).

  • 6a — `LearningStore` mirror structure: the inputs to
    `taskDecisionPure` as they would be packaged at the perception
    layer (skill-gap requirement, history presence, vpc/baseline/
    margin/confidence). State-carried via three new Bool/Rat fields
    on Liveness `State` is deferred; for 6a we ship the BRIDGE
    structure and document the connection.

  • 6b — connection theorem: under the assumption that the
    perception layer wires the opaque `taskCancelFires` to
    `taskDecisionPure ... = .PIVOT`, the Liveness-side cancel
    selection mirrors the safety-side PIVOT decision exactly.

NO new axioms.
-/

namespace Formal.Liveness.LearningStoreBridge

open Formal.Liveness.Plan
open Formal.Liveness.Measure
open Formal.Liveness.ProductionLadder
open Formal.TaskDecision

/-- Item 6a: bundled inputs to `taskDecisionPure`. Mirrors what the
    perception layer passes after reading the production LearningStore:
    skill-gap requirement flags, history presence, plus the VPC
    parameters. -/
structure LearningStore where
  reqIsNone : Bool
  reqIsCombat : Bool
  historyPresent : Bool
  skillUpVpc : Rat
  baseline : Rat
  margin : Rat
  confidence : Rat

/-- The pure decision projected from a LearningStore. -/
def decide (ls : LearningStore) : Decision :=
  taskDecisionPure ls.reqIsNone ls.reqIsCombat ls.historyPresent
    ls.skillUpVpc ls.baseline ls.margin ls.confidence

/-! ## Item 6b — Connection bridge

The Liveness-side `taskCancelFires : Bool` is OPAQUE in the model
(`Formal.Liveness.Measure.taskCancelFires := s.taskCancelFires`).
The perception layer is INTENDED to populate this field with
`decide ls = .PIVOT` for the cycle's learning store `ls`. The bridge
condition makes that explicit: if the perception layer respects
this contract, the safety-side PIVOT semantics carry over.
-/

/-- Bridge condition: state's opaque taskCancelFires reflects the
    PIVOT decision of the bundled learning store. -/
def taskCancelMirrorsPivot (s : State) (ls : LearningStore) : Prop :=
  s.taskCancelFires = (decide ls == Decision.PIVOT)

/-- When the bridge holds and the learning store decides PIVOT, the
    Liveness-side taskCancelFires is true (so the ladder will fire
    `.taskCancel` per `means.py:80-83`). -/
theorem taskCancelFires_when_PIVOT (s : State) (ls : LearningStore)
    (hBridge : taskCancelMirrorsPivot s ls)
    (hPivot : decide ls = Decision.PIVOT) :
    s.taskCancelFires = true := by
  unfold taskCancelMirrorsPivot at hBridge
  rw [hBridge, hPivot]
  rfl

/-- When the bridge holds and the learning store decides PURSUE, the
    Liveness-side taskCancelFires is false (so the ladder skips
    `.taskCancel` and proceeds to `.pursueTask`). -/
theorem taskCancelFires_false_when_PURSUE (s : State) (ls : LearningStore)
    (hBridge : taskCancelMirrorsPivot s ls)
    (hPursue : decide ls = Decision.PURSUE) :
    s.taskCancelFires = false := by
  unfold taskCancelMirrorsPivot at hBridge
  rw [hBridge, hPursue]
  rfl

/-! ## Re-export: combat-or-no-history pivots (Phase 13 → Liveness) -/

/-- Item 6b re-export at the Liveness layer: when the requirement is
    NOT none AND (combat OR no history), the learning store decides
    PIVOT. -/
theorem ls_pivots_on_combat_or_no_history
    (ls : LearningStore) (hReq : ls.reqIsNone = false)
    (h : ls.reqIsCombat = true ∨ ls.historyPresent = false) :
    decide ls = Decision.PIVOT := by
  unfold decide
  rw [hReq]
  exact combat_or_no_history_pivots ls.reqIsCombat ls.historyPresent
          ls.skillUpVpc ls.baseline ls.margin ls.confidence h

/-- Item 6b re-export: when the requirement is None, the learning
    store decides PURSUE (already-feasible task). -/
theorem ls_pursues_on_req_none
    (ls : LearningStore) (hReq : ls.reqIsNone = true) :
    decide ls = Decision.PURSUE := by
  unfold decide
  rw [hReq]
  exact req_none_pursues ls.reqIsCombat ls.historyPresent
          ls.skillUpVpc ls.baseline ls.margin ls.confidence

end Formal.Liveness.LearningStoreBridge
