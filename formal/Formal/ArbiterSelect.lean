/-
Formal model of the `select_pure` PURE CORE from
`src/artifactsmmo_cli/ai/arbiter_select.py` (extracted from `StrategyArbiter.select`
in `src/artifactsmmo_cli/ai/strategy_driver.py`).

## The Python algorithm

`StrategyArbiter.select` builds an ordered candidate list

    candidates = guards ++ collect ++ (step? :: []) ++ discretionary

with guards `is_means = False` and the rest `is_means = True`. Each candidate
has a `repr` (string). The arbiter holds a sticky `committed_repr`.

1. STICKY block:
   * find a means-candidate `c` with `c.repr = committed`
   * if `c` exists ∧ ¬satisfied ∧ ¬suppressed ∧ no guard candidate precedes `c`
     (`guard_precedes = false`):
     - try planning `c`. If plannable, RETURN `c` immediately.
     - else mark `tried = committed` and fall through.
2. WALK: iterate candidates; skip tried / suppressed / satisfied; return the
   first plannable. New `committed = chosen.repr` if `chosen.is_means`, else `none`.
3. Nothing plans → `(none, none)`.

## Modeling

We model candidate `repr` strings as `Nat` ids. `plannable / satisfied /
suppressed : Nat → Bool` are opaque (mirror the Python closures).

The Python `_precedes` compares by `repr`; production guards and means have
distinct Goal classes, so their reprs never collide. We capture this as a
WELL-FORMEDNESS precondition `idsDisjoint` on the candidate list.

## Safety theorem (sticky-vs-guard) — THE bug-likely property

`select_pure_guard_wins`: under id-disjointness, if the head of `cs` is a
guard `g` that is plannable / not satisfied / not suppressed, `selectPure`
returns `g` regardless of `committed`. Sticky cannot keep a means ahead of a
plannable firing guard, because:
  * `guardPrecedes` checks STRUCTURAL precedence including guards that may not
    be plannable. ANY guard candidate forces `guardPrecedes = true` once the
    committed means is at a later index — and in the production guards-first
    list every means lives after every guard.
  * Then the walk encounters the head guard first and returns it.

Lean core only — no mathlib.
-/

namespace Formal.ArbiterSelect

/-- A candidate is `(id, isMeans)` where `isMeans = false` ⇒ guard. -/
structure Candidate where
  id : Nat
  isMeans : Bool
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

/-- First means-candidate with matching id. -/
def findCommitted (cs : List Candidate) (committed : Nat) : Option Candidate :=
  cs.find? (fun c => c.isMeans && decide (c.id = committed))

/-- Some guard strictly precedes the committed id. -/
def guardPrecedes (cs : List Candidate) (committed : Nat) : Bool :=
  (cs.filter (fun c => !c.isMeans)).any (fun g => precedes cs g.id committed)

/-! ### Walk + selector. -/

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
      else if guardPrecedes cs cid then (none, none)
      else if plannable c.id then (some c, some cid)
      else (none, some cid)

/-- The pure selector. `(chosen?, newCommitted?)`. -/
def selectPure
    (cs : List Candidate)
    (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool) :
    Option Candidate × Option Nat :=
  match stickyOutcome cs committed plannable satisfied suppressed with
  | (some c, _) => (some c, some c.id)  -- c is a means by findCommitted
  | (none, tried) =>
    match walk plannable satisfied suppressed tried cs with
    | none => (none, none)
    | some c => (some c, if c.isMeans then some c.id else none)

/-! ### Well-formedness. -/

/-- Guard ids disjoint from means ids: in the production this holds because
guards and means come from distinct Goal classes whose `repr` strings don't
collide. -/
def idsDisjoint (cs : List Candidate) : Prop :=
  ∀ a b, a ∈ cs → b ∈ cs → a.isMeans = false → b.isMeans = true → a.id ≠ b.id

/-! ### `indexOf?` lemmas. -/

theorem indexOf?_head (c : Candidate) (rest : List Candidate) :
    indexOf? (c :: rest) c.id = some 0 := by
  unfold indexOf?; simp

theorem indexOf?_cons_ne (c : Candidate) (rest : List Candidate) (id : Nat)
    (hne : c.id ≠ id) :
    indexOf? (c :: rest) id = (indexOf? rest id).map (· + 1) := by
  show (if c.id = id then some 0 else (indexOf? rest id).map (· + 1)) = _
  rw [if_neg hne]

theorem indexOf?_isSome_of_mem :
    ∀ (cs : List Candidate) (c : Candidate),
      c ∈ cs → (indexOf? cs c.id).isSome := by
  intro cs c hmem
  induction cs with
  | nil => simp at hmem
  | cons d ds ih =>
    rcases List.mem_cons.mp hmem with rfl | hin
    · rw [indexOf?_head]; rfl
    · by_cases h : d.id = c.id
      · unfold indexOf?; simp [h]
      · rw [indexOf?_cons_ne d ds c.id h]
        have hin' := ih hin
        cases hres : indexOf? ds c.id with
        | none => rw [hres] at hin'; simp at hin'
        | some _ => simp

/-! ### Sticky-safety lemmas. -/

/-- `findCommitted = some c` ⇒ c.isMeans=true ∧ c.id=cid ∧ c ∈ cs. -/
theorem findCommitted_some_props (cs : List Candidate) (cid : Nat) (c : Candidate)
    (hfc : findCommitted cs cid = some c) :
    c.isMeans = true ∧ c.id = cid ∧ c ∈ cs := by
  unfold findCommitted at hfc
  have hmem : c ∈ cs := List.mem_of_find?_eq_some hfc
  -- Prove the predicate at c by induction on cs.
  have hpred : (c.isMeans && decide (c.id = cid)) = true := by
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
  rw [Bool.and_eq_true] at hpred
  obtain ⟨h1, h2⟩ := hpred
  refine ⟨h1, ?_, hmem⟩
  exact decide_eq_true_eq.mp h2

/-- Head-guard precedence: head guard `g` with `g.id ≠ cid` precedes any means
`c ∈ rest` whose `c.id = cid`. -/
theorem guardPrecedes_of_head_guard
    (g : Candidate) (rest : List Candidate) (cid : Nat) (c : Candidate)
    (hguard : g.isMeans = false)
    (hne : g.id ≠ cid)
    (hcin : c ∈ rest)
    (hceq : c.id = cid) :
    guardPrecedes (g :: rest) cid = true := by
  unfold guardPrecedes
  have hpr : precedes (g :: rest) g.id cid = true := by
    unfold precedes
    rw [indexOf?_head]
    rw [indexOf?_cons_ne g rest cid hne]
    have hsome : (indexOf? rest cid).isSome := by
      have := indexOf?_isSome_of_mem rest c hcin
      rw [hceq] at this; exact this
    cases hres : indexOf? rest cid with
    | none => rw [hres] at hsome; simp at hsome
    | some k => simp
  have hin_filter : g ∈ (g :: rest).filter (fun c => !c.isMeans) := by
    rw [List.filter_cons]
    have : (!g.isMeans) = true := by simp [hguard]
    simp [this]
  rw [List.any_eq_true]
  exact ⟨g, hin_filter, hpr⟩

/-- Walk on head plannable / non-skipped returns the head. -/
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

/-! ### Theorem (c): THE sticky-safety theorem. -/

/-- Under id-disjointness, if the head is a plannable / non-satisfied /
non-suppressed guard, `selectPure` returns it regardless of `committed`. -/
theorem select_pure_guard_wins
    (g : Candidate) (rest : List Candidate)
    (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool)
    (hguard : g.isMeans = false)
    (hplan : plannable g.id = true)
    (hnsat : satisfied g.id = false)
    (hnsup : suppressed g.id = false)
    (hdisj : idsDisjoint (g :: rest)) :
    (selectPure (g :: rest) committed plannable satisfied suppressed).1 = some g := by
  -- We prove stickyOutcome has first component `none`, and the resulting `tried`
  -- value is never `some g.id`. Then `walk` returns `some g`.
  have hkey :
      ∃ tried, stickyOutcome (g :: rest) committed plannable satisfied suppressed =
        (none, tried) ∧ tried ≠ some g.id := by
    unfold stickyOutcome
    cases committed with
    | none => exact ⟨none, rfl, by intro h; cases h⟩
    | some cid =>
      cases hfc : findCommitted (g :: rest) cid with
      | none => exact ⟨none, by simp [hfc], by intro h; cases h⟩
      | some c =>
        obtain ⟨hcm, hceq, hcmem⟩ := findCommitted_some_props _ _ _ hfc
        -- c can't be g (means vs guard).
        have hcin_rest : c ∈ rest := by
          rcases List.mem_cons.mp hcmem with heq | hin
          · exfalso
            rw [← heq] at hguard
            rw [hcm] at hguard
            exact Bool.noConfusion hguard
          · exact hin
        -- g.id ≠ c.id by disjointness.
        have hne_id : g.id ≠ c.id :=
          hdisj g c ((by simp : g ∈ g :: rest)) hcmem hguard hcm
        have hne : g.id ≠ cid := by rw [← hceq]; exact hne_id
        -- guardPrecedes = true.
        have hgp : guardPrecedes (g :: rest) cid = true :=
          guardPrecedes_of_head_guard g rest cid c hguard hne hcin_rest hceq
        -- Now split on satisfied||suppressed.
        by_cases hsk : satisfied c.id || suppressed c.id
        · refine ⟨none, ?_, by intro h; cases h⟩
          simp [hfc, hsk]
        · refine ⟨none, ?_, by intro h; cases h⟩
          simp [hfc, hsk, hgp]
  obtain ⟨tried, hso, htried⟩ := hkey
  -- Reduce selectPure using hso.
  unfold selectPure
  rw [hso]
  -- Walk returns some g.
  have hwalk := walk_returns_head g rest plannable satisfied suppressed tried
    hplan hnsat hnsup htried
  simp [hwalk]

/-! ### Theorem (d): Sticky idempotence. -/

/-- When no guard candidate exists and `committed = some cid` matches a means
`c` that is plannable / not satisfied / not suppressed, `selectPure` returns `c`. -/
theorem select_pure_sticky_idempotent
    (cs : List Candidate) (cid : Nat) (c : Candidate)
    (plannable satisfied suppressed : Nat → Bool)
    (hnoguard : ∀ x ∈ cs, x.isMeans = true)
    (hfind : findCommitted cs cid = some c)
    (hplan : plannable c.id = true)
    (hnsat : satisfied c.id = false)
    (hnsup : suppressed c.id = false) :
    (selectPure cs (some cid) plannable satisfied suppressed).1 = some c := by
  have hgp_false : guardPrecedes cs cid = false := by
    unfold guardPrecedes
    have hfilter_nil : cs.filter (fun c => !c.isMeans) = [] := by
      apply List.filter_eq_nil_iff.mpr
      intro x hx
      have := hnoguard x hx
      simp [this]
    rw [hfilter_nil]
    rfl
  have hsk_false : (satisfied c.id || suppressed c.id) = false := by
    simp [hnsat, hnsup]
  have hsticky_eq :
      stickyOutcome cs (some cid) plannable satisfied suppressed = (some c, some cid) := by
    unfold stickyOutcome
    simp [hfind, hsk_false, hgp_false, hplan]
  unfold selectPure
  rw [hsticky_eq]

/-! ### Theorem (b): no commitment ⇒ walk in order. -/

/-- With `committed = none`, `selectPure` reduces to `walk` over `cs`. -/
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

private theorem demo_disjoint_2 :
    idsDisjoint [⟨0, false⟩, ⟨1, true⟩] := by
  intro a b ha hb hga hbm
  rcases List.mem_cons.mp ha with rfl | ha
  · rcases List.mem_cons.mp hb with rfl | hb
    · simp at hbm
    · rcases List.mem_cons.mp hb with rfl | hb
      · intro h; cases h
      · simp at hb
  · rcases List.mem_cons.mp ha with rfl | ha
    · simp at hga
    · simp at ha

/-- Witness for safety: a list with a head guard, committed pointing at a
later means. The guard wins. -/
example :
    (selectPure [⟨0, false⟩, ⟨1, true⟩] (some 1)
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨0, false⟩ :=
  select_pure_guard_wins ⟨0, false⟩ [⟨1, true⟩] (some 1) _ _ _
    rfl rfl rfl rfl demo_disjoint_2

/-- Witness for sticky-idempotence: no guards, committed plans → returned. -/
example :
    (selectPure [⟨1, true⟩, ⟨2, true⟩] (some 2)
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨2, true⟩ := by
  apply select_pure_sticky_idempotent [⟨1, true⟩, ⟨2, true⟩] 2 ⟨2, true⟩
  · intro x hx
    rcases List.mem_cons.mp hx with rfl | hx
    · rfl
    · rcases List.mem_cons.mp hx with rfl | hx
      · rfl
      · simp at hx
  · unfold findCommitted; rfl
  · rfl
  · rfl
  · rfl

/-- Witness for no-commitment band order. With `committed = none` and an
all-plannable list, walk returns the head. -/
example :
    (selectPure [⟨1, true⟩, ⟨2, true⟩] none
      (fun _ => true) (fun _ => false) (fun _ => false)).1 = some ⟨1, true⟩ := by
  rw [select_pure_no_commitment_is_walk]
  unfold walk
  simp

end Formal.ArbiterSelect
