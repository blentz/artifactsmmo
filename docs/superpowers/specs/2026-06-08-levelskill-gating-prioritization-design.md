# LevelSkill gating prioritization

**Date:** 2026-06-08
**Status:** Design — approved for planning
**Area:** `src/artifactsmmo_cli/ai/` (strategy arbiter, objective/prereq tiers, goals)

## Problem

Trace analysis of `play-trace-Robby-20260608-*.jsonl` (167 cycles, 2 sessions) found
no correctness defects — every outcome `ok`, task progress advancing, no stuck
windows, no fight losses. It surfaced one efficiency defect:

**96% of GOAP planner compute is burned on `LevelSkill` goals that never produce a
plan.** In session `210337`, `goals_tried` searched 1.5M planner nodes total;
1.45M (96%) went to `LevelSkill` goals that returned `plan_len=0` on **0 of 24**
attempts, 14 of them hitting the budget ceiling. These probes cluster at task
boundaries (cycles 0, 50, 51), where each stalls the cycle 57–75s versus the ~31s
mid-task baseline.

### Root cause (mechanical)

`objective_roots` (`tiers/prerequisite_graph.py:145-146`) emits a standalone
`ReachSkillLevel(skill, 50)` root for **all 7 skills** every cycle — sourced from
`CharacterObjective.target_skill_levels = {every skill: max_skill_level}`
(`tiers/objective.py:73`) — plus a bootstrap `ReachSkillLevel(skill, 5)` for the
three crafting skills (`prerequisite_graph.py:142-144`). These become objective
**steps**, tried by the arbiter ahead of the discretionary `PURSUE_TASK` /
`ACCEPT_TASK` means. They are width-unfindable: "reach skill level N" requires the
planner to simulate crafting many items (accumulating `projected_skill_xp_delta`),
a deep/wide search that exhausts the budget. The arbiter correctly falls through to
`PursueTask`, but only after burning the budget probing the doomed steps.

`DoomedMemo` (`ai/doomed_memo.py`) is supposed to skip repeatedly-failing goals,
but it only marks on the **escalation** pass (`strategy_driver.py:639`); the
**cheap** pass (`try_plan_cheap`, line 629-632) never marks. At a task boundary the
committed `PursueTask` momentarily can't cheap-plan, so the cheap walk reaches the
LevelSkill steps, probes each at the 10s cheap budget, times out, and — because a
later candidate (`AcceptTask`/`PursueTask`) wins the cheap pass — escalation never
runs and the doomed probes are never memoized. Every boundary repeats them.

### Conceptual cause

Skill leveling is modeled as an always-on objective ("level every skill to 50").
But skill leveling has limited utility: it is only worth doing when a
**strategically interesting goal is blocked by an under-leveled skill**. The fix
keeps the objective roots but makes `LevelSkill` dormant unless it is the binding
gate on a concrete want.

## The game gate (data model)

The blocking relationship is already in game data:

- Every craftable item carries a `craft` block with `skill` (a `CraftSkill`:
  `weaponcrafting | gearcrafting | jewelrycrafting | cooking | woodcutting |
  mining | alchemy`) and `level` (the skill level required to craft it). Exposed as
  `ItemStats.crafting_skill` / `ItemStats.crafting_level`
  (`ai/game_data.py:29-30`).
- Every resource carries `skill` + `level` (the gather gate), exposed as
  `GameData.resource_skill_level(code)`.

`prerequisite_graph.prerequisites()` already derives the gate correctly:
wanting `ObtainItem(X)` whose recipe needs `craft.skill@craft.level` emits
`ReachSkillLevel(skill, level)` as a prerequisite — **only because X is wanted**
(`prerequisite_graph.py:64-65`). This design surfaces that same signal at the
arbiter's ordering layer.

## Decisions (locked)

1. **Keep the objective roots.** Do not remove the `ReachSkillLevel(skill, 50)` or
   bootstrap roots. Fix prioritization purely arbiter-side (ordering + a plannable
   target). The bootstrap-5 root is *subsumed* by the gating predicate.
2. **Demand set that elevates a skill** (the "strategically interesting goal
   blocked" set): equipment/tool upgrades (`target_gear` + `target_tools`), the
   active items-task's own item, and the best combat weapon for `ReachCharLevel`.
   **Raw gather gates are excluded** — a gathering skill elevates only when it is
   the `craft.skill` of a wanted gear/tool/task/combat item, never merely to access
   a raw material.
3. **Preemption:** a gating `LevelSkill` outranks the gear/tool chain it unlocks,
   but does **not** preempt an in-progress paying items-task — *except* when the
   gate is on the active task's own item (then it preempts the already-stalled
   `PursueTask`, since the task cannot progress without it).
4. **Plannability:** when elevated, target a single shallow craft, not
   `ReachSkillLevel(current+3)`. Craft one in-skill item per cycle; the per-cycle
   replan grinds the skill incrementally. Shallow plan = always plannable, no burn.

## Design (Approach A)

### Component 1 — gating predicate: `tiers/skill_gates.py` (new)

Pure function, no I/O:

```python
def gating_skills(
    state: WorldState,
    game_data: GameData,
    objective: CharacterObjective,
    ctx: SelectionContext,
) -> dict[str, SkillGate]:
    """Skills currently blocking a strategically interesting want.

    Maps skill_name -> SkillGate(required_level, source). A skill is gating iff
    it is the craft.skill of some WANTED, NOT-YET-OWNED item (or an item in that
    item's craftable recipe closure) at a craft.level above the character's
    current skill level. Gather/resource skill gates are excluded."""
```

`SkillGate` is a small frozen value object: `required_level: int`,
`source: GateSource` (an enum: `TASK_ITEM`, `GEAR`, `TOOL`, `COMBAT`). When more
than one want gates the same skill, keep the entry whose `required_level` is
highest and prefer `TASK_ITEM` as the source (it drives preemption).

Wanted-item set, each filtered to not-yet-owned via `owned_count_pure`
(`tiers/owned_count.py`):

- `objective.target_gear.values()` → `GEAR`
- `objective.target_tools.values()` → `TOOL`
- active items-task item: `state.task_code` when `state.task_type == "items"` →
  `TASK_ITEM` (walk its recipe closure too)
- `best_attainable_weapon(game_data)` when `not combat_capable(state, game_data)`
  → `COMBAT`

For each wanted item `W`: walk `W` plus its **craftable** recipe closure
(`recipe_closure`). For every node whose `item_stats(node).crafting_skill == S`
and `crafting_level > state.skills.get(S, 0)`, record `S -> SkillGate(level,
source)`. Closure nodes that are gather leaves (no recipe) contribute no gate
(gather gates excluded).

`SkillGate` + `GateSource` live in the same module as cohesive value/enum
declarations (permitted by the one-class-per-file exemption); `gating_skills` is
the single behavioral entry point.

### Component 2 — craft-one target selection: `tiers/skill_grind_target.py` (new)

Pure function:

```python
def skill_grind_target(
    skill: str, state: WorldState, game_data: GameData,
) -> str | None:
    """The in-skill item to craft NOW to gain XP toward the gate: highest-XP,
    craftable at the current skill level, shallowest material chain (prefer
    materials already in inventory/bank). None if nothing in-skill is craftable
    now."""
```

Selection: among items with `crafting_skill == skill` and
`crafting_level <= current`, score by (a) materials-in-hand depth (prefer the
shallowest reachable chain, mirroring `_materials_in_hand` in `strategy_driver`),
then (b) item level (higher tier = more XP). Tie-break by code for determinism.

### Component 3 — arbiter reordering (`strategy_driver.py`)

In `select` after `candidates` is assembled (around line 611) and before the cheap
pass, classify every `LevelSkillGoal` candidate by its skill `S` against
`gating_skills(...)` computed once per cycle:

| Case | Action |
|---|---|
| `S` gates the **active task item** (`source == TASK_ITEM`) | replace goal with the craft-one goal; position **before** the `PURSUE_TASK` candidate |
| `S` gates gear/tool/combat, **no paying task active** | replace with craft-one goal; position **after** `ACCEPT_TASK` but **before** the gear/tool `ObtainItem` steps it unlocks (accepting a task stays the cheap unblock; the grind does not starve task acceptance) |
| `S` gates gear/tool/combat, **paying task active** | replace with craft-one goal; position **after** the `PURSUE_TASK` candidate |
| `S` **not gating** | demote to the end, immediately before `WAIT` |

"Paying task active" = `state.task_type == "items"` and `state.task_code` and
`state.task_progress < state.task_total`.

The craft-one goal is `GatherMaterialsGoal(target_item=t, needed={t: 1})` where
`t = skill_grind_target(S, state, game_data)` (reuses the existing plannable
goal/action machinery). If `skill_grind_target` returns `None`, the LevelSkill
candidate is demoted to the end (no craftable progress exists — nothing to do).

Implementation note: prefer a small pure helper `reorder_skill_candidates(
candidates, gates, state, game_data) -> list[Candidate]` so the ordering policy is
unit-testable in isolation from the arbiter's planning loop.

### Data flow

```
CharacterObjective ─┐
WorldState ─────────┼─> gating_skills() ─> {skill: SkillGate}
GameData ───────────┤                          │
SelectionContext ───┘                          ▼
candidates (tier-assembled) ──> reorder_skill_candidates() ──> ordered candidates
                                       │  (gating LevelSkill -> GatherMaterials craft-one;
                                       │   non-gating -> end)
                                       ▼
                            select_pure cheap pass -> escalation -> Wait
```

### Why the burn disappears

- **Non-gating** LevelSkill: demoted past every cheap winner. The cheap pass selects
  `PursueTask`/`AcceptTask` first and never probes it. Zero wasted nodes.
- **Gating** LevelSkill: mapped to a shallow `GatherMaterials` craft-one goal —
  plannable in the cheap pass, no timeout, emits a real craft action.
- `DoomedMemo` becomes a backstop rather than the primary defense.

## Interactions / invariants preserved

- **Roots unchanged** (decision 1): `objective_roots` / `target_skill_levels` are
  untouched. Only candidate ordering and the per-cycle goal target change.
- **Bootstrap subsumed:** a crafting skill that gates real gear elevates via the
  predicate; one that gates nothing is dormant instead of burning budget. The
  chicken-and-egg the bootstrap-5 root solved (skill never grows because no goal
  forces a craft) is now solved by the craft-one target firing whenever gear is
  gated.
- **Items-task stand-down lessons** (`strategy_driver.py:356-384`): honored by
  decision 3 — gear-gating crafting skills never abandon a paying task.

## Known tradeoff (flagged for review)

Gear-gating crafting skills (`weaponcrafting` / `gearcrafting` / `jewelrycrafting`)
do not preempt a chained items-task **and** sit below `ACCEPT_TASK` when no task is
active, so under continuous tasking they grind only in the narrow windows where
neither a task nor a task-acceptance is available — potentially near-inert for those
three skills. This is the deliberate conservative reading of decision 3. The grind
still fires whenever the gate is on the active task's own item (`TASK_ITEM` source
preempts), and cooking/mining/woodcutting/etc. continue to level naturally from task
crafts and gathers. If gear progression proves too slow in live traces, the lever is
decision 3 — let a gating-gear `LevelSkill` rank above `ACCEPT_TASK` (and optionally
preempt a paying task for a bounded number of cycles). We start conservative and
tune from trace evidence.

## Testing

Per project rules: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests in
`tests/`, using the real suite and real fixtures (no simple/throwaway tests, no
mocking the unit under test).

- `gating_skills` unit tests over fixture recipes:
  - gear gated by `craft.level > current` → skill present with `GEAR` source.
  - closure-gated (intermediate craftable gated) → gating skill surfaced.
  - item already owned (inventory/bank/equipped) → not gating.
  - active items-task item gated → `TASK_ITEM` source.
  - combat weapon gated when `not combat_capable` → `COMBAT` source.
  - gather-only gate (resource skill) → absent (excluded).
  - same skill gated by two wants → highest `required_level`, `TASK_ITEM` source
    wins.
- `skill_grind_target` unit tests: picks shallowest-chain / highest-XP craftable;
  returns `None` when nothing in-skill is craftable at current level.
- `reorder_skill_candidates` unit tests: one per row of the ordering table, asserting
  the LevelSkill candidate's resulting position and that its goal became
  `GatherMaterials` (gating) or stayed demoted (non-gating).
- Plannability test: gated skill + shallow craftable → cheap-budget plan emitted,
  no timeout.
- Regression against captured traces: assert zero LevelSkill probes while a paying
  task is active, and a plannable craft-one when a gear gate exists with no task.

## Files

New:
- `src/artifactsmmo_cli/ai/tiers/skill_gates.py` — `gating_skills`, `SkillGate`,
  `GateSource`.
- `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py` — `skill_grind_target`.
- `src/artifactsmmo_cli/ai/strategy_reorder.py` — `reorder_skill_candidates`
  (pure ordering policy), if it does not fit cleanly inside `strategy_driver`.

Modified:
- `src/artifactsmmo_cli/ai/strategy_driver.py` — call `gating_skills` once per
  cycle; apply `reorder_skill_candidates` before the cheap pass; map gating
  LevelSkill candidates to the craft-one `GatherMaterialsGoal`.

Out of scope: removing objective roots, changing `DoomedMemo`, gather-gate
elevation, any change to `PursueTask`/guard ordering.
