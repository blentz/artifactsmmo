-- @concept: core, planner @property: dominance, totality
/-
Formal model of the `select_interrupt` / `select_pure` PURE CORE from
`src/artifactsmmo_cli/ai/arbiter_select.py` (extracted from
`StrategyArbiter._arbitrate` in `src/artifactsmmo_cli/ai/strategy_driver.py`).

## The Python algorithm

`StrategyArbiter.select` builds an ordered candidate list

    candidates = guards ++ collect ++ step? ++ raids ++ fallbacks ++ discretionary

and `_arbitrate` splits it (Phase 5-2a of docs/PLAN_decision_architecture_redesign.md):

1. INTERRUPTS (`select_interrupt`): the band-0 guards, in order. The first one
   that is not satisfied and plans wins, and the commitment is UNCHANGED — an
   interrupt runs and the intention resumes.
2. Otherwise the MEANS (`select_pure`): the rest, in band order.
   * STICKY: if the committed id names a candidate that is not satisfied, not
     suppressed, and not preceded by a strictly-lower-band candidate (unless it
     is discretionary, band 5), try it first; if it plans, return it.
   * WALK: skip the sticky-tried id and every suppressed / satisfied candidate;
     return the first that plans. It becomes the new commitment.
   * Nothing plans → `(none, none)`.

Until Phase 5-2a the guards were candidates of the same walk, with a
`guardPrecedes` rule blocking the sticky path whenever one was present; that
rule and its theorems are now `selectInterrupt` and the `arbitrate_*`
theorems, where "a plannable interrupt wins regardless of commitment" holds by
construction.

## Modeling

Candidate `repr` strings are `Nat` ids; `plannable / satisfied / suppressed :
Nat → Bool` are opaque (mirror the Python closures).

Lean core only — no mathlib.
-/

namespace Formal.ArbiterSelect

/-- A candidate is `(id, band)`. `band` is the priority band (guards 0, collect
1, step 2, raid 3, fallback step 4, discretionary 5); lower band = higher
priority. Band-0 candidates are interrupts. -/
structure Candidate where
  id : Nat
  band : Int
deriving Repr, DecidableEq

/-! ### Helpers (mirror Python `_precedes`). -/

/-- Index of the first candidate whose id matches, else `none`. -/
def indexOf? : List Candidate → Nat → Option Nat
  | [], _ => none
  | c :: rest, id =>
    if c.id = id then some 0
    else (indexOf? rest id).map (· + 1)

/-- `a` strictly precedes `b` in `cs`. Both must be present. -/
def precedes (cs : List Candidate) (a b : Nat) : Bool :=
  match indexOf? cs a, indexOf? cs b with
  | some ia, some ib => decide (ia < ib)
  | _, _ => false

/-- First candidate with matching id. -/
def findCommitted (cs : List Candidate) (committed : Nat) : Option Candidate :=
  cs.find? (fun c => decide (c.id = committed))

/-- A strictly-lower-band candidate strictly precedes the committed id — and the
committed band is not discretionary (band < 5). Mirrors the Python band-aware
sticky preemption: a higher-priority (lower-band) means that comes first must not
be preempted by a sticky lower-priority commitment. Discretionary commits
(band 5) are exempt.

The literal mirrors the SAME inlined literal in `arbiter_select.select_pure`
(the extractor's v1 subset cannot resolve a module constant), so the two must
move together — the Python half is guarded by
`test_discretionary_band_literal_matches_constant`. -/
def lowerBandPrecedes (cs : List Candidate) (committed : Nat) (committedBand : Int) : Bool :=
  decide (committedBand < 5) &&
    cs.any (fun d => decide (d.band < committedBand) && precedes cs d.id committed)

/-! ### Interrupt pre-pass. -/

/-- The first interrupt that is not satisfied and plans. Mirrors
`select_interrupt`. -/
def selectInterrupt (is : List Candidate) (plannable satisfied : Nat → Bool) :
    Option Candidate :=
  is.find? (fun c => !satisfied c.id && plannable c.id)

/-! ### Walk + selector over the means. -/

/-- Walk: first candidate that is plannable, not in `tried`, not suppressed,
not satisfied. -/
def walk
    (plannable satisfied suppressed : Nat → Bool)
    (tried : Option Nat) : List Candidate → Option Candidate
  | [] => none
  | c :: rest =>
      let skip :=
        (match tried with | some t => decide (t = c.id) | none => false)
        || suppressed c.id || satisfied c.id
      if skip then walk plannable satisfied suppressed tried rest
      else if plannable c.id then some c
      else walk plannable satisfied suppressed tried rest

/-- Sticky outcome: `(chosenIfPlanned, triedIfAttempted)`. -/
def stickyOutcome
    (cs : List Candidate) (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool) :
    Option Candidate × Option Nat :=
  match committed with
  | none => (none, none)
  | some cid =>
    match findCommitted cs cid with
    | none => (none, none)
    | some c =>
      if satisfied c.id || suppressed c.id then (none, none)
      else if lowerBandPrecedes cs cid c.band then (none, none)
      else if plannable c.id then (some c, some cid)
      else (none, some cid)

/-- The pure selector over the means. `(chosen?, newCommitted?)`: the chosen
candidate becomes the commitment. -/
def selectPure
    (cs : List Candidate)
    (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool) :
    Option Candidate × Option Nat :=
  match stickyOutcome cs committed plannable satisfied suppressed with
  | (some c, _) => (some c, some c.id)
  | (none, tried) =>
    match walk plannable satisfied suppressed tried cs with
    | none => (none, none)
    | some c => (some c, some c.id)

/-- The arbitration: interrupts first (commitment kept), then the means. -/
def arbitrate
    (is cs : List Candidate)
    (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool) :
    Option Candidate × Option Nat :=
  match selectInterrupt is plannable satisfied with
  | some g => (some g, committed)
  | none => selectPure cs committed plannable satisfied suppressed

/-! ### `indexOf?` lemmas. -/

theorem indexOf?_head (c : Candidate) (rest : List Candidate) :
    indexOf? (c :: rest) c.id = some 0 := by
  simp [indexOf?]

theorem indexOf?_cons_ne (c : Candidate) (rest : List Candidate) (id : Nat)
    (hne : c.id ≠ id) :
    indexOf? (c :: rest) id = (indexOf? rest id).map (· + 1) := by
  show (if c.id = id then some 0 else (indexOf? rest id).map (· + 1)) = _
  rw [if_neg hne]

/-- `findCommitted = some c` ⇒ `c.id = cid ∧ c ∈ cs`. -/
theorem findCommitted_some_props (cs : List Candidate) (cid : Nat) (c : Candidate)
    (hfc : findCommitted cs cid = some c) :
    c.id = cid ∧ c ∈ cs := by
  unfold findCommitted at hfc
  have hmem : c ∈ cs := List.mem_of_find?_eq_some hfc
  have hpred : decide (c.id = cid) = true := by
    clear hmem
    induction cs with
    | nil => simp [List.find?] at hfc
    | cons d ds ih =>
      rw [List.find?] at hfc
      split at hfc
      · rename_i hd
        injection hfc with heq
        rw [← heq]; exact hd
      · exact ih hfc
  exact ⟨decide_eq_true_eq.mp hpred, hmem⟩

/-! ### Interrupt theorems. -/

/-- The first interrupt in order wins when it is unsatisfied and plans. -/
theorem select_interrupt_head_wins (g : Candidate) (rest : List Candidate)
    (plannable satisfied : Nat → Bool)
    (hplan : plannable g.id = true) (hnsat : satisfied g.id = false) :
    selectInterrupt (g :: rest) plannable satisfied = some g := by
  simp [selectInterrupt, List.find?, hplan, hnsat]

/-- Any unsatisfied plannable interrupt makes the pre-pass return SOME
interrupt from the list (the first such one). -/
theorem select_interrupt_any_plannable_wins (is : List Candidate) (g : Candidate)
    (plannable satisfied : Nat → Bool)
    (hmem : g ∈ is) (hplan : plannable g.id = true) (hnsat : satisfied g.id = false) :
    ∃ r, selectInterrupt is plannable satisfied = some r ∧ r ∈ is := by
  unfold selectInterrupt
  cases hf : is.find? (fun c => !satisfied c.id && plannable c.id) with
  | none =>
    exfalso
    have hall := List.find?_eq_none.mp hf g hmem
    simp [hplan, hnsat] at hall
  | some r => exact ⟨r, rfl, List.mem_of_find?_eq_some hf⟩

/-- INTERRUPT SAFETY: a plannable, unsatisfied interrupt wins the arbitration
REGARDLESS of the commitment, and the commitment survives it (the intention
resumes after the interrupt). -/
theorem arbitrate_interrupt_wins (is cs : List Candidate) (committed : Option Nat)
    (g : Candidate) (plannable satisfied suppressed : Nat → Bool)
    (hmem : g ∈ is) (hplan : plannable g.id = true) (hnsat : satisfied g.id = false) :
    ∃ r, r ∈ is ∧
      arbitrate is cs committed plannable satisfied suppressed = (some r, committed) := by
  obtain ⟨r, hr, hrmem⟩ :=
    select_interrupt_any_plannable_wins is g plannable satisfied hmem hplan hnsat
  exact ⟨r, hrmem, by simp [arbitrate, hr]⟩

/-- With no interrupt to run, the arbitration is the means selector. -/
theorem arbitrate_no_interrupt_is_select_pure (is cs : List Candidate)
    (committed : Option Nat) (plannable satisfied suppressed : Nat → Bool)
    (hnone : selectInterrupt is plannable satisfied = none) :
    arbitrate is cs committed plannable satisfied suppressed =
      selectPure cs committed plannable satisfied suppressed := by
  simp [arbitrate, hnone]

/-! ### Means theorems. -/

/-- Walk-head: a head candidate that is plannable and not skipped is returned. -/
theorem walk_returns_head
    (c : Candidate) (rest : List Candidate)
    (plannable satisfied suppressed : Nat → Bool)
    (tried : Option Nat)
    (hplan : plannable c.id = true)
    (hnsat : satisfied c.id = false)
    (hnsup : suppressed c.id = false)
    (htried : tried ≠ some c.id) :
    walk plannable satisfied suppressed tried (c :: rest) = some c := by
  unfold walk
  cases htr : tried with
  | none => simp [hnsat, hnsup, hplan]
  | some t =>
    have ht_ne : t ≠ c.id := by
      intro heq; apply htried; rw [htr, heq]
    simp [ht_ne, hnsat, hnsup, hplan]

/-- Sticky idempotence: when `committed = some cid` names a candidate `c` that
plans, is not satisfied / suppressed, and is not preceded by a lower band,
`selectPure` returns `c`. -/
theorem select_pure_sticky_idempotent
    (cs : List Candidate) (cid : Nat) (c : Candidate)
    (plannable satisfied suppressed : Nat → Bool)
    (hfind : findCommitted cs cid = some c)
    (hlbp : lowerBandPrecedes cs cid c.band = false)
    (hplan : plannable c.id = true)
    (hnsat : satisfied c.id = false)
    (hnsup : suppressed c.id = false) :
    (selectPure cs (some cid) plannable satisfied suppressed).1 = some c := by
  have hsk_false : (satisfied c.id || suppressed c.id) = false := by
    simp [hnsat, hnsup]
  have hsticky_eq :
      stickyOutcome cs (some cid) plannable satisfied suppressed = (some c, some cid) := by
    unfold stickyOutcome
    simp [hfind, hsk_false, hlbp, hplan]
  unfold selectPure
  rw [hsticky_eq]

/-- Band-aware anti-freeze (the copper_ring freeze): when a strictly-lower-band
candidate `d` precedes the committed candidate `c` (and `c` is not
discretionary, `c.band < 5`), the sticky path does NOT return the committed
candidate — `selectPure` runs the walk instead. -/
theorem select_pure_no_sticky_preempt_lower_band
    (cs : List Candidate) (cid : Nat) (c d : Candidate)
    (plannable satisfied suppressed : Nat → Bool)
    (hfind : findCommitted cs cid = some c)
    (hlow : d ∈ cs)
    (hband : d.band < c.band)
    (hcbandlt : c.band < 5)
    (hprec : precedes cs d.id cid = true) :
    (stickyOutcome cs (some cid) plannable satisfied suppressed).1 = none := by
  have hlbp : lowerBandPrecedes cs cid c.band = true := by
    unfold lowerBandPrecedes
    have h1 : decide (c.band < 5) = true := by rw [decide_eq_true_eq]; exact hcbandlt
    have h2 : cs.any (fun x => decide (x.band < c.band) && precedes cs x.id cid) = true := by
      rw [List.any_eq_true]
      refine ⟨d, hlow, ?_⟩
      rw [Bool.and_eq_true]
      refine ⟨?_, hprec⟩
      rw [decide_eq_true_eq]; exact hband
    rw [h1, h2]; rfl
  unfold stickyOutcome
  simp only [hfind]
  by_cases h1 : satisfied c.id || suppressed c.id
  · simp [h1]
  · simp [h1, hlbp]

/-- With no commitment, `selectPure` is the walk in band order. -/
theorem select_pure_no_commitment_is_walk
    (cs : List Candidate)
    (plannable satisfied suppressed : Nat → Bool) :
    (selectPure cs none plannable satisfied suppressed).1 =
      walk plannable satisfied suppressed none cs := by
  have hsticky_eq :
      stickyOutcome cs none plannable satisfied suppressed = (none, none) := by
    unfold stickyOutcome; rfl
  unfold selectPure
  rw [hsticky_eq]
  cases hw : walk plannable satisfied suppressed none cs with
  | none => simp [hw]
  | some c => simp [hw]

/-! ### Non-vacuity witnesses (real provable instances). -/

/-- An interrupt (the second, the first does not plan) wins over a commitment to
a later means, and the commitment is kept. -/
example :
    arbitrate [⟨0, 0⟩, ⟨1, 0⟩] [⟨2, 2⟩] (some 2)
      (fun n => decide (n = 1) || decide (n = 2)) (fun _ => false) (fun _ => false)
      = (some ⟨1, 0⟩, some 2) := by
  decide

/-- With no interrupt planning, the committed means is kept sticky. -/
example :
    (selectPure [⟨1, 2⟩, ⟨2, 2⟩] (some 2)
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨2, 2⟩ :=
  select_pure_sticky_idempotent [⟨1, 2⟩, ⟨2, 2⟩] 2 ⟨2, 2⟩ _ _ _
    (by decide) (by decide) rfl rfl rfl

/-- No commitment: the walk returns the head. -/
example :
    (selectPure [⟨1, 2⟩, ⟨2, 2⟩] none
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨1, 2⟩ := by
  rw [select_pure_no_commitment_is_walk]
  unfold walk
  simp

/-- The copper_ring freeze witness: a committed FALLBACK-band means `⟨1, 4⟩`
preceded by a band-2 means — the sticky path yields `none`. -/
example :
    (stickyOutcome [⟨0, 2⟩, ⟨1, 4⟩] (some 1)
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = none :=
  select_pure_no_sticky_preempt_lower_band
    [⟨0, 2⟩, ⟨1, 4⟩] 1 ⟨1, 4⟩ ⟨0, 2⟩
    (fun _ => true) (fun _ => false) (fun _ => false)
    (by decide) (by decide) (by decide) (by decide) (by decide)

/-- The other side of the boundary: a committed DISCRETIONARY means (band 5)
preceded by a band-2 means is exempt. -/
example :
    lowerBandPrecedes [⟨0, 2⟩, ⟨1, 5⟩] 1 5 = false := by decide

/-- End-to-end: with the sticky path blocked, the walk returns the band-2 means. -/
example :
    (selectPure [⟨0, 2⟩, ⟨1, 4⟩] (some 1)
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨0, 2⟩ := by
  decide

end Formal.ArbiterSelect
