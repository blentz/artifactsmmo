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
