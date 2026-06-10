# PLAN: trace-bug fixes (2026-06-09 analysis)

Source: analysis of 5 play traces (17.6h, 1,485 cycles, level 4 frozen, 0 combat XP).
Goal: fix all confirmed behavioral bugs. Constraints: 100% coverage, mypy strict, ruff,
formal diff oracles green, mutation anchors intact (run mutate.py after ai/ changes),
Lean models updated in lockstep where behavior is pinned.

## Bugs

| # | Sev | Bug | Status |
|---|-----|-----|--------|
| 1 | P0 | Task-material theft: gear goals consume PursueTask's crafted task items (no reservation); task restarts from zero | INVESTIGATE → FIX |
| 2 | P0 | No combat ever: objective_step_goal(ReachCharLevel) → None every cycle; crafted gear never equipped; 1,485 cycles, 0 fights | INVESTIGATE → FIX |
| 3 | P1 | TaskExchange timeout storm: guaranteed 40-46k-node timeout retried at every doomed-memo expiry; 24-29% wall clock | INVESTIGATE → FIX |
| 4 | P1 | Gather replan failure at depth 3 when on-hand ore crosses ~30 → 13/20-cycle oscillation with doomed-memo TTL as clock | REPRO → FIX |
| 5 | P2 | Worth-gate bypass is steady state (55-69% cycles) — mostly consequence of #2; re-check after #2 | DEFER until #2 fixed |
| 6 | P2 | ReachCharLevel roots vanish from strategy ranking on exact 20-cycle grid (bank-refresh correlated is_reachable dropout); sticky guard can't protect filtered-out candidates | FIX |
| 7 | P2 | CraftRelief flap: 1:1 recipes (cooked_gudgeon) relieve no inventory; guard re-fires every gather; crafts ×1 with 8 on hand | FIX |
| 8 | P3 | BATCH_CAP=10 travel amortization (38% wall = travel) — throughput tuning, formally pinned (test_task_batch_diff + Lean) | DEFER (perf, not correctness) |
| 9 | P3 | Withdraw dribbles (×3 ten times; ×10↔trade ping-pong) — plan-shape inefficiency | DEFER (perf) |
| 10 | P2 | commands/: dead cooldown_remaining elif branches in every command (real helper never sets it) + account logs expects doubly-nested .data.data | FIX (no formal pinning) |

## Phases

- **Phase 1 (this session): parallel root-cause investigations** for #1-#4 (read/repro only),
  plus immediate fix of #10 (independent, commands layer).
- **Phase 2: implement fixes** in dependency order; Lean/diff-oracle updates in same change
  where behavior is pinned (#1 candidate order / worth gate → arbiter oracle; #4 may touch
  gather relevant_actions pinned by gather oracles).
- **Phase 3: gates** — full pytest, mypy, ruff, formal diff suite, mutate.py (anchor check),
  then a live play session to confirm combat actually happens (user-run).

## Phase 1 findings (2026-06-09)

- **#2 no-combat**: winnable∩[L-1,L+2] = ∅ at L4 (winnable={chicken L1, yellow_slime L2}, window=[3,6]).
  `_pick_winnable_monster` (player.py) returns None forever; `objective_step_goal` → None.
  Secondary: `_sync_bank`/`_sync_pending` rebuild WorldState dropping attack/dmg/resistance/etc →
  combat_capable=False every 20th cycle — THIS IS ALSO BUG #6 (same root). Lean:
  CombatTargetExistence theorem violated by production (no window in model); promised
  test_combat_picker_diff.py never shipped. FIX: picker window-preferred with fallback to
  highest-level winnable with xp_per_kill>0; FightAction lower gate → xp_per_kill>0 (upper stays
  L+2); _sync_* → dataclasses.replace; ship combat-picker oracle; update ActionApplicability +
  CombatTargetExistence Lean.
- **#4 gather prune**: net-0 coverage credits bank stock unreachable by withdraw quanta (factory
  emits ×10/×80; ×1 only for equippables). FIX: factory emits residual-quantity withdraw for every
  material → makes the documented admissibility true. Regression test pins trace state
  (inv ore 22, bank {ore:28, bar:1} → plan non-empty). Keep plan_exists mutation anchors.
- **#3 TaskExchange**: is_satisfied = drain-ALL-coins (min_coins stuck at bootstrap 1; never learned
  because no exchange ever executes — chicken/egg). 22 coins → 33-action plan > max_depth 15 →
  guaranteed 300s timeout, re-armed every doomed-memo TTL. Lean CycleStep already one-batch.
  FIX: one-batch is_satisfied (initial_total − min_coins) + narrow relevant_actions + doomed-memo
  escalation (doubling TTL); Lean GoalSystem fixture lockstep; fix stale 90s comments.
- **#1 theft**: thief = GatherMaterials built by skill_grind_target (maximizes materials-on-hand =
  theft-targeting by construction) entering via fallback-step tier; `_suppress_step_for_task` checks
  wrong direction AND `_build_candidates` re-appends fallback alts unsuppressed (leak). Committed
  PursueTask permanently worth-suppressed (items task serves no char_xp need) → only runs via bypass.
  FIX: new ai/task_reservation.py (closure demand × remaining need; surplus free), reservation
  clause in _suppress_step_for_task + applied to fallback alts; TaskReservation.lean + diff test +
  mutate.py mutations; tests incl. trace-locked regression.
- **#10 commands**: FIXED in phase 1 (24 dead cooldown branches deleted + account logs flat-schema
  rendering; 419 lines deleted; full suite 3014 passed, 100%).

## Phase 2 execution order

- Wave A (parallel): F1 combat fix (player.py, actions/combat.py, Lean, oracle) + F2 factory
  withdraw fix (actions/factory.py only).
- Wave B: F3 TaskExchange (goals/task_exchange.py, doomed_memo.py, Lean GoalSystem).
- Wave C: F4 reservation (task_reservation.py NEW, strategy_driver.py, TaskReservation.lean NEW,
  mutate.py additions).
- After each wave: full pytest + targeted oracles. Final: full diff suite + mutate.py + push.

## Session log

- 2026-06-09: plan created; Phase 1 launched.
- 2026-06-09 (later): Phase 1 complete — root causes confirmed with repros; #10 fixed; Phase 2 launched.
