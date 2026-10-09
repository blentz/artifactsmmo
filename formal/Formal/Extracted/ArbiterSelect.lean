-- GENERATED from src/artifactsmmo_cli/ai/arbiter_select.py (sha256: 4cd3f7806edb69b871d5b30a09315a3f6ecda1bccd9d35974793d71fc364e4a4) — DO NOT EDIT
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

/-- Extracted from `@dataclass Candidate` (line 65). -/
structure Candidate (Goal : Type) where
  goal : Goal
  repr_ : String
  band : Int

/-- Extracted from `_precedes` (line 81). -/
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

/-- Extracted from `select_interrupt` (line 90). -/
def select_interrupt {Goal : Type} {Action : Type} (interrupts : List (Candidate Goal)) (try_plan : (Goal → (List Action))) (is_satisfied : (Goal → Bool)) :
    ((Option Goal) × (List Action)) :=
  (match (_findSome
      (fun (cand : Candidate Goal) =>
        (if (is_satisfied (cand.goal))
       then
        none
       else
        let plan := (try_plan (cand.goal))
        (if (decide ((Int.ofNat (List.length plan)) > 0))
         then
          (some ((some (cand.goal)), plan))
         else
          none)))
      interrupts) with
  | some _r_1 => _r_1
  | none =>
    (none, []))

/-- Extracted from `select_pure` (line 106). -/
def select_pure {Goal : Type} {Action : Type} (candidates : List (Candidate Goal)) (committed_repr : Option String) (try_plan : (Goal → (List Action))) (is_satisfied : (Goal → Bool)) :
    ((Option Goal) × (List Action) × (Option String)) :=
  let tried_repr : Option String := none
  (match committed_repr with
  | some committed_repr_1 =>
    let committed_cand := (_find (fun (c : Candidate Goal) => (decide ((c.repr_) = committed_repr_1))) candidates)
    (match committed_cand with
    | some committed_cand_2 =>
      (if (!(is_satisfied (committed_cand_2.goal)))
       then
        let lower_band_precedes := ((decide ((committed_cand_2.band) < 5)) && (List.any candidates (fun (c : Candidate Goal) => ((decide ((c.band) < (committed_cand_2.band))) && (_precedes candidates (c.repr_) committed_repr_1)))))
        (if (!lower_band_precedes)
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
                  (if (is_satisfied (cand.goal))
                   then
                    none
                   else
                    let plan := (try_plan (cand.goal))
                    (if (decide ((Int.ofNat (List.length plan)) > 0))
                     then
                      (some ((some (cand.goal)), plan, (some (cand.repr_))))
                     else
                      none))))
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
                (if (is_satisfied (cand.goal))
                 then
                  none
                 else
                  let plan := (try_plan (cand.goal))
                  (if (decide ((Int.ofNat (List.length plan)) > 0))
                   then
                    (some ((some (cand.goal)), plan, (some (cand.repr_))))
                   else
                    none))))
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
              (if (is_satisfied (cand.goal))
               then
                none
               else
                let plan := (try_plan (cand.goal))
                (if (decide ((Int.ofNat (List.length plan)) > 0))
                 then
                  (some ((some (cand.goal)), plan, (some (cand.repr_))))
                 else
                  none))))
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
              (if (is_satisfied (cand.goal))
               then
                none
               else
                let plan := (try_plan (cand.goal))
                (if (decide ((Int.ofNat (List.length plan)) > 0))
                 then
                  (some ((some (cand.goal)), plan, (some (cand.repr_))))
                 else
                  none))))
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
          (if (is_satisfied (cand.goal))
           then
            none
           else
            let plan := (try_plan (cand.goal))
            (if (decide ((Int.ofNat (List.length plan)) > 0))
             then
              (some ((some (cand.goal)), plan, (some (cand.repr_))))
             else
              none))))
        candidates) with
    | some _r_7 => _r_7
    | none =>
      (none, [], none)))

/-- Extracted from `arbitrate` (line 165). -/
def arbitrate {Goal : Type} {Action : Type} (interrupts : List (Candidate Goal)) (candidates : List (Candidate Goal)) (committed_repr : Option String) (try_plan : (Goal → (List Action))) (is_satisfied : (Goal → Bool)) :
    ((Option Goal) × (List Action) × (Option String)) :=
  let interrupt := (select_interrupt interrupts try_plan is_satisfied)
  (if (decide ((Int.ofNat (List.length (interrupt.2))) > 0))
   then
    ((interrupt.1), (interrupt.2), committed_repr)
   else
    (select_pure candidates committed_repr try_plan is_satisfied))

end Extracted.ArbiterSelect
