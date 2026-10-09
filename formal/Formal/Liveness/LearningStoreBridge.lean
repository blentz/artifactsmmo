import Formal.TaskDecision
import Mathlib.Tactic

/-! # LearningStoreBridge — Item 6a/6b

Bridges the safety-side `Formal.TaskDecision.taskDecisionPure` model
(Phase 13: PURSUE/PIVOT decision over learning-store observations)
to the Liveness layer. The opaque firing predicates it once connected
(`taskCancelFires`, `pursueTaskFires`) left the model with the
TASK_CANCEL and PURSUE_TASK rungs (Phase 5-2c-iii); the
`State.taskCancelFires` connection lemmas went with them, and the
re-exports below remain.

  • 6a — `LearningStore` mirror structure: the inputs to
    `taskDecisionPure` as they would be packaged at the perception
    layer (skill-gap requirement, history presence, vpc/baseline/
    margin/confidence). State-carried via three new Bool/Rat fields
    on Liveness `State` is deferred; for 6a we ship the BRIDGE
    structure and document the connection.

  • 6b — re-exports of the PIVOT/PURSUE verdicts at the Liveness
    layer over a bundled `LearningStore`.

NO new axioms.
-/

namespace Formal.Liveness.LearningStoreBridge

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
