-- GENERATED from src/artifactsmmo_cli/ai/task_reservation.py (sha256: 803091ed686af9a90e405725837d3e4947703105ecabe941b26f09dc5253e3d7) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).
import Formal.Extracted.RecipeClosure

namespace Extracted.TaskReservation

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- A Python `for` loop whose body only `continue`s or `return`s: the first
iteration producing `some` wins; `none` falls through to the code after the
loop (value-polymorphic). -/
def _findSome {α β : Type} (f : α → Option β) (xs : List α) : Option β :=
  match xs with
  | [] => none
  | x :: rest =>
    match f x with
    | some r => some r
    | none => _findSome f rest

/-- Extracted from `task_reserved_demand_pure` (line 35). -/
def task_reserved_demand_pure (task_type : Option String) (task_code : Option String) (task_total : Int) (task_progress : Int) (recipes : List (String × List (String × Int))) :
    List (String × Int) :=
  (match task_code with
  | none =>
    []
  | some task_code_1 =>
    (if ((!(decide (task_type = some "items"))) || (decide (task_code_1 = "")))
     then
      []
     else
      let remaining := (task_total - task_progress)
      (if (decide (remaining ≤ 0))
       then
        []
       else
        let no_visited : List (String × Int) := []
        let demand : List (String × Int) := []
        let demand := (Extracted.RecipeClosure._closure_demand (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) task_code_1 remaining recipes no_visited demand)
        demand)))

/-- Extracted from `consumes_reserved_pure` (line 59). -/
def consumes_reserved_pure (needed : List (String × Int)) (task_type : Option String) (task_code : Option String) (task_total : Int) (task_progress : Int) (inventory : List (String × Int)) (bank_items : Option (List (String × Int))) (recipes : List (String × List (String × Int))) :
    Bool :=
  let demand := (task_reserved_demand_pure task_type task_code task_total task_progress recipes)
  (if (decide ((Int.ofNat (List.length demand)) = 0))
   then
    false
   else
    let no_visited : List (String × Int) := []
    let conflict : List (String × Int) := []
    let conflict := List.foldl
      (fun conflict _x =>
        let item := (_x.1)
        let _qty := (_x.2)
        let conflict := (Extracted.RecipeClosure._closure_demand (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item 1 recipes no_visited conflict)
        conflict)
      conflict needed
    let bank : List (String × Int) := []
    (match bank_items with
    | some bank_items_1 =>
      let bank := bank_items_1
      (match (_findSome
          (fun (_x : (String × Int)) =>
            let item := (_x.1)
            let _conflict_qty := (_x.2)
            (if (decide ((_dictGetD demand item 0) = 0))
           then
            none
           else
            let owned := ((_dictGetD inventory item 0) + (_dictGetD bank item 0))
            (if ((decide (0 < owned)) && (decide (owned ≤ (_dictGetD demand item 0))))
             then
              (some true)
             else
              none)))
          conflict) with
      | some _r_2 => _r_2
      | none =>
        false)
    | none =>
      (match (_findSome
          (fun (_x : (String × Int)) =>
            let item := (_x.1)
            let _conflict_qty := (_x.2)
            (if (decide ((_dictGetD demand item 0) = 0))
           then
            none
           else
            let owned := ((_dictGetD inventory item 0) + (_dictGetD bank item 0))
            (if ((decide (0 < owned)) && (decide (owned ≤ (_dictGetD demand item 0))))
             then
              (some true)
             else
              none)))
          conflict) with
      | some _r_3 => _r_3
      | none =>
        false)))

end Extracted.TaskReservation
