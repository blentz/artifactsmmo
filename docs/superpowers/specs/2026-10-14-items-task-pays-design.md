# A held items task defers the level step only while it pays

Date: 2026-10-14.

## Intent (USER 2026-10-14)

- The level step's choice between fighting and a held items task is
  **priced by useful XP** ("Price it by useful XP"), the fleet objective of the
  food-role epic: maximum fleet XP throughput, useful XP only (character XP,
  plus skill XP only where the goal-action DAG demands the level).
- Approach 1: `task_worth` gates the deferral, then XP rates decide.
- **Priced at every gap.** The 4-level bootstrap guarantee is dropped ("Price
  gap ≤ 4 too"); liveness is argued from the payment, not from a gap.
- A worthless held task without a coin is **held, not worked**; this replaces
  "Work it to clear it" (2026-10-07) for the level step.

## The live problem (learning.db, 2026-10-14 13:21–18:51Z, fleet on 35329d03)

- HAL, level 35, root `ReachCharLevel(40)`: **0 character XP in 5.5 h**, 0
  fights. It worked items tasks: iron_bar (1.4 h), 199 cooked_shrimp for 150
  gold and 2 tasks_coin (3.1 h), then trout. Between tasks it accepted and
  cancelled until it held another items task.
- `task_worth_for` on HAL's held `trout` task: `TaskWorth(xp=False, gold=False,
  drops=False)` — fishing is not in `skill_demand`, gold is not short. The
  grind it deferred (imp) pays 15/31 ≈ 0.48 XP/s.
- Cause: `strategy_driver.objective_step_goal`'s `ReachCharLevel` arm returns
  no step when `objective_step_is_fight_pure` is False, which it is whenever
  `target - level > 4` and an items task is in progress, whatever the task
  pays. HAL's gap is 5. The June 2026 livelock this rule was patched for
  ("items tasks chain indefinitely … the bot NEVER fought") is back whenever a
  root sits more than 4 levels away.

## Design

### §1 The decision (pure core, Lean-bound)

`objective_step_is_fight_pure` drops `target` and `level` and gains
`task_pays: bool`:

    fires = is_reach_char_level
            and has_combat_monster
            and not (items_task_active and task_pays)

`items_task_active` is unchanged (type "items", a code, total > 0, progress <
total). With no gap term, `bootstrapCharHorizon`
(`ObjectiveStepFight.lean`, emitted by `Oracle.lean`) and
`_CHAR_LEVEL_BOOTSTRAP_HORIZON` (`tiers/prerequisite_graph.py`, kept only as
that anchor) have no remaining meaning and are retired with their
differential check.

Lean (`formal/Formal/ObjectiveStepFight.lean`): the model takes the same
inputs. Theorems:

- `fires_iff` — the characterization above.
- `not_reach_char_level_never_fires`, `no_combat_monster_never_fires` — kept.
- `completed_task_fires` — kept (a finished task never defers).
- `unpaid_task_fires` (new) — `task_pays = false` ⇒ Fight-led.
- `no_items_task_fires` (new) — no items task in progress ⇒ Fight-led.
- `bootstrap_always_fires`, `bootstrap_step_always_fires` — RETIRED: they are
  false under the new rule. They appear only in `Contracts.lean`,
  `Manifest.lean` and `Audit.lean`; no capstone proof consumes them.

`Contracts.lean`, `Manifest.lean`, `Audit.lean`, `Oracle.lean` and
`formal/diff/test_objective_step_is_fight_diff.py` change with the model.

### §2 `task_pays` (impure shell)

New module `ai/held_task_pays.py`, one function
`held_task_pays(state, game_data, ctx, history) -> bool`, called by the
`ReachCharLevel` arm with the held task. It reads `task_worth_for(state.
task_code, state.task_type, remaining, …)` and returns True when:

1. `worth.gold` (gold short, and the task's gold rate beats the grind's) or
   `worth.drops` — today's verdicts, unchanged (an items task never sets
   `drops`); or
2. `worth.xp` (its producing skill is in `ctx.skill_demand`) AND the task's
   skill XP per second exceeds the grind's character XP per second:
   - task side: a new `LearningStore.task_work_xp_per_second(task_code,
     skills)` — the XP of the demanded skills (`ctx.skill_demand`) over the
     cooldown seconds of this character's cycles WORKING that task: rows with
     `Cycle.task_code == task_code` whose goal is one of the two
     `strategy_driver._pursue_goal` emits (`PursueTask(<code>)`,
     `GatherMaterials(<code>, {…})`). Every such cycle stays in the
     denominator, zero-XP gathers included: a mean over XP-gaining cycles only
     is the 50x over-estimate `skill_grind_rate` was written to stop (R2D2,
     2026-08-08). Fight cycles while the task is held are not its work and are
     excluded, so fighting cannot lower the task's rate (an absorbing state).
     Fallback: the fleet's rows for the same task
     (`fleet_task_work_xp_per_second`), one-way, as `skill_grind_rate` does;
   - grind side: `best_loadout(state, game_data, ctx, ctx.combat_monster,
     history).rate.xp_per_second` (`loop_rate`'s rate, recovery included).

**Rulings.**

- With no learned skill rate (no store, or `task_work_xp_per_second` returns
  None for this character and the fleet), clause 2 is `worth.xp` alone. Cost if wrong: a slow demanded task
  preempts the grind until the skill has history.
- The two sides are measured differently: the task side is LEARNED seconds,
  the grind side the MODELLED loop (`loop_rate`, the rate the loadout chooser
  already ranks by). Cost if wrong: a model that overstates the grind's rate
  sends a paying task's character to fight; the live check compares HAL's
  measured fight XP/s against the modelled one.

### §3 Liveness without the gap

A deferral needs a paying task. Items tasks chain (one completes, another is
drawn), so the argument is per payment, not per task:

- XP: each deferring task pays skill XP the DAG demands, faster than the grind
  pays character XP; demanded skill levels are finite, and a met level leaves
  `skill_demand`, so XP deferrals end.
- Gold: only while `ctx.gold_short`, and only at a better gold rate than the
  grind.
- Drops: never for an items task.

This is an argument, not a proof: the Lean model proves the decision
(`unpaid_task_fires`), not that payment ends. The retired
`bootstrap_step_always_fires` did not feed the capstone either.

### §4 What changes live

- A worthless held task (HAL's `trout`) no longer defers the step: the
  character fights. Without a coin the task is held, not worked, and blocks
  drawing a new task until a coin is held (USER, approach 1).
- A task paying demanded skill XP faster than the grind is worked at any gap
  (today a bootstrap grind, gap ≤ 4, preempted it).

### Non-goals

- `task_worth_core` and the cancel/draw verdicts: unchanged.
- A common XP currency for gold and coins (approach 3): not built.
- Monsters tasks: unchanged (the predicate's stand-down is items-only).

## Testing

TDD in `tests/test_ai/`:

- §1: characterization over every input; the gap no longer matters (a gap of
  1 and of 10 give the same answer).
- §2: worthless ⇒ False; gold or drops verdict ⇒ True; demanded skill faster
  than the grind ⇒ True, slower ⇒ False; no learned rate ⇒ `worth.xp`.
- Strategy driver: HAL's shape (gap 5, worthless items task) yields
  `GrindCharacterXPGoal`; a paying task yields no step.
- Lean: the theorems above build; `#print axioms` clean; the differential test
  agrees over random inputs.
- Mutation anchors for every new branch in the same commit.
- Full `formal/gate.sh` green before push.

## Live verification (learning.db, after restart)

- HAL character XP/h above 0 while it holds a worthless items task.
- Fleet character XP/h above the 13:21–18:51Z rate (17,820 / 5.5 h ≈ 3,240/h).
- No character spends an hour on an items task whose `task_worth` is
  all-False.
