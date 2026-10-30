"""Whether a character can EVER come to hold an item (`is_suppliable`).

Its own module, outside the `ai.tiers` package, because the gear objective
(`gear_objective`) asks it and `ai.tiers`' package import runs the strategy
engine, whose root walk reads the task horizon, which reads the gear objective
(`gear_objective_for`, plan C Task 2): imported from `tiers.objective`, that
was an import cycle.
"""

from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState


def is_suppliable(code: str, state: WorldState, game_data: GameData) -> bool:
    """Can this character EVER come to hold `code`? Two kinds of item, and the
    difference between them is the whole point.

    PRODUCIBLE — something in the catalogue MINTS the item: a recipe, a resource
    that drops it, a monster that drops it, a vendor that sells it, or the task
    board that pays it. Supply is unbounded, so the answer is yes, and it stays
    yes while every one of those routes is closed today. Whether a route is open
    RIGHT NOW is `is_attainable_now`'s separate question, and a target that
    answers no there and yes here is exactly the skill-gated / gear-gated /
    unaffordable root the walk exists to grind toward. Those must keep being
    pursued, so this predicate must never be used as a substitute for that one.

    FIXED SUPPLY — nothing mints it. Every copy that will ever exist already
    exists, so supply is not a route but a COUNT: the copies free for this
    character to take. A copy in its own inventory is free; a copy in the
    account-wide bank is free (any sibling may withdraw it). A copy a sibling is
    WEARING is not free — and needs no special case to exclude, because a worn
    copy appears in no inventory this character reads and not in the bank, so it
    can never be counted here. When the count is zero this character goes
    without, permanently, and a target it can never hold is not a target.

    Live case: `novice_guide`, a level-10 artifact (hp +25, wisdom +25,
    prospecting +25) whose only supplier is the one-time `novice` achievement,
    completed 2026-07-03. `craft: null`, `tradeable: false`, and absent from
    every monster, resource, NPC, task and event table. ONE copy exists on the
    account and Robby is wearing it. It outranks every artifact the others can
    reach, so `gear_targets_with_blockers` handed it to every one of the three
    whose walk reached a gear root at all — C3P0, Lor and R2D2 — for an empty
    artifact slot, `classify_target` fell to its
    LAST arm (no recipe and not attainable, therefore its own blocker), and
    `IsThisTargetBlocked` returned `ObtainItem(novice_guide)` as the chosen
    root. The step graph then had nothing to plan and the cycle fell through to
    whatever goal ranked next: `plan C3P0` showed `chosen_root` and
    `chosen_step` both `ObtainItem(novice_guide)` under `selected_goal:
    CraftPotionsGoal`. Those three characters ran 6,115 cycles in 24 hours that
    way, and across 3 days not one cycle carried `novice_guide` in
    `selected_goal` or `action_repr`.

    The first arm is `ObtainModel.mints`, the capability question ("does any
    route that makes new copies exist, readiness ignored?"). NOT `ready` or
    `feasible`: those are state-aware, and an item whose only dropper is
    unwinnable today is still producible — grinding gear until the dropper falls
    is precisely the pursuit this must preserve. The task board is a mint too
    (`SourceKind.TASK_REWARD`): without it `tasks_coin` — the ONLY task-earnable
    item among the ten the live bundle reports routeless — would read as fixed
    supply and its funding loop would be declared dead. (This arm asked the
    state-free `RequirementGraph` plus `is_task_earnable` until step 4 of
    docs/PLAN_decision_architecture_redesign.md.)"""
    # A store-less feasibility walk: every drop at its API prior, passed
    # explicitly (ruling T16b).
    model = ObtainModel(state, game_data,
                       replace(NO_PROFILE_CONTEXT, learned_drops=LearnedDrops.empty()),
                       datetime.now(UTC))
    if model.mints(code):
        return True
    bank = state.bank_items or {}
    return state.inventory.get(code, 0) > 0 or bank.get(code, 0) > 0
