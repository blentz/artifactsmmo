-- @concept: crafting, planner @property: safety, totality
/-
Role theorems for `skill_grind_selection_pure` (the recipe-aware skill-grind
target selector). Proved DIRECTLY on the extracted def (String-keyed in both
Python and Lean — no encoding bridge needed).

THE CONTRACT (why this exists): the live bot, committed to weaponcrafting, ground
gearcrafting because `skill_grind_target` picked an UNOBTAINABLE weaponcrafting
item whose GatherMaterials GOAP-failed, and the arbiter fell cross-skill. The
selector now considers ONLY same-skill, in-level, obtainable candidates. These
theorems prove the selected code (when non-empty) ALWAYS belongs to a candidate
that is same-skill ∧ in-level ∧ obtainable — the cross-skill outcome is
unrepresentable at the selection layer. `actionable` ties non-empty result to the
existence of a feasible candidate.

Core only — no mathlib. Fold induction.
-/
import Formal.Extracted.SkillGrindSelection

namespace Formal.SkillGrindSelection

open Extracted.SkillGrindSelection

/-- A candidate is FEASIBLE for `skill` at `level`: same craft skill, in level,
obtainable. (The extracted fold's `continue` guard is exactly its negation.) -/
def feasible (skill : String) (level : Int) (c : GrindCandidate) : Prop :=
  c.craft_skill = skill ∧ c.craft_level ≤ level ∧ c.obtainable = true

/-- The fold step used by `skill_grind_selection_pure` (matches the extracted
inline lambda). -/
def step (skill : String) (level : Int)
    (best : Option GrindCandidate) (c : GrindCandidate) : Option GrindCandidate :=
  if ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level)) || (!c.obtainable))
  then best
  else (if _beats c best then some c else best)

/-- The extracted selector's fold IS `List.foldl (step ...) none`. -/
theorem unfold_select (skill : String) (level : Int) (cands : List GrindCandidate) :
    skill_grind_selection_pure skill level cands
      = (match List.foldl (step skill level) none cands with
         | some c => c.code
         | none => "") := by
  unfold skill_grind_selection_pure step
  rfl

/-- When the guard is FALSE (the else-branch of `step` fires), the candidate is
feasible. -/
theorem guard_false_feasible (skill : String) (level : Int) (c : GrindCandidate)
    (hg : ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level))
            || (!c.obtainable)) = false) :
    feasible skill level c := by
  simp only [Bool.or_eq_false_iff, Bool.not_eq_eq_eq_not, Bool.not_false,
    decide_eq_true_eq, decide_eq_false_iff_not] at hg
  obtain ⟨⟨hskill, hlevel⟩, hobt⟩ := hg
  refine ⟨hskill, ?_, hobt⟩
  omega

/-- Structural characterization of `step`: its result is either the incoming
`best`, or `some d` with `d` feasible. -/
theorem step_cases (skill : String) (level : Int)
    (best : Option GrindCandidate) (d : GrindCandidate) :
    step skill level best d = best
      ∨ (step skill level best d = some d ∧ feasible skill level d) := by
  unfold step
  by_cases hg : ((!(decide (d.craft_skill = skill))) || (decide (d.craft_level > level))
            || (!d.obtainable)) = true
  · rw [if_pos hg]; exact Or.inl rfl
  · rw [Bool.not_eq_true] at hg
    rw [if_neg (by rw [hg]; simp)]
    have hfeas := guard_false_feasible skill level d hg
    by_cases hb : _beats d best = true
    · rw [if_pos hb]; exact Or.inr ⟨rfl, hfeas⟩
    · rw [Bool.not_eq_true] at hb
      rw [if_neg (by rw [hb]; simp)]; exact Or.inl rfl

/-- FOLD INVARIANT: if the fold (from a feasible-or-none init) returns `some c`,
then `c` is feasible and a member of the processed list (or the init). -/
theorem fold_some_feasible (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∀ d, init = some d → feasible skill level d) →
      ∀ c, List.foldl (step skill level) init cands = some c →
        feasible skill level c ∧ (c ∈ cands ∨ init = some c) := by
  intro cands
  induction cands with
  | nil =>
    intro init hinit c h
    simp only [List.foldl_nil] at h
    exact ⟨hinit c h, Or.inr h⟩
  | cons d rest ih =>
    intro init hinit c h
    simp only [List.foldl_cons] at h
    -- acc is feasible-or-none: either it's `init` (feasible by hinit) or `some d`
    -- with d feasible (the else-branch only fires when d passes the guard).
    have hacc_inv : ∀ e, step skill level init d = some e → feasible skill level e := by
      intro e he
      rcases step_cases skill level init d with hstep | ⟨hstep, hfeas⟩
      · rw [hstep] at he; exact hinit e he
      · rw [hstep] at he; rw [Option.some.injEq] at he; exact he ▸ hfeas
    have hres := ih (step skill level init d) hacc_inv c h
    refine ⟨hres.1, ?_⟩
    rcases hres.2 with hmem | hinit_acc
    · exact Or.inl (List.mem_cons_of_mem _ hmem)
    · -- c came from acc = step init d; so c = d (∈ cons) or acc = init (Or.inr)
      rcases step_cases skill level init d with hstep | ⟨hstep, _⟩
      · rw [hstep] at hinit_acc; exact Or.inr hinit_acc
      · rw [hstep] at hinit_acc; rw [Option.some.injEq] at hinit_acc
        exact Or.inl (hinit_acc ▸ List.mem_cons_self)

/-- THE ROLE LEMMA: a non-empty selected code belongs to a feasible candidate. -/
theorem result_feasible (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ feasible skill level c := by
  rw [unfold_select] at h ⊢
  cases hfold : List.foldl (step skill level) none cands with
  | none => simp [hfold] at h
  | some c =>
    have hfeas := fold_some_feasible skill level cands none (by simp) c hfold
    have hmem : c ∈ cands := by
      rcases hfeas.2 with hm | hcontra
      · exact hm
      · simp at hcontra
    exact ⟨c, hmem, rfl, hfeas.1⟩

/-- `grind_same_skill`: the selected code (when non-empty) is a candidate whose
craft_skill is the committed skill. NO cross-skill selection, ever. -/
theorem grind_same_skill (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.craft_skill = skill := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.1⟩

/-- `grind_in_level`: the selected candidate is craftable at the current level. -/
theorem grind_in_level (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.craft_level ≤ level := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.2.1⟩

/-- `grind_obtainable`: the selected candidate is obtainable (recipe reachable). -/
theorem grind_obtainable (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.obtainable = true := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.2.2⟩

/-- `step` never maps `some → none`: once the accumulator is `some`, it stays
`some` after one step. -/
theorem step_preserves_some (skill : String) (level : Int)
    (best : Option GrindCandidate) (d : GrindCandidate)
    (hb : ∃ b, best = some b) :
    ∃ b, step skill level best d = some b := by
  rcases step_cases skill level best d with hstep | ⟨hstep, _⟩
  · rw [hstep]; exact hb
  · exact ⟨d, hstep⟩

/-- A `some` accumulator is preserved across the whole fold. -/
theorem fold_preserves_some (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∃ b, init = some b) →
      ∃ b, List.foldl (step skill level) init cands = some b := by
  intro cands
  induction cands with
  | nil => intro init hb; simpa using hb
  | cons d rest ih =>
    intro init hb
    simp only [List.foldl_cons]
    exact ih (step skill level init d) (step_preserves_some skill level init d hb)

/-- Stepping a feasible candidate from ANY accumulator yields `some _`: if the
incoming `best` is already `some`, it is preserved; if it is `none`, then
`_beats c none = true` and the else-branch produces `some c`. -/
theorem step_feasible_some (skill : String) (level : Int)
    (best : Option GrindCandidate) (c : GrindCandidate) (hf : feasible skill level c) :
    ∃ b, step skill level best c = some b := by
  rcases step_cases skill level best c with hstep | ⟨hstep, _⟩
  · -- step returned `best`; show `best` is itself `some`
    rw [hstep]
    cases hbest : best with
    | some b => exact ⟨b, rfl⟩
    | none =>
      -- guard is false (c feasible), so step = (if _beats c none then some c else none);
      -- _beats c none = true, hence step = some c ≠ none = best, contradiction
      exfalso
      obtain ⟨hskill, hlevel, hobt⟩ := hf
      have hguard : ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level))
          || (!c.obtainable)) = false := by
        simp only [Bool.or_eq_false_iff, Bool.not_eq_eq_eq_not, Bool.not_false,
          decide_eq_true_eq, decide_eq_false_iff_not, hskill, hobt,
          and_true, true_and]
        omega
      have : step skill level none c = some c := by
        unfold step _beats
        rw [if_neg (by rw [hguard]; simp)]
        simp
      rw [hbest, this] at hstep
      exact absurd hstep (by simp)
  · exact ⟨c, hstep⟩

/-- FOLD REACHES SOME: a fold over a list that contains a feasible member, from
`none`, yields `some _`. The first feasible candidate flips `none → some`, and
`some` is preserved thereafter. -/
theorem fold_reaches_some (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∃ c, c ∈ cands ∧ feasible skill level c) ∨ (∃ b, init = some b) →
      ∃ b, List.foldl (step skill level) init cands = some b := by
  intro cands
  induction cands with
  | nil =>
    intro init h
    rcases h with ⟨c, hc, _⟩ | hb
    · exact absurd hc (List.not_mem_nil)
    · simpa using hb
  | cons d rest ih =>
    intro init h
    simp only [List.foldl_cons]
    rcases h with ⟨c, hc, hcf⟩ | hb
    · rcases List.mem_cons.mp hc with hcd | hcrest
      · -- the feasible member is the head: after stepping it, accumulator is `some`
        subst hcd
        exact ih (step skill level init c) (Or.inr (step_feasible_some skill level init c hcf))
      · exact ih (step skill level init d) (Or.inl ⟨c, hcrest, hcf⟩)
    · exact ih (step skill level init d)
        (Or.inr (step_preserves_some skill level init d hb))

/-- `grind_actionable` (one direction — the load-bearing one): a feasible
candidate with a non-empty code forces a non-empty result. (The selector never
returns "" while an actionable in-skill craft exists.) -/
theorem grind_actionable (skill : String) (level : Int) (cands : List GrindCandidate)
    (c : GrindCandidate) (hmem : c ∈ cands) (hf : feasible skill level c)
    (hne : ∀ d ∈ cands, d.code ≠ "") :
    skill_grind_selection_pure skill level cands ≠ "" := by
  rw [unfold_select]
  obtain ⟨b, hb⟩ := fold_reaches_some skill level cands none (Or.inl ⟨c, hmem, hf⟩)
  rw [hb]
  -- b ∈ cands (feasible-or-none init with none ⇒ membership), so b.code ≠ ""
  have hfeas := fold_some_feasible skill level cands none (by simp) b hb
  have hbmem : b ∈ cands := by
    rcases hfeas.2 with hm | hcontra
    · exact hm
    · simp at hcontra
  exact hne b hbmem

/-- `beats_prefers_wanted`: a WANTED candidate strictly beats a non-wanted
incumbent — the wanted-first primary key (an objective gear/tool target outranks
a throwaway regardless of its material count or craft level). -/
theorem beats_prefers_wanted (c b : GrindCandidate)
    (hc : c.wanted = true) (hb : b.wanted = false) :
    _beats c (some b) = true := by
  simp [_beats, hc, hb]

/-- `unwanted_not_beats_wanted`: a non-wanted candidate NEVER displaces a wanted
incumbent — even with fewer missing materials or a higher craft level. -/
theorem unwanted_not_beats_wanted (c b : GrindCandidate)
    (hc : c.wanted = false) (hb : b.wanted = true) :
    _beats c (some b) = false := by
  simp [_beats, hc, hb]

end Formal.SkillGrindSelection
