import Formal.CalculatePath
import Formal.TaskBatch
import Formal.InventoryCaps
import Formal.PredictWin
import Formal.LoadoutProjection
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin Formal.LoadoutProjection
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

/-! ### PredictWin role contracts. -/

-- predict_win_eq_sim: closed-form verdict = operational fight-sim verdict
-- (∀ stat tuples in the modeled domain: crit ≥ 0, HP ≥ 1, with enough sim fuel).
example : ∀ (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool),
    0 ≤ pCrit → 0 ≤ mCrit → 1 ≤ monsterHp → 1 ≤ playerMaxHp →
    ∀ (fk fd : Nat),
      (roundsTo monsterHp rawPlayer pCrit).toNat ≤ fk →
      (roundsTo playerMaxHp rawMonster mCrit).toNat ≤ fd →
      predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst
        = (if rawPlayer ≤ 0 then false
           else
             let rtk := simRounds monsterHp rawPlayer pCrit fk
             if rtk > maxTurns then false
             else if rawMonster ≤ 0 then true
             else
               let rtd := simRounds playerMaxHp rawMonster mCrit fd
               if playerFirst then rtk ≤ rtd else rtk < rtd) :=
  @predict_win_eq_sim
-- maxturns_sound: rounds_to_kill > MAX_TURNS ⇒ ¬win
example : ∀ (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool),
    0 < rawPlayer → roundsTo monsterHp rawPlayer pCrit > maxTurns →
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = false :=
  @maxturns_sound
-- predict_win_mono_player: increasing player raw never flips a win to a loss
example : ∀ (raw1 raw2 pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool),
    0 ≤ pCrit → 0 < raw1 → raw1 ≤ raw2 → 0 ≤ monsterHp →
    predictWin raw1 pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = true →
    predictWin raw2 pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = true :=
  @predict_win_mono_player
-- predict_win_mono_monsterhp: decreasing monster HP never flips a win to a loss
example : ∀ (rawPlayer pCrit monsterHp1 monsterHp2 rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool),
    0 ≤ pCrit → 0 < rawPlayer → 0 ≤ monsterHp2 → monsterHp2 ≤ monsterHp1 →
    predictWin rawPlayer pCrit monsterHp1 rawMonster mCrit playerMaxHp playerFirst = true →
    predictWin rawPlayer pCrit monsterHp2 rawMonster mCrit playerMaxHp playerFirst = true :=
  @predict_win_mono_monsterhp

/-! ### LoadoutProjection role contracts. -/

-- proj_identity: loadout = equipment ⇒ projected field = current (per field)
example : ∀ (current : Int) (slots : List SlotData),
    isIdentity slots → projectedField current slots = current :=
  @proj_identity
-- proj_additive: projected = current + UNCONDITIONAL Σ (new − old) (per field)
example : ∀ (current : Int) (slots : List SlotData),
    slotsWf slots → projectedField current slots = current + unconditionalSum slots :=
  @proj_additive
-- guarded_eq_unconditional: the changed-slot-guarded sum equals the
-- unconditional all-slot sum (the `continue` guard is sound)
example : ∀ (slots : List SlotData),
    slotsWf slots → guardedSum slots = unconditionalSum slots :=
  @guarded_eq_unconditional
-- dropZeros_preserves_nonzero: _drop_zeros keeps every nonzero entry's value
example : ∀ (d : List (Int × Int)) (k v : Int),
    (k, v) ∈ d → v ≠ 0 → (∀ kv ∈ d, kv.1 = k → kv.2 = v) →
    lookupD (dropZeros d) k = v :=
  @dropZeros_preserves_nonzero
-- dropZeros_zero_reads_zero: a dropped zero reads back as 0 (dict.get(k, 0))
example : ∀ (d : List (Int × Int)) (k : Int),
    (∀ kv ∈ d, kv.1 = k → kv.2 = 0) → lookupD (dropZeros d) k = 0 :=
  @dropZeros_zero_reads_zero
