# Goal Tiers — P3c: Strategy as Sole Arbiter

Date: 2026-05-23
Status: Draft (for review)

The phase that finishes the tiered cutover: the Tier-3 strategy becomes the
**single** decision point. Economy and task goals fold into the strategy
decision, `priorities.py` and the `_select_goal` max-priority machinery retire,
and the plumbing orphaned by the P3b/P3b.1 cutover is deleted.

Prior phases: P1 objective+gap+personality, P2 prerequisite graph, P3a strategy
engine (shadow), P3b cutover (strategy drives progression), P3b.1 winnable
combat target. After P3c there is no flat-priority selection layer left.

## Goal

`decide(state, game_data)` returns one structured decision describing the entire
cycle choice: ordered active **guards** (state-pressure interrupts + prerequisite
gates), the **objective step** (the existing contribution/cost frontier winner),
and **means** (tasks / economy) in two structural bands. A driver maps the
decision to the single goal to pursue — top active guard, else the top
*plannable* means — owning sticky commitment. `priorities.py`, `_select_goal`'s
max-`priority()` arbitration, the goals' `priority()` methods, and the dead
committed-target / FarmMonster / FarmItems plumbing all go.

## Current state

`GamePlayer._build_goals` returns a flat list of ~13 goals; `_select_goal` picks
the max `priority()` with sticky commitment; the strategy goal is slotted at a
fixed `STRATEGY_BAND` (50) with a `FALLBACK_BAND` (25) grind safety net.
`priorities.py` (123 lines) is the single source of every goal's priority number,
imported by ~10 goal files. `decide()` already ranks Tier-1 objective roots by
contribution/cost and emits `chosen_step` plus an **unused** `interrupt="restore_hp"`
flag. Guard/economy/task goals each compute `priority()` from `priorities.py`.

## Design

### Total preemption order

```
guards (interrupts)  >  collect-reward means  >  objective step  >  discretionary means
```

Heal / free the bag / clear a gate first → claim what's already earned → pursue
the objective → opportunistic filler. Bands are **structural**, not numeric: no
learned cross-band scoring (the rejected "common value currency" option). Within
a band, a fixed structural order.

### `StrategyDecision` (extended) — `tiers/strategy.py`

`decide()` returns:
- `interrupts: list[Guard]` — active guards only, in fixed guard order.
- `chosen_root` / `chosen_step` — unchanged (the objective frontier winner).
- `collect_reward: list[Means]` and `discretionary: list[Means]` — active means
  only, each in fixed within-band order.
- `ranking`, `desired_state` — unchanged (trace/shadow).

`Guard` and `Means` are lightweight frozen identifiers (an enum member or a
small frozen dataclass carrying a `kind` tag) — enough for the driver to map to a
goal and for the trace to render. They carry **no** goal instance (the driver
constructs goals, keeping `tiers/` free of `goals/` imports — the existing
layering rule).

### Guard tier — `tiers/guards.py` (new)

The single surviving priority ladder, scoped to guards: an **ordered tuple** of
guard kinds (highest preemption first) plus, for each, a pure trigger predicate
`(state, game_data, history) -> bool`. `decide()` evaluates the predicates and
emits the triggered guards in ladder order.

| Order | Guard kind | Trigger predicate | Goal (driver maps to) |
|---|---|---|---|
| 1 | `HP_CRITICAL` | `state.hp_percent < CRITICAL_HP_FRACTION` | `RestoreHPGoal()` |
| 2 | `BANK_UNLOCK` | bank locked and the unlock fight is attemptable | `UnlockBankGoal` |
| 3 | `REACH_UNLOCK_LEVEL` | a learned blocker requires a higher char level (within achievable gap) | `ReachUnlockLevelGoal` |
| 4 | `DISCARD_CRITICAL` | overstock present and `inventory_used ≥ 0.95·inventory_max` | `DiscardOverstockGoal` |
| 5 | `DEPOSIT_FULL` | `inventory_used ≥ 0.80·inventory_max` and bank accessible | `DepositInventoryGoal` |
| 6 | `DISCARD_HIGH` | overstock present and `inventory_used ≥ 0.85·inventory_max` | `DiscardOverstockGoal` |

This preserves `priorities.py`'s documented precedence (hard prerequisite gates
above discard-critical; deposit-full above discard-high). The graduated
`priorities.py` ramps (deposit 0→80, discard 40/55/85) collapse
into discrete trigger thresholds + fixed order: a guard either fires (and
preempts every means) or it doesn't. Threshold fractions move to named constants
in `guards.py`. `CRITICAL_HP_FRACTION` is the existing constant. Guards never
need sticky commitment (they are state-triggered).

The trigger predicates reproduce the *activation* conditions currently embedded
in each guard goal's `priority()` (e.g. `DepositInventoryGoal`'s ramp start,
`DiscardOverstockGoal`'s pressure fractions, `UnlockBankGoal`/`ReachUnlockLevelGoal`'s
gate checks). Those goals keep `is_satisfied`/`relevant_actions`/`desired_state`/
`value` for planning and lose `priority()`.

### Means bands — `tiers/means.py` (new)

Two ordered tuples of means kinds with the same predicate shape. A means appears
in the decision only when its predicate fires.

**Collect-reward band** (above the objective step):
| Order | Means kind | Fires when | Goal |
|---|---|---|---|
| 1 | `CLAIM_PENDING` | pending items waiting | `ClaimPendingGoal` |
| 2 | `COMPLETE_TASK` | held task fully progressed | `CompleteTaskGoal` |
| 3 | `SELL_PRESSURED` | bag-pressure and sellable stock present | `SellInventoryGoal` |
| 4 | `LOW_YIELD_CANCEL` | projection shows alternatives clearly pay more | `LowYieldCancelGoal` |
| 5 | `TASK_CANCEL` | held task structurally too-hard / unwinnable | `TaskCancelGoal` |

**Discretionary band** (below the objective step):
| Order | Means kind | Fires when | Goal |
|---|---|---|---|
| 1 | `ACCEPT_TASK` | no task held | `AcceptTaskGoal` |
| 2 | `TASK_EXCHANGE` | enough task-coin for a full batch | `TaskExchangeGoal` |
| 3 | `SELL_IDLE` | sellable stock, no bag pressure | `SellInventoryGoal` |
| 4 | `BANK_EXPAND` | gold ≥ next expansion cost and slots tight | `ExpandBankGoal` |

Cancels live in collect-reward: shedding a dead-weight task is net-positive
housekeeping that should clear before the objective step re-engages; they fire
only when a task is held and the predicate flags it. The means predicates reuse
the *same conditions* the goals' `is_satisfied`/`value` already encode (lifted so
the driver can order without instantiating); the goals keep their planning
methods and lose `priority()`.

`SellInventoryGoal` appears in both bands under different predicates
(`SELL_PRESSURED` vs `SELL_IDLE`); the driver maps both kinds to the same goal.

**Intended behavior change:** in `priorities.py`, `COMPLETE_TASK` (90) outranked
`DEPOSIT_FULL` (80); under the new strata every guard (deposit-full included)
preempts collect-reward, so a bag at ≥0.80 deposits *before* turning in a
finished task. This is deliberate — a full bag makes the post-completion loop
(accept next task, gather) fail until cleared, so freeing it first is correct.

### Driver — `strategy_driver.py`

```python
def select(decision, state, game_data, actions, planner) -> Goal | None:
    # 1. Guards: ordered, already triggered. First that plans wins.
    for guard in decision.interrupts:
        goal = map_guard(guard, state, game_data)
        if _plans(goal, state, game_data, actions, planner):
            return _commit(goal)
    # 2. Means, in band order: collect-reward, objective step, discretionary.
    for means in decision.collect_reward:
        goal = map_means(means, state, game_data)
        if _plans(goal, ...):
            return _commit(goal)
    step_goal = strategy_goal(decision.chosen_step, state, game_data, combat_monster)
    if step_goal is not None and _plans(step_goal, ...):
        return _commit(step_goal)
    for means in decision.discretionary:
        goal = map_means(means, state, game_data)
        if _plans(goal, ...):
            return _commit(goal)
    return None
```

- **Top-plannable, not top-ranked.** `_plans` runs the planner against the
  candidate; an unplannable candidate (no route/resources) falls through to the
  next. This subsumes today's `FALLBACK_BAND` grind safety net — the objective
  step or a lower means is reached naturally when a higher one can't plan.
- **Sticky commitment moves here.** The driver remembers the committed means key
  (the chosen step/means repr) across cycles and stays on it until it is
  satisfied, becomes invalid (predicate stops firing / goal `is_satisfied`), or a
  higher stratum preempts. This replaces `_select_goal`'s sticky logic. Guards
  bypass stickiness.
- **`map_guard` / `map_means`** are the guard/means → `Goal` constructors; they
  live in `strategy_driver.py` (above `goals/` and `tiers/`, the only layer
  allowed to import both). `map_means` extends today's `strategy_goal`.

### Selection-core retirement (`player.py`)

- `_select_goal` (max-`priority()` + sticky commitment) — **deleted**; the driver
  decides.
- `_build_goals` no longer assembles a flat ranked list. The per-cycle flow
  becomes: build `state` → `decision = self._strategy.decide(state, game_data)` →
  `goal = select(decision, state, game_data, actions, planner)`.
- `MetaGoalAdapter` loses its `priority_band` (the driver orders directly); it
  shrinks to a plain repr wrapper or is removed if the driver returns inner goals
  directly. `STRATEGY_BAND` / `FALLBACK_BAND` retire.
- `priorities.py` — **deleted**; the ~10 goal `priority()` methods that imported
  it are removed; `learning/projections.py`'s use is replaced (it referenced
  band constants for projection math — fold the needed value into the projection
  or the guard/means modules).

### Cleanup (delete all provably-dead)

Verified by grep (no live reader) + green suite:
- `_committed_upgrade_target`, `_upgrade_target_still_valid`, and the per-cycle
  committed-target computation in `_build_goals`.
- `state.crafting_target` and the now-dead branches in `active_gathering_skills`
  and any consumer that existed only for tool-relevance priority; drop the
  `crafting_target` argument from `active_gathering_skills`.
- `_gating_skill_targets`.
- `FarmMonsterGoal` and `FarmItemsGoal` classes + their tests (dormant since P3b).
- Any `priorities.py`-only helper left unreferenced.

## Error handling

- `select` returns `None` when nothing plans → existing idle/recovery path (no
  raise). `decide()` already never raises.
- A guard whose goal can't plan (e.g. bank unreachable) falls through to the next
  guard/means — the bot is never wedged on an unplannable interrupt.
- Trigger predicates are pure and read only `state`/`game_data`/`history`; a cold
  history defers to structural conditions (matching current goal behavior).

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **Guard ladder (`guards.py`):** each trigger predicate fires / does not at its
  threshold; `active_guards(state, gd, history)` returns triggered guards in
  ladder order; HP outranks all; deposit/discard thresholds correct.
- **Means bands (`means.py`):** each predicate fires per its condition; band
  membership + within-band order; `SELL_PRESSURED` vs `SELL_IDLE` mutually
  exclusive on bag pressure.
- **Driver (`strategy_driver.py`):** returns the top *plannable* candidate;
  falls through an unplannable higher candidate to a lower one; a triggered guard
  preempts all means; commits stickily to the chosen means and switches only on
  satisfy/invalidate/higher-preempt; returns `None` when nothing plans.
- **Player integration:** end-to-end `decide`→`select` gives sane sequences —
  bag-full → Deposit; done-task → CompleteTask; healthy + gear gap → objective
  step; idle + no task → AcceptTask; nothing → `None`.
- **Retirement:** `_select_goal`/`priorities.py` tests removed; a repo grep for
  `import priorities` / `from artifactsmmo_cli.ai.priorities` returns nothing;
  goal classes no longer define `priority()`.
- **Cleanup:** FarmMonster/FarmItems tests removed; grep confirms
  `_committed_upgrade_target` / `crafting_target` / `_gating_skill_targets`
  unreferenced.

## Files

- Create: `src/artifactsmmo_cli/ai/tiers/guards.py` (guard ladder + predicates),
  `src/artifactsmmo_cli/ai/tiers/means.py` (means bands + predicates).
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`StrategyDecision` +
  `decide` emit guards/means), `src/artifactsmmo_cli/ai/strategy_driver.py`
  (`select` arbiter, `map_guard`/`map_means`, sticky commitment), `player.py`
  (retire `_select_goal`, rewire `_build_goals`/cycle, delete dead plumbing).
- Delete: `src/artifactsmmo_cli/ai/priorities.py`;
  `src/artifactsmmo_cli/ai/goals/farm_items.py` (FarmItemsGoal). Remove the
  `FarmMonsterGoal` class from `src/artifactsmmo_cli/ai/goals/combat.py` (which
  also holds `AcceptTaskGoal`/`CompleteTaskGoal` — keep those; the file stays).
  Remove `priority()` from the remaining goal classes.
- Tests: new `test_tiers_guards.py`, `test_tiers_means.py`; extend
  `test_strategy_driver.py`/`test_player.py`; remove obsolete
  `test_priorities.py`, FarmMonster/FarmItems tests, `_select_goal` tests.

## Out of scope

- Tactical policies / battle-prep (P4): weapon swaps, consumable-vs-rest,
  craft-vs-buy.
- Pluggable AI personalities weighting skill/level/balanced (P5).
- A learned gold→progress valuation (the rejected "common value currency"); means
  stay structurally banded.
