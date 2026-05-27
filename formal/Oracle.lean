import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin
open Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve Formal.RecipeClosure

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
