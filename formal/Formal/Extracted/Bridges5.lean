import Formal.CyclesForProgress
import Formal.Scalarizer
import Formal.Extracted.CyclesForProgress
import Formal.Extracted.ScalarCore

/-!
# Extracted ↔ hand-model bridge lemmas, part 5 (P3c: the exact-Fraction
learning cores)

HAND-WRITTEN (size split of Bridges.lean..Bridges4.lean; same namespace).
The P3c wave refactored the two float-typed Tier-3 learning cores to EXACT
`Fraction` arithmetic (`cycles_for_progress_exact` in
`cycles_for_progress_core.py`, `scalar_yield_exact` in `scalar_core.py`),
mechanically extracted them to `Formal/Extracted/{CyclesForProgress,
ScalarCore}.lean`, and this file proves them against the pre-existing hand
models `Formal.CyclesForProgress` / `Formal.Scalarizer`.

## THE FLOAT BOUNDARY (the new trusted seam — read this)

The bridges below live ENTIRELY on the exact rational cores: every proved
equality is between the extracted `Rat` definition and the hand `Rat` model.
The Python public wrappers `cycles_for_progress_pure` / `scalar_yield_pure`
convert their inputs to `Fraction` EXACTLY (a Python float IS a binary
rational; `Fraction(float)` is its exact expansion), run the proved exact
core, and round ONCE — `float(total)` — at the very end. That single
conversion is OUTSIDE everything proved here. It is the trusted seam, and it
is sampled, not proved:

  * the differential suites (`test_cycles_for_progress_diff.py`,
    `test_scalarizer_diff.py`) compare the exact cores to the Lean oracle
    EXACTLY (Fraction == Rat numerator/denominator, no tolerance), and
    separately assert the float wrappers equal `float(exact result)` on
    every generated input — the wrappers' correctness reduces to "Python's
    `float()` of a Fraction is the correctly-rounded double", a property of
    CPython, not of this code.
  * for `cycles_for_progress` the boundary is even tighter: an odd-count
    median is an integer (exact in float far below 2^53) and an even-count
    median `float(Fraction(a + b, 2))` is bit-identical to the historical
    `(a + b) / 2` float division (both are round-to-nearest of the same
    rational).

## MODEL-FIDELITY FINDING (P2c-class, fixed in this wave)

The hand `strictIntervalsAux` KEPT `prevProgress` through a `none`
`task_progress` row, while the Python loop overwrites `prev_progress` every
iteration — a `none` reading RESETS the strict-increase detector. The two
genuinely diverged on streams MIXING `none`/`some` readings (e.g.
chronological progress `0, none, 5, 7`: Python emits NO strict interval, the
old model emitted `[1]`). The differential generator only built all-`none`
or all-`some` streams, masking the class. Python is the spec: the hand model
was aligned (`Formal/CyclesForProgress.lean`, P3c note + kernel witness),
the generator now mixes readings, and the diff suite pins the reset
semantics. The strict fold bridge below is UNIVERSAL only because of that
fix.

## Bridge inventory

* `cycles_for_progress_bridge` — FULL: the extracted exact core equals the
  hand `cyclesForProgressPure` for EVERY row stream and every Nat warm-up
  bound (over the field-for-field `encCycleRow` embedding; warm-up at
  `Int.ofNat W` — the production-reachable domain, the only caller passes
  `WARMUP_MIN_SAMPLES = 10`). Built from universal component bridges:
  `cycles_sort_bridge` (emitted insertion sort = hand `insSortInt`),
  `cycles_nth_bridge`, `cycles_median_bridge` (exact median, the degenerate
  empty list included: BOTH sides answer 0), `cycles_strict_fold_bridge` /
  `cycles_satisfy_fold_bridge` (the two accumulator folds = the hand
  interval streams, snoc-vs-cons by append associativity), and
  `revList_eq_reverse`. `cycles_median_concat_extracted` transfers THE
  verdict-(b) contract (median of the concatenated dual-signal streams) to
  the extracted def; `cycles_warmup_blocks_extracted` transfers the warm-up
  gate.

* `scalar_yield_bridge` — FULL: the extracted `scalar_yield_exact` equals
  the hand `scalarYield` for EVERY rational input, over the `encSkillTerm`
  weight-selection embedding (the hand model takes pre-selected
  `(weight, xp)` terms; the extracted core performs the membership
  selection itself — `List.contains`, order-independent over the
  frozenset image) and with the hand `goldUnit` instantiated at
  `1 / gold_per_xp` (Rat division IS multiplication by the reciprocal:
  `Rat.div_def`). `scalar_yield_mono_gold_extracted` transfers gold
  monotonicity to the extracted def.

* `coins_spent_bridge` — FULL (definitional): the extracted
  `coins_spent_from_delta` IS the hand `coinsSpent`;
  `coins_spent_inverts_extracted` transfers the no-sign-error inversion.

No sorry/admit, no new axioms; Lean core only.
-/

namespace Extracted.Bridges

/-- Field-for-field embedding of the hand `CycleRow` into the extracted
structure. -/
def encCycleRow (c : Formal.CyclesForProgress.CycleRow) :
    Extracted.CyclesForProgress.CycleRow :=
  { cycle_index := c.cycleIndex,
    task_progress := c.taskProgress,
    cycles_to_satisfy := c.cyclesToSatisfy }

/-! ### Component bridges: sort / nth / median. -/

/-- Emitted sorted-insert = the hand model's nested `insSortInt.ins`. -/
theorem cycles_sort_insert_bridge (x : Int) :
    ∀ ys : List Int,
      Extracted.CyclesForProgress._sortIntInsert x ys
        = Formal.CyclesForProgress.insSortInt.ins x ys := by
  intro ys
  induction ys with
  | nil => rfl
  | cons y ys ih =>
    simp only [Extracted.CyclesForProgress._sortIntInsert,
               Formal.CyclesForProgress.insSortInt.ins]
    rw [ih]

/-- Emitted insertion sort = hand `insSortInt`, for every list. -/
theorem cycles_sort_bridge :
    ∀ xs : List Int,
      Extracted.CyclesForProgress._sortInt xs
        = Formal.CyclesForProgress.insSortInt xs := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [Extracted.CyclesForProgress._sortInt,
               Formal.CyclesForProgress.insSortInt]
    rw [ih, cycles_sort_insert_bridge]

/-- Emitted Nat-indexed element read = hand `nthInt` (same default 0). -/
theorem cycles_nth_bridge :
    ∀ (xs : List Int) (n : Nat),
      Extracted.CyclesForProgress._nthIntNat xs n
        = Formal.CyclesForProgress.nthInt xs n := by
  intro xs
  induction xs with
  | nil => intro n; rfl
  | cons x xs ih =>
    intro n
    cases n with
    | zero => rfl
    | succ n =>
      simp only [Extracted.CyclesForProgress._nthIntNat,
                 Formal.CyclesForProgress.nthInt]
      exact ih n

/-- `Int.fdiv` of a non-negative numerator by 2 is Nat division. -/
private theorem fdiv2_ofNat (L : Nat) :
    Int.fdiv (Int.ofNat L) 2 = Int.ofNat (L / 2) := by
  rw [Int.fdiv_eq_ediv]
  simp only [Int.ofNat_eq_natCast]
  omega

/-- `Int.fmod` of a non-negative numerator by 2 is Nat mod. -/
private theorem fmod2_ofNat (L : Nat) :
    Int.fmod (Int.ofNat L) 2 = Int.ofNat (L % 2) := by
  rw [Int.fmod_eq_emod]
  simp only [Int.ofNat_eq_natCast]
  omega

/-- Exact-median bridge: the extracted `_median_exact` equals the hand
`medianQ` on EVERY list (the empty list included: the extracted even-count
branch reads the total defaults `0 + 0` over 2 — exactly the hand's
explicit `0`). -/
theorem cycles_median_bridge (xs : List Int) :
    Extracted.CyclesForProgress._median_exact xs
      = Formal.CyclesForProgress.medianQ xs := by
  simp only [Extracted.CyclesForProgress._median_exact,
             Formal.CyclesForProgress.medianQ,
             cycles_sort_bridge, Extracted.CyclesForProgress._nthInt,
             cycles_nth_bridge]
  generalize Formal.CyclesForProgress.insSortInt xs = s
  cases s with
  | nil => decide
  | cons h t =>
    rw [fmod2_ofNat, fdiv2_ofNat]
    simp only [decide_eq_true_eq]
    rw [if_neg (by simp : ¬ (h :: t).length = 0)]
    have htn : (Int.ofNat ((h :: t).length / 2)).toNat = (h :: t).length / 2 := by
      simp only [Int.ofNat_eq_natCast]; omega
    by_cases hodd : (h :: t).length % 2 = 1
    · rw [if_pos hodd,
          if_pos (by rw [hodd]; rfl : Int.ofNat ((h :: t).length % 2) = (1 : Int)),
          htn, Rat.mkRat_one]
    · rw [if_neg hodd,
          if_neg (by simp only [Int.ofNat_eq_natCast]; omega
                  : ¬ Int.ofNat ((h :: t).length % 2) = (1 : Int)),
          (by simp only [Int.ofNat_eq_natCast]; omega
            : (Int.ofNat ((h :: t).length / 2) - 1).toNat = (h :: t).length / 2 - 1),
          htn]

/-! ### Fold bridges: the two interval scans.

The extracted step functions never unify with the foldl lambda once
unfolded (the P2b stuck-matcher lesson), so each constructor-shaped input is
first reduced through a dedicated step lemma and only then folded into the
inductive hypothesis. -/

private theorem estep_pnone (acc : List Int) (l : Option Int) (ci : Int)
    (tp cts : Option Int) :
    Extracted.CyclesForProgress._strict_step (acc, l, none) ⟨ci, tp, cts⟩
      = (acc, l, tp) := rfl

private theorem estep_tpnone (acc : List Int) (l : Option Int) (pv ci : Int)
    (cts : Option Int) :
    Extracted.CyclesForProgress._strict_step (acc, l, some pv) ⟨ci, none, cts⟩
      = (acc, l, none) := rfl

private theorem estep_le (acc : List Int) (l : Option Int) (pv ci tp : Int)
    (cts : Option Int) (h : tp ≤ pv) :
    Extracted.CyclesForProgress._strict_step (acc, l, some pv) ⟨ci, some tp, cts⟩
      = (acc, l, some tp) := by
  simp [Extracted.CyclesForProgress._strict_step, h]

private theorem estep_gt_lnone (acc : List Int) (pv ci tp : Int)
    (cts : Option Int) (h : ¬ tp ≤ pv) :
    Extracted.CyclesForProgress._strict_step (acc, none, some pv) ⟨ci, some tp, cts⟩
      = (acc, some ci, some tp) := by
  simp [Extracted.CyclesForProgress._strict_step, h]

private theorem estep_gt_lsome (acc : List Int) (lp pv ci tp : Int)
    (cts : Option Int) (h : ¬ tp ≤ pv) :
    Extracted.CyclesForProgress._strict_step (acc, some lp, some pv) ⟨ci, some tp, cts⟩
      = (acc ++ [ci - lp], some ci, some tp) := by
  simp [Extracted.CyclesForProgress._strict_step, h]

/-- The strict-progress fold over encoded rows accumulates exactly the hand
`strictIntervalsAux` stream behind the running accumulator (snoc vs cons via
append associativity). Universal in the seed state — and TRUE only with the
P3c hand-model fix (a `none` reading threads `none`: the Python reset). -/
theorem cycles_strict_fold_bridge :
    ∀ (rows : List Formal.CyclesForProgress.CycleRow)
      (acc : List Int) (l p : Option Int),
      (List.foldl
        (fun state cycle => Extracted.CyclesForProgress._strict_step state cycle)
        (acc, l, p) (rows.map encCycleRow)).1
        = acc ++ Formal.CyclesForProgress.strictIntervalsAux p l rows := by
  intro rows
  induction rows with
  | nil =>
    intro acc l p
    simp [Formal.CyclesForProgress.strictIntervalsAux]
  | cons c cs ih =>
    intro acc l p
    simp only [List.map_cons, List.foldl_cons, encCycleRow]
    cases hp : p with
    | none =>
      rw [estep_pnone]
      cases htp : c.taskProgress with
      | none =>
        rw [ih acc l none]
        simp only [Formal.CyclesForProgress.strictIntervalsAux, htp]
      | some tp =>
        rw [ih acc l (some tp)]
        simp only [Formal.CyclesForProgress.strictIntervalsAux, htp]
    | some pv =>
      cases htp : c.taskProgress with
      | none =>
        rw [estep_tpnone, ih acc l none]
        simp only [Formal.CyclesForProgress.strictIntervalsAux, htp]
      | some tp =>
        by_cases hcmp : tp ≤ pv
        · rw [estep_le acc l pv c.cycleIndex tp c.cyclesToSatisfy hcmp,
              ih acc l (some tp)]
          simp only [Formal.CyclesForProgress.strictIntervalsAux, htp,
                     if_neg (by omega : ¬ tp > pv)]
        · cases hl : l with
          | none =>
            rw [estep_gt_lnone acc pv c.cycleIndex tp c.cyclesToSatisfy hcmp,
                ih acc (some c.cycleIndex) (some tp)]
            simp only [Formal.CyclesForProgress.strictIntervalsAux, htp,
                       if_pos (by omega : tp > pv)]
          | some lp =>
            rw [estep_gt_lsome acc lp pv c.cycleIndex tp c.cyclesToSatisfy hcmp,
                ih (acc ++ [c.cycleIndex - lp]) (some c.cycleIndex) (some tp)]
            simp only [Formal.CyclesForProgress.strictIntervalsAux, htp,
                       if_pos (by omega : tp > pv), List.append_assoc,
                       List.singleton_append]

private theorem esat_none (acc : List Int) (ci : Int) (tp : Option Int) :
    Extracted.CyclesForProgress._satisfy_step acc ⟨ci, tp, none⟩ = acc := rfl

private theorem esat_le (acc : List Int) (ci v : Int) (tp : Option Int)
    (h : v ≤ 0) :
    Extracted.CyclesForProgress._satisfy_step acc ⟨ci, tp, some v⟩ = acc := by
  simp [Extracted.CyclesForProgress._satisfy_step, h]

private theorem esat_pos (acc : List Int) (ci v : Int) (tp : Option Int)
    (h : ¬ v ≤ 0) :
    Extracted.CyclesForProgress._satisfy_step acc ⟨ci, tp, some v⟩
      = acc ++ [v] := by
  simp [Extracted.CyclesForProgress._satisfy_step, h]

/-- The satisfy fold over encoded rows accumulates exactly the hand
`satisfyIntervals` stream behind the running accumulator. -/
theorem cycles_satisfy_fold_bridge :
    ∀ (rows : List Formal.CyclesForProgress.CycleRow) (acc : List Int),
      List.foldl
        (fun intervals cycle =>
          Extracted.CyclesForProgress._satisfy_step intervals cycle)
        acc (rows.map encCycleRow)
        = acc ++ Formal.CyclesForProgress.satisfyIntervals rows := by
  intro rows
  induction rows with
  | nil =>
    intro acc
    simp [Formal.CyclesForProgress.satisfyIntervals]
  | cons c cs ih =>
    intro acc
    simp only [List.map_cons, List.foldl_cons, encCycleRow]
    cases hcs : c.cyclesToSatisfy with
    | none =>
      rw [esat_none, ih acc]
      simp only [Formal.CyclesForProgress.satisfyIntervals, hcs]
    | some v =>
      by_cases hv : v ≤ 0
      · rw [esat_le acc c.cycleIndex v c.taskProgress hv, ih acc]
        simp only [Formal.CyclesForProgress.satisfyIntervals, hcs,
                   if_neg (by omega : ¬ v > 0)]
      · rw [esat_pos acc c.cycleIndex v c.taskProgress hv, ih (acc ++ [v])]
        simp only [Formal.CyclesForProgress.satisfyIntervals, hcs,
                   if_pos (by omega : v > 0), List.append_assoc,
                   List.singleton_append]

/-- The hand `revList` is `List.reverse`. -/
theorem revList_eq_reverse {α : Type} :
    ∀ xs : List α, Formal.CyclesForProgress.revList xs = xs.reverse := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [Formal.CyclesForProgress.revList, List.reverse_cons]
    rw [ih]

/-! ### The full cycles_for_progress bridge. -/

/-- FULL BRIDGE: the extracted exact core equals the hand model for EVERY
newest-first row stream and every Nat warm-up bound. -/
theorem cycles_for_progress_bridge
    (rows : List Formal.CyclesForProgress.CycleRow) (W : Nat) :
    Extracted.CyclesForProgress.cycles_for_progress_exact
        (rows.map encCycleRow) (Int.ofNat W)
      = Formal.CyclesForProgress.cyclesForProgressPure rows W := by
  cases rows with
  | nil =>
    simp [Extracted.CyclesForProgress.cycles_for_progress_exact,
          Formal.CyclesForProgress.cyclesForProgressPure]
  | cons r rs =>
    simp only [Extracted.CyclesForProgress.cycles_for_progress_exact,
               Formal.CyclesForProgress.cyclesForProgressPure,
               decide_eq_true_eq]
    rw [if_neg (by simp only [List.length_map, List.length_cons,
                              Int.ofNat_eq_natCast]
                   omega
        : ¬ Int.ofNat (((r :: rs).map encCycleRow)).length = 0)]
    have hrev : ((r :: rs).map encCycleRow).reverse
        = (Formal.CyclesForProgress.revList (r :: rs)).map encCycleRow := by
      rw [revList_eq_reverse, List.map_reverse]
    rw [hrev,
        cycles_strict_fold_bridge (Formal.CyclesForProgress.revList (r :: rs))
          [] none none,
        cycles_satisfy_fold_bridge (Formal.CyclesForProgress.revList (r :: rs))]
    simp only [List.nil_append, Formal.CyclesForProgress.allIntervals,
               Formal.CyclesForProgress.strictIntervals, Int.ofNat_eq_natCast]
    by_cases hW : (Formal.CyclesForProgress.strictIntervalsAux none none
          (Formal.CyclesForProgress.revList (r :: rs))
        ++ Formal.CyclesForProgress.satisfyIntervals
          (Formal.CyclesForProgress.revList (r :: rs))).length < W
    · rw [if_pos ((Int.ofNat_lt).mpr hW), if_pos hW]
    · rw [if_neg (fun hc => hW ((Int.ofNat_lt).mp hc)),
          if_neg hW, cycles_median_bridge]

/-- TRANSFER of the verdict-(b) contract to the extracted def: above warm-up
the extracted exact core returns the median of the strict-increase intervals
concatenated with the satisfy intervals — the production dual-signal
semantics. -/
theorem cycles_median_concat_extracted
    (rows : List Formal.CyclesForProgress.CycleRow) (W : Nat)
    (hne : rows ≠ [])
    (hW : ¬ (Formal.CyclesForProgress.allIntervals
        (Formal.CyclesForProgress.revList rows)).length < W) :
    Extracted.CyclesForProgress.cycles_for_progress_exact
        (rows.map encCycleRow) (Int.ofNat W)
      = some (Formal.CyclesForProgress.medianQ
          (Formal.CyclesForProgress.strictIntervals
            (Formal.CyclesForProgress.revList rows)
           ++ Formal.CyclesForProgress.satisfyIntervals
            (Formal.CyclesForProgress.revList rows))) :=
  (cycles_for_progress_bridge rows W).trans
    (Formal.CyclesForProgress.cyclesForProgressPure_eq_median_concat rows W hne hW)

/-- TRANSFER of the warm-up gate to the extracted def. -/
theorem cycles_warmup_blocks_extracted
    (rows : List Formal.CyclesForProgress.CycleRow) (W : Nat)
    (h : (Formal.CyclesForProgress.allIntervals
        (Formal.CyclesForProgress.revList rows)).length < W) :
    Extracted.CyclesForProgress.cycles_for_progress_exact
        (rows.map encCycleRow) (Int.ofNat W) = none :=
  (cycles_for_progress_bridge rows W).trans
    (Formal.CyclesForProgress.warmup_blocks rows W h)

/-! ### Scalarizer bridges. -/

/-- Weight-selection embedding: the hand model consumes pre-selected
`(weight, xp)` terms; the extracted core selects the weight by membership.
-/
def encSkillTerm (active : List String) (relW baseW : Rat)
    (kv : String × Rat) : Formal.Scalarizer.SkillTerm :=
  ((if List.contains active kv.1 then relW else baseW), kv.2)

/-- The extracted skill fold equals the hand `skillSum` over the encoded
terms, behind any running accumulator. -/
private theorem scalar_skill_fold (active : List String) (relW baseW : Rat) :
    ∀ (terms : List (String × Rat)) (acc : Rat),
      List.foldl
        (fun s kv => s + kv.2 * (if List.contains active kv.1 then relW else baseW))
        acc terms
        = acc + Formal.Scalarizer.skillSum
            (terms.map (encSkillTerm active relW baseW)) := by
  intro terms
  induction terms with
  | nil =>
    intro acc
    simp [Formal.Scalarizer.skillSum, Rat.add_zero]
  | cons kv rest ih =>
    intro acc
    simp only [List.map_cons, List.foldl_cons, encSkillTerm,
               Formal.Scalarizer.skillSum]
    rw [ih]
    have hcomm : kv.2 * (if List.contains active kv.1 then relW else baseW)
        = (if List.contains active kv.1 then relW else baseW) * kv.2 :=
      Rat.mul_comm _ _
    rw [hcomm, Rat.add_assoc]

/-- FULL BRIDGE: the extracted `scalar_yield_exact` equals the hand
`scalarYield` for EVERY rational input — level cast into `Rat`, skill terms
through the membership encoding, the hand `goldUnit` at `1 / gold_per_xp`.
-/
theorem scalar_yield_bridge (charXp : Rat) (level : Int)
    (skillXp : List (String × Rat)) (active : List String)
    (gold tasksCoins coinValue baseW relW goldPerXp charScale : Rat) :
    Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
        gold tasksCoins coinValue baseW relW goldPerXp charScale
      = Formal.Scalarizer.scalarYield charXp (level : Rat)
          (skillXp.map (encSkillTerm active relW baseW))
          gold tasksCoins coinValue charScale (1 / goldPerXp) := by
  simp only [Extracted.ScalarCore.scalar_yield_exact,
             Formal.Scalarizer.scalarYield]
  rw [scalar_skill_fold]
  have hlevel : mkRat (level + 1) 1 = (level : Rat) + 1 := by
    rw [Rat.mkRat_one, Rat.intCast_add, Rat.intCast_one]
  have hzero : mkRat 0 1 = (0 : Rat) := by decide
  have hgold : gold / goldPerXp = gold * (1 / goldPerXp) := by
    simp [Rat.div_def]
  have hcoin : tasksCoins * coinValue / goldPerXp
      = tasksCoins * coinValue * (1 / goldPerXp) := by
    simp [Rat.div_def]
  rw [hlevel, hzero, hgold, hcoin, Rat.zero_add]

/-- TRANSFER of gold monotonicity to the extracted def: with a non-negative
gold unit (production: `1/100`), more gold never lowers the extracted
scalar. -/
theorem scalar_yield_mono_gold_extracted (charXp : Rat) (level : Int)
    (skillXp : List (String × Rat)) (active : List String)
    (gold gold' tasksCoins coinValue baseW relW goldPerXp charScale : Rat)
    (hunit : 0 ≤ 1 / goldPerXp) (h : gold ≤ gold') :
    Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
        gold tasksCoins coinValue baseW relW goldPerXp charScale
      ≤ Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
          gold' tasksCoins coinValue baseW relW goldPerXp charScale := by
  rw [scalar_yield_bridge, scalar_yield_bridge]
  exact Formal.Scalarizer.scalarYield_mono_gold charXp (level : Rat)
    (skillXp.map (encSkillTerm active relW baseW))
    gold gold' tasksCoins coinValue charScale (1 / goldPerXp) hunit h

/-- FULL BRIDGE (definitional): the extracted `coins_spent_from_delta` IS
the hand `coinsSpent`. -/
theorem coins_spent_bridge (received delta : Int) :
    Extracted.ScalarCore.coins_spent_from_delta received delta
      = Formal.Scalarizer.coinsSpent received delta := rfl

/-- TRANSFER of the no-sign-error inversion to the extracted def. -/
theorem coins_spent_inverts_extracted (received delta : Int) :
    received - Extracted.ScalarCore.coins_spent_from_delta received delta
      = delta := by
  rw [coins_spent_bridge]
  exact Formal.Scalarizer.coinsSpent_inverts received delta

end Extracted.Bridges
