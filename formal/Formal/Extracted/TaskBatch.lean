-- GENERATED from src/artifactsmmo_cli/ai/task_batch.py (sha256: 3578392413589109184a1e77b686fd42045da49e91b27b5a8c9875c6596c5874) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).
import Formal.Extracted.RecipeClosure

namespace Extracted.TaskBatch

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Extracted module constant `BATCH_CAP` (line 24). -/
def BATCH_CAP : Int := 10

/-- Extracted module constant `_MIN_FREE_SLOTS` (line 27). -/
def _MIN_FREE_SLOTS : Int := 3

/-- Extracted from `craft_batch_size_pure` (line 31). -/
def craft_batch_size_pure (code : Option String) (demand : Int) (inventory : List (String × Int)) (inventory_free : Int) (recipes : List (String × List (String × Int))) (drops : List (String × String)) (yields : List (String × Int)) :
    Int :=
  (match code with
  | none =>
    1
  | some code_1 =>
    (if (decide (demand ≤ 0))
     then
      1
     else
      let no_visited : List (String × Int) := []
      let mats_per_unit := (Extracted.RecipeClosure._raw_units (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) code_1 recipes yields no_visited)
      (if (decide (mats_per_unit = 0))
       then
        (max 1 (min demand BATCH_CAP))
       else
        let closure : List (String × Int) := []
        let closure := (Extracted.RecipeClosure._closure_visited (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) code_1 recipes closure)
        let held_recipe := 0
        let held_recipe := List.foldl
          (fun held_recipe _x =>
            let _res := (_x.1)
            let drop_item := (_x.2)
            let held_recipe := (if (decide ((_dictGetD closure drop_item 0) = 1)) then (held_recipe + (_dictGetD inventory drop_item 0)) else held_recipe)
            held_recipe)
          held_recipe drops
        let usable := ((inventory_free + held_recipe) - _MIN_FREE_SLOTS)
        let fit := (Int.fdiv usable mats_per_unit)
        (max 1 (min demand (min fit BATCH_CAP))))))

/-- Extracted from `task_batch_size_pure` (line 70). -/
def task_batch_size_pure (task_type : Option String) (task_code : Option String) (task_total : Int) (task_progress : Int) (inventory : List (String × Int)) (inventory_free : Int) (recipes : List (String × List (String × Int))) (drops : List (String × String)) (yields : List (String × Int)) :
    Int :=
  (if ((!(decide (task_type = some "items"))) || (decide (task_code = some "")) || (decide (task_total ≤ 0)))
   then
    1
   else
    let remaining := (task_total - task_progress)
    (if (decide (remaining ≤ 0))
     then
      1
     else
      (craft_batch_size_pure task_code remaining inventory inventory_free recipes drops yields)))

end Extracted.TaskBatch
