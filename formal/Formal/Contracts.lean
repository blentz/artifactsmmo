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
import Formal.OwnedCount
import Formal.UpgradeSelection
import Formal.Scalarizer
import Formal.PlannerAdmissibility
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
example : ∀ (floor ceiling bonus : Int), floor ≤ ceiling →
    floor ≤ Formal.PriorityBand.clampIntoBand floor ceiling bonus :=
  @Formal.PriorityBand.clamp_lower_bound
-- band-upper: clampIntoBand floor ceiling bonus ≤ ceiling (given floor ≤ ceiling).
example : ∀ (floor ceiling bonus : Int), floor ≤ ceiling →
    Formal.PriorityBand.clampIntoBand floor ceiling bonus ≤ ceiling :=
  @Formal.PriorityBand.clamp_upper_bound
-- survival-floor-safety: ceiling < survival ⇒ clamped result < survival (any bonus).
example : ∀ (floor ceiling bonus survival : Int), floor ≤ ceiling → ceiling < survival →
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

/-! ### PlannerAdmissibility role contracts. REFUTATION of planner.py:99
    "A* pops nodes in f-score order; first satisfied node is optimal." -/
-- conditional intent: an ADMISSIBLE heuristic forces f = g at a satisfied node —
-- the load-bearing fact that would make "first popped satisfied = least cost" sound.
example : ∀ {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop),
    Formal.PlannerAdmissibility.Admissible h trueRemaining →
    Formal.PlannerAdmissibility.GoalZero trueRemaining sat →
    ∀ (s : α) (g : Nat), sat s → Formal.PlannerAdmissibility.fScore g (h s) = g :=
  @Formal.PlannerAdmissibility.fScore_eq_g_at_goal_of_admissible
-- the urgency heuristic value() (RestoreHPGoal) is NOT admissible.
example : ¬ Formal.PlannerAdmissibility.Admissible
    Formal.PlannerAdmissibility.CEh Formal.PlannerAdmissibility.CEtrueRemaining :=
  Formal.PlannerAdmissibility.CE_not_admissible
-- best-first pops the expensive Rest-node (f=10) before the cheap Move-node (f=55).
example : Formal.PlannerAdmissibility.fScore 10
      (Formal.PlannerAdmissibility.CEh Formal.PlannerAdmissibility.CEState.rested)
    < Formal.PlannerAdmissibility.fScore 5
      (Formal.PlannerAdmissibility.CEh Formal.PlannerAdmissibility.CEState.moved) :=
  Formal.PlannerAdmissibility.CE_rest_popped_before_move
-- THE BUG: the returned plan (cost 10) is strictly costlier than optimal (cost 7).
example : Formal.PlannerAdmissibility.CEoptimalPlanCost
    < Formal.PlannerAdmissibility.CEfirstSatPlanCost :=
  Formal.PlannerAdmissibility.CE_first_satisfied_not_optimal
-- what admissibility WOULD buy: f = g at the genuine optimum.
example : ∀ (h : Formal.PlannerAdmissibility.CEState → Nat),
    Formal.PlannerAdmissibility.Admissible h Formal.PlannerAdmissibility.CEtrueRemaining →
    Formal.PlannerAdmissibility.fScore Formal.PlannerAdmissibility.CEoptimalPlanCost
        (h Formal.PlannerAdmissibility.CEState.eaten)
      = Formal.PlannerAdmissibility.CEoptimalPlanCost :=
  @Formal.PlannerAdmissibility.CE_admissible_would_be_optimal
