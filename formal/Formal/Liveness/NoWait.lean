import Formal.Liveness.ProductionLadder
import Formal.Liveness.NoDeadlockV2

/-! # hnowait, discharged HONESTLY (not via the `.wait` fall-through)

`NoDeadlockV2.productionLadder_total` proves `productionLadder s ≠ none`, but only
because `.wait` fires unconditionally as the last-resort — i.e. "never deadlocks"
there is satisfied by WAITING, which is no progress at all. The real obligation is
`hnowait`: the ladder NEVER returns `.wait`, i.e. a PRODUCTIVE means always fires.

It holds while a task is in flight or the objective has a step: the two task
means left on the ladder cover every held task —
  `pursueTaskFires  = (phase ∈ {accepted, inProgress})`
  `completeTaskFires = (phase = complete)`
and both, like `.objectiveStep`, sit before `.wait` in `allInLadderOrder`.

THE TASKLESS CASE MOVED, it did not vanish (Phase 5-2c-iii-c-2 #3). Taking a
draw was the ACCEPT_TASK rung; it is now the task objective's step, inside
`.objectiveStep`: an owed draw makes `decisions.root._task_root` offer
`ReachTaskOutcome(None)`, so `objectiveStepFires` holds whenever a draw is owed
(pinned in production by `test_an_owed_draw_offers_the_objective`). The model's
`objectiveStepFires` is opaque, so that link lives on the production side.

Core liveness module (Mathlib allowed). No new axioms.
-/

namespace Formal.Liveness.NoWait

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder

/-- Phase-totality over a HELD task: pursue or complete fires, or the character
    holds no task. (Until Phase 5-2c-iii-c-2 #3 an `acceptTask` disjunct also
    covered the taskless state with a draw owed; that draw is now the task
    objective's step, inside `.objectiveStep` — see the module docstring.) -/
theorem task_means_always_fires (s : State) :
    fires .pursueTask s = true
      ∨ fires .completeTask s = true
      ∨ s.taskLifecyclePhase = .none := by
  simp only [fires, pursueTaskFires, completeTaskFires]
  cases h : s.taskLifecyclePhase <;> simp

/-- Generic: a member whose body is `some` makes `findSome?` non-`none`. -/
theorem findSome?_ne_none_of_mem {α β : Type} {f : α → Option β} {l : List α}
    {a : α} (hmem : a ∈ l) {b : β} (hfa : f a = some b) :
    l.findSome? f ≠ none := by
  intro hnone
  rw [List.findSome?_eq_none_iff] at hnone
  exact absurd (hnone a hmem) (by rw [hfa]; simp)

private noncomputable def f (s : State) : MeansKind → Option MeansKind :=
  fun k => if fires k s then some k else none

/-- `allInLadderOrder` is its init ++ the trailing `.wait`. -/
theorem ladder_split : allInLadderOrder = allInLadderOrder.dropLast ++ [MeansKind.wait] := by
  decide

theorem wait_notin_init : MeansKind.wait ∉ allInLadderOrder.dropLast := by decide

/-- **hnowait, CONDITIONAL.** The ladder never returns `.wait` while a task is
    in flight or the objective has a step.

    An owed draw is no longer its own disjunct (Phase 5-2c-iii-c-2 #3): it is
    the task objective's step, so in production it implies `objectiveStepFires`
    (module docstring). Taskless with no objective step is the one hole, and
    `.wait` is the CORRECT answer there — `WaitGoal` is the declared totality
    witness for it. -/
theorem productionLadder_ne_wait (s : State)
    (hlive : s.taskLifecyclePhase ≠ .none
             ∨ s.objectiveStepFires = true) :
    productionLadder s ≠ some .wait := by
  -- A task means fires AND lives in the init (before .wait).
  have hinit_fires : ∃ k ∈ allInLadderOrder.dropLast, fires k s = true := by
    rcases task_means_always_fires s with h | h | hnone
    · exact ⟨.pursueTask, by decide, h⟩
    · exact ⟨.completeTask, by decide, h⟩
    · rcases hlive with hph | hstep
      · exact absurd hnone hph
      · exact ⟨.objectiveStep, by decide, by simp [fires, objectiveStepFires, hstep]⟩
  obtain ⟨k, hkmem, hkf⟩ := hinit_fires
  -- so the init's findSome? is `some b` for some firing init member b.
  have hne : allInLadderOrder.dropLast.findSome? (f s) ≠ none :=
    findSome?_ne_none_of_mem hkmem (b := k) (by simp [f, hkf])
  cases hi : allInLadderOrder.dropLast.findSome? (f s) with
  | none => exact absurd hi hne
  | some b =>
    -- b comes from the init, so b ≠ .wait.
    have hbmem : b ∈ allInLadderOrder.dropLast := by
      have := List.findSome?_eq_some_iff.mp hi
      obtain ⟨pre, a, post, hsp, hb, _⟩ := this
      have ha : a = b := by
        by_cases hfa : fires a s
        · simp [f, hfa] at hb; exact hb
        · simp [f, hfa] at hb
      rw [hsp]; rw [ha] at *; exact List.mem_append.mpr (Or.inr (List.mem_cons_self))
    have hbne : b ≠ .wait := fun h => wait_notin_init (h ▸ hbmem)
    -- productionLadder = findSome? over (init ++ [wait]) = some b (init already hits).
    unfold productionLadder
    rw [ladder_split, List.findSome?_append]
    show ((allInLadderOrder.dropLast.findSome? (f s)).or _) ≠ some .wait
    rw [hi]
    simpa using fun h => hbne (Option.some.inj h)

end Formal.Liveness.NoWait
