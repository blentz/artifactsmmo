# PLAN: Unify combat-beatability + finish deferrals

From the 2026-05-25 deferral/generalization survey. All TDD; 100% coverage + mypy + ruff
enforced via pyproject addopts, so every step ends with a clean `uv run pytest`.

## #1 — One combat-beatability predictor (delete the 3 static margins)
Authoritative core: `ai/combat.py:predict_win(state, game_data, monster_code)` (stat sim).
Add `is_winnable(state, game_data, monster_code, history=None)` in `ai/combat.py` =
predict_win + learned-loss veto (sample_count ≥ MIN_WIN_SAMPLES & success_rate < WIN_RATE_THRESHOLD).
Move WIN_RATE_THRESHOLD / MIN_WIN_SAMPLES from player.py → combat.py.

Migrate the four sites:
- [ ] `player._is_winnable` → delegate to `is_winnable(..., self.history)` (no behavior change).
- [ ] `tiers/prerequisite_graph.combat_capable` → `any(predict_win(...))` not `level<=level+1`. (#2)
- [ ] `actions/combat.py FightAction.is_applicable` → keep locations/inventory_free/hp>0.3,
      replace `min_level<=monster_level<=level+2` + `best_eq>=monster_level-1` with `predict_win`
      (gear already folded in via pick_loadout). Stat-only (no history param on is_applicable);
      the learned veto applies upstream at target selection.
- [ ] `task_feasibility.task_requirement` monster branch → infeasible when `not predict_win`,
      keep monster_level as the grind target. Delete MONSTER_LEVEL_MARGIN.

## #3 — batch_refresh_window
- [ ] `player._build_actions()` runs before `_maybe_periodic_refresh`; the built Craft×K/TaskTrade×K
      can diverge from the goal's K after a mid-cycle refresh. Fix: build actions from the same
      post-refresh snapshot (move the refresh before _build_actions, or share one snapshot).

## low-priority
- [ ] `tasks_coin` string literal duplicated (bank_selection, inventory_caps, means) → one constant.
- Tunable guesses (recovery windows, inventory caps, BATCH_CAP, planner budget): NOT code bugs —
  they need play-data tuning, not a rewrite. Leave with a note unless told otherwise.

## Status — DONE (2026-05-25)
- #1: is_winnable predictor added (combat.py); player._is_winnable delegates.
  DEVIATION: FightAction.is_applicable + task_feasibility kept their cheap +2
  gate (NOT predict_win). Routing predict_win through the GOAP precondition
  made fights applicable via best-on-hand loadout → planner fights before a
  beneficial swap, defeating LOADOUT_PENALTY (confirmed regression via a
  stashed clean-main comparison). Two-tier design: cheap +2 filters
  (FightAction + task_feasibility, mutually consistent) + authoritative
  is_winnable (runtime selection + prerequisite graph). Divergent +1 removed.
- #2: prerequisite_graph.combat_capable → predict_win. DONE.
- #3: refresh-before-build ordering fixed + ordering test. DONE.
- low-pri: tasks_coin → world_state.TASKS_COIN_CODE (was 7 sites / 4 defs). DONE.
- low-pri tunables (recovery windows, inventory caps, BATCH_CAP, planner budget):
  intentionally NOT changed — they need play-data tuning, not a code fix.
- Final: 2416 pass / 100% cov / mypy 0 / ruff clean. Branch fix/unify-combat-beatability.
