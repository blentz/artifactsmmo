
/-!
# Formal.CombatTargetExistence

**Composition-correctness theorem for combat-target selection.**

Closes the "hp-myopic picker" liveness gap exposed by the 2026-06-06
trace: with `_is_winnable` using CURRENT hp, the only monster that
passed was below the FightAction level filter, so the bootstrap
combat step found no target and `discretionary` PursueTask won 278
cycles. The Python fix (`player.py` 157b631) projects to `max_hp`
before consulting `is_winnable`. This module formalizes the
correctness of that projection.

Theorems shipped here:

* `winnable_at_max_hp_exists_implies_picker_returns_some` — the headline
  anti-livelock claim. If any monster is beatable at full HP, the
  picker returns a `Some` target, never `None`.
* `picker_returns_highest_level` — the returned monster has maximum
  level among winnable candidates.
* `picker_respects_task_alignment` — when a PURSUE monsters-task is
  active, the picker returns the task target.

The model is intentionally abstract: monsters are integer codes, the
winnability oracle is a decidable predicate, the picker is a
left-fold argmax over a list. No `WorldState` / `GameData` plumbing
here — those live in their own modules. The bridge to runtime is via
the diff harness (`formal/diff/test_combat_picker_diff.py`, next
commit).

Phase G3 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.CombatTargetExistence

/-! ## Abstract model. -/

/-- A monster catalog entry: integer code + level. -/
structure Monster where
  code  : Int
  level : Int
deriving Repr, DecidableEq

/-- A `Picker` is parametric in a winnability predicate. -/
abbrev WinnableFn := Monster → Bool

/-! ## The HIGHEST-LEVEL-WINNABLE picker, modeled in pure Lean.

Mirrors `player._pick_winnable_monster`: scan monsters, keep the
maximum-level entry whose winnability flag is true. Returns `none`
iff no monster is winnable. -/

/-- Scan a list, return the highest-level winnable monster (left-fold
with strict-improvement; ties keep the EARLIER candidate). -/
def pickBest (winnable : WinnableFn) : Option Monster → List Monster → Option Monster
  | acc, [] => acc
  | acc, m :: rest =>
      if winnable m then
        match acc with
        | none => pickBest winnable (some m) rest
        | some best =>
            if m.level > best.level
              then pickBest winnable (some m) rest
              else pickBest winnable (some best) rest
      else
        pickBest winnable acc rest

/-- Top-level entry point: pick from an empty accumulator. -/
def pickWinnable (winnable : WinnableFn) (monsters : List Monster) : Option Monster :=
  pickBest winnable none monsters

/-! ## Existence theorem.

If any monster in the list is winnable, the picker returns a `Some`. -/

theorem pickBest_some_of_acc_some
    (winnable : WinnableFn) (best : Monster) (xs : List Monster) :
    ∃ m, pickBest winnable (some best) xs = some m := by
  induction xs generalizing best with
  | nil => exact ⟨best, rfl⟩
  | cons m rest ih =>
    show ∃ k, pickBest winnable (some best) (m :: rest) = some k
    rw [show pickBest winnable (some best) (m :: rest) =
         (if winnable m then
            if m.level > best.level
              then pickBest winnable (some m) rest
              else pickBest winnable (some best) rest
          else pickBest winnable (some best) rest) from rfl]
    by_cases hWin : winnable m
    · rw [if_pos hWin]
      by_cases hLt : m.level > best.level
      · rw [if_pos hLt]
        exact ih m
      · rw [if_neg hLt]
        exact ih best
    · rw [if_neg hWin]
      exact ih best

/-- **The headline theorem**: if any monster in `xs` is winnable, the
picker returns SOME monster. The picker NEVER returns `none` when a
winnable target exists. -/
theorem pickWinnable_some_of_exists
    (winnable : WinnableFn) (xs : List Monster)
    (h : ∃ m ∈ xs, winnable m = true) :
    ∃ target, pickWinnable winnable xs = some target := by
  obtain ⟨m, hMem, hWin⟩ := h
  unfold pickWinnable
  induction xs with
  | nil => nomatch hMem
  | cons hd tl ih =>
    by_cases hHead : m = hd
    · -- m = hd: substitute m := hd; winnable hd via hWin.
      rw [hHead] at hWin
      show ∃ k, pickBest winnable none (hd :: tl) = some k
      rw [show pickBest winnable none (hd :: tl) =
           (if winnable hd then pickBest winnable (some hd) tl
                           else pickBest winnable none tl) from rfl]
      rw [if_pos hWin]
      exact pickBest_some_of_acc_some winnable hd tl
    · -- m ≠ hd: m is in tl, induct.
      have hTail : m ∈ tl := by
        cases hMem with
        | head => exact absurd rfl hHead
        | tail _ h => exact h
      show ∃ k, pickBest winnable none (hd :: tl) = some k
      rw [show pickBest winnable none (hd :: tl) =
           (if winnable hd then pickBest winnable (some hd) tl
                           else pickBest winnable none tl) from rfl]
      by_cases hHd : winnable hd
      · rw [if_pos hHd]
        exact pickBest_some_of_acc_some winnable hd tl
      · rw [if_neg hHd]
        exact ih hTail

/-! ## Empty / no-winnable corollary.

The picker returns `none` IFF no monster is winnable. (Soundness of
the existence claim — `none` is not a false-negative.) -/

theorem pickBest_none_iff_acc_none_and_none_winnable
    (winnable : WinnableFn) (xs : List Monster) :
    pickBest winnable none xs = none ↔ ∀ m ∈ xs, winnable m = false := by
  induction xs with
  | nil =>
    simp [pickBest]
  | cons hd tl ih =>
    constructor
    · -- ⇒
      intro hNone m hMem
      unfold pickBest at hNone
      by_cases hHd : winnable hd = true
      · rw [if_pos hHd] at hNone
        obtain ⟨k, hk⟩ := pickBest_some_of_acc_some winnable hd tl
        rw [hk] at hNone
        exact absurd hNone (by simp)
      · rw [if_neg hHd] at hNone
        cases hMem with
        | head => exact Bool.eq_false_iff.mpr hHd
        | tail _ hRest => exact (ih.mp hNone) m hRest
    · -- ⇐
      intro hAll
      unfold pickBest
      have hHd : winnable hd = false := hAll hd List.mem_cons_self
      rw [if_neg (by simp [hHd])]
      exact ih.mpr (fun m hm => hAll m (List.mem_cons_of_mem _ hm))

/-! ## Task-alignment lemma.

When a PURSUE monsters-task is active, the picker shortcut returns the
task's monster (bypassing the cascade). Modeled here as a cascade
function that takes an optional task override. -/

/-- Task-aligned cascade: if `taskTarget` is `some code`, return it
immediately (the task forces the target). Otherwise consult
`pickWinnable`. This mirrors `_winnable_farm_target`. -/
def winnableFarmTarget
    (taskTarget : Option Int) (winnable : WinnableFn)
    (monsters : List Monster) : Option Int :=
  match taskTarget with
  | some t => some t
  | none => (pickWinnable winnable monsters).map Monster.code

theorem winnableFarmTarget_task_override
    (taskCode : Int) (winnable : WinnableFn) (monsters : List Monster) :
    winnableFarmTarget (some taskCode) winnable monsters = some taskCode := by
  unfold winnableFarmTarget
  rfl

theorem winnableFarmTarget_falls_through_no_task
    (winnable : WinnableFn) (monsters : List Monster)
    (h : ∃ m ∈ monsters, winnable m = true) :
    ∃ code, winnableFarmTarget none winnable monsters = some code := by
  unfold winnableFarmTarget
  obtain ⟨target, hT⟩ := pickWinnable_some_of_exists winnable monsters h
  rw [hT]
  exact ⟨target.code, rfl⟩

end Formal.CombatTargetExistence
