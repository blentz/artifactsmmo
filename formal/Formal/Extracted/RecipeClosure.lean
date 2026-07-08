-- GENERATED from src/artifactsmmo_cli/ai/recipe_closure.py (sha256: 5a26452b3b9c7895cadd0952cfbffce508df42800e08fb813dc126e604358e5b) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.RecipeClosure

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Python `d[k] = v` over an insertion-ordered association list: replace the
first matching entry in place, else append — every other entry is preserved
bit-for-bit, mirroring dict update semantics (value-polymorphic). -/
def _dictSet {α : Type} (m : List (String × α)) (k : String) (v : α) : List (String × α) :=
  match m with
  | [] => [(k, v)]
  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: _dictSet rest k v

/-- Extracted from `_closure_visited` (line 62; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _closure_visited :
    Nat → String → (List (String × List (String × Int))) → (List (String × Int)) → (List (String × Int))
  | 0, _, _, visited =>
    visited
  | fuel + 1, material, recipes, visited =>
    (if (decide ((_dictGetD visited material 0) = 1))
     then
      visited
     else
      let visited := (_dictSet visited material 1)
      let recipe := (_dictGetD recipes material [])
      let visited := List.foldl
        (fun visited _x =>
          let sub_mat := (_x.1)
          let _qty := (_x.2)
          let visited := (_closure_visited fuel sub_mat recipes visited)
          visited)
        visited recipe
      visited)

/-- Extracted from `_raw_units` (line 78; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _raw_units :
    Nat → String → (List (String × List (String × Int))) → (List (String × Int)) → (List (String × Int)) → Int
  | 0, _, _, _, _ =>
    1
  | fuel + 1, item, recipes, yields, visited =>
    (if (decide ((_dictGetD visited item 0) = 1))
     then
      1
     else
      let recipe := (_dictGetD recipes item [])
      (if (decide ((Int.ofNat (List.length recipe)) = 0))
       then
        1
       else
        let deeper := visited
        let deeper := (_dictSet deeper item 1)
        let total := 0
        let total := List.foldl
          (fun total _x =>
            let sub := (_x.1)
            let qty := (_x.2)
            let total := (total + (qty * (_raw_units fuel sub recipes yields deeper)))
            total)
          total recipe
        let y := (_dictGetD yields item 1)
        (-(Int.fdiv (-total) y))))

/-- Extracted from `_closure_demand` (line 104; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _closure_demand :
    Nat → String → Int → (List (String × List (String × Int))) → (List (String × Int)) → (List (String × Int)) → (List (String × Int)) → (List (String × Int))
  | 0, _, _, _, _, _, out =>
    out
  | fuel + 1, root, multiplier, recipes, yields, visited, out =>
    (if (decide ((_dictGetD visited root 0) = 1))
     then
      out
     else
      let sub_visited := visited
      let sub_visited := (_dictSet sub_visited root 1)
      (if (decide (multiplier > (_dictGetD out root 0)))
       then
        let out := (_dictSet out root multiplier)
        let recipe := (_dictGetD recipes root [])
        let y := (_dictGetD yields root 1)
        let batches := (-(Int.fdiv (-multiplier) y))
        let out := List.foldl
          (fun out _x =>
            let mat := (_x.1)
            let qty_per := (_x.2)
            (if (decide (qty_per ≤ 0))
             then
              out
             else
              let out := (_closure_demand fuel mat (batches * qty_per) recipes yields sub_visited out)
              out))
          out recipe
        out
       else
        let recipe := (_dictGetD recipes root [])
        let y := (_dictGetD yields root 1)
        let batches := (-(Int.fdiv (-multiplier) y))
        let out := List.foldl
          (fun out _x =>
            let mat := (_x.1)
            let qty_per := (_x.2)
            (if (decide (qty_per ≤ 0))
             then
              out
             else
              let out := (_closure_demand fuel mat (batches * qty_per) recipes yields sub_visited out)
              out))
          out recipe
        out))

/-- Extracted from `recipe_closure_pure` (line 138). -/
def recipe_closure_pure (roots : List String) (recipes : List (String × List (String × Int))) (drops : List (String × String)) :
    ((List String) × (List String)) :=
  let visited : List (String × Int) := []
  let visited := List.foldl
    (fun visited root =>
      let visited := (_closure_visited (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) root recipes visited)
      visited)
    visited roots
  let needed_resources : List String := (List.map (fun _kv => (_kv.1)) (List.filter (fun _kv => (decide ((_dictGetD visited (_kv.2) 0) = 1))) drops))
  let craftable_mats : List String := (List.map (fun _kv => (_kv.1)) (List.filter (fun _kv => (decide ((Int.ofNat (List.length (_dictGetD recipes (_kv.1) []))) > 0))) visited))
  (needed_resources, craftable_mats)

end Extracted.RecipeClosure
