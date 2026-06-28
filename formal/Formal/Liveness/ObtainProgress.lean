-- @concept: liveness, planner @property: monotonicity
import Formal.RecipeClosure
import Mathlib.Tactic

/-! # ObtainProgress — the deepened obtain-progress witness is faithful

`root_progress.py::_obtain_progress` (the production `progressed` witness for an
`ObtainItem` gear root, consumed by the sticky progress gate) was SHALLOW: it counted
only the DIRECT recipe inputs held in inventory. During a long ore-gather stretch toward
`copper_boots` the direct `copper_bar` count stayed flat, so the root read as
"not progressing", the sticky anchor was released every cycle, and a tied same-tier gear
root cannibalised the shared `copper_bar` — the copper_boots never-crafted livelock
(trace 2026-06-21).

The fix deepens the witness to the raw-material-unit-weighted owned count over the WHOLE
recipe closure (target + every transitive intermediate + raw resource):

    obtainProgress r y fuel owned nodes = Σ_{i ∈ nodes} owned i * rawUnits r y fuel i

This module proves the witness is FAITHFUL — the property `ZombieFreedom.lean`'s
`hprogFaithful` obligation hand-waved to the differential for gear roots:

* `obtainProgress_gather` / `obtainProgress_gather_strict` — gathering one raw unit of a
  closure node strictly increases the witness (so ore-gathering toward boots registers
  as progress; the shallow predecessor's false-flat is impossible). THIS is the
  bug-killer.
* `obtainProgress_mono` — owned pointwise ↑ ⇒ witness ↑ (never a spurious drop from
  acquiring more material).
* `obtainProgress_craft_invariant` — a recipe conversion (consume `Σ qty·child`, produce
  one output) leaves the witness UNCHANGED (the raw-unit weight conserves across a craft),
  so smelting never reads as a regression. Rests on `RecipeClosure.rawUnits_eq_cost`.

Liveness namespace — Mathlib permitted.
-/

namespace Formal.Liveness.ObtainProgress

open Formal.RecipeClosure

/-- The deepened obtain-progress witness: raw-material-unit-weighted owned count over a
node list (the target plus its transitive recipe closure). Mirrors the non-equipped
branch of Python `_obtain_progress`. -/
def obtainProgress (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat) (nodes : List Nat) : Nat :=
  (nodes.map (fun i => owned i * rawUnits r y fuel i)).sum

/-- On a list not containing `g`, the gather update is invisible — the mapped sum is
unchanged. -/
private theorem sum_gather_no_g (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat)
    (nodes : List Nat) (g k : Nat) (h : g ∉ nodes) :
    (nodes.map (fun i => (owned i + (if i = g then k else 0)) * rawUnits r y fuel i)).sum
      = (nodes.map (fun i => owned i * rawUnits r y fuel i)).sum := by
  apply congrArg List.sum
  apply List.map_congr_left
  intro i hi
  have hne : i ≠ g := fun he => h (he ▸ hi)
  simp [hne]

/-- Bumping the owned count of a node `g` (present once in `nodes`) by `k` raises the
witness by exactly `k * rawUnits r y fuel g`. The exact delta law the gather/strict-mono
corollaries rest on. -/
theorem obtainProgress_gather (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat)
    (nodes : List Nat) (g k : Nat) (hg : g ∈ nodes) (hnd : nodes.Nodup) :
    obtainProgress r y fuel (fun j => owned j + (if j = g then k else 0)) nodes
      = obtainProgress r y fuel owned nodes + k * rawUnits r y fuel g := by
  unfold obtainProgress
  induction nodes with
  | nil => exact absurd hg (List.not_mem_nil)
  | cons hd tl ih =>
    rw [List.nodup_cons] at hnd
    obtain ⟨hhd, htl⟩ := hnd
    simp only [List.map_cons, List.sum_cons]
    rcases List.mem_cons.mp hg with hgeq | hgtl
    · -- g is the head; the tail never mentions g (Nodup), so its sum is unchanged.
      subst hgeq
      rw [sum_gather_no_g r y fuel owned tl g k hhd, if_pos rfl]
      ring
    · -- g is in the tail; the head never mentions g, so its term is unchanged.
      have hhdne : hd ≠ g := fun he => hhd (he ▸ hgtl)
      rw [if_neg hhdne, ih hgtl htl]
      ring

/-- Acquiring material never lowers the witness: owned pointwise ↑ ⇒ witness ↑. Rules
out a spurious progress drop from gaining inventory. -/
theorem obtainProgress_mono (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned owned' : Nat → Nat)
    (nodes : List Nat) (h : ∀ i, owned i ≤ owned' i) :
    obtainProgress r y fuel owned nodes ≤ obtainProgress r y fuel owned' nodes := by
  unfold obtainProgress
  induction nodes with
  | nil => simp
  | cons hd tl ih =>
    simp only [List.map_cons, List.sum_cons]
    exact Nat.add_le_add (Nat.mul_le_mul_right _ (h hd)) ih

/-- Gathering one raw unit of a closure node with positive raw weight STRICTLY increases
the witness — the false-flat the shallow predecessor produced is impossible. -/
theorem obtainProgress_gather_strict (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat)
    (nodes : List Nat) (g : Nat) (hg : g ∈ nodes) (hnd : nodes.Nodup)
    (hpos : 0 < rawUnits r y fuel g) :
    obtainProgress r y fuel owned nodes
      < obtainProgress r y fuel (fun j => owned j + (if j = g then 1 else 0)) nodes := by
  rw [obtainProgress_gather r y fuel owned nodes g 1 hg hnd]
  omega

/-- Consuming `k` units of a node `c` (present once in `nodes`, with `k ≤ owned c`) lowers
the witness by exactly `k * rawUnits r y fuel c`. Dual of `obtainProgress_gather`; the craft
theorem pairs a production (+output) with this consumption (−inputs). -/
theorem obtainProgress_consume (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat)
    (nodes : List Nat) (c k : Nat) (hc : c ∈ nodes) (hnd : nodes.Nodup) (hk : k ≤ owned c) :
    obtainProgress r y fuel (fun j => owned j - (if j = c then k else 0)) nodes
      + k * rawUnits r y fuel c = obtainProgress r y fuel owned nodes := by
  unfold obtainProgress
  induction nodes with
  | nil => exact absurd hc (List.not_mem_nil)
  | cons hd tl ih =>
    rw [List.nodup_cons] at hnd
    obtain ⟨hhd, htl⟩ := hnd
    simp only [List.map_cons, List.sum_cons]
    rcases List.mem_cons.mp hc with hceq | hctl
    · subst hceq
      have htl_eq : (tl.map (fun i => (owned i - (if i = c then k else 0)) * rawUnits r y fuel i)).sum
          = (tl.map (fun i => owned i * rawUnits r y fuel i)).sum := by
        apply congrArg List.sum; apply List.map_congr_left
        intro i hi; have : i ≠ c := fun he => hhd (he ▸ hi); simp [this]
      rw [htl_eq, if_pos rfl, Nat.sub_mul]
      have : k * rawUnits r y fuel c ≤ owned c * rawUnits r y fuel c :=
        Nat.mul_le_mul_right _ hk
      omega
    · have hhdne : hd ≠ c := fun he => hhd (he ▸ hctl)
      rw [if_neg hhdne, Nat.sub_zero, Nat.add_assoc, ih hctl htl]

/-- **Craft neutrality (single-intermediate recipe).** Crafting one unit of `o` from a
recipe `r o = [(c, qty)]` — producing 1 `o`, consuming `qty` of its single child `c` —
leaves the witness UNCHANGED, because the raw-unit weight conserves: `rawUnits o = qty *
rawUnits c` (`rawUnits_top_eq_cost`, supplied as `hcons`). So smelting/crafting never
reads as a regression — the second half of the witness's faithfulness. Both `o` and `c`
are distinct closure nodes and the bot holds enough `c` to craft.

Covers the live boots chain exactly: copper_boots ← {copper_bar:8} and
copper_bar ← {copper_ore:10} are both single-intermediate. -/
theorem obtainProgress_craft_invariant (r : Recipe) (y : Nat → Nat) (fuel : Nat) (owned : Nat → Nat)
    (nodes : List Nat) (o c qty : Nat) (ho : o ∈ nodes) (hcm : c ∈ nodes) (hoc : o ≠ c)
    (hnd : nodes.Nodup) (hq : qty ≤ owned c)
    (hcons : rawUnits r y fuel o = qty * rawUnits r y fuel c) :
    obtainProgress r y fuel
        (fun j => (owned j + (if j = o then 1 else 0)) - (if j = c then qty else 0)) nodes
      = obtainProgress r y fuel owned nodes := by
  -- The output bump is invisible to the consume step (o ≠ c) and vice-versa, so the two
  -- deltas compose: +rawUnits o from producing o, −qty·rawUnits c from consuming c.
  have key := obtainProgress_consume r y fuel (fun j => owned j + (if j = o then 1 else 0))
    nodes c qty hcm hnd (by simp [hoc.symm]; exact hq)
  have prod := obtainProgress_gather r y fuel owned nodes o 1 ho hnd
  -- The goal's lambda IS the consume of the produced state (after beta); key/prod give the
  -- two deltas, hcons (rawUnits o = qty·rawUnits c) cancels them.
  simp only [] at key
  rw [hcons] at prod
  omega

end Formal.Liveness.ObtainProgress
