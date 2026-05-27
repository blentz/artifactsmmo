import Formal
import Lean.Data.Json

open Lean Formal.CalculatePath

/-- Compute one path/cost result using the SAME proved `pathFrom`/`manhattan`. -/
def runOne (sx sy ex ey : Int) : Json :=
  let start : Coord := (sx, sy)
  let dst : Coord := (ex, ey)
  let steps := pathFrom start dst
  let stepsJson := Json.arr ((steps.map (fun c => Json.arr #[Json.num c.1, Json.num c.2])).toArray)
  Json.mkObj [("steps", stepsJson), ("total_distance", Json.num (manhattan start dst)),
    ("estimated_time", Json.num (Int.ofNat (estimatedTime start dst)))]

def main : IO Unit := do
  let input ← (← IO.getStdin).readToEnd
  match Json.parse input with
  | .error e => IO.eprintln s!"parse error: {e}"; IO.Process.exit 1
  | .ok j =>
    let arr := (j.getArr?).toOption.getD #[]
    let results := arr.map (fun item =>
      let xs := ((item.getArr?).toOption.getD #[]).map (fun n => (n.getInt?).toOption.getD 0)
      runOne (xs[0]!) (xs[1]!) (xs[2]!) (xs[3]!))
    IO.println (Json.arr results).compress
