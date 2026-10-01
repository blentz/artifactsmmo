"""The rung one grind cycle makes (Phase 2d of
docs/PLAN_decision_architecture_redesign.md): ANOTHER copy of the in-skill
rung, so the cycle's committed plan ends in the leg that earns the skill's XP
(`Formal.Liveness.GrindCycles`). The one walk plans the whole chain to it
(`craft_plan_gen._decompose_grind`).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def craft_rung(skill: str, state: WorldState, game_data: GameData,
               ctx: SelectionContext = NO_PROFILE_CONTEXT) -> str | None:
    """The craftable in-skill rung a grind of `skill` makes: one that leaves
    the committed step's materials alone when there is one
    (`ctx.step_profile`: live Robby 2026-08-05, a grind that ate the very
    hardwood the committed step had gathered), else any."""
    return (skill_grind_target(skill, state, game_data, frozenset(ctx.step_profile), ctx)
            or skill_grind_target(skill, state, game_data, ctx=ctx))


def grind_rung_goal(skill: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext = NO_PROFILE_CONTEXT) -> GatherMaterialsGoal | None:
    """One grind cycle of `skill` as the one walk serves it (Phase 2d-L3): make
    ANOTHER rung — the craftable in-skill rung, else the gatherable in-skill
    resource — so the cycle's committed plan ends in the leg that earns the
    skill's XP (`Formal.Liveness.GrindCycles`: a cycle is preparatory legs,
    then the earning leg). None when the skill has no rung from here.

    No descent: the retired `next_grind_goal` aimed at the deepest actionable
    material so the A* search stayed small, and a cycle then earned nothing in
    the skill (live C3P0 2026-09-30: a weaponcrafting cycle was
    `Gather(iron_rocks×47) → Craft(iron_bar×6)`, mining XP only). The walk plans the whole chain, and
    `produce={rung}` keeps the rung to the routes that earn."""
    rung = craft_rung(skill, state, game_data, ctx)
    if rung is None:
        rung = best_gather_resource_drop(skill, state.skills.get(skill, 1), game_data)
    if rung is None:
        return None
    bank = state.bank_items or {}
    held = state.inventory.get(rung, 0) + bank.get(rung, 0)
    return GatherMaterialsGoal(target_item=rung, needed={rung: held + 1},
                               skill_grind=True, exclude_recycle=frozenset({rung}))
