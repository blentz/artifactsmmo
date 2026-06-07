import Formal.CalculatePath
import Formal.TaskBatch
import Formal.InventoryCaps
import Formal.PredictWin
import Formal.LoadoutProjection
import Formal.EquipmentScoring
import Formal.SkillXpCurve
import Formal.RecipeClosure
import Formal.TaskFeasibility
import Formal.PrerequisiteGraph
import Formal.Objective
import Formal.StrategyTraversal
import Formal.BankSelection
import Formal.StuckDetector
import Formal.PriorityBand
import Formal.GoalValueBands
import Formal.GoalSystem
import Formal.OwnedCount
import Formal.UpgradeSelection
import Formal.Scalarizer
import Formal.PlannerAdmissibility
import Formal.PlannerDepthBound
import Formal.TieredSelection
import Formal.GearLatch
import Formal.TaskDecision
import Formal.LowYieldCancel
import Formal.StrategyBlend
import Formal.DecideKey
import Formal.CyclesForProgress
import Formal.GatherApply
import Formal.GatherSelection
import Formal.NpcBuyInventory
import Formal.InventoryChainSafe
import Formal.ActionCostNonneg
import Formal.ApplyBaseline
import Formal.Phase7Invariants
import Formal.Phase8Invariants
import Formal.StoreWarmup
import Formal.GameDataAccessors
import Formal.WinnableCascade
import Formal.RealizableLoadout
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

-- cap_eq_max_of_five: ¬equipped ⇒ cap = max(recipeCap, taskCap, actionCap, equippableCap, consumableCap)
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int),
    cap recipeDemand equippableCap consumableCap actionCap taskRemaining false
      = max (recipeCap recipeDemand)
          (max taskRemaining
            (max actionCap
              (max equippableCap consumableCap))) :=
  @cap_eq_max_of_five
-- cap_eq_max_one_of_five: equipped ⇒ cap = max(1, max-of-five)
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int),
    cap recipeDemand equippableCap consumableCap actionCap taskRemaining true
      = max 1 (max (recipeCap recipeDemand)
          (max taskRemaining
            (max actionCap
              (max equippableCap consumableCap)))) :=
  @cap_eq_max_one_of_five
-- equipped_ge_one: equipped ⇒ 1 ≤ cap
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int),
    1 ≤ cap recipeDemand equippableCap consumableCap actionCap taskRemaining true :=
  @equipped_ge_one
-- recipe_cap_ge_safety: recipeDemand > 0 ⇒ recipeCap ≥ SAFETY_FLOOR
example : ∀ (recipeDemand : Int), recipeDemand > 0 → safetyFloor ≤ recipeCap recipeDemand :=
  @recipe_cap_ge_safety
-- overstock_exact: excess = (qty - cap) iff (qty > 0 ∧ qty > cap), else 0
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty
      = (if qty > 0 ∧ qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped
         then qty - cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped
         else 0) :=
  @overstock_exact
-- overstock_pos_of_over: over ⇒ excess > 0
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    qty > 0 → qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped →
    0 < overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty :=
  @overstock_pos_of_over
-- overstock_zero_of_not_over: ¬over ⇒ excess = 0
example : ∀ (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int),
    ¬ (qty > 0 ∧ qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped) →
    overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty = 0 :=
  @overstock_zero_of_not_over

-- equipCap_zero_of_not_equippable: not equippable ⇒ equippableCap = 0
example : ∀ (isDominated : Bool),
    equipCapValue false isDominated = 0 :=
  @equipCap_zero_of_not_equippable
-- equipCap_zero_of_dominated: dominated ⇒ equippableCap = 0 (regardless of equippable flag)
example : ∀ (isEquippable : Bool),
    equipCapValue isEquippable true = 0 :=
  @equipCap_zero_of_dominated
-- equipCap_eq_keep_of_undominated_equippable: equippable AND not dominated ⇒ equippableCap = EQUIPPABLE_KEEP
example : equipCapValue true false = equippableKeep :=
  @equipCap_eq_keep_of_undominated_equippable
-- consumableCap_zero_of_not_healing: hp_restore = 0 ⇒ consumableCap = 0
example : consumableCapValue 0 = 0 :=
  @consumableCap_zero_of_not_healing
-- consumableCap_eq_keep_of_healing: hp_restore > 0 ⇒ consumableCap = CONSUMABLE_KEEP
example : ∀ (hpRestore : Int), hpRestore > 0 →
    consumableCapValue hpRestore = consumableKeep :=
  @consumableCap_eq_keep_of_healing
-- equipCapFromPeers_dominated: dominance-detected peers zero the equippable cap
example : ∀ (isEquippable : Bool) (peers : List Peer) (slotCount : Int),
    isDominatedBy peers slotCount = true →
    equipCapFromPeers isEquippable peers slotCount = 0 :=
  @equipCapFromPeers_dominated
-- isDominatedBy_nil_of_positive_slot: empty peer list never dominates (positive slots)
example : ∀ (slotCount : Int), slotCount ≥ 1 →
    isDominatedBy [] slotCount = false :=
  @isDominatedBy_nil_of_positive_slot

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

/-! ### TaskFeasibility role contracts.

`Recipe`, `Reachable`, `satN`, `closureItems` clash with `RecipeClosure`'s
definitions of the same names; we fully-qualify the `TaskFeasibility` ones. -/

-- worst_eq_max_unmet: returned required_level = MAX craftLevel over the UNMET
-- items in the craft closure of the task item.
example : ∀ (r : Formal.TaskFeasibility.Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : Formal.TaskFeasibility.HasSkill) (craftLevel : Formal.TaskFeasibility.CraftLevel)
    (skillLevel : Formal.TaskFeasibility.SkillLevel),
    Formal.TaskFeasibility.worstLevel r roots fuel hasSkill craftLevel skillLevel
      = Formal.TaskFeasibility.listMax craftLevel
          (Formal.TaskFeasibility.unmetItems r roots fuel hasSkill craftLevel skillLevel) :=
  @Formal.TaskFeasibility.worst_eq_max_unmet
-- worst_is_max: every unmet closure item's craftLevel ≤ the returned worst (it
-- truly is the maximum).
example : ∀ (r : Formal.TaskFeasibility.Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : Formal.TaskFeasibility.HasSkill) (craftLevel : Formal.TaskFeasibility.CraftLevel)
    (skillLevel : Formal.TaskFeasibility.SkillLevel) {m : Nat},
    m ∈ Formal.TaskFeasibility.unmetItems r roots fuel hasSkill craftLevel skillLevel →
    craftLevel m ≤ Formal.TaskFeasibility.worstLevel r roots fuel hasSkill craftLevel skillLevel :=
  @Formal.TaskFeasibility.worst_is_max
-- none_iff_no_unmet: under positive craft levels, result is None (worst = 0) IFF
-- no closure item is unmet — the operational feasibility condition.
example : ∀ (r : Formal.TaskFeasibility.Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : Formal.TaskFeasibility.HasSkill) (craftLevel : Formal.TaskFeasibility.CraftLevel)
    (skillLevel : Formal.TaskFeasibility.SkillLevel),
    (∀ m ∈ Formal.TaskFeasibility.closureItems r roots fuel,
        Formal.TaskFeasibility.unmet hasSkill craftLevel skillLevel m = true → 0 < craftLevel m) →
    (Formal.TaskFeasibility.worstLevel r roots fuel hasSkill craftLevel skillLevel = 0
      ↔ ∀ m ∈ Formal.TaskFeasibility.closureItems r roots fuel,
          Formal.TaskFeasibility.unmet hasSkill craftLevel skillLevel m = false) :=
  @Formal.TaskFeasibility.none_iff_no_unmet
-- worst_is_real_gap: a positive result is a GENUINE gap — ∃ reachable item that
-- is unmet at exactly the returned level.
example : ∀ (r : Formal.TaskFeasibility.Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : Formal.TaskFeasibility.HasSkill) (craftLevel : Formal.TaskFeasibility.CraftLevel)
    (skillLevel : Formal.TaskFeasibility.SkillLevel),
    0 < Formal.TaskFeasibility.worstLevel r roots fuel hasSkill craftLevel skillLevel →
    ∃ m, Formal.TaskFeasibility.Reachable r roots m ∧
      Formal.TaskFeasibility.unmet hasSkill craftLevel skillLevel m = true ∧
      craftLevel m = Formal.TaskFeasibility.worstLevel r roots fuel hasSkill craftLevel skillLevel :=
  @Formal.TaskFeasibility.worst_is_real_gap
-- monster_gate: the gate fires IFF 0 < monster_level ∧ char_level + 2 < monster_level
-- (independent arithmetic spec, not X ↔ X).
example : ∀ (monsterLevel charLevel : Nat),
    Formal.TaskFeasibility.monsterGates monsterLevel charLevel = true
      ↔ (0 < monsterLevel ∧ charLevel + 2 < monsterLevel) :=
  @Formal.TaskFeasibility.monster_gate
-- monster_gate_boundary_false: monster EXACTLY at char_level + 2 does NOT gate
-- (off-by-one anchor — would be TRUE under a ≥-margin bug).
example : ∀ (charLevel : Nat),
    Formal.TaskFeasibility.monsterGates (charLevel + 2) charLevel = false :=
  @Formal.TaskFeasibility.monster_gate_boundary_false
-- monster_gate_just_past: monster at char_level + 3 DOES gate (other side of anchor).
example : ∀ (charLevel : Nat),
    Formal.TaskFeasibility.monsterGates (charLevel + 3) charLevel = true :=
  @Formal.TaskFeasibility.monster_gate_just_past
-- monster_gate_zero_never: monster_level = 0 never gates.
example : ∀ (charLevel : Nat),
    Formal.TaskFeasibility.monsterGates 0 charLevel = false :=
  @Formal.TaskFeasibility.monster_gate_zero_never

/-! ### PrerequisiteGraph role contracts. -/

-- prereqs_recipe_with_skill: craftable item WITH a crafting skill ⇒ EXACTLY the
-- skill edge first, then one item edge per ingredient (data-derived edge set).
example : ∀ (ingredients : List (Nat × Nat)) (s l : Nat)
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat),
    Formal.PrerequisiteGraph.prereqEdges (some ingredients) (some (s, l)) resDrops code
      = Formal.PrerequisiteGraph.Edge.skill s l ::
          ingredients.map (fun p => Formal.PrerequisiteGraph.Edge.item p.1 p.2) :=
  @Formal.PrerequisiteGraph.prereqs_recipe_with_skill
-- prereqs_recipe_no_skill: craftable item with NO crafting skill ⇒ EXACTLY one
-- item edge per ingredient and NO skill edge.
example : ∀ (ingredients : List (Nat × Nat))
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat),
    Formal.PrerequisiteGraph.prereqEdges (some ingredients) none resDrops code
      = ingredients.map (fun p => Formal.PrerequisiteGraph.Edge.item p.1 p.2) :=
  @Formal.PrerequisiteGraph.prereqs_recipe_no_skill
-- prereqs_membership: EXACT edge set for a craftable item — an edge is present
-- IFF it is the skill edge (skill present) OR an item edge of some ingredient.
example : ∀ (ingredients : List (Nat × Nat)) (craftSkill : Option (Nat × Nat))
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat)
    (e : Formal.PrerequisiteGraph.Edge),
    e ∈ Formal.PrerequisiteGraph.prereqEdges (some ingredients) craftSkill resDrops code
      ↔ (∃ s l, craftSkill = some (s, l) ∧ e = Formal.PrerequisiteGraph.Edge.skill s l)
        ∨ (∃ mat qty, (mat, qty) ∈ ingredients ∧ e = Formal.PrerequisiteGraph.Edge.item mat qty) :=
  @Formal.PrerequisiteGraph.prereqs_membership
-- prereqs_resource: NON-craftable item whose first matching resource drop has a
-- skill ⇒ EXACTLY that single resource-skill edge.
example : ∀ (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code s l : Nat),
    Formal.PrerequisiteGraph.firstResSkill resDrops code = some (s, l) →
    Formal.PrerequisiteGraph.prereqEdges none none resDrops code
      = [Formal.PrerequisiteGraph.Edge.skill s l] :=
  @Formal.PrerequisiteGraph.prereqs_resource
-- prereqs_leaf: NON-craftable, non-resource item ⇒ LEAF (no prerequisites).
example : ∀ (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat),
    Formal.PrerequisiteGraph.firstResSkill resDrops code = none →
    Formal.PrerequisiteGraph.prereqEdges none none resDrops code = [] :=
  @Formal.PrerequisiteGraph.prereqs_leaf
-- resource_branch_no_item: the resource branch NEVER emits an item edge (recipe
-- is the only source of item edges).
example : ∀ (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code c q : Nat),
    Formal.PrerequisiteGraph.Edge.item c q
      ∉ Formal.PrerequisiteGraph.prereqEdges none none resDrops code :=
  @Formal.PrerequisiteGraph.resource_branch_no_item
-- combat_capable_iff: combat_capable ↔ ∃ beatable monster (independent
-- existential, NOT the any-fold reapplied).
example : ∀ (beatable : Nat → Bool) (monsters : List Nat),
    Formal.PrerequisiteGraph.combatCapable beatable monsters = true
      ↔ ∃ m ∈ monsters, beatable m = true :=
  @Formal.PrerequisiteGraph.combat_capable_iff
-- combat_capable_demorgan: ¬combat_capable ↔ EVERY monster unbeatable (De Morgan
-- dual — catches an any→all mutation).
example : ∀ (beatable : Nat → Bool) (monsters : List Nat),
    Formal.PrerequisiteGraph.combatCapable beatable monsters = false
      ↔ ∀ m ∈ monsters, beatable m = false :=
  @Formal.PrerequisiteGraph.combat_capable_demorgan
-- combat_capable_empty: no monsters ⇒ never capable (any of [] = false, ≠ all).
example : ∀ (beatable : Nat → Bool),
    Formal.PrerequisiteGraph.combatCapable beatable [] = false :=
  @Formal.PrerequisiteGraph.combat_capable_empty

/-! ### Objective role contracts.

`Recipe` clashes with `RecipeClosure`/`TaskFeasibility`; we fully-qualify the
`Objective` ones. -/

-- is_attainable = grounding fixpoint: SOUNDNESS (accept ⇒ Grounded, any fuel) +
-- COMPLETENESS (Grounded ⇒ accepted for all adequate fuel). A cyclic recipe or a
-- drop-only-but-not-grounded component is NOT Grounded, hence NOT attainable.
example : ∀ (r : Formal.Objective.Recipe) (hasRec : Formal.Objective.HasRecipe)
    (drop : Formal.Objective.IsDrop) (item : Nat),
    (∀ fuel, Formal.Objective.isAttainable r hasRec drop fuel item = true →
        Formal.Objective.Grounded r hasRec drop item) ∧
    (Formal.Objective.Grounded r hasRec drop item →
      ∃ N, ∀ fuel, N ≤ fuel → Formal.Objective.isAttainable r hasRec drop fuel item = true) :=
  @Formal.Objective.is_attainable_eq_grounding
-- grounding SOUNDNESS of the saturation: groundedByN accepts only Grounded items.
example : ∀ (r : Formal.Objective.Recipe) (hasRec : Formal.Objective.HasRecipe)
    (drop : Formal.Objective.IsDrop) (n item : Nat),
    Formal.Objective.groundedByN r hasRec drop n item = true →
      Formal.Objective.Grounded r hasRec drop item :=
  @Formal.Objective.groundedByN_sound
-- grounding COMPLETENESS of the saturation: every Grounded item appears in a round.
example : ∀ (r : Formal.Objective.Recipe) (hasRec : Formal.Objective.HasRecipe)
    (drop : Formal.Objective.IsDrop) {item : Nat},
    Formal.Objective.Grounded r hasRec drop item →
      ∃ n, Formal.Objective.groundedByN r hasRec drop n item = true :=
  @Formal.Objective.grounded_groundedByN
-- best_gear_argmax: the chosen first-slot item IS attainable, IS a candidate, and
-- ranks ≥ every attainable candidate under (-value, code) — the genuine argmax.
example : ∀ (attain : Formal.Objective.Gear → Bool) (items : List Formal.Objective.Gear)
    (chosen : Formal.Objective.Gear),
    Formal.Objective.bestAttainableGear attain items = some chosen →
    attain chosen = true ∧ chosen ∈ items ∧
    (∀ y ∈ items, attain y = true →
      chosen.value > y.value ∨ (chosen.value = y.value ∧ chosen.code ≤ y.code)) :=
  @Formal.Objective.best_gear_argmax
-- gap_nonneg: the gap-sum numerator is ≥ 0 (each per-axis gap is max(0, …)).
example : ∀ (pairs : List (Int × Int)), 0 ≤ Formal.Objective.gapSum pairs :=
  @Formal.Objective.gapSum_nonneg
-- gap_le_denom: nonneg haves AND nonneg targets ⇒ gapSum ≤ targetSum, so with
-- gapSum_nonneg the fraction gapSum/targetSum ∈ [0,1] (integer-only bound).
example : ∀ (pairs : List (Int × Int)),
    (∀ p ∈ pairs, 0 ≤ p.2) → (∀ p ∈ pairs, 0 ≤ p.1) →
    Formal.Objective.gapSum pairs ≤ Formal.Objective.targetSum pairs :=
  @Formal.Objective.gapSum_le_targetSum
-- charGap_bounds: 0 ≤ char gap ≤ target (so the char fraction ∈ [0,1]).
example : ∀ (targetLevel level : Int), 0 ≤ level → 0 ≤ targetLevel →
    0 ≤ Formal.Objective.axisGap targetLevel level ∧
    Formal.Objective.axisGap targetLevel level ≤ targetLevel :=
  @Formal.Objective.charGap_bounds
-- is_complete_iff: is_complete ↔ INDEPENDENT raw-target form (char gap 0 ∧ every
-- skill gap 0 ∧ every gear gap 0) — NOT a restatement of is_complete's own body.
example : ∀ (charGap : Int) (skillPairs gearPairs : List (Int × Int)),
    Formal.Objective.isComplete charGap skillPairs gearPairs = true ↔
      (charGap = 0 ∧
       (∀ p ∈ skillPairs, Formal.Objective.axisGap p.1 p.2 = 0) ∧
       (∀ p ∈ gearPairs, Formal.Objective.axisGap p.1 p.2 = 0)) :=
  @Formal.Objective.is_complete_iff
-- axisGap_zero_iff: a per-axis gap is 0 ↔ the raw target is met (have ≥ target).
example : ∀ (target have_ : Int),
    Formal.Objective.axisGap target have_ = 0 ↔ target ≤ have_ :=
  @Formal.Objective.axisGap_zero_iff

/-! ### StrategyTraversal role contracts.

`Grounded`, `groundedByN`, `IsMinRound` etc. are namespaced; we fully-qualify the
`StrategyTraversal` ones to avoid clashes with `Objective` / `RecipeClosure`. -/

-- is_reachable = grounding fixpoint: SOUNDNESS (accept ⇒ Grounded, any fuel) +
-- COMPLETENESS (Grounded ⇒ accepted for all adequate fuel). A node on a cycle of
-- un-grounded nodes is NOT Grounded, hence NOT reachable.
example : ∀ (g : Formal.StrategyTraversal.Graph) (node : Nat),
    (∀ fuel, Formal.StrategyTraversal.isReachable g fuel node = true →
        Formal.StrategyTraversal.Grounded g node) ∧
    (Formal.StrategyTraversal.Grounded g node →
      ∃ N, ∀ fuel, N ≤ fuel → Formal.StrategyTraversal.isReachable g fuel node = true) :=
  @Formal.StrategyTraversal.is_reachable_eq_grounding
-- grounding SOUNDNESS of the saturation.
example : ∀ (g : Formal.StrategyTraversal.Graph) (n node : Nat),
    Formal.StrategyTraversal.groundedByN g n node = true →
      Formal.StrategyTraversal.Grounded g node :=
  @Formal.StrategyTraversal.groundedByN_sound
-- grounding COMPLETENESS of the saturation.
example : ∀ (g : Formal.StrategyTraversal.Graph) {node : Nat},
    Formal.StrategyTraversal.Grounded g node →
      ∃ n, Formal.StrategyTraversal.groundedByN g n node = true :=
  @Formal.StrategyTraversal.grounded_groundedByN
-- reachAux SOUNDNESS: accept ⇒ Grounded (any path/fuel) — the cycle guard only rejects.
example : ∀ (g : Formal.StrategyTraversal.Graph) (fuel : Nat) (path : List Nat) (node : Nat),
    Formal.StrategyTraversal.reachAux g fuel path node = true →
      Formal.StrategyTraversal.Grounded g node :=
  @Formal.StrategyTraversal.reachAux_sound
-- closure_size ≥ 1: the unmet-closure count is floored at 1 (the `max(·,1)`).
example : ∀ (g : Formal.StrategyTraversal.Graph) (root fuel : Nat),
    1 ≤ Formal.StrategyTraversal.unmetClosureSize g root fuel :=
  @Formal.StrategyTraversal.unmetClosureSize_ge_one
-- closure_size = count of distinct UNMET nodes in the visited set (satisfied-
-- interior pruning faithful: the count filters out satisfied nodes), floored at 1.
example : ∀ (g : Formal.StrategyTraversal.Graph) (root fuel : Nat),
    Formal.StrategyTraversal.unmetClosureSize g root fuel
      = max ((Formal.StrategyTraversal.unmetSatN g root fuel).eraseDups.filter
              (fun n => !g.isSat n)).length 1 :=
  @Formal.StrategyTraversal.unmetClosureSize_eq_count
-- every counted closure node is UNMET (no satisfied node is ever counted).
example : ∀ (g : Formal.StrategyTraversal.Graph) (root fuel : Nat) {n : Nat},
    n ∈ Formal.StrategyTraversal.unmetNodes g root fuel → g.isSat n = false :=
  @Formal.StrategyTraversal.unmetNodes_unmet
-- actionable_correct (SOUNDNESS): the RETURNED node (entered on an unmet root) is
-- ActionableNode — unmet ∧ all direct prereqs satisfied ∧ (obtain ⇒ producible).
example : ∀ (g : Formal.StrategyTraversal.Graph) (fuel root r : Nat),
    g.isSat root = false →
    Formal.StrategyTraversal.actionableStep g fuel root = some r →
      Formal.StrategyTraversal.ActionableNode g r :=
  @Formal.StrategyTraversal.actionable_step_sound
-- actionable_correct (NONE half): eventually-none ↔ NO actionable node is reachable
-- from root via unmet-prereq descent — an INDEPENDENT De-Morgan characterization of
-- the actionable set (ActionableNode predicate + UnmetReach relation), not the
-- function restated.
example : ∀ (g : Formal.StrategyTraversal.Graph) (root : Nat),
    g.isSat root = false →
    ((∃ N, ∀ fuel, N ≤ fuel → Formal.StrategyTraversal.actionableStep g fuel root = none)
      ↔ ¬ ∃ a, Formal.StrategyTraversal.UnmetReach g root a ∧
            Formal.StrategyTraversal.ActionableNode g a) :=
  @Formal.StrategyTraversal.actionable_step_none_iff
-- the returned node is UnmetReach-able from root (lives in the unmet closure).
example : ∀ (g : Formal.StrategyTraversal.Graph) (fuel root r : Nat),
    g.isSat root = false →
    Formal.StrategyTraversal.actionableStep g fuel root = some r →
      Formal.StrategyTraversal.UnmetReach g root r :=
  @Formal.StrategyTraversal.actionable_step_reach
-- root_cost ≥ 1: the effort proxy is floored at 1 for EVERY root kind.
example : ∀ (g : Formal.StrategyTraversal.Graph) (kind : Formal.StrategyTraversal.Kind)
    (target have_ root fuel : Nat),
    1 ≤ Formal.StrategyTraversal.rootCost g kind target have_ root fuel :=
  @Formal.StrategyTraversal.rootCost_ge_one
-- reachable-implies-actionable (THE PRODUCTION ASSERT, strategy.decide:251): for a
-- WELL-FORMED graph and an UNMET root, `is_reachable root = true` (the decide guard)
-- ⇒ for all adequate fuel `actionable_step root ≠ none`. So `assert step is not None`
-- never fires. The two functions' DIFFERENT cycle-trackers (per-path `path` vs shared
-- `visited`) cannot diverge: an actionable node has no unmet prereqs so it is returned
-- the FIRST time reached — the shared visited set never blocks a reachable one.
example : ∀ (g : Formal.StrategyTraversal.Graph),
    Formal.StrategyTraversal.WellFormed g →
    ∀ (fuel root : Nat), g.isSat root = false →
      Formal.StrategyTraversal.isReachable g fuel root = true →
        ∃ N, ∀ fuel', N ≤ fuel' →
          Formal.StrategyTraversal.actionableStep g fuel' root ≠ none :=
  @Formal.StrategyTraversal.reachable_implies_actionable
-- the bridge graph-fact: an unmet Grounded (reachable) node has a reachable
-- ActionableNode descendant (independent of cycle-tracking).
example : ∀ (g : Formal.StrategyTraversal.Graph),
    Formal.StrategyTraversal.WellFormed g →
    ∀ {node : Nat}, Formal.StrategyTraversal.Grounded g node → g.isSat node = false →
      ∃ a, Formal.StrategyTraversal.UnmetReach g node a ∧
           Formal.StrategyTraversal.ActionableNode g a :=
  @Formal.StrategyTraversal.grounded_unmet_has_actionable

/-! ### BankSelection role contracts.

`Recipe`, `Reachable`, `satN`, `closureItems`, `childrenOf` are REUSED from
`RecipeClosure` (opened above); the `BankSelection` defs are namespaced. -/

-- deposits_exact: the deposit candidates are EXACTLY the inventory entries with
-- qty>0 and code ∉ keep (membership characterization, pre-sort).
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) (cq : Nat × Nat),
    cq ∈ Formal.BankSelection.depositCandidates s fuel
      ↔ cq ∈ s.inventory ∧ cq.2 > 0 ∧ cq.1 ∉ Formal.BankSelection.keepList s fuel :=
  @Formal.BankSelection.deposits_exact
-- deposits_mem_iff: the SORTED deposit list deposits exactly the same entries
-- (the sort is a permutation — same set, reordered).
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) (cq : Nat × Nat),
    cq ∈ Formal.BankSelection.deposits s fuel
      ↔ cq ∈ s.inventory ∧ cq.2 > 0 ∧ cq.1 ∉ Formal.BankSelection.keepList s fuel :=
  @Formal.BankSelection.deposits_mem_iff
-- freeze_invariant: NO deposited code is in the keep set (deposits ∩ keep = ∅) —
-- the PursueTask-freeze guarantee, a protected item is NEVER banked.
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) (cq : Nat × Nat),
    cq ∈ Formal.BankSelection.deposits s fuel →
      cq.1 ∉ Formal.BankSelection.keepList s fuel :=
  @Formal.BankSelection.freeze_invariant
-- task_inputs_protected: every captured recipe material of the protected roots
-- (crafting target ∪ items-task code) is in the keep set.
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) {m : Nat},
    m ∈ Formal.BankSelection.recipeMaterialList s fuel →
      m ∈ Formal.BankSelection.keepList s fuel :=
  @Formal.BankSelection.task_inputs_protected
-- task_material_not_deposited: a protected recipe material is NEVER deposited (the
-- direct freeze guarantee for task inputs — the documented Robby-8/20 freeze).
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) (cq : Nat × Nat),
    cq.1 ∈ Formal.BankSelection.recipeMaterialList s fuel →
      cq ∉ Formal.BankSelection.deposits s fuel :=
  @Formal.BankSelection.task_material_not_deposited
-- keep_closed: every captured recipe material is BOTH in the keep set AND a
-- genuine StepReachable material (the reused least-fixpoint walk is sound + the
-- keep set contains it).
example : ∀ (s : Formal.BankSelection.State) (fuel : Nat) {m : Nat},
    m ∈ Formal.BankSelection.recipeMaterialList s fuel →
      m ∈ Formal.BankSelection.keepList s fuel ∧ Formal.BankSelection.recipeMaterials s m :=
  @Formal.BankSelection.keep_closed
-- recipeMaterials_closed: the recipe-material set is CLOSED under taking further
-- recipe children — once a material is protected, all its sub-materials are too
-- (the closure property of the walk over the reused recipe-child relation).
example : ∀ (s : Formal.BankSelection.State) {item child : Nat},
    Formal.BankSelection.recipeMaterials s item →
    child ∈ (s.recipe item).map Prod.fst →
      Formal.BankSelection.recipeMaterials s child :=
  @Formal.BankSelection.recipeMaterials_closed
-- recipeMaterialList_complete: any material reached via a recipe edge from an item
-- captured at round n ≤ fuel is in the material list (COMPLETENESS — with adequate
-- fuel the full StepReachable closure is kept).
example : ∀ (s : Formal.BankSelection.State) (fuel n : Nat), n ≤ fuel →
    ∀ {item m : Nat}, item ∈ satN s.recipe (Formal.BankSelection.recipeRoots s) n →
    m ∈ (s.recipe item).map Prod.fst →
      m ∈ Formal.BankSelection.recipeMaterialList s fuel :=
  @Formal.BankSelection.recipeMaterialList_complete
-- best_weapon_argmax: the best fighting weapon's attack is ≥ EVERY fighting-weapon
-- candidate's attack — the genuine argmax (max-attack non-tool weapon) over
-- inventory ∪ equipped.
example : ∀ (s : Formal.BankSelection.State) (c : Nat),
    Formal.BankSelection.bestWeaponCode s = some c →
    ∀ y ∈ Formal.BankSelection.weaponCandidates s,
      Formal.BankSelection.isFightingWeapon s y = true → s.attack y ≤ s.attack c :=
  @Formal.BankSelection.best_weapon_argmax
-- best_weapon_is_fighting: the chosen best weapon is a fighting weapon (a weapon,
-- not a tool) — tools (skill_effects) are excluded.
example : ∀ (s : Formal.BankSelection.State) (c : Nat),
    Formal.BankSelection.bestWeaponCode s = some c →
      Formal.BankSelection.isFightingWeapon s c = true :=
  @Formal.BankSelection.best_weapon_is_fighting

/-! ### StuckDetector role contracts.

The deterministic stuck-state machine. Statements pin the INDEX ARITHMETIC of
`_recent_since` (the historical off-by-one), the strict detect precedence, the
exact thresholds, and acknowledge suppression. -/

-- recent_since_window: `_recent_since(cutoff,count)` = keep buffered records whose
-- GLOBAL index `startIdx + i ≥ cutoff`, then take the LAST `count` (the exact index
-- arithmetic; a `± 1` start-index perturbation is a different function).
example : ∀ (d : Formal.StuckDetector.Detector) (cutoff count : Nat),
    Formal.StuckDetector.recentSince d cutoff count
      = Formal.StuckDetector.takeLast count
          (((List.range d.history.length).zip d.history
            |>.filter (fun p => decide (Formal.StuckDetector.startIdx d + p.1 ≥ cutoff))).map
              Prod.snd) :=
  @Formal.StuckDetector.recent_since_window
-- recentSince_mem_global: every kept record came from a buffer position whose
-- GLOBAL index clears the cutoff (the filter genuinely uses `startIdx + i`).
example : ∀ (d : Formal.StuckDetector.Detector) (cutoff count : Nat) (r : Formal.StuckDetector.Rec),
    r ∈ Formal.StuckDetector.recentSince d cutoff count →
      ∃ i, i < d.history.length ∧
        Formal.StuckDetector.startIdx d + i ≥ cutoff ∧ d.history[i]? = some r :=
  @Formal.StuckDetector.recentSince_mem_global
-- detect_precedence: strict order frozen > osc > noprog, else none (the cascade).
example : ∀ (d : Formal.StuckDetector.Detector),
    (Formal.StuckDetector.checkStateFrozen d = true →
      Formal.StuckDetector.detect d = some Formal.StuckDetector.Signal.frozen) ∧
    (Formal.StuckDetector.checkStateFrozen d = false →
      Formal.StuckDetector.checkGoalOscillation d = true →
      Formal.StuckDetector.detect d = some Formal.StuckDetector.Signal.osc) ∧
    (Formal.StuckDetector.checkStateFrozen d = false →
      Formal.StuckDetector.checkGoalOscillation d = false →
      Formal.StuckDetector.checkNoProgress d = true →
      Formal.StuckDetector.detect d = some Formal.StuckDetector.Signal.noprog) ∧
    (Formal.StuckDetector.checkStateFrozen d = false →
      Formal.StuckDetector.checkGoalOscillation d = false →
      Formal.StuckDetector.checkNoProgress d = false →
      Formal.StuckDetector.detect d = none) :=
  @Formal.StuckDetector.detect_precedence
-- detect_frozen_wins: frozen check holding forces frozen even if osc/noprog hold.
example : ∀ (d : Formal.StuckDetector.Detector),
    Formal.StuckDetector.checkStateFrozen d = true →
      Formal.StuckDetector.detect d = some Formal.StuckDetector.Signal.frozen :=
  @Formal.StuckDetector.detect_frozen_wins
-- detect_osc_over_noprog: frozen false ∧ osc true ⇒ osc wins over noprog.
example : ∀ (d : Formal.StuckDetector.Detector),
    Formal.StuckDetector.checkStateFrozen d = false →
    Formal.StuckDetector.checkGoalOscillation d = true →
      Formal.StuckDetector.detect d = some Formal.StuckDetector.Signal.osc :=
  @Formal.StuckDetector.detect_osc_over_noprog
-- noprog_threshold: noprog ↔ post-ack last-4 window is full (= 4) ∧ all <no_plan>.
example : ∀ (d : Formal.StuckDetector.Detector),
    Formal.StuckDetector.checkNoProgress d = true
      ↔ ((Formal.StuckDetector.recentSince d d.ackNoprog
            Formal.StuckDetector.noprogThreshold).length = Formal.StuckDetector.noprogThreshold ∧
          (Formal.StuckDetector.recentSince d d.ackNoprog
            Formal.StuckDetector.noprogThreshold).all (fun r => r.noPlan) = true) :=
  @Formal.StuckDetector.noprog_threshold
-- osc_threshold: osc ↔ post-ack last-8 window full (= 8) ∧ EXACTLY 2 distinct goals.
example : ∀ (d : Formal.StuckDetector.Detector),
    Formal.StuckDetector.checkGoalOscillation d = true
      ↔ ((Formal.StuckDetector.recentSince d d.ackOsc
            Formal.StuckDetector.oscThreshold).length = Formal.StuckDetector.oscThreshold ∧
          (Formal.StuckDetector.distinctGoals (Formal.StuckDetector.recentSince d d.ackOsc
            Formal.StuckDetector.oscThreshold)).length = 2) :=
  @Formal.StuckDetector.osc_threshold
-- frozen_threshold: frozen ↔ post-ack last-10 window full (= 10) ∧ some state ≥ 5.
example : ∀ (d : Formal.StuckDetector.Detector),
    Formal.StuckDetector.checkStateFrozen d = true
      ↔ ((Formal.StuckDetector.recentSince d d.ackFrozen
            Formal.StuckDetector.frozenThreshold).length = Formal.StuckDetector.frozenThreshold ∧
          ∃ r ∈ Formal.StuckDetector.recentSince d d.ackFrozen Formal.StuckDetector.frozenThreshold,
            Formal.StuckDetector.stateCount r.state
              (Formal.StuckDetector.recentSince d d.ackFrozen
                Formal.StuckDetector.frozenThreshold) ≥ 5) :=
  @Formal.StuckDetector.frozen_threshold
-- ack_suppression (noprog): immediately after acknowledge(noprog) the noprog
-- window is EMPTY (cutoff = counter excludes every buffered record).
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.recentSince (Formal.StuckDetector.acknowledge d
        Formal.StuckDetector.Signal.noprog)
      (Formal.StuckDetector.acknowledge d Formal.StuckDetector.Signal.noprog).ackNoprog
      Formal.StuckDetector.noprogThreshold = [] :=
  @Formal.StuckDetector.ack_suppression_noprog
-- ack_suppression (frozen) / (osc): same emptiness for the other windows.
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.recentSince (Formal.StuckDetector.acknowledge d
        Formal.StuckDetector.Signal.frozen)
      (Formal.StuckDetector.acknowledge d Formal.StuckDetector.Signal.frozen).ackFrozen
      Formal.StuckDetector.frozenThreshold = [] :=
  @Formal.StuckDetector.ack_suppression_frozen
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.recentSince (Formal.StuckDetector.acknowledge d
        Formal.StuckDetector.Signal.osc)
      (Formal.StuckDetector.acknowledge d Formal.StuckDetector.Signal.osc).ackOsc
      Formal.StuckDetector.oscThreshold = [] :=
  @Formal.StuckDetector.ack_suppression_osc
-- ack_*_cannot_fire: an empty post-ack window can never meet the threshold, so
-- the just-acked signal cannot re-fire until ≥ threshold fresh records accumulate.
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.checkNoProgress (Formal.StuckDetector.acknowledge d
      Formal.StuckDetector.Signal.noprog) = false :=
  @Formal.StuckDetector.ack_noprog_cannot_fire
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.checkStateFrozen (Formal.StuckDetector.acknowledge d
      Formal.StuckDetector.Signal.frozen) = false :=
  @Formal.StuckDetector.ack_frozen_cannot_fire
example : ∀ (d : Formal.StuckDetector.Detector), d.history.length ≤ d.counter →
    Formal.StuckDetector.checkGoalOscillation (Formal.StuckDetector.acknowledge d
      Formal.StuckDetector.Signal.osc) = false :=
  @Formal.StuckDetector.ack_osc_cannot_fire

/-! ### PriorityBand role contracts.

The discretionary-band clamp. Statements pin both band bounds and the key
survival-floor safety property (a clamped discretionary priority is strictly
below the survival floor for ANY bonus). -/

-- band-lower: floor ≤ clampIntoBand floor ceiling bonus (given floor ≤ ceiling).
example : ∀ (floor ceiling bonus : Rat), floor ≤ ceiling →
    floor ≤ Formal.PriorityBand.clampIntoBand floor ceiling bonus :=
  @Formal.PriorityBand.clamp_lower_bound
-- band-upper: clampIntoBand floor ceiling bonus ≤ ceiling (given floor ≤ ceiling).
example : ∀ (floor ceiling bonus : Rat), floor ≤ ceiling →
    Formal.PriorityBand.clampIntoBand floor ceiling bonus ≤ ceiling :=
  @Formal.PriorityBand.clamp_upper_bound
-- survival-floor-safety: ceiling < survival ⇒ clamped result < survival (any bonus).
example : ∀ (floor ceiling bonus survival : Rat), floor ≤ ceiling → ceiling < survival →
    Formal.PriorityBand.clampIntoBand floor ceiling bonus < survival :=
  @Formal.PriorityBand.clamp_below_survival

/-! ### OwnedCount role contracts.

The owned-count satisfaction primitive. The equipped copy lives in a separate
server slot from the inventory list (equipping decrements inventory), so the
count is the unconditional sum of three disjoint stores: spares + bank + equipped.
Statements pin (1) that exact summation, (2) that an item owned only by wearing it
still counts (no re-acquire loop), and (3) monotonicity in the spare store. -/

-- owned-count-sum: count = spares + bank + (1 if equipped), unconditionally.
example : ∀ (inv bank : String → Nat) (equipped : String → Bool) (code : String),
    Formal.OwnedCount.ownedCount inv bank equipped code
      = inv code + bank code + (if equipped code then 1 else 0) :=
  @Formal.OwnedCount.ownedCount_eq_total
-- owned-count-counts-equipped: an equipped item counts as owned (≥ 1) even with
-- zero spares and zero bank.
example : ∀ (inv bank : String → Nat) (equipped : String → Bool) (code : String),
    equipped code = true →
    Formal.OwnedCount.ownedCount inv bank equipped code ≥ 1 :=
  @Formal.OwnedCount.ownedCount_counts_equipped
-- owned-count-monotone: count is non-decreasing in the spare store.
example : ∀ (inv inv' bank : String → Nat) (equipped : String → Bool) (code : String),
    inv code ≤ inv' code →
    Formal.OwnedCount.ownedCount inv bank equipped code
      ≤ Formal.OwnedCount.ownedCount inv' bank equipped code :=
  @Formal.OwnedCount.ownedCount_monotone

/-! ### UpgradeSelection role contracts.

The pure upgrade-selection cores. Statements pin (1) best_by_value never returns
the strictly-worse pick and ties go to inventory, (2) the two lexicographic key
comparators are each a strict total order (trichotomy + antisymmetry +
transitivity + eq-forces-equal-code determinism), (3) a committed target is
returned EXACTLY (never substituted), and (4) best_by_key is a sound argmax. -/

-- best-no-downgrade: best_by_value of two picks has value ≥ both (never worse).
example : ∀ (inv craft : Formal.UpgradeSelection.Candidate),
    ∃ r, Formal.UpgradeSelection.bestByValue (some inv) (some craft) = some r ∧
      inv.value ≤ r.value ∧ craft.value ≤ r.value :=
  @Formal.UpgradeSelection.best_by_value_not_worse
-- best-no-downgrade: a tie (equal value) returns the inventory pick exactly.
example : ∀ (inv craft : Formal.UpgradeSelection.Candidate), inv.value = craft.value →
    Formal.UpgradeSelection.bestByValue (some inv) (some craft) = some inv :=
  @Formal.UpgradeSelection.best_by_value_tie_inv
-- key-total-order: craftable comparator is trichotomous.
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.craftableCmp a b = .lt ∨
    Formal.UpgradeSelection.craftableCmp a b = .eq ∨
    Formal.UpgradeSelection.craftableCmp a b = .gt :=
  @Formal.UpgradeSelection.craftableCmp_trichotomy
-- key-total-order: craftable comparator is antisymmetric (swap = .swap).
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.craftableCmp b a = (Formal.UpgradeSelection.craftableCmp a b).swap :=
  @Formal.UpgradeSelection.craftableCmp_swap
-- key-total-order: craftable comparator is transitive on `.lt`.
example : ∀ {a b c : Formal.UpgradeSelection.Candidate},
    Formal.UpgradeSelection.craftableCmp a b = .lt →
    Formal.UpgradeSelection.craftableCmp b c = .lt →
    Formal.UpgradeSelection.craftableCmp a c = .lt :=
  @Formal.UpgradeSelection.craftableCmp_lt_trans
-- key-total-order: craftable `eq` forces equal item codes (distinct codes never tie).
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.craftableCmp a b = .eq → a.itemCode = b.itemCode :=
  @Formal.UpgradeSelection.craftableCmp_eq_imp_code
-- key-total-order: inventory comparator is trichotomous.
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.inventoryCmp a b = .lt ∨
    Formal.UpgradeSelection.inventoryCmp a b = .eq ∨
    Formal.UpgradeSelection.inventoryCmp a b = .gt :=
  @Formal.UpgradeSelection.inventoryCmp_trichotomy
-- key-total-order: inventory comparator is antisymmetric.
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.inventoryCmp b a = (Formal.UpgradeSelection.inventoryCmp a b).swap :=
  @Formal.UpgradeSelection.inventoryCmp_swap
-- key-total-order: inventory comparator is transitive on `.lt`.
example : ∀ {a b c : Formal.UpgradeSelection.Candidate},
    Formal.UpgradeSelection.inventoryCmp a b = .lt →
    Formal.UpgradeSelection.inventoryCmp b c = .lt →
    Formal.UpgradeSelection.inventoryCmp a c = .lt :=
  @Formal.UpgradeSelection.inventoryCmp_lt_trans
-- key-total-order: inventory `eq` forces equal item codes.
example : ∀ (a b : Formal.UpgradeSelection.Candidate),
    Formal.UpgradeSelection.inventoryCmp a b = .eq → a.itemCode = b.itemCode :=
  @Formal.UpgradeSelection.inventoryCmp_eq_imp_code
-- argmax-sound: best_by_key over a nonempty list returns a member that dominates
-- every element (nothing compares strictly greater).
example : ∀ (cmp : Formal.UpgradeSelection.Candidate → Formal.UpgradeSelection.Candidate → Ordering)
    [Std.OrientedCmp cmp] [Std.TransCmp cmp]
    (x : Formal.UpgradeSelection.Candidate) (xs : List Formal.UpgradeSelection.Candidate),
    ∃ r, Formal.UpgradeSelection.bestByKey cmp (x :: xs) = some r ∧
      r ∈ (x :: xs) ∧ ∀ y ∈ (x :: xs), cmp y r ≠ .gt :=
  @Formal.UpgradeSelection.bestByKey_sound

/-! ### Scalarizer role contracts.

The pure cores of `scalar_yield`/`coins_spent`. The model is EXACT over the
rationals (`Rat`) — the bot's Yield fields are fractional averages, so the
scalar is modeled with no scaling and the proved orderings are faithful to the
real fractional formula. Statements pin: monotonicity in each
non-negative-contribution component (char_xp given level ≥ 0; gold;
tasks_coins given coin_value ≥ 0; a single skill's xp given its weight ≥ 0), the
relevant ≥ baseline weight dominance, and the coin-inversion identity (delta =
received - coins_spent inverts exactly; counts are integers so this stays Int). -/

-- mono-charxp: scalar non-decreasing in char_xp, given level ≥ 0 (game level ≥ 1)
-- and the non-negative char scale.
example : ∀ (charXp charXp' level : Rat) (skills : List Formal.Scalarizer.SkillTerm)
    (gold tasksCoins coinValue charScale goldUnit : Rat),
    0 ≤ level → 0 ≤ charScale → charXp ≤ charXp' →
    Formal.Scalarizer.scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ Formal.Scalarizer.scalarYield charXp' level skills gold tasksCoins coinValue charScale goldUnit :=
  @Formal.Scalarizer.scalarYield_mono_charxp
-- mono-gold: scalar non-decreasing in gold, given the non-negative gold unit.
example : ∀ (charXp level : Rat) (skills : List Formal.Scalarizer.SkillTerm)
    (gold gold' tasksCoins coinValue charScale goldUnit : Rat),
    0 ≤ goldUnit → gold ≤ gold' →
    Formal.Scalarizer.scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ Formal.Scalarizer.scalarYield charXp level skills gold' tasksCoins coinValue charScale goldUnit :=
  @Formal.Scalarizer.scalarYield_mono_gold
-- mono-coins: scalar non-decreasing in tasks_coins, given coin_value ≥ 0 and unit ≥ 0.
example : ∀ (charXp level : Rat) (skills : List Formal.Scalarizer.SkillTerm)
    (gold tasksCoins tasksCoins' coinValue charScale goldUnit : Rat),
    0 ≤ coinValue → 0 ≤ goldUnit → tasksCoins ≤ tasksCoins' →
    Formal.Scalarizer.scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ Formal.Scalarizer.scalarYield charXp level skills gold tasksCoins' coinValue charScale goldUnit :=
  @Formal.Scalarizer.scalarYield_mono_coins
-- mono-skillxp: skill sum non-decreasing in one skill's xp, given its weight ≥ 0.
example : ∀ (w xp xp' : Rat) (rest : List Formal.Scalarizer.SkillTerm),
    0 ≤ w → xp ≤ xp' →
    Formal.Scalarizer.skillSum ((w, xp) :: rest) ≤ Formal.Scalarizer.skillSum ((w, xp') :: rest) :=
  @Formal.Scalarizer.skillSum_mono_one
-- weight-dominance: relevant weight ≥ baseline weight per non-negative xp unit.
example : ∀ (baselineW relevantW xp : Rat),
    baselineW ≤ relevantW → 0 ≤ xp → baselineW * xp ≤ relevantW * xp :=
  @Formal.Scalarizer.relevant_weight_dominates
-- coin-inversion: received - coinsSpent received delta = delta (no sign error).
example : ∀ (received delta : Int),
    received - Formal.Scalarizer.coinsSpent received delta = delta :=
  @Formal.Scalarizer.coinsSpent_inverts

/-! ### PlannerAdmissibility role contracts. AFFIRMATION of planner.py:99
    "first satisfied node popped is least-cost" — post-fix (h ≡ 0, Dijkstra). -/
-- conditional intent: an ADMISSIBLE heuristic forces f = g at a satisfied node —
-- the load-bearing fact that makes "first popped satisfied = least cost" sound.
example : ∀ {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop),
    Formal.PlannerAdmissibility.Admissible h trueRemaining →
    Formal.PlannerAdmissibility.GoalZero trueRemaining sat →
    ∀ (s : α) (g : Nat), sat s → Formal.PlannerAdmissibility.fScore g (h s) = g :=
  @Formal.PlannerAdmissibility.fScore_eq_g_at_goal_of_admissible
-- general A* optimality conditional: admissible h ⇒ first popped satisfied node is least cost.
example : ∀ {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop),
    Formal.PlannerAdmissibility.Admissible h trueRemaining →
    Formal.PlannerAdmissibility.GoalZero trueRemaining sat →
    ∀ (s₁ s₂ : α) (g₁ g₂ : Nat), sat s₁ → sat s₂ →
      Formal.PlannerAdmissibility.fScore g₁ (h s₁) ≤
        Formal.PlannerAdmissibility.fScore g₂ (h s₂) → g₁ ≤ g₂ :=
  @Formal.PlannerAdmissibility.firstSatisfied_least_cost_of_admissible
-- the planner's post-fix h ≡ 0 IS admissible w.r.t. any trueRemaining.
example : ∀ {α : Type} (trueRemaining : α → Nat),
    Formal.PlannerAdmissibility.Admissible (fun _ : α => 0) trueRemaining :=
  @Formal.PlannerAdmissibility.zero_h_admissible
-- RestoreHP instance: optimal (g=7) node pops strictly before rest (g=10).
example : Formal.PlannerAdmissibility.fScore
      Formal.PlannerAdmissibility.RHPoptimalPlanCost
      (Formal.PlannerAdmissibility.RHPh Formal.PlannerAdmissibility.RHPState.eaten)
    < Formal.PlannerAdmissibility.fScore
      Formal.PlannerAdmissibility.RHPrestPlanCost
      (Formal.PlannerAdmissibility.RHPh Formal.PlannerAdmissibility.RHPState.rested) :=
  Formal.PlannerAdmissibility.RHP_optimal_popped_before_rest
-- THE FIX: the planner now returns the optimal plan (cost 7 ≤ rest 10).
example : Formal.PlannerAdmissibility.RHPoptimalPlanCost
    ≤ Formal.PlannerAdmissibility.RHPrestPlanCost :=
  Formal.PlannerAdmissibility.RHP_first_satisfied_is_optimal
-- and the optimum is STRICTLY cheaper than the rest plan.
example : Formal.PlannerAdmissibility.RHPoptimalPlanCost
    < Formal.PlannerAdmissibility.RHPrestPlanCost :=
  Formal.PlannerAdmissibility.RHP_optimal_strictly_cheaper_than_rest

/-! ### TaskDecision role contracts. -/
-- combat-pivots: combat ∨ ¬history ⇒ PIVOT (unconditional safety short-circuit).
example : ∀ (reqIsCombat historyPresent : Bool)
    (skillUpVpc baseline margin confidence : Rat),
    reqIsCombat = true ∨ historyPresent = false →
    Formal.TaskDecision.taskDecisionPure false reqIsCombat historyPresent
        skillUpVpc baseline margin confidence = Formal.TaskDecision.Decision.PIVOT :=
  @Formal.TaskDecision.combat_or_no_history_pivots
-- already-feasible: req None ⇒ PURSUE.
example : ∀ (reqIsCombat historyPresent : Bool)
    (skillUpVpc baseline margin confidence : Rat),
    Formal.TaskDecision.taskDecisionPure true reqIsCombat historyPresent
        skillUpVpc baseline margin confidence = Formal.TaskDecision.Decision.PURSUE :=
  @Formal.TaskDecision.req_none_pursues
-- no-div-by-zero: cross-file invariant (task_total ≥ 1 when reqIsNone = false)
-- forces total_cycles ≥ 1 ⇒ caller's divide-by-total_cycles is safe.
example : ∀ (reqIsNone : Bool) (skillCycles taskTotal : Nat),
    (reqIsNone = false → taskTotal ≥ 1) →
    reqIsNone = false → skillCycles + taskTotal ≥ 1 :=
  @Formal.TaskDecision.no_div_by_zero_from_invariant
-- confidence-monotone (threshold): required_vpc antitone in confidence.
example : ∀ (baseline margin c c' : Rat),
    0 ≤ baseline → 0 ≤ margin → c ≤ c' →
    Formal.TaskDecision.requiredVpc baseline margin c'
      ≤ Formal.TaskDecision.requiredVpc baseline margin c :=
  @Formal.TaskDecision.requiredVpc_antitone_in_confidence
-- confidence-monotone (decision): PURSUE at c is preserved at any c' ≥ c.
example : ∀ (skillUpVpc baseline margin c c' : Rat),
    0 ≤ baseline → 0 ≤ margin → c ≤ c' →
    Formal.TaskDecision.taskDecisionPure false false true skillUpVpc baseline margin c
      = Formal.TaskDecision.Decision.PURSUE →
    Formal.TaskDecision.taskDecisionPure false false true skillUpVpc baseline margin c'
      = Formal.TaskDecision.Decision.PURSUE :=
  @Formal.TaskDecision.decision_pursue_confidence_monotone
-- vpc-monotone: PURSUE at v is preserved at any v' ≥ v.
example : ∀ (v v' baseline margin confidence : Rat),
    v ≤ v' →
    Formal.TaskDecision.taskDecisionPure false false true v baseline margin confidence
      = Formal.TaskDecision.Decision.PURSUE →
    Formal.TaskDecision.taskDecisionPure false false true v' baseline margin confidence
      = Formal.TaskDecision.Decision.PURSUE :=
  @Formal.TaskDecision.decision_pursue_vpc_monotone

/-! ### LowYieldCancel role contracts. -/
-- shell-safety: ¬hasTask ⇒ never fires (unconditional).
example : ∀ (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    Formal.LowYieldCancel.lowYieldFiresPure false currentXp altXp confidence
        farmSamples altSamples margin minConfidence = false :=
  @Formal.LowYieldCancel.no_task_never_fires
-- sample-gate: farm=0 ∨ alt=0 ⇒ never fires.
example : ∀ (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    farmSamples = 0 ∨ altSamples = 0 →
    Formal.LowYieldCancel.lowYieldFiresPure true currentXp altXp confidence
        farmSamples altSamples margin minConfidence = false :=
  @Formal.LowYieldCancel.no_samples_blocks
-- margin-monotone: under positive currentXp and confidence ≥ gate, raising altXp
-- preserves a fire.
example : ∀ (currentXp alt alt' confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    farmSamples ≠ 0 → altSamples ≠ 0 →
    currentXp > 0 → confidence ≥ minConfidence → alt ≤ alt' →
    Formal.LowYieldCancel.lowYieldFiresPure true currentXp alt confidence
        farmSamples altSamples margin minConfidence = true →
    Formal.LowYieldCancel.lowYieldFiresPure true currentXp alt' confidence
        farmSamples altSamples margin minConfidence = true :=
  @Formal.LowYieldCancel.fires_monotone_in_alt
-- zero-fast-path: currentXp = 0 ∧ altXp > 0 ⇒ fires regardless of confidence/sample count
-- (beyond > 0). INTENTIONAL — Robby gudgeon scenario; see LowYieldCancel.lean header.
example : ∀ (altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    farmSamples ≠ 0 → altSamples ≠ 0 → altXp > 0 →
    Formal.LowYieldCancel.lowYieldFiresPure true 0 altXp confidence
        farmSamples altSamples margin minConfidence = true :=
  @Formal.LowYieldCancel.zero_fast_path_fires_unconditionally
-- zero-fast-path concrete witness: confidence = 0 (< 1/2 gate) AND alt_samples = 1
-- AND fires. Pins the bypass as the intended contract.
example :
    Formal.LowYieldCancel.lowYieldFiresPure true 0 1 0 1 1 (3/2) (1/2) = true :=
  Formal.LowYieldCancel.zero_fast_path_fires_with_low_confidence_witness
-- margin soundness: positive currentXp ∧ fires ⇒ altXp ≥ currentXp * margin.
example : ∀ (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    currentXp > 0 →
    Formal.LowYieldCancel.lowYieldFiresPure true currentXp altXp confidence
        farmSamples altSamples margin minConfidence = true →
    altXp ≥ currentXp * margin :=
  @Formal.LowYieldCancel.positive_current_fires_implies_margin
-- confidence soundness: positive currentXp ∧ fires ⇒ confidence ≥ minConfidence.
example : ∀ (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat),
    currentXp > 0 →
    Formal.LowYieldCancel.lowYieldFiresPure true currentXp altXp confidence
        farmSamples altSamples margin minConfidence = true →
    confidence ≥ minConfidence :=
  @Formal.LowYieldCancel.positive_current_fires_implies_confidence

/-! ### StrategyBlend role contracts. -/

example : ∀ (leader current : Int),
    Formal.StrategyBlend.balanceMinScaled
      ≤ Formal.StrategyBlend.balancingScaled leader current :=
  @Formal.StrategyBlend.balancingScaled_ge_min
example : ∀ (leader current : Int),
    Formal.StrategyBlend.balancingScaled leader current
      ≤ Formal.StrategyBlend.balanceMaxScaled :=
  @Formal.StrategyBlend.balancingScaled_le_max
example : ∀ (leader current : Int),
    leader - current = Formal.StrategyBlend.balanceThresh →
    Formal.StrategyBlend.balancingScaled leader current = 4 :=
  @Formal.StrategyBlend.balancingScaled_at_threshold
example : ∀ (s : Int),
    Formal.StrategyBlend.balancingScaled s s = Formal.StrategyBlend.balanceMinScaled :=
  @Formal.StrategyBlend.balancingScaled_at_equal_clamps_to_min
example : ∀ (leader current leader' current' : Int),
    leader - current ≤ leader' - current' →
    Formal.StrategyBlend.balancingScaled leader current
      ≤ Formal.StrategyBlend.balancingScaled leader' current' :=
  @Formal.StrategyBlend.balancingScaled_mono
example : ∀ (value normalized : Rat),
    Formal.StrategyBlend.learnedBlend value normalized 0 = value :=
  @Formal.StrategyBlend.learnedBlend_w_zero
example : ∀ (value normalized : Rat),
    Formal.StrategyBlend.learnedBlend value normalized 1 = normalized :=
  @Formal.StrategyBlend.learnedBlend_w_one
example : ∀ (value normalized w : Rat),
    0 ≤ w → value ≤ normalized →
    value ≤ Formal.StrategyBlend.learnedBlend value normalized w :=
  @Formal.StrategyBlend.learnedBlend_ge_value_when_le
example : ∀ (value normalized w : Rat),
    w ≤ 1 → value ≤ normalized →
    Formal.StrategyBlend.learnedBlend value normalized w ≤ normalized :=
  @Formal.StrategyBlend.learnedBlend_le_normalized_when_le
example : ∀ (value normalized w : Rat),
    w ≤ 1 → normalized ≤ value →
    normalized ≤ Formal.StrategyBlend.learnedBlend value normalized w :=
  @Formal.StrategyBlend.learnedBlend_ge_normalized_when_ge
example : ∀ (value normalized w : Rat),
    0 ≤ w → normalized ≤ value →
    Formal.StrategyBlend.learnedBlend value normalized w ≤ value :=
  @Formal.StrategyBlend.learnedBlend_le_value_when_ge
example : ∀ (value n n' w : Rat),
    0 ≤ w → n ≤ n' →
    Formal.StrategyBlend.learnedBlend value n w
      ≤ Formal.StrategyBlend.learnedBlend value n' w :=
  @Formal.StrategyBlend.learnedBlend_mono_normalized
example : ∀ (v v' normalized w : Rat),
    w ≤ 1 → v ≤ v' →
    Formal.StrategyBlend.learnedBlend v normalized w
      ≤ Formal.StrategyBlend.learnedBlend v' normalized w :=
  @Formal.StrategyBlend.learnedBlend_mono_value

/-! ### DecideKey role contracts. -/

example : ∀ (a b : Formal.DecideKey.Key),
    Formal.DecideKey.decideCmp a b = .lt
      ∨ Formal.DecideKey.decideCmp a b = .eq
      ∨ Formal.DecideKey.decideCmp a b = .gt :=
  @Formal.DecideKey.decideCmp_trichotomy
example : ∀ (a b : Formal.DecideKey.Key),
    Formal.DecideKey.decideCmp b a = (Formal.DecideKey.decideCmp a b).swap :=
  @Formal.DecideKey.decideCmp_swap
example : ∀ {a b c : Formal.DecideKey.Key},
    Formal.DecideKey.decideCmp a b = .lt →
    Formal.DecideKey.decideCmp b c = .lt →
    Formal.DecideKey.decideCmp a c = .lt :=
  @Formal.DecideKey.decideCmp_lt_trans
example : ∀ (a b : Formal.DecideKey.Key),
    Formal.DecideKey.decideCmp a b = .eq → a.rootRepr = b.rootRepr :=
  @Formal.DecideKey.decideCmp_eq_imp_repr
example : ∀ (a b : Formal.DecideKey.Key),
    Formal.DecideKey.decideCmp a b = .eq → a.negFinal = b.negFinal :=
  @Formal.DecideKey.decideCmp_eq_imp_negFinal
example : ∀ (a b : Formal.DecideKey.Key),
    Formal.DecideKey.decideCmp a b = .eq → a.effort = b.effort :=
  @Formal.DecideKey.decideCmp_eq_imp_effort
example : ∀ (k : Formal.DecideKey.GuardKind),
    (Formal.DecideKey.goalReprOfGuard k).length > 0 :=
  @Formal.DecideKey.goalReprOfGuard_nonempty
example : ∀ (k : Formal.DecideKey.MeansKind),
    (Formal.DecideKey.goalReprOfMeans k).length > 0 :=
  @Formal.DecideKey.goalReprOfMeans_nonempty

/-! ### CyclesForProgress role contracts. -/

example : ∀ (rows : List Formal.CyclesForProgress.CycleRow) (W : Nat),
    rows ≠ [] →
    ¬ (Formal.CyclesForProgress.allIntervals
          (Formal.CyclesForProgress.revList rows)).length < W →
    Formal.CyclesForProgress.cyclesForProgressPure rows W
      = some (Formal.CyclesForProgress.medianQ
          (Formal.CyclesForProgress.strictIntervals
            (Formal.CyclesForProgress.revList rows)
           ++ Formal.CyclesForProgress.satisfyIntervals
            (Formal.CyclesForProgress.revList rows))) :=
  @Formal.CyclesForProgress.cyclesForProgressPure_eq_median_concat
example : ∀ (rows : List Formal.CyclesForProgress.CycleRow) (W : Nat),
    (Formal.CyclesForProgress.allIntervals
        (Formal.CyclesForProgress.revList rows)).length < W →
    Formal.CyclesForProgress.cyclesForProgressPure rows W = none :=
  @Formal.CyclesForProgress.warmup_blocks
example : ∀ (W : Nat),
    Formal.CyclesForProgress.cyclesForProgressPure [] W = none :=
  @Formal.CyclesForProgress.empty_none
example : ∀ (rows : List Formal.CyclesForProgress.CycleRow),
    ∀ x ∈ Formal.CyclesForProgress.satisfyIntervals rows, 0 < x :=
  @Formal.CyclesForProgress.satisfyIntervals_pos
example : ∀ (rows : List Formal.CyclesForProgress.CycleRow),
    Formal.CyclesForProgress.monoChrono rows →
    ∀ x ∈ Formal.CyclesForProgress.strictIntervals rows, 0 < x :=
  @Formal.CyclesForProgress.strictIntervals_pos
example : ∀ (rows : List Formal.CyclesForProgress.CycleRow),
    Formal.CyclesForProgress.monoChrono rows →
    ∀ x ∈ Formal.CyclesForProgress.allIntervals rows, 0 < x :=
  @Formal.CyclesForProgress.allIntervals_pos

/-! ### GatherApply role contracts. -/

-- is_applicable lower bound: passing check ⇒ free ≥ k (Nat-truncating)
example : ∀ (i : Formal.GatherApply.Inv) (k : Nat),
    Formal.GatherApply.isApplicable i k = true → k ≤ i.cap - i.used :=
  @Formal.GatherApply.is_applicable_imp_free_ge
-- per-step safety: k ≥ 1 ∧ is_applicable ⇒ post.used ≤ cap
example : ∀ (i : Formal.GatherApply.Inv) (k : Nat),
    1 ≤ k → Formal.GatherApply.isApplicable i k = true →
    (Formal.GatherApply.apply i).used ≤ i.cap :=
  @Formal.GatherApply.apply_inventory_safe
-- per-step safety at production constant MIN_FREE_SLOTS = 3
example : ∀ (i : Formal.GatherApply.Inv),
    Formal.GatherApply.isApplicable i Formal.GatherApply.MIN_FREE_SLOTS = true →
    (Formal.GatherApply.apply i).used ≤ i.cap :=
  @Formal.GatherApply.apply_inventory_safe_prod
-- applyN bookkeeping: used' = used + n
example : ∀ (i : Formal.GatherApply.Inv) (n : Nat),
    (Formal.GatherApply.applyN i n).used = i.used + n :=
  @Formal.GatherApply.applyN_used
-- applyN bookkeeping: cap unchanged
example : ∀ (i : Formal.GatherApply.Inv) (n : Nat),
    (Formal.GatherApply.applyN i n).cap = i.cap :=
  @Formal.GatherApply.applyN_cap
-- chain safety: wellformed start + n ≤ free ⇒ chain stays in cap
example : ∀ (i : Formal.GatherApply.Inv) (n : Nat),
    i.used ≤ i.cap → n ≤ i.cap - i.used →
    (Formal.GatherApply.applyN i n).used ≤ i.cap :=
  @Formal.GatherApply.chain_safe

/-! ### NpcBuyInventory role contracts (REAL BUG #6). -/

-- is_applicable lower bound (slot): passing check ⇒ quantity ≤ free
example : ∀ (i : Formal.NpcBuyInventory.Inv) (quantity gold price : Nat),
    Formal.NpcBuyInventory.isApplicable i quantity gold price = true →
    quantity ≤ i.cap - i.used :=
  @Formal.NpcBuyInventory.npc_buy_is_applicable_imp_free_ge
-- is_applicable lower bound (gold): passing check ⇒ price*quantity ≤ gold
example : ∀ (i : Formal.NpcBuyInventory.Inv) (quantity gold price : Nat),
    Formal.NpcBuyInventory.isApplicable i quantity gold price = true →
    price * quantity ≤ gold :=
  @Formal.NpcBuyInventory.npc_buy_is_applicable_imp_gold_ge
-- per-step safety: wellformed + is_applicable ⇒ post.used ≤ cap (chain-safe contract)
example : ∀ (i : Formal.NpcBuyInventory.Inv) (quantity gold price : Nat),
    i.used ≤ i.cap →
    Formal.NpcBuyInventory.isApplicable i quantity gold price = true →
    (Formal.NpcBuyInventory.apply i quantity).used ≤ i.cap :=
  @Formal.NpcBuyInventory.npc_buy_apply_inventory_safe
-- applyN bookkeeping: used' = used + qs.sum
example : ∀ (i : Formal.NpcBuyInventory.Inv) (qs : List Nat),
    (Formal.NpcBuyInventory.applyN i qs).used = i.used + qs.sum :=
  @Formal.NpcBuyInventory.applyN_used
-- applyN bookkeeping: cap unchanged
example : ∀ (i : Formal.NpcBuyInventory.Inv) (qs : List Nat),
    (Formal.NpcBuyInventory.applyN i qs).cap = i.cap :=
  @Formal.NpcBuyInventory.applyN_cap
-- chain safety: wellformed start + qs.sum ≤ free ⇒ chain stays in cap
example : ∀ (i : Formal.NpcBuyInventory.Inv) (qs : List Nat),
    i.used ≤ i.cap → qs.sum ≤ i.cap - i.used →
    (Formal.NpcBuyInventory.applyN i qs).used ≤ i.cap :=
  @Formal.NpcBuyInventory.npc_buy_chain_safe

-- ActionCostNonneg statement contracts. Pin the role theorems' exact types.
-- bucket 1: constant cost ≥ 0
example : ∀ (k : Nat), 0 ≤ Formal.ActionCostNonneg.constantCost k :=
  @Formal.ActionCostNonneg.constantCost_nonneg
-- bucket 2: distance cost ≥ 0
example : ∀ (base d : Nat), 0 ≤ Formal.ActionCostNonneg.distanceCost base d :=
  @Formal.ActionCostNonneg.distanceCost_nonneg
-- bucket 3: qty cost ≥ 0
example : ∀ (base qty d perUnit : Nat),
    0 ≤ Formal.ActionCostNonneg.qtyCost base qty d perUnit :=
  @Formal.ActionCostNonneg.qtyCost_nonneg
-- bucket 4 (history fraction): learned ≥ 0 ∧ rateFloor > 0 ⇒ learned/max(rate,floor) ≥ 0
example : ∀ (learned rate rateFloor : Rat),
    0 ≤ learned → 0 < rateFloor →
    0 ≤ Formal.ActionCostNonneg.learnedFraction learned rate rateFloor :=
  @Formal.ActionCostNonneg.learnedFraction_nonneg
-- bucket 5: history-dependent full switch ≥ 0 under writer invariants
example : ∀ (static learned rate rateFloor confidentThreshold : Rat) (hasHistory : Bool),
    0 ≤ static → 0 ≤ learned → 0 < rateFloor →
    0 ≤ Formal.ActionCostNonneg.learnedCost static learned rate rateFloor
          confidentThreshold hasHistory :=
  @Formal.ActionCostNonneg.learnedCost_nonneg
-- production rate floor positivity (the load-bearing constant)
example : 0 < Formal.ActionCostNonneg.rateFloorProd :=
  @Formal.ActionCostNonneg.rateFloorProd_pos
-- per-action history-dependent ≥ 0
example : ∀ (dist : Nat) (learned rate loadoutPenalty : Rat),
    0 ≤ learned → 0 ≤ loadoutPenalty →
    0 ≤ Formal.ActionCostNonneg.fightCost dist learned rate loadoutPenalty :=
  @Formal.ActionCostNonneg.fight_cost_nonneg
example : ∀ (dist : Nat) (learned rate : Rat),
    0 ≤ learned →
    0 ≤ Formal.ActionCostNonneg.gatherCost dist learned rate :=
  @Formal.ActionCostNonneg.gather_cost_nonneg
example : ∀ (dist : Nat) (learned rate : Rat),
    0 ≤ learned →
    0 ≤ Formal.ActionCostNonneg.moveCost dist learned rate :=
  @Formal.ActionCostNonneg.move_cost_nonneg
-- instance-parameterized delete branches all ≥ 0
example : ∀ (b : Nat), 0 ≤ Formal.ActionCostNonneg.deleteCost b :=
  @Formal.ActionCostNonneg.delete_cost_nonneg
-- HEADLINE: the Phase-2 admissibility precondition (every concrete Action ≥ 0)
example : ∀ (t : Formal.ActionCostNonneg.ActionTag),
    (∀ s l r rf ct h, t = .hist s l r rf ct h →
      0 ≤ s ∧ 0 ≤ l ∧ 0 < rf) →
    0 ≤ Formal.ActionCostNonneg.evalCost t :=
  @Formal.ActionCostNonneg.all_actions_cost_nonneg

/-! ### ApplyBaseline role contracts (REAL BUG #5 — silent stat-baseline drop).

    Phase-14: gap closed — all 24 concrete `Action.apply` methods modeled. -/

-- apply-preserves-baseline-move: MoveAction.apply preserves all 8 baseline fields.
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean) (newX newY : Int),
    Formal.ApplyBaseline.preservesBaseline s (Formal.ApplyBaseline.moveApply s newX newY) :=
  @Formal.ApplyBaseline.moveApply_preserves_baseline
-- apply-preserves-baseline-equip: EquipAction.apply preserves all 8 baseline fields.
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)),
    Formal.ApplyBaseline.preservesBaseline s (Formal.ApplyBaseline.equipApply s i e) :=
  @Formal.ApplyBaseline.equipApply_preserves_baseline
-- apply-preserves-baseline-claim: ClaimPendingItemAction.apply preserves all 8 baseline fields.
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean) (i : List (String × Nat))
    (p : Option (List (String × String))),
    Formal.ApplyBaseline.preservesBaseline s (Formal.ApplyBaseline.claimApply s i p) :=
  @Formal.ApplyBaseline.claimApply_preserves_baseline
-- headline-preserves-baseline: every modeled apply preserves the 8 baseline fields.
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean) (a : Formal.ApplyBaseline.ModeledApply),
    Formal.ApplyBaseline.preservesBaseline s (a.run s) :=
  @Formal.ApplyBaseline.headline_preserves_baseline
-- Phase-14 HEADLINE: all 24 modeled actions preserve the 8 baseline fields.
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean) (a : Formal.ApplyBaseline.ModeledApply),
    Formal.ApplyBaseline.preservesBaseline s (a.run s) :=
  @Formal.ApplyBaseline.all_actions_preserve_baseline
-- reflexivity: a state preserves its own baseline (identity apply / Transition).
example : ∀ (s : Formal.ApplyBaseline.WorldStateLean),
    Formal.ApplyBaseline.preservesBaseline s s :=
  @Formal.ApplyBaseline.preservesBaseline_refl
-- transitivity: a chain of preserving applys still preserves (planner sim composition).
example : ∀ {a b c : Formal.ApplyBaseline.WorldStateLean},
    Formal.ApplyBaseline.preservesBaseline a b → Formal.ApplyBaseline.preservesBaseline b c →
    Formal.ApplyBaseline.preservesBaseline a c :=
  @Formal.ApplyBaseline.preservesBaseline_trans
-- Phase-14: per-action preservation for the OTHER 21 modeled actions
example := @Formal.ApplyBaseline.moveSemanticApply_preserves_baseline
example := @Formal.ApplyBaseline.mapTransitionApply_preserves_baseline
example := @Formal.ApplyBaseline.gatherApply_preserves_baseline
example := @Formal.ApplyBaseline.npcBuyApply_preserves_baseline
example := @Formal.ApplyBaseline.withdrawGoldApply_preserves_baseline
example := @Formal.ApplyBaseline.withdrawItemApply_preserves_baseline
example := @Formal.ApplyBaseline.craftApply_preserves_baseline
example := @Formal.ApplyBaseline.recycleApply_preserves_baseline
example := @Formal.ApplyBaseline.npcSellApply_preserves_baseline
example := @Formal.ApplyBaseline.depositGoldApply_preserves_baseline
example := @Formal.ApplyBaseline.depositAllApply_preserves_baseline
example := @Formal.ApplyBaseline.useConsumableApply_preserves_baseline
example := @Formal.ApplyBaseline.deleteApply_preserves_baseline
example := @Formal.ApplyBaseline.unequipApply_preserves_baseline
example := @Formal.ApplyBaseline.optimizeLoadoutApply_preserves_baseline
example := @Formal.ApplyBaseline.acceptTaskApply_preserves_baseline
example := @Formal.ApplyBaseline.completeTaskApply_preserves_baseline
example := @Formal.ApplyBaseline.taskCancelApply_preserves_baseline
example := @Formal.ApplyBaseline.taskExchangeApply_preserves_baseline
example := @Formal.ApplyBaseline.taskTradeApply_preserves_baseline
example := @Formal.ApplyBaseline.restApply_preserves_baseline
example := @Formal.ApplyBaseline.buyBankExpansionApply_preserves_baseline
example := @Formal.ApplyBaseline.fightApply_preserves_baseline
-- Phase-14: per-action mutates-only-declared-fields contracts (representative)
example := @Formal.ApplyBaseline.move_mutates_only_declared_fields
example := @Formal.ApplyBaseline.rest_mutates_only_declared_fields
example := @Formal.ApplyBaseline.buyBankExpansion_mutates_only_declared_fields
example := @Formal.ApplyBaseline.equip_mutates_only_declared_fields
example := @Formal.ApplyBaseline.claim_mutates_only_declared_fields
example := @Formal.ApplyBaseline.fight_mutates_only_declared_fields

/-! ### InventoryChainSafe role contracts (REAL BUGS #7-#10 inventory + #11 task-cancel coin). -/

-- Template: per-step safety
example : ∀ (i : Formal.InventoryChainSafe.Inv) (k : Nat),
    i.used ≤ i.cap →
    Formal.InventoryChainSafe.isApplicableK i k = true →
    (Formal.InventoryChainSafe.applyK i k).used ≤ i.cap :=
  @Formal.InventoryChainSafe.applyK_inventory_safe
-- Template: chain safety
example : ∀ (i : Formal.InventoryChainSafe.Inv) (ks : List Nat),
    i.used ≤ i.cap → ks.sum ≤ i.cap - i.used →
    (Formal.InventoryChainSafe.applyKN i ks).used ≤ i.cap :=
  @Formal.InventoryChainSafe.chain_safe_template

-- Withdraw: precondition implies inventory headroom AND bank availability.
example : ∀ (i : Formal.InventoryChainSafe.Inv) (quantity bankQty : Nat),
    Formal.InventoryChainSafe.withdrawIsApplicable i quantity bankQty = true →
    quantity ≤ i.cap - i.used :=
  @Formal.InventoryChainSafe.withdraw_is_applicable_imp_free_ge
example : ∀ (i : Formal.InventoryChainSafe.Inv) (quantity bankQty : Nat),
    Formal.InventoryChainSafe.withdrawIsApplicable i quantity bankQty = true →
    quantity ≤ bankQty :=
  @Formal.InventoryChainSafe.withdraw_is_applicable_imp_bank_ge
-- Withdraw: per-step safety
example : ∀ (i : Formal.InventoryChainSafe.Inv) (quantity bankQty : Nat),
    i.used ≤ i.cap →
    Formal.InventoryChainSafe.withdrawIsApplicable i quantity bankQty = true →
    (Formal.InventoryChainSafe.withdrawApply i quantity).used ≤ i.cap :=
  @Formal.InventoryChainSafe.withdraw_apply_inventory_safe
-- Withdraw: chain safety
example : ∀ (i : Formal.InventoryChainSafe.Inv) (qs : List Nat),
    i.used ≤ i.cap → qs.sum ≤ i.cap - i.used →
    (Formal.InventoryChainSafe.applyKN i qs).used ≤ i.cap :=
  @Formal.InventoryChainSafe.withdraw_chain_safe

-- Claim: precondition implies inventory headroom.
example : ∀ (i : Formal.InventoryChainSafe.Inv) (hasPending : Bool),
    Formal.InventoryChainSafe.claimIsApplicable i hasPending = true → 1 ≤ i.cap - i.used :=
  @Formal.InventoryChainSafe.claim_is_applicable_imp_free_ge
-- Claim: per-step safety
example : ∀ (i : Formal.InventoryChainSafe.Inv) (hasPending : Bool),
    i.used ≤ i.cap →
    Formal.InventoryChainSafe.claimIsApplicable i hasPending = true →
    (Formal.InventoryChainSafe.claimApply i).used ≤ i.cap :=
  @Formal.InventoryChainSafe.claim_apply_inventory_safe
-- Claim: chain safety (n claims at +1 each)
example : ∀ (i : Formal.InventoryChainSafe.Inv) (n : Nat),
    i.used ≤ i.cap → n ≤ i.cap - i.used →
    (Formal.InventoryChainSafe.applyKN i (List.replicate n 1)).used ≤ i.cap :=
  @Formal.InventoryChainSafe.claim_chain_safe

-- Unequip: precondition implies inventory headroom.
example : ∀ (i : Formal.InventoryChainSafe.Inv) (slotNonEmpty : Bool),
    Formal.InventoryChainSafe.unequipIsApplicable i slotNonEmpty = true → 1 ≤ i.cap - i.used :=
  @Formal.InventoryChainSafe.unequip_is_applicable_imp_free_ge
example : ∀ (i : Formal.InventoryChainSafe.Inv) (slotNonEmpty : Bool),
    i.used ≤ i.cap →
    Formal.InventoryChainSafe.unequipIsApplicable i slotNonEmpty = true →
    (Formal.InventoryChainSafe.unequipApply i).used ≤ i.cap :=
  @Formal.InventoryChainSafe.unequip_apply_inventory_safe
example : ∀ (i : Formal.InventoryChainSafe.Inv) (n : Nat),
    i.used ≤ i.cap → n ≤ i.cap - i.used →
    (Formal.InventoryChainSafe.applyKN i (List.replicate n 1)).used ≤ i.cap :=
  @Formal.InventoryChainSafe.unequip_chain_safe

-- TaskExchange: precondition implies inventory headroom AND coins headroom.
example : ∀ (i : Formal.InventoryChainSafe.Inv) (coins minCoins : Nat),
    Formal.InventoryChainSafe.taskExchangeIsApplicable i coins minCoins = true →
    1 ≤ i.cap - i.used :=
  @Formal.InventoryChainSafe.task_exchange_is_applicable_imp_free_ge
example : ∀ (i : Formal.InventoryChainSafe.Inv) (coins minCoins : Nat),
    Formal.InventoryChainSafe.taskExchangeIsApplicable i coins minCoins = true →
    minCoins ≤ coins :=
  @Formal.InventoryChainSafe.task_exchange_is_applicable_imp_coins_ge
example : ∀ (i : Formal.InventoryChainSafe.Inv) (coins minCoins : Nat),
    i.used ≤ i.cap →
    Formal.InventoryChainSafe.taskExchangeIsApplicable i coins minCoins = true →
    (Formal.InventoryChainSafe.taskExchangeApply i 1).used ≤ i.cap :=
  @Formal.InventoryChainSafe.task_exchange_apply_inventory_safe
example : ∀ (i : Formal.InventoryChainSafe.Inv) (rewards : List Nat),
    i.used ≤ i.cap → rewards.sum ≤ i.cap - i.used →
    (Formal.InventoryChainSafe.applyKN i rewards).used ≤ i.cap :=
  @Formal.InventoryChainSafe.task_exchange_chain_safe

-- TaskCancel coin: precondition implies coin ≥ 1.
example : ∀ (p : Formal.InventoryChainSafe.CoinPurse) (hasTask : Bool),
    Formal.InventoryChainSafe.taskCancelIsApplicable p hasTask = true → 1 ≤ p.coins :=
  @Formal.InventoryChainSafe.task_cancel_is_applicable_imp_coin_ge
-- TaskCancel: apply decrements by exactly 1.
example : ∀ (p : Formal.InventoryChainSafe.CoinPurse) (hasTask : Bool),
    Formal.InventoryChainSafe.taskCancelIsApplicable p hasTask = true →
    (Formal.InventoryChainSafe.taskCancelApply p).coins = p.coins - 1 :=
  @Formal.InventoryChainSafe.task_cancel_apply_coin_eq_pre_minus_one
example : ∀ (p : Formal.InventoryChainSafe.CoinPurse) (hasTask : Bool),
    Formal.InventoryChainSafe.taskCancelIsApplicable p hasTask = true →
    (Formal.InventoryChainSafe.taskCancelApply p).coins < p.coins :=
  @Formal.InventoryChainSafe.task_cancel_apply_strictly_decreases
example : ∀ (p : Formal.InventoryChainSafe.CoinPurse) (n : Nat),
    (Formal.InventoryChainSafe.taskCancelApplyN p n).coins = p.coins - n :=
  @Formal.InventoryChainSafe.task_cancel_applyN_coin

/-! ### Phase7Invariants role contracts (Phase-7 batch: A, D, E). -/

-- Target A: baseValue non-positive totalNeeded ⇒ 0 (the div-by-zero guard).
example : ∀ (totalEffective : Rat) (totalNeeded : Int),
    totalNeeded ≤ 0 → Formal.Phase7Invariants.baseValue totalNeeded totalEffective = 0 :=
  @Formal.Phase7Invariants.baseValue_nonpos_zero
-- Target A: positive totalNeeded ⇒ result ≥ 1 (the clamp floor).
example : ∀ (totalEffective : Rat) (totalNeeded : Int),
    0 < totalNeeded → 1 ≤ Formal.Phase7Invariants.baseValue totalNeeded totalEffective :=
  @Formal.Phase7Invariants.baseValue_pos_ge_one
-- Target A: baseValue ≥ 0 unconditionally.
example : ∀ (totalEffective : Rat) (totalNeeded : Int),
    0 ≤ Formal.Phase7Invariants.baseValue totalNeeded totalEffective :=
  @Formal.Phase7Invariants.baseValue_nonneg

-- Target D: passing precondition ⇒ slot ∈ table[itemType].
example : ∀ (st : Formal.Phase7Invariants.EquipState)
    (stats : Option Formal.Phase7Invariants.ItemStats) (slot : Nat)
    (tbl : Formal.Phase7Invariants.SlotTable),
    Formal.Phase7Invariants.isApplicable st stats slot tbl = true →
      ∃ s, stats = some s ∧ slot ∈ tbl s.itemType :=
  @Formal.Phase7Invariants.isApplicable_imp_slot_in_table
-- Target D: passing precondition ⇒ inventory has code.
example : ∀ (st : Formal.Phase7Invariants.EquipState)
    (stats : Option Formal.Phase7Invariants.ItemStats) (slot : Nat)
    (tbl : Formal.Phase7Invariants.SlotTable),
    Formal.Phase7Invariants.isApplicable st stats slot tbl = true → 0 < st.invQty :=
  @Formal.Phase7Invariants.isApplicable_imp_inv_pos
-- Target D: passing precondition ⇒ level requirement met.
example : ∀ (st : Formal.Phase7Invariants.EquipState)
    (stats : Option Formal.Phase7Invariants.ItemStats) (slot : Nat)
    (tbl : Formal.Phase7Invariants.SlotTable),
    Formal.Phase7Invariants.isApplicable st stats slot tbl = true →
      ∃ s, stats = some s ∧ s.level ≤ st.charLevel :=
  @Formal.Phase7Invariants.isApplicable_imp_level_ge
-- Target D: slot mismatch ⇒ refused (the load-bearing Phase-7 gate).
example : ∀ (st : Formal.Phase7Invariants.EquipState)
    (s : Formal.Phase7Invariants.ItemStats) (slot : Nat)
    (tbl : Formal.Phase7Invariants.SlotTable),
    0 < st.invQty → s.level ≤ st.charLevel → slot ∉ tbl s.itemType →
    Formal.Phase7Invariants.isApplicable st (some s) slot tbl = false :=
  @Formal.Phase7Invariants.isApplicable_slot_mismatch_refused

-- Target E: inventory_used = Σ qty (bookkeeping equality).
example : ∀ (s : Formal.Phase7Invariants.WS),
    Formal.Phase7Invariants.inventoryUsed s = (s.inventory.map Prod.snd).sum :=
  @Formal.Phase7Invariants.inventoryUsed_eq_sum
-- Target E: inventory_free = invMax - inventoryUsed.
example : ∀ (s : Formal.Phase7Invariants.WS),
    Formal.Phase7Invariants.inventoryFree s = s.invMax - Formal.Phase7Invariants.inventoryUsed s :=
  @Formal.Phase7Invariants.inventoryFree_eq_diff
-- Target E: at well-formed states (used ≤ max), free + used = max.
example : ∀ (s : Formal.Phase7Invariants.WS),
    Formal.Phase7Invariants.inventoryUsed s ≤ s.invMax →
    Formal.Phase7Invariants.inventoryFree s + Formal.Phase7Invariants.inventoryUsed s = s.invMax :=
  @Formal.Phase7Invariants.inventoryFree_plus_used_eq_max
-- Target E: hp_percent div-zero guard = 1 when maxHp = 0.
example : ∀ (s : Formal.Phase7Invariants.WS),
    s.maxHp = 0 → Formal.Phase7Invariants.hpPercent s = 1 :=
  @Formal.Phase7Invariants.hpPercent_maxhp_zero
-- Target E: hp_percent = hp / maxHp when maxHp > 0.
example : ∀ (s : Formal.Phase7Invariants.WS),
    s.maxHp ≠ 0 → Formal.Phase7Invariants.hpPercent s = (s.hp : Rat) / (s.maxHp : Rat) :=
  @Formal.Phase7Invariants.hpPercent_maxhp_pos
-- Target E: hp_percent ≥ 0 unconditionally.
example : ∀ (s : Formal.Phase7Invariants.WS),
    0 ≤ Formal.Phase7Invariants.hpPercent s :=
  @Formal.Phase7Invariants.hpPercent_nonneg

/-! ### StoreWarmup role contracts (Phase-7 Target F). -/

-- Below the warmup gate ⇒ median returns none.
example : ∀ (samples : List Int) (median : Int),
    samples.length < Formal.StoreWarmup.warmupMinSamples →
    Formal.StoreWarmup.warmupGatedMedian samples median = none :=
  @Formal.StoreWarmup.warmupGatedMedian_below_gate
-- At or above the gate ⇒ median returns some.
example : ∀ (samples : List Int) (median : Int),
    Formal.StoreWarmup.warmupMinSamples ≤ samples.length →
    Formal.StoreWarmup.warmupGatedMedian samples median = some median :=
  @Formal.StoreWarmup.warmupGatedMedian_at_or_above_gate
-- Below the gate ⇒ success rate = 1 (the warm-up default).
example : ∀ (okCount total : Nat),
    total < Formal.StoreWarmup.warmupMinSamples →
    Formal.StoreWarmup.warmupGatedSuccessRate okCount total = 1 :=
  @Formal.StoreWarmup.warmupGatedSuccessRate_below_gate
-- At or above the gate ⇒ success rate = okCount / total.
example : ∀ (okCount total : Nat),
    Formal.StoreWarmup.warmupMinSamples ≤ total →
    Formal.StoreWarmup.warmupGatedSuccessRate okCount total =
      (okCount : Rat) / (total : Rat) :=
  @Formal.StoreWarmup.warmupGatedSuccessRate_at_or_above_gate
-- Success rate is non-negative on every branch.
example : ∀ (okCount total : Nat),
    0 ≤ Formal.StoreWarmup.warmupGatedSuccessRate okCount total :=
  @Formal.StoreWarmup.warmupGatedSuccessRate_nonneg

/-! ### Phase8Invariants Target B — Bank expansion projection (REAL BUG #15). -/

-- Headline (a): per-step capacity increment by exactly BANK_EXPANSION_SLOTS.
example : ∀ (b : Formal.Phase8Invariants.BankProj),
    (Formal.Phase8Invariants.buyBankExpansionApply b).capacity =
      b.capacity + Formal.Phase8Invariants.BANK_EXPANSION_SLOTS :=
  @Formal.Phase8Invariants.bank_expansion_apply_increments_capacity

-- Bookkeeping: N applies add N * SLOTS to capacity.
example : ∀ (b : Formal.Phase8Invariants.BankProj) (n : Nat),
    (Formal.Phase8Invariants.buyBankExpansionApplyN b n).capacity =
      b.capacity + n * Formal.Phase8Invariants.BANK_EXPANSION_SLOTS :=
  @Formal.Phase8Invariants.buyBankExpansion_capacityN

-- Headline (b): the projection chain reaches `is_satisfied`.
example : ∀ (b : Formal.Phase8Invariants.BankProj) (n : Nat),
    10 * b.bankItems < 9 * (b.capacity + n * Formal.Phase8Invariants.BANK_EXPANSION_SLOTS) →
    Formal.Phase8Invariants.expandBankIsSatisfied
      (Formal.Phase8Invariants.buyBankExpansionApplyN b n) = true :=
  @Formal.Phase8Invariants.bank_expansion_chain_reaches_satisfied

-- Regression anchor: the pre-fix (buggy) apply never lifts the gap.
example : ∀ (b : Formal.Phase8Invariants.BankProj) (n : Nat),
    Formal.Phase8Invariants.expandBankIsSatisfied b = false →
    Formal.Phase8Invariants.expandBankIsSatisfied
      (Formal.Phase8Invariants.buyBankExpansionApplyPreFixN b n) = false :=
  @Formal.Phase8Invariants.bank_expansion_pre_fix_projection_gap

/-! ### Phase-9 (REAL BUG #16): GameDataAccessors -/

/-- Statement-pin: post-fix accessor returns `some` iff key is present. -/
example : ∀ {α : Type} (m : Formal.GameDataAccessors.Lookup α) (k : String),
    (Formal.GameDataAccessors.accessor m k).isSome ↔
      Formal.GameDataAccessors.present m k :=
  @Formal.GameDataAccessors.accessor_some_iff_present

/-- Statement-pin: post-fix accessor returns `none` iff key is absent
(modelling the Python `KeyError` raise). -/
example : ∀ {α : Type} (m : Formal.GameDataAccessors.Lookup α) (k : String),
    Formal.GameDataAccessors.accessor m k = none ↔
      ¬ Formal.GameDataAccessors.present m k :=
  @Formal.GameDataAccessors.accessor_none_iff_absent

/-- Statement-pin: pre-fix bug pattern: absent key ⇒ returns the default. -/
example : ∀ {α : Type} (m : Formal.GameDataAccessors.Lookup α) (k : String)
    (default : α), ¬ Formal.GameDataAccessors.present m k →
      Formal.GameDataAccessors.silentDefaultAccessor m k default = default :=
  @Formal.GameDataAccessors.silentDefault_absent_returns_default

/-- Statement-pin: load-bearing bug counterexample. The pre-fix silent-zero
defaults make `predictWinLite_buggy` return True on an unknown monster. -/
example : Formal.GameDataAccessors.predictWinLite_buggy [] [] "unknown_monster" 1
    = true :=
  Formal.GameDataAccessors.predictWinLite_buggy_unknown_returns_true

/-! ### Phase-11 (Target A): Player._winnable_farm_target cascade -/

/-- Statement-pin: task tier wins outright (winnable check bypassed). -/
example : ∀ (i : Formal.WinnableCascade.CascadeInputs) (t : String),
    i.taskMonster = some t →
    Formal.WinnableCascade.winnableFarmTargetPure i = some t :=
  @Formal.WinnableCascade.task_wins

/-- Statement-pin: path tier wins when task absent and path is winnable. -/
example : ∀ (i : Formal.WinnableCascade.CascadeInputs) (p : String),
    i.taskMonster = none →
    i.pathMonster = some p →
    i.pathWinnable = true →
    Formal.WinnableCascade.winnableFarmTargetPure i = some p :=
  @Formal.WinnableCascade.path_wins_when_winnable

/-- Statement-pin: pick tier wins when path absent. -/
example : ∀ (i : Formal.WinnableCascade.CascadeInputs),
    i.taskMonster = none →
    i.pathMonster = none →
    Formal.WinnableCascade.winnableFarmTargetPure i = i.pickWinnable :=
  @Formal.WinnableCascade.pick_wins_when_no_path

/-- Statement-pin: pick tier wins when path is present but not winnable
(safety: cascade never returns a non-winnable path monster). -/
example : ∀ (i : Formal.WinnableCascade.CascadeInputs),
    i.taskMonster = none →
    i.pathWinnable = false →
    Formal.WinnableCascade.winnableFarmTargetPure i = i.pickWinnable :=
  @Formal.WinnableCascade.pick_wins_when_path_not_winnable

/-- Statement-pin: contrapositive safety — if the cascade returns a path
monster that is not in the pick fallback, the path must have been
winnable. -/
example : ∀ (i : Formal.WinnableCascade.CascadeInputs) (p : String),
    i.taskMonster = none →
    i.pathMonster = some p →
    Formal.WinnableCascade.winnableFarmTargetPure i = some p →
    i.pickWinnable ≠ some p →
    i.pathWinnable = true :=
  @Formal.WinnableCascade.path_result_was_winnable

/-! ### RealizableLoadout (Phase-15): full `pick_loadout` algorithm pins. -/

/-- Property 1 — output realizability. -/
example : ∀ (inv : Formal.RealizableLoadout.Inventory)
            (equip : Formal.RealizableLoadout.SlotList)
            (slots : List Formal.RealizableLoadout.ScoredSlot),
    Formal.RealizableLoadout.isRealizable
      (Formal.RealizableLoadout.pickLoadout inv equip slots) inv equip :=
  @Formal.RealizableLoadout.pickLoadout_realizable

/-- Property 2 — per-slot no-downgrade (modulo stolen-current branch). -/
example : ∀ (inv : Formal.RealizableLoadout.Inventory)
            (equip : Formal.RealizableLoadout.SlotList)
            (rec : Formal.RealizableLoadout.SlotRecord)
            (score : Formal.RealizableLoadout.Code → Int)
            (claimed : Formal.RealizableLoadout.Code → Nat)
            (cur r : Formal.RealizableLoadout.Code),
    rec.current = some cur →
    (Formal.RealizableLoadout.pickSlotStep inv equip rec score claimed).1 = some r →
    cur ≠ r →
    score cur ≤ score r ∨ ¬ (1 ≤ Formal.RealizableLoadout.effAvail cur inv equip claimed) :=
  @Formal.RealizableLoadout.pickSlotStep_no_downgrade

/-- Property 3 — per-slot optimality (argmax over post-claim feasible). -/
example : ∀ (inv : Formal.RealizableLoadout.Inventory)
            (equip : Formal.RealizableLoadout.SlotList)
            (rec : Formal.RealizableLoadout.SlotRecord)
            (score : Formal.RealizableLoadout.Code → Int)
            (claimed : Formal.RealizableLoadout.Code → Nat)
            (f : Formal.RealizableLoadout.Code) (fs : List Formal.RealizableLoadout.Code),
    rec.candidates.filter
        (fun c => decide (1 ≤ Formal.RealizableLoadout.effAvail c inv equip claimed))
      = f :: fs →
    ∀ r,
    (Formal.RealizableLoadout.pickSlotStep inv equip rec score claimed).1 = some r →
    (∀ cur, rec.current = some cur → cur ≠ r) →
    r = Formal.RealizableLoadout.argmaxByCode score f fs :=
  @Formal.RealizableLoadout.pickSlotStep_optimal

/-- Property 4 — determinism (pure function of inputs). -/
example : ∀ (inv : Formal.RealizableLoadout.Inventory)
            (equip : Formal.RealizableLoadout.SlotList)
            (slots₁ slots₂ : List Formal.RealizableLoadout.ScoredSlot),
    slots₁ = slots₂ →
    Formal.RealizableLoadout.pickLoadout inv equip slots₁ =
      Formal.RealizableLoadout.pickLoadout inv equip slots₂ :=
  @Formal.RealizableLoadout.pickLoadout_extensional

/-! ### GoalValueBands role contracts (Phase-17).

PursueTaskGoal and GatherMaterialsGoal each route their discretionary
priority through `clampIntoBand` with a per-goal band whose ceiling sits
strictly below the survival floor (70). The contracts below pin:
  (a) band sanity (floor ≤ ceiling, ceiling < 70),
  (b) the HEADLINE survival-floor safety (value < 70 ∀ bonus),
  (c) band inclusion (floor ≤ value ≤ ceiling),
  (d) monotonicity in the learned-yield bonus,
  (e) the cold-path identity (bonus=0 ⇒ value=floor) so a no-history call
      reproduces the pre-Phase-17 priority bit-exactly. -/

example : Formal.GoalValueBands.pursueTaskFloor
    ≤ Formal.GoalValueBands.pursueTaskCeiling :=
  @Formal.GoalValueBands.pursueTask_floor_le_ceiling

example : Formal.GoalValueBands.gatherMaterialsFloor
    ≤ Formal.GoalValueBands.gatherMaterialsCeiling :=
  @Formal.GoalValueBands.gatherMaterials_floor_le_ceiling

example : Formal.GoalValueBands.pursueTaskCeiling
    < Formal.GoalValueBands.survivalFloor :=
  @Formal.GoalValueBands.pursueTask_ceiling_lt_survival

example : Formal.GoalValueBands.gatherMaterialsCeiling
    < Formal.GoalValueBands.survivalFloor :=
  @Formal.GoalValueBands.gatherMaterials_ceiling_lt_survival

-- HEADLINE: PursueTaskGoal.value < survival floor for ANY bonus.
example : ∀ (bonus : Rat),
    Formal.GoalValueBands.pursueTaskValue bonus
      < Formal.GoalValueBands.survivalFloor :=
  @Formal.GoalValueBands.pursueTask_value_below_survival_floor

-- HEADLINE: GatherMaterialsGoal.value < survival floor for ANY bonus.
example : ∀ (bonus : Rat),
    Formal.GoalValueBands.gatherMaterialsValue bonus
      < Formal.GoalValueBands.survivalFloor :=
  @Formal.GoalValueBands.gatherMaterials_value_below_survival_floor

example : ∀ (bonus : Rat),
    Formal.GoalValueBands.pursueTaskFloor
      ≤ Formal.GoalValueBands.pursueTaskValue bonus ∧
    Formal.GoalValueBands.pursueTaskValue bonus
      ≤ Formal.GoalValueBands.pursueTaskCeiling :=
  @Formal.GoalValueBands.pursueTask_value_in_band

example : ∀ (bonus : Rat),
    Formal.GoalValueBands.gatherMaterialsFloor
      ≤ Formal.GoalValueBands.gatherMaterialsValue bonus ∧
    Formal.GoalValueBands.gatherMaterialsValue bonus
      ≤ Formal.GoalValueBands.gatherMaterialsCeiling :=
  @Formal.GoalValueBands.gatherMaterials_value_in_band

example : ∀ (floor ceiling b₁ b₂ : Rat), b₁ ≤ b₂ →
    Formal.PriorityBand.clampIntoBand floor ceiling b₁
      ≤ Formal.PriorityBand.clampIntoBand floor ceiling b₂ :=
  @Formal.GoalValueBands.clampIntoBand_mono_bonus

example : ∀ (b₁ b₂ : Rat), b₁ ≤ b₂ →
    Formal.GoalValueBands.pursueTaskValue b₁
      ≤ Formal.GoalValueBands.pursueTaskValue b₂ :=
  @Formal.GoalValueBands.pursueTask_value_monotone_in_bonus

example : ∀ (b₁ b₂ : Rat), b₁ ≤ b₂ →
    Formal.GoalValueBands.gatherMaterialsValue b₁
      ≤ Formal.GoalValueBands.gatherMaterialsValue b₂ :=
  @Formal.GoalValueBands.gatherMaterials_value_monotone_in_bonus

example : Formal.GoalValueBands.pursueTaskValue 0
    = Formal.GoalValueBands.pursueTaskFloor :=
  @Formal.GoalValueBands.pursueTask_cold_eq_floor

example : Formal.GoalValueBands.gatherMaterialsValue 0
    = Formal.GoalValueBands.gatherMaterialsFloor :=
  @Formal.GoalValueBands.gatherMaterials_cold_eq_floor

-- PlannerDepthBound (planner returns no plan longer than max_depth ⇒ the
-- depth-based reachability gate is sound):
example : ∀ (maxDepth : Nat) (n : Formal.PlannerDepthBound.Node),
    Formal.PlannerDepthBound.Reachable maxDepth n → n.planLen ≤ maxDepth :=
  @Formal.PlannerDepthBound.plan_length_le_max_depth

example : ∀ (maxDepth lb : Nat) (satisfyingLen : Formal.PlannerDepthBound.Node → Prop),
    (∀ n, satisfyingLen n → n.planLen ≥ lb) → maxDepth < lb →
    ∀ (n : Formal.PlannerDepthBound.Node),
      Formal.PlannerDepthBound.Reachable maxDepth n → ¬ satisfyingLen n :=
  @Formal.PlannerDepthBound.reachable_not_satisfying_when_lb_exceeds_depth

-- TieredSelection (StrategyArbiter two-pass walk: cheap pass first, escalate to
-- full budget, else Wait; the no-plan memo soundly elides re-planning):
-- cheap_winner_is_first_cheaply_plannable: pass-1 result is the FIRST non-skipped
-- candidate that plans cheaply (plannable, non-skipped, member, prefix all fail).
example : ∀ {C : Type} (skip cheapPlans : C → Bool) (cand : List C) (c : C),
    Formal.TieredSelection.firstPlanning skip cheapPlans cand = some c →
    cheapPlans c = true ∧ skip c = false ∧ c ∈ cand ∧
    (∃ pre post, cand = pre ++ c :: post ∧
        ∀ x ∈ pre, ¬ (cheapPlans x = true ∧ skip x = false)) :=
  @Formal.TieredSelection.cheap_winner_is_first_cheaply_plannable
-- escalation_iff_no_cheap: select = full-pass result ⇔ (no non-skipped candidate
-- plans cheaply) ∨ (pass 1 and pass 2 coincide).
example : ∀ {C : Type} (skip cheapPlans fullPlans : C → Bool) (cand : List C),
    Formal.TieredSelection.select skip cheapPlans fullPlans cand
        = Formal.TieredSelection.firstPlanning skip fullPlans cand
      ↔ (∀ c ∈ cand, ¬ (cheapPlans c = true ∧ skip c = false))
        ∨ Formal.TieredSelection.firstPlanning skip cheapPlans cand
            = Formal.TieredSelection.firstPlanning skip fullPlans cand :=
  @Formal.TieredSelection.escalation_iff_no_cheap
-- wait_only_when_no_full: select = none (Wait) ⇒ no non-skipped candidate plans fully.
example : ∀ {C : Type} (skip cheapPlans fullPlans : C → Bool) (cand : List C),
    Formal.TieredSelection.select skip cheapPlans fullPlans cand = none →
    ∀ c ∈ cand, ¬ (fullPlans c = true ∧ skip c = false) :=
  @Formal.TieredSelection.wait_only_when_no_full
-- memo_skip_sound: the memo only carries goals with no plan at either budget;
-- a skipped candidate plans NEITHER cheaply NOR fully.
example : ∀ {C : Type} (skip cheapPlans fullPlans : C → Bool),
    (∀ c, skip c = true → cheapPlans c = false ∧ fullPlans c = false) →
    ∀ (c : C), skip c = true → ¬ (cheapPlans c = true) ∧ ¬ (fullPlans c = true) :=
  @Formal.TieredSelection.memo_skip_sound

-- GearLatch (gear-review latch transition mirroring GearLatch.update):
-- set_on_levelup: level-up + craftable upgrade ⇒ latch ON.
example : ∀ {leveledUp : Bool} (active loss hasUpgrade : Bool),
    leveledUp = true → hasUpgrade = true →
    Formal.GearLatch.step active leveledUp loss hasUpgrade = true :=
  @Formal.GearLatch.set_on_levelup
-- set_on_loss: fight-loss + craftable upgrade ⇒ latch ON.
example : ∀ (active leveledUp loss hasUpgrade : Bool),
    loss = true → hasUpgrade = true →
    Formal.GearLatch.step active leveledUp loss hasUpgrade = true :=
  @Formal.GearLatch.set_on_loss
-- clear_iff_no_upgrade: no craftable upgrade ⇒ latch forced OFF this cycle.
example : ∀ (active leveledUp loss : Bool),
    Formal.GearLatch.step active leveledUp loss false = false :=
  @Formal.GearLatch.clear_iff_no_upgrade
-- monotone_until_clear: once set, no new trigger, upgrade available ⇒ stays ON.
example : ∀ (active leveledUp loss hasUpgrade : Bool),
    active = true → leveledUp = false → loss = false → hasUpgrade = true →
    Formal.GearLatch.step active leveledUp loss hasUpgrade = true :=
  @Formal.GearLatch.monotone_until_clear

/-! ### GatherSelection role contracts (yield-rate lex-argmin gather-source). -/

-- select_some_iff_nonempty: TOTALITY/no-deadlock — none ⇔ empty list.
example : ∀ (cs : List Formal.GatherSelection.Candidate),
    Formal.GatherSelection.selectGatherSource cs = none ↔ cs = [] :=
  @Formal.GatherSelection.select_some_iff_nonempty
-- select_mem: the winner is a REAL candidate in the input list.
example : ∀ {cs : List Formal.GatherSelection.Candidate} {c : Formal.GatherSelection.Candidate},
    Formal.GatherSelection.selectGatherSource cs = some c → c ∈ cs :=
  @Formal.GatherSelection.select_mem
-- select_is_lex_min: DOMINANCE — no candidate strictly beats the winner on the lex key.
example : ∀ {cs : List Formal.GatherSelection.Candidate} {c : Formal.GatherSelection.Candidate},
    Formal.GatherSelection.selectGatherSource cs = some c →
    ∀ x ∈ cs, ¬ Formal.GatherSelection.keyLt x c :=
  @Formal.GatherSelection.select_is_lex_min
-- select_no_cheaper_at_le_distance: a strictly-cheaper candidate must be strictly FARTHER.
example : ∀ {cs : List Formal.GatherSelection.Candidate} {c : Formal.GatherSelection.Candidate},
    Formal.GatherSelection.selectGatherSource cs = some c →
    ∀ x ∈ cs,
      Formal.GatherSelection.expectedGathers x < Formal.GatherSelection.expectedGathers c →
      c.dist < x.dist :=
  @Formal.GatherSelection.select_no_cheaper_at_le_distance
-- expected_gathers_mono_in_rate: MONOTONICITY — ↑rate (yields fixed, positive avg) ⇒ ≥ expected gathers.
example : ∀ (a b : Formal.GatherSelection.Candidate),
    a.minQ = b.minQ → a.maxQ = b.maxQ → 0 < a.minQ + a.maxQ → a.rate ≤ b.rate →
    Formal.GatherSelection.expectedGathers a ≤ Formal.GatherSelection.expectedGathers b :=
  @Formal.GatherSelection.expected_gathers_mono_in_rate
-- gather_selected_reaches_needed: REACHABILITY — +1 loop reaches the needed quantity.
example : ∀ (needed owned : Nat), needed ≤ owned + (needed - owned) :=
  @Formal.GatherSelection.gather_selected_reaches_needed
