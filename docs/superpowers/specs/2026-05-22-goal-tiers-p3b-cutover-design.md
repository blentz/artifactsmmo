# Goal Tiers — P3b: Strategy Cutover (Drive the Bot)

Date: 2026-05-22
Status: Draft (for review)

The first **behavior-changing** phase: the Tier-3 strategy engine (validated in
shadow through P3a/3a.1/3a.2/3a.3) now drives the bot's progression decisions.

Prior phases: P1 objective+gap+personality, P2 prerequisite graph, P3a strategy
engine (shadow). Next: P3c folds economy + tasks into the frontier and retires
`priorities.py`.

## Goal

Each cycle, the strategy picks the actionable step (`chosen_step`); the player
maps it to a parameterized instance of an existing, planner-tested goal and
selects it at a fixed progression priority. The six self-directed progression
goals are removed from flat auto-selection; survival/economy/task goals stay and
still preempt when urgent. A low-priority fallback grind keeps the bot moving
when the strategy step can't be planned.

## Current state

`GamePlayer._build_goals` returns a flat list; `_select_goal` picks the max
`priority()` with sticky commitment; the planner uses `goal.is_satisfied`
(terminate), `goal.value` (A* heuristic — **not** `desired_state`),
`goal.relevant_actions`, `goal.max_depth`. The strategy engine
(`tiers/strategy.py`) already computes `StrategyDecision(chosen_step, ...)` each
cycle and traces it (shadow). Actions simulate inventory/position, **not**
skill-XP or level — so `GrindCharacterXP`/`LevelSkill` use per-cycle "progress
this cycle" satisfaction, while `GatherMaterials`/`UpgradeEquipment` use
"have/equipped". Goal constructors:
- `GatherMaterialsGoal(target_item, needed: {mat: qty})` — satisfied when
  inventory+bank holds `needed`.
- `UpgradeEquipmentGoal(committed_target=(code, slot))` — crafts + equips that item.
- `LevelSkillGoal(skill_name, target_level)` — satisfied when skill ≥ target.
- `GrindCharacterXPGoal(target_monster, initial_xp)` — satisfied when `xp > initial_xp`.

## Design

### `MetaGoalAdapter(Goal)` — `tiers/strategy_adapter.py`
A thin wrapper that delegates planning to an **inner** existing goal but selects
at a fixed priority band:
- `__init__(inner: Goal, priority_band: float)`.
- `value`, `is_satisfied`, `desired_state`, `relevant_actions`, `max_depth` →
  delegate to `inner` (so the planner sees the inner goal's tested behavior,
  including its `value()` heuristic).
- `priority()` → `priority_band` (fixed; overrides the inner goal's dynamic
  priority for selection).
- `__repr__` → `f"Strategy({inner!r})"`.

### `strategy_goal(step, state, game_data, priority_band) -> MetaGoalAdapter | None`
Maps the strategy's `chosen_step` to a parameterized inner goal:
- `ObtainItem(code, qty)`:
  - **equippable gear** (`stats.type_` in `ITEM_TYPE_TO_SLOTS`) →
    `UpgradeEquipmentGoal(committed_target=(code, ITEM_TYPE_TO_SLOTS[type_][0]))`
    (crafts the chain **and equips** — closes the equipped-value gear gap).
  - else (material/raw) → `GatherMaterialsGoal(target_item=code, needed={code: qty})`
    (gather/craft until `qty` held).
- `ReachSkillLevel(skill, target)` → `LevelSkillGoal(skill, target)`.
- `ReachCharLevel(_)` → `GrindCharacterXPGoal(best_beatable_monster(state, game_data), state.xp)`
  (per-cycle XP progress via fights). Returns `None` if no beatable monster.
- Returns `None` when no mapping applies (then no strategy goal that cycle).

`best_beatable_monster` = highest-level monster with `monster_level <=
state.level + 1` (mirrors `combat_capable`), or `None`.

### Player cutover (`player.py`)
- **Remove** from `_build_goals`: `UpgradeEquipmentGoal`, `GatherMaterialsGoal`,
  `LevelSkillGoal`, `FarmMonsterGoal`, `GrindCharacterXPGoal`, `FarmItemsGoal`
  (no longer auto-selected by priority). Their classes remain — the adapter
  reuses four of them; `FarmMonster`/`FarmItems` become dormant (deleted in P3c).
  The committed-upgrade-target plumbing that fed `UpgradeEquipmentGoal` is no
  longer needed for selection but stays until P3c.
- **Each cycle** after building `state`: `step = self._strategy.decide(state,
  game_data).chosen_step`; if `strategy_goal(step, state, game_data,
  STRATEGY_BAND)` is non-None, append it.
- **Fallback**: also append `MetaGoalAdapter(GrindCharacterXPGoal(
  best_beatable_monster(...), state.xp), FALLBACK_BAND)` when a beatable monster
  exists — a low-priority safety net so the bot always has a plannable action if
  the strategy step won't plan.
- **Keep**: `RestoreHPGoal` (HP interrupt, 110), `DepositInventoryGoal`,
  `SellInventoryGoal`, `DiscardOverstockGoal`, `ClaimPendingGoal`,
  `CompleteTaskGoal`, `AcceptTaskGoal`, `TaskExchangeGoal`, `TaskCancelGoal`,
  `LowYieldCancelGoal`, `ExpandBankGoal`, `UnlockBankGoal`,
  `ReachUnlockLevelGoal` — with their current priorities.
- **Priorities**: `STRATEGY_BAND = 50` (tactical-pursuit; below HP 110 /
  complete-task 90 / bank-unlock 90 / deposit-full→80; above the fallback).
  `FALLBACK_BAND = 25` (above idle accept-task 20, below STRATEGY 50). Final
  order: interrupts (80–110) > STRATEGY 50 > FALLBACK 25 > accept-task 20.

### Behavior consequences
- The bot pursues the best-attainable gear / skills / char level via the
  strategy's next reachable step; combat-for-XP runs through the mapped
  `GrindCharacterXP`.
- **Items-tasks pause** (no `FarmItems`/`FarmMonster`): the bot won't gather/
  deliver items-task materials. `Accept/Complete/Exchange/Cancel` task goals stay
  (a monster task may still complete incidentally via strategy fights;
  `LowYieldCancel`/`TaskCancel` can shed a stuck items-task). P3c integrates
  tasks as instrumental means.
- HP/deposit/bank-unlock still preempt via their existing priorities.

### Validation
Keep the shadow `strategy` trace field. `selected_goal` now often reads
`Strategy(GatherMaterials(...))` / `Strategy(GrindCharacterXP(...))` etc., so
the trace shows the cutover live.

## Error handling
- `strategy_goal` returns `None` (no mapping / no monster) → that cycle relies on
  fallback + kept goals; never raises.
- Adapter delegates to a tested inner goal; planner no-plan handled by the
  existing stuck-detector/recovery plus the fallback grind.
- `best_beatable_monster` None → no fallback that cycle (recovery escalates).

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on new code.

- **`MetaGoalAdapter`:** delegates is_satisfied/value/relevant_actions/desired_state/
  max_depth to inner; `priority()` returns the fixed band; repr.
- **`strategy_goal` mapping:** gear `ObtainItem` → `UpgradeEquipmentGoal` with the
  right committed_target; material `ObtainItem` → `GatherMaterialsGoal(needed={code:qty})`;
  `ReachSkillLevel` → `LevelSkillGoal`; `ReachCharLevel` → `GrindCharacterXPGoal`
  with `initial_xp=state.xp` and the best beatable monster; `None` when no monster.
- **`best_beatable_monster`:** highest level ≤ char+1; None when none.
- **Player `_build_goals`:** the 6 progression goals are absent; the strategy
  adapter + fallback are present (given a step / monster); kept goals present.
- **Planner integration:** with a small world, the selected strategy goal plans a
  sane action sequence (e.g. gather→craft for a material step); HP-critical still
  selects RestoreHP; bag-full still selects Deposit.
- Update/curate existing `_build_goals`/selection tests that asserted the removed
  goals.

## Files
- Create `src/artifactsmmo_cli/ai/tiers/strategy_adapter.py` (+ exports).
- Modify `src/artifactsmmo_cli/ai/player.py` — remove 6 goals; add strategy goal
  + fallback each cycle.
- Tests: `tests/test_ai/test_tiers_strategy_adapter.py`, update player goal-build
  tests.

## Open question for review
The two brainstorm answers slightly conflict: "strategy parameterizes existing
goals" (reuses `GrindCharacterXP` for `ReachCharLevel`) vs "retire
`GrindCharacterXP` entirely + new fallback class". This spec **reconciles** by
reusing the goal *classes* in the mapper (incl. `GrindCharacterXP`) and removing
all six from flat auto-selection; the fallback is a low-band adapter-wrapped
grind (no new class — DRY). If you'd rather delete `GrindCharacterXP` and write a
brand-new minimal fallback goal, say so and I'll revise before the plan.

## Out of scope (P3c)
- Retiring `priorities.py` and the kept goals' `priority()` methods.
- Tasks-as-instrumental-means; deleting `FarmMonster`/`FarmItems`.
- Tactical policies / battle-prep (P4).
