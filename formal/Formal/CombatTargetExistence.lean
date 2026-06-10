-- @concept: combat, monsters @property: reachability, safety

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

**P0 revision (2026-06-09)**: the production picker is now
WINDOW-PREFERRED WITH LIVENESS FALLBACK (`pickWinnableWindowed`):

  1. PREFERRED — highest-level winnable monster in the FightAction
     level window `[max(1, L-1), L+2]`.
  2. FALLBACK — when the window is empty of winnable monsters, the
     highest-level winnable monster with `xp_per_kill > 0` that is
     still under the `L+2` suicide guard.
  3. `none` only when nothing winnable grants XP — a true combat
     deadlock (gear progression is then the only path).

The old window-only picker returned `none` FOREVER at level 4 when the
only stat-winnable monsters were L1/L2 (below the window) — the P0
no-combat deadlock.

Theorems shipped here:

* `pickWinnableWindowed_some_of_winnable_xp_positive` — the headline
  anti-livelock claim, TRUE of production: if any winnable monster has
  positive XP (and is under the suicide guard), the picker returns a
  `Some` target, never `none`.
* `pickWinnableWindowed_prefers_window` — when the window holds a
  winnable monster, the result comes from the window tier.
* `pickWinnable_some_of_exists` / `pickBest_*` — the single-tier argmax
  lemmas the windowed picker is built from.
* `winnableFarmTarget_task_override` — when a PURSUE monsters-task is
  active, the cascade returns the task target.

The model is intentionally abstract: monsters are integer codes, the
winnability / xp oracles are decidable predicates, each tier is a
left-fold argmax over a list. No `WorldState` / `GameData` plumbing
here — those live in their own modules. The bridge to runtime is the
diff harness (`formal/diff/test_combat_picker_diff.py`) against the
Python pure core `ai/combat_picker.pick_winnable_monster_pure`.

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

/-! ## Window-preferred picker with liveness fallback (P0 2026-06-09).

Mirrors the revised `player._pick_winnable_monster` /
`combat_picker.pick_winnable_monster_pure`. -/

/-- The FightAction level window: `max(1, L-1) ≤ level ≤ L+2`. -/
def inWindow (playerLevel : Int) (m : Monster) : Bool :=
  decide (max 1 (playerLevel - 1) ≤ m.level ∧ m.level ≤ playerLevel + 2)

/-- The suicide-guard upper bound only (the fallback tier's level filter —
the lower bound is replaced by the xp>0 oracle). -/
def notOverleveled (playerLevel : Int) (m : Monster) : Bool :=
  decide (m.level ≤ playerLevel + 2)

/-- Window-preferred picker: try the window tier; when it is empty of
winnable monsters, fall back to the highest-level winnable monster with
positive XP under the suicide guard. -/
def pickWinnableWindowed (playerLevel : Int) (winnable xpPos : WinnableFn)
    (monsters : List Monster) : Option Monster :=
  match pickWinnable (fun m => winnable m && inWindow playerLevel m) monsters with
  | some best => some best
  | none =>
      pickWinnable
        (fun m => winnable m && xpPos m && notOverleveled playerLevel m) monsters

/-- **The headline theorem (TRUE of production)**: if any monster is
winnable with positive XP under the suicide guard, the windowed picker
returns SOME target. The fallback tier makes this nearly definitional —
and it is exactly the claim the P0 deadlock violated (window-only picker
returned `none` while chicken/yellow_slime were winnable and XP-positive). -/
theorem pickWinnableWindowed_some_of_winnable_xp_positive
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : ∃ m ∈ xs, winnable m = true ∧ xpPos m = true ∧
                   notOverleveled playerLevel m = true) :
    ∃ target, pickWinnableWindowed playerLevel winnable xpPos xs = some target := by
  unfold pickWinnableWindowed
  cases hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs with
  | some best => exact ⟨best, rfl⟩
  | none =>
      obtain ⟨m, hMem, hW, hX, hO⟩ := h
      have hFall :
          ∃ t, pickWinnable
            (fun m => winnable m && xpPos m && notOverleveled playerLevel m) xs
            = some t :=
        pickWinnable_some_of_exists _ xs ⟨m, hMem, by simp [hW, hX, hO]⟩
      obtain ⟨t, hT⟩ := hFall
      exact ⟨t, hT⟩

/-- When the window tier finds a winnable monster, the windowed picker
returns the window tier's answer (the fallback is never consulted). -/
theorem pickWinnableWindowed_prefers_window
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (best : Monster)
    (hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs
            = some best) :
    pickWinnableWindowed playerLevel winnable xpPos xs = some best := by
  unfold pickWinnableWindowed
  rw [hWin]

/-- `none` is honest: the windowed picker returns `none` only when NO
monster is simultaneously winnable, XP-positive, and under the suicide
guard — a true combat deadlock. -/
theorem pickWinnableWindowed_none_implies_no_viable_target
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (hNone : pickWinnableWindowed playerLevel winnable xpPos xs = none) :
    ∀ m ∈ xs, (winnable m && xpPos m && notOverleveled playerLevel m) = false := by
  unfold pickWinnableWindowed at hNone
  cases hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs with
  | some best => rw [hWin] at hNone; exact absurd hNone (by simp)
  | none =>
      rw [hWin] at hNone
      exact (pickBest_none_iff_acc_none_and_none_winnable _ xs).mp hNone

/-! ## Task-alignment lemma.

When a PURSUE monsters-task is active, the picker shortcut returns the
task's monster (bypassing the cascade). Modeled here as a cascade
function that takes an optional task override. -/

/-- Task-aligned cascade: if `taskTarget` is `some code`, return it
immediately (the task forces the target). Otherwise consult the
window-preferred-with-fallback picker. This mirrors
`_winnable_farm_target`. -/
def winnableFarmTarget
    (playerLevel : Int) (taskTarget : Option Int) (winnable xpPos : WinnableFn)
    (monsters : List Monster) : Option Int :=
  match taskTarget with
  | some t => some t
  | none => (pickWinnableWindowed playerLevel winnable xpPos monsters).map Monster.code

theorem winnableFarmTarget_task_override
    (playerLevel taskCode : Int) (winnable xpPos : WinnableFn)
    (monsters : List Monster) :
    winnableFarmTarget playerLevel (some taskCode) winnable xpPos monsters
      = some taskCode := by
  unfold winnableFarmTarget
  rfl

theorem winnableFarmTarget_falls_through_no_task
    (playerLevel : Int) (winnable xpPos : WinnableFn) (monsters : List Monster)
    (h : ∃ m ∈ monsters, winnable m = true ∧ xpPos m = true ∧
                         notOverleveled playerLevel m = true) :
    ∃ code, winnableFarmTarget playerLevel none winnable xpPos monsters
              = some code := by
  unfold winnableFarmTarget
  obtain ⟨target, hT⟩ :=
    pickWinnableWindowed_some_of_winnable_xp_positive playerLevel winnable xpPos monsters h
  rw [hT]
  exact ⟨target.code, rfl⟩

end Formal.CombatTargetExistence
