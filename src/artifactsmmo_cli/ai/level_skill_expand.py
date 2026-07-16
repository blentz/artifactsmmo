"""Expand a LevelSkill plan step into one grind cycle's goal.

The LevelSkill action is a planner abstraction (its apply optimistically levels
the skill); at execution the player runs ONE cycle of the concrete grind — one
leg toward crafting an in-skill rung — and replans, exactly as the retired
tree-level skill-grind dispatch did. This picks the rung and builds the
skill_grind GatherMaterials goal; the caller plans it and executes its first leg.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState


def next_grind_goal(skill: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext = NO_PROFILE_CONTEXT) -> GatherMaterialsGoal | None:
    """The skill_grind GatherMaterials goal for one grind cycle of `skill`, or
    None when the skill cannot be ground from the current level.

    Prefers a craftable in-skill rung (`skill_grind_target`); falls back to a
    gatherable in-skill resource (`best_gather_resource_drop`) for a gather
    skill whose lowest craftable rung is out of reach (e.g. alchemy at level 1,
    ground by gathering sunflower).

    DESCENT (live Robby trace 2026-07-12): the goal targets the rung's
    `actionable_step` — the deepest unmet node whose direct prerequisites are
    satisfied — NOT the rung item itself. Targeting a rung with a DEEP recipe
    makes the GOAP search interleave dozens of gathers with crafts and deposits
    and EXPLODE: `GatherMaterials(fire_staff)` (fire_staff <- 5 ash_plank <- 50
    ash_wood) hit the 1M-node cap with no plan, so `_execute_level_skill` raised
    on the empty sub-plan every cycle and the bot LIVELOCKED on `error:other`
    with zero progress. The deepest step is a FLAT gather that plans in ~70
    nodes and makes real incremental progress — the same descent the gear path
    already performs (see `gather_step_target`'s docstring, which documents this
    exact explosion, and `tiers/strategy.actionable_step`).

    The descent costs nothing on a shallow rung: the player executes only leg 0
    of the plan, and the deepest step's first action IS the rung plan's first
    action. Once the rung's materials are all in hand its actionable_step is the
    rung itself, so the goal targets the rung and the plan is the craft that
    earns the skill XP (`held + 1` keeps that perpetual — craft ANOTHER).

    `ctx` (the player's per-cycle `SelectionContext`, wired in at the per-cycle
    seam) is forwarded to `actionable_step` so the descent stops at a material
    with any ready `ai/obtain_sources` route instead of falling into its
    recipe (live Robby 2026-07-13: weaponcrafting's fire_staff needs
    ash_plank, recyclable from the 7 held fishing_net, but without this the
    descent fell all the way to ash_wood — 50 gathers of WOODCUTTING xp per
    weaponcrafting grind cycle). Defaults to `NO_PROFILE_CONTEXT`, reproducing
    the pre-epic descent byte-for-byte for every caller that doesn't wire it
    in."""
    rung = skill_grind_target(skill, state, game_data)
    if rung is not None:
        bank = state.bank_items or {}
        held = state.inventory.get(rung, 0) + bank.get(rung, 0)
        # Descend on the grind quantity (held + 1), NOT the default 1: when the
        # character already HOLDS copies of the rung, ObtainItem(rung, 1) is
        # trivially satisfied by them, so actionable_step short-circuits at the
        # rung and the grind goal becomes GatherMaterials(rung, held+1) — "craft
        # ANOTHER rung" — whose recipe materials are NOT in hand, exploding the
        # sub-plan search to a timeout / empty plan and livelocking on
        # error:other (live Robby 2026-07-15: fire_staff x3 held, no ash_plank,
        # 38 cycles at ~10s CPU each). held + 1 makes the deficit unmet, so the
        # descent enters the recipe and stops at the deepest actionable material.
        step = actionable_step(ObtainItem(rung, quantity=held + 1),
                               state, game_data, ctx)
        if isinstance(step, ObtainItem) and step.code != rung:
            # exclude_recycle={rung}: never recycle the rung to source its own
            # crafting material — that is the null cycle (rung -> material ->
            # re-craft rung) that churned surplus fire_staff on live Robby.
            return GatherMaterialsGoal(target_item=step.code,
                                       needed={step.code: step.quantity},
                                       skill_grind=True,
                                       exclude_recycle=frozenset({rung}))
    else:
        rung = best_gather_resource_drop(
            skill, state.skills.get(skill, 1), game_data)
    if rung is None:
        return None
    bank = state.bank_items or {}
    held = state.inventory.get(rung, 0) + bank.get(rung, 0)
    return GatherMaterialsGoal(target_item=rung, needed={rung: held + 1},
                               skill_grind=True,
                               exclude_recycle=frozenset({rung}))
