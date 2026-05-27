import Formal.CalculatePath
import Formal.TaskBatch
import Formal.InventoryCaps
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps
/-! STATEMENT CONTRACTS. Each `example` pins a role theorem's EXACT statement by
    ascribing it the full expected type. If a theorem's statement is weakened or
    changed, the ascription fails to elaborate and the build goes RED. This is the
    mechanized "theorem-statement review" — names alone are not enough (Manifest).
    Do NOT relax an expected type to make it compile; that defeats the gate. -/

-- validity
example : ∀ (start dst : Coord), ValidKingWalk start dst (pathFrom start dst) :=
  @pathFrom_valid
-- optimality achieved (length = Chebyshev, exactly)
example : ∀ (start dst : Coord), (pathFrom start dst).length = (cheb start dst).toNat :=
  @pathFrom_len_eq_cheb
-- optimality lower bound (EVERY valid king-walk ≥ Chebyshev)
example : ∀ (start dst : Coord) (p : List Coord),
    ValidKingWalk start dst p → (cheb start dst).toNat ≤ p.length :=
  @kingWalk_len_ge_cheb
-- cost: produced length ≤ reported Manhattan
example : ∀ (start dst : Coord),
    (pathFrom start dst).length ≤ (manhattan start dst).toNat :=
  @pathFrom_cost
-- cost: Chebyshev ≤ Manhattan
example : ∀ (start dst : Coord), cheb start dst ≤ manhattan start dst :=
  @cheb_le_manhattan
-- estimated_time: 5 × Chebyshev (len(steps) * 5)
example : ∀ (start dst : Coord), estimatedTime start dst = (cheb start dst).toNat * 5 :=
  @estimatedTime_eq_cheb

/-! ### TaskBatch role contracts. -/

-- batch_ge_one: result ≥ 1 for ANY branch flag and any inputs
example : ∀ (tb : Bool) (remaining mats free held : Int),
    1 ≤ batchSize tb remaining mats free held :=
  @batch_ge_one
-- batch_le_remaining: task-branch ⇒ result ≤ remaining (given remaining ≥ 1)
example : ∀ (remaining mats free held : Int),
    1 ≤ remaining → batchSize true remaining mats free held ≤ remaining :=
  @batch_le_remaining
-- batch_le_cap: task-branch ⇒ result ≤ batchCap (= 10)
example : ∀ (remaining mats free held : Int),
    batchSize true remaining mats free held ≤ batchCap :=
  @batch_le_cap
-- batch_fits: task-branch ∧ mats ≥ 1 ∧ usable ≥ mats ⇒ result*mats ≤ usable
example : ∀ (remaining mats free held : Int),
    1 ≤ mats → mats ≤ (free + held) - minFree →
    batchSize true remaining mats free held * mats ≤ (free + held) - minFree :=
  @batch_fits
-- non_task_one: ¬task-branch ⇒ result = 1
example : ∀ (remaining mats free held : Int),
    batchSize false remaining mats free held = 1 :=
  @non_task_one

/-! ### InventoryCaps role contracts. -/

-- cap_eq_max_of_four: ¬equipped ⇒ cap = max(recipeCap, taskCap, actionCap, equipCap)
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int),
    cap recipeDemand equippable actionCap taskRemaining false
      = max (recipeCap recipeDemand)
          (max taskRemaining (max actionCap (equipCap equippable))) :=
  @cap_eq_max_of_four
-- cap_eq_max_one_of_four: equipped ⇒ cap = max(1, max-of-four)
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int),
    cap recipeDemand equippable actionCap taskRemaining true
      = max 1 (max (recipeCap recipeDemand)
          (max taskRemaining (max actionCap (equipCap equippable)))) :=
  @cap_eq_max_one_of_four
-- equipped_ge_one: equipped ⇒ 1 ≤ cap
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int),
    1 ≤ cap recipeDemand equippable actionCap taskRemaining true :=
  @equipped_ge_one
-- recipe_cap_ge_safety: recipeDemand > 0 ⇒ recipeCap ≥ SAFETY_FLOOR
example : ∀ (recipeDemand : Int), recipeDemand > 0 → safetyFloor ≤ recipeCap recipeDemand :=
  @recipe_cap_ge_safety
-- overstock_exact: excess = (qty - cap) iff (qty > 0 ∧ qty > cap), else 0
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    overstock recipeDemand equippable actionCap taskRemaining equipped qty
      = (if qty > 0 ∧ qty > cap recipeDemand equippable actionCap taskRemaining equipped
         then qty - cap recipeDemand equippable actionCap taskRemaining equipped
         else 0) :=
  @overstock_exact
-- overstock_pos_of_over: over ⇒ excess > 0
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    qty > 0 → qty > cap recipeDemand equippable actionCap taskRemaining equipped →
    0 < overstock recipeDemand equippable actionCap taskRemaining equipped qty :=
  @overstock_pos_of_over
-- overstock_zero_of_not_over: ¬over ⇒ excess = 0
example : ∀ (recipeDemand : Int) (equippable : Bool) (actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    ¬ (qty > 0 ∧ qty > cap recipeDemand equippable actionCap taskRemaining equipped) →
    overstock recipeDemand equippable actionCap taskRemaining equipped qty = 0 :=
  @overstock_zero_of_not_over
