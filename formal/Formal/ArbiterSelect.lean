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

## Safety theorems (sticky-vs-guard)

* `select_pure_guard_wins` (HEAD specialisation): if the HEAD of `cs` is a
  plannable / non-satisfied / non-suppressed guard, `selectPure` returns it.

* `select_pure_any_plannable_guard_wins` (GENERAL — closes the prior
  head-only caveat): under `guardsFirst` (every guard precedes every means —
  the genuine production band ordering `guards ++ collect ++ step ++
  discretionary`) and `idsDisjoint`, ANY plannable / non-satisfied /
  non-suppressed guard `g ∈ cs` forces `selectPure` to return a guard
  (`.isMeans = false`), regardless of `committed`. The proof routes through
  a helper `guard_precedes_means_in_guardsFirst` that produces explicit
  indices `i < j` for the guard/means pair, then concludes via a walk lemma
  `walk_returns_guard_when_plannable_guard_exists` that the walk over `cs`
  returns a guard whenever such a `g` exists. There is no longer a "head-
  guard only" disclosed gap; the differential test's full coverage is now
  matched by a Lean theorem with the same scope.

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

/-! ### Theorem (c'): GENERALISED guard-wins — any plannable firing guard in
the list (not just the head) prevents a means from being returned.

In production `candidates = guards ++ collect ++ (step?) ++ discretionary` so
EVERY guard precedes EVERY means in the list. We capture this as the structural
invariant `guardsFirst`. Then ANY plannable / non-satisfied / non-suppressed
guard `g ∈ cs` forces `selectPure`'s returned candidate to itself be a guard
(`.isMeans = false`), regardless of `committed`. This closes the gap that the
head-only `select_pure_guard_wins` left as a differential-test caveat. -/

/-- Structural invariant: every guard candidate precedes every means candidate
in the list. (Genuine production invariant from the band ordering.) -/
def guardsFirst : List Candidate → Prop
  | [] => True
  | c :: rest =>
    (c.isMeans = true → ∀ x ∈ rest, x.isMeans = true) ∧ guardsFirst rest

theorem guardsFirst_cons {c : Candidate} {rest : List Candidate}
    (h : guardsFirst (c :: rest)) :
    (c.isMeans = true → ∀ x ∈ rest, x.isMeans = true) ∧ guardsFirst rest := h

/-- Under `guardsFirst`, once we see a means at the head, every following
candidate is also a means. -/
theorem guardsFirst_tail_all_means {c : Candidate} {rest : List Candidate}
    (h : guardsFirst (c :: rest)) (hcm : c.isMeans = true) :
    ∀ x ∈ rest, x.isMeans = true :=
  (guardsFirst_cons h).1 hcm

/-- If `guardsFirst cs` and `g ∈ cs` is a guard, no preceding cand in walk-order
can be a means: equivalently, induction shows the guard is reached before any
means in cs. We capture this via: if `c :: rest` is `guardsFirst` and some guard
exists in `c :: rest`, then `c` itself is a guard OR the head-means case is empty.

Sharper form: a `guardsFirst` list containing a guard has its head be a guard. -/
theorem guardsFirst_head_guard_of_mem
    (c : Candidate) (rest : List Candidate) (g : Candidate)
    (hgf : guardsFirst (c :: rest)) (hg : g ∈ c :: rest) (hguard : g.isMeans = false) :
    c.isMeans = false := by
  rcases List.mem_cons.mp hg with rfl | hin
  · exact hguard
  · -- g ∈ rest with g.isMeans=false; if c.isMeans=true then guardsFirst forces
    -- every x ∈ rest to be a means, contradicting g.
    cases hcm : c.isMeans with
    | false => rfl
    | true =>
      have := guardsFirst_tail_all_means hgf hcm g hin
      rw [hguard] at this; exact Bool.noConfusion this

/-- WALK lemma: if `cs` is `guardsFirst` and contains a plannable / non-satisfied
/ non-suppressed guard whose id is not `tried`, then `walk` returns a candidate
whose `isMeans = false` (a guard). -/
theorem walk_returns_guard_when_plannable_guard_exists
    (cs : List Candidate)
    (plannable satisfied suppressed : Nat → Bool)
    (tried : Option Nat)
    (hgf : guardsFirst cs)
    (g : Candidate) (hgmem : g ∈ cs) (hguard : g.isMeans = false)
    (hplan : plannable g.id = true)
    (hnsat : satisfied g.id = false)
    (hnsup : suppressed g.id = false)
    (htried : tried ≠ some g.id) :
    ∃ r, walk plannable satisfied suppressed tried cs = some r ∧ r.isMeans = false := by
  induction cs with
  | nil => simp at hgmem
  | cons c rest ih =>
    -- The head of (c :: rest) must itself be a guard by guardsFirst.
    have hch : c.isMeans = false := guardsFirst_head_guard_of_mem c rest g hgf hgmem hguard
    -- Case split on whether the head is the witness g or a different guard.
    by_cases heq : c = g
    · -- Head is g itself: walk returns g (which is a guard).
      subst heq
      refine ⟨c, ?_, hch⟩
      exact walk_returns_head c rest plannable satisfied suppressed tried hplan hnsat hnsup htried
    · -- Head is a different guard. Walk either returns the head (if it is itself
      -- plannable / not-skipped / not-tried), else recurses on `rest`.
      have hgrest : g ∈ rest := by
        rcases List.mem_cons.mp hgmem with hh | hh
        · exact absurd hh.symm heq
        · exact hh
      have hrec : ∃ r, walk plannable satisfied suppressed tried rest = some r ∧
                       r.isMeans = false := ih hgf.2 hgrest
      obtain ⟨r, hwr, hrm⟩ := hrec
      -- Concretely compute walk on (c :: rest) by cases on `tried`.
      cases htr : tried with
      | none =>
        unfold walk
        -- skip = false || suppressed c.id || satisfied c.id
        by_cases hsk : (suppressed c.id || satisfied c.id) = true
        · simp only [Bool.false_or, hsk, if_true]
          rw [htr] at hwr
          exact ⟨r, hwr, hrm⟩
        · have hskf : (suppressed c.id || satisfied c.id) = false := by
            cases hh : (suppressed c.id || satisfied c.id) with
            | false => rfl
            | true => exact absurd hh hsk
          simp only [Bool.false_or, hskf]
          by_cases hplc : plannable c.id = true
          · simp only [hplc, if_true]
            exact ⟨c, rfl, hch⟩
          · have hplc' : plannable c.id = false := by
              cases hpl : plannable c.id with
              | false => rfl
              | true => exact absurd hpl hplc
            simp only [hplc']
            rw [htr] at hwr
            exact ⟨r, hwr, hrm⟩
      | some t =>
        unfold walk
        -- skip evaluates to: decide (t = c.id) || suppressed c.id || satisfied c.id
        by_cases htc : t = c.id
        · -- walk skips head (skip is true via the tried branch), recurse on rest
          have ht_dec : decide (t = c.id) = true := by simp [htc]
          simp only [ht_dec, Bool.true_or, if_true]
          rw [htr] at hwr
          exact ⟨r, hwr, hrm⟩
        · have ht_dec : decide (t = c.id) = false := by simp [htc]
          by_cases hsk : (suppressed c.id || satisfied c.id) = true
          · simp only [ht_dec, Bool.false_or, hsk, if_true]
            rw [htr] at hwr
            exact ⟨r, hwr, hrm⟩
          · have hskf : (suppressed c.id || satisfied c.id) = false := by
              cases hh : (suppressed c.id || satisfied c.id) with
              | false => rfl
              | true => exact absurd hh hsk
            simp only [ht_dec, Bool.false_or, hskf]
            by_cases hplc : plannable c.id = true
            · simp only [hplc, if_true]
              exact ⟨c, rfl, hch⟩
            · have hplc' : plannable c.id = false := by
                cases hpl : plannable c.id with
                | false => rfl
                | true => exact absurd hpl hplc
              simp only [hplc']
              rw [htr] at hwr
              exact ⟨r, hwr, hrm⟩

/-- A guard `g` in a `guardsFirst` list precedes any means `c` (with c.id = cid,
g.id ≠ cid) in the same list — direct index existence. -/
theorem guard_precedes_means_in_guardsFirst
    (cs : List Candidate) (g c : Candidate) (cid : Nat)
    (hgmem : g ∈ cs) (hguard : g.isMeans = false)
    (hcmem : c ∈ cs) (hcm : c.isMeans = true) (hceq : c.id = cid)
    (hne_cid : g.id ≠ cid)
    (hgf : guardsFirst cs) (hdisj : idsDisjoint cs) :
    ∃ i j, indexOf? cs g.id = some i ∧ indexOf? cs cid = some j ∧ i < j := by
  induction cs with
  | nil => simp at hgmem
  | cons d ds ih =>
    have hdh : d.isMeans = false :=
      guardsFirst_head_guard_of_mem d ds g hgf hgmem hguard
    by_cases hdg : d.id = g.id
    · -- d is head with id = g.id. c is means (head is guard) so c ∈ ds.
      have hcds : c ∈ ds := by
        rcases List.mem_cons.mp hcmem with hh | hh
        · -- hh : c = d. then c.isMeans = d.isMeans = false, contradicting hcm.
          exfalso
          have : c.isMeans = false := by rw [hh]; exact hdh
          rw [this] at hcm; exact Bool.noConfusion hcm
        · exact hh
      have hsome : (indexOf? ds cid).isSome := by
        have := indexOf?_isSome_of_mem ds c hcds; rw [hceq] at this; exact this
      cases hres : indexOf? ds cid with
      | none => rw [hres] at hsome; simp at hsome
      | some kb =>
        refine ⟨0, kb + 1, ?_, ?_, by omega⟩
        · unfold indexOf?; simp [hdg]
        · have hdnc : d.id ≠ cid := by rw [hdg]; exact hne_cid
          rw [indexOf?_cons_ne d ds cid hdnc, hres]; rfl
    · -- d.id ≠ g.id. g ∈ ds. Recurse.
      have hgds : g ∈ ds := by
        rcases List.mem_cons.mp hgmem with hh | hh
        · exfalso; rw [hh] at hdg; exact hdg rfl
        · exact hh
      have hcds : c ∈ ds := by
        rcases List.mem_cons.mp hcmem with hh | hh
        · exfalso
          have : c.isMeans = false := by rw [hh]; exact hdh
          rw [this] at hcm; exact Bool.noConfusion hcm
        · exact hh
      have hgf' : guardsFirst ds := hgf.2
      have hdisj' : idsDisjoint ds := by
        intro a b ha hb hga hbm
        exact hdisj a b (List.mem_cons_of_mem _ ha)
          (List.mem_cons_of_mem _ hb) hga hbm
      obtain ⟨i, j, hgi, hcj, hij⟩ := ih hgds hcds hgf' hdisj'
      have hdnc : d.id ≠ cid := by
        rw [← hceq]
        exact hdisj d c (by simp) hcmem hdh hcm
      refine ⟨i + 1, j + 1, ?_, ?_, by omega⟩
      · rw [indexOf?_cons_ne d ds g.id hdg, hgi]; rfl
      · rw [indexOf?_cons_ne d ds cid hdnc, hcj]; rfl

/-- THE GENERALISED guard-safety theorem: under `guardsFirst` + `idsDisjoint`,
ANY plannable / non-satisfied / non-suppressed guard `g ∈ cs` forces
`selectPure` to return a guard — even if the committed means lies later in the
list and even if `g` is not the head. -/
theorem select_pure_any_plannable_guard_wins
    (cs : List Candidate) (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool)
    (g : Candidate) (hgmem : g ∈ cs) (hguard : g.isMeans = false)
    (hplan : plannable g.id = true)
    (hnsat : satisfied g.id = false)
    (hnsup : suppressed g.id = false)
    (hgf : guardsFirst cs)
    (hdisj : idsDisjoint cs) :
    ∃ r, (selectPure cs committed plannable satisfied suppressed).1 = some r ∧
         r.isMeans = false := by
  -- Sticky outcome: tried is never `some g.id` because any committed id either
  -- mismatches g.id (disjointness) or doesn't bind a means at all.
  have hkey :
      ∃ tried, stickyOutcome cs committed plannable satisfied suppressed = (none, tried)
        ∧ tried ≠ some g.id := by
    unfold stickyOutcome
    cases committed with
    | none => exact ⟨none, rfl, by intro h; cases h⟩
    | some cid =>
      cases hfc : findCommitted cs cid with
      | none => exact ⟨none, by simp [hfc], by intro h; cases h⟩
      | some c =>
        obtain ⟨hcm, hceq, hcmem⟩ := findCommitted_some_props _ _ _ hfc
        -- c is a means with id=cid. By disjointness, g.id ≠ c.id.
        have hne_id : g.id ≠ c.id := hdisj g c hgmem hcmem hguard hcm
        have hne_cid : g.id ≠ cid := by rw [← hceq]; exact hne_id
        -- guardPrecedes cs cid = true because g (a guard ∈ cs) precedes c.
        -- We don't need to compute it explicitly; we just need to show tried ≠ some g.id.
        -- Whichever branch stickyOutcome takes, tried ∈ {none, some cid}, and cid ≠ g.id.
        by_cases hsk : satisfied c.id || suppressed c.id
        · refine ⟨none, ?_, by intro h; cases h⟩
          simp [hfc, hsk]
        · by_cases hgp : guardPrecedes cs cid = true
          · refine ⟨none, ?_, by intro h; cases h⟩
            simp [hfc, hsk, hgp]
          · have hgp' : guardPrecedes cs cid = false := by
              cases hg' : guardPrecedes cs cid with
              | false => rfl
              | true => exact absurd hg' hgp
            by_cases hplc : plannable c.id = true
            · -- This branch returns (some c, some cid) — but THIS would crash
              -- our walk-based reasoning. So we must show this branch is
              -- impossible UNDER the guardsFirst hypothesis: if cs is guardsFirst
              -- and contains a guard g, then ANY means in cs comes AFTER g,
              -- making guardPrecedes cs cid = true. Contradiction with hgp'.
              exfalso
              -- Show guardPrecedes cs cid = true using g.
              have hpr : precedes cs g.id cid = true := by
                obtain ⟨i, j, hgi, hcj, hij⟩ :=
                  guard_precedes_means_in_guardsFirst cs g c cid
                    hgmem hguard hcmem hcm hceq hne_cid hgf hdisj
                unfold precedes
                rw [hgi, hcj]
                simp [hij]
              -- guardPrecedes via g (a guard in cs) precedes c
              have hgin_filter : g ∈ cs.filter (fun c => !c.isMeans) := by
                rw [List.mem_filter]; exact ⟨hgmem, by simp [hguard]⟩
              have : guardPrecedes cs cid = true := by
                unfold guardPrecedes
                rw [List.any_eq_true]
                exact ⟨g, hgin_filter, hpr⟩
              exact absurd this hgp
            · have hplc' : plannable c.id = false := by
                cases hp : plannable c.id with
                | false => rfl
                | true => exact absurd hp hplc
              refine ⟨some cid, ?_, ?_⟩
              · simp [hfc, hsk, hgp', hplc']
              · intro h; injection h with h; exact hne_cid h.symm
  obtain ⟨tried, hso, htried⟩ := hkey
  obtain ⟨r, hwalk, hrm⟩ :=
    walk_returns_guard_when_plannable_guard_exists cs plannable satisfied suppressed tried
      hgf g hgmem hguard hplan hnsat hnsup htried
  refine ⟨r, ?_, hrm⟩
  unfold selectPure
  rw [hso]
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

/-- Non-vacuity witness for the GENERALISED any-plannable-guard-wins theorem:
a multi-guard input where the SECOND guard is the firing one (head guard is
non-plannable). With `committed = some 2` (a means later in the list) the
selector returns a guard (specifically the second guard, which is plannable). -/
example :
    let cs : List Candidate := [⟨0, false⟩, ⟨1, false⟩, ⟨2, true⟩]
    let pl : Nat → Bool := fun n => decide (n = 1) || decide (n = 2)  -- guard 1 + means 2 plannable
    let sat : Nat → Bool := fun _ => false
    let sup : Nat → Bool := fun _ => false
    ∃ r, (selectPure cs (some 2) pl sat sup).1 = some r ∧ r.isMeans = false := by
  apply select_pure_any_plannable_guard_wins
    [⟨0, false⟩, ⟨1, false⟩, ⟨2, true⟩] (some 2) _ _ _ ⟨1, false⟩
  · simp
  · rfl
  · rfl
  · rfl
  · rfl
  · -- guardsFirst: [⟨0,f⟩, ⟨1,f⟩, ⟨2,t⟩]. Each conjunct: head.isMeans=true → all tail are means.
    -- For c0 (isMeans=false): premise false, trivial.
    -- For c1 (isMeans=false): premise false, trivial.
    -- For c2 (isMeans=true): tail is [], vacuous.
    refine ⟨?_, ?_, ?_, trivial⟩
    · intro h; exact Bool.noConfusion h
    · intro h; exact Bool.noConfusion h
    · intro _ x hx; simp at hx
  · -- idsDisjoint: all means ids ≠ all guard ids
    intro a b ha hb hga hbm
    rcases List.mem_cons.mp ha with rfl | ha
    · rcases List.mem_cons.mp hb with rfl | hb
      · simp at hbm
      · rcases List.mem_cons.mp hb with rfl | hb
        · simp at hbm
        · rcases List.mem_cons.mp hb with rfl | hb
          · intro h; cases h
          · simp at hb
    · rcases List.mem_cons.mp ha with rfl | ha
      · rcases List.mem_cons.mp hb with rfl | hb
        · simp at hbm
        · rcases List.mem_cons.mp hb with rfl | hb
          · simp at hbm
          · rcases List.mem_cons.mp hb with rfl | hb
            · intro h; cases h
            · simp at hb
      · rcases List.mem_cons.mp ha with rfl | ha
        · simp at hga
        · simp at ha

end Formal.ArbiterSelect
