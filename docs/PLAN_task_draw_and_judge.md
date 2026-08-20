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
3. **The held-task premium (S-050).** ✅ ALREADY BUILT, and I claimed otherwise
   once — the correction is worth keeping. `GamePlayer._task_aligned_monster` +
   `_winnable_farm_target`'s cascade already make a held PURSUE monsters-task
   force the grind target, which IS "a course sharing the task's target wins",
   and `test_pursue_monster_task_retargets_grind` has pinned it all along.
   `projections.project_task_completion` already values the held task from the
   API reward (`task_gold_reward` / `task_coin_reward`), not a hardcoded figure.

   Verified live 2026-08-19 with a task injected into each character's real
   state: Robby's grind moves `pig -> chicken`, Lor's `red_slime -> chicken`, and
   `draw_owed` reads False while the task is held — the no-redraw rule holding.

   **What is genuinely absent is the VALUATION half, not the behaviour.** The
   objective's ranking (`branch_ranking` / `J`) does not add the task's reward to
   a course sharing its target, so the premium cannot tip a choice BETWEEN
   courses — only the already-chosen grind is retargeted. Pricing it needs the
   reward in cycles, which needs S-046's rate, which is inert until a sell route
   exists (every buyer is an event NPC). So this is blocked behind gold, not
   behind tasks.
4. **Re-measure.** With acceptance live, the learning DB finally gets task rows —
   which is the only way the ASSIGNMENT distribution S-014 needs can ever be
   observed. It is published nowhere.

## First live run — the rung works, and the premise does not

173 cycles, five characters, ~40 minutes (learning.db `cycles`, 2026-08-20T01:14
to 01:54). Not the trace files, which are not durable.

**What worked.** All five accepted a task, once each — the first `AcceptTask`
selections in 63,483 recorded cycles. The gate, the promotion and the per-course
draw all behaved.

**What the draws actually were.** Five of five were MONSTERS tasks, and every one
is enormous:

| character | task | kills | reward | gold/kill | advances? |
|---|---|---|---|---|---|
| Robby | `rat` | 107 | 300g + 4 coins | 2.8 | yes |
| R2D2 | `pig` | 137 | 300g + 4 coins | 2.2 | yes |
| C3P0 | `pig` | 104 | 300g + 4 coins | 2.9 | yes |
| HAL | `sheep` | 317 | 200g + 3 coins | 0.6 | **no (grey)** |
| Lor | `yellow_slime` | 185 | 200g + 3 coins | 1.1 | **no (grey)** |

`task_total` of 104–317 is an order of magnitude above what this plan assumed. At
the calibrated ~52 cycles/hour/character, HAL's sheep task is roughly SIX HOURS of
kills for 200 gold.

**PROGRESS IS ZERO IN ALL 173 CYCLES, AND THE CAUSE IS STRUCTURAL.** `PURSUE_TASK`
— the rung that pursues a held task — is ITEMS-ONLY:

```python
if kind is MeansKind.PURSUE_TASK:
    return (state.task_type == "items" and ...)
```

A MONSTERS task has no rung that pursues it. Its only mechanism is the grind
retarget (`_task_aligned_monster` → `_winnable_farm_target`), which only bites
when the objective is already running a character-XP grind. All five characters
are doing GEAR work — `GatherMaterials(hardwood_plank)`, `UpgradeEquipment`,
`SupplyBank` — so the retarget never applies and the task is inert annotation.

**So S-052 is not honoured in practice.** "A task that cannot be discarded is
worked": they cannot discard (0 coins, never completed one) and they are not
working it. They carry it dead — the outcome the USER's decision explicitly
rejected. The clause is implemented as "do not cancel without a coin"; nothing
makes the work happen.

**And the epic's premise does not hold as stated.** "The demanded kills are ones
they would make anyway" was measured against characters whose objective was a
grind. These five are chasing gear, so the overlap is zero and the task is pure
added cost. The synergy is real (it was measured) but CONDITIONAL on the objective
being a grind — and that condition is not part of the accept decision.

**Three ways to close it, and the choice is the USER's:**

* **Owe a draw only while the objective is a character-XP grind.** Smallest, and
  closest to the stated intent — "tasks are ideal as SYNERGISTIC goals". The
  accept gate already exists; this narrows when it arms. Characters chasing gear
  simply do not draw.
* **Give monsters tasks a pursuit rung**, the twin of items-only `PURSUE_TASK`.
  Makes the task real work in its own right — which the USER called desirable only
  when the rewards are needed, so it wants the reward valuation S-046 blocks.
* **Judge the SIZE at draw time.** 317 kills for 200 gold is a bad trade at any
  overlap; S-047 currently asks only whether the target is grey, not whether the
  demand is proportionate.

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

**USER chose "do not redraw immediately" (2026-08-19). Investigating how to build
it turned up two things that change what that costs.**

**1. The redraw rule does not, by itself, discharge the proof obligation.**
`fMeasure`'s third lex slot is `phasePresent := b2n (phase ≠ .none)`, and nothing
earlier changes on an accept — so accepting STRICTLY INCREASES the measure. Any rung
above `.objectiveStep` that CREATES a task is unprovable under
`UnconditionalDescent`, whose theorem shape is "every selected rung descends",
whatever rule governs when the accept fires. Removing the livelock and discharging
the descent are two different problems.

**2. The model already has machinery for exactly this hazard, and it rests on an
assumption reality does not honour.** `State` carries `taskPool` and
`taskCodesSeen`, added to discharge `accept_cancel_loop_bound` by pigeonhole: each
`.taskCancel` pushes the cancelled code onto `taskCodesSeen`, and `.acceptTask`
draws a code NOT already seen (`CycleStepDC`:
`taskPool.find? (fun c => ¬ (c ∈ s.taskCodesSeen))`), so after `|taskPool|` cancels
the bot must ride a task to completion. Two problems with leaning on it:

* `accept_cancel_loop_bound` is an **AXIOM**, not a theorem (`LivenessAudit`
  references "the accept_cancel_loop_bound axiom's existential"), so the bound is
  assumed rather than proved.
* It models the server as never re-drawing a cancelled code. The USER's own
  description says otherwise — the assignment is level-appropriate and its target
  is otherwise unguaranteed, so a redraw CAN repeat. **Production has no
  counterpart to `taskCodesSeen` at all** (grep finds nothing), so the assumption
  is neither enforced nor observed.

**What that leaves.** Building the USER's rule needs, in order:

1. A production notion of "a draw is owed for this course" — the rule itself. Small,
   and INERT until acceptance can fire, so it is not worth landing alone.
2. Either a new measure slot that the accept DESCENDS (the "draw owed" bit is the
   natural candidate: accept clears it), or a change to `UnconditionalDescent`'s
   theorem shape from "every rung descends" to "descends or is bounded". The first
   is one bit and mechanical-ish; the second is architecture.
3. The oracle vector grows from 33 slots, and `cycle_step_d` reuses index 33
   onward — so every extra arg shifts, in `Oracle.lean` and both harnesses.

That is a real increment with a Lean core, not a follow-on to the predicate work.
It should be budgeted as one.

## The Lean increment — done, and where it stops

**Landed (`0c82d5dc`, green): `fMeasure` widened with `drawOwedFlag`.** The slot
sits between `xpDeficit` and `phasePresent` precisely so discharging an owed draw
dominates the phase rise one slot below — every previously-promoted rung
(geCancel, supplyBank, currencyTurnIn) could take a flag at the BOTTOM of the
cascade because its apply touches no higher slot, and `.acceptTask` cannot, because
it RAISES `phasePresent`. The placement also makes a course boundary safe: setting
the flag raises slot 3, but a boundary decreases `xpDeficit` at slot 2, which is
earlier. Third widening of this tuple; mechanical, and the whole tree rebuilds.

**Stopped at the next obligation, which is not mechanical.** Gating
`acceptTaskFires` on `drawOwed` — required, or selecting `.acceptTask` with no draw
owed would not descend — breaks three proofs, and one of them is headline:

```
theorem productionLadder_ne_wait (s : State) : productionLadder s ≠ some .wait
```

It is UNCONDITIONAL, and its proof is `task_means_always_fires`: for every state
one of acceptTask / pursueTask / completeTask fires, because `acceptTask` fires
whenever the phase is `.none`. **The model's entire no-wait guarantee rests on "you
can always accept a task."** Gate the accept and a state with no task, no owed draw
and no objective step reaches `.wait`.

That is not a proof artefact — it is a real behaviour change. Today production
cannot idle while taskless, because ACCEPT_TASK fires unconditionally at the bottom
of the ladder. Under the rule it can.

**So the honest next step weakens a liveness guarantee**, from "the ladder never
waits" to "the ladder never waits while a draw is owed, a task is held, or the
objective has a step". Everything downstream of `productionLadder_ne_wait` inherits
that. It is defensible — waiting IS correct when there is genuinely nothing to do,
and `WaitGoal` exists as the totality witness for exactly that — but it is a
deliberate loosening of a no-deadlock property and should be signed off, not
absorbed as a step in an increment.

Reverted to green: the gate and the `.acceptTask` clear are backed out; only the
measure widening is committed. Resuming means starting there.

**The three options as originally written:**

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
