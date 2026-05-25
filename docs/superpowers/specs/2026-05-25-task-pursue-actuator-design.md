# Task PURSUE Actuator

Date: 2026-05-25
Status: Draft (for review)

Give the strategy a way to actually *work* an accepted task. Today `task_decision`
returns `PURSUE` or `PIVOT`, but only `PIVOT` is wired (→ `TaskCancel`). `PURSUE`
has no actuator, so an accepted task that should be pursued just stalls while the
bot grinds discretionary combat XP, never progressing the task to turn-in.

## Problem

The arbiter selects the **first plannable** candidate in band order:
`guards → collect-reward → objective-step → discretionary`.

After `AcceptTask` fires (observed: items task `copper_bar 0/20`), every
task-related means stays quiet — `COMPLETE_TASK` only fires at
`progress >= total`, `TASK_CANCEL` only on `PIVOT`, `ACCEPT_TASK` only with no
task. Nothing produces the task items. The objective step
(`ReachCharLevel → GrindCharacterXP(chicken)`) plans first and wins every cycle,
so the task freezes at `0/20` forever.

The goal that used to do this work — `FarmItems` (value ~35, drove
gather/craft → `TaskTrade` → turn-in) — was retired in P3c and never replaced.
Its actions still exist (`TaskTradeAction` is in the action list,
`TaskTradeAction.apply` increments `task_progress`), but no goal's
`desired_state` asks for them. This spec restores that behavior as the missing
`PURSUE` actuator, split by task type, and lifts the `current+1` planning bound
to `current+3` now that the planner (90s budget, per-search SQLite cache) can
afford deeper lookahead.

## Design

Five parts. The actuator lives in the **discretionary** band; the objective-step
grind stands down only when it cannot advance the task, so the discretionary
`PURSUE_TASK` becomes the first plannable candidate.

### 1. `LEVEL_LOOKAHEAD` — lift the `current+1` bound to `current+3`

The `current+1` rule was a planning-cost shortcut ("we always re-plan after a
level-up"), never a correctness requirement. Replace the hard-coded `current + 1`
in `objective_step_goal` (`strategy_driver.py:101`) with a module constant:

```python
LEVEL_LOOKAHEAD = 3
"""How many levels ahead the objective step / task skill-gate targets. The
planner re-plans every cycle and executes only plan[0], so this only steers
search direction and reachability, not commitment. Tunable: raise toward 5 if
traces show budget headroom; a deep recipe chain at a larger value risks a 90s
timeout -> no_plan."""
```

- `objective_step_goal` for `ReachSkillLevel`:
  `target = min(step.level, current + LEVEL_LOOKAHEAD)` (was `current + 1`).
- `LevelSkillGoal.is_satisfied` is unchanged: it already trips on the first
  `skill_xp` gain beyond `initial_skill_xp` (per-cycle P4 behavior), so a higher
  `target_level` only widens the planner's search target, not the per-cycle
  commitment.
- `MAX_SKILL_GAP = 5` (`level_skill.py:17`) stays — with `LEVEL_LOOKAHEAD = 3`
  the objective-path gap is ≤ 3, so the guard remains inert for that path.
  Update the now-stale `current+1` comment at `level_skill.py:44-47` to
  `current+LEVEL_LOOKAHEAD`.

This makes Part 4 (skill-gated tasks) more coherent: one `LevelSkillGoal` can
target a gate up to 3 levels away directly, instead of the arbiter re-committing
the target level cycle-by-cycle.

### 2. Monster tasks — retarget the grind (no new goal)

A `PURSUE` monster-task is winnable by definition: `task_decision` returns
`PIVOT` when the monster is combat-gated (`task_requirement` →
`SkillRequirement("combat", ...)`). So the existing objective-step grind already
advances a monster-task — it just needs to point at the *task* monster, not the
generic winnable target.

In `player.py` (which holds `self.game_data` and `self.history`), add a
task-aligned override consulted before the generic winnable pick:

```python
def _task_aligned_monster(self) -> str | None:
    """The active task's monster when it's a PURSUE monster-task; else None."""
    s = self.state
    if s is None or s.task_type != "monsters" or not s.task_code:
        return None
    if s.task_total == 0 or s.task_progress >= s.task_total:
        return None
    if task_decision(s, self.game_data, self.history) != PURSUE:
        return None
    return s.task_code
```

`_winnable_farm_target` prefers it when present:

```python
def _winnable_farm_target(self) -> str | None:
    task_monster = self._task_aligned_monster()
    if task_monster is not None:
        return task_monster
    target = self._path_aligned_monster()
    if target is None or not self._is_winnable(target):
        target = self._pick_winnable_monster()
    return target
```

The objective-step `GrindCharacterXP` then farms the task monster; each kill
advances the task; `COMPLETE_TASK` (collect-reward) turns it in at full. No new
goal, no new means for monster tasks.

### 3. `PursueTaskGoal` — items-task actuator (new goal)

New file `src/artifactsmmo_cli/ai/goals/pursue_task.py`, one class:

```python
class PursueTaskGoal(Goal):
    """Drive gather/craft -> TaskTrade to advance an items-type task by one
    unit. Re-plans each cycle (executes plan[0]); satisfied when the task is
    full, after which CompleteTask turns it in."""

    def __init__(self, task_code: str, initial_progress: int) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress

    def value(self, state, game_data, history=None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_FIRING        # see ordering note below

    def is_satisfied(self, state) -> bool:
        # Stop the moment progress advances (per-cycle) OR the task is full /
        # gone, so the arbiter re-decides with fresh state each cycle.
        if not state.task_code or state.task_total == 0:
            return True
        if state.task_progress >= state.task_total:
            return True
        return state.task_progress > self._initial_progress

    def desired_state(self, state, game_data) -> dict[str, object]:
        # One more unit traded. The planner chains Gather/Craft -> TaskTrade;
        # TaskTradeAction.apply increments task_progress, so this is reachable
        # with a shallow search. Looking further ahead than +1 adds search cost
        # with no execution benefit (only plan[0] runs).
        return {"task_progress": self._initial_progress + 1}

    def relevant_actions(self, actions, state, game_data) -> list[Action]:
        # Gather (replenish materials), Craft (produce the item or sub-recipes),
        # TaskTrade (submit), plus recovery/deposit. Excludes combat/equip noise.
        ...

    @property
    def max_depth(self) -> int:
        return 100        # deep recipe chains, matches LevelSkillGoal/GatherMaterials

    def __repr__(self) -> str:
        return f"PursueTask({self._task_code})"
```

`is_satisfied` uses the same per-cycle "advanced by one" trip as `LevelSkillGoal`
so a committed `PursueTask` is re-evaluated against fresh state every cycle
(progress observed from the API after the real `TaskTrade`), not held across a
stale simulation.

### 4. `MeansKind.PURSUE_TASK` — wiring + skill-gate split

Add to `means.py`:

```python
class MeansKind(Enum):
    ...
    PURSUE_TASK = "pursue_task"

DISCRETIONARY_ORDER = (
    MeansKind.PURSUE_TASK,     # work an accepted PURSUE task before idle options
    MeansKind.ACCEPT_TASK,
    MeansKind.TASK_EXCHANGE,
    MeansKind.SELL_IDLE,
    MeansKind.BANK_EXPAND,
)
```

`_fires` for `PURSUE_TASK` (items only — monster tasks are handled by Part 2's
grind retarget, so they must NOT also fire a means):

```python
if kind is MeansKind.PURSUE_TASK:
    return (state.task_type == "items"
            and bool(state.task_code) and state.task_total > 0
            and state.task_progress < state.task_total
            and history is not None
            and task_decision(state, game_data, history) == PURSUE)
```

`PURSUE_TASK` and `ACCEPT_TASK` are mutually exclusive (task held vs. no task),
so their relative order is immaterial; `PURSUE_TASK` leads the band for clarity.

The `map_means` mapping in `strategy_driver.py` splits on `task_requirement`,
mirroring the §3 gear-gated-skill inheritance:

```python
if kind is MeansKind.PURSUE_TASK:
    req = task_requirement(state, game_data)
    if req is not None and req.skill != "combat":
        target = min(req.required_level, state.skills.get(req.skill, 0) + LEVEL_LOOKAHEAD)
        return LevelSkillGoal(skill_name=req.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(req.skill, 0))
    return PursueTaskGoal(task_code=state.task_code, initial_progress=state.task_progress)
```

`req.skill == "combat"` cannot occur here (that path yields `PIVOT`, so
`PURSUE_TASK` never fires), but the guard documents the invariant and is the
safe branch. When the skill reaches the gate, `task_requirement` returns `None`
and the mapping flips to `PursueTaskGoal`.

### 5. Items stand-down at the single construction point; drop the stale self-suppression

`grind_character_xp.py:52-55` currently returns `0.0` under *any* task with the
stale comment "FarmItems/CompleteTask own the cycle." That blanket suppression is
both wrong and a second layer of control:

- **Monster PURSUE task:** the grind IS the actuator (Part 2) — it must NOT
  suppress. With the retarget, `combat_monster` is the task monster, so grinding
  it is task progress.
- **Items PURSUE task:** the grind cannot advance the task; it must stand down so
  discretionary `PURSUE_TASK` runs.

`objective_step_goal` is the **only** constructor of `GrindCharacterXPGoal`
(verified: it is imported and instantiated nowhere else). So the stand-down
belongs there and *only* there — a single decision point, no defense-in-depth.
`objective_step_goal` returns `None` for the `ReachCharLevel` step when an items
PURSUE task is active:

```python
if isinstance(step, ReachCharLevel):
    if ctx.combat_monster is None:
        return None
    if state.task_type == "items" and state.task_code and state.task_total > 0 \
            and state.task_progress < state.task_total:
        return None        # grind can't advance an items task; let PURSUE_TASK run
    return GrindCharacterXPGoal(...)
```

With the objective step removed for items tasks, the arbiter falls through to the
discretionary `PURSUE_TASK`. **Remove** `grind_character_xp.py`'s blanket
`if state.task_code: return 0.0` entirely (and its stale comment): the goal is
never constructed under an items task, and under a monster task it SHOULD value
normally (it is grinding the retargeted task monster). The goal's value logic
becomes task-agnostic — the task-vs-grind decision lives wholly in
`objective_step_goal` and the band ordering.

## Error handling

- **Unproducible item / no plan:** `PursueTaskGoal` yields no plan; the arbiter
  falls through. The existing `LowYieldCancel` / `TaskCancel` escape hatches drop
  a genuinely stuck task. No second cancel path is added.
- **`history is None`:** `PURSUE_TASK._fires` requires history (it calls
  `task_decision`); with no history it does not fire, and the bot accepts/keeps
  the task without the pursue boost (cold-start safe — `task_decision` itself
  treats `history is None` as `PIVOT` for combat tasks).
- **Empty/zero task fields:** every predicate guards `task_total > 0` and
  `task_progress < task_total`.
- Pure logic; no API in the decision path; no `except Exception`.

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`LEVEL_LOOKAHEAD`:** `objective_step_goal` for a `ReachSkillLevel(skill, 50)`
  step at skill level `L` returns `LevelSkillGoal` targeting `min(50, L+3)`; at
  `L=48` it caps at `50`.
- **Monster retarget:** with a PURSUE monster-task `chicken`-winnable but task is
  `yellow_slime`, `_winnable_farm_target` returns `yellow_slime`; with no task it
  returns the generic winnable; with a PIVOT monster-task it does NOT retarget.
- **`PURSUE_TASK._fires`:** fires for an items task, `progress < total`,
  `task_decision == PURSUE`; does not fire for a monster task, a full task, a
  `PIVOT` task, or `history is None`.
- **`map_means` split:** with an items task whose craft needs a skill above
  current → `LevelSkillGoal(skill, min(gate, current+3))`; with the skill at/above
  the gate → `PursueTaskGoal`.
- **`PursueTaskGoal`:** `is_satisfied` true when full / gone / progress advanced;
  `desired_state` is `progress+1`; `relevant_actions` includes Gather/Craft/
  TaskTrade/recovery/deposit and excludes combat/equip.
- **`objective_step_goal` items stand-down:** returns `None` for the
  `ReachCharLevel` step when an items PURSUE task is active; returns
  `GrindCharacterXPGoal` otherwise.
- **`GrindCharacterXPGoal`:** value is task-agnostic after the change — non-zero
  learned-rate value under a monster task and with no task (no longer reads
  `task_code`); the items stand-down is asserted via `objective_step_goal`
  returning `None`, not here.
- **End-to-end arbiter (the decisive test):** reconstruct the observed stall —
  items task `copper_bar 0/20`, materials reachable — and assert the selected
  goal is `PursueTask(copper_bar)` (or `LevelSkill(...)` when skill-gated), NOT
  `GrindCharacterXP(chicken)`.
- **Regression:** existing task/grind/arbiter tests updated for the new band
  member and the lifted bound; trace (`goals_tried` / `goal_rank`) still renders.

## Files

- Create `src/artifactsmmo_cli/ai/goals/pursue_task.py` — `PursueTaskGoal`.
- Modify `src/artifactsmmo_cli/ai/tiers/means.py` — `MeansKind.PURSUE_TASK`,
  `DISCRETIONARY_ORDER`, `_fires`.
- Modify `src/artifactsmmo_cli/ai/strategy_driver.py` — `LEVEL_LOOKAHEAD`
  constant; `objective_step_goal` lifted bound + items stand-down; `map_means`
  `PURSUE_TASK` split.
- Modify `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` — remove the
  blanket `if state.task_code: return 0.0` suppression and its stale comment
  (stand-down now lives solely in `objective_step_goal`).
- Modify `src/artifactsmmo_cli/ai/goals/level_skill.py` — refresh the stale
  `current+1` comment to `current+LEVEL_LOOKAHEAD`.
- Modify `src/artifactsmmo_cli/ai/player.py` — `_task_aligned_monster`,
  `_winnable_farm_target` preference.
- Tests: `tests/test_ai/` — new `PursueTaskGoal` tests, means/`_fires` tests,
  `map_means` split, retarget, stand-down, end-to-end arbiter, regression
  curation.

## Out of scope

- Monster-task pursuit via a dedicated goal (handled by grind retarget instead).
- Re-valuing tasks as StrategyEngine objective roots (deferred; the marginal-
  value model stays gear/char/skill).
- Tuning `task_decision` PURSUE/PIVOT thresholds.
- Raising `LEVEL_LOOKAHEAD` beyond 3 (one-line change later if traces justify).
