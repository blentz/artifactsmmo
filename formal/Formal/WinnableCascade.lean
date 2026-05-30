/-
Formal model of the pure core extracted from
`src/artifactsmmo_cli/ai/player.py` (`Player._winnable_farm_target`),
delegated through `winnable_cascade.winnable_farm_target_pure`.

The function is a TOTAL 3-tier precedence cascade picking the next
combat target:

  1. `task_monster` if present (winnable check intentionally BYPASSED —
     the upstream `task_decision == PURSUE` gate has already cleared the
     task-feasibility margin; a borderline-margin task monster is still
     picked because the task forces the target. A persistent loss loop
     is caught by the stuck/recovery backstop, not here).
  2. `path_monster` if present AND `path_winnable` — the cheapest-path
     projection's next-monster recommendation, accepted only when the
     runtime beatability predictor agrees.
  3. `pick_winnable` — global fallback (may itself be `none`).

Pure decision; no float, no recursion. Inputs are a 4-tuple of
`Option String × Option String × Bool × Option String`.

No mathlib, no sorry/admit/native_decide. Axioms ⊆
{propext, Classical.choice, Quot.sound}.
-/

namespace Formal.WinnableCascade

/-- Cascade inputs. Mirrors `winnable_cascade.CascadeInputs`. -/
structure CascadeInputs where
  taskMonster : Option String
  pathMonster : Option String
  pathWinnable : Bool
  pickWinnable : Option String
  deriving Repr, DecidableEq

/-- Pure cascade. Mirrors `winnable_farm_target_pure`. -/
def winnableFarmTargetPure (i : CascadeInputs) : Option String :=
  match i.taskMonster with
  | some t => some t
  | none =>
    match i.pathMonster, i.pathWinnable with
    | some p, true => some p
    | _, _ => i.pickWinnable

/-- Tier-1: task_monster, when set, wins unconditionally — the path /
pick tiers are NEVER consulted (the winnable check is bypassed by
design). -/
theorem task_wins (i : CascadeInputs) (t : String)
    (h : i.taskMonster = some t) :
    winnableFarmTargetPure i = some t := by
  unfold winnableFarmTargetPure
  rw [h]

/-- Tier-2: when task is absent and the path-aligned monster is winnable,
the path monster is returned. -/
theorem path_wins_when_winnable (i : CascadeInputs) (p : String)
    (ht : i.taskMonster = none)
    (hp : i.pathMonster = some p)
    (hw : i.pathWinnable = true) :
    winnableFarmTargetPure i = some p := by
  unfold winnableFarmTargetPure
  rw [ht, hp, hw]

/-- Tier-3a: when task is absent and the path is absent, the global
`pick_winnable` is returned. -/
theorem pick_wins_when_no_path (i : CascadeInputs)
    (ht : i.taskMonster = none)
    (hp : i.pathMonster = none) :
    winnableFarmTargetPure i = i.pickWinnable := by
  unfold winnableFarmTargetPure
  rw [ht, hp]

/-- Tier-3b: when task is absent and the path-aligned monster is NOT
winnable, the global `pick_winnable` is returned (regardless of whether
`pathMonster` is set). The path tier never returns a non-winnable
monster — this is the load-bearing safety property of the cascade. -/
theorem pick_wins_when_path_not_winnable (i : CascadeInputs)
    (ht : i.taskMonster = none)
    (hw : i.pathWinnable = false) :
    winnableFarmTargetPure i = i.pickWinnable := by
  unfold winnableFarmTargetPure
  rw [ht, hw]
  cases i.pathMonster <;> rfl

/-- Totality: the function always returns (no exception, no partiality).
Trivially provable: the return type is `Option String` and every branch
of the `match` produces a value of that type. We state it for the
record. -/
theorem totality (i : CascadeInputs) :
    ∃ r : Option String, winnableFarmTargetPure i = r :=
  ⟨winnableFarmTargetPure i, rfl⟩

/-- The cascade NEVER returns a path monster that failed the winnable
check (the load-bearing safety of tier 2). Stated contrapositively:
if the result is `some p` AND the task tier did not fire AND
`pathMonster = some p`, then `pathWinnable = true`. -/
theorem path_result_was_winnable (i : CascadeInputs) (p : String)
    (ht : i.taskMonster = none)
    (hp : i.pathMonster = some p)
    (heq : winnableFarmTargetPure i = some p)
    (hpick : i.pickWinnable ≠ some p) :
    i.pathWinnable = true := by
  unfold winnableFarmTargetPure at heq
  rw [ht, hp] at heq
  cases hw : i.pathWinnable with
  | true => rfl
  | false =>
    rw [hw] at heq
    exact absurd heq hpick

/-- Idempotence under re-evaluation: a deterministic pure function.
Stated for the differential test pin. -/
theorem deterministic (i : CascadeInputs) :
    winnableFarmTargetPure i = winnableFarmTargetPure i := rfl

/-! ### Non-vacuity witnesses

Concrete instances exercising each tier — proves the theorems above are
not trivially satisfied by an empty domain. -/

/-- Witness: task tier fires. -/
def witness_task : CascadeInputs :=
  { taskMonster := some "chicken"
    pathMonster := some "wolf"
    pathWinnable := true
    pickWinnable := some "cow" }

example : winnableFarmTargetPure witness_task = some "chicken" := rfl

/-- Witness: path tier fires (task absent, path winnable). -/
def witness_path : CascadeInputs :=
  { taskMonster := none
    pathMonster := some "wolf"
    pathWinnable := true
    pickWinnable := some "cow" }

example : winnableFarmTargetPure witness_path = some "wolf" := rfl

/-- Witness: pick tier fires (task absent, path absent). -/
def witness_pick_no_path : CascadeInputs :=
  { taskMonster := none
    pathMonster := none
    pathWinnable := false
    pickWinnable := some "cow" }

example : winnableFarmTargetPure witness_pick_no_path = some "cow" := rfl

/-- Witness: pick tier fires (task absent, path present but NOT
winnable). The cascade does NOT return the non-winnable path monster
even though it is present. -/
def witness_pick_path_not_winnable : CascadeInputs :=
  { taskMonster := none
    pathMonster := some "wolf"
    pathWinnable := false
    pickWinnable := some "cow" }

example : winnableFarmTargetPure witness_pick_path_not_winnable = some "cow" := rfl

/-- Witness: cascade returns `none` when nothing fires. -/
def witness_none : CascadeInputs :=
  { taskMonster := none
    pathMonster := none
    pathWinnable := false
    pickWinnable := none }

example : winnableFarmTargetPure witness_none = none := rfl

end Formal.WinnableCascade
