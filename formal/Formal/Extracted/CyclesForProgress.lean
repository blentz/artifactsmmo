-- GENERATED from src/artifactsmmo_cli/ai/learning/cycles_for_progress_core.py (sha256: f9e7cb5295f7a9c03121e4045c4605104862bf35e1914ca6efc8f8fbaf754b44) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.CyclesForProgress

/-- Insert into an ascending-sorted list — the inner step of `_sortInt`. -/
def _sortIntInsert (x : Int) : List Int → List Int
  | [] => [x]
  | y :: ys => if x ≤ y then x :: y :: ys else y :: _sortIntInsert x ys

/-- Python `sorted` over ints (insertion sort). Sorting a multiset of ints is
order-independent, so this agrees with Python's stable Timsort on every input. -/
def _sortInt : List Int → List Int
  | [] => []
  | x :: xs => _sortIntInsert x (_sortInt xs)

/-- Element at a Nat index, default 0 past the end (the recursion behind
`_nthInt`). -/
def _nthIntNat : List Int → Nat → Int
  | [], _ => 0
  | x :: _, 0 => x
  | _ :: xs, n + 1 => _nthIntNat xs n

/-- Python `xs[i]` on a list of ints. TOTAL: an out-of-range index reads 0 and
a negative index clamps to 0 where Python raises/wraps — extracted cores keep
indices in range by construction. -/
def _nthInt (xs : List Int) (i : Int) : Int := _nthIntNat xs i.toNat

/-- Extracted from `@dataclass CycleRow` (line 95). -/
structure CycleRow where
  cycle_index : Int
  task_progress : Option Int
  cycles_to_satisfy : Option Int

/-- Extracted from `_strict_step` (line 106). -/
def _strict_step (state : ((List Int) × (Option Int) × (Option Int))) (cycle : CycleRow) :
    ((List Int) × (Option Int) × (Option Int)) :=
  let intervals := (state.1)
  let last_progress_at := (state.2.1)
  let prev_progress := (state.2.2)
  let tp := (cycle.task_progress)
  (match prev_progress with
  | none =>
    (intervals, last_progress_at, tp)
  | some prev_progress_1 =>
    (match tp with
    | none =>
      (intervals, last_progress_at, tp)
    | some tp_2 =>
      (if (decide (tp_2 ≤ prev_progress_1))
       then
        (intervals, last_progress_at, (some tp_2))
       else
        (match last_progress_at with
        | none =>
          (intervals, (some (cycle.cycle_index)), (some tp_2))
        | some last_progress_at_3 =>
          ((intervals ++ [((cycle.cycle_index) - last_progress_at_3)]), (some (cycle.cycle_index)), (some tp_2))))))

/-- Extracted from `_satisfy_step` (line 132). -/
def _satisfy_step (intervals : List Int) (cycle : CycleRow) :
    List Int :=
  let cts := (cycle.cycles_to_satisfy)
  (match cts with
  | none =>
    intervals
  | some cts_1 =>
    (if (decide (cts_1 ≤ 0))
     then
      intervals
     else
      (intervals ++ [cts_1])))

/-- Extracted from `_median_exact` (line 143). -/
def _median_exact (intervals : List Int) :
    Rat :=
  let ordered := (_sortInt intervals)
  let n := (Int.ofNat (List.length ordered))
  (if (decide ((Int.fmod n 2) = 1))
   then
    (mkRat (_nthInt ordered (Int.fdiv n 2)) 1)
   else
    let a := (_nthInt ordered ((Int.fdiv n 2) - 1))
    let b := (_nthInt ordered (Int.fdiv n 2))
    (mkRat (a + b) 2))

/-- Extracted from `cycles_for_progress_exact` (line 158). -/
def cycles_for_progress_exact (rows_newest_first : List CycleRow) (warmup_min_samples : Int) :
    Option Rat :=
  (if (decide ((Int.ofNat (List.length rows_newest_first)) = 0))
   then
    none
   else
    let chrono := (List.reverse rows_newest_first)
    let state : ((List Int) × (Option Int) × (Option Int)) := ([], none, none)
    let state := List.foldl
      (fun state cycle =>
        let state := (_strict_step state cycle)
        state)
      state chrono
    let intervals := (state.1)
    let intervals := List.foldl
      (fun intervals cycle =>
        let intervals := (_satisfy_step intervals cycle)
        intervals)
      intervals chrono
    (if (decide ((Int.ofNat (List.length intervals)) < warmup_min_samples))
     then
      none
     else
      (some (_median_exact intervals))))

end Extracted.CyclesForProgress
