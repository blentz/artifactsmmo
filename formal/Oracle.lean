import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin
open Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve Formal.RecipeClosure
open Formal.BankSelection Formal.PriorityBand Formal.OwnedCount Formal.UpgradeSelection
open Formal.Scalarizer
open Formal.TaskDecision
open Formal.WeightedRemaining
open Formal.LowYieldCancel
open Formal.StrategyBlend
open Formal.DecideKey
open Formal.CyclesForProgress
open Formal.GatherApply
open Formal.ActionCostNonneg
open Formal.InventoryChainSafe
open Formal.InventoryProfile
open Formal.Phase7Invariants
open Formal.StoreWarmup
open Formal.WinnableCascade
open Formal.NearestTile

/-- Compute one calculate_path result using the SAME proved `pathFrom`/`manhattan`. -/
def runCalculatePath (sx sy ex ey : Int) : Json :=
  let start : Coord := (sx, sy)
  let dst : Coord := (ex, ey)
  let steps := pathFrom start dst
  let stepsJson := Json.arr ((steps.map (fun c => Json.arr #[Json.num c.1, Json.num c.2])).toArray)
  Json.mkObj [("steps", stepsJson), ("total_distance", Json.num (manhattan start dst)),
    ("estimated_time", Json.num (Int.ofNat (estimatedTime start dst)))]

/-- Compute one task_batch result using the SAME proved `batchSize`. -/
def runTaskBatch (taskBranch : Bool) (remaining mats free held : Int) : Json :=
  Json.mkObj [("k", Json.num (batchSize taskBranch remaining mats free held))]

/-- Compute one inventory_caps result using the SAME proved `cap`/`overstock`.

    args layout (9 ints):
    * batchBuf, safetyFlr, recipeDemand, equippableCap, consumableCap,
      actionCap, taskRemaining, equipped(0/1), qty

    The Python differential side computes `equippableCap` and
    `consumableCap` from the per-item predicates (`ITEM_TYPE_TO_SLOTS`,
    dominance walk, `stats.hp_restore > 0`) before encoding the request,
    so the Lean model takes the resulting Int components and the
    differential is end-to-end. -/
def runInventoryCaps (batchBuf safetyFlr recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int)
    (equipped : Bool) (qty : Int) : Json :=
  let c := capWith batchBuf safetyFlr recipeDemand
              equippableCap consumableCap actionCap taskRemaining equipped
  let o := overstockWith batchBuf safetyFlr recipeDemand
              equippableCap consumableCap actionCap taskRemaining equipped qty
  Json.mkObj [("cap", Json.num c), ("overstock", Json.num o)]

/-- Compute one predict_win verdict using the SAME proved `predictWin`/`rawHit`.

args layout (29 ints):
* player element damage vs monster resist: a0 d0 r0 a1 d1 r1 a2 d2 r2 a3 d3 r3  (0..11)
* pCrit                                                                          (12)
* monsterHp                                                                      (13)
* monster element damage vs player resist: a0 d0 r0 ... a3 d3 r3                 (14..25)
* mCrit                                                                          (26)
* playerMaxHp                                                                    (27)
* playerFirst (0/1)                                                              (28)
-/
def runPredictWin (g : Nat → Int) : Json :=
  let rawPlayer := rawHit (g 0) (g 1) (g 2) (g 3) (g 4) (g 5)
    (g 6) (g 7) (g 8) (g 9) (g 10) (g 11)
  let pCrit := g 12
  let monsterHp := g 13
  let rawMonster := rawHit (g 14) (g 15) (g 16) (g 17) (g 18) (g 19)
    (g 20) (g 21) (g 22) (g 23) (g 24) (g 25)
  let mCrit := g 26
  let playerMaxHp := g 27
  let playerFirst := g 28 != 0
  -- lifesteal extension: [29]=pLifesteal [30]=pAtkSum [31]=mLifesteal [32]=mAtkSum
  let pLifesteal := g 29
  let pAtkSum := g 30
  let mLifesteal := g 31
  let mAtkSum := g 32
  -- poison extension: [33]=monsterPoison (flat per-turn DoT on the player)
  let monsterPoison := g 33
  -- barrier extension: [34]=monsterBarrier (absorbing shield ⇒ extra effective HP)
  let monsterBarrier := g 34
  -- burn extension: [35]=monsterBurn (percent-of-attack DoT, modeled flat/no-decay)
  let monsterBurn := g 35
  -- healing extension: [36]=monsterHealing (regen %; subtracted from killStep)
  let monsterHealing := g 36
  -- reconstitution extension: [37]=monsterReconstitution (full-heal period; turn-cap)
  let monsterReconstitution := g 37
  let verdict := predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing monsterReconstitution playerFirst
  Json.mkObj [("win", Json.bool verdict), ("raw_player", Json.num rawPlayer),
    ("raw_monster", Json.num rawMonster)]

/-- Read an Int field (defaulting to 0) from a JSON array of Ints. -/
def intArg (xs : Array Json) (i : Nat) : Int := (xs[i]!.getInt?).toOption.getD 0

/-- Read a String field (defaulting to "") from a JSON array. The diff side
encodes strings directly as `Json.str`, so this reads the REAL string (no
interning), letting the oracle call String-keyed extracted cores unchanged. -/
def strArg (xs : Array Json) (i : Nat) : String := (xs[i]!.getStr?).toOption.getD ""

/-- Evaluate the `equipCapValue` predicate-level model in Lean.
    args layout (2 ints): equippable(0/1), dominated(0/1).
    Returns the Lean-computed `equippableCap` component. -/
def runEquipCapValue (isEquippable isDominated : Int) : Json :=
  Json.mkObj [("equippable_cap",
    Json.num (equipCapValue (isEquippable != 0) (isDominated != 0)))]

/-- Evaluate the `consumableCapValue` predicate-level model in Lean.
    args layout (1 int): hpRestore. Returns the Lean-computed
    `consumableCap` component. -/
def runConsumableCapValue (hpRestore : Int) : Json :=
  Json.mkObj [("consumable_cap", Json.num (consumableCapValue hpRestore))]

/-- Evaluate the `equipCapFromPeers` (dominance + slot gate) model in Lean.
    args layout: equippable(0/1), slotCount, peer_count, then for each
    peer: fitsAllSlots(0/1), strictlyHigher(0/1), coversSkillEffects(0/1),
    ownedCount. Returns the Lean-computed `equippableCap` after the
    dominance check. -/
def runEquipCapFromPeers (args : Array Json) : Json :=
  let isEquippable := intArg args 0 != 0
  let slotCount := intArg args 1
  let peerCount := (intArg args 2).toNat
  let peers : List Peer := (List.range peerCount).map fun i =>
    let base := 3 + i * 4
    { fitsAllSlots := intArg args base != 0
      strictlyHigher := intArg args (base + 1) != 0
      coversSkillEffects := intArg args (base + 2) != 0
      ownedCount := intArg args (base + 3) }
  Json.mkObj [("equippable_cap",
    Json.num (equipCapFromPeers isEquippable peers slotCount))]

/-- Group a flat Int list into `SlotData` quadruples
(newCode, oldCode, newC, oldC). Trailing partials are dropped. -/
def toSlots : List Int → List SlotData
  | a :: b :: c :: d :: rest => (a, b, c, d) :: toSlots rest
  | _ => []

/-- Compute one loadout_projection result using the SAME proved `projectedField`.

args layout: [current, then groups of 4: newCode, oldCode, newC, oldC per slot].
Emits the projected value of ONE stat field (the differential test calls the
oracle once per field/element, treating dropped-zero element keys as 0). -/
def runLoadoutProjection (args : Array Json) : Json :=
  let current := intArg args 0
  let rest := (List.range (args.size - 1)).map (fun i => intArg args (i + 1))
  let slots := toSlots rest
  Json.mkObj [("projected", Json.num (projectedField current slots))]

/-- Build a model `Item` from a flat 12-int block:
`[code, level, fits(0/1), atk0..atk3, res0..res3, crit]`. Element keys are 0..3. -/
def itemFromBlock (b : Nat → Int) : Item :=
  { code := b 0, level := b 1, fits := b 2 != 0,
    attack := [(0, b 3), (1, b 4), (2, b 5), (3, b 6)],
    resistance := [(0, b 7), (1, b 8), (2, b 9), (3, b 10)],
    crit := b 11, flatUtil := b 12 }

/-- Build an `ElemStats` (monster atk OR res) from 4 ints at offset `o`. -/
def elemFromArgs (args : Array Json) (o : Nat) : ElemStats :=
  [(0, intArg args o), (1, intArg args (o+1)), (2, intArg args (o+2)), (3, intArg args (o+3))]

/-- Compute one equipment_scoring per-slot pick using the SAME proved `pickSlot`.

args layout:
* 0:        playerLevel
* 1:        scoreKind (0 = weapon, 1 = armor)
* 2..5:     monster element stats (resistance for weapon, attack for armor)
* 6:        currentPresent (0/1)
* 7..19:    current item block (13 ints; ignored when currentPresent = 0)
* 20..:     candidate item blocks, 13 ints each (13th int = flatUtil)

Emits the picked item's CODE (or -1 = none / leave-as-is), its SCORE, the MAX
feasible score, and the current item's score (for the no-downgrade assertion). -/
def runEquipmentScoring (args : Array Json) : Json :=
  let playerLevel := intArg args 0
  let isWeapon := intArg args 1 == 0
  let monStats := elemFromArgs args 2
  let score : Item → Int :=
    if isWeapon then (fun it => WScore it monStats) else (fun it => AScore it monStats)
  let curPresent := intArg args 6 != 0
  let current : Option Item :=
    if curPresent then some (itemFromBlock (fun i => intArg args (7 + i))) else none
  -- candidate blocks start at 20, 13 ints each
  let nCand := (args.size - 20) / 13
  let items : List Item :=
    (List.range nCand).map (fun k => itemFromBlock (fun i => intArg args (20 + k * 13 + i)))
  let picked := pickSlot score playerLevel current items
  let pickedCode : Int := match picked with | some it => it.code | none => -1
  let pickedScore : Int := match picked with | some it => score it | none => 0
  let cands := candidates playerLevel items
  let maxScore : Int := match cands with
    | [] => (match current with | some it => score it | none => 0)
    | c :: cs => score (argmaxBy score c cs)
  let curScore : Int := match current with | some it => score it | none => 0
  Json.mkObj [("picked_code", Json.num pickedCode), ("picked_score", Json.num pickedScore),
    ("max_score", Json.num maxScore), ("cur_score", Json.num curScore)]

/-- Compute one skill_target_curve result using the proved `skillCurveTarget`.

args layout (Ints):
* `[0]`   charLevel
* `[1]`   lookahead
* `[2]`   maxSkill
* `[3]`   skill (interned to a small Int by the diff side)
* then 4-int item blocks: `[craftSkill, craftLevel, itemLevel, gearRelevant(0/1)]`

Emits `{"target": Int}` — the recipe-aware curve target for `skill`. -/
def runSkillTargetCurve (args : Array Json) : Json :=
  let charLevel := intArg args 0
  let lookahead := intArg args 1
  let maxSkill := intArg args 2
  let skill := intArg args 3
  let nItems := (args.size - 4) / 4
  let items : List Formal.SkillTargetCurve.Item :=
    (List.range nItems).map (fun k =>
      { craftSkill := intArg args (4 + k*4), craftLevel := intArg args (5 + k*4),
        itemLevel := intArg args (6 + k*4),
        gearRelevant := intArg args (7 + k*4) != 0 })
  Json.mkObj [("target",
    Json.num (Formal.SkillTargetCurve.skillCurveTarget skill charLevel lookahead maxSkill items))]

/-- Compute one skill_xp_curve result using the SAME proved defs.

args layout:
* 0:            nObs (number of observed pairs)
* 1 .. 2*nObs:  observed pairs, flat (level0, xp0, level1, xp1, ...)
* then:         current, target, xpPerCycle, queryLevel

Emits ONLY the modeled integer/count/branch outputs:
* `required_xp` of `queryLevel` (exact on observed levels; on the two zero
  branches it is 0; the abstracted geometric estimate is NOT emitted — the
  Python diff only queries observed/zero levels).
* `conf_num` / `conf_den` (exact confidence rational over the gap).
* `is_confident` (bool).
* `cycles_branch` (0 / inf-sentinel -1 / 1=finite).
* `total` over the gap (exact, valid as the Python total only when the range is
  fully observed; the diff restricts to that case).
* `uses_default` (bool). -/
def runSkillXpCurve (args : Array Json) : Json :=
  let nObs := (intArg args 0).toNat
  let obs : Observed :=
    (List.range nObs).map (fun k => (intArg args (1 + 2 * k), intArg args (2 + 2 * k)))
  let base := 1 + 2 * nObs
  let current := intArg args base
  let target := intArg args (base + 1)
  let xpPerCycle := intArg args (base + 2)
  let queryLevel := intArg args (base + 3)
  -- required_xp is emitted with a zero estimate (the diff only queries
  -- observed/zero-branch levels, where the estimate is unreached).
  let reqXp := requiredXp (fun _ => 0) obs queryLevel
  Json.mkObj [
    ("required_xp", Json.num reqXp),
    ("conf_num", Json.num (Int.ofNat (confNum obs current target))),
    ("conf_den", Json.num (Int.ofNat (confDen current target))),
    ("is_confident", Json.bool (isConfident obs current target)),
    ("cycles_branch", Json.num (cyclesBranch current target xpPerCycle)),
    ("total", Json.num (totalXpToReach obs current target)),
    ("uses_default", Json.bool (usesDefaultRatio obs))]

/-- Build a `Recipe` (Nat → List (Nat × Nat)) from a list of `(item, sub, qty)`
triples: `r item` = every `(sub, qty)` whose triple's first component is `item`,
in encounter order (mirrors a Python dict's insertion-ordered ingredient map). -/
def recipeFromTriples (triples : List (Nat × Nat × Nat)) : Recipe :=
  fun item => (triples.filter (fun t => decide (t.1 = item))).map (fun t => (t.2.1, t.2.2))

/-- Compute one recipe_closure result using the proved `craftableList` /
`neededList` / `rawUnits`.

args layout (all Nat, encoded as Int ≥ 0):
* `[0]`            nRecipe (number of `(item, sub, qty)` triples)
* `[1 .. 3*nRecipe]`   the triples, flat: item0 sub0 qty0 item1 sub1 qty1 ...
* next: nDrops, then `(res, drop)` pairs flat
* next: nRoots, then roots
* next: queryItem (for raw_material_units), fuel

Emits sorted `needed_resources` / `craftable_mats` lists and the
`raw_material_units(queryItem)` value. -/
def runRecipeClosure (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let nRecipe := g 0
  let triples : List (Nat × Nat × Nat) :=
    (List.range nRecipe).map (fun k => (g (1 + 3*k), g (2 + 3*k), g (3 + 3*k)))
  let p1 := 1 + 3*nRecipe
  let nDrops := g p1
  let drops : List (Nat × Nat) :=
    (List.range nDrops).map (fun k => (g (p1 + 1 + 2*k), g (p1 + 2 + 2*k)))
  let p2 := p1 + 1 + 2*nDrops
  let nRoots := g p2
  let roots : List Nat := (List.range nRoots).map (fun k => g (p2 + 1 + k))
  let p3 := p2 + 1 + nRoots
  let queryItem := g p3
  let fuel := g (p3 + 1)
  let r := recipeFromTriples triples
  let needed := (neededList r roots drops fuel).mergeSort (· ≤ ·) |>.eraseDups
  let craft := (craftableList r roots fuel).mergeSort (· ≤ ·) |>.eraseDups
  let toJson := fun (xs : List Nat) => Json.arr ((xs.map (fun n => Json.num (Int.ofNat n))).toArray)
  Json.mkObj [("needed_resources", toJson needed), ("craftable_mats", toJson craft),
    ("raw_material_units", Json.num (Int.ofNat (rawUnits r fuel queryItem)))]

/-- Build a `TaskFeasibility.Recipe` (Nat → List Nat, ingredient codes only)
from a list of `(item, sub)` pairs: `r item` = every `sub` whose pair's first
component is `item`, in encounter order. -/
def tfRecipeFromPairs (pairs : List (Nat × Nat)) : Formal.TaskFeasibility.Recipe :=
  fun item => (pairs.filter (fun p => decide (p.1 = item))).map Prod.snd

/-- Build a per-item lookup table from a flat assoc list, defaulting to `d`. -/
def tableLookup (tbl : List (Nat × Nat)) (d : Nat) : Nat → Nat :=
  fun k => match tbl.find? (fun p => decide (p.1 = k)) with
    | some p => p.2
    | none => d

/-- Compute one task_feasibility ITEMS result using the proved `worstLevel`.

args layout (all Nat ≥ 0):
* `[0]`                   nEdges (number of `(item, sub)` recipe edges)
* `[1 .. 2*nEdges]`       edges flat: item0 sub0 item1 sub1 ...
* next: nSkillItems, then `(item, hasSkill(0/1))` pairs flat
* next: nCraft, then `(item, craftLevel)` pairs flat
* next: nSkillLvl, then `(item, charSkillLevelForThatItem)` pairs flat
* next: taskItem, fuel

Emits the worst required_level (0 = none / feasible). -/
def runTaskFeasibilityItems (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let nEdges := g 0
  let pairs : List (Nat × Nat) :=
    (List.range nEdges).map (fun k => (g (1 + 2*k), g (2 + 2*k)))
  let p1 := 1 + 2*nEdges
  let nSkill := g p1
  let skillTbl : List (Nat × Nat) :=
    (List.range nSkill).map (fun k => (g (p1 + 1 + 2*k), g (p1 + 2 + 2*k)))
  let p2 := p1 + 1 + 2*nSkill
  let nCraft := g p2
  let craftTbl : List (Nat × Nat) :=
    (List.range nCraft).map (fun k => (g (p2 + 1 + 2*k), g (p2 + 2 + 2*k)))
  let p3 := p2 + 1 + 2*nCraft
  let nLvl := g p3
  let lvlTbl : List (Nat × Nat) :=
    (List.range nLvl).map (fun k => (g (p3 + 1 + 2*k), g (p3 + 2 + 2*k)))
  let p4 := p3 + 1 + 2*nLvl
  let taskItem := g p4
  let fuel := g (p4 + 1)
  let r := tfRecipeFromPairs pairs
  let hasSkill : Formal.TaskFeasibility.HasSkill := fun k => tableLookup skillTbl 0 k != 0
  let craftLevel : Formal.TaskFeasibility.CraftLevel := tableLookup craftTbl 0
  let skillLevel : Formal.TaskFeasibility.SkillLevel := tableLookup lvlTbl 0
  let worst := Formal.TaskFeasibility.worstLevel r [taskItem] fuel hasSkill craftLevel skillLevel
  Json.mkObj [("required_level", Json.num (Int.ofNat worst))]

/-- Compute one prerequisite_graph edge list using the proved `prereqEdges`.

Models the DATA-DERIVED edges of an unsatisfied `ObtainItem code`.

args layout (all Nat ≥ 0):
* `[0]`              hasRecipe (0/1)
* `[1]`              nIngredients
* `[2 .. 2*n+1]`     ingredients flat: mat0 qty0 mat1 qty1 ...  (only read when hasRecipe=1)
* next: hasCraftSkill (0/1), craftSkill, craftLevel  (skill/level only meaningful when 1)
* next: nDrops, then `(res, drop, hasSkill(0/1), skill, level)` quintuples flat
* next: code

Emits the edge list as tagged JSON objects:
`{"kind":"skill","a":skill,"b":level}` or `{"kind":"item","a":code,"b":qty}`. -/
def runPrerequisiteGraph (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let hasRecipe := g 0 != 0
  let nIng := g 1
  let ingredients : List (Nat × Nat) :=
    (List.range nIng).map (fun k => (g (2 + 2*k), g (3 + 2*k)))
  let p1 := 2 + 2*nIng
  let hasCraftSkill := g p1 != 0
  let craftSkill : Option (Nat × Nat) :=
    if hasCraftSkill then some (g (p1 + 1), g (p1 + 2)) else none
  let p2 := p1 + 3
  let nDrops := g p2
  let resDrops : List (Nat × Nat × Option (Nat × Nat)) :=
    (List.range nDrops).map (fun k =>
      let base := p2 + 1 + 5*k
      let res := g base
      let drop := g (base + 1)
      let skill : Option (Nat × Nat) :=
        if g (base + 2) != 0 then some (g (base + 3), g (base + 4)) else none
      (res, drop, skill))
  let p3 := p2 + 1 + 5*nDrops
  let code := g p3
  let recipe : Option (List (Nat × Nat)) := if hasRecipe then some ingredients else none
  let edges := Formal.PrerequisiteGraph.prereqEdges recipe craftSkill resDrops code
  let edgeJson := fun (e : Formal.PrerequisiteGraph.Edge) => match e with
    | Formal.PrerequisiteGraph.Edge.skill s l =>
      Json.mkObj [("kind", Json.str "skill"), ("a", Json.num (Int.ofNat s)),
        ("b", Json.num (Int.ofNat l))]
    | Formal.PrerequisiteGraph.Edge.item c q =>
      Json.mkObj [("kind", Json.str "item"), ("a", Json.num (Int.ofNat c)),
        ("b", Json.num (Int.ofNat q))]
  Json.mkObj [("edges", Json.arr ((edges.map edgeJson).toArray))]

/-- Compute one combat_capable verdict using the proved `combatCapable`.

args layout: `[n, beatable0, beatable1, ...]` — n monster verdicts (each 0/1).
The monster CODE is its index. Emits the `any` aggregation bool. -/
def runCombatCapable (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let beatableList := (List.range n).map (fun k => intArg args (1 + k) != 0)
  let monsters := List.range n
  let beatable : Nat → Bool := fun m => (beatableList[m]?).getD false
  Json.mkObj [("capable", Json.bool (Formal.PrerequisiteGraph.combatCapable beatable monsters))]

/-- Compute one task_feasibility MONSTER gate using the proved `monsterGates`.
args: [monsterLevel, charLevel]. Emits the gate bool. -/
def runTaskFeasibilityMonster (args : Array Json) : Json :=
  let monsterLevel := (intArg args 0).toNat
  let charLevel := (intArg args 1).toNat
  Json.mkObj [("gates", Json.bool (Formal.TaskFeasibility.monsterGates monsterLevel charLevel))]

/-- Build an `Objective.Recipe` (Nat → List Nat, materials only) and the
`hasRecipe` / `isDrop` predicates from flat args, then run `isAttainable`.

args layout (all Nat ≥ 0):
* `[0]`              nEdges (number of `(item, mat)` recipe-material edges)
* `[1 .. 2*nEdges]`  edges flat: item0 mat0 item1 mat1 ...
* next: nHasRecipe, then the item codes that HAVE a recipe
* next: nDrops, then the drop-item codes (resource-drop values)
* next: queryItem, fuel

Emits `is_attainable` (bool). -/
def runObjectiveAttainable (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let nEdges := g 0
  let edges : List (Nat × Nat) :=
    (List.range nEdges).map (fun k => (g (1 + 2*k), g (2 + 2*k)))
  let p1 := 1 + 2*nEdges
  let nHas := g p1
  let hasList : List Nat := (List.range nHas).map (fun k => g (p1 + 1 + k))
  let p2 := p1 + 1 + nHas
  let nDrops := g p2
  let dropList : List Nat := (List.range nDrops).map (fun k => g (p2 + 1 + k))
  let p3 := p2 + 1 + nDrops
  let queryItem := g p3
  let fuel := g (p3 + 1)
  let r : Formal.Objective.Recipe := fun item =>
    (edges.filter (fun e => decide (e.1 = item))).map Prod.snd
  let hasRec : Formal.Objective.HasRecipe := fun item => decide (item ∈ hasList)
  let drop : Formal.Objective.IsDrop := fun item => decide (item ∈ dropList)
  Json.mkObj [("is_attainable",
    Json.bool (Formal.Objective.isAttainable r hasRec drop fuel queryItem))]

/-- Run `bestAttainableGear`: choose the first-slot item for a gear type.

args layout: `[n, code0, value0, attain0, code1, value1, attain1, ...]` — `n`
items, each `(code, equip_value, attainable(0/1))`. Emits the chosen code (or -1
if none attainable), and its equip_value. -/
def runObjectiveBestGear (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let items : List Formal.Objective.Gear :=
    (List.range n).map (fun k =>
      { code := intArg args (1 + 3*k), value := intArg args (2 + 3*k) })
  let attainBits : List Bool :=
    (List.range n).map (fun k => intArg args (3 + 3*k) != 0)
  -- attain by position: map each gear to its bit via code+value identity is
  -- fragile under dup codes, so we attach the bit by index using a parallel list.
  let codeVal := fun (it : Formal.Objective.Gear) => (it.code, it.value)
  let pairs : List (Formal.Objective.Gear × Bool) := items.zip attainBits
  let attain : Formal.Objective.Gear → Bool := fun it =>
    match pairs.find? (fun p => decide (codeVal p.1 = codeVal it)) with
    | some p => p.2
    | none => false
  let chosen := Formal.Objective.bestAttainableGear attain items
  let code : Int := match chosen with | some it => it.code | none => -1
  let val : Int := match chosen with | some it => it.value | none => 0
  Json.mkObj [("chosen_code", Json.num code), ("chosen_value", Json.num val)]

/-- Run the `gap` integer numerators/denominators and `is_complete`.

args layout (Ints): `[targetLevel, level, nSkills, (target, have)*nSkills,
nGear, (target, have)*nGear]`. Emits char gap, skill gap sum + denom, gear gap
sum + denom, and is_complete. -/
def runObjectiveGap (args : Array Json) : Json :=
  let targetLevel := intArg args 0
  let level := intArg args 1
  let charGap := Formal.Objective.axisGap targetLevel level
  let nSkills := (intArg args 2).toNat
  let skillPairs : List (Int × Int) :=
    (List.range nSkills).map (fun k => (intArg args (3 + 2*k), intArg args (4 + 2*k)))
  let p := 3 + 2*nSkills
  let nGear := (intArg args p).toNat
  let gearPairs : List (Int × Int) :=
    (List.range nGear).map (fun k => (intArg args (p + 1 + 2*k), intArg args (p + 2 + 2*k)))
  Json.mkObj [
    ("char_gap", Json.num charGap),
    ("skill_gap_sum", Json.num (Formal.Objective.gapSum skillPairs)),
    ("skill_denom", Json.num (Formal.Objective.targetSum skillPairs)),
    ("gear_gap_sum", Json.num (Formal.Objective.gapSum gearPairs)),
    ("gear_denom", Json.num (Formal.Objective.targetSum gearPairs)),
    ("is_complete", Json.bool (Formal.Objective.isComplete charGap skillPairs gearPairs))]

/-- Build a `StrategyTraversal.Graph` from a flat node encoding and return it
together with the node count.

args node-graph layout (all Nat ≥ 0), starting at offset `o`:
* `[o]`        n (number of nodes; node codes are `0 .. n-1`)
* then n node blocks, each: `isSat(0/1), producible(0/1), kind(0=obtain,1=skill,2=char),
  nPrereqs, prereq0, prereq1, ...`

Returns `(graph, n, nextOffset)`. Out-of-range nodes default to leaf/unmet/obtain. -/
def parseGraph (args : Array Json) (o : Nat) :
    Formal.StrategyTraversal.Graph × Nat × Nat := Id.run do
  let g := fun i => (intArg args i).toNat
  let n := g o
  -- collect per-node (isSat, producible, kind, prereqs) into assoc lists
  let mut satTbl : List (Nat × Bool) := []
  let mut prodTbl : List (Nat × Bool) := []
  let mut kindTbl : List (Nat × Formal.StrategyTraversal.Kind) := []
  let mut prereqTbl : List (Nat × List Nat) := []
  let mut p := o + 1
  for node in List.range n do
    let isSat := g p != 0
    let producible := g (p + 1) != 0
    let kindCode := g (p + 2)
    let kind : Formal.StrategyTraversal.Kind :=
      if kindCode == 1 then Formal.StrategyTraversal.Kind.skill
      else if kindCode == 2 then Formal.StrategyTraversal.Kind.char
      else Formal.StrategyTraversal.Kind.obtain
    let nPre := g (p + 3)
    let prereqs := (List.range nPre).map (fun k => g (p + 4 + k))
    satTbl := (node, isSat) :: satTbl
    prodTbl := (node, producible) :: prodTbl
    kindTbl := (node, kind) :: kindTbl
    prereqTbl := (node, prereqs) :: prereqTbl
    p := p + 4 + nPre
  let lookupBool := fun (tbl : List (Nat × Bool)) (d : Bool) (k : Nat) =>
    match tbl.find? (fun e => decide (e.1 = k)) with | some e => e.2 | none => d
  let graph : Formal.StrategyTraversal.Graph := {
    prereqs := fun k => match prereqTbl.find? (fun e => decide (e.1 = k)) with
      | some e => e.2 | none => []
    isSat := fun k => lookupBool satTbl false k
    producible := fun k => lookupBool prodTbl false k
    kind := fun k => match kindTbl.find? (fun e => decide (e.1 = k)) with
      | some e => e.2 | none => Formal.StrategyTraversal.Kind.obtain }
  return (graph, n, p)

/-- Compute one strategy_traversal result via the proved defs. The `query`
selects the metric. The node graph is parsed from offset 0; the trailing args
(after the graph) are `root, fuel` (and for root_cost: `kindCode, target, have`). -/
def runStrategyTraversal (query : String) (args : Array Json) : Json :=
  let (g, _, nextOff) := parseGraph args 0
  let tail := fun i => (intArg args (nextOff + i)).toNat
  let root := tail 0
  let fuel := tail 1
  if query == "is_reachable" then
    Json.mkObj [("is_reachable",
      Json.bool (Formal.StrategyTraversal.isReachable g fuel root))]
  else if query == "closure_size" then
    Json.mkObj [("closure_size",
      Json.num (Int.ofNat (Formal.StrategyTraversal.unmetClosureSize g root fuel)))]
  else if query == "actionable" then
    match Formal.StrategyTraversal.actionableStep g fuel root with
    | some r => Json.mkObj [("actionable", Json.num (Int.ofNat r))]
    | none => Json.mkObj [("actionable", Json.null)]
  else  -- root_cost: tail = root, fuel, kindCode, target, have
    let kindCode := tail 2
    let target := tail 3
    let have_ := tail 4
    let kind : Formal.StrategyTraversal.Kind :=
      if kindCode == 1 then Formal.StrategyTraversal.Kind.skill
      else if kindCode == 2 then Formal.StrategyTraversal.Kind.char
      else Formal.StrategyTraversal.Kind.obtain
    Json.mkObj [("root_cost",
      Json.num (Int.ofNat (Formal.StrategyTraversal.rootCost g kind target have_ root fuel)))]

/-- Build a `Nat → α` lookup from an assoc list of `(code, value)` Int pairs via a
projection `f`, defaulting to `d`. -/
def attrLookup {α : Type} (tbl : List (Nat × Int)) (f : Int → α) (d : α) : Nat → α :=
  fun k => match tbl.find? (fun p => decide (p.1 = k)) with
    | some p => f p.2
    | none => d

/-- Compute one bank_selection result using the proved `keepList` / `deposits`.

args layout (Ints; codes/qtys/flags are Nat ≥ 0, attack/sellValue may be any Int):
* `[0]`            tasksCoin
* `[1]`            hasTask (0/1)
* `[2]`            taskCode (meaningful only when hasTask = 1)
* `[3]`            taskIsItems (0/1)
* `[4]`            hasCraftTarget (0/1)
* `[5]`            craftingTarget (meaningful only when hasCraftTarget = 1)
* `[6]`            nInv, then nInv pairs flat: code0 qty0 code1 qty1 ...
* next: nEquip, then equip codes flat
* next: nRecipe, then `(item, sub, qty)` triples flat
* next: nAttr, then per-item 6-int blocks:
  `code, attack, isWeapon(0/1), isTool(0/1), hpRestore, sellValue`
* next: fuel

Emits the sorted keep-set codes and the deposit list (codes, in sort order). -/
def runBankSelection (args : Array Json) : Json :=
  let gN := fun i => (intArg args i).toNat
  let tasksCoin := gN 0
  let taskCode : Option Nat := if intArg args 1 != 0 then some (gN 2) else none
  let taskIsItems := intArg args 3 != 0
  let craftingTarget : Option Nat := if intArg args 4 != 0 then some (gN 5) else none
  let nInv := gN 6
  let inventory : List (Nat × Nat) :=
    (List.range nInv).map (fun k => (gN (7 + 2*k), gN (8 + 2*k)))
  let p1 := 7 + 2*nInv
  let nEquip := gN p1
  let equipped : List Nat := (List.range nEquip).map (fun k => gN (p1 + 1 + k))
  let p2 := p1 + 1 + nEquip
  let nRecipe := gN p2
  let triples : List (Nat × Nat × Nat) :=
    (List.range nRecipe).map (fun k => (gN (p2 + 1 + 3*k), gN (p2 + 2 + 3*k), gN (p2 + 3 + 3*k)))
  let p3 := p2 + 1 + 3*nRecipe
  let nAttr := gN p3
  let attackTbl : List (Nat × Int) :=
    (List.range nAttr).map (fun k => (gN (p3 + 1 + 6*k), intArg args (p3 + 2 + 6*k)))
  let weaponTbl : List (Nat × Int) :=
    (List.range nAttr).map (fun k => (gN (p3 + 1 + 6*k), intArg args (p3 + 3 + 6*k)))
  let toolTbl : List (Nat × Int) :=
    (List.range nAttr).map (fun k => (gN (p3 + 1 + 6*k), intArg args (p3 + 4 + 6*k)))
  let hpTbl : List (Nat × Int) :=
    (List.range nAttr).map (fun k => (gN (p3 + 1 + 6*k), intArg args (p3 + 5 + 6*k)))
  let sellTbl : List (Nat × Int) :=
    (List.range nAttr).map (fun k => (gN (p3 + 1 + 6*k), intArg args (p3 + 6 + 6*k)))
  let p4 := p3 + 1 + 6*nAttr
  let fuel := gN p4
  let s : State := {
    tasksCoin := tasksCoin, taskCode := taskCode, taskIsItems := taskIsItems,
    craftingTarget := craftingTarget, inventory := inventory, equipped := equipped,
    recipe := recipeFromTriples triples,
    attack := attrLookup attackTbl id 0,
    isWeapon := attrLookup weaponTbl (fun v => decide (v != 0)) false,
    isTool := attrLookup toolTbl (fun v => decide (v != 0)) false,
    hpRestore := attrLookup hpTbl id 0,
    sellValue := attrLookup sellTbl id 0 }
  let keep := (keepList s fuel).mergeSort (· ≤ ·) |>.eraseDups
  let deps := deposits s fuel
  let keepJson := Json.arr ((keep.map (fun n => Json.num (Int.ofNat n))).toArray)
  let depsJson := Json.arr ((deps.map
    (fun cq => Json.arr #[Json.num (Int.ofNat cq.1), Json.num (Int.ofNat cq.2)])).toArray)
  Json.mkObj [("keep", keepJson), ("deposits", depsJson)]

/-- Compute one stuck_detector result using the proved `detect` / `recentSince`.

args layout (all Nat ≥ 0):
* `[0]`            counter (global cycle counter; ≥ history length)
* `[1]`            ackFrozen cutoff
* `[2]`            ackOsc cutoff
* `[3]`            ackNoprog cutoff
* `[4]`            n (history length)
* `[5 .. 5+4n-1]`  n records flat: state0 goal0 noPlan0(0/1) ok0(0/1) state1 ...
  (oldest first, mirroring `list(deque)`)

Emits the `detect()` verdict ("frozen"/"osc"/"noprog"/"none"), the three
window lengths (to pin `_recent_since`'s index arithmetic), and the osc
switch/failure counts (to pin the genuine-oscillation gates). -/
def runStuckDetector (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let counter := g 0
  let ackFrozen := g 1
  let ackOsc := g 2
  let ackNoprog := g 3
  let n := g 4
  let history : List Formal.StuckDetector.Rec :=
    (List.range n).map (fun k =>
      { state := g (5 + 4*k), goal := g (6 + 4*k), noPlan := g (7 + 4*k) != 0,
        ok := g (8 + 4*k) != 0 })
  let d : Formal.StuckDetector.Detector :=
    { history := history, counter := counter,
      ackFrozen := ackFrozen, ackOsc := ackOsc, ackNoprog := ackNoprog }
  let verdict : String := match Formal.StuckDetector.detect d with
    | some Formal.StuckDetector.Signal.frozen => "frozen"
    | some Formal.StuckDetector.Signal.osc => "osc"
    | some Formal.StuckDetector.Signal.noprog => "noprog"
    | none => "none"
  let frozenLen := (Formal.StuckDetector.recentSince d ackFrozen
    Formal.StuckDetector.frozenThreshold).length
  let oscLen := (Formal.StuckDetector.recentSince d ackOsc
    Formal.StuckDetector.oscThreshold).length
  let noprogLen := (Formal.StuckDetector.recentSince d ackNoprog
    Formal.StuckDetector.noprogThreshold).length
  let oscWindow := Formal.StuckDetector.recentSince d ackOsc
    Formal.StuckDetector.oscThreshold
  let oscSwitches := Formal.StuckDetector.switches
    (oscWindow.map Formal.StuckDetector.Rec.goal)
  let oscFailures := Formal.StuckDetector.failures oscWindow
  Json.mkObj [("detect", Json.str verdict),
    ("frozen_window_len", Json.num (Int.ofNat frozenLen)),
    ("osc_window_len", Json.num (Int.ofNat oscLen)),
    ("noprog_window_len", Json.num (Int.ofNat noprogLen)),
    ("osc_switches", Json.num (Int.ofNat oscSwitches)),
    ("osc_failures", Json.num (Int.ofNat oscFailures))]

/-- Read a rational field from a flat Int arg list as a (numerator, denominator)
pair starting at index `i`. The Python diff feeds EXACT `fractions.Fraction`
inputs split into their numerator/denominator, so the oracle reconstructs the
exact `Rat` (the fractional domain the bot really compares). -/
def ratArg (xs : Array Json) (i : Nat) : Rat :=
  mkRat (intArg xs i) (intArg xs (i + 1)).toNat

/-- Compute one priority_band result using the SAME proved `clampIntoBand` over `Rat`.
Each input is a (num, den) pair; args layout:
* `[0,1]`  floor   (num, den)
* `[2,3]`  ceiling (num, den)
* `[4,5]`  bonus   (num, den)
Emits the clamped band value as separate numerator / denominator integers. -/
def runPriorityBand (args : Array Json) : Json :=
  let floor := ratArg args 0
  let ceiling := ratArg args 2
  let bonus := ratArg args 4
  let r := clampIntoBand floor ceiling bonus
  Json.mkObj [("clamped_num", Json.num r.num),
              ("clamped_den", Json.num (Int.ofNat r.den))]

/-- Compute one owned_count result using the SAME proved `ownedCount`.

The query is scalarized to the single code of interest: args are the queried
code's three store contributions — `[invCount, bankCount, equipped(0/1)]`. The
proved `ownedCount` is instantiated with constant count functions returning those
values at the query code (any code; the value is the same). Emits the count. -/
def runOwnedCount (args : Array Json) : Json :=
  let invCount := (intArg args 0).toNat
  let bankCount := (intArg args 1).toNat
  let equipped := intArg args 2 != 0
  let inv : String → Nat := fun _ => invCount
  let bank : String → Nat := fun _ => bankCount
  let eq : String → Bool := fun _ => equipped
  Json.mkObj [("owned", Json.num (Int.ofNat (ownedCount inv bank eq "x")))]

/-- Build an upgrade `Candidate` from a flat 6-int block:
`[codeInt, value, level, craftLevel, relevant(0/1), fillsEmpty(0/1)]`. The item
code is the decimal string of `codeInt` (matching the Python `str(code)`), so the
String tiebreak in the comparators agrees with Python's string ordering on the
same codes. -/
def upgradeCandFromBlock (b : Nat → Int) : Candidate :=
  { itemCode := toString (b 0), value := b 1, level := b 2, craftLevel := b 3,
    relevant := b 4 != 0, fillsEmpty := b 5 != 0 }

/-- Emit a candidate as `[codeInt, value]` (the fields the diff compares). -/
def candJson (c : Candidate) : Json :=
  Json.mkObj [("code", Json.str c.itemCode), ("value", Json.num c.value)]

/-- Compute one upgrade_selection result using the proved cores.

args layout (Ints):
* `[0]`   query: 0 = best_by_value, 1 = best_by_key (craftable), 2 = best_by_key
          (inventory)
* `[1]`   for query 0: invPresent(0/1); for 1/2: n (number of candidates)
* For query 0: `[1]`=invPresent, `[2]`=craftPresent, then up to two 6-int blocks
  (inventory block if present, then craftable block if present).
* For query 1/2: `[1]`=n, then n 6-int candidate blocks. -/
def runUpgradeSelection (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 0 then
    let invPresent := intArg args 1 != 0
    let craftPresent := intArg args 2 != 0
    let invCand : Option Candidate := if invPresent then some (upgradeCandFromBlock (fun i => intArg args (3 + i))) else none
    let craftBase := if invPresent then 9 else 3
    let craftCand : Option Candidate := if craftPresent then some (upgradeCandFromBlock (fun i => intArg args (craftBase + i))) else none
    match bestByValue invCand craftCand with
    | some r => Json.mkObj [("present", Json.bool true), ("chosen", candJson r)]
    | none => Json.mkObj [("present", Json.bool false)]
  else
    let n := (intArg args 1).toNat
    let cands : List Candidate := (List.range n).map (fun k => upgradeCandFromBlock (fun i => intArg args (2 + 6*k + i)))
    let cmp := if q == 1 then craftableCmp else inventoryCmp
    match bestByKey cmp cands with
    | some r => Json.mkObj [("present", Json.bool true), ("chosen", candJson r)]
    | none => Json.mkObj [("present", Json.bool false)]

/-- Compute one scalarizer result using the SAME proved `scalarYield`, over the
EXACT RATIONAL domain (no scaling). Each rational input is a (num, den) pair.

args layout (Ints, read as rational num/den pairs):
* `[0,1]`          charXp      (num, den)
* `[2,3]`          level       (num, den)
* `[4,5]`          gold        (num, den)
* `[6,7]`          tasksCoins  (num, den)
* `[8,9]`          coinValue   (num, den)
* `[10,11]`        charScale   (num, den; production = 1/1)
* `[12,13]`        goldUnit    (num, den; production = 1/100)
* `[14]`           nSkills, then nSkills (weightNum, weightDen, xpNum, xpDen) quads

Emits the exact scalar as separate numerator / denominator integers. -/
def runScalarizer (args : Array Json) : Json :=
  let charXp := ratArg args 0
  let level := ratArg args 2
  let gold := ratArg args 4
  let tasksCoins := ratArg args 6
  let coinValue := ratArg args 8
  let charScale := ratArg args 10
  let goldUnit := ratArg args 12
  let nSkills := (intArg args 14).toNat
  let skills : List Formal.Scalarizer.SkillTerm :=
    (List.range nSkills).map (fun k => (ratArg args (15 + 4*k), ratArg args (17 + 4*k)))
  let r := Formal.Scalarizer.scalarYield charXp level skills gold tasksCoins
    coinValue charScale goldUnit
  Json.mkObj [("scalar_num", Json.num r.num), ("scalar_den", Json.num (Int.ofNat r.den))]

/-- Compute one arbiter_select result using the SAME proved `selectPure`.

args layout:
* `[0]`          = nCands
* per-candidate block (5 Ints, repeated nCands times starting at index 1):
  `[id, isMeans(0/1), plannable(0/1), satisfied(0/1), suppressed(0/1)]`
* trailing: `[committed_present(0/1), committed_id]`

The per-candidate `plannable/satisfied/suppressed` flags encode the closures
the Python passes in. The oracle reconstructs an `id → Bool` table keyed by
`Candidate.id` (assumes ids are unique across the candidate list — the
production guarantee captured by `idsDisjoint`-style well-formedness in the
diff generator).

Emits the chosen id (or -1), is-means flag, and new committed id (or -1). -/
def runArbiterSelect (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let cands : List Formal.ArbiterSelect.Candidate :=
    (List.range n).map (fun k =>
      let base := 1 + 5 * k
      ⟨(intArg args base).toNat, intArg args (base + 1) != 0⟩)
  -- Build (id → Bool) tables.
  let lookup (offset : Nat) (id : Nat) : Bool :=
    let rec loop : Nat → Bool
      | 0 => false
      | k + 1 =>
        let base := 1 + 5 * (n - k - 1)
        if (intArg args base).toNat = id then intArg args (base + offset) != 0
        else loop k
    loop n
  let plannable := lookup 2
  let satisfied := lookup 3
  let suppressed := lookup 4
  let commPresent := intArg args (1 + 5 * n) != 0
  let commId := intArg args (2 + 5 * n)
  let committed : Option Nat := if commPresent then some commId.toNat else none
  let (chosen, newCommitted) := Formal.ArbiterSelect.selectPure cands committed plannable satisfied suppressed
  let chosenId : Int := match chosen with | some c => Int.ofNat c.id | none => -1
  let chosenIsMeans : Bool := match chosen with | some c => c.isMeans | none => false
  let newCommittedId : Int := match newCommitted with | some i => Int.ofNat i | none => -1
  Json.mkObj [
    ("chosen_id", Json.num chosenId),
    ("chosen_is_means", Json.bool chosenIsMeans),
    ("new_committed_id", Json.num newCommittedId)
  ]

/-- Compute one coins_spent result using the SAME proved `coinsSpent`.
args: [received, delta]. Emits coins_spent and the inverted delta (received-cs). -/
def runCoinsSpent (args : Array Json) : Json :=
  let received := intArg args 0
  let delta := intArg args 1
  let cs := Formal.Scalarizer.coinsSpent received delta
  Json.mkObj [("coins_spent", Json.num cs), ("inverted_delta", Json.num (received - cs))]

/-- Compute one task_decision result using the SAME proved `taskDecisionPure`.

args layout (Ints; rationals as num/den pairs):
* `[0]`     reqIsNone (0/1)
* `[1]`     reqIsCombat (0/1)
* `[2]`     historyPresent (0/1)
* `[3,4]`   skillUpVpc  (num, den)
* `[5,6]`   baseline    (num, den)
* `[7,8]`   margin      (num, den)
* `[9,10]`  confidence  (num, den)

Emits the decision label as a string. -/
def runTaskDecision (args : Array Json) : Json :=
  let reqIsNone := intArg args 0 != 0
  let reqIsCombat := intArg args 1 != 0
  let historyPresent := intArg args 2 != 0
  let skillUpVpc := ratArg args 3
  let baseline := ratArg args 5
  let margin := ratArg args 7
  let confidence := ratArg args 9
  let d := taskDecisionPure reqIsNone reqIsCombat historyPresent
              skillUpVpc baseline margin confidence
  let label := match d with
    | Decision.PURSUE => "pursue"
    | Decision.PIVOT => "pivot"
  Json.mkObj [("decision", Json.str label)]

/-- Compute one weighted_remaining + is_complete result over the proved
`weightedRemaining` / `isComplete`.

args layout (Ints; rationals as num/den pairs):
* `[0]`        nTerms
* per-term block (4 Ints): `[weightNum, weightDen, fractionNum, fractionDen]`

Emits `wr_num`/`wr_den` (the exact scalar over `ℚ`), and `is_complete`. -/
def runWeightedRemaining (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let terms : List Formal.WeightedRemaining.Term :=
    (List.range n).map (fun k =>
      (ratArg args (1 + 4 * k), ratArg args (3 + 4 * k)))
  let r := Formal.WeightedRemaining.weightedRemaining terms
  Json.mkObj [
    ("wr_num", Json.num r.num),
    ("wr_den", Json.num (Int.ofNat r.den)),
    ("is_complete", Json.bool (decide (Formal.WeightedRemaining.isComplete terms)))]

/-- Compute one low_yield_cancel result using the SAME proved
`lowYieldFiresPure`.

args layout (Ints; rationals as num/den pairs):
* `[0]`      hasTask (0/1)
* `[1,2]`    currentXp (num, den)
* `[3,4]`    altXp (num, den)
* `[5,6]`    confidence (num, den)
* `[7]`      farmSamples (Nat)
* `[8]`      altSamples (Nat)
* `[9,10]`   margin (num, den)
* `[11,12]`  minConfidence (num, den)

Emits `fires` as a Bool. -/
def runLowYieldCancel (args : Array Json) : Json :=
  let hasTask := intArg args 0 != 0
  let currentXp := ratArg args 1
  let altXp := ratArg args 3
  let confidence := ratArg args 5
  let farmSamples := (intArg args 7).toNat
  let altSamples := (intArg args 8).toNat
  let margin := ratArg args 9
  let minConfidence := ratArg args 11
  let b := lowYieldFiresPure hasTask currentXp altXp confidence
              farmSamples altSamples margin minConfidence
  Json.mkObj [("fires", Json.bool b)]

/-- Compute one strategy_blend result using the SAME proved cores.

args layout (Ints; rationals as num/den pairs):
* `[0]`      query: 0 = balancing (scaled), 1 = learned_blend
* For query 0: `[1, 2]` = leader, current (Ints).
* For query 1: `[1,2]`/`[3,4]`/`[5,6]` = value/normalized/w (num, den each).

Emits the scaled Int result for balancing OR the rational num/den for blend. -/
def runStrategyBlend (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 0 then
    let leader := intArg args 1
    let current := intArg args 2
    Json.mkObj [("scaled", Json.num (Formal.StrategyBlend.balancingScaled leader current))]
  else
    let value := ratArg args 1
    let normalized := ratArg args 3
    let w := ratArg args 5
    let r := Formal.StrategyBlend.learnedBlend value normalized w
    Json.mkObj [("blend_num", Json.num r.num), ("blend_den", Json.num (Int.ofNat r.den))]

/-- Compute one decide_key result using the SAME proved `decideCmp` / dispatch
maps.

args layout (Ints; rootRepr/guard/means strings encoded as a single trailing
JSON field via the outer wrapper isn't supported here, so we tag the query
type and use a small int encoding for enum kinds and a string lookup via the
trailing args).

* `[0]`         query: 0 = compare two keys, 1 = goalReprOfGuard, 2 = goalReprOfMeans
* For query 0: `[1, 2, 3, 4]` = a.negFinal, a.effort, b.negFinal, b.effort.
  Reprs are passed as separate string fields via the JSON wrapper:
  `[5]`/`[6]` carry the string encodings as integer-tagged codes (we use the
  string CHARS reconstructed via a separate dispatch path — see diff test).
  To keep the oracle interface integer-only, the diff test compares ONLY the
  comparator outcome when reprs are equal-by-construction; otherwise it
  passes encoded reprs via an out-of-band string-arg array (unsupported here
  — the diff test uses query 0 only on numeric fields and parameterises repr
  ties off-line). For simplicity we emit cmp(a, b) treating reprs as equal
  (the strict-total-order property at the (negFinal, effort) projection).
* For query 1: `[1]` = GuardKind index 0..8.
* For query 2: `[1]` = MeansKind index 0..10.

Emits:
* query 0: cmp outcome as `"lt" | "eq" | "gt"`.
* query 1/2: the dispatched repr string. -/
def runDecideKey (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 0 then
    let a : Formal.DecideKey.Key := ⟨intArg args 1, intArg args 2, ""⟩
    let b : Formal.DecideKey.Key := ⟨intArg args 3, intArg args 4, ""⟩
    let label : String := match Formal.DecideKey.decideCmp a b with
      | .lt => "lt" | .eq => "eq" | .gt => "gt"
    Json.mkObj [("cmp", Json.str label)]
  else if q == 1 then
    let idx := (intArg args 1).toNat
    let k : Formal.DecideKey.GuardKind := match idx with
      | 0 => .hpCritical
      | 1 => .bankUnlock
      | 2 => .reachUnlockLevel
      | 3 => .discardCritical
      | 4 => .craftRelief
      | 5 => .depositFull
      | 6 => .discardHigh
      | 7 => .restForCombat
      | _ => .gearReview
    Json.mkObj [("repr", Json.str (Formal.DecideKey.goalReprOfGuard k))]
  else
    let idx := (intArg args 1).toNat
    let k : Formal.DecideKey.MeansKind := match idx with
      | 0 => .claimPending
      | 1 => .completeTask
      | 2 => .sellPressured
      | 3 => .lowYieldCancel
      | 4 => .taskCancel
      | 5 => .pursueTask
      | 6 => .acceptTask
      | 7 => .taskExchange
      | 8 => .sellIdle
      | 9 => .recycleSurplus
      | 10 => .bankExpand
      | _ => .wait
    Json.mkObj [("repr", Json.str (Formal.DecideKey.goalReprOfMeans k))]

/-- Compute one cycles_for_progress result using the SAME proved
`cyclesForProgressPure`.

args layout (all Ints):
* `[0]`        warmupMinSamples (Nat)
* `[1]`        nRows
* per row (5 Ints, repeated nRows times starting at index 2):
  `[cycleIndex, hasTaskProgress(0/1), taskProgress, hasCyclesToSatisfy(0/1),
    cyclesToSatisfy]`

Rows are passed newest-first (as `recent_goal_cycles` returns them).

Emits the result as `{"present": Bool, "num": Int, "den": Int}`. When
`present = false`, num/den are 0. -/
def runCyclesForProgress (args : Array Json) : Json :=
  let warmup := (intArg args 0).toNat
  let n := (intArg args 1).toNat
  let rows : List Formal.CyclesForProgress.CycleRow :=
    (List.range n).map (fun k =>
      let base := 2 + 5 * k
      let cyc := intArg args base
      let tpPresent := intArg args (base + 1) != 0
      let tp : Option Int := if tpPresent then some (intArg args (base + 2)) else none
      let csPresent := intArg args (base + 3) != 0
      let cs : Option Int := if csPresent then some (intArg args (base + 4)) else none
      { cycleIndex := cyc, taskProgress := tp, cyclesToSatisfy := cs })
  match Formal.CyclesForProgress.cyclesForProgressPure rows warmup with
  | some r =>
    Json.mkObj [("present", Json.bool true),
                ("num", Json.num r.num),
                ("den", Json.num (Int.ofNat r.den))]
  | none =>
    Json.mkObj [("present", Json.bool false),
                ("num", Json.num 0), ("den", Json.num 1)]

/-- Compute one gather_apply result.

Two queries (chosen by `args[0]`):
* query 0 = `is_applicable` slot check. args: `[0, used, cap, k]`. Emits
  `{"applicable": Bool, "free": Int}`.
* query 1 = `apply` projection. args: `[1, used, cap, n]` where `n` is the
  number of chained applies (typically 1). Emits the post-state
  `{"used": Int, "cap": Int}` after `applyN n`.

Reuses the proved `Formal.GatherApply.isApplicable` / `applyN` directly. -/
def runGatherApply (args : Array Json) : Json :=
  let q := intArg args 0
  let used := (intArg args 1).toNat
  let cap := (intArg args 2).toNat
  let i : Formal.GatherApply.Inv := { used := used, cap := cap }
  if q == 0 then
    let k := (intArg args 3).toNat
    Json.mkObj [("applicable", Json.bool (Formal.GatherApply.isApplicable i k)),
                ("free", Json.num (Int.ofNat (Formal.GatherApply.free i)))]
  else
    let n := (intArg args 3).toNat
    let post := Formal.GatherApply.applyN i n
    Json.mkObj [("used", Json.num (Int.ofNat post.used)),
                ("cap", Json.num (Int.ofNat post.cap))]

/-- Compute one gather_selection result using the SAME proved
`Formal.GatherSelection.selectGatherSource`.

Variable-length candidate list, flattened the same way as `runArbiterSelect`:
`args = [N, c0,r0,mn0,mx0,d0, c1,r1,mn1,mx1,d1, ...]` where `N` is the candidate
count and each record is the 5 ints `[code, rate, minQ, maxQ, dist]`. Builds the
`List Candidate`, runs the lex-argmin selector, and emits the winning candidate's
`code` (or `-1` when the list is empty, mirroring `Option.none`). -/
def runGatherSelection (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let cands : List Formal.GatherSelection.Candidate :=
    (List.range n).map (fun k =>
      let base := 1 + 5 * k
      { code := (intArg args base).toNat,
        rate := (intArg args (base + 1)).toNat,
        minQ := (intArg args (base + 2)).toNat,
        maxQ := (intArg args (base + 3)).toNat,
        dist := (intArg args (base + 4)).toNat })
  let selected : Int :=
    match Formal.GatherSelection.selectGatherSource cands with
    | some c => Int.ofNat c.code
    | none => -1
  Json.mkObj [("selected", Json.num selected)]

/-- Compute one shopping_list result using the SAME proved
`Formal.ShoppingList.shoppingList` (threaded-consume semantics, P2c — and via
the universal `Extracted.Bridges.shopping_list_bridge` also exactly the
mechanically extracted Python image).

args layout (all Nat ≥ 0):
* `[0]`                  nRecipe (number of `(item, sub, qty)` triples)
* `[1 .. 3*nRecipe]`     the triples, flat: item0 sub0 qty0 ...
* next: nOwned, then `(item, qty)` owned pairs flat
* next: queryItem, queryQty

Item codes are Nats on the wire; the model's String items are `toString code`.
The fuel is seeded internally with `recipes.length + 1`, exactly like the
Python `shopping_list`. Emits the raw-leaf work `netSumRaw` of the net
(compared against the Python sum of net deficits over raw-leaf items) and the
sorted net keys (compared against `sorted(net.keys())`). -/
def runShoppingList (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let nRecipe := g 0
  let triples : List (Nat × Nat × Nat) :=
    (List.range nRecipe).map (fun k => (g (1 + 3*k), g (2 + 3*k), g (3 + 3*k)))
  let p1 := 1 + 3*nRecipe
  let nOwned := g p1
  let ownedPairs : List (Nat × Nat) :=
    (List.range nOwned).map (fun k => (g (p1 + 1 + 2*k), g (p1 + 2 + 2*k)))
  let p2 := p1 + 1 + 2*nOwned
  let queryItem := g p2
  let queryQty := g (p2 + 1)
  let parents := (triples.map (fun t => t.1)).eraseDups
  let recipes : Formal.ShoppingList.Recipes :=
    parents.map (fun it =>
      (toString it,
       (triples.filter (fun t => decide (t.1 = it))).map
         (fun t => (toString t.2.1, Int.ofNat t.2.2))))
  let owned : Formal.ShoppingList.Dict Int :=
    ownedPairs.map (fun kv => (toString kv.1, Int.ofNat kv.2))
  let net := Formal.ShoppingList.shoppingList (toString queryItem)
    (Int.ofNat queryQty) recipes owned
  let keys := (net.map (fun kv => (kv.1.toNat?).getD 0)).mergeSort (· ≤ ·)
  let keysJson := Json.arr ((keys.map (fun n => Json.num (Int.ofNat n))).toArray)
  Json.mkObj [("raw_work", Json.num (Formal.ShoppingList.netSumRaw recipes net)),
    ("keys", keysJson)]

/-- Compute one gather_step_target result using the SAME proved
`Formal.StepDispatch.gatherTarget` (which calls
`Formal.StepDispatch.minGathersCount` — the threaded-CONSUME gather lower
bound, P3d; the fuel is seeded internally with `len(recipes) + 1`, exactly
like the Python `min_gathers`).

This is the Piece-C feasibility router: a depth-unreachable equippable root
(min_gathers(root) > equipMaxDepth) routes the GatherMaterials goal to the
strategy's deepest actionable step instead of the deep root recipe.

args layout (all Nat ≥ 0), same recipe/owned prefix as shopping_list:
* `[0]`                  nRecipe (number of `(item, sub, qty)` triples)
* `[1 .. 3*nRecipe]`     the triples, flat: item0 sub0 qty0 ...
* next: nOwned, then `(item, qty)` owned pairs flat
* next: rootItem, stepItem, stepQty, equipMaxDepth

Emits the routed `{"code": _, "qty": _}` — compared against the Python
`gather_step_target`. -/
def runGatherStepTarget (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let nRecipe := g 0
  let triples : List (Nat × Nat × Nat) :=
    (List.range nRecipe).map (fun k => (g (1 + 3*k), g (2 + 3*k), g (3 + 3*k)))
  let p1 := 1 + 3*nRecipe
  let nOwned := g p1
  let ownedPairs : List (Nat × Nat) :=
    (List.range nOwned).map (fun k => (g (p1 + 1 + 2*k), g (p1 + 2 + 2*k)))
  let p2 := p1 + 1 + 2*nOwned
  let rootItem := g p2
  let stepItem := g (p2 + 1)
  let stepQty := g (p2 + 2)
  let equipMaxDepth := g (p2 + 3)
  let parents := (triples.map (fun t => t.1)).eraseDups
  let recipes : Formal.ShoppingList.Recipes :=
    parents.map (fun it =>
      (toString it,
       (triples.filter (fun t => decide (t.1 = it))).map
         (fun t => (toString t.2.1, Int.ofNat t.2.2))))
  let owned : Formal.ShoppingList.Dict Int :=
    ownedPairs.map (fun kv => (toString kv.1, Int.ofNat kv.2))
  let (code, qty) :=
    Formal.StepDispatch.gatherTarget recipes owned (toString rootItem)
      (toString stepItem) (Int.ofNat stepQty) (Int.ofNat equipMaxDepth)
  Json.mkObj [("code", Json.num (Int.ofNat ((code.toNat?).getD 0))),
    ("qty", Json.num qty)]

/-- Compute one monster_drop_selection result using the SAME proved
`Formal.MonsterDropSelection.selectMonsterForDrop`.

Variable-length candidate list, flattened the same way as `runGatherSelection`:
`args = [N, c0,r0,mn0,mx0,d0, c1,r1,mn1,mx1,d1, ...]` where `N` is the candidate
count and each record is the 5 ints `[code, rate, minQ, maxQ, dist]`. Builds the
`List Candidate`, runs the lex-argmin selector, and emits the winning candidate's
`code` (or `-1` when the list is empty, mirroring `Option.none`). -/
def runMonsterDropSelection (args : Array Json) : Json :=
  let n := (intArg args 0).toNat
  let cands : List Formal.MonsterDropSelection.Candidate :=
    (List.range n).map (fun k =>
      let base := 1 + 5 * k
      { code := (intArg args base).toNat,
        rate := (intArg args (base + 1)).toNat,
        minQ := (intArg args (base + 2)).toNat,
        maxQ := (intArg args (base + 3)).toNat,
        dist := (intArg args (base + 4)).toNat })
  let selected : Int :=
    match Formal.MonsterDropSelection.selectMonsterForDrop cands with
    | some c => Int.ofNat c.code
    | none => -1
  Json.mkObj [("selected", Json.num selected)]

/-- Compute one craft_vs_buy result using the SAME proved
`Formal.CraftVsBuy.cheaperAcquisition`.

args layout (5 Ints): `[craftCd, buyCd, totalPrice, gold, reserve]`. Runs the
decision and emits `{"method": 1}` for BUY / `{"method": 0}` for CRAFT, matching
the Python `Method.BUY`/`Method.CRAFT` encoding in the differential test. -/
def runCraftVsBuy (args : Array Json) : Json :=
  let m := Formal.CraftVsBuy.cheaperAcquisition
    (intArg args 0) (intArg args 1) (intArg args 2) (intArg args 3) (intArg args 4)
  let code : Int := match m with
    | Formal.CraftVsBuy.Method.buy => 1
    | Formal.CraftVsBuy.Method.craft => 0
  Json.mkObj [("method", Json.num code)]

/-- Compute one liquidation_venue result using the SAME proved
`Formal.LiquidationVenue.chooseVenue` / `realizedProceeds`.

args layout (3 Ints): `[npcPay, gePresent(0/1), geProceeds]`. When
`gePresent = 0` the standing-order field is `none` (the anti-surrogate guard);
otherwise it is `some geProceeds`. Emits the chosen venue (`1` = GE, `0` = NPC,
matching the Python `Venue.GE`/`Venue.NPC` encoding) and the realized proceeds at
that choice (so the differential pins the gold coupling, not just the label). -/
def runLiquidationVenue (args : Array Json) : Json :=
  let npcPay := intArg args 0
  let geProceeds : Option Int :=
    if intArg args 1 != 0 then some (intArg args 2) else none
  let venue := Formal.LiquidationVenue.chooseVenue npcPay geProceeds
  let code : Int := match venue with
    | Formal.LiquidationVenue.Venue.ge => 1
    | Formal.LiquidationVenue.Venue.npc => 0
  let realized := Formal.LiquidationVenue.realizedProceeds npcPay geProceeds venue
  Json.mkObj [("venue", Json.num code), ("realized", Json.num realized)]

/-- Compute one buy_source_venue result using the SAME proved
`Formal.BuySourceVenue.chooseBuyVenue` / `realizedCost` (the DUAL of
liquidation_venue).

args layout (3 Ints): `[npcPrice, gePresent(0/1), gePrice]`. When `gePresent = 0`
the standing-order field is `none` (the anti-surrogate guard); otherwise it is
`some gePrice`. Emits the chosen venue (`1` = GE, `0` = NPC, matching the Python
`BuyVenue.GE`/`BuyVenue.NPC` encoding) and the realized cost at that choice (so the
differential pins the gold coupling, not just the label). -/
def runBuySourceVenue (args : Array Json) : Json :=
  let npcPrice := intArg args 0
  let gePrice : Option Int :=
    if intArg args 1 != 0 then some (intArg args 2) else none
  let venue := Formal.BuySourceVenue.chooseBuyVenue npcPrice gePrice
  let code : Int := match venue with
    | Formal.BuySourceVenue.BuyVenue.ge => 1
    | Formal.BuySourceVenue.BuyVenue.npc => 0
  let realized := Formal.BuySourceVenue.realizedCost npcPrice gePrice venue
  Json.mkObj [("venue", Json.num code), ("realized", Json.num realized)]

/-- Compute one nearest_tile result using the SAME proved
`Formal.NearestTile.nearestTile`.

args layout: `[originX, originY, N, x0, y0, x1, y1, ...]` — the origin coords, the
tile count `N`, then `N` `(x, y)` Int pairs. Builds the `List Tile`, runs the
Manhattan-lex-argmin selector, and emits the selected tile's `x`/`y` (with
`present = false` when the list is empty, mirroring `Option.none`). -/
def runNearestTile (args : Array Json) : Json :=
  let originX := intArg args 0
  let originY := intArg args 1
  let n := (intArg args 2).toNat
  let tiles : List Formal.NearestTile.Tile :=
    (List.range n).map (fun k =>
      let base := 3 + 2 * k
      (intArg args base, intArg args (base + 1)))
  match Formal.NearestTile.nearestTile originX originY tiles with
  | some t => Json.mkObj [("present", Json.bool true), ("x", Json.num t.1), ("y", Json.num t.2)]
  | none => Json.mkObj [("present", Json.bool false), ("x", Json.num 0), ("y", Json.num 0)]

/-- Compute one consumable_selection result using the SAME proved
`Formal.ConsumableSelection.selectConsumable`.

args layout: `[deficit, N, code0, restore0, qty0, code1, restore1, qty1, ...]` —
the deficit, then `N` candidates, each the 3 ints `[code, restore, qty]`. Builds
the `List Candidate`, runs the overheal-aware lex-argmin, and emits the winning
candidate's `code` (or `-1` when nothing is usable, mirroring `Option.none`). -/
def runConsumableSelection (args : Array Json) : Json :=
  let deficit := intArg args 0
  let n := (intArg args 1).toNat
  let cands : List Formal.ConsumableSelection.Candidate :=
    (List.range n).map (fun k =>
      let base := 2 + 3 * k
      { code := (intArg args base).toNat,
        restore := intArg args (base + 1),
        qty := intArg args (base + 2) })
  let selected : Int :=
    match Formal.ConsumableSelection.selectConsumable deficit cands with
    | some c => Int.ofNat c.code
    | none => -1
  Json.mkObj [("selected", Json.num selected)]

/-- Compute one bank_expansion_timing result using the SAME proved
`Formal.BankExpansionTiming.shouldExpandBank`.

args layout (7 Ints): `[used, capacity, gold, cost, reserve, triggerNum, triggerDen]`.
Runs the firing decision and emits `{"expand": 1}` when it fires / `{"expand": 0}`
otherwise, matching the Python `int(should_expand_bank(...))` encoding in the
differential test. -/
def runBankExpansionTiming (args : Array Json) : Json :=
  let b := Formal.BankExpansionTiming.shouldExpandBank
    (intArg args 0) (intArg args 1) (intArg args 2) (intArg args 3)
    (intArg args 4) (intArg args 5) (intArg args 6)
  Json.mkObj [("expand", Json.num (if b then 1 else 0))]

/-- Compute one event_window result using the SAME proved
`Formal.EventWindow.eventNpcTradeable`.

args layout (6 Ints): `[isEvent, active, hasSpawn, remaining, travel, margin]`,
where the three boolean flags are encoded as `0/1` (and read as `!= 0`) and the
last three are the integer seconds the Python side derives:
* `isEvent`   = `npc_event_code(...) is not None`,
* `active`    = event code ∈ `active_events`,
* `hasSpawn`  = `npc_location(...) is not None`,
* `remaining` = `int((expiration - now).total_seconds())`,
* `travel`    = `manhattan_distance * 5`,
* `margin`    = `10`.

Emits `{"tradeable": 1}` for tradeable / `{"tradeable": 0}` otherwise, matching the
Python `int(event_npc_tradeable(...))` encoding in the differential test. -/
def runEventWindow (args : Array Json) : Json :=
  let isEvent := intArg args 0 != 0
  let active := intArg args 1 != 0
  let hasSpawn := intArg args 2 != 0
  let remaining := intArg args 3
  let travel := intArg args 4
  let margin := intArg args 5
  let b := Formal.EventWindow.eventNpcTradeable isEvent active hasSpawn remaining travel margin
  Json.mkObj [("tradeable", Json.num (if b then 1 else 0))]

/-- Compute one npc_buy_inventory result.

Two queries (chosen by `args[0]`):
* query 0 = `is_applicable` slot+gold check. args:
  `[0, used, cap, quantity, gold, price]`. Emits
  `{"applicable": Bool, "free": Int}`.
* query 1 = `apply` projection: chain ONE buy of `quantity`. args:
  `[1, used, cap, quantity, _gold, _price]`. Emits the post-state
  `{"used": Int, "cap": Int}` after `apply` once.

Reuses the proved `Formal.NpcBuyInventory.isApplicable` / `apply` directly. -/
def runNpcBuyInventory (args : Array Json) : Json :=
  let q := intArg args 0
  let used := (intArg args 1).toNat
  let cap := (intArg args 2).toNat
  let i : Formal.NpcBuyInventory.Inv := { used := used, cap := cap }
  if q == 0 then
    let quantity := (intArg args 3).toNat
    let gold := (intArg args 4).toNat
    let price := (intArg args 5).toNat
    Json.mkObj
      [("applicable", Json.bool (Formal.NpcBuyInventory.isApplicable i quantity gold price)),
       ("free", Json.num (Int.ofNat (Formal.NpcBuyInventory.free i)))]
  else
    let quantity := (intArg args 3).toNat
    let post := Formal.NpcBuyInventory.apply i quantity
    Json.mkObj [("used", Json.num (Int.ofNat post.used)),
                ("cap", Json.num (Int.ofNat post.cap))]

/-- Compute one action_cost_nonneg result using the proved structural cores.

Dispatches on `args[0]`:
* `0`: constant cost  — `[0, k]`               → `{"cost": k}`
* `1`: distance cost  — `[1, base, d]`         → `{"cost": base + d}`
* `2`: qty cost       — `[2, base, qty, d, perUnit]` → `{"cost": base + perUnit*qty + d}`
* `3`: delete cost    — `[3, branch]`          → `{"cost": deleteCost branch}`

Reuses the proved Nat cores directly. The `Rat`-valued history-fraction
core is exercised on the Python side against the structural formula. -/
def runActionCostNonneg (args : Array Json) : Json :=
  let q := intArg args 0
  let cost : Nat :=
    if q == 0 then
      Formal.ActionCostNonneg.constantCost (intArg args 1).toNat
    else if q == 1 then
      Formal.ActionCostNonneg.distanceCost (intArg args 1).toNat (intArg args 2).toNat
    else if q == 2 then
      Formal.ActionCostNonneg.qtyCost (intArg args 1).toNat (intArg args 2).toNat
        (intArg args 3).toNat (intArg args 4).toNat
    else if q == 3 then
      Formal.ActionCostNonneg.deleteCost (intArg args 1).toNat
    else
      0
  Json.mkObj [("cost", Json.num (Int.ofNat cost)),
              ("nonneg", Json.bool true)]

/-- Compute one inventory_chain_safe result. Single shared dispatcher for the
four chain_safe instantiations and the TaskCancel coin step.

Sub-kinds (chosen by `args[0]`):
* `0` = withdraw: `[0, used, cap, quantity, bankQty]` → applicable / free / post.used
* `1` = claim:    `[1, used, cap, hasPending(0/1)]` → applicable / free / post.used
* `2` = unequip:  `[2, used, cap, slotNonEmpty(0/1)]` → applicable / free / post.used
* `3` = task_exchange: `[3, used, cap, coins, minCoins]` → applicable / free / post.used (reward=1)
* `4` = task_cancel coin: `[4, coins, hasTask(0/1)]` → applicable / post.coins -/
def runInventoryChainSafe (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 4 then
    let coins := (intArg args 1).toNat
    let hasTask := intArg args 2 != 0
    let p : Formal.InventoryChainSafe.CoinPurse := { coins := coins }
    let app := Formal.InventoryChainSafe.taskCancelIsApplicable p hasTask
    let post := Formal.InventoryChainSafe.taskCancelApply p
    Json.mkObj [("applicable", Json.bool app),
                ("post_coins", Json.num (Int.ofNat post.coins))]
  else
    let used := (intArg args 1).toNat
    let cap := (intArg args 2).toNat
    let i : Formal.InventoryChainSafe.Inv := { used := used, cap := cap }
    if q == 0 then
      let quantity := (intArg args 3).toNat
      let bankQty := (intArg args 4).toNat
      let app := Formal.InventoryChainSafe.withdrawIsApplicable i quantity bankQty
      let post := Formal.InventoryChainSafe.withdrawApply i quantity
      Json.mkObj [("applicable", Json.bool app),
                  ("free", Json.num (Int.ofNat (Formal.InventoryChainSafe.free i))),
                  ("post_used", Json.num (Int.ofNat post.used)),
                  ("cap", Json.num (Int.ofNat post.cap))]
    else if q == 1 then
      let hasPending := intArg args 3 != 0
      let app := Formal.InventoryChainSafe.claimIsApplicable i hasPending
      let post := Formal.InventoryChainSafe.claimApply i
      Json.mkObj [("applicable", Json.bool app),
                  ("free", Json.num (Int.ofNat (Formal.InventoryChainSafe.free i))),
                  ("post_used", Json.num (Int.ofNat post.used)),
                  ("cap", Json.num (Int.ofNat post.cap))]
    else if q == 2 then
      let slotNonEmpty := intArg args 3 != 0
      let app := Formal.InventoryChainSafe.unequipIsApplicable i slotNonEmpty
      let post := Formal.InventoryChainSafe.unequipApply i
      Json.mkObj [("applicable", Json.bool app),
                  ("free", Json.num (Int.ofNat (Formal.InventoryChainSafe.free i))),
                  ("post_used", Json.num (Int.ofNat post.used)),
                  ("cap", Json.num (Int.ofNat post.cap))]
    else
      let coins := (intArg args 3).toNat
      let minCoins := (intArg args 4).toNat
      let app := Formal.InventoryChainSafe.taskExchangeIsApplicable i coins minCoins
      let post := Formal.InventoryChainSafe.taskExchangeApply i 1
      Json.mkObj [("applicable", Json.bool app),
                  ("free", Json.num (Int.ofNat (Formal.InventoryChainSafe.free i))),
                  ("post_used", Json.num (Int.ofNat post.used)),
                  ("cap", Json.num (Int.ofNat post.cap))]

/-- Compute one inventory_profile result using the SAME proved `overstockExcess`.

    args layout (7 ints): `[held, profileTarget, usefulFloor, used, cap,
    watermarkNum, watermarkDen]`. Emits the overstock excess and the
    under-pressure flag (the two observable outputs of the space-driven core,
    mirroring `overstock_excess` in inventory_caps.py). -/
def runInventoryProfile (args : Array Json) : Json :=
  let held := intArg args 0
  let profileTarget := intArg args 1
  let usefulFloor := intArg args 2
  let used := intArg args 3
  let cap := intArg args 4
  let wnum := intArg args 5
  let wden := intArg args 6
  let excess := Formal.InventoryProfile.overstockExcess held profileTarget usefulFloor
                  used cap wnum wden
  let pressure := Formal.InventoryProfile.underPressure used cap wnum wden
  Json.mkObj [("excess", Json.num excess), ("under_pressure", Json.bool pressure)]

/-- Compute one phase7_invariants result. Three sub-queries:
* `0` = baseValue: `[0, totalNeeded, effectiveNum, effectiveDen]` → `{value_num, value_den}`
* `1` = isApplicable: `[1, invQty, charLevel, hasStats(0/1), itemType, level,
  slot, nSlots, slot0, slot1, ..., itemCode, nEquip, eqSlot0, eqCode0, ...,
  dupAllowed(0/1)]`
  → `{applicable: Bool}` (the itemCode/equipment block encodes the
  2026-06-10 code-already-worn gate; only OCCUPIED slots are listed; the
  final dupAllowed flag is the 2026-06-14 ring carve-out — when set, the
  worn-elsewhere gate is lifted for the candidate)
* `2` = WS invariants: `[2, query, nInv, code0, qty0, …, invMax, hp, maxHp]`
  where query=0 emits inventoryUsed, query=1 emits inventoryFree,
  query=2 emits hpPercent (as num/den).
-/
def runPhase7Invariants (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 0 then
    let totalNeeded := intArg args 1
    let effective : Rat := ratArg args 2
    let v := Formal.Phase7Invariants.baseValue totalNeeded effective
    Json.mkObj [("value_num", Json.num v.num),
                ("value_den", Json.num (Int.ofNat v.den))]
  else if q == 1 then
    let invQty := (intArg args 1).toNat
    let charLevel := (intArg args 2).toNat
    let hasStats := intArg args 3 != 0
    let itemType := (intArg args 4).toNat
    let level := (intArg args 5).toNat
    let slot := (intArg args 6).toNat
    let nSlots := (intArg args 7).toNat
    let slots : List Nat := (List.range nSlots).map (fun k => (intArg args (8 + k)).toNat)
    let tbl : Formal.Phase7Invariants.SlotTable := fun t =>
      if t = itemType then slots else []
    let base := 8 + nSlots
    let itemCode := (intArg args base).toNat
    let nEquip := (intArg args (base + 1)).toNat
    let equipment : List (Nat × Nat) :=
      (List.range nEquip).map (fun k =>
        ((intArg args (base + 2 + 2*k)).toNat, (intArg args (base + 3 + 2*k)).toNat))
    let st : Formal.Phase7Invariants.EquipState :=
      { invQty := invQty, charLevel := charLevel,
        itemCode := itemCode, equipment := equipment }
    let stats : Option Formal.Phase7Invariants.ItemStats :=
      if hasStats then some { itemType := itemType, level := level } else none
    -- 2026-06-14: trailing dup-allowed flag (candidate type ∈ DUPLICATE_SLOT_TYPES),
    -- read AFTER the equipment block (which ends at base + 2 + 2*nEquip).
    let dupAllowed := intArg args (base + 2 + 2*nEquip) != 0
    let app := Formal.Phase7Invariants.isApplicable st stats slot tbl dupAllowed
    Json.mkObj [("applicable", Json.bool app)]
  else
    let subq := intArg args 1
    let nInv := (intArg args 2).toNat
    let inv : List (Nat × Nat) :=
      (List.range nInv).map (fun k =>
        ((intArg args (3 + 2*k)).toNat, (intArg args (4 + 2*k)).toNat))
    let p := 3 + 2*nInv
    let invMax := (intArg args p).toNat
    let hp := (intArg args (p + 1)).toNat
    let maxHp := (intArg args (p + 2)).toNat
    let s : Formal.Phase7Invariants.WS :=
      { inventory := inv, invMax := invMax, hp := hp, maxHp := maxHp }
    if subq == 0 then
      Json.mkObj [("used", Json.num (Int.ofNat (Formal.Phase7Invariants.inventoryUsed s)))]
    else if subq == 1 then
      Json.mkObj [("free", Json.num (Int.ofNat (Formal.Phase7Invariants.inventoryFree s)))]
    else
      let hpp := Formal.Phase7Invariants.hpPercent s
      Json.mkObj [("hp_percent_num", Json.num hpp.num),
                  ("hp_percent_den", Json.num (Int.ofNat hpp.den))]

/-- Compute one store_warmup result. Two sub-queries:
* `0` = median: `[0, nSamples, median, sample0, sample1, ...]` → emits the
  warmup-gated median as `{present, value}`.
* `1` = success_rate: `[1, okCount, total]` → emits the rational rate as
  `{rate_num, rate_den}`.
-/
def runStoreWarmup (args : Array Json) : Json :=
  let q := intArg args 0
  if q == 0 then
    let nSamples := (intArg args 1).toNat
    let median := intArg args 2
    let samples : List Int := (List.range nSamples).map (fun k => intArg args (3 + k))
    match Formal.StoreWarmup.warmupGatedMedian samples median with
    | some v => Json.mkObj [("present", Json.bool true), ("value", Json.num v)]
    | none => Json.mkObj [("present", Json.bool false), ("value", Json.num 0)]
  else
    let okCount := (intArg args 1).toNat
    let total := (intArg args 2).toNat
    let r := Formal.StoreWarmup.warmupGatedSuccessRate okCount total
    Json.mkObj [("rate_num", Json.num r.num),
                ("rate_den", Json.num (Int.ofNat r.den))]

/-- Encode an `Option String` as JSON (None → null, Some s → string). -/
def optStrToJson : Option String → Json
  | none => Json.null
  | some s => Json.str s

/-- Decode a small-int code → `Option String` for the cascade diff.
0 → none; 1 → "A"; 2 → "B"; 3 → "C"; any other → none. -/
def codeToOptStr : Int → Option String
  | 0 => none
  | 1 => some "A"
  | 2 => some "B"
  | 3 => some "C"
  | _ => none

/-- Compute one winnable_cascade result via the SAME proved
`winnableFarmTargetPure`.
args: [taskCode, pathCode, pathWinnable(0/1), pickCode]
    where *Code is the small-int encoding above. -/
def runWinnableCascade (args : Array Json) : Json :=
  let i : Formal.WinnableCascade.CascadeInputs :=
    { taskMonster := codeToOptStr (intArg args 0)
      pathMonster := codeToOptStr (intArg args 1)
      pathWinnable := intArg args 2 != 0
      pickWinnable := codeToOptStr (intArg args 3) }
  Json.mkObj [("result", optStrToJson (Formal.WinnableCascade.winnableFarmTargetPure i))]

/-- Compute one combat_picker result via the SAME proved
`pickWinnableWindowed` (window-preferred picker with the P0-2026-06-09
xp>0 liveness fallback).
args layout:
  [charLevel, nMonsters,
   m0.code, m0.level, m0.winnable(0/1), m0.xpPositive(0/1),
   m1.code, m1.level, m1.winnable(0/1), m1.xpPositive(0/1), ...]
Monster codes are small ints (unique per request — the predicates are
keyed by code via first-match lookup).
Output: { result: code | null }. -/
def runCombatPicker (args : Array Json) : Json :=
  let charLevel := intArg args 0
  let n := (intArg args 1).toNat
  let entry := fun (k : Nat) =>
    (intArg args (2 + 4 * k), intArg args (3 + 4 * k),
     intArg args (4 + 4 * k) != 0, intArg args (5 + 4 * k) != 0)
  let entries : List (Int × Int × Bool × Bool) := (List.range n).map entry
  let monsters : List Formal.CombatTargetExistence.Monster :=
    entries.map (fun e => { code := e.1, level := e.2.1 })
  let winnable : Formal.CombatTargetExistence.WinnableFn := fun m =>
    ((entries.find? (fun e => e.1 == m.code)).map (fun e => e.2.2.1)).getD false
  let xpPos : Formal.CombatTargetExistence.WinnableFn := fun m =>
    ((entries.find? (fun e => e.1 == m.code)).map (fun e => e.2.2.2)).getD false
  match Formal.CombatTargetExistence.pickWinnableWindowed
      charLevel winnable xpPos monsters with
  | none => Json.mkObj [("result", Json.null)]
  | some m => Json.mkObj [("result", Json.num m.code)]

/-- Run the cheapest-path greedy model.
args layout:
  [current, target, maxXp, xpInLevel, nMonsters,
   m0.code, m0.level, m0.xpPerCycle,
   m1.code, m1.level, m1.xpPerCycle, ...]
Output: { blocked: bool, n_segments: int, monster_codes: [int] } -/
def runCheapestPath (args : Array Json) : Json :=
  let current := (intArg args 0).toNat
  let target := (intArg args 1).toNat
  let maxXp := (intArg args 2).toNat
  let xpInLevel := (intArg args 3).toNat
  let nMonsters := (intArg args 4).toNat
  let monsters : List Formal.CheapestPath.Monster :=
    (List.range nMonsters).map (fun k =>
      { code := (intArg args (5 + 3 * k)).toNat
        level := (intArg args (5 + 3 * k + 1)).toNat
        xpPerCycle := (intArg args (5 + 3 * k + 2)).toNat })
  let plan := Formal.CheapestPath.cheapestPath current target maxXp xpInLevel monsters
  Json.mkObj
    [ ("blocked", Json.bool plan.blocked)
    , ("n_segments", Json.num (Int.ofNat plan.segments.length))
    , ("monster_codes",
        Json.arr ((plan.segments.map (fun s => Json.num (Int.ofNat s.monster.code))).toArray))
    , ("total_cycles", Json.num (Int.ofNat plan.totalCycles))
    ]

/-- Compute one items_task_run result using the SAME proved
`Formal.Liveness.ItemsTaskRun.trade` / `applyRun`.

Models the live `TaskTradeAction` (held/progress projection) as `quantity`-fold
application of the proven per-unit `trade`: from `RunState{held, progress,
total}`, fold `quantity` copies of `trade` via `applyRun … (List.replicate
quantity trade)`. Over the reachable trading domain (`held >= quantity ≥ 1` and
`progress + quantity ≤ total`) every per-unit trade fires, so the result is
`held - quantity`, `progress + quantity` — exactly what the live
`task_trade_step` computes.

args layout (4 Ints): `[held, progress, total, quantity]`. Emits the post-state
`{"held": Int, "progress": Int}` and the applicability flag `{"applicable":
Bool}` (whether the per-unit `trade` is fireable at the start state, i.e.
`0 < held ∧ progress < total`). -/
def runItemsTaskRun (args : Array Json) : Json :=
  let held := (intArg args 0).toNat
  let progress := (intArg args 1).toNat
  let total := (intArg args 2).toNat
  let quantity := (intArg args 3).toNat
  let s : Formal.Liveness.ItemsTaskRun.RunState :=
    { held := held, progress := progress, total := total }
  let post := Formal.Liveness.ItemsTaskRun.applyRun s
    (List.replicate quantity Formal.Liveness.ItemsTaskRun.trade)
  let fireable := decide (0 < s.held ∧ s.progress < s.total)
  Json.mkObj [("held", Json.num (Int.ofNat post.held)),
              ("progress", Json.num (Int.ofNat post.progress)),
              ("applicable", Json.bool fireable)]

/-- Compute one task_reservation result via the SAME proved
`reservedDemand` / `consumesReserved` (P0 2026-06-09 task-material
reservation; formal/Formal/TaskReservation.lean).
args layout (flat ints):
  [nRecipe, (item, sub, qty) * nRecipe,
   taskIsItems(0/1), taskCode, taskTotal, taskProgress,
   nNeeded, needed * nNeeded,
   nOwned, (item, qty) * nOwned,
   nQuery, query * nQuery,
   fuel]
Item codes are small Nats. Output:
  { consumes: Bool,
    demand_vals: [lookup demand q | q in query],
    demand_keys: [hasKey demand q | q in query] }. -/
def runTaskReservation (args : Array Json) : Json :=
  let nR := (intArg args 0).toNat
  let triples : List (Nat × Nat × Nat) := (List.range nR).map (fun k =>
    ((intArg args (1 + 3 * k)).toNat, (intArg args (2 + 3 * k)).toNat,
     (intArg args (3 + 3 * k)).toNat))
  let base := 1 + 3 * nR
  let t : Formal.TaskReservation.TaskCtx :=
    { taskIsItems := intArg args base != 0
      taskCode := (intArg args (base + 1)).toNat
      taskTotal := (intArg args (base + 2)).toNat
      taskProgress := (intArg args (base + 3)).toNat }
  let nNeeded := (intArg args (base + 4)).toNat
  let needed := (List.range nNeeded).map
    (fun k => (intArg args (base + 5 + k)).toNat)
  let oBase := base + 5 + nNeeded
  let nOwned := (intArg args oBase).toNat
  let ownedPairs : List (Nat × Nat) := (List.range nOwned).map (fun k =>
    ((intArg args (oBase + 1 + 2 * k)).toNat,
     (intArg args (oBase + 2 + 2 * k)).toNat))
  let qBase := oBase + 1 + 2 * nOwned
  let nQuery := (intArg args qBase).toNat
  let queries := (List.range nQuery).map
    (fun k => (intArg args (qBase + 1 + k)).toNat)
  let fuel := (intArg args (qBase + 1 + nQuery)).toNat
  let recipe : Formal.TaskReservation.Recipe := fun i =>
    (triples.filter (fun tr => tr.1 == i)).map (fun tr => (tr.2.1, tr.2.2))
  let owned : Nat → Nat := fun i =>
    ((ownedPairs.find? (fun p => p.1 == i)).map (fun p => p.2)).getD 0
  let demand := Formal.TaskReservation.reservedDemand recipe fuel t
  let consumes :=
    Formal.TaskReservation.consumesReserved recipe fuel t owned needed
  Json.mkObj
    [ ("consumes", Json.bool consumes)
    , ("demand_vals", Json.arr ((queries.map (fun q =>
        Json.num (Int.ofNat (Formal.TaskReservation.lookup demand q)))).toArray))
    , ("demand_keys", Json.arr ((queries.map (fun q =>
        Json.bool (Formal.TaskReservation.hasKey demand q))).toArray))
    ]

/-- Compute one skill_grind_selection result using the SAME mechanically
extracted `Extracted.SkillGrindSelection.skill_grind_selection_pure`.

args layout (mixed String/Int):
* `[0]`  skill          (String)
* `[1]`  current_level  (Int)
* then candidate blocks of 5:
  `code(String), craft_skill(String), craft_level(Int), mats_missing(Int),
   obtainable(0/1 Int)`

Strings are read directly via `strArg` (the diff side packs them as JSON
strings), so the extracted String-keyed `craft_skill == skill` / `code`
comparisons run unchanged. Emits the chosen in-skill item `{"code": String}`
(`""` when none qualifies). -/
def runSkillGrindSelection (args : Array Json) : Json :=
  let skill := strArg args 0
  let currentLevel := intArg args 1
  let nCand := (args.size - 2) / 5
  let candidates : List Extracted.SkillGrindSelection.GrindCandidate :=
    (List.range nCand).map (fun k =>
      let base := 2 + 5 * k
      { code := strArg args base,
        craft_skill := strArg args (base + 1),
        craft_level := intArg args (base + 2),
        mats_missing := intArg args (base + 3),
        obtainable := intArg args (base + 4) != 0 })
  let result := Extracted.SkillGrindSelection.skill_grind_selection_pure
    skill currentLevel candidates
  Json.mkObj [("code", Json.str result)]

/-- Compute one combine_dispatch result via the EXTRACTED
`Extracted.SkillStepDispatch.combine_dispatch_pure` directly (arbitrary pick
strings, exercising the full-preference branch the wrapper short-circuits).

args: `[skill, current_level, committed_skill, committed_level, full_pick,
relaxed_pick]`. Emits `{"kind": String, "code": String}`. -/
def runCombineDispatch (args : Array Json) : Json :=
  let result := Extracted.SkillStepDispatch.combine_dispatch_pure
    (strArg args 0) (intArg args 1) (strArg args 2) (intArg args 3)
    (strArg args 4) (strArg args 5)
  Json.mkObj [("kind", Json.str result.1), ("code", Json.str result.2)]

/-- Compute one skill_step_dispatch result via the hand model
`Formal.SkillStepDispatch.dispatch` (filter → proved selection → extracted
combine). Mirrors the real `skill_step_dispatch_pure`.

args layout (mixed String/Int):
* `[0]` skill            (String)
* `[1]` current_level    (Int)
* `[2]` committed_skill  (String, "" = none)
* `[3]` committed_level  (Int)
* then candidate blocks of 7:
  `code(String), craft_skill(String), craft_level(Int), mats_missing(Int),
   obtainable(0/1), uses_reserved_full(0/1), uses_reserved_relaxed(0/1)`

Emits `{"kind": String, "code": String}`. -/
def runSkillStepDispatch (args : Array Json) : Json :=
  let skill := strArg args 0
  let currentLevel := intArg args 1
  let committedSkill := strArg args 2
  let committedLevel := intArg args 3
  let nCand := (args.size - 4) / 7
  let candidates : List Formal.SkillStepDispatch.DC :=
    (List.range nCand).map (fun k =>
      let base := 4 + 7 * k
      { code := strArg args base,
        craft_skill := strArg args (base + 1),
        craft_level := intArg args (base + 2),
        mats_missing := intArg args (base + 3),
        obtainable := intArg args (base + 4) != 0,
        uses_reserved_full := intArg args (base + 5) != 0,
        uses_reserved_relaxed := intArg args (base + 6) != 0 })
  let result := Formal.SkillStepDispatch.dispatch
    skill currentLevel committedSkill committedLevel candidates
  Json.mkObj [("kind", Json.str result.1), ("code", Json.str result.2)]

/-- Compute `apply_monster_drops_pure` via `Formal.MonsterDropApply.applyDrops`
from an EMPTY initial inventory. args: `[used, cap, n_drops, n_query]` then the
drop code strings then the query code strings. Emits `{"used": Nat,
"counts": [Nat...]}` (the post count for each query key). -/
def runMonsterDropApply (args : Array Json) : Json :=
  let nDrops := (intArg args 2).toNat
  let nQuery := (intArg args 3).toNat
  let drops := (List.range nDrops).map (fun i => strArg args (4 + i))
  let query := (List.range nQuery).map (fun i => strArg args (4 + nDrops + i))
  let inv : Formal.MonsterDropApply.Inv :=
    { used := (intArg args 0).toNat, cap := (intArg args 1).toNat, counts := fun _ => 0 }
  let out := Formal.MonsterDropApply.applyDrops inv drops
  Json.mkObj [("used", Json.num (Int.ofNat out.used)),
              ("counts", Json.arr ((query.map (fun k => Json.num (Int.ofNat (out.counts k)))).toArray))]

/-- Compute `dispatch_candidate_flags` via `Formal.GrindLadder.flagsFor`.
args: `[cl, craft_level, is_target(0/1), owned(0/1), cann(0/1), n_mats, n_rf,
n_rr]` then the mats / reserved_full / reserved_relaxed code strings in that
order. Emits `{"full": Bool, "relaxed": Bool}`. -/
def runCandidateFlags (args : Array Json) : Json :=
  let cl := intArg args 0
  let nMats := (intArg args 5).toNat
  let nRf := (intArg args 6).toNat
  let nRr := (intArg args 7).toNat
  let mats := (List.range nMats).map (fun i => strArg args (8 + i))
  let rf := (List.range nRf).map (fun i => strArg args (8 + nMats + i))
  let rr := (List.range nRr).map (fun i => strArg args (8 + nMats + nRf + i))
  let rc : Formal.GrindLadder.RC :=
    { code := "x", craft_skill := "s", craft_level := intArg args 1, mats_missing := 0,
      obtainable := true, is_target := intArg args 2 != 0, owned := intArg args 3 != 0,
      recipe_mats := mats }
  let f := Formal.GrindLadder.flagsFor rc cl rf rr (intArg args 4 != 0)
  Json.mkObj [("full", Json.bool f.1), ("relaxed", Json.bool f.2)]

/-- Compute `cannibalize_pure` via `Formal.GrindLadder.cannibalizeModel`.
args: `[cl, n]` then per candidate `[craft_level, obtainable(0/1), owned(0/1)]`.
Emits `{"cannibalize": Bool}`. -/
def runCannibalize (args : Array Json) : Json :=
  let n := (intArg args 1).toNat
  let rcs : List Formal.GrindLadder.RC := (List.range n).map (fun k =>
    let b := 2 + 3 * k
    { code := "c", craft_skill := "s", craft_level := intArg args b, mats_missing := 0,
      obtainable := intArg args (b + 1) != 0, is_target := false,
      owned := intArg args (b + 2) != 0, recipe_mats := [] })
  Json.mkObj [("cannibalize", Json.bool (Formal.GrindLadder.cannibalizeModel (intArg args 0) rcs))]

/-- Dispatch one tagged request `{"kind": ..., "args": [...]}`. -/
-- DoomedMemo: re-probe window ttl(base, maxR, failures).
def runDoomedTtl (args : Array Json) : Json :=
  let r := Formal.DoomedMemo.ttl (intArg args 0).toNat (intArg args 1).toNat (intArg args 2).toNat
  Json.mkObj [("ttl", Json.num (Int.ofNat r))]

-- DoomedMemo: is_doomed decision. args = [base, maxR, sig0, setAt, failures, sig, cycle]
-- (signatures modeled as Int — isDoomed only compares them for equality).
def runDoomedIsDoomed (args : Array Json) : Json :=
  let d := Formal.DoomedMemo.isDoomed (σ := Int)
    (intArg args 0).toNat (intArg args 1).toNat (intArg args 2)
    (intArg args 3).toNat (intArg args 4).toNat (intArg args 5) (intArg args 6).toNat
  Json.mkObj [("doomed", Json.bool d)]

-- SkillGateFastFail: is_plannable fast-fail.
-- args = [targetInNeeded(0/1), hasGate(0/1), curLevel, craftLevel, owned, needed]
def runGatherPlannable (args : Array Json) : Json :=
  let p := Formal.SkillGateFastFail.isPlannable
    (intArg args 0 != 0) (intArg args 1 != 0)
    (intArg args 2).toNat (intArg args 3).toNat (intArg args 4).toNat (intArg args 5).toNat
  Json.mkObj [("plannable", Json.bool p)]

def runOne (item : Json) : Json :=
  let kind := (item.getObjValD "kind" |>.getStr?).toOption.getD ""
  let args := ((item.getObjValD "args" |>.getArr?).toOption.getD #[])
  if kind == "calculate_path" then
    runCalculatePath (intArg args 0) (intArg args 1) (intArg args 2) (intArg args 3)
  else if kind == "task_batch" then
    -- args: [taskBranch(0/1), remaining, mats, free, held]
    runTaskBatch (intArg args 0 != 0) (intArg args 1) (intArg args 2)
      (intArg args 3) (intArg args 4)
  else if kind == "inventory_caps" then
    -- args: [batchBuf, safetyFlr, recipeDemand, equippableCap, consumableCap,
    --        actionCap, taskRemaining, equipped(0/1), qty]
    runInventoryCaps (intArg args 0) (intArg args 1) (intArg args 2)
      (intArg args 3) (intArg args 4) (intArg args 5) (intArg args 6)
      (intArg args 7 != 0) (intArg args 8)
  else if kind == "equip_cap_value" then
    -- args: [equippable(0/1), dominated(0/1)]
    runEquipCapValue (intArg args 0) (intArg args 1)
  else if kind == "consumable_cap_value" then
    -- args: [hpRestore]
    runConsumableCapValue (intArg args 0)
  else if kind == "equip_cap_from_peers" then
    -- args: [equippable(0/1), slotCount, peerCount,
    --        for each peer: fitsAllSlots(0/1), strictlyHigher(0/1),
    --        coversSkillEffects(0/1), ownedCount]
    runEquipCapFromPeers args
  else if kind == "predict_win" then
    runPredictWin (fun i => intArg args i)
  else if kind == "loadout_projection" then
    runLoadoutProjection args
  else if kind == "equipment_scoring" then
    runEquipmentScoring args
  else if kind == "skill_target_curve" then
    runSkillTargetCurve args
  else if kind == "skill_xp_curve" then
    runSkillXpCurve args
  else if kind == "recipe_closure" then
    runRecipeClosure args
  else if kind == "task_feasibility_items" then
    runTaskFeasibilityItems args
  else if kind == "task_feasibility_monster" then
    runTaskFeasibilityMonster args
  else if kind == "prerequisite_graph" then
    runPrerequisiteGraph args
  else if kind == "combat_capable" then
    runCombatCapable args
  else if kind == "objective_attainable" then
    runObjectiveAttainable args
  else if kind == "objective_best_gear" then
    runObjectiveBestGear args
  else if kind == "objective_gap" then
    runObjectiveGap args
  else if kind == "strategy_is_reachable" then
    runStrategyTraversal "is_reachable" args
  else if kind == "strategy_closure_size" then
    runStrategyTraversal "closure_size" args
  else if kind == "strategy_actionable" then
    runStrategyTraversal "actionable" args
  else if kind == "strategy_root_cost" then
    runStrategyTraversal "root_cost" args
  else if kind == "bank_selection" then
    runBankSelection args
  else if kind == "stuck_detector" then
    runStuckDetector args
  else if kind == "priority_band" then
    runPriorityBand args
  else if kind == "owned_count" then
    runOwnedCount args
  else if kind == "upgrade_selection" then
    runUpgradeSelection args
  else if kind == "scalarizer" then
    runScalarizer args
  else if kind == "coins_spent" then
    runCoinsSpent args
  else if kind == "arbiter_select" then
    runArbiterSelect args
  else if kind == "task_decision" then
    runTaskDecision args
  else if kind == "weighted_remaining" then
    runWeightedRemaining args
  else if kind == "low_yield_cancel" then
    runLowYieldCancel args
  else if kind == "strategy_blend" then
    runStrategyBlend args
  else if kind == "decide_key" then
    runDecideKey args
  else if kind == "cycles_for_progress" then
    runCyclesForProgress args
  else if kind == "gather_apply" then
    runGatherApply args
  else if kind == "gather_selection" then
    runGatherSelection args
  else if kind == "shopping_list" then
    runShoppingList args
  else if kind == "gather_step_target" then
    runGatherStepTarget args
  else if kind == "monster_drop_selection" then
    runMonsterDropSelection args
  else if kind == "craft_vs_buy" then
    runCraftVsBuy args
  else if kind == "liquidation_venue" then
    runLiquidationVenue args
  else if kind == "buy_source_venue" then
    runBuySourceVenue args
  else if kind == "nearest_tile" then
    runNearestTile args
  else if kind == "consumable_selection" then
    runConsumableSelection args
  else if kind == "bank_expansion_timing" then
    runBankExpansionTiming args
  else if kind == "event_window" then
    runEventWindow args
  else if kind == "npc_buy_inventory" then
    runNpcBuyInventory args
  else if kind == "action_cost_nonneg" then
    runActionCostNonneg args
  else if kind == "inventory_chain_safe" then
    runInventoryChainSafe args
  else if kind == "inventory_profile" then
    runInventoryProfile args
  else if kind == "phase7_invariants" then
    runPhase7Invariants args
  else if kind == "store_warmup" then
    runStoreWarmup args
  else if kind == "winnable_cascade" then
    runWinnableCascade args
  else if kind == "combat_picker" then
    runCombatPicker args
  else if kind == "cheapest_path" then
    runCheapestPath args
  else if kind == "items_task_run" then
    runItemsTaskRun args
  else if kind == "task_reservation" then
    runTaskReservation args
  else if kind == "skill_grind_selection" then
    runSkillGrindSelection args
  else if kind == "skill_step_dispatch" then
    runSkillStepDispatch args
  else if kind == "combine_dispatch" then
    runCombineDispatch args
  else if kind == "candidate_flags" then
    runCandidateFlags args
  else if kind == "cannibalize" then
    runCannibalize args
  else if kind == "monster_drop_apply" then
    runMonsterDropApply args
  else if kind == "doomed_ttl" then
    runDoomedTtl args
  else if kind == "doomed_is_doomed" then
    runDoomedIsDoomed args
  else if kind == "gather_plannable" then
    runGatherPlannable args
  else
    Json.mkObj [("error", Json.str s!"unknown kind: {kind}")]

def main : IO Unit := do
  let input ← (← IO.getStdin).readToEnd
  match Json.parse input with
  | .error e => IO.eprintln s!"parse error: {e}"; IO.Process.exit 1
  | .ok j =>
    let arr := (j.getArr?).toOption.getD #[]
    let results := arr.map runOne
    IO.println (Json.arr results).compress
