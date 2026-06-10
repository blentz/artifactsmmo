-- GENERATED from src/artifactsmmo_cli/ai/shopping_list.py (sha256: 4cc051d203ef9b5cc3db4696930928d79072b180c4a1c55e6c064119b2f12278) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.ShoppingList

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

/-- Extracted from `_expand` (line 62; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _expand :
    Nat → String → Int → (List (String × List (String × Int))) → ((List (String × Int)) × (List (String × Int))) → ((List (String × Int)) × (List (String × Int)))
  | 0, _, _, _, state =>
    state
  | fuel + 1, item, qty, recipes, state =>
    let owned := (state.1)
    let net := (state.2)
    let held := (_dictGetD owned item 0)
    let used := (min held qty)
    let owned := (_dictSet owned item (held - used))
    let deficit := (qty - used)
    let net := (_dictSet net item ((_dictGetD net item 0) + deficit))
    (if (decide (deficit ≤ 0))
     then
      (owned, net)
     else
      let recipe := (_dictGetD recipes item [])
      (if (decide ((Int.ofNat (List.length recipe)) = 0))
       then
        (owned, net)
       else
        let state := (owned, net)
        let state := List.foldl
          (fun state _x =>
            let material := (_x.1)
            let per_unit := (_x.2)
            let state := (_expand fuel material (per_unit * deficit) recipes state)
            state)
          state recipe
        state))

/-- Extracted from `shopping_list` (line 40). -/
def shopping_list (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) :
    List (String × Int) :=
  let net : List (String × Int) := []
  let state := (_expand (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item qty recipes (owned, net))
  (state.2)

/-- Extracted from `fully_covered_materials` (line 103). -/
def fully_covered_materials (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) :
    List String :=
  let net := (shopping_list item qty recipes owned)
  (List.map (fun _kv => (_kv.1)) (List.filter (fun _kv => (decide ((_kv.2) ≤ 0))) net))

end Extracted.ShoppingList
