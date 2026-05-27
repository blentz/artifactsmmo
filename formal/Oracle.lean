import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps

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
