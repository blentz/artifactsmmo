-- GENERATED from src/artifactsmmo_cli/ai/min_gather_steps.py (sha256: c4ec89d7b29f0789c4df1c2e23d0f3114aefc407cdcc87e3feef4fedd8216f1b) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.MinGatherSteps

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

/-- Extracted from `_min_gather_steps` (line 38; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _min_gather_steps :
    Nat → String → Int → (List (String × List (String × Int))) → ((List String) × (List (String × Int))) → ((List String) × (List (String × Int)))
  | 0, item, _, _, state =>
    ((if (List.contains (state.1) item) then (state.1) else ((state.1) ++ [item])), (state.2))
  | fuel + 1, item, qty, recipes, state =>
    let leaves := (state.1)
    let owned := (state.2)
    let held := (_dictGetD owned item 0)
    let used := (min held qty)
    let owned := (_dictSet owned item (held - used))
    let remaining := (qty - used)
    (if (decide (remaining ≤ 0))
     then
      (leaves, owned)
     else
      let recipe := (_dictGetD recipes item [])
      (if (decide ((Int.ofNat (List.length recipe)) = 0))
       then
        ((if (List.contains leaves item) then leaves else (leaves ++ [item])), owned)
       else
        let state := (leaves, owned)
        let state := List.foldl
          (fun state _x =>
            let material := (_x.1)
            let per_unit := (_x.2)
            let state := (_min_gather_steps fuel material (per_unit * remaining) recipes state)
            state)
          state recipe
        state))

/-- Extracted from `min_gather_steps` (line 31). -/
def min_gather_steps (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) :
    Int :=
  let initial_state : ((List String) × (List (String × Int))) := ([], owned)
  let state := (_min_gather_steps (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item qty recipes initial_state)
  (Int.ofNat (List.length (state.1)))

end Extracted.MinGatherSteps
