# PLAN: Monster-drop farming (feather unblock)

Status: CLOSED 2026-06-12. Outcome below differs from the original framing —
the investigation found drop-farming ALREADY existed; the real defect was
narrower.

## Problem (run-17 trace 2026-06-12 09:47, cycles 89-104)

Both top gear roots dead-ended on `feather` (chicken drop, rate 8):
`copper_legs_armor = 5 copper_bar + 2 feather`; `feather_coat = 5 feather +
2 ash_plank`. Bank held 9 feathers; `GatherMaterials(feather_coat)` was
unplannable (plan_len 0) and `GatherMaterials(copper_legs_armor)` burned
1.2M nodes / ~200s re-proving it EVERY cycle (XP rate 670→76 xp/h).

## What was actually wrong (and fixed)

1. **Withdraw filter excluded monster-drop leaf materials** —
   `GatherMaterialsGoal.relevant_actions` built its withdrawable set from
   craftable intermediates + needed + RESOURCE drops only; `Withdraw(feather)`
   never entered a plan despite 9 banked. FIX: withdrawable now includes the
   full `closure_demand` material set (shell-level; the Lean-mirrored
   `recipe_closure_pure` core untouched). Tests: run-17 c94 repro
   (relevant_actions + planner-level withdraw→craft plan).
2. **`objective_needs._producible_by_self` ignored monster drops** — feather
   classified buy-only, distorting the worth gate. FIX: consult
   `monsters_dropping` (consistent with `tiers/strategy._producible`).
   Test: monster-drop ingredient is a material need, not buy-only.

## What already existed (no change needed — initial diagnosis was wrong)

The "no component can farm a drop" claim was FALSE. The system already has a
complete, formally-anchored drop-farming path:
* `tiers/strategy._producible` gates drop-leaf steps on `monsters_dropping`
  + `is_winnable` + locations (actionable_step descends to the unmet
  `ObtainItem(feather)` leaf when stock is short).
* `objective_step_goal` maps it to `GatherMaterialsGoal(feather)`, whose
  `relevant_actions` enumerates FightActions per winnable dropper and keeps
  ONLY the `select_monster_for_drop` winner (proven core; see
  tests/test_ai/test_monster_drop_wiring.py).

A duplicate `FarmDropsGoal` + step routing was briefly added during this work
and REVERTED the same session (it intercepted and broke the proven path;
"one implementation" rule). If drop-farming behavior needs tuning later, tune
the existing GatherMaterials wiring.

## Phase 3 — follow-ups (deferred, user review)

* Rest threshold: both run-17 losses entered at 79/175 hp vs yellow_slime
  64-88 dmg; `predict_win` admits coin flips at the margin (formal-modeled —
  needs careful treatment).
* GearLatch fired on 2nd loss only, not the 1st (`error:fight_lost` at c86).
* Goal-history efficiency de-rank abandoned the copper_bar:5 prefetch 9
  gathers short (window=20 punishes on-track long gathers).
* Reserved-set protects only the CHOSEN root's recipe; crossover helmet ate
  the runner-up legs root's 6 bars.
* Junk band-lock (relief at 70% starves deposit at 90%) — open design Q.
* Step-ordering: materials-before-skill-gate prefetch eaten by grind crafts.
* Strategy cost model prices skill-gate grinds at ~cost 2 vs real ~12h
  (the all-night level freeze); time-aware step cost proposal pending.

## Verification

Next supervised run should show: feathers withdrawn from bank, legs/coat
crafted + equipped, no 200s planning cycles, combat XP rate recovered.
