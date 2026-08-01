"""Expand a LevelSkill plan step into one grind cycle's goal.

The LevelSkill action is a planner abstraction (its apply optimistically levels
the skill); at execution the player runs ONE cycle of the concrete grind — one
leg toward crafting an in-skill rung — and replans, exactly as the retired
tree-level skill-grind dispatch did. This picks the rung and builds the
skill_grind GatherMaterials goal; the caller plans it and executes its first leg.
"""

import dataclasses

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState


def _grind_probe_state(state: WorldState, rung: str) -> WorldState:
    """`state` with every carried, banked and WORN copy of `rung` removed.

    The descent state for a skill grind, NOT a state anything executes against.
    A grind earns its XP from the CRAFT, so copies the character already owns
    are not a way to serve it — but `prerequisites` leafs an item that is
    already owned, already worn, or has a ready withdraw source, and each of
    those stops the descent dead at the rung. Discounting the rung's own
    holdings is what keeps the deficit real and the descent inside the recipe
    (see `next_grind_goal`).

    The equipment slots matter as much as the bag: `ObtainItem.is_satisfied`
    reports an EQUIPPABLE satisfied whenever its code is worn, IGNORING
    quantity (`tiers/meta_goal.py` — "owning isn't the end-state, the objective
    is to WEAR them"). A gear grind wears what it makes, so the very first rung
    the character equips would otherwise leaf the rung on the `is_satisfied`
    arm and no quantity could ever defeat it.

    Only the rung's own entries are dropped; every other material and every
    other equipped item stays, so a material that IS legitimately in hand still
    leafs normally and the combat stats behind `_producible`'s winnability gate
    lose only the one item the grind is about to make another of.
    """
    inventory = {code: qty for code, qty in state.inventory.items()
                 if code != rung}
    bank_items = (None if state.bank_items is None
                  else {code: qty for code, qty in state.bank_items.items()
                        if code != rung})
    equipment = {slot: (None if code == rung else code)
                 for slot, code in state.equipment.items()}
    return dataclasses.replace(state, inventory=inventory,
                               bank_items=bank_items, equipment=equipment)


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
        # Descend for ONE rung against a state with the rung's own copies
        # removed (`_grind_probe_state`). A grind must CRAFT a new rung —
        # withdrawing, re-wearing or otherwise reusing a copy it already owns
        # earns zero skill XP — so the copies it has already made are
        # irrelevant to what it should do next, and letting them influence the
        # descent is what broke it three ways. `prerequisites` leafs the rung
        # (ending the descent AT it) on any of:
        #
        #   * `owned_count_pure(...) >= node.quantity`. The old
        #     `quantity = held + 1` device defeated exactly this arm (live
        #     Robby 2026-07-15: fire_staff x3 in the BAG, no ash_plank, 38
        #     cycles at ~10s CPU each) and nothing else.
        #   * a ready non-craft SOURCE. A copy in the BANK is a ready WITHDRAW
        #     source, and `held + 1` does nothing about that arm, so
        #     `actionable_step` still stopped at the rung and the fallthrough
        #     below emitted GatherMaterials(rung, held+1) — a full from-scratch
        #     craft chain whose node count GROWS with the banked count, because
        #     every banked copy adds another applicable Withdraw. Live C3P0
        #     2026-08-01 on the real catalog: held=1 => 24k nodes, held=3 =>
        #     47k, held>=5 => the 10s CHEAP_BUDGET_SECONDS is exhausted and the
        #     sub-plan comes back EMPTY, so `_execute_level_skill` raised
        #     "grind produced no leg" every cycle for 9.5h with ZERO character
        #     progress until the run StuckExit-ed. The grind's own success is
        #     what broke it.
        #   * `is_satisfied`, which reports an EQUIPPABLE satisfied whenever its
        #     code is WORN, ignoring quantity. A gear grind wears what it makes,
        #     so no quantity can defeat this arm at all.
        #
        # Removing the holdings makes the deficit unconditionally real, so the
        # descent enters the recipe and stops at the deepest actionable
        # material — a flat, cheap gather — no matter how many copies are
        # already banked, carried or worn.
        # exclude_recycle_leaf=True: a skill grind GATHERS its materials fresh —
        # the descent skips a recyclable-only intermediate (ash_plank via
        # recycling gear) and lands on the gatherable raw (ash_wood), a flat,
        # always-plannable gather. This keeps the grind plannable AND cannot
        # churn gear to grind (recycling the rung to source its own material is
        # a null cycle; recycling OTHER current-tier gear is low priority).
        step = actionable_step(ObtainItem(rung, quantity=1),
                               _grind_probe_state(state, rung),
                               game_data, ctx, exclude_recycle_leaf=True)
        if isinstance(step, ObtainItem) and step.code != rung:
            # exclude_recycle={rung}: never recycle the rung to source its own
            # crafting material — that is the null cycle (rung -> material ->
            # re-craft rung) that churned surplus fire_staff on live Robby.
            return GatherMaterialsGoal(target_item=step.code,
                                       needed={step.code: step.quantity},
                                       skill_grind=True,
                                       exclude_recycle=frozenset({rung}))
        if not isinstance(step, ObtainItem):
            # The descent is BLOCKED (cyclic, or every branch dead-ends) — it
            # found no material to gather. Falling through to the rung goal
            # would hand the planner the very from-scratch chain documented
            # above, so report "cannot grind from here" and let the caller pick
            # another goal instead of burning a budget it cannot spend.
            return None
        # Descent landed ON the rung with its own copies discounted: the
        # recipe materials really are in hand, so the plan is the single craft
        # that earns the XP. `held + 1` (REAL held) keeps that perpetual —
        # craft ANOTHER — and stays cheap because the materials are present.
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
