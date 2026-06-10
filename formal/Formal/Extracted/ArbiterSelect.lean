-- GENERATED from src/artifactsmmo_cli/ai/arbiter_select.py (sha256: 629df959646655f6755e0227725b3cab6ebfbdb1393c0934998c0627d96dc971) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.ArbiterSelect

/-- Python `next((x for x in xs if p(x)), None)`: the first element
satisfying `p`, else `none` (value-polymorphic). -/
def _find {α : Type} (p : α → Bool) (xs : List α) : Option α :=
  match xs with
  | [] => none
  | x :: rest => if p x then some x else _find p rest

/-- Index search from a running offset — the recursion behind `_findIdx`. -/
def _findIdxFrom {α : Type} (p : α → Bool) (i : Int) (xs : List α) : Option Int :=
  match xs with
  | [] => none
  | x :: rest => if p x then some i else _findIdxFrom p (i + 1) rest

/-- Python `next((i for i, x in enumerate(xs) if p(x)), None)`: the index of
the first element satisfying `p`, else `none` (value-polymorphic). -/
def _findIdx {α : Type} (p : α → Bool) (xs : List α) : Option Int :=
  _findIdxFrom p 0 xs

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

/-- Extracted from `@dataclass Candidate` (line 34). -/
structure Candidate (Goal : Type) where
  goal : Goal
  is_means : Bool
  repr_ : String

/-- Extracted from `_precedes` (line 41). -/
def _precedes {Goal : Type} (candidates : List (Candidate Goal)) (a_repr : String) (b_repr : String) :
    Bool :=
  let a_idx := (_findIdx (fun (c : Candidate Goal) => (decide ((c.repr_) = a_repr))) candidates)
  let b_idx := (_findIdx (fun (c : Candidate Goal) => (decide ((c.repr_) = b_repr))) candidates)
  (match a_idx with
  | none =>
    false
  | some a_idx_1 =>
    (match b_idx with
    | none =>
      false
    | some b_idx_2 =>
      (decide (a_idx_1 < b_idx_2))))

/-- Extracted from `select_pure` (line 50). -/
def select_pure {Goal : Type} {Action : Type} (candidates : List (Candidate Goal)) (committed_repr : Option String) (try_plan : (Goal → (List Action))) (is_satisfied : (Goal → Bool)) (is_suppressed : (Goal → Bool)) :
    ((Option Goal) × (List Action) × (Option String)) :=
  let tried_repr : Option String := none
  (match committed_repr with
  | some committed_repr_1 =>
    let committed_cand := (_find (fun (c : Candidate Goal) => ((c.is_means) && (decide ((c.repr_) = committed_repr_1)))) candidates)
    (match committed_cand with
    | some committed_cand_2 =>
      (if ((!(is_satisfied (committed_cand_2.goal))) && (!(is_suppressed (committed_cand_2.goal))))
       then
        let guard_reprs := (List.map (fun (c : Candidate Goal) => (c.repr_)) (List.filter (fun (c : Candidate Goal) => (!(c.is_means))) candidates))
        let guard_precedes := (List.any guard_reprs (fun (gr : String) => (_precedes candidates gr committed_repr_1)))
        (if (!guard_precedes)
         then
          let plan := (try_plan (committed_cand_2.goal))
          let tried_repr := (some committed_repr_1)
          (if (decide ((Int.ofNat (List.length plan)) > 0))
           then
            ((some (committed_cand_2.goal)), plan, (some committed_repr_1))
           else
            (match (_findSome
                (fun (cand : Candidate Goal) =>
                  (if (decide (tried_repr = some (cand.repr_)))
                 then
                  none
                 else
                  (if (is_suppressed (cand.goal))
                   then
                    none
                   else
                    (if (is_satisfied (cand.goal))
                     then
                      none
                     else
                      let plan := (try_plan (cand.goal))
                      (if (decide ((Int.ofNat (List.length plan)) > 0))
                       then
                        let new_committed := (if (cand.is_means) then (some (cand.repr_)) else none)
                        (some ((some (cand.goal)), plan, new_committed))
                       else
                        none)))))
                candidates) with
            | some _r_3 => _r_3
            | none =>
              (none, [], none)))
         else
          (match (_findSome
              (fun (cand : Candidate Goal) =>
                (if (decide (tried_repr = some (cand.repr_)))
               then
                none
               else
                (if (is_suppressed (cand.goal))
                 then
                  none
                 else
                  (if (is_satisfied (cand.goal))
                   then
                    none
                   else
                    let plan := (try_plan (cand.goal))
                    (if (decide ((Int.ofNat (List.length plan)) > 0))
                     then
                      let new_committed := (if (cand.is_means) then (some (cand.repr_)) else none)
                      (some ((some (cand.goal)), plan, new_committed))
                     else
                      none)))))
              candidates) with
          | some _r_4 => _r_4
          | none =>
            (none, [], none)))
       else
        (match (_findSome
            (fun (cand : Candidate Goal) =>
              (if (decide (tried_repr = some (cand.repr_)))
             then
              none
             else
              (if (is_suppressed (cand.goal))
               then
                none
               else
                (if (is_satisfied (cand.goal))
                 then
                  none
                 else
                  let plan := (try_plan (cand.goal))
                  (if (decide ((Int.ofNat (List.length plan)) > 0))
                   then
                    let new_committed := (if (cand.is_means) then (some (cand.repr_)) else none)
                    (some ((some (cand.goal)), plan, new_committed))
                   else
                    none)))))
            candidates) with
        | some _r_5 => _r_5
        | none =>
          (none, [], none)))
    | none =>
        (match (_findSome
            (fun (cand : Candidate Goal) =>
              (if (decide (tried_repr = some (cand.repr_)))
             then
              none
             else
              (if (is_suppressed (cand.goal))
               then
                none
               else
                (if (is_satisfied (cand.goal))
                 then
                  none
                 else
                  let plan := (try_plan (cand.goal))
                  (if (decide ((Int.ofNat (List.length plan)) > 0))
                   then
                    let new_committed := (if (cand.is_means) then (some (cand.repr_)) else none)
                    (some ((some (cand.goal)), plan, new_committed))
                   else
                    none)))))
            candidates) with
        | some _r_6 => _r_6
        | none =>
          (none, [], none)))
  | none =>
    (match (_findSome
        (fun (cand : Candidate Goal) =>
          (if (decide (tried_repr = some (cand.repr_)))
         then
          none
         else
          (if (is_suppressed (cand.goal))
           then
            none
           else
            (if (is_satisfied (cand.goal))
             then
              none
             else
              let plan := (try_plan (cand.goal))
              (if (decide ((Int.ofNat (List.length plan)) > 0))
               then
                let new_committed := (if (cand.is_means) then (some (cand.repr_)) else none)
                (some ((some (cand.goal)), plan, new_committed))
               else
                none)))))
        candidates) with
    | some _r_7 => _r_7
    | none =>
      (none, [], none)))

end Extracted.ArbiterSelect
