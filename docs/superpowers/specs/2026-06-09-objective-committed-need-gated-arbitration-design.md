# Objective-committed, need-gated arbitration

**Date:** 2026-06-09
**Status:** Design — approved for planning
**Area:** `src/artifactsmmo_cli/ai/` (strategy arbiter, decision tier, means tier, planner)
**Supersedes:** parts of `2026-06-08-levelskill-gating-prioritization-design.md` (the
`reorder_skill_candidates` mechanism is removed; `gating_skills` /
`skill_grind_target` are retained and repurposed)

## Problem

Trace `play-trace-Robby-20260608-233647.jsonl` (676 cycles, post-merge of the
LevelSkill gating feature): the character is **stuck at level 4 with zero fights
for the entire run**. `weaponcrafting_xp` is frozen at 65; `selected_goal` is
`PursueTask` 632 / `CraftRelief` 38 / `CompleteTask` 3 / `AcceptTask` 3. The bot
farms items-tasks (`cooked_gudgeon`, `sunflower`, `copper_ore`) forever and never
gears up for combat.

### Root cause (evidenced)

`goals_tried` length is **1 in all 676 cycles**, including the 3 task boundaries.
The arbiter never reaches the objective-step tier. Mechanism, in layers:

1. **Sticky short-circuit (dominant).** `arbiter_select.select_pure` tries the
   committed discretionary goal (`PursueTask`, or `CompleteTask`/`AcceptTask` at
   boundaries) FIRST; it plans, and the walk short-circuits before any objective
   step is probed. The strategically-correct goal (a weaponcrafting grind) is
   never evaluated. Pre-merge trace `210337` probed ~9 goals at boundaries;
   post-merge it is 1 — the gating-feature reorder closed that window too.
2. **Scoring.** `ReachSkillLevel(weaponcrafting)` scores ≈ `0.6 × 0.2 × balance ≈
   0.12` (`tiers/strategy.py` `PRIOR_COMBAT_CRAFT_SKILL` × `SKILL_MARGINAL`) — the
   lowest-ranked fallback step. Even if probed, it is last.
3. **Reorder placement.** The shipped `reorder_skill_candidates` moves the
   (now-plannable) gating craft-one AFTER `PursueTask` (during a task) / AFTER
   `AcceptTask` (at a boundary, compounded by the `task_code is None → step_goal =
   None` rule at `strategy_driver.py:573-575`). So even when reached, the task
   goal wins first. This is the "AcceptTask is over-prioritized" symptom.

**Circular combat dead-end:** `ReachCharLevel → GrindCharacterXP` returns `None`
when `combat_monster is None` (`strategy_driver.py:354`). Not combat-capable → no
combat goal → 0 fights. Becoming combat-capable needs a better weapon → the weapon
is weaponcrafting-gated → the weaponcrafting grind is never engaged (layers 1-3) →
weapon never crafted → never combat-capable. Self-perpetuating.

### Why this is architectural, not a patch

The arbiter uses **planning-cost-avoidance (the sticky short-circuit) as its
priority mechanism**: priority is effectively "whoever is committed and can plan
cheaply," not "what is strategically most valuable." Stickiness itself is not
wrong — every multi-step goal needs to be pursued for a stretch. The defect is
that stickiness is **selective**: tasks are sticky, weapon upgrades are not, so a
slow-but-correct weapon plan is perpetually hijacked by an always-available task
plan that makes faster *local* progress on something the bot does not need.

The fix is to make the **long-term objective the unit of commitment**, and to
gate every replan by whether it actually serves that objective.

## Principle

> Remember the long-term objective. Each replan, evaluate whether the new plan is
> worth pursuing toward that objective; discard "worse" plans (e.g. a `PursueTask`
> that yields gold / skill-XP we do not need) and stay committed to the objective.

## Design

### Component 1 — Objective memory (commitment unit)

The committed long-term objective is the decision tier's `chosen_root`
(`StrategyEngine.decide`, `tiers/strategy.py`). It is already computed every cycle,
already carries `STICKY_DOMINANCE_RATIO = 1.5` hysteresis, and is already persisted
across cycles (`player._last_strategy_root` → `decide(last_chosen_root=...)`). The
objective changes only when a new root dominates the incumbent by the ratio. **No
new state** — today the arbiter simply ignores this memory. The redesign makes the
arbiter honor it.

### Component 2 — Objective needs (`tiers/objective_needs.py`, new)

Pure, no planning:

```python
def objective_needs(root: MetaGoal, state: WorldState, game_data: GameData) -> NeedSet
```

`NeedSet` (frozen value object) captures the committed objective's UNMET needs,
derived from state alone:

- **materials**: items in the objective's `recipe_closure` not yet owned
  (`recipe_closure` − inventory − bank − equipped).
- **skill_xp**: the binding gating skill(s) from `gating_skills` (retained from the
  prior feature), **scoped to the committed objective's own item** (not the
  full gear/tool/task/combat want set) — the craft skill whose `craft.level` blocks
  this objective.
- **gold**: a gold threshold, only when buying is the SOLE source of an otherwise
  unobtainable input (no recipe, no gather, no winnable drop).
- **char_xp**: set when the objective is (or descends to) a `ReachCharLevel` gate.

`NeedSet` is the cheap, legible statement of "what would actually move me forward."

### Component 3 — Worth gate on means (`tiers/means_worth.py`, new)

Pure:

```python
def means_serves(kind: MeansKind, goal: Goal, needs: NeedSet,
                 state: WorldState, game_data: GameData) -> bool
```

A discretionary means is "worth pursuing" iff its OUTPUT satisfies an unmet need:

- `PURSUE_TASK` / `AcceptTask`: an items-task outputs (a) the craft/gather **skill
  XP** of its task item, (b) **`tasks_coin`** (→ taskmaster-exchangeable for needed
  resources), (c) **gold**. It serves the objective iff its skill-XP matches a
  `skill_xp` need, OR `tasks_coin`/gold is needed for a `materials`/`gold` need that
  is only obtainable that way. An items-task awarding cooking-XP + gold while the
  objective is a weapon serves NO need → not worth pursuing.
- `SELL_IDLE` / `BANK_EXPAND` / `TASK_EXCHANGE`: serve a need only when the need is
  gold / inventory space / a taskmaster-exchange input respectively.

If `needs` is empty (objective satisfied or no binding objective), the worth gate
is inert and means behave as today (tasks are the default activity). The gate only
bites when there IS an unmet objective the means does not serve.

### Component 4 — Arbiter: objective-step-first, need-gated means (`strategy_driver.py`)

Replace the sticky-short-circuit + "first plannable means wins" walk with:

1. **Guards** unchanged (survival/bank/gear-review preempt everything).
2. **Objective step.** Plan the committed objective's `chosen_step` (and its
   ranked fallback steps). If one plans → select it. This is direct objective
   progress and is evaluated BEFORE any non-serving means. Commitment now attaches
   to the objective (its step repr), not to a means.
3. **Need-serving means.** If no objective step plans, walk the discretionary means
   but SKIP any means where `means_serves(...) is False`. The first need-serving
   plannable means wins (e.g. a task that earns `tasks_coin` for a needed input).
4. **Last resort.** If neither an objective step nor a need-serving means plans,
   fall back to the highest-ranked plannable means **ignoring the worth gate** (the
   pre-redesign behavior — typically `PursueTask` for income / keep-moving) so the
   bot never idles. This path is explicit and emitted to the trace (a
   `worth_gate_bypassed` marker), not silent, so "objective stalled, doing income
   instead" is observable rather than indistinguishable from normal task pursuit.

The committed-objective replan is "evaluated for worth" each cycle: a replan that
yields a non-serving means is discarded in favor of staying on the objective step
(steps 2-3). The dominance hysteresis on `chosen_root` (Component 1) prevents
objective thrash.

### Component 5 — Plannable objective steps (retain craft-one)

`skill_grind_target` (retained) keeps a gating-skill step shallow and plannable:
`objective_step_goal` maps a `ReachSkillLevel` step whose skill is a binding gate to
`GatherMaterialsGoal(craft_one_target, {target: 1})` instead of the
width-unfindable `LevelSkillGoal(current+3)`. This moves the craft-one from the
removed reorder into normal step generation. A gating craft skill with no craftable
item at the current level remains a `SkillProgressionError` (LIV-SKILL-2, retained).

### Component 6 — Remove the reorder

`reorder_skill_candidates` (`strategy_reorder.py`) and its call site are removed:
objective-step-first + need-gating replace post-hoc repositioning. `gating_skills`,
`SkillGate`, `GateSource`, `SkillProgressionError`, `skill_grind_target` are
retained (now feed Components 2 and 5). Their unit tests stay; the reorder tests
are removed.

### Component 7 — Planner performance (profile-then-target)

Honest correction to an earlier mis-claim: the learned-cost lookups are ALREADY
memoized per search (`LearningStore._cached` over `search_cache()`,
`store.py:156-161`), so the ~20ms/node is **not** per-node SQLite — it is compute
(branching × `WorldState` copy / recipe-walk in `is_applicable`/`apply`) plus ~N
windowed `Cycle`-table aggregates per search (one per distinct action repr, growing
with the Cycle table).

Under the new arbiter the realistic load is ~1-2 planned goals/cycle (objective
step + maybe one need-serving means), not the ~25-candidate probe the old "revert
sticky" fear assumed — so perf is lighter than feared. Still, a **profiling pass**
precedes any change to pinpoint the dominant cost, then target it:

- index `Cycle` on `(character, action_repr, ts)` if the windowed aggregates scan;
- preload per-cycle cost aggregates once (not per search) if that is the cost;
- tighten `relevant_actions` branching / `WorldState.apply` copy if node-compute
  dominates.

Target: planning fits inside the ~29s game cooldown so it is hidden (median
overhead today is 2.8s; only deep replans exceed cooldown). No fixed numeric SLA is
asserted without the profile.

**Profile result (2026-06-09).** Offline profiling is not cleanly reproducible: no
learning DB is on disk (created at runtime, gitignored), and a synthetic deep goal
short-circuits in `relevant_actions`/`recipe_closure` before a real search runs, so
`cProfile` yields no representative node-expansion sample. The architectural facts
nonetheless settle scope: learned-cost lookups are already memoized per search
(`LearningStore._cached`), so cost is compute (node expansion: `WorldState.apply`
copy + `is_applicable` over the action set) plus ~N windowed `Cycle` aggregates per
search (N = distinct action reprs, growing with the table). Under the redesign the
arbiter plans ~1-2 goals/cycle (objective step + maybe one need-serving means), and
median planning overhead (2.8s) is hidden under the ~29s cooldown — only deep gear
replans exceed it. **Conclusion:** Task 7 is conditional and deferrable; it is best
done from a live `--learn` run with the planner instrumented to log per-search
wall-time + `nodes_explored`, then targeting whichever of {Cycle-table aggregates,
`apply` copy, branching} the live profile shows dominant. The behavior fix
(Components 1-6, 8) does not depend on it.

### Component 8 — Combat-readiness as binding objective

When `combat_monster is None`, the decision tier must make the combat-enabling
weapon `ObtainItem` the `chosen_root`. It already emits the weapon root; the change
is a **combat-readiness urgency multiplier** in `StrategyEngine._marginal` for the
combat-enabling weapon root — analogous to the existing inverse-gap char-level
urgency (`CHAR_GAP_PER_LEVEL`) — applied only while `combat_monster is None`, sized
to lift that root above competing gear/tool/skill roots so it becomes `chosen_root`.
Once a weapon makes the bot combat-capable, `combat_monster` resolves and the
multiplier switches off (no permanent override of the long-term objective). Its
`actionable_step` descends to the weaponcrafting gate → craft-one (Component 5). The
worth gate (Component 3)
rejects the items-task → the bot grinds weaponcrafting → crafts the weapon →
becomes combat-capable → `combat_monster` resolves → the existing `GrindCharacterXP`
combat goal activates and fighting resumes.

## Data flow

```
StrategyEngine.decide ──► chosen_root (objective, hysteresis)  ──► objective_needs() ──► NeedSet
   (persisted via _last_strategy_root)        │                                          │
                                              ▼                                          ▼
                              objective_step_goal(chosen_step)            means_worth.means_serves(means, NeedSet)
                                  (craft-one if gating-skill)                             │
                                              │                                          │
                                              ▼                                          ▼
   arbiter: guards ─► OBJECTIVE STEP (plan; win if plannable) ─► need-serving MEANS only ─► last-resort means
```

## Invariants / interactions

- **Hysteresis preserved:** objective changes only on `STICKY_DOMINANCE_RATIO`
  dominance at the decision tier (unchanged). Within a committed objective, the
  arbiter pursues its step / need-serving means — no per-cycle flap.
- **Liveness:** the last-resort means (step 4) guarantees the bot always has an
  action; `SkillProgressionError` still fires only on a true gating-skill deadlock.
- **Guards untouched:** survival/bank/gear-review still preempt the objective.
- **Empty NeedSet ⇒ legacy behavior:** with no binding objective, means run as
  today (no regression for a maxed/idle character).

## Testing

Per project rules: 0 errors, 0 warnings, 0 skipped, 100% coverage; all tests in
`tests/`, real fixtures, no mocking the unit under test.

- `objective_needs`: closure-material, gating-skill-xp, buy-only-gold, char-xp gate
  cases; empty NeedSet when objective satisfied.
- `means_serves`: items-task whose skill-XP matches a need → True; same task when
  objective is an unrelated weapon → False; `tasks_coin`-for-needed-input → True;
  gold-needed vs gold-not-needed.
- Arbiter integration: stuck-state fixture (level 4, no weapon, weaponcrafting
  gated, items-task active) → selects the weaponcrafting craft-one, NOT `PursueTask`
  (the trace bug, locked by a regression test). Objective-satisfied fixture →
  `PursueTask` still wins (no regression). Last-resort path → an action is always
  returned.
- Combat-loop closure (simulated multi-cycle): weaponcrafting rises across cycles →
  weapon becomes craftable → `combat_monster` resolves → `GrindCharacterXP`
  selectable. Asserts the bot is no longer frozen.
- Remove `reorder_skill_candidates` tests; keep `gating_skills` /
  `skill_grind_target` tests.

## Implementation phases (one spec, sequenced)

1. **Profile** the planner; record the dominant cost (informs Component 7 scope).
2. `objective_needs` + `means_serves` pure modules + tests.
3. Arbiter rewrite: objective-step-first + need-gated means + last-resort;
   move craft-one into `objective_step_goal`; remove `reorder_skill_candidates`.
4. Decision-tier: ensure the combat-enabling weapon is the `chosen_root` when not
   combat-capable (Component 8).
5. Planner perf change targeted by the Phase-1 profile.
6. Full regression vs the captured stuck-state trace; 100% coverage gate.

## Files

New:
- `src/artifactsmmo_cli/ai/tiers/objective_needs.py` — `objective_needs`, `NeedSet`.
- `src/artifactsmmo_cli/ai/tiers/means_worth.py` — `means_serves`.

Modified:
- `src/artifactsmmo_cli/ai/strategy_driver.py` — arbiter walk (objective-step-first,
  need-gated means, last-resort); craft-one into `objective_step_goal`; drop the
  reorder call + `task_code is None → step_goal = None` AcceptTask over-priority.
- `src/artifactsmmo_cli/ai/tiers/strategy.py` — combat-enabling weapon ranks as
  `chosen_root` when not combat-capable.
- Planner module(s) per the Phase-1 profile.

Removed:
- `src/artifactsmmo_cli/ai/strategy_reorder.py` + its tests.

Retained from the prior feature: `tiers/skill_gates.py`, `tiers/skill_grind_target.py`.

Out of scope: combat-formula / loadout changes; learning-store schema beyond an
index; any new objective beyond what `objective_roots` already emits.
