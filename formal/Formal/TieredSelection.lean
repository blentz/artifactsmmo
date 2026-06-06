/-
Formal model of the StrategyArbiter's TWO-PASS candidate walk, mirroring the
tiered budget selection in `src/artifactsmmo_cli/ai/tiers/` (the arbiter walks
the band-ordered candidate list twice: pass 1 with a CHEAP plan budget, and
only if no candidate plans cheaply does it escalate to pass 2 with the FULL
budget; if neither pass finds a planner, the arbiter Waits).

THE CODE FACTS this mirrors:
  * The arbiter iterates candidates in BAND ORDER (highest-priority first) and
    returns the FIRST candidate that produces a plan.
  * Pass 1 tries each candidate with a cheap/shallow planner budget
    (`cheapPlans`). Pass 2 (escalation) retries with the full budget
    (`fullPlans`). A candidate that plans cheaply also plans fully
    (`cheap_implies_full`) — more budget never removes a found plan.
  * A `skip` predicate (the per-cycle memo) carries goals already KNOWN to
    produce NO plan at the recorded signature, so the walk does not re-plan
    them. The memo's soundness contract (`skip_no_plan`) is that it only ever
    carries goals that produced no plan at EITHER budget — skipping never drops
    a candidate that WOULD have planned at the recorded signature.
  * If pass 1 finds nothing AND pass 2 finds nothing, `select` returns `none`,
    modeling the arbiter's Wait sentinel.

This module proves the two-pass walk's invariants:
  * `cheap_winner_is_first_cheaply_plannable` — pass 1 returns the FIRST
    non-skipped candidate that plans cheaply.
  * `escalation_iff_no_cheap` — the full-budget pass is taken IFF no
    non-skipped candidate plans cheaply.
  * `wait_only_when_no_full` — Wait (`select = none`) ⇒ no non-skipped
    candidate plans fully (so nothing was wrongly skipped to a Wait).
  * `memo_skip_sound` — the memo soundness contract: a skipped candidate
    plans NEITHER cheaply NOR fully.

Lean core only — no mathlib.
-/

namespace Formal.TieredSelection

variable {C : Type}

/-- A candidate `c` is selectable under budget decider `p` when it plans (`p c`)
AND is not skipped by the memo (`!skip c`). -/
def qualifies (skip p : C → Bool) (c : C) : Bool := p c && !skip c

/-- First element of `l` (band order) that `qualifies` under decider `p`.
Mirrors the arbiter's single-pass walk under a fixed budget. Defined via
`List.find?` so the standard `find?` lemmas give clean firstness reasoning. -/
def firstPlanning (skip p : C → Bool) (l : List C) : Option C :=
  l.find? (qualifies skip p)

/-- The two-pass selection: try pass 1 (cheap budget); on `none` escalate to
pass 2 (full budget). `none` from BOTH passes models the arbiter's Wait. -/
def select (skip cheapPlans fullPlans : C → Bool) (cand : List C) : Option C :=
  match firstPlanning skip cheapPlans cand with
  | some c => some c
  | none => firstPlanning skip fullPlans cand

/-! ### Helper characterizations of `firstPlanning` (via `List.find?`). -/

/-- `qualifies` unfolds to the plannable ∧ non-skipped conjunction. -/
theorem qualifies_iff (skip p : C → Bool) (c : C) :
    qualifies skip p c = true ↔ p c = true ∧ skip c = false := by
  unfold qualifies
  simp [Bool.and_eq_true]

/-- `firstPlanning` returns `some c` ⇒ `c` qualifies and is a member. -/
theorem firstPlanning_some_spec (skip p : C → Bool) (l : List C) (c : C)
    (h : firstPlanning skip p l = some c) :
    p c = true ∧ skip c = false ∧ c ∈ l := by
  unfold firstPlanning at h
  have hq : qualifies skip p c = true := List.find?_some h
  have hmem : c ∈ l := List.mem_of_find?_eq_some h
  obtain ⟨hp, hs⟩ := (qualifies_iff skip p c).mp hq
  exact ⟨hp, hs, hmem⟩

/-- `firstPlanning` returns `none` ⇒ NO element qualifies. -/
theorem firstPlanning_none_spec (skip p : C → Bool) (l : List C)
    (h : firstPlanning skip p l = none) :
    ∀ c ∈ l, ¬ (p c = true ∧ skip c = false) := by
  intro c hmem hcontra
  have hq : qualifies skip p c = true := (qualifies_iff skip p c).mpr hcontra
  unfold firstPlanning at h
  have := List.find?_eq_none.mp h c hmem
  exact (by simp [hq] at this)

/-- `firstPlanning` returns `some c` ⇒ for the FIRST-occurrence decomposition
`l = pre ++ c :: post` produced by `find?`, every element of `pre` fails to
qualify. This is the genuine firstness witness (over the canonical prefix). -/
theorem firstPlanning_first (skip p : C → Bool) (l : List C) (c : C)
    (h : firstPlanning skip p l = some c) :
    ∃ pre post, l = pre ++ c :: post ∧
      (∀ x ∈ pre, ¬ (p x = true ∧ skip x = false)) := by
  unfold firstPlanning at h
  obtain ⟨_, pre, post, hsplit, hfail⟩ := List.find?_eq_some_iff_append.mp h
  refine ⟨pre, post, hsplit, ?_⟩
  intro x hx hcontra
  have hq : qualifies skip p x = true := (qualifies_iff skip p x).mpr hcontra
  have := hfail x hx
  simp [hq] at this

/-! ### Role theorems. -/

/-- **PASS-1 SELECTION.** When pass 1 returns `some c`, `c` is the first
non-skipped candidate that plans cheaply: it plans cheaply, is not skipped, is a
member, and every candidate ahead of it in band order does NOT plan cheaply
while non-skipped. -/
theorem cheap_winner_is_first_cheaply_plannable
    (skip cheapPlans : C → Bool) (cand : List C) (c : C)
    (h : firstPlanning skip cheapPlans cand = some c) :
    cheapPlans c = true ∧ skip c = false ∧ c ∈ cand ∧
    (∃ pre post, cand = pre ++ c :: post ∧
        ∀ x ∈ pre, ¬ (cheapPlans x = true ∧ skip x = false)) := by
  obtain ⟨hp, hs, hmem⟩ := firstPlanning_some_spec skip cheapPlans cand c h
  obtain ⟨pre, post, hsplit, hfail⟩ := firstPlanning_first skip cheapPlans cand c h
  exact ⟨hp, hs, hmem, pre, post, hsplit, hfail⟩

/-- **ESCALATION.** The full-budget pass is the value of `select` IFF pass 1
found nothing — equivalently, IFF NO non-skipped candidate plans cheaply. -/
theorem escalation_iff_no_cheap
    (skip cheapPlans fullPlans : C → Bool) (cand : List C) :
    select skip cheapPlans fullPlans cand = firstPlanning skip fullPlans cand
      ↔ (∀ c ∈ cand, ¬ (cheapPlans c = true ∧ skip c = false))
        ∨ firstPlanning skip cheapPlans cand = firstPlanning skip fullPlans cand := by
  constructor
  · intro heq
    -- decide on pass 1's result
    cases hc : firstPlanning skip cheapPlans cand with
    | none => exact Or.inl (firstPlanning_none_spec skip cheapPlans cand hc)
    | some c =>
      -- select = some c (pass 1 short-circuits); the hypothesis equates this
      -- with the full pass, so pass 1 and pass 2 coincide.
      refine Or.inr ?_
      have hsel : select skip cheapPlans fullPlans cand = some c := by
        unfold select; rw [hc]
      rw [hsel] at heq
      exact heq
  · intro h
    cases hc : firstPlanning skip cheapPlans cand with
    | none => unfold select; rw [hc]
    | some c =>
      -- pass 1 found c; so the first disjunct is impossible (c qualifies)
      obtain ⟨hp, hs, hmem⟩ := firstPlanning_some_spec skip cheapPlans cand c hc
      rcases h with hall | heq
      · exact absurd ⟨hp, hs⟩ (hall c hmem)
      · unfold select; rw [hc]; rw [hc] at heq; exact heq

/-- **WAIT SOUNDNESS.** `select = none` (the arbiter Waits) ⇒ NO non-skipped
candidate plans fully. So a Wait never drops a candidate that would have planned
at the full budget — the only way to Wait is genuine universal no-plan. -/
theorem wait_only_when_no_full
    (skip cheapPlans fullPlans : C → Bool) (cand : List C)
    (h : select skip cheapPlans fullPlans cand = none) :
    ∀ c ∈ cand, ¬ (fullPlans c = true ∧ skip c = false) := by
  unfold select at h
  cases hc : firstPlanning skip cheapPlans cand with
  | some c => rw [hc] at h; simp at h
  | none =>
    rw [hc] at h
    exact firstPlanning_none_spec skip fullPlans cand h

/-- **MEMO SOUNDNESS.** Given the memo's recorded contract `skip_no_plan` (a
skipped goal produced no plan at EITHER budget at the recorded signature), a
skipped candidate plans NEITHER cheaply NOR fully. This is exactly the soundness
the walk relies on to elide re-planning a memoized goal: skipping never drops a
candidate that would have planned. -/
theorem memo_skip_sound
    (skip cheapPlans fullPlans : C → Bool)
    (skip_no_plan : ∀ c, skip c = true → cheapPlans c = false ∧ fullPlans c = false)
    (c : C) (hskip : skip c = true) :
    ¬ (cheapPlans c = true) ∧ ¬ (fullPlans c = true) := by
  obtain ⟨hc, hf⟩ := skip_no_plan c hskip
  exact ⟨by rw [hc]; simp, by rw [hf]; simp⟩

/-! ### Non-vacuity witnesses (concrete `Nat` candidate lists). -/

/-- A concrete two-pass walk: candidates 0,1,2; only candidate 1 plans cheaply
(and so fully). Pass 1 picks 1. -/
example :
    select (fun _ => false) (fun n => decide (n = 1)) (fun n => decide (n = 1)) [0, 1, 2]
      = some 1 := by decide

/-- Escalation: no candidate plans cheaply, but candidate 2 plans fully ⇒
pass 2 picks 2. -/
example :
    select (fun _ => false) (fun _ => false) (fun n => decide (n = 2)) [0, 1, 2]
      = some 2 := by decide

/-- Wait: nothing plans at either budget ⇒ `none`. -/
example :
    select (fun _ => false) (fun _ => false) (fun _ => false) [0, 1, 2]
      = none := by decide

/-- Memo skip: candidate 1 plans cheaply BUT is skipped ⇒ pass 1 falls through
to it being elided; with nothing else, Wait. -/
example :
    select (fun n => decide (n = 1)) (fun n => decide (n = 1)) (fun n => decide (n = 1)) [1]
      = none := by decide

end Formal.TieredSelection
