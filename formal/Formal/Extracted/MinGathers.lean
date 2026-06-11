-- GENERATED from src/artifactsmmo_cli/ai/min_gathers.py (sha256: b7706a2ba2563d6f815ff66ff3adb08b80e03c14a321682cbfad1e42cf96a88c) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.MinGathers

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

/-- Extracted from `_min_gathers` (line 43; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _min_gathers :
    Nat → String → Int → (List (String × List (String × Int))) → (Int × (List (String × Int))) → (Int × (List (String × Int)))
  | 0, _, qty, _, state =>
    (((state.1) + qty), (state.2))
  | fuel + 1, item, qty, recipes, state =>
    let total := (state.1)
    let owned := (state.2)
    let held := (_dictGetD owned item 0)
    let used := (min held qty)
    let owned := (_dictSet owned item (held - used))
    let remaining := (qty - used)
    (if (decide (remaining ≤ 0))
     then
      (total, owned)
     else
      let recipe := (_dictGetD recipes item [])
      (if (decide ((Int.ofNat (List.length recipe)) = 0))
       then
        ((total + remaining), owned)
       else
        let state := (total, owned)
        let state := List.foldl
          (fun state _x =>
            let material := (_x.1)
            let per_unit := (_x.2)
            let state := (_min_gathers fuel material (per_unit * remaining) recipes state)
            state)
          state recipe
        state))

/-- Extracted from `min_gathers` (line 28). -/
def min_gathers (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) :
    Int :=
  let state := (_min_gathers (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item qty recipes (0, owned))
  (state.1)

end Extracted.MinGathers
