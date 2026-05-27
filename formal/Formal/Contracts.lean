import Formal.CalculatePath
import Formal.TaskBatch
import Formal.InventoryCaps
import Formal.PredictWin
import Formal.LoadoutProjection
import Formal.EquipmentScoring
import Formal.SkillXpCurve
import Formal.RecipeClosure
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve Formal.RecipeClosure
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

/-! ### EquipmentScoring role contracts. -/

-- pickslot_score_optimal: the picked best dominates EVERY feasible candidate's score
example : ∀ (score : Item → Int) (playerLevel : Int) (items : List Item)
    (c : Item) (cs : List Item),
    candidates playerLevel items = c :: cs →
    ∀ y ∈ candidates playerLevel items, score y ≤ score (argmaxBy score c cs) :=
  @pickslot_score_optimal
-- pickslot_no_downgrade: with a current item, the result's score ≥ current's score
example : ∀ (score : Item → Int) (playerLevel : Int) (cur : Item) (items : List Item),
    ∃ r, pickSlot score playerLevel (some cur) items = some r ∧ score cur ≤ score r :=
  @pickslot_no_downgrade
-- pickslot_best_feasible: the freshly-picked best is level-feasible ∧ slot-fitting
example : ∀ (score : Item → Int) (playerLevel : Int) (items : List Item)
    (c : Item) (cs : List Item),
    candidates playerLevel items = c :: cs →
    feasible playerLevel (argmaxBy score c cs) = true :=
  @pickslot_best_feasible
-- pickslot_ties_keep_current: argmax score = current's score ⇒ result = current
example : ∀ (score : Item → Int) (playerLevel : Int) (cur : Item) (items : List Item)
    (c : Item) (cs : List Item),
    candidates playerLevel items = c :: cs →
    score (argmaxBy score c cs) = score cur →
    pickSlot score playerLevel (some cur) items = some cur :=
  @pickslot_ties_keep_current
-- pickslot_empty_fills: empty slot + feasible candidate ⇒ fill with argmax best
example : ∀ (score : Item → Int) (playerLevel : Int) (items : List Item)
    (c : Item) (cs : List Item),
    candidates playerLevel items = c :: cs →
    pickSlot score playerLevel none items = some (argmaxBy score c cs) :=
  @pickslot_empty_fills
-- pickslot_no_candidates_keeps: no feasible candidate ⇒ slot left as-is
example : ∀ (score : Item → Int) (playerLevel : Int) (current : Option Item)
    (items : List Item),
    candidates playerLevel items = [] →
    pickSlot score playerLevel current items = current :=
  @pickslot_no_candidates_keeps
-- weapon_score_nonneg: nonneg per-element attacks ⇒ WScore ≥ 0 (the clamp earns this)
example : ∀ (item : Item) (monsterRes : ElemStats),
    (∀ e ∈ elements, 0 ≤ elemGet item.attack e) → 0 ≤ WScore item monsterRes :=
  @weapon_score_nonneg

/-! ### SkillXpCurve role contracts. -/

-- required_xp_observed: observed level ⇒ required_xp = stored xp (∀ estimate)
example : ∀ (estimate : Int → Int) (obs : Observed) (level : Int),
    hasLevel obs level = true → requiredXp estimate obs level = lookup obs level :=
  @required_xp_observed
-- required_xp_zero: no data ∨ no level below ⇒ required_xp = 0
example : ∀ (estimate : Int → Int) (obs : Observed) (level : Int),
    hasLevel obs level = false →
    (obs.isEmpty = true ∨ hasBelow obs level = false) →
    requiredXp estimate obs level = 0 :=
  @required_xp_zero
-- confNum_le_confDen: 0 ≤ confNum ≤ confDen (fraction ∈ [0,1])
example : ∀ (obs : Observed) (current target : Int),
    confNum obs current target ≤ confDen current target :=
  @confNum_le_confDen
-- is_confident_iff_full: is_confident ↔ confNum = confDen (every gap level observed)
example : ∀ (obs : Observed) (current target : Int),
    isConfident obs current target = true
      ↔ confNum obs current target = confDen current target :=
  @is_confident_iff_full
-- cycles_zero: target ≤ current ⇒ 0
example : ∀ (current target xpPerCycle : Int),
    target ≤ current → cyclesBranch current target xpPerCycle = 0 :=
  @cycles_zero
-- cycles_inf: target > current ∧ xp_per_cycle ≤ 0 ⇒ inf-sentinel
example : ∀ (current target xpPerCycle : Int),
    target > current → xpPerCycle ≤ 0 →
    cyclesBranch current target xpPerCycle = cyclesInf :=
  @cycles_inf
-- total_monotone: total(cur,tgt) ≤ total(cur,tgt+1) over observed range (term ≥ 0)
example : ∀ (obs : Observed) (current target : Int),
    current ≤ target → 0 ≤ lookup obs target →
    totalXpToReach obs current target ≤ totalXpToReach obs current (target + 1) :=
  @total_monotone
-- growth_default_iff: uses-default ↔ no consecutive observed pair (independent count = 0)
example : ∀ (obs : Observed),
    usesDefaultRatio obs = true ↔ consecutivePairCount obs = 0 :=
  @growth_default_iff
-- growth_nondefault_of_pair: a consecutive observed pair (positive lower xp) ⇒ ¬default
example : ∀ (obs : Observed) (lvl v : Int),
    (lvl, v) ∈ obs → v > 0 → hasLevel obs (lvl + 1) = true →
    usesDefaultRatio obs = false :=
  @growth_nondefault_of_pair

/-! ### RecipeClosure role contracts. -/

-- closure = least fixpoint: a material is Reachable IFF it appears in some
-- bounded saturation round (soundness + completeness of the DFS).
example : ∀ (r : Recipe) (roots : List Nat) (m : Nat),
    Reachable r roots m ↔ ∃ n, m ∈ satN r roots n :=
  @reachable_iff_satN
-- LEAST: any set containing the roots and closed under the recipe-child relation
-- contains every Reachable item (Reachable is the smallest fixpoint).
example : ∀ (r : Recipe) (roots : List Nat) (S : Nat → Prop),
    (∀ m ∈ roots, S m) →
    (∀ item child, S item → child ∈ (r item).map Prod.fst → S child) →
    ∀ {m : Nat}, Reachable r roots m → S m :=
  @reachable_least
-- SOUNDNESS of the computed closure: every produced item is Reachable.
example : ∀ (r : Recipe) (roots : List Nat) (fuel : Nat) {m : Nat},
    m ∈ closureItems r roots fuel → Reachable r roots m :=
  @closureItems_sound
-- COMPLETENESS of the computed closure: an item appearing at round n ≤ fuel is
-- in the computed closure (nothing reachable within budget is missed).
example : ∀ (r : Recipe) (roots : List Nat) (fuel n : Nat),
    n ≤ fuel → ∀ {m : Nat}, m ∈ satN r roots n → m ∈ closureItems r roots fuel :=
  @closureItems_complete
-- craftable_mats soundness: a craftable-list member is Reachable ∧ has a recipe.
example : ∀ (r : Recipe) (roots : List Nat) (fuel : Nat) {m : Nat},
    m ∈ craftableList r roots fuel → isCraftable r roots m :=
  @craftableList_isCraftable
-- needed_resources soundness: a needed-list member's drop is Reachable.
example : ∀ (r : Recipe) (roots : List Nat) (drops : List (Nat × Nat)) (fuel : Nat) {res : Nat},
    res ∈ neededList r roots drops fuel → isNeeded r roots drops res :=
  @neededList_isNeeded
-- raw_units_eq_cost: documented quantity math — Σ qty * units(sub) over the recipe.
example : ∀ (r : Recipe) (n : Nat) (visited : List Nat) (item : Nat),
    item ∉ visited → ∀ (rcp : List (Nat × Nat)), r item = rcp → rcp ≠ [] →
    rawUnitsAux r (n + 1) visited item
      = (rcp.map (fun p => p.2 * rawUnitsAux r n (item :: visited) p.1)).sum :=
  @rawUnits_eq_cost
-- raw_units cyclic guard: a revisited item costs exactly 1 (cycle-safe).
example : ∀ (r : Recipe) (n : Nat) (visited : List Nat) (item : Nat),
    item ∈ visited → rawUnitsAux r (n + 1) visited item = 1 :=
  @rawUnits_revisit
-- TERMINATION on cyclic recipes: the remaining-universe measure strictly
-- decreases on each recursive descent (well-founded ⇒ terminates).
example : ∀ (univ visited : List Nat) (item : Nat),
    item ∈ univ → item ∉ visited →
    remaining univ (item :: visited) < remaining univ visited :=
  @remaining_decreasing
-- TERMINATION / well-definedness: with adequate fuel (≥ remaining universe) the
-- cost is fuel-independent — the recursion has fully bottomed out (no divergence
-- even on cycles).
example : ∀ (r : Recipe) (univ : List Nat), UnivClosed r univ →
    ∀ (f f' : Nat) (visited : List Nat) (item : Nat),
      item ∈ univ → remaining univ visited ≤ f → remaining univ visited ≤ f' →
      rawUnitsAux r f visited item = rawUnitsAux r f' visited item :=
  @rawUnits_fuel_stable
