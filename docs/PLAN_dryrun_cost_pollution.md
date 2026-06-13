# PLAN: dry-run learning-store pollution (suboptimal monster lock)

Status: CLOSED 2026-06-12 (evening loop, run-4 finding).

## Problem (run traces 2026-06-12 + learning.db probe)

Robby ground **green_slime** (lvl4, 15 xp/kill) every combat cycle even after
the crit fix made **blue_slime** (lvl6, 22 xp/kill) reliably winnable. Digging
into `cheapest_path_to_level`:

* `xp_per_cycle = observed.char_xp` (if sampled) else `xpk / max(cost, 1.0)`
  where `cost = store.action_cost("Fight(code)", default=30)`.
* `action_cost` = median `actual_cooldown_seconds` over the last 50 ok cycles.
* **29 of 50 `Fight(green_slime)` rows had `actual_cooldown_seconds = 0`** →
  median 0 → `15 / max(0,1.0) = 15.0`/cyc, crushing blue_slime's real
  `22/30 = 0.73`/cyc. green_slime locked in.

The zero-cost rows were SIMULATED: dry-run cycles (`action.apply`, no server
cooldown) recorded in bursts seconds apart (00:38:51→00:39:06), dxp=10/dhp=-41.

## Root cause

`GamePlayer._record_learning_cycle` persisted to the LearningStore gated only on
`history is None` — NOT on `dry_run`. So `play --dry-run --learn` (a routine
planner-inspection probe) wrote apply()-projected cycles into the observed-cost
store. A Fight always incurs a real ~50s cooldown, so a `Fight(*)` ok-row with
cooldown 0 is provably non-real.

## Fix

1. `player.py::_record_learning_cycle` no-ops when `self.dry_run` (single
   chokepoint; also covers the no_plan record path). TDD tests in
   `test_player.py::TestDryRunDoesNotPersistLearning` (dry-run persists nothing;
   real run persists one row). Full suite 3202 green @ 100%.
2. One-time cleanup (user-approved): deleted the 29 poisoned
   `Fight(%) outcome=ok cooldown=0` rows from `~/.cache/artifactsmmo/learning.db`.

## Verified live (post-fix + purge)

* green_slime cost 0→61.4 (real median) → 0.244/cyc; blue_slime 0.733/cyc.
* `_winnable_farm_target` now returns **blue_slime** (was green_slime).
* Phase-11 safety intact: `cheapest_path` still PROJECTS cow (lvl8) because its
  `beatable` filter is `lvl ≤ state.level+1`, not `is_winnable`; the cascade
  drops it (`path_winnable=False` → `pick_winnable`) so cow is never fought.

## Follow-up (deferred, low severity)

`cheapest_path_to_level.beatable` uses the level heuristic, not `is_winnable`,
so its `projected_cycles_to_max` ETA can route through an unbeatable monster
(cow). Affects only the trace ETA number, never an action (actual play is
winnable-gated). Documented in the function's own "Known limits". Tighten to
`is_winnable` if the ETA is ever consumed for a decision.
