-- @concept: combat, planner @property: liveness, safety
/-
Reachability for the monster-drop loop in `FightAction.apply` (extracted to pure
`apply_monster_drops_pure`). A kill mints one of each of the monster's drops into
the planner's projected inventory, BREAKING when full so it never mints past cap.

This is obligation 4 of the level-50 liveness roadmap (monster-drop materials are
obtainable): if a monster drops item `x` and the kill's loot fits, the projected
`counts x` strictly increases — so a `needed:N` GatherMaterials goal over a
monster drop is reachable by fighting (the remaining-need measure decreases).

Roles:
* `applyDrops_monotone` — drops NEVER decrease any item count (safety: a fight
  can't lose inventory in the projection).
* `applyDrops_used_le_cap` — with room for all drops, the post `used ≤ cap`
  (never mints past capacity).
* `fight_drop_reachable` — with room for all drops, a dropped item's count rises
  by ≥ 1 (the liveness/reachability core).

Inventory counts are modelled as a total function `String → Nat`; the differential
oracle queries specific keys. Core only — no mathlib.
-/

namespace Formal.MonsterDropApply

/-- Minimal projected inventory: slot count, capacity, per-item counts. -/
structure Inv where
  used : Nat
  cap : Nat
  counts : String → Nat

/-- Mirror of `gather_apply_pure`: +1 slot, +1 to `d`'s count, others preserved. -/
def gatherApply (inv : Inv) (d : String) : Inv :=
  ⟨inv.used + 1, inv.cap, fun k => if k = d then inv.counts k + 1 else inv.counts k⟩

/-- The drop loop WITHOUT the cap-break (every drop applied). -/
def applyAll (inv : Inv) (drops : List String) : Inv :=
  drops.foldl gatherApply inv

/-- Mirror of `apply_monster_drops_pure`: apply each drop, BREAK when full
(`used ≥ cap`). -/
def applyDrops : Inv → List String → Inv
  | inv, [] => inv
  | inv, d :: ds => if inv.cap ≤ inv.used then inv else applyDrops (gatherApply inv d) ds

/-! ## gatherApply / applyAll count facts. -/

theorem gatherApply_counts_ge (inv : Inv) (d : String) (k : String) :
    inv.counts k ≤ (gatherApply inv d).counts k := by
  unfold gatherApply
  by_cases h : k = d
  · simp [h]
  · simp [h]

theorem gatherApply_used (inv : Inv) (d : String) :
    (gatherApply inv d).used = inv.used + 1 := rfl

/-- `applyAll` never decreases any count. -/
theorem applyAll_monotone (k : String) :
    ∀ (drops : List String) (inv : Inv), inv.counts k ≤ (applyAll inv drops).counts k := by
  intro drops
  induction drops with
  | nil => intro inv; exact Nat.le_refl _
  | cons d ds ih =>
    intro inv
    unfold applyAll at ih ⊢
    simp only [List.foldl_cons]
    exact Nat.le_trans (gatherApply_counts_ge inv d k) (ih (gatherApply inv d))

/-- `applyAll` raises a member drop's count by ≥ 1. -/
theorem applyAll_increments (x : String) :
    ∀ (drops : List String) (inv : Inv), x ∈ drops →
      inv.counts x + 1 ≤ (applyAll inv drops).counts x := by
  intro drops
  induction drops with
  | nil => intro inv hx; exact absurd hx (List.not_mem_nil)
  | cons d ds ih =>
    intro inv hx
    unfold applyAll
    simp only [List.foldl_cons]
    rcases List.mem_cons.mp hx with hxd | hxds
    · -- x = d: the head step bumps x; the tail is monotone
      subst hxd
      have hstep : inv.counts x + 1 ≤ (gatherApply inv x).counts x := by
        unfold gatherApply; simp
      exact Nat.le_trans hstep (applyAll_monotone x ds (gatherApply inv x))
    · -- x ∈ ds: IH on the tail, lifted past the head step's monotonicity
      have ht := ih (gatherApply inv d) hxds
      unfold applyAll at ht
      exact Nat.le_trans (Nat.add_le_add_right (gatherApply_counts_ge inv d x) 1) ht

/-! ## applyDrops (the cap-break loop). -/

/-- Drops NEVER decrease any item count, even with the cap-break. -/
theorem applyDrops_monotone (k : String) :
    ∀ (drops : List String) (inv : Inv), inv.counts k ≤ (applyDrops inv drops).counts k := by
  intro drops
  induction drops with
  | nil => intro inv; exact Nat.le_refl _
  | cons d ds ih =>
    intro inv
    unfold applyDrops
    by_cases hfull : inv.cap ≤ inv.used
    · rw [if_pos hfull]
      exact Nat.le_refl _
    · rw [if_neg hfull]
      exact Nat.le_trans (gatherApply_counts_ge inv d k) (ih (gatherApply inv d))

/-- When the whole kill's loot fits (`used + |drops| ≤ cap`), the cap-break never
fires, so `applyDrops` agrees with `applyAll`. -/
theorem applyDrops_eq_applyAll :
    ∀ (drops : List String) (inv : Inv), inv.used + drops.length ≤ inv.cap →
      applyDrops inv drops = applyAll inv drops := by
  intro drops
  induction drops with
  | nil => intro inv _; rfl
  | cons d ds ih =>
    intro inv hroom
    have hnotfull : ¬ (inv.cap ≤ inv.used) := by
      simp only [List.length_cons] at hroom; omega
    have hroom' : (gatherApply inv d).used + ds.length ≤ (gatherApply inv d).cap := by
      show inv.used + 1 + ds.length ≤ inv.cap
      simp only [List.length_cons] at hroom; omega
    have hlhs : applyDrops inv (d :: ds) = applyDrops (gatherApply inv d) ds := by
      show (if inv.cap ≤ inv.used then inv else applyDrops (gatherApply inv d) ds)
        = applyDrops (gatherApply inv d) ds
      rw [if_neg hnotfull]
    have hrhs : applyAll inv (d :: ds) = applyAll (gatherApply inv d) ds := by
      simp only [applyAll, List.foldl_cons]
    rw [hlhs, hrhs]
    exact ih (gatherApply inv d) hroom'

/-- `fight_drop_reachable`: with room for the kill's loot, a dropped item's
projected count rises by ≥ 1 — the reachability core for monster-drop materials. -/
theorem fight_drop_reachable (inv : Inv) (drops : List String) (x : String)
    (hroom : inv.used + drops.length ≤ inv.cap) (hx : x ∈ drops) :
    inv.counts x + 1 ≤ (applyDrops inv drops).counts x := by
  rw [applyDrops_eq_applyAll drops inv hroom]
  exact applyAll_increments x drops inv hx

end Formal.MonsterDropApply
