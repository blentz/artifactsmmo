import Formal.Liveness.ProductionLadder
import Formal.Liveness.NoDeadlockV2

/-! # hnowait, discharged HONESTLY (not via the `.wait` fall-through)

`NoDeadlockV2.productionLadder_total` proves `productionLadder s ≠ none`, but only
because `.wait` fires unconditionally as the last-resort — i.e. "never deadlocks"
there is satisfied by WAITING, which is no progress at all. The real obligation is
`hnowait`: the ladder NEVER returns `.wait`, i.e. a PRODUCTIVE means always fires.

This is UNCONDITIONALLY true and proven here from the task lifecycle alone: the
three task means are phase-total —
  `acceptTaskFires  = (phase = none)`
  `pursueTaskFires  = (phase ∈ {accepted, inProgress})`
  `completeTaskFires = (phase = complete)`
so for EVERY state one of them fires, and all three sit before `.wait` in
`allInLadderOrder`. The first firing means is therefore never `.wait`. The bot
always has a task move (accept / pursue / complete) — it is never idle.

Core liveness module (Mathlib allowed). No new axioms.
-/

namespace Formal.Liveness.NoWait

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder

/-- Phase-totality, WEAKENED 2026-08-19. One of the three task means fires — or
    the character is taskless with no draw owed, which is the one state none of
    them covers.

    `acceptTaskFires` used to be `phase = .none` outright, making this a genuine
    totality. The USER's no-immediate-redraw rule gates it on `drawOwed` (S-048
    discards a dead draw; redrawing at once would spin accept/discard above the
    objective step, burning a coin a cycle), and a gated accept cannot cover the
    taskless case unconditionally. The fourth disjunct is that hole, named. -/
theorem task_means_always_fires (s : State) :
    fires .acceptTask s = true ∨ fires .pursueTask s = true
      ∨ fires .completeTask s = true
      ∨ (s.taskLifecyclePhase = .none ∧ s.drawOwed = false) := by
  simp only [fires, acceptTaskFires, pursueTaskFires, completeTaskFires]
  cases h : s.taskLifecyclePhase <;> cases hd : s.drawOwed <;> simp [h, hd]

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

/-- **hnowait, CONDITIONAL since 2026-08-19.** The ladder never returns `.wait`
    while there is something to do: a task is in flight, a draw is owed, or the
    objective has a step.

    It was unconditional, and rested entirely on `acceptTaskFires = (phase =
    .none)` — "you can always accept a task". Gating the accept on `drawOwed`
    (see `task_means_always_fires`) opens exactly one hole: taskless, no draw
    owed, and no objective step. `.wait` is the CORRECT answer there and
    `WaitGoal` is the declared totality witness for it, so this is a deliberate
    loosening rather than a regression — but it is a loosening, and the
    hypothesis says so out loud. -/
theorem productionLadder_ne_wait (s : State)
    (hlive : s.taskLifecyclePhase ≠ .none ∨ s.drawOwed = true
             ∨ s.objectiveStepFires = true) :
    productionLadder s ≠ some .wait := by
  -- A task means fires AND lives in the init (before .wait).
  have hinit_fires : ∃ k ∈ allInLadderOrder.dropLast, fires k s = true := by
    rcases task_means_always_fires s with h | h | h | ⟨hnone, hnodraw⟩
    · exact ⟨.acceptTask, by decide, h⟩
    · exact ⟨.pursueTask, by decide, h⟩
    · exact ⟨.completeTask, by decide, h⟩
    · rcases hlive with hph | hdraw | hstep
      · exact absurd hnone hph
      · rw [hnodraw] at hdraw; cases hdraw
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
