/-
Formal model of `task_batch_size` from
`src/artifactsmmo_cli/ai/task_batch.py`.

The Python routine decides how many task units to produce per PursueTask plan.
It returns 1 unless on the "items task" branch (task_type == "items", a task_code
is present, task_total > 0, and remaining > 0). On that branch it clamps:

    usable = (inventory_free + held_recipe) - MIN_FREE   (MIN_FREE = 3)
    fit    = usable // mats_per_unit                     (Python floor division)
    result = max(1, min(remaining, fit, BATCH_CAP))      (BATCH_CAP = 10)

We abstract `mats_per_unit` (≥ 1) and `held_recipe` as integer inputs — they are
recipe-closure math proven elsewhere. Python's `//` is floor division, modelled
by `Int.fdiv`.

This clamp is now the shared core of BOTH `task_batch_size_pure` and the
code-agnostic `craft_batch_size_pure` (Python): `batchSize`'s `remaining`
argument abstracts the demand generically, so the task path is exactly the
`demand = remaining` specialization. All five theorems below hold for ANY
demand, so no new hand proofs are needed for the generalization; the extracted
`craft_batch_size_pure`/`task_batch_size_pure` are bridged to `batchSize` in
`Formal/Extracted/Bridges3.lean` (`craft_batch_bridge`, `task_batch_bridge`,
`task_batch_bridge_none`), which transfer these theorems to the extracted defs.
The Python `craft_batch_size_pure` additionally guards `mats_per_unit = 0` (a
degenerate zero-quantity recipe) by returning `max 1 (min demand batchCap)` — a
div-by-zero shield outside this model's `mats ≥ 1` assumption, handled as a
separate branch in the bridge.

Lean core only — no mathlib. Integer arithmetic is handled by `omega`.
-/

namespace Formal.TaskBatch

/-- Depth cap (mirrors `BATCH_CAP`). -/
def batchCap : Int := 10

/-- Min free slots reserved (mirrors `_MIN_FREE_SLOTS`). -/
def minFree : Int := 3

/-- The model of `task_batch_size`.

`taskBranch` is the conjunction `task_type == "items" ∧ task_code ∧ task_total > 0
∧ remaining > 0` evaluated in Python. `mats` is `mats_per_unit` (≥ 1 by
recipe-closure invariant). `free` is `inventory_free`, `held` is `held_recipe`.

When not on the task branch the function returns 1. On the task branch it clamps
the produced units between 1 and `min(remaining, usable // mats, batchCap)`. -/
def batchSize (taskBranch : Bool) (remaining mats free held : Int) : Int :=
  if taskBranch then
    let usable := (free + held) - minFree
    let fit := Int.fdiv usable mats
    max 1 (min remaining (min fit batchCap))
  else
    1

/-- `result ≥ 1` always (the floor at 1). -/
theorem batch_ge_one (tb : Bool) (remaining mats free held : Int) :
    1 ≤ batchSize tb remaining mats free held := by
  unfold batchSize
  split
  · exact Int.le_max_left 1 _
  · exact Int.le_refl 1

/-- On the task branch the result never exceeds `remaining`. -/
theorem batch_le_remaining (remaining mats free held : Int)
    (hrem : 1 ≤ remaining) :
    batchSize true remaining mats free held ≤ remaining := by
  unfold batchSize
  simp only [if_true]
  apply Int.max_le.mpr
  exact ⟨hrem, Int.min_le_left _ _⟩

/-- On the task branch the result never exceeds `batchCap` (= 10). -/
theorem batch_le_cap (remaining mats free held : Int) :
    batchSize true remaining mats free held ≤ batchCap := by
  unfold batchSize
  simp only [if_true]
  apply Int.max_le.mpr
  refine ⟨by decide, ?_⟩
  exact Int.le_trans (Int.min_le_right _ _) (Int.min_le_right _ _)

/-- On the task branch, if `usable ≥ mats` then `result * mats ≤ usable`,
where `usable = (free + held) - minFree`. The floor-division clamp guarantees the
raw materials for `result` units fit in the usable space. Requires `mats ≥ 1`. -/
theorem batch_fits (remaining mats free held : Int)
    (hmats : 1 ≤ mats)
    (husable : mats ≤ (free + held) - minFree) :
    batchSize true remaining mats free held * mats ≤ (free + held) - minFree := by
  unfold batchSize
  simp only [if_true]
  have hmpos : 0 < mats := by omega
  have husable_nonneg : (0 : Int) ≤ (free + held) - minFree := by omega
  -- fit * mats ≤ usable  (floor-division lower bound, mats > 0, usable ≥ 0)
  have hfloor : Int.fdiv ((free + held) - minFree) mats * mats ≤ (free + held) - minFree := by
    have hdm := Int.mul_fdiv_add_fmod ((free + held) - minFree) mats
    have hmod : 0 ≤ Int.fmod ((free + held) - minFree) mats :=
      Int.fmod_nonneg husable_nonneg (by omega)
    have hcomm : mats * Int.fdiv ((free + held) - minFree) mats
        = Int.fdiv ((free + held) - minFree) mats * mats := Int.mul_comm _ _
    omega
  -- 1 ≤ fit : since mats ≤ usable and 0 < mats, the floor is ≥ 1
  have hfit_ge_one : 1 ≤ Int.fdiv ((free + held) - minFree) mats := by
    rcases Int.lt_or_le (Int.fdiv ((free + held) - minFree) mats) 1 with hc | hc
    · exfalso
      have hlt := Int.lt_fdiv_add_one_mul_self ((free + held) - minFree) hmpos
      have hle : (Int.fdiv ((free + held) - minFree) mats + 1) * mats ≤ 1 * mats :=
        Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
      simp only [Int.one_mul] at hle
      omega
    · exact hc
  have hclamp_le_fit :
      max 1 (min remaining (min (Int.fdiv ((free + held) - minFree) mats) batchCap))
        ≤ Int.fdiv ((free + held) - minFree) mats := by
    apply Int.max_le.mpr
    exact ⟨hfit_ge_one, Int.le_trans (Int.min_le_right _ _) (Int.min_le_left _ _)⟩
  calc max 1 (min remaining (min (Int.fdiv ((free + held) - minFree) mats) batchCap)) * mats
      ≤ Int.fdiv ((free + held) - minFree) mats * mats :=
        Int.mul_le_mul_of_nonneg_right hclamp_le_fit (by omega)
    _ ≤ (free + held) - minFree := hfloor

/-- Off the task branch the result is exactly 1. -/
theorem non_task_one (remaining mats free held : Int) :
    batchSize false remaining mats free held = 1 := by
  unfold batchSize
  simp

end Formal.TaskBatch
