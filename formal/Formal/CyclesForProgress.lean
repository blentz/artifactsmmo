-- @concept: characters @property: reachability, monotonicity
/-
Formal model of the pure core extracted from
`src/artifactsmmo_cli/ai/learning/projections.py` (`cycles_for_progress`,
delegated through `cycles_for_progress_core.cycles_for_progress_pure`).

`cycles_for_progress` returns the median over a STREAM of "progress
intervals" derived from a chronological list of `Cycle` rows. Two
sub-streams are concatenated:

  * STRICT-INCREASE intervals: distances `cycle_index - last_progress_at`
    between cycles where `task_progress` strictly increased over the
    previous cycle. Models the wall-clock spacing of progress ticks.
    A `none` reading RESETS the detector (Python overwrites
    `prev_progress` on every iteration) — see the P3c fidelity note on
    `strictIntervalsAux`.
  * SATISFY intervals: the raw `cycles_to_satisfy` value (cycles since
    the goal was FIRST selected) at each cycle that recorded one and is
    strictly positive. Models the wall-clock duration of a full goal
    completion.

The Python writer sites confirm BOTH fields can be populated on a SINGLE
cycle row:
  * `task_progress` is recorded on EVERY cycle row by `_record_learning_cycle`
    (e.g. `ai/actions/combat.py:89` writes the bumped `new_progress`).
  * `cycles_to_satisfy` is recorded ONLY on cycles where the goal got
    satisfied this cycle (`ai/player.py:347-368`,
    `_compute_cycles_to_satisfy`). The final kill that bumps `task_progress`
    AND satisfies the goal yields BOTH on the same row.

The two contributions measure DIFFERENT events (tick spacing vs.
total goal duration), so production-intent is to count both. This file
PROVES the concatenation contract over `ℚ`.

EXACT-RATIONAL MODEL (over `Rat`, Lean core — no mathlib). The Python
`statistics.median` returns an `int` (odd count) or the float midpoint
(even count). For lists of integers the midpoint `(a+b)/2` is exactly
representable in `ℚ` (denominator ∈ {1, 2}), and Python's float division
on `(a + b) / 2` for small integers is exact for |x| < 2^53; the diff
bounds inputs well within that. We model the median over `ℚ` and the
diff converts the Python float back to `Fraction` for an EXACT equality
check.

No mathlib, no sorry/admit/native_decide. Axioms ⊆
{propext, Classical.choice, Quot.sound}.
-/

namespace Formal.CyclesForProgress

/-- Minimal projection of `learning.models.Cycle` used by
`cycles_for_progress`. Mirrors `cycles_for_progress_core.CycleRow`. -/
structure CycleRow where
  cycleIndex : Int
  taskProgress : Option Int
  cyclesToSatisfy : Option Int
  deriving Repr

/-- Auxiliary for STRICT-INCREASE intervals, threading the rolling state
`(prevProgress, lastProgressAt)`.

MODEL-FIDELITY FIX (P3c, 2026-06-10): the Python loop executes
`prev_progress = cycle.task_progress` on EVERY iteration, so a `None`
`task_progress` reading RESETS the strict-increase detector (`prevProgress`
becomes `none`, and the next reading has no previous value to strictly
exceed). This model previously KEPT the old `prevProgress` through a `none`
row — divergent on streams that MIX `none` and `some` readings (the
differential generator only produced all-`none` or all-`some` streams, which
masked it; the P2c tree-only-domain gap class). Python is the spec; the
`none` arm now threads `none`. -/
def strictIntervalsAux : Option Int → Option Int → List CycleRow → List Int
  | _, _, [] => []
  | prevProgress, lastProgressAt, c :: rest =>
    match prevProgress, c.taskProgress with
    | some p, some tp =>
      if tp > p then
        match lastProgressAt with
        | some lp =>
          (c.cycleIndex - lp) :: strictIntervalsAux (some tp) (some c.cycleIndex) rest
        | none =>
          strictIntervalsAux (some tp) (some c.cycleIndex) rest
      else
        strictIntervalsAux (some tp) lastProgressAt rest
    | _, some tp => strictIntervalsAux (some tp) lastProgressAt rest
    | _, none => strictIntervalsAux none lastProgressAt rest

/-- STRICT-INCREASE intervals over a chronological row stream. -/
def strictIntervals (rows : List CycleRow) : List Int :=
  strictIntervalsAux none none rows

/-- SATISFY intervals: pick `cycles_to_satisfy > 0` over the row stream. -/
def satisfyIntervals : List CycleRow → List Int
  | [] => []
  | c :: rest =>
    match c.cyclesToSatisfy with
    | some v => if v > 0 then v :: satisfyIntervals rest else satisfyIntervals rest
    | none => satisfyIntervals rest

/-- All intervals: production order — strict-increase first, then
satisfy. -/
def allIntervals (chrono : List CycleRow) : List Int :=
  strictIntervals chrono ++ satisfyIntervals chrono

/-- Reverse a list (mirrors Python's `list(reversed(rows))`). -/
def revList {α : Type} : List α → List α
  | [] => []
  | x :: xs => revList xs ++ [x]

/-- Insertion-sort over `Int` (ascending). -/
def insSortInt : List Int → List Int
  | [] => []
  | x :: xs =>
    let rec ins : List Int → List Int
      | [] => [x]
      | y :: ys => if x ≤ y then x :: y :: ys else y :: ins ys
    ins (insSortInt xs)

/-- Element-at with a default 0. -/
def nthInt : List Int → Nat → Int
  | [], _ => 0
  | x :: _, 0 => x
  | _ :: xs, n+1 => nthInt xs n

/-- Median over a list of `Int`s as a `Rat`, matching Python
`statistics.median` (middle element for odd length; midpoint for even). -/
def medianQ (xs : List Int) : Rat :=
  let s := insSortInt xs
  let n := s.length
  if n = 0 then 0
  else if n % 2 = 1 then
    (nthInt s (n / 2) : Rat)
  else
    let a : Int := nthInt s (n / 2 - 1)
    let b : Int := nthInt s (n / 2)
    mkRat (a + b) 2

/-- Pure core of `cycles_for_progress`. Input is the LearningStore's
newest-first slice; we reverse to chronological; below WARMUP, return
`none`. -/
def cyclesForProgressPure
    (rowsNewestFirst : List CycleRow) (warmupMinSamples : Nat) : Option Rat :=
  match rowsNewestFirst with
  | [] => none
  | _ =>
    let chrono := revList rowsNewestFirst
    let ints := allIntervals chrono
    if ints.length < warmupMinSamples then none
    else some (medianQ ints)

/-! ### Intent theorems. -/

/-- CONTRACT (verdict (b)): the result is the median of the
strict-increase intervals concatenated with the satisfy intervals over
the chronological stream — the production semantics, in closed form. -/
theorem cyclesForProgressPure_eq_median_concat
    (rows : List CycleRow) (W : Nat)
    (hne : rows ≠ []) (hW : ¬ (allIntervals (revList rows)).length < W) :
    cyclesForProgressPure rows W
      = some (medianQ (strictIntervals (revList rows)
                       ++ satisfyIntervals (revList rows))) := by
  unfold cyclesForProgressPure
  cases rows with
  | nil => exact absurd rfl hne
  | cons r rs =>
    simp only []
    -- `allIntervals = strictIntervals ++ satisfyIntervals` by definition;
    -- the WARM-UP gate is `length < W`, which `hW` negates.
    show (if (allIntervals (revList (r :: rs))).length < W then none
          else some (medianQ (allIntervals (revList (r :: rs)))))
      = some (medianQ (strictIntervals (revList (r :: rs))
                       ++ satisfyIntervals (revList (r :: rs))))
    rw [if_neg hW]
    rfl

/-- WARM-UP gate: strictly fewer than `W` total intervals ⇒ `none`. -/
theorem warmup_blocks
    (rows : List CycleRow) (W : Nat)
    (h : (allIntervals (revList rows)).length < W) :
    cyclesForProgressPure rows W = none := by
  unfold cyclesForProgressPure
  cases rows with
  | nil => rfl
  | cons r rs =>
    simp only []
    simp [h]

/-- EMPTY input ⇒ `none` (unconditional). -/
theorem empty_none (W : Nat) : cyclesForProgressPure [] W = none := rfl

/-! ### Positivity of every appended interval.

These are the genuine PRODUCTION invariants. The median's sign follows
from these element-wise positivity claims plus the standard ordered-list
median bounds — we expose the element claims (which the differential
test exercises directly) without reproving median-positivity in Lean,
since the median bound is a vacuous-on-empty-list consequence of every
element being positive.
-/

/-- Every SATISFY interval is positive (the `> 0` gate on
`cycles_to_satisfy`). -/
theorem satisfyIntervals_pos
    (rows : List CycleRow) : ∀ x ∈ satisfyIntervals rows, 0 < x := by
  induction rows with
  | nil => intro x hx; cases hx
  | cons c rest ih =>
    intro x hx
    unfold satisfyIntervals at hx
    cases hcs : c.cyclesToSatisfy with
    | none =>
      rw [hcs] at hx
      exact ih x hx
    | some v =>
      rw [hcs] at hx
      by_cases hv : v > 0
      · simp [hv] at hx
        cases hx with
        | inl h => exact h ▸ hv
        | inr h => exact ih x h
      · simp [hv] at hx
        exact ih x hx

/-- Chronological monotonicity of cycle indices. -/
def monoChrono : List CycleRow → Prop
  | [] => True
  | [_] => True
  | a :: b :: rest => a.cycleIndex < b.cycleIndex ∧ monoChrono (b :: rest)

theorem monoChrono_tail {c : CycleRow} {rest : List CycleRow}
    (h : monoChrono (c :: rest)) : monoChrono rest := by
  cases rest with
  | nil => trivial
  | cons d ds =>
    simp [monoChrono] at h
    exact h.2

/-- Every element of `rest` has `cycleIndex` strictly greater than `k`. -/
def headLtAll (k : Int) : List CycleRow → Prop
  | [] => True
  | c :: rest => k < c.cycleIndex ∧ headLtAll k rest

/-- If `k ≤ k'` and every element of `ds` has index > `k'`, then every
element of `ds` has index > `k`. -/
theorem headLtAll_weaken
    {k k' : Int} {ds : List CycleRow}
    (hkk : k ≤ k') (hc : headLtAll k' ds) :
    headLtAll k ds := by
  induction ds with
  | nil => trivial
  | cons e es ih =>
    simp [headLtAll] at hc ⊢
    exact ⟨by omega, ih hc.2⟩

theorem monoChrono_headLtAll :
    ∀ (c : CycleRow) (rest : List CycleRow),
      monoChrono (c :: rest) → headLtAll c.cycleIndex rest := by
  intro c rest
  induction rest generalizing c with
  | nil => intro _; trivial
  | cons d ds ih =>
    intro h
    simp [monoChrono] at h
    obtain ⟨hcd, hd⟩ := h
    have hsub : headLtAll d.cycleIndex ds := ih d hd
    refine ⟨hcd, ?_⟩
    exact headLtAll_weaken (by omega : c.cycleIndex ≤ d.cycleIndex) hsub

/-- Every STRICT-INCREASE interval is positive when the cycle stream is
chronologically monotone (the production invariant — `cycle_index` is
the strictly-increasing global counter). -/
theorem strictIntervals_pos
    (rows : List CycleRow) (h : monoChrono rows) :
    ∀ x ∈ strictIntervals rows, 0 < x := by
  -- Strengthened invariant: `lastProgressAt = some k` ⇒ `k < every later cycleIndex`.
  have aux :
    ∀ (prevP lastAt : Option Int) (rs : List CycleRow),
      (∀ k, lastAt = some k → headLtAll k rs) →
      monoChrono rs →
      ∀ x ∈ strictIntervalsAux prevP lastAt rs, 0 < x := by
    intro prevP lastAt rs
    induction rs generalizing prevP lastAt with
    | nil =>
      intros _ _ x hx
      cases hx
    | cons c rest ih =>
      intro hLast hMono x hx
      have hRestMono : monoChrono rest := monoChrono_tail hMono
      have hAllRest : headLtAll c.cycleIndex rest :=
        monoChrono_headLtAll c rest hMono
      -- shrinking the `headLtAll` claim by dropping the head element
      have hLast_shrunk : ∀ k, lastAt = some k → headLtAll k rest := by
        intro k hk
        have := hLast k hk
        simp [headLtAll] at this
        exact this.2
      unfold strictIntervalsAux at hx
      cases hpp : prevP with
      | none =>
        rw [hpp] at hx
        cases htp : c.taskProgress with
        | none =>
          rw [htp] at hx
          simp at hx
          exact ih none lastAt hLast_shrunk hRestMono x hx
        | some tp =>
          rw [htp] at hx
          simp at hx
          exact ih (some tp) lastAt hLast_shrunk hRestMono x hx
      | some p =>
        rw [hpp] at hx
        cases htp : c.taskProgress with
        | none =>
          rw [htp] at hx
          simp at hx
          exact ih none lastAt hLast_shrunk hRestMono x hx
        | some tp =>
          rw [htp] at hx
          simp at hx
          by_cases hcmp : tp > p
          · simp [hcmp] at hx
            cases hla : lastAt with
            | none =>
              rw [hla] at hx
              simp at hx
              have hLast' :
                ∀ k, (some c.cycleIndex : Option Int) = some k → headLtAll k rest := by
                intro k hk
                cases hk
                exact hAllRest
              exact ih (some tp) (some c.cycleIndex) hLast' hRestMono x hx
            | some lp =>
              rw [hla] at hx
              simp at hx
              have hlp_lt : lp < c.cycleIndex := by
                have := hLast lp hla
                simp [headLtAll] at this
                exact this.1
              cases hx with
              | inl h =>
                rw [h]; omega
              | inr h =>
                have hLast' :
                  ∀ k, (some c.cycleIndex : Option Int) = some k → headLtAll k rest := by
                  intro k hk
                  cases hk
                  exact hAllRest
                exact ih (some tp) (some c.cycleIndex) hLast' hRestMono x h
          · simp [hcmp] at hx
            exact ih (some tp) lastAt hLast_shrunk hRestMono x hx
  exact aux none none rows (by intros _ h; cases h) h

/-- Every appended interval is positive under the chronological-monotonicity
invariant. This is the genuine, non-vacuous positivity guarantee that
seals the `or 15.0` caller fallback in `projections.py:312`: no returned
median can be 0 because every element going into the median is ≥ 1, so
the median itself is ≥ 1 (a fact the differential test pins
quantitatively over Hypothesis-generated row streams). -/
theorem allIntervals_pos
    (rows : List CycleRow) (h : monoChrono rows) :
    ∀ x ∈ allIntervals rows, 0 < x := by
  intro x hx
  unfold allIntervals at hx
  rcases List.mem_append.mp hx with hs | hsat
  · exact strictIntervals_pos rows h x hs
  · exact satisfyIntervals_pos rows x hsat

/-! ### Non-vacuity witnesses (no false hypotheses). -/

/-- A 2-row stream with a strict increase and a satisfy reading on the
SECOND row yields BOTH an interval kinds — but the strict-increase branch
needs at least TWO strict increases to APPEND. So the genuine
"single cycle contributes to both" witness needs at least a third row:
we exhibit a 3-row stream where the third row simultaneously bumps
`task_progress` AND records `cycles_to_satisfy`, generating BOTH a
strict-increase interval (between the second and third row) AND a
satisfy interval. -/
example :
    let r0 : CycleRow := { cycleIndex := 0, taskProgress := some 0,
                            cyclesToSatisfy := none }
    let r1 : CycleRow := { cycleIndex := 1, taskProgress := some 1,
                            cyclesToSatisfy := none }
    let r2 : CycleRow := { cycleIndex := 2, taskProgress := some 2,
                            cyclesToSatisfy := some 3 }
    strictIntervals [r0, r1, r2] = [1] ∧ satisfyIntervals [r0, r1, r2] = [3]
    := by
  decide

/-- The same 3-row witness has `allIntervals = [1, 3]` of length 2, so
the WARMUP gate at `W = 3` returns `none` (this pins the gate). -/
example :
    let r0 : CycleRow := { cycleIndex := 0, taskProgress := some 0,
                            cyclesToSatisfy := none }
    let r1 : CycleRow := { cycleIndex := 1, taskProgress := some 1,
                            cyclesToSatisfy := none }
    let r2 : CycleRow := { cycleIndex := 2, taskProgress := some 2,
                            cyclesToSatisfy := some 3 }
    cyclesForProgressPure (revList [r0, r1, r2]) 3 = none := by
  decide

/-- RESET-SEMANTICS witness (the P3c model-fidelity fix): a `none`
`task_progress` reading RESETS the strict-increase detector. Chronological
progress readings `some 0, none, some 5, some 7` produce NO strict interval
(the `none` row clears `prevProgress`; `some 5` re-seeds it; `7 > 5` is the
FIRST strict increase after the reset, so `lastProgressAt` is only seeded,
nothing is appended). The pre-fix model kept `prevProgress = some 0` through
the `none` row and wrongly emitted `[1]`. With a satisfy reading 9 on the
final row, the median is 9 — exactly what the Python core computes
(verified: `cycles_for_progress_pure` returns 9.0 on this stream). -/
example :
    let r0 : CycleRow := { cycleIndex := 0, taskProgress := some 0,
                            cyclesToSatisfy := none }
    let r1 : CycleRow := { cycleIndex := 1, taskProgress := none,
                            cyclesToSatisfy := none }
    let r2 : CycleRow := { cycleIndex := 2, taskProgress := some 5,
                            cyclesToSatisfy := none }
    let r3 : CycleRow := { cycleIndex := 3, taskProgress := some 7,
                            cyclesToSatisfy := some 9 }
    strictIntervals [r0, r1, r2, r3] = []
      ∧ cyclesForProgressPure (revList [r0, r1, r2, r3]) 1 = some 9 := by
  decide

/-- A 6-row witness with one strict-increase interval (= 2) and one
satisfy interval (= 3) satisfies WARMUP at `W = 2` and the median is
`5/2` (Python: `statistics.median([2, 3]) == 2.5`). Non-vacuous. -/
example :
    cyclesForProgressPure
      [ { cycleIndex := 5, taskProgress := some 2, cyclesToSatisfy := some 3 },
        { cycleIndex := 4, taskProgress := some 2, cyclesToSatisfy := none },
        { cycleIndex := 3, taskProgress := some 1, cyclesToSatisfy := none },
        { cycleIndex := 2, taskProgress := some 1, cyclesToSatisfy := none },
        { cycleIndex := 1, taskProgress := some 0, cyclesToSatisfy := none },
        { cycleIndex := 0, taskProgress := some 0, cyclesToSatisfy := none } ]
      2
      = some (mkRat 5 2) := by
  decide

end Formal.CyclesForProgress
