import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin
open Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve

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
