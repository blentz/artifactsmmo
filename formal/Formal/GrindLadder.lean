-- @concept: crafting, planner @property: liveness, safety
/-
Liveness for the skill-grind RESERVATION LADDER (the impure flag hoisting in
`_skill_dispatch_candidates`, now extracted to pure `cannibalize_pure` /
`dispatch_candidate_flags`).

The dispatch CORE (Formal.SkillStepDispatch) proves: given per-candidate reserved
flags, a feasible relaxed candidate forces a grind. THIS module models how those
flags are COMPUTED from raw candidates + reserved sets + ownership, and proves the
two liveness extensions the 2026-06-15 fixes added — the cases where the ladder
guarantees the grind never freezes:

* `grind_when_unowned_target` — an unowned, craftable-now committed TARGET is
  always grindable (crafting it is dual slot+skill progress), even though its
  materials are reserved.
* `grind_when_all_owned` — once ≥1 of every feasible in-skill item is owned (no
  unowned target left), the grind re-crafts an owned item (cannibalizes) rather
  than freezing.

HONEST SCOPE: this is NOT unconditional never-freeze. An unowned NON-target
throwaway whose every material is relaxed-reserved still yields NO_GRIND — these
theorems state exactly the two corners the ladder covers, no more.

Core only — no mathlib. Builds on Formal.SkillStepDispatch.
-/
import Formal.SkillStepDispatch

namespace Formal.GrindLadder

open Formal.SkillStepDispatch
open Extracted.SkillGrindSelection (GrindCandidate)

/-- A raw grind candidate before flag computation: the selection fields plus the
recipe inputs, target membership, and ownership the ladder reads. -/
structure RC where
  code : String
  craft_skill : String
  craft_level : Int
  mats_missing : Int
  obtainable : Bool
  is_target : Bool
  owned : Bool
  recipe_mats : List String

/-- Mirror of `dispatch_candidate_flags`: `(uses_reserved_full,
uses_reserved_relaxed)`. An unowned, in-level target is EXEMPT (both false). -/
def flagsFor (rc : RC) (cl : Int) (rf rr : List String) (cann : Bool) : Bool × Bool :=
  let exempt := rc.is_target && decide (rc.craft_level ≤ cl) && (!rc.owned)
  ((!exempt) && rc.recipe_mats.any (fun m => rf.contains m),
   (!exempt) && (!cann) && rc.recipe_mats.any (fun m => rr.contains m))

/-- Mirror of `cannibalize_pure`: every craftable-now obtainable candidate owned. -/
def cannibalizeModel (cl : Int) (rcs : List RC) : Bool :=
  let feasible := rcs.filter (fun rc => decide (rc.craft_level ≤ cl) && rc.obtainable)
  decide (feasible.length > 0) && (!(feasible.any (fun rc => !rc.owned)))

/-- Project a raw candidate to a `DC` with its computed flags. -/
def toDC (rc : RC) (cl : Int) (rf rr : List String) (cann : Bool) : DC :=
  { code := rc.code, craft_skill := rc.craft_skill, craft_level := rc.craft_level,
    mats_missing := rc.mats_missing, obtainable := rc.obtainable,
    uses_reserved_full := (flagsFor rc cl rf rr cann).1,
    uses_reserved_relaxed := (flagsFor rc cl rf rr cann).2,
    wanted := rc.is_target }

/-- The full grind dispatch from raw candidates: compute the cannibalize flag,
project each candidate, run the proved `dispatch`. Mirrors the Python
`skill_step_dispatch_pure ∘ _skill_dispatch_candidates`. -/
def dispatchFromRaw (skill : String) (cl : Int) (cs : String) (clv : Int)
    (rf rr : List String) (rcs : List RC) : String × String :=
  dispatch skill cl cs clv
    (rcs.map (fun rc => toDC rc cl rf rr (cannibalizeModel cl rcs)))

/-- `RC`-level feasibility: same craft skill, in level, obtainable. -/
def feasibleRC (skill : String) (cl : Int) (rc : RC) : Prop :=
  rc.craft_skill = skill ∧ rc.craft_level ≤ cl ∧ rc.obtainable = true

/-! ## Flag lemmas. -/

/-- `flags_exempt`: an unowned, in-level target gets BOTH reserved flags false. -/
theorem flags_exempt (rc : RC) (cl : Int) (rf rr : List String) (cann : Bool)
    (ht : rc.is_target = true) (hl : rc.craft_level ≤ cl) (ho : rc.owned = false) :
    flagsFor rc cl rf rr cann = (false, false) := by
  unfold flagsFor
  have hexempt : (rc.is_target && decide (rc.craft_level ≤ cl) && (!rc.owned)) = true := by
    rw [ht, ho]; simp [hl]
  rw [hexempt]; simp

/-- `flags_cannibalize`: under cannibalization the relaxed flag is always false. -/
theorem flags_cannibalize (rc : RC) (cl : Int) (rf rr : List String) :
    (flagsFor rc cl rf rr true).2 = false := by
  unfold flagsFor; simp

/-! ## Projection preserves the selection view. -/

@[simp] theorem toDC_code (rc : RC) (cl) (rf rr) (cann) :
    (toDC rc cl rf rr cann).code = rc.code := rfl

theorem toDC_feasible (skill : String) (cl : Int) (rf rr : List String) (cann : Bool)
    (rc : RC) (h : feasibleRC skill cl rc) :
    feasibleDC skill cl (toDC rc cl rf rr cann) := by
  obtain ⟨hs, hlv, hob⟩ := h
  exact ⟨hs, hlv, hob⟩

/-- Every relaxedList member's code comes from an `rc ∈ rcs`. -/
theorem relaxedList_codes (cl : Int) (rf rr : List String) (cann : Bool)
    (rcs : List RC) (d : GrindCandidate)
    (hd : d ∈ relaxedList (rcs.map (fun rc => toDC rc cl rf rr cann))) :
    ∃ rc, rc ∈ rcs ∧ d.code = rc.code := by
  obtain ⟨c, hcmem, hcg⟩ := mem_relaxedList _ d hd
  rw [List.mem_map] at hcmem
  obtain ⟨rc, hrc, hrctoDC⟩ := hcmem
  refine ⟨rc, hrc, ?_⟩
  rw [← hcg, toGrind_code, ← hrctoDC, toDC_code]

/-! ## Liveness theorems. -/

/-- `grind_when_unowned_target`: NOT suppressed plus a feasible, unowned, in-skill
TARGET (non-empty codes) forces a "grind" — the target is always craftable for
the grind despite the reservation (the 2026-06-14 230824 unfreeze). -/
theorem grind_when_unowned_target (skill : String) (cl : Int) (cs : String) (clv : Int)
    (rf rr : List String) (rcs : List RC) (hns : ¬ (cs = skill ∧ clv ≤ cl))
    (rc : RC) (hmem : rc ∈ rcs) (hf : feasibleRC skill cl rc)
    (ht : rc.is_target = true) (ho : rc.owned = false)
    (hne : ∀ r ∈ rcs, r.code ≠ "") :
    (dispatchFromRaw skill cl cs clv rf rr rcs).1 = "grind" := by
  unfold dispatchFromRaw
  apply forward_progress skill cl cs clv _ hns
    (toDC rc cl rf rr (cannibalizeModel cl rcs))
  · rw [List.mem_map]; exact ⟨rc, hmem, rfl⟩
  · show (flagsFor rc cl rf rr (cannibalizeModel cl rcs)).2 = false
    rw [flags_exempt rc cl rf rr (cannibalizeModel cl rcs) ht hf.2.1 ho]
  · exact toDC_feasible skill cl rf rr (cannibalizeModel cl rcs) rc hf
  · intro d hd
    obtain ⟨r, hrmem, hdc⟩ := relaxedList_codes cl rf rr (cannibalizeModel cl rcs) rcs d hd
    rw [hdc]; exact hne r hrmem

/-- `grind_when_all_owned` (cannibalization backstop): NOT suppressed, a feasible
in-skill candidate exists, and cannibalization is active (≥1 of every feasible
item owned) ⇒ "grind". The grind re-crafts an owned item to keep leveling rather
than freezing. -/
theorem grind_when_all_owned (skill : String) (cl : Int) (cs : String) (clv : Int)
    (rf rr : List String) (rcs : List RC) (hns : ¬ (cs = skill ∧ clv ≤ cl))
    (rc : RC) (hmem : rc ∈ rcs) (hf : feasibleRC skill cl rc)
    (hcann : cannibalizeModel cl rcs = true)
    (hne : ∀ r ∈ rcs, r.code ≠ "") :
    (dispatchFromRaw skill cl cs clv rf rr rcs).1 = "grind" := by
  unfold dispatchFromRaw
  rw [hcann]
  apply forward_progress skill cl cs clv _ hns (toDC rc cl rf rr true)
  · rw [List.mem_map]; exact ⟨rc, hmem, rfl⟩
  · show (flagsFor rc cl rf rr true).2 = false
    exact flags_cannibalize rc cl rf rr
  · exact toDC_feasible skill cl rf rr true rc hf
  · intro d hd
    obtain ⟨r, hrmem, hdc⟩ := relaxedList_codes cl rf rr true rcs d hd
    rw [hdc]; exact hne r hrmem

end Formal.GrindLadder
