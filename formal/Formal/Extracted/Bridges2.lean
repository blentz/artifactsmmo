import Formal.Extracted.ArbiterSelect
import Formal.ArbiterSelect

/-!
# Extracted ↔ hand-model bridge: arbiter_select (P2b, docs/PLAN_mechanical_extraction.md)

HAND-WRITTEN (continuation of `Bridges.lean`; split out for size). Proves the
mechanically-extracted `Extracted.ArbiterSelect.select_pure` (regenerated from
`src/artifactsmmo_cli/ai/arbiter_select.py` by `scripts/extract_lean.py`)
equal to the hand model `Formal.ArbiterSelect.selectPure` — THE most-pinned
decision function in the repo (objective-committed arbitration, worth
suppression, sticky preemption).

* `arbiter_select_bridge` — a FULL commuting square, with NO wellformedness
  hypothesis beyond injectivity of the id embedding: for EVERY injective
  `f : Nat → String` (the hand model codes candidate `repr` strings as `Nat`
  ids; `f` embeds them back into strings), every candidate list, every
  committed id and all three predicate oracles,

      extracted ∘ encode = encOut ∘ handModel

  where the encoding instantiates the extracted polymorphism at `Goal := Nat`,
  `Action := Unit` (goals are pure payload — carried, never inspected; a plan
  is `[()]` iff plannable) and `encOut` packages the hand `(chosen?,
  newCommitted?)` as the Python `(goal?, plan, committed_repr?)` triple.
  Duplicate ids, missing committed ids and arbitrary orderings are all in
  scope: both sides resolve them first-match-wins, so no `idsDisjoint` /
  `guardsFirst` precondition is needed for equality (those remain hypotheses
  of the hand SAFETY theorems only).

* `select_pure_guard_wins_extracted` — THE sticky-safety theorem transferred
  to the extracted definition: a plannable, non-satisfied, non-suppressed
  head guard wins regardless of commitment. The generalised
  any-plannable-guard-wins, sticky-idempotence and walk-order theorems
  transfer through the same square.

NO sorry / admit / extra axioms (gate-enforced). Lean core only — no mathlib.
-/

namespace Extracted.Bridges

open Formal.ArbiterSelect (indexOf? precedes findCommitted guardPrecedes walk
  stickyOutcome selectPure)

/-! ## Encodings -/

/-- Candidate encoding: the hand `(id, isMeans)` becomes the extracted
`(goal, is_means, repr_)` with `Goal := Nat` (the id is the payload) and the
repr string the image of the id under the embedding `f`. -/
def encC (f : Nat → String) (c : Formal.ArbiterSelect.Candidate) :
    Extracted.ArbiterSelect.Candidate Nat :=
  ⟨c.id, c.isMeans, f c.id⟩

@[simp] theorem encC_goal (f : Nat → String) (c : Formal.ArbiterSelect.Candidate) :
    (encC f c).goal = c.id := rfl

@[simp] theorem encC_is_means (f : Nat → String) (c : Formal.ArbiterSelect.Candidate) :
    (encC f c).is_means = c.isMeans := rfl

@[simp] theorem encC_repr (f : Nat → String) (c : Formal.ArbiterSelect.Candidate) :
    (encC f c).repr_ = f c.id := rfl

/-- Plan oracle encoding: `Action := Unit`; a goal plans to the one-step plan
`[()]` exactly when the hand `plannable` oracle fires (Python truthiness of
the plan list = the hand Bool). -/
def encPlan (plannable : Nat → Bool) : Nat → List Unit :=
  fun id => if plannable id then [()] else []

/-- Output encoding: the hand `(chosen?, newCommitted?)` as the Python
`(goal?, plan, committed_repr?)` triple. A chosen candidate always carries
the plan `[()]` (the selector only returns plannable candidates). -/
def encOut (f : Nat → String) :
    Option Formal.ArbiterSelect.Candidate × Option Nat →
      Option Nat × List Unit × Option String
  | (some c, n) => (some c.id, [()], n.map f)
  | (none, _) => (none, [], none)

/-- The walk-loop body the extractor emits (the `_findSome` lambda); marked
reducible so `rw` can match it against the generated term. -/
@[reducible] def eWalkBody (f? : Nat → List Unit) (sat sup : Nat → Bool)
    (t : Option String) (cand : Extracted.ArbiterSelect.Candidate Nat) :
    Option (Option Nat × List Unit × Option String) :=
  if decide (t = some cand.repr_) then none
  else if sup cand.goal then none
  else if sat cand.goal then none
  else
    let plan := f? cand.goal
    if decide ((Int.ofNat (List.length plan)) > 0) then
      let new_committed := if cand.is_means then some cand.repr_ else none
      some (some cand.goal, plan, new_committed)
    else none

/-! ## Pointwise transport lemmas (injective `f`) -/

private theorem findIdxFrom_bridge (f : Nat → String)
    (hf : ∀ a b, f a = f b → a = b) (id : Nat) :
    ∀ (cs : List Formal.ArbiterSelect.Candidate) (i : Int),
      Extracted.ArbiterSelect._findIdxFrom
          (fun c => decide (c.repr_ = f id)) i (cs.map (encC f))
        = (indexOf? cs id).map (fun n => i + Int.ofNat n) := by
  intro cs
  induction cs with
  | nil => intro i; rfl
  | cons c rest ih =>
    intro i
    by_cases h : c.id = id
    · have hfe : f c.id = f id := congrArg f h
      have hidx : indexOf? (c :: rest) id = some 0 := by
        rw [← h]; exact Formal.ArbiterSelect.indexOf?_head c rest
      simp [Extracted.ArbiterSelect._findIdxFrom, hfe, hidx]
    · have hne : f c.id ≠ f id := fun hc => h (hf _ _ hc)
      rw [Formal.ArbiterSelect.indexOf?_cons_ne c rest id h]
      simp only [List.map_cons, Extracted.ArbiterSelect._findIdxFrom, encC_repr,
        hne, decide_eq_true_eq, if_false, ih (i + 1)]
      cases hres : indexOf? rest id with
      | none => rfl
      | some k =>
        simp only [Option.map_some, Option.some.injEq, Int.ofNat_eq_natCast]
        omega

/-- The extracted `_precedes` over the encoded list IS the hand `precedes`. -/
private theorem precedes_bridge (f : Nat → String) (hf : ∀ a b, f a = f b → a = b)
    (cs : List Formal.ArbiterSelect.Candidate) (a b : Nat) :
    Extracted.ArbiterSelect._precedes (cs.map (encC f)) (f a) (f b)
      = precedes cs a b := by
  simp only [Extracted.ArbiterSelect._precedes, Extracted.ArbiterSelect._findIdx]
  rw [findIdxFrom_bridge f hf a cs 0, findIdxFrom_bridge f hf b cs 0]
  unfold Formal.ArbiterSelect.precedes
  cases ha : indexOf? cs a with
  | none => rfl
  | some ia =>
    cases hb : indexOf? cs b with
    | none => rfl
    | some ib =>
      simp only [Option.map_some]
      have hiff : ((0 : Int) + Int.ofNat ia < 0 + Int.ofNat ib) ↔ (ia < ib) := by
        simp only [Int.ofNat_eq_natCast]
        omega
      rw [decide_eq_decide.mpr hiff]

/-- The extracted `_find` of the committed predicate commutes with the hand
`findCommitted`. -/
private theorem find_committed_bridge (f : Nat → String)
    (hf : ∀ a b, f a = f b → a = b) (cid : Nat) :
    ∀ cs : List Formal.ArbiterSelect.Candidate,
      Extracted.ArbiterSelect._find
          (fun c => c.is_means && decide (c.repr_ = f cid)) (cs.map (encC f))
        = (findCommitted cs cid).map (encC f) := by
  intro cs
  induction cs with
  | nil => rfl
  | cons c rest ih =>
    unfold Formal.ArbiterSelect.findCommitted at ih ⊢
    by_cases h : c.id = cid
    · cases hm : c.isMeans with
      | true => simp [Extracted.ArbiterSelect._find, hm, h]
      | false => simp [Extracted.ArbiterSelect._find, hm, h, ih]
    · have hne : f c.id ≠ f cid := fun hc => h (hf _ _ hc)
      simp [Extracted.ArbiterSelect._find, h, hne, ih]

/-- The generated guard scan (`any` of `_precedes` over `map repr_ ∘ filter
¬is_means`) IS the hand `guardPrecedes`. -/
private theorem guard_any_aux (f : Nat → String) (hf : ∀ a b, f a = f b → a = b)
    (cs : List Formal.ArbiterSelect.Candidate) (cid : Nat) :
    ∀ gs : List Formal.ArbiterSelect.Candidate,
      List.any
          (List.map (fun c => c.repr_)
            (List.filter (fun c => !c.is_means) (gs.map (encC f))))
          (fun gr => Extracted.ArbiterSelect._precedes (cs.map (encC f)) gr (f cid))
        = (gs.filter (fun c => !c.isMeans)).any (fun g => precedes cs g.id cid) := by
  intro gs
  induction gs with
  | nil => rfl
  | cons g rest ih =>
    cases hm : g.isMeans with
    | true =>
      simp only [List.map_cons, List.filter_cons, encC_is_means, hm,
        Bool.not_true, Bool.false_eq_true, if_false, ih]
    | false =>
      simp only [List.map_cons, List.filter_cons, encC_is_means, hm,
        Bool.not_false, if_true, List.any_cons, ih, encC_repr,
        precedes_bridge f hf cs g.id cid]

private theorem guard_any_bridge (f : Nat → String) (hf : ∀ a b, f a = f b → a = b)
    (cs : List Formal.ArbiterSelect.Candidate) (cid : Nat) :
    List.any
        (List.map (fun c => c.repr_)
          (List.filter (fun c => !c.is_means) (cs.map (encC f))))
        (fun gr => Extracted.ArbiterSelect._precedes (cs.map (encC f)) gr (f cid))
      = guardPrecedes cs cid := by
  unfold Formal.ArbiterSelect.guardPrecedes
  exact guard_any_aux f hf cs cid cs

/-! ## The walk -/

/-- The generated `_findSome` walk equals the hand `walk`, mapped through the
output encoding — for any `t : Option String` whose tried-test agrees with the
hand `tried` pointwise (instantiated below at `none` / `some (f cid)`). -/
private theorem findSome_walk_bridge (f : Nat → String)
    (p sat sup : Nat → Bool) (tried : Option Nat) (t : Option String)
    (hT : ∀ id : Nat, decide (t = some (f id))
        = (match tried with | some u => decide (u = id) | none => false)) :
    ∀ cs : List Formal.ArbiterSelect.Candidate,
      Extracted.ArbiterSelect._findSome
          (eWalkBody (encPlan p) sat sup t) (cs.map (encC f))
        = (walk p sat sup tried cs).map
            (fun c => (some c.id, [()], if c.isMeans then some (f c.id) else none)) := by
  intro cs
  cases tried with
  | none =>
    induction cs with
    | nil => rfl
    | cons c rest ih =>
      have ht : ¬(t = some (f c.id)) := by simpa using hT c.id
      simp only [List.map_cons, Extracted.ArbiterSelect._findSome, eWalkBody,
        encC_repr, encC_goal, encC_is_means, Formal.ArbiterSelect.walk,
        Bool.false_or]
      by_cases hsup : sup c.id = true
      · simpa [ht, hsup] using ih
      · by_cases hsat : sat c.id = true
        · simpa [ht, hsup, hsat] using ih
        · by_cases hp : p c.id = true
          · simp [ht, hsup, hsat, hp, encPlan]
          · simpa [ht, hsup, hsat, hp, encPlan] using ih
  | some u =>
    induction cs with
    | nil => rfl
    | cons c rest ih =>
      have ht : (t = some (f c.id)) ↔ (u = c.id) := by simpa using hT c.id
      simp only [List.map_cons, Extracted.ArbiterSelect._findSome, eWalkBody,
        encC_repr, encC_goal, encC_is_means, Formal.ArbiterSelect.walk]
      by_cases hu : u = c.id
      · simpa [ht, hu] using ih
      · by_cases hsup : sup c.id = true
        · simpa [ht, hu, hsup] using ih
        · by_cases hsat : sat c.id = true
          · simpa [ht, hu, hsup, hsat] using ih
          · by_cases hp : p c.id = true
            · simp [ht, hu, hsup, hsat, hp, encPlan]
            · simpa [ht, hu, hsup, hsat, hp, encPlan] using ih

/-- `hT` instance: no sticky attempt (`t = none`). -/
private theorem hT_none (f : Nat → String) :
    ∀ id : Nat, decide ((none : Option String) = some (f id))
      = (match (none : Option Nat) with
         | some u => decide (u = id) | none => false) := by
  intro id; simp

/-- `hT` instance: the sticky-tried walk (`t = some (f cid)`). -/
private theorem hT_some (f : Nat → String) (hf : ∀ a b, f a = f b → a = b)
    (cid : Nat) :
    ∀ id : Nat, decide ((some (f cid) : Option String) = some (f id))
      = (match (some cid : Option Nat) with
         | some u => decide (u = id) | none => false) := by
  intro id
  simp only [Option.some.injEq]
  by_cases h : cid = id
  · simp [h]
  · have hne : f cid ≠ f id := fun hc => h (hf _ _ hc)
    simp [h, hne]

/-! ## THE BRIDGE -/

/-- BRIDGE: the extracted selector commutes with the hand model through the
candidate/plan/output encodings, for EVERY injective id embedding `f`, every
candidate list (duplicate ids and all), every commitment and every oracle
triple — `extracted ∘ encode = encOut ∘ handModel`. All
`Formal.ArbiterSelect` safety theorems (guard-wins, generalised
any-plannable-guard-wins, sticky idempotence, no-commitment walk order)
transfer. -/
theorem arbiter_select_bridge (f : Nat → String) (hf : ∀ a b, f a = f b → a = b)
    (cs : List Formal.ArbiterSelect.Candidate) (committed : Option Nat)
    (plannable satisfied suppressed : Nat → Bool) :
    Extracted.ArbiterSelect.select_pure
        (cs.map (encC f)) (committed.map f)
        (encPlan plannable) satisfied suppressed
      = encOut f (selectPure cs committed plannable satisfied suppressed) := by
  cases committed with
  | none =>
    simp only [Extracted.ArbiterSelect.select_pure, Option.map_none]
    rw [findSome_walk_bridge f plannable satisfied suppressed none none
      (hT_none f) cs]
    cases hw : walk plannable satisfied suppressed none cs with
    | none =>
      simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
        hw, encOut]
    | some c =>
      cases hm : c.isMeans with
      | true =>
        simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
          hw, hm, encOut]
      | false =>
        simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
          hw, hm, encOut]
  | some cid =>
    simp only [Extracted.ArbiterSelect.select_pure, Option.map_some]
    rw [find_committed_bridge f hf cid cs]
    cases hfc : findCommitted cs cid with
    | none =>
      simp only [Option.map_none]
      rw [findSome_walk_bridge f plannable satisfied suppressed none none
        (hT_none f) cs]
      cases hw : walk plannable satisfied suppressed none cs with
      | none =>
        simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
          hfc, hw, encOut]
      | some c =>
        cases hm : c.isMeans with
        | true =>
          simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
            hfc, hw, hm, encOut]
        | false =>
          simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
            hfc, hw, hm, encOut]
    | some c =>
      obtain ⟨hcm, hcid, _⟩ :=
        Formal.ArbiterSelect.findCommitted_some_props cs cid c hfc
      simp only [Option.map_some, encC_goal]
      rw [guard_any_bridge f hf cs cid]
      rw [findSome_walk_bridge f plannable satisfied suppressed (some cid)
        (some (f cid)) (hT_some f hf cid) cs]
      rw [findSome_walk_bridge f plannable satisfied suppressed none none
        (hT_none f) cs]
      cases hs : satisfied c.id with
      | true =>
        cases hw : walk plannable satisfied suppressed none cs with
        | none =>
          simp [Formal.ArbiterSelect.selectPure, Formal.ArbiterSelect.stickyOutcome,
            hfc, hs, hw, encOut]
        | some c' =>
          cases hm' : c'.isMeans with
          | true =>
            simp [Formal.ArbiterSelect.selectPure,
              Formal.ArbiterSelect.stickyOutcome, hfc, hs, hw, hm', encOut]
          | false =>
            simp [Formal.ArbiterSelect.selectPure,
              Formal.ArbiterSelect.stickyOutcome, hfc, hs, hw, hm', encOut]
      | false =>
        cases hsu : suppressed c.id with
        | true =>
          cases hw : walk plannable satisfied suppressed none cs with
          | none =>
            simp [Formal.ArbiterSelect.selectPure,
              Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hw, encOut]
          | some c' =>
            cases hm' : c'.isMeans with
            | true =>
              simp [Formal.ArbiterSelect.selectPure,
                Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hw, hm', encOut]
            | false =>
              simp [Formal.ArbiterSelect.selectPure,
                Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hw, hm', encOut]
        | false =>
          cases hgp : guardPrecedes cs cid with
          | true =>
            cases hw : walk plannable satisfied suppressed none cs with
            | none =>
              simp [Formal.ArbiterSelect.selectPure,
                Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hw, encOut]
            | some c' =>
              cases hm' : c'.isMeans with
              | true =>
                simp [Formal.ArbiterSelect.selectPure,
                  Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hw,
                  hm', encOut]
              | false =>
                simp [Formal.ArbiterSelect.selectPure,
                  Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hw,
                  hm', encOut]
          | false =>
            cases hp : plannable c.id with
            | true =>
              have hp' : plannable cid = true := hcid ▸ hp
              have hs' : satisfied cid = false := hcid ▸ hs
              have hsu' : suppressed cid = false := hcid ▸ hsu
              simp [Formal.ArbiterSelect.selectPure,
                Formal.ArbiterSelect.stickyOutcome, hfc, hgp,
                hp', hs', hsu', encOut, encPlan, hcid]
            | false =>
              cases hw : walk plannable satisfied suppressed (some cid) cs with
              | none =>
                simp [Formal.ArbiterSelect.selectPure,
                  Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hp, hw,
                  encOut, encPlan]
              | some c' =>
                cases hm' : c'.isMeans with
                | true =>
                  simp [Formal.ArbiterSelect.selectPure,
                    Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hp,
                    hw, hm', encOut, encPlan]
                | false =>
                  simp [Formal.ArbiterSelect.selectPure,
                    Formal.ArbiterSelect.stickyOutcome, hfc, hs, hsu, hgp, hp,
                    hw, hm', encOut, encPlan]

/-! ## Transferred safety theorem -/

/-- THE sticky-safety theorem, restated on the EXTRACTED definition: under
id-disjointness, a plannable / non-satisfied / non-suppressed HEAD guard wins
regardless of commitment — through every encoding. -/
theorem select_pure_guard_wins_extracted (f : Nat → String)
    (hf : ∀ a b, f a = f b → a = b)
    (g : Formal.ArbiterSelect.Candidate) (rest : List Formal.ArbiterSelect.Candidate)
    (committed : Option Nat) (plannable satisfied suppressed : Nat → Bool)
    (hguard : g.isMeans = false)
    (hplan : plannable g.id = true)
    (hnsat : satisfied g.id = false)
    (hnsup : suppressed g.id = false)
    (hdisj : Formal.ArbiterSelect.idsDisjoint (g :: rest)) :
    (Extracted.ArbiterSelect.select_pure
        ((g :: rest).map (encC f)) (committed.map f)
        (encPlan plannable) satisfied suppressed).1 = some g.id := by
  rw [arbiter_select_bridge f hf]
  have h := Formal.ArbiterSelect.select_pure_guard_wins g rest committed
    plannable satisfied suppressed hguard hplan hnsat hnsup hdisj
  rcases hsel : selectPure (g :: rest) committed plannable satisfied suppressed
    with ⟨c?, n⟩
  rw [hsel] at h
  simp only at h
  subst h
  rfl

end Extracted.Bridges
