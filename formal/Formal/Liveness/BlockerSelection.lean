import Formal.Liveness.ProductionLadder
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # BlockerSelection — converse selection lemmas (SELECT-reach sub-lemma 1)

`productionLadder s = allInLadderOrder.findSome? (fun k => if fires k s then some k
else none)` returns the FIRST firing means over a fixed 23-slot priority list. The
`BlockerQuieting` clear lemmas assume a blocker is ALREADY selected
(`productionLadder s = some B`); to drive the warm-up we need the CONVERSE: a
blocker is selected exactly when it fires and every higher-priority slot is quiet.
Only `pursueTask` and `objectiveStep` had such lemmas
(`PursueTaskSelection`, `FightFairness`); this module adds the eight for the
FightReadyCore blocker clears (hp / discard / deposit / gear / claim / sell /
craft). Each is the `findSome?` short-circuit: the quiet prefix maps to `none`,
the firing blocker returns `some B`, and `.or` stops there (suffix fires values
irrelevant). These feed the per-seed reaches (SELECT-reach sub-lemmas 3-4).

Liveness namespace — Mathlib allowed.
-/

namespace Formal.Liveness.BlockerSelection

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- hp-critical is the FIRST ladder slot: it is selected whenever it fires. -/
theorem productionLadder_eq_hpCritical (s : State)
    (hfire : fires .hpCritical s = true) :
    productionLadder s = some .hpCritical := by
  simp [productionLadder, allInLadderOrder, hfire]

/-- `discardCritical` (slot 4) is selected when it fires and the four higher slots
    (hpCritical, restForCombat, bankUnlock, reachUnlockLevel) are quiet. -/
theorem productionLadder_eq_discardCritical (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (hfire : fires .discardCritical s = true) :
    productionLadder s = some .discardCritical := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, hfire]

/-- `craftRelief` (slot 5) — higher: slots 0-4. -/
theorem productionLadder_eq_craftRelief (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false)
    (hfire : fires .craftRelief s = true) :
    productionLadder s = some .craftRelief := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, hfire]

/-- `depositFull` (slot 8) — higher: slots 0-7 (incl. recycleRelief, sellRelief). -/
theorem productionLadder_eq_depositFull (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false) (h5 : fires .craftRelief s = false)
    (h5b : fires .recycleRelief s = false)
    (h5c : fires .sellRelief s = false)
    (hfire : fires .depositFull s = true) :
    productionLadder s = some .depositFull := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, h5, h5b, h5c, hfire]

/-- `discardHigh` (slot 9) — higher: slots 0-8. -/
theorem productionLadder_eq_discardHigh (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false) (h5 : fires .craftRelief s = false)
    (h5b : fires .recycleRelief s = false)
    (h5c : fires .sellRelief s = false)
    (h6 : fires .depositFull s = false)
    (hfire : fires .discardHigh s = true) :
    productionLadder s = some .discardHigh := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, h5, h5b, h5c, h6, hfire]

/-- `gearReview` (slot 10) — higher: slots 0-9. -/
theorem productionLadder_eq_gearReview (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false) (h5 : fires .craftRelief s = false)
    (h5b : fires .recycleRelief s = false)
    (h5c : fires .sellRelief s = false)
    (h6 : fires .depositFull s = false) (h7 : fires .discardHigh s = false)
    (hfire : fires .gearReview s = true) :
    productionLadder s = some .gearReview := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, h5, h5b, h5c, h6, h7, hfire]

/-- `claimPending` (slot 11) — higher: slots 0-10. -/
theorem productionLadder_eq_claimPending (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false) (h5 : fires .craftRelief s = false)
    (h5b : fires .recycleRelief s = false)
    (h5c : fires .sellRelief s = false)
    (h6 : fires .depositFull s = false) (h7 : fires .discardHigh s = false)
    (h8 : fires .gearReview s = false) (h8b : fires .craftPotions s = false)
    (hfire : fires .claimPending s = true) :
    productionLadder s = some .claimPending := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, h5, h5b, h5c, h6, h7, h8, h8b, hfire]

/-- `sellPressured` (slot 13) — higher: slots 0-12 (incl. completeTask). -/
theorem productionLadder_eq_sellPressured (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false) (h3 : fires .reachUnlockLevel s = false)
    (h4 : fires .discardCritical s = false) (h5 : fires .craftRelief s = false)
    (h5b : fires .recycleRelief s = false)
    (h5c : fires .sellRelief s = false)
    (h6 : fires .depositFull s = false) (h7 : fires .discardHigh s = false)
    (h8 : fires .gearReview s = false) (h8b : fires .craftPotions s = false)
    (h9 : fires .claimPending s = false)
    (h10 : fires .completeTask s = false)
    (hfire : fires .sellPressured s = true) :
    productionLadder s = some .sellPressured := by
  simp [productionLadder, allInLadderOrder,
    h0, h1, h2, h3, h4, h5, h5b, h5c, h6, h7, h8, h8b, h9, h10, hfire]

/-- `bankUnlock` (slot 2, a FIGHT means) is selected when it fires and the two
    higher slots (hpCritical, restForCombat) are quiet. Used by the B-0 bootstrap
    descent: in the window a level-up can RE-ARM bankUnlock, but bankUnlock also
    dispatches `.fight`, so the cycle fights whether bankUnlock or
    reachUnlockLevel is selected. -/
theorem productionLadder_eq_bankUnlock (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hfire : fires .bankUnlock s = true) :
    productionLadder s = some .bankUnlock := by
  simp [productionLadder, allInLadderOrder, h0, h1, hfire]

/-- `reachUnlockLevel` (slot 3, a FIGHT means) is selected when it fires and the
    three higher slots (hpCritical, restForCombat, bankUnlock) are quiet. Used by
    the B-0 bootstrap reach: in the under-bankRequiredLevel window reachUnlockLevel
    fires unconditionally, so once hp is restored + bankUnlock retires it is the
    selected means and the cycle fights. -/
theorem productionLadder_eq_reachUnlockLevel (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false)
    (hfire : fires .reachUnlockLevel s = true) :
    productionLadder s = some .reachUnlockLevel := by
  simp [productionLadder, allInLadderOrder, h0, h1, h2, hfire]

end Formal.Liveness.BlockerSelection
