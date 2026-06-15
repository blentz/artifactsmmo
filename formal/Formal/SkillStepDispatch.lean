-- @concept: crafting, planner @property: safety, liveness
/-
Role theorems for the skill-step dispatch decision (`skill_step_dispatch_pure`).

The Python core filters the in-skill grind candidates by two reserved sets
(FULL, then RELAXED — relaxed frees skill-gated objective materials), runs the
PROVED `skill_grind_selection_pure` over each, and combines the two picks with
the extracted `combine_dispatch_pure` (suppress / grind / no_grind).

This module models that exact pipeline as `dispatch` (hand-written so it can
carry the per-candidate reserved flags the extractor cannot type cross-module),
composing the extracted `combine_dispatch_pure` and the proved selection. The
load-bearing theorems:

* `suppress_correct`  — SUPPRESS iff the committed item is same-skill craftable now.
* `full_preference`   — when the FULL pass picks, that pick is the result and it
                        respects the full reservation (anti-cannibalization).
* `forward_progress`  — a feasible RELAXED candidate is NEVER starved into the
                        dead NO_GRIND fallback (the trace-192617 anti-deadlock).
* `reservation_safety`— a FULL-pass grind code is a candidate with
                        `uses_reserved_full = false` (never eats reserved mats).
* `grind_valid`       — a grind code is a same-skill, in-level, obtainable candidate.

Core only — no mathlib. Builds on Formal.SkillGrindSelection's fold lemmas.
-/
import Formal.Extracted.SkillStepDispatch
import Formal.SkillGrindSelection

namespace Formal.SkillStepDispatch

open Extracted.SkillStepDispatch
open Extracted.SkillGrindSelection
open Formal.SkillGrindSelection

/-- A dispatch candidate: the `GrindCandidate` selection fields plus the two
hoisted reserved-set membership flags. -/
structure DC where
  code : String
  craft_skill : String
  craft_level : Int
  mats_missing : Int
  obtainable : Bool
  uses_reserved_full : Bool
  uses_reserved_relaxed : Bool

/-- Project a `DC` to the selection's `GrindCandidate` (drops the reserved flags;
preserves every field the selection reads). -/
def toGrind (c : DC) : GrindCandidate :=
  { code := c.code, craft_skill := c.craft_skill, craft_level := c.craft_level,
    mats_missing := c.mats_missing, obtainable := c.obtainable }

/-- The FULL-reservation candidate list: drop any candidate that uses a
full-reserved material, project to GrindCandidate. -/
def fullList (cands : List DC) : List GrindCandidate :=
  (cands.filter (fun c => !c.uses_reserved_full)).map toGrind

/-- The RELAXED candidate list: drop any candidate that uses a relaxed-reserved
material (relaxed ⊆ full, so this list ⊇ fullList). -/
def relaxedList (cands : List DC) : List GrindCandidate :=
  (cands.filter (fun c => !c.uses_reserved_relaxed)).map toGrind

/-- The full model of `skill_step_dispatch_pure`: filter → select → select →
combine. (The Python wrapper short-circuits the relaxed selection when the full
pick is non-empty; `combine_dispatch_pure` ignores `relaxed_pick` in exactly
that case, so this eager form computes the same decision.) -/
def dispatch (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) : String × String :=
  combine_dispatch_pure skill cl cs clv
    (skill_grind_selection_pure skill cl (fullList cands))
    (skill_grind_selection_pure skill cl (relaxedList cands))

/-- `DC`-level feasibility: its `toGrind` projection is feasible for selection. -/
def feasibleDC (skill : String) (level : Int) (c : DC) : Prop :=
  feasible skill level (toGrind c)

/-! ## Combine-core lemmas (over arbitrary pick strings). -/

/-- The suppress condition is false exactly when the committed item is not
same-skill-craftable-now. -/
theorem suppress_cond_false (cs skill : String) (clv cl : Int)
    (hns : ¬ (cs = skill ∧ clv ≤ cl)) :
    (decide (cs = skill) && decide (clv ≤ cl)) = false := by
  by_cases h1 : cs = skill
  · by_cases h2 : clv ≤ cl
    · exact absurd ⟨h1, h2⟩ hns
    · simp [h2]
  · simp [h1]

/-- The suppress guard reduces by the helper. -/
theorem combine_not_suppressed (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) (hns : ¬ (cs = skill ∧ clv ≤ cl)) :
    combine_dispatch_pure skill cl cs clv fp rp
      = (if fp ≠ "" then ("grind", fp)
         else if rp ≠ "" then ("grind", rp) else ("no_grind", "")) := by
  unfold combine_dispatch_pure
  rw [if_neg (by rw [suppress_cond_false cs skill clv cl hns]; simp)]
  by_cases hf : fp = ""
  · subst hf; simp
  · simp [hf]

/-- SUPPRESS iff the committed item is same-skill and craftable now. -/
theorem combine_suppress_iff (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) :
    (combine_dispatch_pure skill cl cs clv fp rp).1 = "suppress"
      ↔ (cs = skill ∧ clv ≤ cl) := by
  by_cases h : cs = skill ∧ clv ≤ cl
  · unfold combine_dispatch_pure
    rw [if_pos (by simp [h.1, h.2])]; simp [h]
  · rw [combine_not_suppressed skill cl cs clv fp rp h]
    constructor
    · intro hsup; exfalso
      by_cases hf : fp = ""
      · subst hf
        by_cases hr : rp = ""
        · subst hr; simp at hsup
        · simp [hr] at hsup
      · simp [hf] at hsup
    · intro hc; exact absurd hc h

/-- When NOT suppressed and at least one pass picked, the decision is "grind". -/
theorem combine_grind_of_pick (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) (hns : ¬ (cs = skill ∧ clv ≤ cl)) (hpick : fp ≠ "" ∨ rp ≠ "") :
    (combine_dispatch_pure skill cl cs clv fp rp).1 = "grind" := by
  rw [combine_not_suppressed skill cl cs clv fp rp hns]
  by_cases hf : fp = ""
  · subst hf
    have hrp : rp ≠ "" := by
      rcases hpick with h | h
      · exact absurd rfl h
      · exact h
    simp [hrp]
  · simp [hf]

/-- When NOT suppressed and the FULL pass picked, the result IS that full pick. -/
theorem combine_full_pick (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) (hns : ¬ (cs = skill ∧ clv ≤ cl)) (hfp : fp ≠ "") :
    combine_dispatch_pure skill cl cs clv fp rp = ("grind", fp) := by
  rw [combine_not_suppressed skill cl cs clv fp rp hns]; simp [hfp]

/-- NOT suppressed, full empty, relaxed picks ⇒ result is that relaxed pick. -/
theorem combine_relaxed_pick (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) (hns : ¬ (cs = skill ∧ clv ≤ cl)) (hfp : fp = "") (hrp : rp ≠ "") :
    combine_dispatch_pure skill cl cs clv fp rp = ("grind", rp) := by
  rw [combine_not_suppressed skill cl cs clv fp rp hns]; subst hfp; simp [hrp]

/-- NOT suppressed, both passes empty ⇒ NO_GRIND. -/
theorem combine_no_grind (skill : String) (cl : Int) (cs : String) (clv : Int)
    (fp rp : String) (hns : ¬ (cs = skill ∧ clv ≤ cl)) (hfp : fp = "") (hrp : rp = "") :
    combine_dispatch_pure skill cl cs clv fp rp = ("no_grind", "") := by
  rw [combine_not_suppressed skill cl cs clv fp rp hns]; subst hfp; subst hrp; simp

/-! ## Membership through filter+map (reservation bookkeeping). -/

/-- A member of `fullList` comes from a `DC` in `cands` with the full flag false,
sharing its code and feasibility. -/
theorem mem_fullList (cands : List DC) (g : GrindCandidate) (hg : g ∈ fullList cands) :
    ∃ c, c ∈ cands ∧ c.uses_reserved_full = false ∧ toGrind c = g := by
  unfold fullList at hg
  rw [List.mem_map] at hg
  obtain ⟨c, hcf, hcg⟩ := hg
  rw [List.mem_filter] at hcf
  refine ⟨c, hcf.1, ?_, hcg⟩
  have := hcf.2
  simpa using this

/-- A `DC` with the relaxed flag false projects into `relaxedList`. -/
theorem toGrind_mem_relaxedList (cands : List DC) (c : DC) (hc : c ∈ cands)
    (hr : c.uses_reserved_relaxed = false) : toGrind c ∈ relaxedList cands := by
  unfold relaxedList
  rw [List.mem_map]
  exact ⟨c, by rw [List.mem_filter]; exact ⟨hc, by simp [hr]⟩, rfl⟩

@[simp] theorem toGrind_code (c : DC) : (toGrind c).code = c.code := rfl

/-- A member of `relaxedList` comes from a `DC` in `cands`, sharing its code. -/
theorem mem_relaxedList (cands : List DC) (g : GrindCandidate)
    (hg : g ∈ relaxedList cands) : ∃ c, c ∈ cands ∧ toGrind c = g := by
  unfold relaxedList at hg
  rw [List.mem_map] at hg
  obtain ⟨c, hcf, hcg⟩ := hg
  rw [List.mem_filter] at hcf
  exact ⟨c, hcf.1, hcg⟩

/-! ## Role theorems on `dispatch`. -/

/-- `suppress_correct`: `dispatch` suppresses iff the committed item is same-skill
craftable now. -/
theorem suppress_correct (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) :
    (dispatch skill cl cs clv cands).1 = "suppress" ↔ (cs = skill ∧ clv ≤ cl) := by
  unfold dispatch
  exact combine_suppress_iff _ _ _ _ _ _

/-- `full_preference`: when NOT suppressed and the FULL pass picks something, the
result is exactly that full pick (the relaxed pass is not consulted). -/
theorem full_preference (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (hns : ¬ (cs = skill ∧ clv ≤ cl))
    (hfp : skill_grind_selection_pure skill cl (fullList cands) ≠ "") :
    dispatch skill cl cs clv cands
      = ("grind", skill_grind_selection_pure skill cl (fullList cands)) := by
  unfold dispatch
  exact combine_full_pick _ _ _ _ _ _ hns hfp

/-- `reservation_safety`: a FULL-pass grind code belongs to a candidate whose
`uses_reserved_full` flag is false — the grind never consumes a fully-reserved
objective material. -/
theorem reservation_safety (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (hns : ¬ (cs = skill ∧ clv ≤ cl))
    (hfp : skill_grind_selection_pure skill cl (fullList cands) ≠ "") :
    ∃ c, c ∈ cands ∧ c.uses_reserved_full = false
      ∧ c.code = (dispatch skill cl cs clv cands).2 := by
  obtain ⟨g, hgmem, hgcode, _⟩ := result_feasible skill cl (fullList cands) hfp
  obtain ⟨c, hcmem, hcflag, hcg⟩ := mem_fullList cands g hgmem
  refine ⟨c, hcmem, hcflag, ?_⟩
  rw [full_preference skill cl cs clv cands hns hfp]
  -- (dispatch ...).2 = the full pick; c.code = (toGrind c).code = g.code = pick
  have hcode : c.code = g.code := by rw [← hcg, toGrind_code]
  rw [hcode, hgcode]

/-- `forward_progress` (anti-deadlock): NOT suppressed plus a feasible RELAXED
candidate (with non-empty codes everywhere in the relaxed list) forces a
"grind" decision — the dispatch never falls to NO_GRIND while a level-appropriate
relaxed grind exists. -/
theorem forward_progress (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (hns : ¬ (cs = skill ∧ clv ≤ cl))
    (c : DC) (hcmem : c ∈ cands) (hcrelaxed : c.uses_reserved_relaxed = false)
    (hcfeas : feasibleDC skill cl c)
    (hne : ∀ d ∈ relaxedList cands, d.code ≠ "") :
    (dispatch skill cl cs clv cands).1 = "grind" := by
  unfold dispatch
  have hmem : toGrind c ∈ relaxedList cands :=
    toGrind_mem_relaxedList cands c hcmem hcrelaxed
  have hrp : skill_grind_selection_pure skill cl (relaxedList cands) ≠ "" :=
    grind_actionable skill cl (relaxedList cands) (toGrind c) hmem hcfeas hne
  exact combine_grind_of_pick _ _ _ _ _ _ hns (Or.inr hrp)

/-- `grind_valid`: a "grind" decision's code is a same-skill, in-level,
obtainable candidate (from whichever pass produced it). -/
theorem grind_valid (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (hg : (dispatch skill cl cs clv cands).1 = "grind") :
    ∃ c, c ∈ cands ∧ c.code = (dispatch skill cl cs clv cands).2
      ∧ feasibleDC skill cl c := by
  have hns : ¬ (cs = skill ∧ clv ≤ cl) := by
    intro hc
    rw [(suppress_correct skill cl cs clv cands).mpr hc] at hg
    exact absurd hg (by decide)
  by_cases hfp : skill_grind_selection_pure skill cl (fullList cands) = ""
  · -- full empty ⇒ result from relaxed pass; "grind" forces rp ≠ ""
    have hrp : skill_grind_selection_pure skill cl (relaxedList cands) ≠ "" := by
      intro hrp0
      have hno : dispatch skill cl cs clv cands = ("no_grind", "") := by
        unfold dispatch; exact combine_no_grind _ _ _ _ _ _ hns hfp hrp0
      rw [hno] at hg; exact absurd hg (by decide)
    have hres : dispatch skill cl cs clv cands
        = ("grind", skill_grind_selection_pure skill cl (relaxedList cands)) := by
      unfold dispatch; exact combine_relaxed_pick _ _ _ _ _ _ hns hfp hrp
    obtain ⟨g, hgmem, hgcode, hgfeas⟩ := result_feasible skill cl (relaxedList cands) hrp
    obtain ⟨c, hcmem, hcg⟩ := mem_relaxedList cands g hgmem
    refine ⟨c, hcmem, ?_, ?_⟩
    · rw [hres]; show c.code = skill_grind_selection_pure skill cl (relaxedList cands)
      rw [← hgcode, ← hcg, toGrind_code]
    · show feasible skill cl (toGrind c); rw [hcg]; exact hgfeas
  · -- full non-empty ⇒ result from full pass
    have hres := full_preference skill cl cs clv cands hns hfp
    obtain ⟨g, hgmem, hgcode, hgfeas⟩ := result_feasible skill cl (fullList cands) hfp
    obtain ⟨c, hcmem, _, hcg⟩ := mem_fullList cands g hgmem
    refine ⟨c, hcmem, ?_, ?_⟩
    · rw [hres]; show c.code = skill_grind_selection_pure skill cl (fullList cands)
      rw [← hgcode, ← hcg, toGrind_code]
    · show feasible skill cl (toGrind c); rw [hcg]; exact hgfeas

end Formal.SkillStepDispatch
