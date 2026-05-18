# Strategic Reasoning Layer (Phase G) — Design

**Date:** 2026-05-18
**Status:** Draft
**Prior phases:** Robustness Layer (2026-05-15), Autoregressive Planning (2026-05-17)

---

## Motivation

The GOAP player works tactically — given a goal, pick the cheapest plan that
satisfies it. The autoregressive layer added local adaptation: an action's
cost reflects its learned cooldown and success rate; a goal's value reflects
its learned cycles-to-satisfy. Both bias *individual* choices.

What's missing is **strategic** reasoning: deciding *which goal is worth
pursuing right now* based on projected throughput.

Concrete failure case observed in real play:

- Robby accepts a taskmaster items-task: `gudgeon ×347`.
- ~3 hours of fishing yields a fixed payout (gold + ~3 tasks_coin) on
  CompleteTask, plus fishing-skill XP that doesn't level his character.
- An equivalent 3 hours of monster-hunting could earn ~2 character levels,
  weapon drops, and several monster-task completions worth their own
  tasks_coin batches.
- Robby never weighs the two. He grinds whatever the taskmaster handed him.

Goal priority is currently hardcoded (`FarmItems=35`, `FarmMonster=30`,
`UpgradeEquipment=35`, etc.). Those constants encode a designer's guess at
"what should usually win." The strategic layer replaces those guesses with
projections grounded in observed throughput.

## Out of scope

- Multi-character coordination. Robby is solo.
- Market/economy modeling beyond NPC sells/buys + known coin-exchange payout.
- Predicting *what* the taskmaster will hand out next (no public RNG seed).

## Current state (what the autoregressive store already gives us)

Per `Cycle` row, the store records (today):

- `action_repr`, `selected_goal`, `outcome`
- `predicted_cost`, `actual_cooldown_seconds`
- `delta_xp`, `delta_hp`, `delta_gold`, `delta_inventory_used`
- `planner_nodes`, `planner_depth`, `planner_timed_out`, `plan_len`
- `cycles_to_satisfy` (filled the moment the goal becomes satisfied)

Queries already available:

- `action_cost(repr, default, window)` — median cooldown observed
- `success_rate(repr, window)`
- `action_effect(repr, key, window)` — median delta on a specific field
- `goal_avg_cycles_to_satisfy(repr, window)`

What's missing:

- **XP source attribution.** `delta_xp` is a single number; we can't tell
  whether a Fight gave 12 character-XP or a Craft gave 12 weaponcrafting-XP.
- **Goal-level rate aggregation.** We know cycles-to-satisfy per goal, but
  not "expected character-XP per cycle" or "expected gold per cycle" while
  *pursuing* that goal.
- **Cross-goal comparison.** No primitive for "if I drop my current goal and
  pivot to goal G, how much better off am I in T cycles?"

## Proposed architecture

Five pieces, layered.

### 1. Extend the per-cycle record (data layer)

Add columns to `Cycle`:

- `delta_char_xp: int` — character-XP gained this cycle (separate from skill XP)
- `delta_skill_xp_json: str` — JSON map `{skill_name: delta}` (sparse)

The character API returns both `xp` (character) and `<skill>_xp` per skill.
`GamePlayer._record_learning_cycle` already diffs `prev_state` vs `new_state`;
extend it to diff each skill independently.

Migration: add columns with default values so old DBs work.

### 2. Throughput projections (estimator layer)

New module `src/artifactsmmo_cli/ai/learning/projections.py` with pure
functions over the store:

- `cycles_for_progress(goal_repr, store) -> float` — average cycles per
  "progress unit" while a goal was active. For FarmItems with a `gudgeon`
  task, progress unit = 1 fish delivered. For FarmMonster, progress unit =
  1 monster killed (proxied by Fight outcome=ok). Falls back to a default
  if sample count < N.
- `expected_yield_per_cycle(goal_repr, store) -> Yield` where `Yield` is a
  pydantic model:

  ```python
  class Yield(BaseModel):
      char_xp: float = 0.0
      skill_xp: dict[str, float] = {}
      gold: float = 0.0
      tasks_coins: float = 0.0
      drop_value: float = 0.0  # estimated NPC-sell value of incidental drops
  ```

- `project_task_completion(state, store) -> TaskProjection` — for an in-flight
  items- or monsters-task, returns total expected cycles and total expected
  reward (gold + coin payout + character XP).

All projections use windowed history (default last 100 cycles) and return
`None` (or a low-confidence sentinel) when the sample count is below a
threshold. Strategic goals must check the sentinel and defer to the existing
hardcoded priorities until warm.

### 3. A scalarizer (preference layer)

Different yields aren't fungible. We need a single number per cycle so we
can compare "Goal A: 5 char-XP/cycle + 0.1 gold/cycle" against "Goal B: 0
char-XP/cycle + 2 fishing-XP/cycle + 0.05 tasks_coin/cycle".

Proposal: a `value_function(yield, state)` that returns a scalar in units
of "approximate cycles-to-next-character-level equivalent":

- Character XP weighted by `(level + 1)` so leveling up is roughly
  preserved as the goal.
- Skill XP weighted by `0.2` plus a multiplier if the skill is on the
  critical path to a known craftable upgrade (reuses
  `GameData.active_gathering_skills` for craft-skill upgrades too).
- Gold weighted by `1 / xp_to_next_level / 100` (small but non-zero).
- tasks_coins weighted by their *expected* exchange value (see §4).

These weights are tunable constants in one place. Real-play telemetry
should inform them but we don't need a learned weight model to ship.

### 4. Tasks-coin exchange value (estimator subcomponent)

`TaskExchange` burns 3 coins and returns 1+ items from a random pool. We
don't know the pool a-priori, but we can observe: every time the player
calls TaskExchange, the action's `delta_inventory_used` and any new item
codes tell us what dropped. The store already has `action_effect`. Add a
projection `expected_coin_value(store) -> float` that averages the
NPC-sell value of items received across past TaskExchange calls, divided
by 3 (coins per call).

Default while warming: use a constant (e.g. "1 coin ≈ 5 gold").

### 5. Strategic goals (decision layer)

Three new goals, all priority-driven by the projections above:

#### `CancelTaskGoal`

- **Active when:** Robby holds a task AND the projection says completing it
  has lower expected reward-per-cycle than the best alternative goal,
  *after* accounting for the 1-coin cancel cost.
- **Math:**

  ```
  current_rate    = task_projection.scalar_reward / task_projection.cycles_remaining
  best_alt_rate   = max(yield_scalar(g) for g in alternative_goals)
  cancel_cost     = scalar_value_of(1 tasks_coin) + cycles_to_walk_to_taskmaster
  fires_when:     (best_alt_rate * task_projection.cycles_remaining) - cancel_cost
                  > task_projection.scalar_reward
  ```

- **Action:** `TaskCancelAction` (already exists).
- **Priority:** 70 — high, but below survival (RestoreHP) and bank-state
  goals (UnlockBank).

#### `LevelSkillGoal(skill: str)`

- **Active when:**
  1. There exists a craftable upgrade gated on `skill` level ≥ N
  2. Robby's current `skill` level < N
  3. `N - current` ≤ a reasonable threshold (e.g. 5) so we don't try to
     bootstrap from 1 to 30 in one strategy pivot
- **Math:** Same scalarizer applied to "craft cheapest no-prereq item in
  `skill`'s recipe family repeatedly until level N."
- **Action set:** Existing CraftAction and GatherMaterialsGoal logic, but
  with a different target.
- **Priority:** depends on projected payback. If the skill levelup unlocks
  a tool that cuts active-task cycle time by >X%, priority = 55 (beats
  FarmItems but loses to CancelTask if both would fire).

#### `GrindCharacterXPGoal`

- **Active when:** no task held AND best monster grind gives a clearly
  better scalar-per-cycle than other available goals.
- **Action set:** Existing FarmMonster, but targeting the highest-level
  monster Robby can beat reliably (proxy: success_rate ≥ 0.8 over last
  50 fights).
- **Priority:** computed from projection; usually 30–45.

### Goal-priority math, end-to-end

Today `_build_goals` returns goals with hardcoded priorities. Under this
proposal, **every priority is computed**:

```
priority(g, state) = base_priority(g) * confidence(g, store) +
                     value_per_cycle(g, store) * weight
```

`base_priority` keeps the survival floor (RestoreHP=80, UnlockBank=70 — these
must always dominate). `value_per_cycle` is the scalarized yield from §3.
`confidence` is in [0, 1] based on sample count; warm goals get a real
projection, cold goals fall back to designer constants.

This means the existing FarmItems/FarmMonster/UpgradeEquipment values
become starting estimates. The store overwrites them as evidence
accumulates.

## Open questions

1. **When does Robby trust the projection?** Need a confidence threshold.
   Strawman: ≥ 30 cycles of observed `progress`. Too low and we cancel
   tasks on noise; too high and Robby never adapts.

2. **Action-attribution for `goal_active_during(cycle) → goal_repr`.** The
   store records the *selected* goal per cycle. But a cycle's reward
   belongs partly to the *acting* goal and partly to side effects
   (TaskTrade always progresses task even if FarmItems wasn't the goal that
   selected it that cycle). Simpler: attribute the whole cycle to the
   selected goal. Good enough for v1.

3. **Skill-XP weight calibration.** Picking `0.2` is arbitrary. Could
   instead measure: "how many skill-XP equivalents does it take to enable a
   craftable upgrade equivalent to 1 character-level's worth of fight
   capability?" Punted to a follow-up.

4. **TaskmasterRNG.** We can't predict what the next task will be, so
   CancelTaskGoal's expected-alt-rate has to assume *the average* task,
   not the specific next draw. The store tells us the distribution of past
   tasks; use the *median* task scalar reward as the baseline. (Selection
   bias risk: if we cancel only bad tasks, the median stays artificially
   high. Track this via a "tasks_seen" counter, not "tasks_completed".)

5. **Coupling to spec for autoregressive planning.** Phase G builds on the
   `Cycle`/`Session` storage from Phase F. No schema break, only column
   additions. Old data still queryable; new projections silently degrade
   to fallback when historical rows lack the new columns.

6. **Are TaskExchange reward items even worth scalarizing right now?**
   Items dropped from coin exchange might be high-tier equipment Robby
   can't equip yet. Their NPC-sell value is a weak proxy. Until we know
   more, use NPC sell-back gold + a "future-equippable" bonus only if the
   item is craftable into something Robby could use.

## Phasing

This is large. Suggested split:

- **G-A — Data layer extension (~1 day):** new Cycle columns,
  `_record_learning_cycle` populates them, migration tested. Ship without
  consumers.
- **G-B — Projections module (~1 day):** `projections.py` with pure
  functions + tests using a synthetic in-memory store.
- **G-C — Scalarizer + value_function (~1 day):** weights as constants;
  unit tests assert expected ordering for canned scenarios.
- **G-D — CancelTaskGoal (~1 day):** first strategic goal; integration
  test that simulates a low-yield task vs a high-yield alternative.
- **G-E — LevelSkillGoal + GrindCharacterXPGoal (~1 day each):**
  parameterized on data, but the integration plumbing mirrors G-D.
- **G-F — Priority computation rewrite (~1 day):** replace hardcoded
  priorities with `base + confidence * value_per_cycle`. Regression-test
  every existing goal stays selected in the same scenarios where the old
  constants picked it.

Each sub-phase is one writing-plans-style implementation plan. Land G-A
first because every later piece reads its columns.

## Success criteria

After Phase G ships:

- Trace shows `CancelTaskGoal` firing when the current task's projected
  reward-per-cycle drops below the median alternative.
- After ~100 cycles of warmup, goal priorities visibly diverge from their
  hardcoded defaults (assert via a small CLI: `artifactsmmo learn
  show-projections`).
- Real-play: Robby measurably reaches level 5+ faster than current main
  (concretely, fewer wall-clock hours per character level), even though
  he's the same character class.
- No regression: every existing test still passes; new tests cover each
  projection edge case (zero samples, all-failure samples, single sample,
  warmup boundary).
