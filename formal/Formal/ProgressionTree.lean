-- @concept: progression @property: safety, totality, dominance
/-
Formal model of the progression-tree pure cores extracted from
`src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
(spec docs/superpowers/specs/2026-07-06-progression-tree-design.md).
The Python cores are bound to these semantics by the
PROGRESSION_TREE_MUTATIONS group (unit-killed, formal/diff/mutate.py).

The tree replaced the flat scalar root ranking. WAVE 3a replaced the tree's own
scored/branching layer with the five-node resolution walk in
`ai/decisions/root.py`, and WAVE 3b deleted what that left with no Python
mirror: `branchPick` (the boolean gear|xp pivot and its 4-row truth table),
`inductive Branch`, and `gearTargetPick`/`focusAgingPick` (the gear argmax and
its aging composition). What is modelled here is what the walk actually runs:

  * trunk    — L10..L50 milestones: `milestonePure level = min 50 ((level/10+1)*10)`
    (exact Nat division, no floats). Proven: the milestone strictly exceeds the
    level below the cap, never exceeds the cap, is band-aligned (`% 10 = 0`),
    and strictly advances when crossed (the trunk-descent measure).
  * potion weights — the closed per-effect-family tuning table
    (health 1, boost/resist/antipoison 1/4, unknown 0). Proven: health is
    maximal, unknown is the floor (an unmodeled consumable never outranks).
  * focus aging — `falloff` is the convex (flat → quadratic decay → floor)
    selection-weight multiplier and `dhondtStepKey` is one seat of the d'Hondt
    / highest-averages apportionment; `WhichSlotIsFurthestBehind._aged_head`
    composes exactly those two (Python `falloff` + `dhondt_step`). Proven:
    `falloff` is flat below the window, pinned at the positive floor above it,
    and antitone throughout; and the step always selects a quotient-maximal key
    (`selectMax_quot_max` / `dhondtStepKey_quot_max`, the highest-averages
    optimality underlying no-starvation).
  * `interleaveDue` — the multi-seat FOLD of that step, kept as the object the
    bounded no-starvation theorem is stated over. Its Python mirror
    `interleave_due` is gone (the player accumulates seats incrementally and
    calls `dhondt_step` once per cycle, which reproduces the fold seat-for-seat
    — see `GamePlayer._interleave_seats`), so this definition is a MODEL, not a
    mirror.

Non-vacuity anchors: every hypothesis is satisfiable — `milestone_gt_level`
and `milestone_advances` are witnessed at `level = 0` (see the concrete
`example`s below); the truth-table theorems are hypothesis-free `decide`s.

`interleaveDue_reaches` (bounded no-starvation reachability) is PROVEN, with no
`sorry`, as `Formal.ProgressionTree.interleaveDue_reaches` — declared in that
namespace but living in the file `Formal/Liveness/InterleaveNoStarvation.lean`,
because the summation argument needs mathlib and mathlib is quarantined out of
this safety core. It was DEFERRED when this header was written; the note above
the `interleaveDue` definition below records the original obstructions and how
the liveness tier discharged them. THIS PROOF IS LIVE OVER CODE THE BOT RUNS —
`falloff` and `dhondt_step` are called every aged cycle at
`ai/decisions/root.py:348-365` — so neither it nor its file is orphaned.

Lean core only — no mathlib (mathlib is quarantined to Formal/Liveness/).
`omega` handles the min/div-by-10 milestone arithmetic; `decide` closes the
finite truth tables and concrete `Rat` comparisons; the fold proofs mirror
`Formal/BankSelection.lean`'s `bestWeaponFold` membership shapes.
-/

namespace Formal.ProgressionTree

/-! ### Trunk: level milestones -/

def trunkCap : Nat := 50
def band : Nat := 10

/-- Next trunk milestone: `min 50 ((level / 10 + 1) * 10)` (exact Nat
division). Mirrors Python `milestone_pure`. -/
def milestonePure (level : Nat) : Nat :=
  min trunkCap ((level / band + 1) * band)

/-- The milestone strictly exceeds the level below the cap. -/
theorem milestone_gt_level (level : Nat) (h : level < trunkCap) :
    level < milestonePure level := by
  simp only [milestonePure, trunkCap, band] at h ⊢
  omega

/-- The milestone never exceeds the cap. -/
theorem milestone_le_cap (level : Nat) : milestonePure level ≤ trunkCap :=
  Nat.min_le_left _ _

/-- Milestones are band boundaries: divisible by 10. -/
theorem milestone_band_aligned (level : Nat) : milestonePure level % band = 0 := by
  simp only [milestonePure, trunkCap, band]
  omega

/-- Crossing a milestone strictly advances it (trunk descent): at the cap it
is a fixed point; below, reaching the milestone yields a strictly bigger
one. -/
theorem milestone_advances (level : Nat) (h : milestonePure level < trunkCap) :
    milestonePure level < milestonePure (milestonePure level) := by
  simp only [milestonePure, trunkCap, band] at h ⊢
  omega

/-- Concrete anchors (non-vacuity + spot semantics): L0→10, L12→20, L49→50,
and the L50 capstone is the fixed point. -/
example : milestonePure 0 = 10 := by decide
example : milestonePure 12 = 20 := by decide
example : milestonePure 49 = 50 := by decide
example : milestonePure 50 = 50 := by decide

/-! ### Potion-family weights -/

inductive PotionFamily
  | hpRestore
  | boost
  | resist
  | antipoison
  | unknown
deriving DecidableEq, Repr

/-- Per-effect-family consumable weights — the ONLY potion tuning surface in
the gear branch (user decision 2026-07-06: health maximized now, other
families dialed later). Unknown weighs 0: an unmodeled consumable must never
outrank modeled gear. Mirrors Python `potion_type_weight` incl. the
`.get(family, 0)` default. Literals via `mkRat` so `decide` reduction
terminates (same idiom as `Formal/ActionCostNonneg.lean`). -/
def potionWeight : PotionFamily → Rat
  | .hpRestore => 1
  | .boost => mkRat 1 4
  | .resist => mkRat 1 4
  | .antipoison => mkRat 1 4
  | .unknown => 0

/-- Health dominates every family (the user's tuning decision, pinned). -/
theorem potionWeight_health_maximal (f : PotionFamily) :
    potionWeight f ≤ potionWeight .hpRestore := by
  cases f <;> decide

/-- Unknown families never outrank anything: 0 is the floor. -/
theorem potionWeight_unknown_floor (f : PotionFamily) :
    potionWeight .unknown ≤ potionWeight f := by
  cases f <;> decide

/-! ### Focus aging: convex selection-weight falloff

Mirrors `falloff` in `progression_tree_core.py`. A root that has been the
committed focus for `focusLevel` iterations keeps FULL weight through the flat
farm window (`focusLevel ≤ focusFlat`), then decays convexly (quadratic
ease-in) to `focusFloor` across the next `focusSpan` iterations, and is held at
`focusFloor` (> 0) forever after — a stuck drop root is never fully abandoned.
Exact `Rat`; the constants are the only tuning surface. -/

def focusFlat : Nat := 10
def focusSpan : Nat := 100
/-- Calibrated (Task 11) against the real Robby trace ratio wolf_ears:iron_ring
= 18100:2000 (~9.05:1): at this floor the asymptotic split once fully decayed
is ~50/50 (18100/9 ≈ 2011 vs 2000). -/
def focusFloor : Rat := mkRat 1 9

/-- Normalised aging parameter `t := (focusLevel - focusFlat) / focusSpan`
(Python `Fraction(focus_level - FOCUS_FLAT, FOCUS_SPAN)`). Over the rationals
`Nat` truncated subtraction is exact on the region where it is evaluated
(`focusFlat < focusLevel`). -/
def falloffT (focusLevel : Nat) : Rat :=
  ((focusLevel - focusFlat : Nat) : Rat) / (focusSpan : Rat)

/-- Selection-weight multiplier: flat `1` through the farm window, convex decay
`1 - (1 - focusFloor) * t * t` across the span, then held at `focusFloor`.
Mirrors Python `falloff`. -/
def falloff (focusLevel : Nat) : Rat :=
  if focusLevel ≤ focusFlat then 1
  else if focusFlat + focusSpan ≤ focusLevel then focusFloor
  else 1 - (1 - focusFloor) * falloffT focusLevel * falloffT focusLevel

/-! Small `Rat` order helpers (core Lean, no mathlib). -/

/-- Division by a positive constant is monotone. -/
theorem ratDivMono {a b c : Rat} (h : a ≤ b) (hc : 0 < c) : a / c ≤ b / c := by
  rw [Rat.div_def, Rat.div_def]
  exact Rat.mul_le_mul_of_nonneg_right h (Rat.le_of_lt (Rat.inv_pos.mpr hc))

/-- A nonneg numerator over a positive denominator is nonneg. -/
theorem ratDivNonneg {a c : Rat} (ha : 0 ≤ a) (hc : 0 < c) : 0 ≤ a / c := by
  rw [Rat.div_def]
  exact Rat.mul_nonneg ha (Rat.le_of_lt (Rat.inv_pos.mpr hc))

theorem focusSpan_pos : (0 : Rat) < (focusSpan : Rat) := by
  have : (0 : Nat) < focusSpan := by decide
  exact_mod_cast this

theorem focusSpan_ne_zero : (focusSpan : Rat) ≠ 0 := by
  have hp := focusSpan_pos
  intro hz
  rw [hz] at hp
  exact absurd hp (by decide)

theorem focusSpan_div_self : (focusSpan : Rat) / (focusSpan : Rat) = 1 := by
  rw [Rat.div_def, Rat.mul_inv_cancel _ focusSpan_ne_zero]

/-- `t ≥ 0` everywhere. -/
theorem falloffT_nonneg (l : Nat) : 0 ≤ falloffT l := by
  unfold falloffT
  exact ratDivNonneg (by exact_mod_cast Nat.zero_le _) focusSpan_pos

/-- `t` is monotone in the focus level. -/
theorem falloffT_mono {a b : Nat} (hab : a ≤ b) : falloffT a ≤ falloffT b := by
  unfold falloffT
  refine ratDivMono ?_ focusSpan_pos
  exact_mod_cast Nat.sub_le_sub_right hab focusFlat

/-- Inside the decay span (`focusLevel < focusFlat + focusSpan`) we have
`t ≤ 1`. -/
theorem falloffT_le_one {l : Nat} (h : ¬ focusFlat + focusSpan ≤ l) :
    falloffT l ≤ 1 := by
  unfold falloffT
  have hnat : (l - focusFlat : Nat) ≤ focusSpan := by
    simp only [focusFlat, focusSpan] at h ⊢; omega
  have hcast : ((l - focusFlat : Nat) : Rat) ≤ (focusSpan : Rat) := by
    exact_mod_cast hnat
  calc ((l - focusFlat : Nat) : Rat) / (focusSpan : Rat)
      ≤ (focusSpan : Rat) / (focusSpan : Rat) := ratDivMono hcast focusSpan_pos
    _ = 1 := focusSpan_div_self

/-- `1 - focusFloor = 8/9 ≥ 0` (the decay coefficient is nonneg). -/
theorem oneSubFloor_nonneg : (0 : Rat) ≤ 1 - focusFloor := by
  have : focusFloor ≤ 1 := by decide
  grind

/-- The multiplier never exceeds `1`. -/
theorem falloff_le_one (l : Nat) : falloff l ≤ 1 := by
  unfold falloff
  split
  · exact Rat.le_refl
  · split
    · decide
    · have h0 : 0 ≤ falloffT l := falloffT_nonneg l
      have hq : 0 ≤ (1 - focusFloor) * falloffT l * falloffT l :=
        Rat.mul_nonneg (Rat.mul_nonneg oneSubFloor_nonneg h0) h0
      grind

/-- The multiplier never drops below `focusFloor` (a stuck root is never fully
abandoned). -/
theorem falloff_ge_floor (l : Nat) : focusFloor ≤ falloff l := by
  unfold falloff
  split
  · decide
  · split
    · exact Rat.le_refl
    · rename_i _ hspan
      have h0 : 0 ≤ falloffT l := falloffT_nonneg l
      have h1 : falloffT l ≤ 1 := falloffT_le_one hspan
      have htt : falloffT l * falloffT l ≤ 1 := by
        have hstep : falloffT l * falloffT l ≤ 1 * falloffT l :=
          Rat.mul_le_mul_of_nonneg_right h1 h0
        have : (1 : Rat) * falloffT l ≤ 1 := by
          have := Rat.one_mul (falloffT l); grind
        exact Rat.le_trans hstep this
      have hZ : (1 - focusFloor) * falloffT l * falloffT l ≤ 1 - focusFloor := by
        rw [Rat.mul_assoc]
        have := Rat.mul_le_mul_of_nonneg_left htt oneSubFloor_nonneg
        rw [Rat.mul_one] at this
        exact this
      grind

/-- FLAT window: below `focusFlat` the multiplier is exactly `1`. -/
theorem falloff_flat (l : Nat) (h : l ≤ focusFlat) : falloff l = 1 := by
  simp only [falloff, if_pos h]

/-- FLOOR: at or past `focusFlat + focusSpan` the multiplier is `focusFloor`. -/
theorem falloff_floor_after (l : Nat) (h : focusFlat + focusSpan ≤ l) :
    falloff l = focusFloor := by
  have h1 : ¬ (l ≤ focusFlat) := by simp only [focusFlat, focusSpan] at h ⊢; omega
  simp only [falloff, if_neg h1, if_pos h]

/-- The floor is strictly positive. -/
theorem falloff_floor_pos : (0 : Rat) < focusFloor := by decide

/-- ANTITONE: aging never increases the multiplier — a longer-focused root is
weighted no higher than a fresher one. -/
theorem falloff_antitone {a b : Nat} (h : a ≤ b) : falloff b ≤ falloff a := by
  by_cases haA : a ≤ focusFlat
  · rw [falloff_flat a haA]; exact falloff_le_one b
  · by_cases haC : focusFlat + focusSpan ≤ a
    · have hbC : focusFlat + focusSpan ≤ b := Nat.le_trans haC h
      rw [falloff_floor_after a haC, falloff_floor_after b hbC]
      exact Rat.le_refl
    · by_cases hbC : focusFlat + focusSpan ≤ b
      · rw [falloff_floor_after b hbC]; exact falloff_ge_floor a
      · have hbA : ¬ (b ≤ focusFlat) := fun hb => haA (Nat.le_trans h hb)
        simp only [falloff, if_neg haA, if_neg haC, if_neg hbA, if_neg hbC]
        -- goal: 1 - c*t_b*t_b ≤ 1 - c*t_a*t_a, where c = 1 - focusFloor
        have hta0 : 0 ≤ falloffT a := falloffT_nonneg a
        have htb0 : 0 ≤ falloffT b := falloffT_nonneg b
        have htab : falloffT a ≤ falloffT b := falloffT_mono h
        have hsq : falloffT a * falloffT a ≤ falloffT b * falloffT b := by
          have s1 : falloffT a * falloffT a ≤ falloffT b * falloffT a :=
            Rat.mul_le_mul_of_nonneg_right htab hta0
          have s2 : falloffT b * falloffT a ≤ falloffT b * falloffT b :=
            Rat.mul_le_mul_of_nonneg_left htab htb0
          exact Rat.le_trans s1 s2
        have hc : (0 : Rat) ≤ 1 - focusFloor := oneSubFloor_nonneg
        have hmul :
            (1 - focusFloor) * (falloffT a * falloffT a)
              ≤ (1 - focusFloor) * (falloffT b * falloffT b) :=
          Rat.mul_le_mul_of_nonneg_left hsq hc
        rw [Rat.mul_assoc, Rat.mul_assoc]
        grind

/-! ### d'Hondt / highest-averages interleave (no-starvation scheduler)

Modelled the Python `interleave_due`, which wave 3b deleted; `dhondtStep`
below is still an exact mirror of the live `dhondt_step`, and the player's seat
accumulator reproduces this fold seat-for-seat. Deterministic proportional
apportionment: hand out
`cycle + 1` seats one at a time, each to the key maximising the quotient
`w / (seats + 1)`, ties broken by `(quotient, weight, key)` — a canonical,
list-order-independent total order. -/

/-- Bump one key's seat count. -/
def bumpSeats (s : String → Nat) (k : String) : String → Nat :=
  fun x => if x = k then s x + 1 else s x

/-- d'Hondt quotient `w / (seats + 1)`. -/
def dhondtQuot (w : Rat) (seats : Nat) : Rat := w / ((seats : Rat) + 1)

/-- Strict selection order: `a` beats `b` when its `(quotient, weight, key)`
triple is lexicographically greater (Python `max` picks the largest). -/
def selBeats (s : String → Nat) (a b : String × Rat) : Bool :=
  let qa := dhondtQuot a.2 (s a.1)
  let qb := dhondtQuot b.2 (s b.1)
  if qa ≠ qb then decide (qb < qa)
  else if a.2 ≠ b.2 then decide (b.2 < a.2)
  else decide (b.1 < a.1)

/-- Argmax under `selBeats` (first-wins on exact ties). -/
def selectMax (weighted : List (String × Rat)) (s : String → Nat) :
    Option (String × Rat) :=
  weighted.foldl
    (fun best kw =>
      match best with
      | none => some kw
      | some b => if selBeats s kw b then some kw else some b)
    none

/-- One seat allocation: recompute the winner from the current seat counts and
bump it. -/
def dhondtStep (weighted : List (String × Rat))
    (st : Option String × (String → Nat)) : Option String × (String → Nat) :=
  match selectMax weighted st.2 with
  | none => st
  | some (k, _) => (some k, bumpSeats st.2 k)

/-- If `a` beats `b`, then `a`'s quotient is at least `b`'s (the tiebreak only
fires on equal quotients). -/
theorem selBeats_true_quot (s : String → Nat) (a b : String × Rat)
    (h : selBeats s a b = true) :
    dhondtQuot b.2 (s b.1) ≤ dhondtQuot a.2 (s a.1) := by
  by_cases hq : dhondtQuot a.2 (s a.1) = dhondtQuot b.2 (s b.1)
  · rw [hq]; exact Rat.le_refl
  · simp only [selBeats, if_pos hq] at h
    exact Rat.le_of_lt (of_decide_eq_true h)

/-- If `a` does NOT beat `b`, then `a`'s quotient is at most `b`'s. -/
theorem selBeats_false_quot (s : String → Nat) (a b : String × Rat)
    (h : selBeats s a b = false) :
    dhondtQuot a.2 (s a.1) ≤ dhondtQuot b.2 (s b.1) := by
  by_cases hq : dhondtQuot a.2 (s a.1) = dhondtQuot b.2 (s b.1)
  · rw [hq]; exact Rat.le_refl
  · simp only [selBeats, if_pos hq] at h
    exact Rat.not_lt.mp (of_decide_eq_false h)

/-- Fold invariant: the argmax accumulator's quotient dominates both the seed
and every folded element. -/
theorem selectMax_fold_max (l : List (String × Rat)) (s : String → Nat) :
    ∀ (acc : Option (String × Rat)) (r : String × Rat),
      l.foldl
        (fun best kw =>
          match best with
          | none => some kw
          | some b => if selBeats s kw b then some kw else some b)
        acc = some r →
      (∀ e, acc = some e → dhondtQuot e.2 (s e.1) ≤ dhondtQuot r.2 (s r.1)) ∧
      (∀ e ∈ l, dhondtQuot e.2 (s e.1) ≤ dhondtQuot r.2 (s r.1)) := by
  induction l with
  | nil =>
    intro acc r h
    simp only [List.foldl_nil] at h
    refine ⟨?_, ?_⟩
    · intro e he
      rw [h] at he
      obtain rfl := Option.some.inj he
      exact Rat.le_refl
    · intro e he; exact absurd he (List.not_mem_nil)
  | cons x t ih =>
    intro acc r h
    simp only [List.foldl_cons] at h
    obtain ⟨ihacc, ihmem⟩ := ih _ r h
    -- x's quotient ≤ r's quotient
    have hx : dhondtQuot x.2 (s x.1) ≤ dhondtQuot r.2 (s r.1) := by
      cases acc with
      | none => exact ihacc x rfl
      | some b =>
        by_cases hb : selBeats s x b = true
        · simp only [hb, if_true] at ihacc; exact ihacc x rfl
        · have hbf : selBeats s x b = false := by
            cases hbb : selBeats s x b with
            | true => exact absurd hbb hb
            | false => rfl
          have hxb : dhondtQuot x.2 (s x.1) ≤ dhondtQuot b.2 (s b.1) :=
            selBeats_false_quot s x b hbf
          simp only [hbf, Bool.false_eq_true, if_false] at ihacc
          exact Rat.le_trans hxb (ihacc b rfl)
    refine ⟨?_, ?_⟩
    · intro e he
      cases acc with
      | none => exact absurd he (by simp)
      | some b =>
        rw [← Option.some.inj he]
        by_cases hb : selBeats s x b = true
        · have hbx : dhondtQuot b.2 (s b.1) ≤ dhondtQuot x.2 (s x.1) :=
            selBeats_true_quot s x b hb
          exact Rat.le_trans hbx hx
        · have hbf : selBeats s x b = false := by
            cases hbb : selBeats s x b with
            | true => exact absurd hbb hb
            | false => rfl
          simp only [hbf, Bool.false_eq_true, if_false] at ihacc
          exact ihacc b rfl
    · intro e he
      rcases List.mem_cons.mp he with rfl | het
      · exact hx
      · exact ihmem e het

/-- HIGHEST-AVERAGES OPTIMALITY: the interleave's per-seat winner maximises the
d'Hondt quotient over all candidates — the defining correctness property of the
scheduler (and the foundation of its no-starvation behaviour: a key's quotient
`w / (seats + 1)` grows unboundedly relative to a saturating rival's). -/
theorem selectMax_quot_max (weighted : List (String × Rat)) (s : String → Nat)
    (r : String × Rat) (hr : selectMax weighted s = some r) :
    ∀ e ∈ weighted, dhondtQuot e.2 (s e.1) ≤ dhondtQuot r.2 (s r.1) :=
  (selectMax_fold_max weighted s none r hr).2

/-- The winning KEY of one d'Hondt seat given the seat counts already handed
out — the direct mirror of Python `dhondt_step(weighted, seats)`, which (unlike
the state-threading `dhondtStep` above) returns the winning key rather than the
updated state. `none` only for an empty list. -/
def dhondtStepKey (weighted : List (String × Rat)) (s : String → Nat) :
    Option String :=
  (selectMax weighted s).map Prod.fst

/-- QUOTIENT-MAXIMAL (Python `dhondt_step` correctness): the key it returns is
one whose d'Hondt quotient dominates every candidate's — exactly one seat of
highest-averages apportionment given prior seats. Reuses `selectMax_quot_max`
(the single-step optimality also underlying `interleaveDue`, of which
`dhondtStep` is the fold step). -/
theorem dhondtStepKey_quot_max (weighted : List (String × Rat)) (s : String → Nat)
    (r : String × Rat) (hr : selectMax weighted s = some r) :
    dhondtStepKey weighted s = some r.1 ∧
      ∀ e ∈ weighted, dhondtQuot e.2 (s e.1) ≤ dhondtQuot r.2 (s r.1) := by
  refine ⟨?_, selectMax_quot_max weighted s r hr⟩
  simp [dhondtStepKey, hr]

/-- The key that receives the `(cycle + 1)`-th seat. `none` only for an empty
list. This modelled Python `interleave_due` (deleted in wave 3b); it is kept as
the object `interleaveDue_reaches` is stated over. The single step it folds,
`dhondtStep`, IS a live mirror — see `dhondtStepKey`. -/
def interleaveDue (weighted : List (String × Rat)) (cycle : Nat) : Option String :=
  match weighted with
  | [] => none
  | _ =>
    (List.range (cycle + 1)).foldl (fun st _ => dhondtStep weighted st)
      ((none : Option String), (fun _ => 0 : String → Nat)) |>.1

/-! ### No-starvation (bounded reachability) — DISCHARGED in the liveness tier

RESOLVED: this theorem is now fully PROVEN (no `sorry`) as
`Formal.ProgressionTree.interleaveDue_reaches` in
`Formal/Liveness/InterleaveNoStarvation.lean`. Per the liveness quarantine
(`Formal/Liveness/README.md`) the summation / ceiling argument that the two
obstructions below cite lives in the Mathlib-permitted tier, so this safety core
stays Mathlib-free. The honest hypotheses the counting argument needs
(`(weighted.map Prod.fst).Nodup` and per-key positivity — see obstruction 2) are
carried on the liveness-tier statement. The note below is retained as a record
of the original obstructions.

Intended theorem (`interleaveDue_reaches`): every strictly-positive-weight key
`(key, w) ∈ weighted` receives a seat within a bounded window
`interleaveWindow weighted := ⌈W / wₘᵢₙ⌉ + 1` (with `W` the total weight and
`wₘᵢₙ` the least positive weight), i.e.
`∃ c < interleaveWindow weighted, interleaveDue weighted c = some key`.

The mathematical proof is the standard d'Hondt no-starvation argument. Its
stepwise core — that each allocated seat goes to a quotient-maximal key while an
unseated key `key` retains quotient `w / (0 + 1) = w` — is PROVEN here as
`selectMax_quot_max`. From it, the invariant `w * seats x ≤ wₓ` (for every key
`x`, while `key` is unseated) is preserved by `dhondtStep`; summing over the
(distinct) keys gives `w * (total seats) ≤ W`, so after `> W / w` seats `key`
must have been chosen — contradiction, hence reachability.

It was DEFERRED, in core-Lean, for two concrete obstructions, NOT because the
statement is false (the liveness tier has since discharged both — see the
RESOLVED note at the top of this section):

  1. The summation step needs list-sum monotonicity / constant-factoring
     (`List.sum_le_sum`, `w * Σ = Σ (w * ·)`) and a `total seats = step count`
     count, none of which exist in Lean core — mathlib's `Finset`/`BigOperators`
     are quarantined out of the safety core (this file imports nothing).
  2. A faithful proof additionally needs `(weighted.map Prod.fst).Nodup` (unique
     slots — true in the real model) and per-key positivity, hypotheses absent
     from the intended signature; adding them would deviate from the brief.

Also note the kernel cannot reduce `Rat` division, so even a concrete
`decide`/`rfl` witness (e.g. the 1:1 case winning `b` then `a`, the 3:1 case
winning `a,a,a,b`) does not close — those hold by `#eval` only. The substitute
accepted while the deferral stood was `selectMax_quot_max` (the highest-averages
optimality that drives no-starvation) here, plus the Python `interleave_due`
no-starvation unit tests binding the 1:1 and 3:1 schedules; wave 3b deleted
`interleave_due` and those tests with it, which costs nothing now that the full
theorem is proven and `dhondt_step`'s own unit tests bind the live step. -/

end Formal.ProgressionTree
