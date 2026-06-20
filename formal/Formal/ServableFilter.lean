import Mathlib.Tactic

/-! # ServableFilter — keep only plannable-step roots when any is plannable

Mirrors `src/artifactsmmo_cli/ai/tiers/servable_filter.py::keep_servable`, the filter
`decide()` applies so `chosen_root` is a root whose actionable step can be served this
cycle (not a top-scored-but-unbuildable objective). Contract: when at least one
candidate is servable, drop the unservable ones; when NONE is servable, keep them all
(graceful fallback — the arbiter's own fallback walk still runs).

`keepServable` operates on `(item, servable)` pairs (the Python zips two equal-length
lists). Proved roles:
* `keepServable_all_servable_of_any` — when any pair is servable, every kept item IS
  servable (the unservable ones are dropped).
* `keepServable_id_of_none` — when none is servable, every item is kept unchanged.
* `keepServable_nonempty_of_nonempty` — the result is never empty for a non-empty input
  (the bot always has a candidate to consider).
-/

namespace Formal.ServableFilter

/-- Keep the servable items; if none are servable, keep all (graceful fallback). -/
def keepServable {α : Type} (tagged : List (α × Bool)) : List α :=
  let kept := tagged.filterMap (fun p => if p.2 then some p.1 else none)
  if kept.isEmpty then tagged.map (·.1) else kept

/-- When at least one item is servable, the result is exactly the servable subset —
    so every kept item is servable. -/
theorem keepServable_all_servable_of_any {α : Type} (tagged : List (α × Bool))
    (h : tagged.any (·.2) = true) :
    keepServable tagged = tagged.filterMap (fun p => if p.2 then some p.1 else none) := by
  have hne : tagged.filterMap (fun p => if p.2 then some p.1 else none) ≠ [] := by
    obtain ⟨p, hmem, hp⟩ := List.any_eq_true.mp h
    intro hnil
    rw [List.filterMap_eq_nil_iff] at hnil
    exact absurd (hnil p hmem) (by simp [show p.2 = true by simpa using hp])
  simp [keepServable, List.isEmpty_iff, hne]

/-- When NO item is servable, the result is all items unchanged. -/
theorem keepServable_id_of_none {α : Type} (tagged : List (α × Bool))
    (h : tagged.any (·.2) = false) :
    keepServable tagged = tagged.map (·.1) := by
  have hnil : tagged.filterMap (fun p => if p.2 then some p.1 else none) = [] := by
    rw [List.filterMap_eq_nil_iff]
    intro p hmem
    have hp2 : p.2 = false := by
      have hf := (List.any_eq_false.mp h) p hmem
      simpa using hf
    simp [hp2]
  simp [keepServable, hnil]

/-- The result is non-empty whenever the input is — the bot always retains a
    candidate to rank (servable subset if any, else the full list). -/
theorem keepServable_nonempty_of_nonempty {α : Type} (tagged : List (α × Bool))
    (h : tagged ≠ []) : keepServable tagged ≠ [] := by
  by_cases hempty : tagged.filterMap (fun p => if p.2 then some p.1 else none) = []
  · simp only [keepServable, List.isEmpty_iff, hempty, if_pos]
    simpa using h
  · simp [keepServable, List.isEmpty_iff, hempty]

end Formal.ServableFilter
