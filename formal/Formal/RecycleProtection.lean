
/-!
# Formal.RecycleProtection

**Correctness of the RecycleAction exclusion filter in `_build_actions`.**

Commit e74c391 added a protected-codes filter to skip RecycleAction
construction for codes in `target_gear ∪ target_tools`. Closes the bug
where the planner used Recycle to destroy copper_dagger / copper_axe /
copper_pickaxe (all target items) for a one-shot copper_bar windfall.

This module proves:

1. The protected set is exactly `target_gear ∪ target_tools`.
2. No code in the protected set appears in the recycle-action codes
   list.
3. Off-target codes ARE still in the recycle set (no over-protection).
4. The filter is monotone — adding to protected set never adds to
   recycle codes.
-/

namespace Formal.RecycleProtection

/-! ## Abstract model.

The action-set builder iterates `craftable equippable` codes and filters
against a protected set. We model the protected set as a list (used as
a set via `List.contains`). -/

structure BuildInputs where
  craftableEquippables : List Int
  targetGear           : List Int
  targetTools          : List Int

/-! ## Protected-set definition. -/

def protectedCodes (b : BuildInputs) : List Int :=
  b.targetGear ++ b.targetTools

theorem protected_contains_target_gear
    (b : BuildInputs) (code : Int) (h : code ∈ b.targetGear) :
    code ∈ protectedCodes b := by
  unfold protectedCodes
  exact List.mem_append.mpr (Or.inl h)

theorem protected_contains_target_tools
    (b : BuildInputs) (code : Int) (h : code ∈ b.targetTools) :
    code ∈ protectedCodes b := by
  unfold protectedCodes
  exact List.mem_append.mpr (Or.inr h)

/-! ## Recycle-action codes after filter. -/

def recycleCodes (b : BuildInputs) : List Int :=
  b.craftableEquippables.filter (fun c => ¬ (protectedCodes b).contains c)

/-! ## Soundness: no protected code in recycle set. -/

theorem protected_excluded_from_recycle
    (b : BuildInputs) (code : Int)
    (hProt : code ∈ protectedCodes b) :
    code ∉ recycleCodes b := by
  unfold recycleCodes
  intro h
  rw [List.mem_filter] at h
  obtain ⟨_, hNot⟩ := h
  simp at hNot
  exact hNot hProt

/-! ## Completeness: off-target codes remain in recycle set. -/

theorem unprotected_craftable_in_recycle
    (b : BuildInputs) (code : Int)
    (hCraft : code ∈ b.craftableEquippables)
    (hNotProt : code ∉ protectedCodes b) :
    code ∈ recycleCodes b := by
  unfold recycleCodes
  rw [List.mem_filter]
  refine ⟨hCraft, ?_⟩
  simpa using hNotProt

/-! ## Monotonicity: extending protected set never adds to recycle set. -/

-- Monotonicity statement reframed as a Boolean filter property to
-- avoid the Mem ↔ contains conversion noise.
theorem recycle_subset_when_protection_grows
    (b1 b2 : BuildInputs)
    (hSame : b1.craftableEquippables = b2.craftableEquippables)
    (hPInc : ∀ c, (protectedCodes b1).contains c = true →
                  (protectedCodes b2).contains c = true) :
    ∀ c ∈ recycleCodes b2, c ∈ recycleCodes b1 := by
  intro c hC
  unfold recycleCodes at hC ⊢
  rw [List.mem_filter] at hC ⊢
  obtain ⟨hCraft, hNot2⟩ := hC
  rw [hSame]
  refine ⟨hCraft, ?_⟩
  -- Normalize both to `¬ (protectedCodes _).contains c = true`.
  simp only [decide_not, Bool.not_eq_true', decide_eq_false_iff_not] at hNot2 ⊢
  intro h1
  exact hNot2 (hPInc c h1)

/-! ## Trace-mirror: the 2026-06-06 16:34 case. -/

/-- Robby's target_gear includes copper_dagger; the recycle filter
excludes it. Pinned as a literal. -/
def traceBuild : BuildInputs := {
  craftableEquippables := [1, 2, 3, 6, 99]   -- 1=copper_dagger, 6=copper_axe, 99=iron_dagger
  targetGear           := [1, 4, 5]
  targetTools          := [6, 7]
}

theorem trace_copper_dagger_excluded :
    1 ∉ recycleCodes traceBuild := by
  unfold recycleCodes traceBuild protectedCodes
  decide

theorem trace_copper_axe_excluded :
    6 ∉ recycleCodes traceBuild := by
  unfold recycleCodes traceBuild protectedCodes
  decide

/-- An off-target item (iron_dagger = 99, not in target sets) STAYS in
the recycle list. -/
theorem trace_off_target_kept :
    99 ∈ recycleCodes traceBuild := by
  unfold recycleCodes traceBuild protectedCodes
  decide

end Formal.RecycleProtection
