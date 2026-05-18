# Max-Level Objective Layer — Design

**Date:** 2026-05-18
**Status:** Draft
**Prior phases:** Robustness (2026-05-15), Autoregressive (2026-05-17),
Strategic Reasoning Phase G (2026-05-18), Generalization Pass (2026-05-18).

---

## Motivation

Phase G added strategic goals (`LowYieldCancelGoal`, `LevelSkillGoal`,
`GrindCharacterXPGoal`) that compare per-cycle yield against alternatives.
The Generalization Pass collapsed special-casing into reusable primitives
(action tags, priority ladder, blocker registry). Documented blockers
were then seeded into the registry so the full progression map is visible.

What's still missing: a single **root objective** the rest of the system
serves. The user's stated primary goal:

> **Find the cheapest path to maximum character level.**

Every other concern (tasks, gold, equipment, skill XP) is a *means* to
that end. Without an explicit root, the existing layers compete on local
metrics:

- Scalarizer weights char_xp by `(state.level + 1)` — gives char_xp a
  boost, but skill_xp / gold / coins still contribute. A goal that pays
  10 skill_xp/cycle can outscore one that pays 1 char_xp/cycle at low
  level.
- `LowYieldCancelGoal` cancels when an alternative scalar exceeds the
  current task's scalar — but scalar is goal-agnostic and doesn't ask
  "does this contribute to max level?"
- `LevelSkillGoal` fires when a craftable upgrade is gated on +N skill —
  but it doesn't ask "will that upgrade actually speed up character
  leveling, or just enable a side branch?"

Concrete failure: Robby spent ~3 hours fishing 347 gudgeon for ~150 gold
+ 1 tasks_coin batch + 0 character XP. Strategic layer eventually
canceled — but only after enough projection samples accumulated. With a
root objective, the cancel would be *immediate*: "this task yields zero
char_xp per cycle for the next 340 cycles; any alternative paying any
char_xp/cycle wins by definition."

## Goal restated formally

Given a character at `state.level` with `state.xp / state.max_xp`
progress into the next level, and a maximum character level `L_max`
(observed from `game_data._monster_level` = 55):

**Minimize** the expected number of action cycles required to reach
`state.level == L_max`.

Equivalently: at every decision point, **maximize** the projected
character-XP rate (XP per cycle), accounting for prereq chains.

## Out of scope

- Optimizing for anything *beyond* max level (e.g. legendary loot drops,
  PvP rankings). Once max level is reached, this layer hands off to
  whatever the user wants next (could be a separate spec).
- Multi-character optimization. Robby is solo.
- Real-time event chasing (event spawn timing). Phase H or later.

## Current state recap

Available primitives:

- `BlockerRegistry`: full documented + discovered progression map.
  `BlockerState` has prereq metadata (required_level, required_skill +
  level, unlock_monster, required_item).
- `LearningStore` per-action stats:
  `action_cost`, `success_rate`, `action_effect("delta_xp", ...)`,
  `recent_goal_cycles`, `expected_yield_per_cycle`, plus per-skill XP
  deltas (G-A `delta_skill_xp_json`).
- `Yield` projection: per-cycle `char_xp, skill_xp{}, gold, tasks_coins`.
- `scalar_yield(yield, state, gd, store)`: collapses to one number with
  designer weights. Useful but not aligned to max-level.

What's missing:

- A canonical `L_max` discovered or asserted.
- A `cheapest_path_to_level(target_level, current_state, registry, store)`
  projection that walks prereqs and computes expected cycles.
- A meta-policy in `GamePlayer._build_goals` or above it that orders
  goals by their *contribution to remaining cycles to max*, not by
  hardcoded priorities.

## Proposed architecture

Three layers, smallest first.

### 1. Max-level discovery and exposure

Add `GameData.max_character_level` as an explicit cached value. Computed
at load time as `max(game_data._monster_level.values())` plus a small
safety margin (so the bot doesn't think L55 is the cap when L56+ monsters
exist undocumented). Or read from a known API endpoint if one exists
(needs probing).

Used by:
- `RootObjective.is_satisfied`: `state.level >= L_max`
- `cheapest_path_to_level`: bounds the search
- Trace metadata: every cycle records `remaining_levels`

### 2. `cheapest_path_to_level` projection

New function in `learning/projections.py`:

```python
def cheapest_path_to_level(
    target_level: int,
    state: WorldState,
    registry: BlockerRegistry,
    store: LearningStore,
    game_data: GameData,
) -> PathPlan:
    """Estimate the cycle cost of reaching target_level from current state.

    Walks the blocker registry as a DAG. Each combat blocker has an
    associated monster; the planner asks the store for that monster's
    observed XP/cycle (or game-data default for unobserved monsters).

    Returns the (action_chain, total_cycles_estimate) tuple for the
    cheapest path, or None when no path exists.
    """
```

Implementation sketch:

1. Build adjacency: from current state, enumerate `fight:<monster>`
   blockers where `state.level >= required_level - 1` (already
   beatable). Each is a frontier node.
2. For each frontier monster, get `expected_yield_per_cycle(f"FarmMonster({code})")`.
   Use observed char_xp, or fall back to a game-data default
   (e.g. `monster.level * 5` based on observation that XP scales with
   monster level).
3. Compute cycles-per-level from current XP curve:
   `xp_to_next_level / observed_xp_per_cycle`.
4. Recurse for next level: after gaining one level, more monsters become
   beatable (frontier expands). Use registry to see which.
5. Total: ∑ `cycles_per_level` for each level from current to target.

This is approximate (assumes optimal grind per level). Good enough for
ranking goals.

### 3. `MaxLevelRootObjective`

Top-level objective that reorders goals based on their projected
contribution to closing the gap. Two implementation options:

**Option A (less invasive): a single high-priority goal**

```python
class MaxLevelRootObjective(Goal):
    """The root: drive to L_max via the cheapest available path."""

    def priority(self, state, gd, history) -> float:
        if state.level >= gd.max_character_level:
            return 0.0
        # When max-level path runs through a specific concrete goal
        # (e.g. FarmMonster(yellow_slime) is the cheapest current step),
        # return the priority of THAT goal — promote it. Otherwise return
        # a base priority that ensures something runs.
        path = cheapest_path_to_level(...)
        if path is None:
            return 0.0
        # Inject the path's first action as a "shadow goal" — see Option B.
        return priorities.MAX_LEVEL_ROOT  # ~100, below HP_CRITICAL only
```

Problem: a goal that returns "do this other goal" is awkward and
duplicates the existing goal-selection loop.

**Option B (cleaner): a meta-policy in `_build_goals`**

`_build_goals` already builds a list of (goal, priority) pairs. Add a
post-processing step that:

1. Computes `cheapest_path_to_level(L_max, ...)` once per cycle.
2. The path is an ordered list of *concrete actions* (e.g. "Fight yellow_slime"
   x N times, then "Fight green_slime", etc.).
3. For each existing goal in the list, ask: "is this goal's relevant_actions
   a superset of the next required action in the path?"
4. If yes: bump its priority to `MAX_LEVEL_ROOT_BOOST` (a big number).
5. If no: don't change.

This keeps the existing goal infrastructure intact. The root objective
just rewards goals that move along the optimal path.

**Option B recommended.** Less invasive, easier to test, doesn't add a
new "fake goal" pattern.

### 4. Char-XP-rate scoring of existing strategic goals

Update `LowYieldCancelGoal` and `GrindCharacterXPGoal` to use char-XP/cycle
directly when the root objective is active:

```python
# In LowYieldCancelGoal.priority():
if root_active:
    current_char_xp_per_cycle = farm_items_yield.char_xp
    alt_char_xp_per_cycle = alt_yield.char_xp
    # The OLD comparison used scalar_yield (which mixes everything).
    # Under root: only char_xp matters.
    if alt_char_xp_per_cycle > current_char_xp_per_cycle:
        return priorities.LOW_YIELD_CANCEL  # fire harder
```

The gudgeon case: `char_xp_per_cycle ≈ 0` (XP only at task completion).
Any alternative paying *any* char_xp/cycle wins immediately. Even one
cycle of FarmMonster(chicken) at 1 XP beats 100 cycles of FarmItems at 0.

This avoids the long warmup before LowYieldCancel fires under the current
opaque-scalar comparison.

## Open questions

1. **Does CompleteTask's lump-sum XP count as XP/cycle?** A task gives
   ~150 gold + 1 tasks_coin batch + some char XP only on
   `CompleteTaskAction`. The projection has to amortize the lump sum
   across the task duration: `xp_at_complete / total_task_cycles`. If
   that's competitive with monster grinding, FarmItems stays viable.
   Otherwise it gets canceled.

2. **How fresh is "observed XP per monster"?** If Robby grinded chickens
   100 cycles ago at level 1 (lots of XP) and is now level 30 (same
   chickens give near-zero XP), the historical average overestimates.
   Need windowed projection that prefers recent samples or weights by
   level-since.

3. **Path projection feasibility under timeout.** `cheapest_path_to_level`
   could be expensive if naïve — 50 levels × N candidate monsters per
   level = thousands of combinations. Cache aggressively. Compute once
   per cycle, not per goal. Cap depth (e.g. only project next 5 levels;
   beyond that, assume "current best grind continues").

4. **What about character XP from skill-craft actions?** Most skills
   give skill_xp, not char_xp. But some content (e.g. higher-tier
   monsters dropping rare items) might be locked behind crafting
   prereqs. The path projection has to allow detours into skill grinds
   *when* the resulting unlock yields net positive char_xp/cycle.

5. **What is L_max actually?** Tentatively 55 (highest observed monster).
   Should verify via API or treat as soft (re-detect if higher monsters
   appear in game data).

6. **Backwards compat with existing strategic goals.** `LevelSkillGoal`,
   `GrindCharacterXPGoal`, `LowYieldCancelGoal` were designed before the
   root objective. Their semantics still hold — they just become
   subordinate. No deletion needed; the meta-policy just biases the
   goal-selection loop.

## Phasing

Same pattern as Phase G: small sub-phases, each independently shippable.

- **G-G — Max-level discovery & projection (~1 day):**
  `GameData.max_character_level`. `cheapest_path_to_level` projection
  with synthetic-test coverage. Doesn't change goal selection yet.

- **G-H — Char-XP-rate scoring of existing goals (~1 day):** Update
  `LowYieldCancelGoal.priority()` to use char_xp/cycle directly when
  contemplating cancel. Similar for `GrindCharacterXPGoal`. Behavioral
  test: gudgeon task gets canceled within 3 cycles instead of 30+.

- **G-I — Path-aware meta-policy in `_build_goals` (~1 day):**
  Post-process the goal list: bump priorities of goals whose
  `relevant_actions` overlap the projected cheapest path's next action.
  Trace records `path_aligned: bool` per goal.

- **G-J — Time-windowed XP projection (~1 day, optional):** Fix the
  staleness problem from Open Q #2. Weight recent samples more heavily.

Each sub-phase is its own plan doc and PR. Land G-G first because G-H
and G-I both depend on the projection.

## Success criteria

After G-G–G-I ship:

- Trace cycle records:
  `remaining_levels`, `projected_cycles_to_max`,
  `path_next_action`, plus per-goal `path_aligned` flag.
- Gudgeon-task scenario: cancel within 3 cycles of observed
  zero-char-XP samples (vs. ~30 with current strategic layer).
- Real-play: Robby at level 2 starts grinding monsters that yield
  positive char_xp, ignores low-yield tasks unless they're on the
  optimal path.
- CLI: `artifactsmmo learn show-path` prints the current projected
  cheapest path with per-step cycle estimates.
- No regressions: every existing test passes; new tests cover the
  projection edge cases (no beatable monsters, all monsters yield 0,
  registry empty, target_level already reached).

## Risks

1. **Over-optimization on a noisy signal.** A few unlucky fights drop
   observed XP/cycle; the bot could thrash between target monsters
   chasing the locally-highest observed rate. Mitigate with the same
   `WARMUP_MIN_SAMPLES` / confidence pattern used in Phase G.

2. **Path projection diverges from reality.** Real combat has variance
   (drops, deaths, cooldowns). The projection is a point estimate —
   actual experience may show paths the projection ranked low actually
   converge faster. Re-evaluate periodically (every N cycles); don't
   over-commit to a single path.

3. **Lump-sum rewards (task complete, achievement) skew the curve.**
   A long task might project as zero-XP/cycle for 99 cycles and then
   a huge spike. Amortization helps but isn't perfect. Accept this as
   a known limitation; the bot's decisions in the middle of the task
   will be "wrong" in the local sense but the LowYieldCancel will
   eventually triage based on actual amortized rate.

4. **Multi-step prereq chains explode planner state.** If unlock paths
   branch (e.g. ranged class vs melee class via different equipment),
   the DAG search could be expensive. Cap depth; cache; fall back to
   "current best grind" beyond the horizon.

5. **Bot becomes single-minded and ignores survival.** RestoreHP and
   UnlockBank already sit above the strategic ladder. As long as
   MAX_LEVEL_ROOT_BOOST < HP_CRITICAL, the bot still heals first.
   Priority math must respect existing floor.
