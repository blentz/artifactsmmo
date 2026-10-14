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

The items-task stand-down is PRICED (spec 2026-10-14 items-task-pays): the step
defers only while an items task is in progress AND it pays (`held_task_pays`,
read by the shell). The level gap plays no part.
"""


def items_task_active(task_type: str | None, task_code: str | None,
                      task_total: int, task_progress: int) -> bool:
    """An items task is held and not yet complete."""
    return (task_type == "items"
            and bool(task_code)
            and task_total > 0
            and task_progress < task_total)


def objective_step_is_fight_pure(
    is_reach_char_level: bool,
    has_combat_monster: bool,
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    task_pays: bool,
) -> bool:
    """Pure `objectiveStepIsFight` decision.

    Mirrors the `ReachCharLevel` branch of `objective_step_goal`:
      1. The committed objective step must be a `ReachCharLevel` goal.
      2. A combat monster must be available (`ctx.combat_monster is not None`).
      3. The step defers (no objective step -> not Fight-led) only while an
         items task is in progress AND it pays (`task_pays`, from
         `held_task_pays`: a gold/drop verdict, or demanded skill XP faster
         than the grind's character XP). Spec 2026-10-14 items-task-pays.
    """
    if not is_reach_char_level:
        return False
    if not has_combat_monster:
        return False
    return not (items_task_active(task_type, task_code, task_total, task_progress)
                and task_pays)
