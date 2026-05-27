import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin
open Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve Formal.RecipeClosure
open Formal.BankSelection Formal.PriorityBand Formal.OwnedCount

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

/-- Compute one inventory_caps result using the SAME proved `cap`/`overstock`. -/
def runInventoryCaps (batchBuf safetyFlr recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) : Json :=
  let c := capWith batchBuf safetyFlr recipeDemand equippable actionCap taskRemaining equipped
  let o := overstockWith batchBuf safetyFlr recipeDemand equippable actionCap taskRemaining equipped qty
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
  let verdict := predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst
  Json.mkObj [("win", Json.bool verdict), ("raw_player", Json.num rawPlayer),
    ("raw_monster", Json.num rawMonster)]

/-- Read an Int field (defaulting to 0) from a JSON array of Ints. -/
def intArg (xs : Array Json) (i : Nat) : Int := (xs[i]!.getInt?).toOption.getD 0

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

/-- Build a model `Item` from a flat 11-int block:
`[code, level, fits(0/1), atk0..atk3, res0..res3]`. Element keys are 0..3. -/
def itemFromBlock (b : Nat → Int) : Item :=
  { code := b 0, level := b 1, fits := b 2 != 0,
    attack := [(0, b 3), (1, b 4), (2, b 5), (3, b 6)],
    resistance := [(0, b 7), (1, b 8), (2, b 9), (3, b 10)] }

/-- Build an `ElemStats` (monster atk OR res) from 4 ints at offset `o`. -/
def elemFromArgs (args : Array Json) (o : Nat) : ElemStats :=
  [(0, intArg args o), (1, intArg args (o+1)), (2, intArg args (o+2)), (3, intArg args (o+3))]

/-- Compute one equipment_scoring per-slot pick using the SAME proved `pickSlot`.

args layout:
* 0:        playerLevel
* 1:        scoreKind (0 = weapon, 1 = armor)
* 2..5:     monster element stats (resistance for weapon, attack for armor)
* 6:        currentPresent (0/1)
* 7..17:    current item block (11 ints; ignored when currentPresent = 0)
* 18..:     candidate item blocks, 11 ints each

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
  -- candidate blocks start at 18, 11 ints each
  let nCand := (args.size - 18) / 11
  let items : List Item :=
    (List.range nCand).map (fun k => itemFromBlock (fun i => intArg args (18 + k * 11 + i)))
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
* `[5 .. 5+3n-1]`  n records flat: state0 goal0 noPlan0(0/1) state1 ...
  (oldest first, mirroring `list(deque)`)

Emits the `detect()` verdict ("frozen"/"osc"/"noprog"/"none") and the three
window lengths (to pin `_recent_since`'s index arithmetic). -/
def runStuckDetector (args : Array Json) : Json :=
  let g := fun i => (intArg args i).toNat
  let counter := g 0
  let ackFrozen := g 1
  let ackOsc := g 2
  let ackNoprog := g 3
  let n := g 4
  let history : List Formal.StuckDetector.Rec :=
    (List.range n).map (fun k =>
      { state := g (5 + 3*k), goal := g (6 + 3*k), noPlan := g (7 + 3*k) != 0 })
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
  Json.mkObj [("detect", Json.str verdict),
    ("frozen_window_len", Json.num (Int.ofNat frozenLen)),
    ("osc_window_len", Json.num (Int.ofNat oscLen)),
    ("noprog_window_len", Json.num (Int.ofNat noprogLen))]

/-- Compute one priority_band result using the SAME proved `clampIntoBand`.
args: [floor, ceiling, bonus]. Emits the clamped band value. -/
def runPriorityBand (args : Array Json) : Json :=
  Json.mkObj [("clamped",
    Json.num (clampIntoBand (intArg args 0) (intArg args 1) (intArg args 2)))]

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

/-- Dispatch one tagged request `{"kind": ..., "args": [...]}`. -/
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
    -- args: [batchBuf, safetyFlr, recipeDemand, equippable(0/1), actionCap, taskRemaining, equipped(0/1), qty]
    runInventoryCaps (intArg args 0) (intArg args 1) (intArg args 2)
      (intArg args 3 != 0) (intArg args 4) (intArg args 5) (intArg args 6 != 0) (intArg args 7)
  else if kind == "predict_win" then
    runPredictWin (fun i => intArg args i)
  else if kind == "loadout_projection" then
    runLoadoutProjection args
  else if kind == "equipment_scoring" then
    runEquipmentScoring args
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
