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
  wanted : Bool

/-- Project a `DC` to the selection's `GrindCandidate` (drops the reserved flags;
preserves every field the selection reads, incl. the wanted-first key). -/
def toGrind (c : DC) : GrindCandidate :=
  { code := c.code, craft_skill := c.craft_skill, craft_level := c.craft_level,
    mats_missing := c.mats_missing, obtainable := c.obtainable, wanted := c.wanted }

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

/-! ## Dampened next-tier throwaway suppression (the wrapper's `dampened` branch).

The impure caller passes a `dampened : Bool` next-tier signal. When set, the
wrapper converts a GRIND on a throwaway (a pick that is NOT a wanted objective
target) into SUPPRESS — the throwaway would only over-skill a tier the committed
root already covers. The branch is guarded by `not wanted`, so committed/wanted
progress is never blocked. `dampSuppress` mirrors the Python `next(...)` lookup;
`dispatchD` is `dispatch` post-composed with that guarded conversion.

Load-bearing theorems:
* `dispatchD_not_dampened`        — `dampened = false` reproduces `dispatch`
                                     exactly, so every `dispatch` role theorem
                                     above transfers to the default call path.
* `dispatchD_suppress_of_throwaway` — a dampened grind on a not-wanted pick
                                     suppresses (the intended new behavior).
* `dispatchD_preserves_wanted_grind`— a grind whose pick IS wanted is NEVER
                                     suppressed by dampening (wanted-progress).
* `dispatchD_changed_only_throwaway_grind` — dampening only ever converts a
                                     not-wanted GRIND into SUPPRESS; suppress /
                                     no_grind / wanted-grind decisions are
                                     untouched (committed-progress safety).
-/

/-- The dampened suppress predicate: mirrors the Python `next((c for c in
candidates if c.code == code), None)` lookup — `true` iff the first candidate
whose code equals the grind pick exists and is NOT a wanted objective target. -/
def dampSuppress (cands : List DC) (code : String) : Bool :=
  match cands.find? (fun c => c.code == code) with
  | some c => !c.wanted
  | none => false

/-- The full model of `skill_step_dispatch_pure` WITH the `dampened` parameter:
the un-dampened `dispatch` decision, except a GRIND on a throwaway (not-wanted)
pick is converted to `("suppress", "")` when `dampened`. -/
def dispatchD (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (dampened : Bool) : String × String :=
  if dampened && (dispatch skill cl cs clv cands).1 == "grind"
      && dampSuppress cands (dispatch skill cl cs clv cands).2
  then ("suppress", "")
  else dispatch skill cl cs clv cands

/-- `dispatchD` with `dampened = false` is exactly `dispatch`: the default call
path is unchanged, so the `suppress_correct` / `full_preference` /
`reservation_safety` / `forward_progress` / `grind_valid` role theorems above
characterize it verbatim. -/
theorem dispatchD_not_dampened (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) :
    dispatchD skill cl cs clv cands false = dispatch skill cl cs clv cands := by
  unfold dispatchD; simp

/-- If the picked candidate (found by code) is WANTED, the dampened suppress
predicate is false — a wanted objective craft is never a throwaway. -/
theorem dampSuppress_eq_false_of_found_wanted (cands : List DC) (code : String) (c : DC)
    (hfound : cands.find? (fun d => d.code == code) = some c) (hw : c.wanted = true) :
    dampSuppress cands code = false := by
  unfold dampSuppress; rw [hfound]; simp [hw]

/-- `dispatchD_suppress_of_throwaway`: a dampened GRIND on a throwaway (not-wanted)
pick is suppressed. -/
theorem dispatchD_suppress_of_throwaway (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (code : String)
    (hd : dispatch skill cl cs clv cands = ("grind", code))
    (hds : dampSuppress cands code = true) :
    dispatchD skill cl cs clv cands true = ("suppress", "") := by
  unfold dispatchD; rw [hd]; simp [hds]

/-- `dispatchD_grind_of_wanted`: when the pick is NOT a throwaway (dampSuppress
false), the grind survives dampening at any `dampened` flag. -/
theorem dispatchD_grind_of_wanted (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (code : String) (dampened : Bool)
    (hd : dispatch skill cl cs clv cands = ("grind", code))
    (hds : dampSuppress cands code = false) :
    dispatchD skill cl cs clv cands dampened = ("grind", code) := by
  unfold dispatchD; rw [hd]; simp [hds]

/-- `dispatchD_preserves_wanted_grind` (wanted-progress): a grind whose pick is a
WANTED objective target is never suppressed by dampening. -/
theorem dispatchD_preserves_wanted_grind (skill : String) (cl : Int) (cs : String) (clv : Int)
    (cands : List DC) (code : String) (dampened : Bool) (c : DC)
    (hd : dispatch skill cl cs clv cands = ("grind", code))
    (hfound : cands.find? (fun d => d.code == code) = some c) (hw : c.wanted = true) :
    dispatchD skill cl cs clv cands dampened = ("grind", code) :=
  dispatchD_grind_of_wanted skill cl cs clv cands code dampened hd
    (dampSuppress_eq_false_of_found_wanted cands code c hfound hw)

/-- `dispatchD_changed_only_throwaway_grind` (committed-progress safety): if
dampening changes the decision at all, the un-dampened decision was a GRIND on a
throwaway (not-wanted) pick and the new decision is SUPPRESS. Hence suppress,
no_grind, and wanted-grind decisions are all preserved. -/
theorem dispatchD_changed_only_throwaway_grind (skill : String) (cl : Int) (cs : String)
    (clv : Int) (cands : List DC) (dampened : Bool)
    (hchg : dispatchD skill cl cs clv cands dampened ≠ dispatch skill cl cs clv cands) :
    dampened = true ∧ (dispatch skill cl cs clv cands).1 = "grind"
      ∧ dampSuppress cands (dispatch skill cl cs clv cands).2 = true
      ∧ dispatchD skill cl cs clv cands dampened = ("suppress", "") := by
  unfold dispatchD at hchg ⊢
  by_cases hcond : (dampened && (dispatch skill cl cs clv cands).1 == "grind"
      && dampSuppress cands (dispatch skill cl cs clv cands).2) = true
  · rw [if_pos hcond]
    rw [Bool.and_eq_true, Bool.and_eq_true] at hcond
    obtain ⟨⟨hdam, hgrind⟩, hsupp⟩ := hcond
    exact ⟨hdam, eq_of_beq hgrind, hsupp, rfl⟩
  · rw [if_neg hcond] at hchg; exact absurd rfl hchg

end Formal.SkillStepDispatch
