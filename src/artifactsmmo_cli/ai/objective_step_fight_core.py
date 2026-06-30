"""Pure decision boundary for `objectiveStepIsFight`.

Isolates the ReachCharLevel -> GrindCharacterXPGoal routing slice of
`objective_step_goal` (strategy_driver.py:719-752) from its impure shell (Goal
construction, game_data, the GOAP planner). The shell fetches scalars from the
committed step / state / selection context, then calls
`objective_step_is_fight_pure` to decide whether the emitted objective step is a
combat/char-leveling goal whose plan leads with Fight.

This is exactly the production meaning of the Lean liveness Bool
`objectiveStepIsFight` (formal/Formal/Liveness/Measure.lean): the committed
objective is a `ReachCharLevel` goal that resolves to `GrindCharacterXPGoal`
(whose `relevant_actions` admit only Fight(target) + recovery + equip, so the
plan head is a Fight). The Lean model in `formal/Formal/ObjectiveStepFight.lean`
mirrors this predicate; the differential gate asserts the two agree over random
inputs.

Faithfulness note: the OTHER `objective_step_goal` branches (ObtainItem ->
gear/currency/gather, ReachSkillLevel -> skill grind) are by definition NOT
combat-led, so they yield `objectiveStepIsFight = False`. This module models only
the combat slice because that is the entire meaning of the Bool — it is the
relevant slice, not a surrogate for the whole routing function.
"""


def objective_step_is_fight_pure(
    is_reach_char_level: bool,
    target: int,
    level: int,
    has_combat_monster: bool,
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
) -> bool:
    """Pure `objectiveStepIsFight` decision.

    Mirrors the `ReachCharLevel` branch of `objective_step_goal`:
      1. The committed objective step must be a `ReachCharLevel` goal.
      2. A combat monster must be available (`ctx.combat_monster is not None`).
      3. The long-haul stand-down must NOT apply: when the level gap
         (`target - level`) exceeds 4 AND an items task is in progress, the grind
         defers to the items task (returns no objective step -> not Fight-led).

    Args:
      is_reach_char_level: committed step is `ReachCharLevel`.
      target:              `ReachCharLevel.level` (the target character level).
      level:               `state.level`.
      has_combat_monster:  `ctx.combat_monster is not None`.
      task_type:           `state.task_type` ("items" / "monsters" / ...).
      task_code:           `state.task_code` (truthy = a task is assigned).
      task_total:          `state.task_total`.
      task_progress:       `state.task_progress`.
    """
    if not is_reach_char_level:
        return False
    if not has_combat_monster:
        return False
    bootstrap_gap = target - level
    items_task_active = (
        task_type == "items"
        and bool(task_code)
        and task_total > 0
        and task_progress < task_total
    )
    # Long-haul stand-down: a > 4-level grind defers to an in-progress items task.
    return not (bootstrap_gap > 4 and items_task_active)
