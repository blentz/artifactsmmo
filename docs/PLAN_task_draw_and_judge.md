# PLAN — the draw-and-judge task rule (S-047 … S-051)

**Spec:** `docs/spec_cycle_economy/SPEC.md`, clauses S-047 to S-051, plus D-11's
level-appropriate-assignment fact.

**Why this is not the band epic.** S-051: accepting a task belongs to a COURSE
rather than competing with one. A means that must out-rank the objective step will
never fire — the discretionary band is selected in 133 of 63,310 cycles, 0.21% — but
a step that is nearly free and strictly increases the value of work already chosen
does not have to out-rank anything. `docs/PLAN_band_unification.md` stays stopped.

## What is measured, and what is therefore true

* Four of five live characters are grinding a monster that IS a task code —
  `pig` and `highwayman` pay 300 gold + 4 coins, `red_slime` 200 + 3. Those kills
  are ones they would make anyway.
* The bot has held a task in **0 of 63,310 cycles**. `ACCEPT_TASK` sits in the
  discretionary band, so nothing downstream of it has ever run.
* Step-suppression on a held task is NARROW and items-only: `_suppress_step_for_task`
  defers a step whose craft would eat the task's reserved materials. Holding a
  monsters task does not stop a grind, so S-049 does not conflict with it.

## Increments

0. **The judgement predicate** — ✅ DONE, `ai/task_alignment.task_advances_progression`.
   S-047's one question: does the held task's target advance the character's level
   (monsters: `xp_per_kill > 0`) or a skill (items: `skill_xp_positive` over
   `producing_requirement`)? Neither band constant is restated locally.
1. **Discard a useless draw (S-048).** Route `task_advances_progression == False` to
   the existing `TaskCancelAction`. ⚠️ Blocked once per character by the coin
   bootstrap below.
2. **Accept as part of a course (S-051).** ⛔ ATTEMPTED 2026-08-19 AND BACKED OUT.
   The promotion is unsafe as stated; see "The redraw loop" below. Increments 3
   and 4 are blocked behind it, because nothing ever accepts.
3. **The held-task premium (S-050).** A course whose work overlaps the held task's
   target is worth more by the reward that work would complete. This is S-018 read
   from the other side and it is what makes S-049's "keep it" pay.
4. **Re-measure.** With acceptance live, the learning DB finally gets task rows —
   which is the only way the ASSIGNMENT distribution S-014 needs can ever be
   observed. It is published nowhere.

## The redraw loop — why increment 2 was backed out

Moving `ACCEPT_TASK` into the COLLECT band puts it ABOVE the objective step, next
to `TASK_CANCEL` which is already there. With S-048 firing the cancel on any grey
draw, that produces:

> no task → **accept** → the draw is grey → **discard** (1 coin) → no task →
> **accept** → …

Both rungs sit above the step, so nothing else runs while it spins. It costs one
coin and two actions per iteration and self-terminates only when the coins run out
and S-052 forces the draw to be worked. Bounded, and still a livelock that preempts
all progress for as long as coins last.

**The Lean liveness proof refused it, which is the proof doing its job.**
`descends_taskCancel` holds because cancelling moves the task phase from present to
none, descending the measure; accepting moves it the other way, so `acceptTask`
above `.objectiveStep` needs a descent argument it does not have. `Measure.lean`
already names the hazard — `accept_cancel_loop_bound` exists because
"taskCancelFires would trigger early and re-enter the `.none → .accepted` cycle
indefinitely". The measure cannot see the COIN, which is the quantity that actually
decreases.

Reverted: `MeansKind.allInLadderOrder`, `UnconditionalDescent`'s prefix/tail split,
the `formal/sim` mirror, the band tuples, and the worth-gate exemption that went
with them. The tree is green and `ACCEPT_TASK` is back where it was — unreachable.

**Three ways forward, and the choice is a design decision:**

* **Make the coin the measure.** Honest — it IS the decreasing quantity — and it is
  real Lean work: a new descent lemma keyed on `taskCoinsTotal`, plus reshaping the
  21-hypothesis bundle in `PursueTaskSelection`.
* **Do not redraw immediately.** Discard, then resume the course, and accept again
  only at the course's next natural boundary. Kills the loop without touching the
  measure, at the cost of a rule about WHEN to accept that nothing states yet.
* **Accept only when a coin is spare**, so a draw is never taken that cannot be
  judged. Simplest, and it inverts S-052: the first task is then never drawn at all,
  which contradicts the decision to work it.

## The decision already taken

**S-048's discard costs a task coin, and coins come only from completing tasks.** At
zero coins the discard is unavailable, so the FIRST draw must be kept whatever it
is. The rule is unreachable exactly once per character, at the moment it would first
apply. Two ways out, and the spec deliberately picks neither:

* **Work the first task even if grey** to buy the coin that makes the rule
  available. Costs the grey work once; every later draw is judgeable.
* **Carry it dead** and wait for a coin from elsewhere. There is no elsewhere today
  — `tasks_coin` has exactly one source, and it is completing a task.

The exposure either way is bounded: a held task blocks no other course. The first is
a one-time cost with a permanent benefit; the second never terminates on its own.
