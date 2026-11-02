-- @concept: combat, monsters @property: dominance, totality
/-
Formal model of the pure core `winnable_cascade.winnable_farm_target_pure`
(`src/artifactsmmo_cli/ai/winnable_cascade.py`), read by
`gear_objective_context.farm_target`.

The function is a TOTAL two-arm precedence cascade picking the next
combat target:

  1. `task_monster` if present. This arm does not TEST winnability;
     the supplier (`Player._task_aligned_monster`) guarantees it by
     applying `_is_winnable` before passing a monster in. The comment
     here previously called the missing check intentional, justified by
     "a persistent loss loop is caught by the stuck/recovery backstop".
     That was wrong — the backstop's remedy is a countdown that expires
     whether or not anything changed, and live on 2026-08-20 a character
     went 0/42 against its task monster and the ladder killed the run.
     The theorems below are unaffected: `task_wins` states the
     PRECEDENCE, which was always the intended contract.
  2. `path_monster` if present AND `path_winnable` — the gear objective's
     `m*`, winnable exactly while its `L*` is held. Otherwise `none`: no
     fight is chosen for XP while a piece of `L*` is missing (spec
     2026-10-18 §2.4).

Plan C Task 4 deleted the third arm (a global winnable-monster pick the
player no longer supplied) and retired its two theorems
(`pick_wins_when_no_path`, `pick_wins_when_path_not_winnable`);
`path_result_was_winnable` lost its pick-arm hypothesis.

Pure decision; no float, no recursion. Inputs are a 3-tuple of
`Option String × Option String × Bool`.

No mathlib, no sorry/admit/native_decide. Axioms ⊆
{propext, Classical.choice, Quot.sound}.
-/

namespace Formal.WinnableCascade

/-- Cascade inputs. Mirrors `winnable_cascade.CascadeInputs`. -/
structure CascadeInputs where
  taskMonster : Option String
  pathMonster : Option String
  pathWinnable : Bool
  deriving Repr, DecidableEq

/-- Pure cascade. Mirrors `winnable_farm_target_pure`. -/
def winnableFarmTargetPure (i : CascadeInputs) : Option String :=
  match i.taskMonster with
  | some t => some t
  | none =>
    match i.pathMonster, i.pathWinnable with
    | some p, true => some p
    | _, _ => none

/-- Arm 1: task_monster, when set, wins unconditionally — the path arm
is NEVER consulted. This is a statement about PRECEDENCE, not about
beatability: the supplier is what guarantees a monster reaching this
arm is winnable. -/
theorem task_wins (i : CascadeInputs) (t : String)
    (h : i.taskMonster = some t) :
    winnableFarmTargetPure i = some t := by
  unfold winnableFarmTargetPure
  rw [h]

/-- Arm 2: when task is absent and the path monster is winnable, the
path monster is returned. -/
theorem path_wins_when_winnable (i : CascadeInputs) (p : String)
    (ht : i.taskMonster = none)
    (hp : i.pathMonster = some p)
    (hw : i.pathWinnable = true) :
    winnableFarmTargetPure i = some p := by
  unfold winnableFarmTargetPure
  rw [ht, hp, hw]

/-- No arm fires: with no task and a path monster that is not winnable
(`L*` not held), there is no target — no fight is chosen for XP. -/
theorem none_when_path_not_winnable (i : CascadeInputs)
    (ht : i.taskMonster = none)
    (hw : i.pathWinnable = false) :
    winnableFarmTargetPure i = none := by
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
check (the load-bearing safety of arm 2): if the result is `some p` AND
the task arm did not fire, then `pathMonster = some p` and
`pathWinnable = true`. -/
theorem path_result_was_winnable (i : CascadeInputs) (p : String)
    (ht : i.taskMonster = none)
    (heq : winnableFarmTargetPure i = some p) :
    i.pathMonster = some p ∧ i.pathWinnable = true := by
  unfold winnableFarmTargetPure at heq
  rw [ht] at heq
  cases hp : i.pathMonster with
  | none => rw [hp] at heq; exact absurd heq (by simp)
  | some q =>
    cases hw : i.pathWinnable with
    | false => rw [hp, hw] at heq; exact absurd heq (by simp)
    | true =>
      rw [hp, hw] at heq
      exact ⟨heq ▸ rfl, rfl⟩

/-- Idempotence under re-evaluation: a deterministic pure function.
Stated for the differential test pin. -/
theorem deterministic (i : CascadeInputs) :
    winnableFarmTargetPure i = winnableFarmTargetPure i := rfl

/-! ### Non-vacuity witnesses

Concrete instances exercising each arm — proves the theorems above are
not trivially satisfied by an empty domain. -/

/-- Witness: task arm fires. -/
def witness_task : CascadeInputs :=
  { taskMonster := some "chicken"
    pathMonster := some "wolf"
    pathWinnable := true }

example : winnableFarmTargetPure witness_task = some "chicken" := rfl

/-- Witness: path arm fires (task absent, path winnable). -/
def witness_path : CascadeInputs :=
  { taskMonster := none
    pathMonster := some "wolf"
    pathWinnable := true }

example : winnableFarmTargetPure witness_path = some "wolf" := rfl

/-- Witness: no arm fires (task absent, path present but NOT winnable).
The cascade does NOT return the non-winnable path monster even though it
is present. -/
def witness_path_not_winnable : CascadeInputs :=
  { taskMonster := none
    pathMonster := some "wolf"
    pathWinnable := false }

example : winnableFarmTargetPure witness_path_not_winnable = none := rfl

/-- Witness: cascade returns `none` when nothing is supplied. -/
def witness_none : CascadeInputs :=
  { taskMonster := none
    pathMonster := none
    pathWinnable := false }

example : winnableFarmTargetPure witness_none = none := rfl

end Formal.WinnableCascade
