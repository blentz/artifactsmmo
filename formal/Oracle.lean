import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin

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
