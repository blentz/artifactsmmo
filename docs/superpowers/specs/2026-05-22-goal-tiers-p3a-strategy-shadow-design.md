# Goal Tiers — P3a: Tier-3 Strategy Engine (Shadow Mode)

Date: 2026-05-22
Status: Approved (design)

Part of the multi-phase goal-architecture redesign:
- P1 (done) — Tier-1 objective + gap + personality seam.
- P2 (done) — Tier-2 meta-goal prerequisite graph (search substrate).
- **P3a (this spec)** — Tier-3 frontier-search strategy engine, run in **shadow
  mode**: it computes a chosen subgoal each cycle and emits it to the tracer,
  but does **not** drive the bot. No behavior change.
- P3b — cut the strategy over to drive progression (planner handoff via a
  MetaGoalAdapter; HP interrupt enacted).
- P3c — economy prerequisite-clearers + tasks-as-means; retire `priorities.py`.

## Goal

Build the Tier-3 decision engine and validate it before it controls the bot.
Each cycle the engine ranks the Tier-1 roots by personality-weighted gap
contribution ÷ a structural cost proxy, descends the highest-ranked reachable
root to the nearest actionable subgoal (a "singular loop" step whose direct
prerequisites are all satisfied), and produces a `StrategyDecision`. In P3a the
decision is **traced only** (a new `strategy` field in `traces.jsonl`) so we can
confirm it picks sane targets against real runs before P3b obeys it.

## Current state

P1+P2 shipped `ai/tiers/`: `CharacterObjective`/`ObjectiveGap`,
`Personality`/`BalancedPersonality`/`weighted_remaining`, meta-goal nodes
(`ReachCharLevel`, `ReachSkillLevel`, `ObtainItem`) and the pure
`prerequisites(node, state, game_data)` / `objective_roots(objective)` graph.
Nothing consumes them yet. The player still decides via the flat `priorities.py`
goal list; `GamePlayer._emit_trace` (player.py) writes a per-cycle JSON record
(state, planner stats, selected_goal, action, outcome) to the `Tracer`.
`RestoreHPGoal.CRITICAL_HP_FRACTION = 0.25`; `WorldState.hp_percent` exists.

## Design

### `src/artifactsmmo_cli/ai/tiers/strategy.py`

**`StrategyDecision`** (frozen): `interrupt: str | None`, `chosen_root: MetaGoal
| None`, `chosen_step: MetaGoal | None`, `desired_state: dict[str, object]`,
`ranking: list[RootScore]`. Method `to_trace() -> dict` returns a JSON-friendly
dict (node `repr`s + scores) for the trace.

**`RootScore`** (frozen): `root_repr: str`, `category: str`, `contribution: float`,
`cost: int`, `score: float`, `step_repr: str` — one per reachable root, for trace
debugging.

**`StrategyEngine`** (frozen dataclass holding `objective: CharacterObjective`,
`personality: Personality`):

`decide(state, game_data) -> StrategyDecision`:
1. **Interrupt:** `interrupt = "restore_hp" if state.hp_percent <
   RestoreHPGoal.CRITICAL_HP_FRACTION else None`. (Recorded; not enacted in P3a.)
2. `gap = objective.gap(state)`.
3. For each `root in objective_roots(objective)` with
   `not root.is_satisfied(state, game_data)`:
   - `step = actionable_step(root, state, game_data)`; skip the root if `None`
     (blocked — no reachable actionable node).
   - `contribution = root_contribution(root, gap, personality, objective)`.
   - `cost = root_cost(root, state, game_data)`.
   - `score = contribution / max(cost, 1)`.
4. Rank by `(score desc, root_repr asc)` (deterministic). `chosen_root`/
   `chosen_step` = top entry's root/step (or `None` when no reachable root).
5. `desired_state = desired_state_of(chosen_step)`.

### Helpers (module-level, pure)

**`actionable_step(root, state, game_data) -> MetaGoal | None`** — cycle-safe DFS:
```
_step(node, visited):
    if node in visited: return None
    visited.add(node)
    unmet = [p for p in prerequisites(node, state, game_data)
             if not p.is_satisfied(state, game_data)]
    if not unmet: return node            # all direct prereqs satisfied → actionable
    for p in sorted(unmet, key=repr):
        step = _step(p, visited)
        if step is not None: return step
    return None                          # cyclically blocked, no actionable leaf
```
Returns the deepest unmet node whose direct prerequisites are all satisfied.

**`root_category(root) -> str`**: `ReachCharLevel→"char_level"`,
`ReachSkillLevel→"skills"`, `ObtainItem→"gear"`.

**`root_contribution(root, gap, personality, objective) -> float`** =
`personality.category_weight(category) × share`, where `share` is the root's own
normalized gap:
- char_level: `gap.char_level_fraction`.
- skills: `gap.skill_gaps.get(skill, 0) / objective._game_data.max_skill_level`.
- gear: slot = the slot whose `objective.target_gear[slot] == code`;
  `gap.gear_gaps.get(slot, 0.0) / gear_target_total`, where `gear_target_total =
  sum(equip_value(item_stats(c)) for c in objective.target_gear.values())`
  (0.0 when total is 0).

**`root_cost(root, state, game_data) -> int`** = number of **unmet** nodes in the
root's prerequisite closure (cycle-safe BFS/DFS with a visited-set), min 1. A
structural proxy for remaining work; no learning dependency.

**`desired_state_of(node) -> dict`**: `ObtainItem(code,qty)→{"have": {code: qty}}`;
`ReachSkillLevel(s,L)→{"skill": {s: L}}`; `ReachCharLevel(N)→{"level": N}`;
`None→{}`. The descriptor P3b will translate into a planner goal.

### Player shadow wiring (player.py)
- After `self.game_data = GameData.load(client)`: build once
  `self._objective = CharacterObjective.from_game_data(self.game_data)` and
  `self._strategy = StrategyEngine(self._objective, BalancedPersonality())`.
- In `_emit_trace`, when `self._strategy` and `self.state` are set, add
  `record["strategy"] = self._strategy.decide(self.state, self.game_data).to_trace()`.
- **Nothing else changes** — `selected_goal`, action selection, and the planner
  are untouched. The shadow decision only appears in the trace.

### Data flow (P3a)
`GameData → CharacterObjective (once) → StrategyEngine`. Per cycle (inside
`_emit_trace`): `decide(state, game_data) → StrategyDecision → to_trace() →
record["strategy"]`. Validation is by reading `traces.jsonl`.

## Error handling
- `decide` is pure, no API. No reachable root → `chosen_root/step = None`,
  `desired_state = {}` (valid empty decision).
- `actionable_step` always terminates (visited-set); blocked roots are excluded.
- Gear with `gear_target_total == 0` → contribution 0 (no div-by-zero).
- `_emit_trace` only adds the field when `self._strategy` exists (e.g. before
  game-data load it's absent), so tracing never raises.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on new code.

- **`actionable_step`:** returns the deepest all-prereqs-satisfied node (e.g.
  craftable whose materials are gatherable-now → the material node); `None` for a
  self-referential/cyclic recipe with no actionable leaf.
- **`root_cost`:** counts unmet closure nodes; min 1; cycle-safe.
- **`root_contribution`:** char/skill/gear shares computed correctly; scales with
  `personality.category_weight`.
- **`decide` ranking:** higher contribution and/or lower cost wins; deterministic
  tiebreak; blocked roots excluded; satisfied roots skipped; empty decision when
  nothing reachable.
- **Personality swap:** a stub personality weighting "skills" heavily flips the
  choice from a gear/level root to a skill root on the same state.
- **HP interrupt flag:** set when `hp_percent < 0.25`, else `None`; never alters
  `chosen_root`.
- **`desired_state_of`:** correct descriptor per node type.
- **Shadow wiring:** with a stubbed tracer, `_emit_trace` includes a `strategy`
  key and `selected_goal`/action are unchanged (a player-level test asserts the
  field appears and the decision is not consumed elsewhere).

## Files
- Create `src/artifactsmmo_cli/ai/tiers/strategy.py` (+ export in `tiers/__init__.py`).
- Modify `src/artifactsmmo_cli/ai/player.py` — build objective+strategy once;
  emit `strategy` in `_emit_trace`.
- Tests: `tests/test_ai/test_tiers_strategy.py`, and a shadow-emit test
  (extend the player/trace tests).

## Out of scope (later phases)
- Driving the planner / changing decisions (P3b: MetaGoalAdapter, HP interrupt enacted).
- Retiring `priorities.py` / the flat goal list (P3c).
- Economy prerequisite-clearers and tasks-as-means (P3b/P3c).
- Learned-projection cost model (replaces the structural proxy in a later phase).
- Battle-prep consumables, tactical policies (P4).
