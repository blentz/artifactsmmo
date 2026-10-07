# PLAN: task value — keep, draw and cancel by worth (Phase 5-2c-iii-c-2 #5)

Status: APPROVED design (USER answers §6, 2026-10-07). Increment 1 next.

## 1. Why

Live 2026-10-07, level 29-30: 4 of 5 draws paid no XP (sheep, mushmush,
green_slime, wolf). Each one was cancelled on the spot by S-048 for 1 task coin;
spider was the only draw kept. A draw is owed only when the chosen root changes,
so after a cancel or a turn-in a character waited 5h+ (C3P0) for its next draw.
A turn-in pays 4 tasks_coin + 300 gold on every record. The exchange costs 6
coins (`fleet_learned_settings`).

The TASK_CANCEL rung (`tiers/means.py:238`) asks three fixed questions:
- S-048: no XP means cancel;
- the one-level horizon: OUT_OF_REACH means cancel;
- items `task_decision == PIVOT` means cancel.

None of them asks what the task is WORTH.

## 2. USER rulings (2026-10-07, verbatim)

- No-XP draw: "Work tasks when below a level-appropriate gold reserve. gold buys
  things from the NPCs and Grand Exchange, so grinding tasks for gold makes sense
  when there's a next step in the chain. Grey Tasks for Gold is not an end unto
  itself."
- Redraw: "Owe a draw when 1. the tasks provide XP plus gold. 2. when we can
  feasibly farm tasks for gold in a short enough timespan that enables an NPC or
  GE purchase. 3. when the task drops items aligned with needed craft
  ingredients (gold plus drops is better than just drops). This is a part of the
  pareto frontier analysis central to the game's progress loop."
- Cancel home: "Fold into task objective".

## 3. Design: one worth verdict

`task_worth(task, state, game_data, ctx, history) -> TaskWorth` is a pure core
over a task code and its type. It returns the set of REASONS the task is worth
working (empty = worthless):

| Reason | Holds when | Sources (existing) |
|---|---|---|
| `XP` | a kill (monsters) or the producing skill (items) pays XP now | `task_alignment.task_advances_progression`, `GameData.xp_per_kill` |
| `GOLD` | there is a pending gold purchase in the chain AND gold held < what it needs AND the task funds the shortfall within the horizon (§6 Q1) | the gold need: `progression_reserve.reserved_targets`/`reserve_floor` or the root's BUY/GE_FILL legs (§6 Q4); gold held: `account_gold`; the task's gold: `task_gold_reward` + `monster_min/max_gold` × kills remaining; the time: `route_price(ReachTaskOutcome)` |
| `DROPS` | the task monster drops an item in the needed ingredient closure | `GameData.monster_drops`, `strategy_driver.monster_drop_inputs` / the RequirementGraph closure of the chosen root and `near_term_targets` |

The task must also be FEASIBLE: winnable now, or its horizon is GEAR or LEVEL_UP
(`resolve_task_horizon`). OUT_OF_REACH makes it worthless, whatever the reasons.

Uses:
- **Keep or cancel (held task):** worthless, a coin in the pocket, and not
  already met means the task objective's step is the cancel
  (`ReachTaskOutcome(code)` offered by `_task_root`; TASK_CANCEL rung deleted).
  Worthless with no coin is §6 Q3.
- **Owe a draw (no task held):** the master's pool for this level
  (`GameData.tasks_for(type, level)`) holds a task whose worth is non-empty, AND
  a coin is in the pocket or a worthy draw is likely enough (§6 Q5). The draw is
  owed on that condition, not on a course change. It is taken on the task
  objective's turn (`accept_due`).
- **Ranking ("gold plus drops is better than just drops"):** the reason set
  orders draws and alternatives as a Pareto set: {XP, GOLD, DROPS} beats any
  subset. The task objective's turn order is unchanged; this order picks between
  task options only.

## 4. Formal

- Lean `Formal/TaskWorth.lean`: the verdict as a computable def over abstract
  inputs (xpPositive, goldShort, fundsWithinHorizon, dropAligned, feasible);
  keep/cancel/draw as defs over it.
- Theorems:
  - cancel ⇒ worthless ∧ coin;
  - a worthy task is never cancelled;
  - draw owed ⇒ some pool task is worthy;
  - Pareto: the superset dominates.
- Differential: `formal/diff/test_task_worth_diff.py` against the pure core.
- Fold the TASK_CANCEL rung like c-2 #1-#4: delete the MeansKind constructor and
  the DecideKey entry, cascade the Lean liveness modules, update the sim and the
  ladder diffs.
- Residuals to fold in: `State.drawOwed` (now worth-driven, not course-driven),
  `State.pursueTaskFires`, and the `arbitrate` `is_suppressed` hook.

## 5. Increments

1. Pure core `ai/task_worth.py` + Lean model + differential (no behaviour change).
2. Keep/cancel through `_task_root` (fold TASK_CANCEL; S-048, horizon and PIVOT
   become worth questions).
3. Draw owed by worth (`_draw_owed_for_course` replaced).
4. Witness live: draws kept, coins not burned, gold-short characters working
   tasks.

## 6. USER answers (2026-10-07)

1. **Gold horizon:** "Faster than other gold". GOLD holds when finishing the
   task funds the shortfall in fewer cycles than the character's best non-task
   gold route (fight gold, selling surplus).
2. **Drops alone:** "Yes, drops alone count". DROPS is a reason on its own;
   gold plus drops still ranks above drops alone (the Pareto order).
3. **Worthless, no coin:** "Work it to clear it". It is rotated in on the task
   turn (4 coins + 300 gold, and the slot frees for a worthy draw).
4. **Gold need:** "Both, the larger". Short when `account_gold` < max(
   `progression_reserve`, the gold on the chosen root's BUY/GE_FILL legs).
5. **Draw without a coin** (follows from 3): a worthless draw is worked to clear
   it, so a draw is owed whenever the master's pool for this level holds a
   worthy task, coin or not.
6. **Low-yield cancel** (c-2 #1, `route.task_pays_less`): "Worth wins, drop
   it". An XP task is kept however slow its XP; the turn order gives the faster
   alternative its own turns.
7. **Other gold:** "The grind target's gold". The comparison rate is the fight
   gold per cycle of `ctx.combat_monster`, the activity the character would
   otherwise do.

## 7. Progress

- **Increment 1 — DONE @fa2ccf4a.** Pure core `ai/task_worth_core.py`, Lean
  `Formal/TaskWorth.lean` (12 theorems), oracle `task_worth`, differential, 8
  mutants.
- **Increment 2 — keep/cancel by worth.**
  - Live inputs: `ai/task_worth.py` (`task_worth_for`, `short_items`,
    `held_task_cancel_due`).
  - `ctx.gold_short` is computed by `GamePlayer._gold_short`. `account_gold` is
    compared with max(`progression_reserve`, `closure_gold_demand` of the
    previous cycle's `ObtainItem` root). It lives in the player to avoid an
    import cycle: `progression_reserve` → `tiers` → `route`.
  - The funnel is `route.task_cancel_due`.
  - `_task_root` and `objective_step_goal` cancel by worth (`TaskCancelGoal`).
    A held unmet items task is always worked.
  - Retired: the TASK_CANCEL rung (production, Lean, sim, diffs), the
    low-yield cancel in root/step, and `task_pursue.pursue_due` (its PIVOT
    gate).
  - Lean restatements: LIV-003a `…_stepFires`, `accepted_state_decides_step`,
    `taskInfeasible_implies_stepFires`.
- **Live probe (2026-10-07):**
  - At L30-32, grey tasks are worthless (sheep, wolf, mushmush), except
    skeleton, whose skeleton_bone is short for the royal_skeleton gear.
  - XP tasks are worthy.
  - GOLD never fires: every character holds about 225k gold against a 1,766
    reserve.
- **Residuals:**
  - `Formal/LowYieldCancel.lean` + `low_yield_cancel_fires` +
    `LowYieldCancelGoal` + their diff and tests have NO production caller now:
    delete them in cleanup.
  - Gold demand counts NPC leaves only; GE leaves are in the reserve via
    `buy_price`.
  - An items task is always feasible (its chain is the walk's to find).
  - `planFor .objectiveStep` has no cancel dispatch (an existing
    over-approximation).
- **Increment 3 (next):** the draw is owed by pool worth (`draw_owed` over
  `GameData.tasks_for`), replacing `_draw_owed_for_course`.

## 8. Increment 3 plan: a draw owed by pool worth

### 8.1 Today

`GamePlayer._draw_owed_for_course` owes a draw only when the chosen root
CHANGES (S-051 plus the no-immediate-redraw rule). It clears the debt while a
task is held. `ctx.draw_owed` feeds `task_accept.accept_due`, which feeds
`_task_root` (the offer) and the objective step (`AcceptTaskGoal` at
`choose_taskmaster`'s master).

Live cost (2026-10-06/07):
- After a turn-in or a cancel, the next draw waits for an unrelated root
  change: C3P0 waited 5h+, and R2D2 held nothing after its 13:28 turn-in.
- The course rule exists to stop an accept→cancel spin, a coin per cycle.
  Under worth, that spin only happens on worthless draws while coins last, so
  a course change is the wrong brake.

### 8.2 The rule (USER: "Owe a draw when" XP plus gold, gold that funds a
purchase quickly, or aligned drops)

A draw is owed when NO task is held and the master's POOL is worth drawing
from:

    p      = worthy share of the pool   (task_worth_for over GameData.tasks_for(type, level),
                                          each task at its mean quantity)
    owe  ⇔ p > 0 ∧ expected rerolls (1 - p) / p ≤ coins a completion pays

A worthless draw is cancelled for 1 coin while a coin is in the pocket, so the
expected coins spent before a worthy draw is (1 - p) / p. A completion pays
`task_coin_reward` (4 on every record). Drawing is a loss when the rerolls
cost more coins than a worthy task returns.

Live probe (2026-10-07, level 30-32):
- C3P0: 9/21 worthy (p ≈ 0.43), 1.33 rerolls.
- Lor and HAL: 7/21 worthy (p ≈ 0.33), 2 rerolls.
- All are owed.

A worthless draw kept for lack of a coin is worked to clear it (rule §6.3). So
a coinless character draws on the same rule: its "reroll" is working the task.

- The COURSE rule is deleted (`_draw_course`, `_draw_owed_for_course`): the
  debt comes from worth, not from root changes.
- The anti-spin bound is the economics above. A pool too poor to pay its
  rerolls owes nothing, and a cancelled draw does not re-arm a pool that was
  not worth drawing from.

### 8.3 Which master

`choose_taskmaster` picks by link-demand synergy, and None means the default
master. Rule: draw from the master whose pool has the higher worthy share `p`
(the master's own task type: monsters or items). A tie or a single master
falls back to `choose_taskmaster`. A master whose pool fails 8.2 is never
chosen.

### 8.4 Formal

`Formal/TaskWorth.lean` gains:
- `drawDue (worthy size coinReward : Nat) : Bool := 0 < worthy ∧
  (size - worthy) ≤ coinReward * worthy`. This is the cross-multiplied
  (1-p)/p ≤ R.
- Theorems:
  - `drawDue → ∃ worthy task` (it refines `drawOwed_iff`);
  - monotone: more worthy tasks never revoke a draw;
  - a pool with no worthy task never owes;
  - satisfiability witnesses.
- Oracle `task_draw_due` and a differential against the Python `draw_due` core.

The Lean liveness `State.drawOwed` stays an OPAQUE Bool. Only its producer
changes, so the F/D/E measure slot and the `{f,d,e}Lt_of_drawOwed_dec` lemmas
are untouched; the residual stays a residual.

### 8.5 Production

- `task_worth_core.draw_due(worthy, size, coin_reward) -> bool` (pure, Lean
  mirror).
- `task_worth.pool_draw(state, gd, ctx, history) -> tuple[str, bool]`: per
  master type, the pool's worthy count, then the chosen master and whether a
  draw is due. Evaluated only when no task is held, once per cycle (the pool
  has about 21 tasks; the horizon walk runs only for a lost fight).
- `GamePlayer`: `ctx.draw_owed` = `pool_draw(...)` when no task is held; the
  course fields go.
- `AcceptTaskGoal` goes to the chosen master's tile.

### 8.6 Tests, mutants, witness

- **Unit:**
  - the draw-due arithmetic, including its boundary (`(1-p)/p` = R owes);
  - an empty pool or a worthless pool owes nothing;
  - master choice by share;
  - no task held is required.
- **Differential:** `test_task_draw_due_diff.py`.
- **Mutants:** the comparator, the worthy>0 guard, master choice, and the held
  check.
- **Witness after restart:**
  - a character holds no task for under one turn after a turn-in;
  - accepted draws per worthy draw ≈ 1/p;
  - no coin is spent on a pool that fails 8.2.

### 8.7 USER answers (2026-10-07) to the questions below

- Brake: "Rerolls ≤ completion coins" (8.2 as written).
- Pool: "Uniform now"; record each accepted draw so the assumption can be
  checked once there are enough draws.
- Master: "Higher worthy share" (8.3 as written).

### 8.8 The questions as asked

1. **The brake:** is "rerolls cost ≤ coins a completion pays" the right
   economics, or should a draw be owed whenever the pool holds any worthy task
   (no brake beyond coins running out)?
2. **The pool distribution:** the rule assumes the master draws uniformly from
   `tasks_for(type, level)`. Keep that assumption, or learn the draw
   distribution from accepted tasks first? Today's evidence: 5 draws, which is
   too few to fit anything.
3. **The master:** choose by worthy share as 8.3, or keep `choose_taskmaster`'s
   link-demand synergy and only gate the draw?

### 8.9 Increment 3 built (2026-10-07)

- **Lean:** `drawDue` + `drawDue_iff` / `_none` / `_mono` /
  `_refines_drawOwed`, manifest and contract pins, oracle `task_draw_due`,
  differential.
- **Core:** `task_worth_core.draw_due`.
- **`task_worth.pool_draw`:** each master's pool, tasks at mean quantity; due
  per `draw_due` at `min_task_coin_reward`; the higher worthy share wins; a tie
  gives None, which leaves the choice to `choose_taskmaster`.
- **Gold rates** are read only when `ctx.gold_short`; otherwise a pool scan ran
  an obtain walk per items task.
- **Player:** `ctx.draw_owed`/`ctx.draw_master` come from `pool_draw`. The
  course rule (`_draw_owed_for_course`, `_draw_course`) is deleted.
  `seed_offline` sets `_draws_enabled = False`, so offline scenarios still draw
  nothing.
- **Step:** `AcceptTaskGoal` goes to `ctx.draw_master`'s tile.
- **Live probe (scratch DB, C3P0/Lor, L30-31):** a draw is due at the ITEMS
  master. Items 16/27 worthy (0.59) against monsters 9/21 (0.43). Items tasks
  are worthy through the producing skill's XP (`task_advances_progression`
  counts a skill). This is a fleet-wide shift toward items tasks. It follows
  the rule as ruled, and is flagged to the USER. `pool_draw` takes 45-91 ms.
- **Recording draws** (USER "record each accepted draw"): the `cycles` rows
  already hold each `AcceptTask` and the next cycle's `task_code`, so no new
  table is needed.
