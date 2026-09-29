"""The route-driven next-action producer: `decompose(goal, ...)`, used by the
arbiter and by a `LevelSkill`'s grind expansion alike.

Phase 2c-2 of docs/PLAN_decision_architecture_redesign.md. A plan is built from
THE ONE WALK (`ObtainModel.walk` over `decompose_core`, proved in
`formal/Formal/Decompose.lean`): feasibility and the next step are one
computation, so decomposition never declines a goal the model judges feasible
(the walk's COMPLETE theorem). Each step becomes a concrete action, is
simulated with that action's own `apply`, and the walk runs again, for a
forecast of up to `_MAX_LEGS` legs; the plan cache replans from the real state
after every step.

This replaces the old descent (`next_craft_core` + `craft_plan_driver_core` over
a separate recipe map and a `Source` projection of the model), which disagreed
with the model about craft yield, secondary-drop gathers and banked copies of
the target, and was patched where each bit (skill-gate emission, a no-source
pre-check, a WITHDRAW filter, a held-leaf exemption, bank-count fudges).

`None` (the caller may search) for a goal shape it does not serve, and for a
decline, which `declined` names: `infeasible:<item>:no_route:<leaves>`,
`unmapped_step:<step>` (a route no concrete action serves yet),
`first_leg_inapplicable:<action>`, `satisfied`, and for potions `no_batch`,
`equip_inapplicable`, `off_ladder_leg`.

SAFETY NET, NOT ADMIT-TIME FILTERING. A route says nothing about a fight's
suicide guard, the bag's free slots or a recycle's floors: the executor
re-validates `is_applicable` on the plan head every cycle before running it, and
`_finish` checks the first leg this cycle.
"""

import dataclasses
from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.decompose_core import OpenGate, Step
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.obtain_model.walk_graph import WalkGraph
from artifactsmmo_cli.ai.obtain_sources import SourceKind
from artifactsmmo_cli.ai.region_edges import admit_region_edges
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def _decline(declined: list[str] | None, reason: str) -> list[Action] | None:
    """Record why decomposition declines (Phase 2c-2.0), then decline. Declines
    were invisible: the caller silently searched instead. `declined` is the
    caller's sink, None when nobody is listening."""
    if declined is not None:
        declined.append(reason)
    return None


def decompose(goal: Goal, state: WorldState, game_data: GameData,
              actions: list[Action], ctx: SelectionContext,
              declined: list[str] | None = None) -> list[Action] | None:
    """The route-driven next-action producer: a plan for `goal` built by
    decomposing its recipe closure over the obtain model's routes, or None when
    decomposition cannot serve it (the caller may then search).

    The ONE entry point every caller uses, so the arbiter's candidate planning
    and a `LevelSkill`'s grind expansion ask the same producer with the same
    source map (Phase 2 of docs/PLAN_decision_architecture_redesign.md). The
    map is built once per call, over the goal's recipe closure, and only for a
    `GatherMaterialsGoal`: every other goal shape short-circuits
    `generate_next_craft_action` immediately. A `CraftPotionsGoal` is served
    as the obtain goal it is (`_decompose_potions`).

    `declined`, when given, receives a named reason for every decline of a goal
    this producer serves (not for a goal shape it does not serve at all)."""
    if isinstance(goal, CraftPotionsGoal):
        return _decompose_potions(goal, state, game_data, actions, ctx, declined)
    if not isinstance(goal, GatherMaterialsGoal):
        return None
    return _walk_plan(goal, state, game_data, actions, ctx, declined)


DECOMPOSE_POLICY = replace(LEGACY, all_gather_routes=True, ge_routes=False)
"""The walk's readiness: LEGACY (what the executor can serve now) with two
switches.

- Every resource that drops an item is offered (D-B), ranked by the proved
  gather-source order. LEGACY's primary-only gather hid a workable spot behind a
  skill-gated one: `small_pearls` drops at bass (fishing 30) and salmon
  (fishing 40, the most frequent), and primary-only offered salmon alone, so
  the walk opened a fishing grind instead of gathering at bass.
- No GE fill (D-E). A fill spends gold, and whether a standing order is worth
  its price against the time a fight or gather costs is a COST question the
  model cannot answer yet (the cost view); fills stay the venue choice goal
  emission makes beside an NPC buy (`choose_buy_venue`). The old descent never
  used them either: its "ge_fill" step fell through the mapping into a fight."""

_MAX_LEGS = 8
"""Legs simulated ahead. The plan cache replans from the real state after every
step, so the tail is a forecast (the TUI shows it; the cache keeps it while each
step stays applicable), never a commitment."""


def _walk_plan(goal: GatherMaterialsGoal, state: WorldState, game_data: GameData,
               actions: list[Action], ctx: SelectionContext,
               declined: list[str] | None) -> list[Action] | None:
    """The goal's plan from THE ONE WALK (Phase 2c-2b of
    docs/PLAN_decision_architecture_redesign.md): the next step of
    `ObtainModel.walk` under `DECOMPOSE_POLICY`, as a concrete action, simulated
    with the action's own `apply`, and walked again, up to `_MAX_LEGS` legs. It
    stops after a fight (its drops are stochastic) and after a skill sub-task
    (a grind of its own); the next cycle replans from the real state.

    The walk is proved complete: a feasible goal the bag does not hold always
    has a step, so a decline here names either an infeasible goal (with the
    item the walk could not supply) or a step no concrete action serves.

    The goal's rung (`exclude_recycle`, a skill grind's) is PRODUCED: its
    banked or recyclable copies do not count toward it, since the XP is in the
    craft. No goal target is ever destroyed to source its own parts. A skill
    gate is a sub-task when the pool holds an applicable `LevelSkill` for it."""
    grinds: dict[tuple[str, int | None], LevelSkill] = {
        (a.skill, a.target_level): a for a in actions if isinstance(a, LevelSkill)}
    verdicts: dict[tuple[str, int | None], bool] = {}

    def openable(gate: Gate) -> bool:
        """A skill gate the pool has an APPLICABLE `LevelSkill` for, asked only
        for the gates the walk meets (a grind's applicability walks its own
        rung, so asking it of the whole pool up front cost more than the walk)."""
        if gate.kind not in (GateKind.GATHER_SKILL, GateKind.CRAFT_SKILL):
            return False
        key = (gate.subject, gate.level)
        if key not in verdicts:
            grind = grinds.get(key)
            verdicts[key] = grind is not None and grind.is_applicable(state, game_data)
        return verdicts[key]

    relevant = admit_region_edges(goal.relevant_actions(actions, state, game_data),
                                  actions, state, game_data)
    for item, needed in goal.needed.items():
        qty = _bag_target(item, needed, goal.exclude_recycle, state)
        legs: list[Action] = []
        sim = state
        for _ in range(_MAX_LEGS):
            answer = ObtainModel(sim, game_data, ctx, datetime.now(UTC)).walk(
                item, qty, DECOMPOSE_POLICY, goal.exclude_recycle, openable, frozenset(goal.needed))
            if answer.step is None:
                if not legs and not answer.feasible:
                    graph = answer.graph
                    dead = sorted(code for code, routes in graph.routes.items()
                                  if not routes and not graph.on_hand.get(code, 0))
                    return _decline(declined, f"infeasible:{item}:no_route:{','.join(dead)}")
                break
            action = _action_for(answer.step, answer.graph, relevant, actions,
                                 sim, game_data, ctx.bank_accessible)
            if action is None:
                if legs:
                    break
                return _decline(declined, f"unmapped_step:{answer.step!r}")
            legs.append(action)
            if isinstance(action, (FightAction, LevelSkill)) or not action.is_applicable(sim, game_data):
                break
            sim = action.apply(sim, game_data)
        if legs:
            return _finish(legs, state, game_data, declined)
    return _decline(declined, "satisfied")


def _bag_target(item: str, needed: int, produce: frozenset[str], state: WorldState) -> int:
    """The walk's target in the bag for `needed` of `item`. `needed` counts the
    bag and the bank, as `GatherMaterialsGoal.is_satisfied` does, and the walk
    withdraws banked copies, so the bag target is `needed` itself. A PRODUCED
    item (a skill grind's rung, `held + 1`) is the exception: its banked copies
    are never withdrawn (the XP is in the making), so the target is the bag plus
    the copies still to MAKE, `needed - bag - bank`, not a bag refill."""
    if item not in produce:
        return needed
    bag = state.inventory.get(item, 0)
    banked = (state.bank_items or {}).get(item, 0)
    return bag + max(0, needed - bag - banked)


def _action_for(step: Step[str], graph: WalkGraph, relevant: list[Action], pool: list[Action],
                state: WorldState, game_data: GameData, bank_accessible: bool) -> Action | None:
    """The concrete action a walk step names, sized to it: the goal's own
    sized actions first, then the whole pool, and a withdraw built at the bank
    tile when neither has one. None for a route no action serves yet (GE fill,
    sale, fight gold, task reward: 2c-2d constructs them)."""
    candidates = (*relevant, *pool)
    if isinstance(step, OpenGate):
        gate = step.gate
        assert isinstance(gate, Gate)
        return next((a for a in candidates if isinstance(a, LevelSkill)
                     and a.skill == gate.subject and a.target_level == gate.level), None)
    route = graph.sources[step.item][step.route]
    if route.kind is SourceKind.WITHDRAW:
        found = next((a for a in candidates
                      if isinstance(a, WithdrawItemAction) and a.code == step.item), None)
        if found is None:
            return WithdrawItemAction(code=step.item, quantity=step.amount,
                                      bank_location=game_data.bank_location(),
                                      accessible=bank_accessible)
        return dataclasses.replace(found, quantity=step.amount)
    if route.kind is SourceKind.GATHER:
        gather = next((a for a in candidates if isinstance(a, GatherAction)
                       and a.resource_code == route.via and a.drop_item(game_data) == step.item), None)
        return None if gather is None else dataclasses.replace(gather, quantity=step.runs)
    if route.kind is SourceKind.CRAFT:
        craft = next((a for a in candidates if isinstance(a, CraftAction) and a.code == step.item), None)
        return None if craft is None else dataclasses.replace(craft, quantity=step.runs)
    if route.kind is SourceKind.RECYCLE:
        recycle = next((a for a in candidates if isinstance(a, RecycleAction) and a.code == route.via), None)
        return None if recycle is None else dataclasses.replace(recycle, quantity=step.runs)
    if route.kind is SourceKind.BUY:
        buy = next((a for a in candidates if isinstance(a, NpcBuyAction)
                    and a.npc_code == route.via and a.item_code == step.item), None)
        return None if buy is None else dataclasses.replace(buy, quantity=step.amount)
    if route.kind is SourceKind.DROP:
        # Which dropper to fight is the proved selection's (expected kills,
        # then distance; the grey drop_farm variant): the route only proved a
        # fight can serve the item.
        # The goal's own actions come last so their fight (possibly the
        # synthesized drop_farm variant the static pool lacks) wins per monster.
        return select_drop_fight(step.item, [*pool, *relevant], state, game_data,
                                 allow_grey=DECOMPOSE_POLICY.allow_grey)
    return None


def _decompose_potions(goal: CraftPotionsGoal, state: WorldState, game_data: GameData,
                       actions: list[Action], ctx: SelectionContext,
                       declined: list[str] | None = None) -> list[Action] | None:
    """The potion batch as an obtain plan: the legs that put the batch in the
    bag, then the equip that lands it (Phase 2c-1 of
    docs/PLAN_decision_architecture_redesign.md).

    Live Robby 2026-09-29: A* searched this goal about 70 times an hour and
    timed out at ~200k nodes, depth 92, with no plan, because the batch the
    guard judged suppliable was longer than the search could reach.

    The plan may stop short of the equip: each leg is a bounded batch, and the
    plan cache replans from the real state after every step, as it does for
    the grind's one-leg plans.

    None (the caller may search) when the goal is unseeded or satisfied, when
    the batch cannot be decomposed, or when its plan would fight or open a
    skill grind: the potion supply ladder serves neither (`POTION_POLICY` has
    no drops and gates gathers on skill), and a guard's batch must not turn
    into a different errand."""
    equip = goal.batch_equip(state)
    if equip is None:
        return _decline(declined, "potion:no_batch")
    obtain = goal.batch_obtain(state)
    if obtain is None:
        if equip.is_applicable(state, game_data):
            return [equip]
        return _decline(declined, f"potion:equip_inapplicable:{equip!r}")
    legs = decompose(obtain, state, game_data, actions, ctx, declined)
    if legs is None:
        return None
    if any(isinstance(a, (FightAction, LevelSkill)) for a in legs):
        errand = next(a for a in legs if isinstance(a, (FightAction, LevelSkill)))
        return _decline(declined, f"potion:off_ladder_leg:{errand!r}")
    # A leg is sized to a bounded batch (`size_intermediate_craft`), so the legs
    # can be a PREFIX of the batch: the equip joins the plan only when they
    # land the whole batch, and otherwise the next cycle decomposes the rest.
    landed = state
    for leg in legs:
        landed = leg.apply(landed, game_data)
    return [*legs, equip] if equip.is_applicable(landed, game_data) else legs


def _finish(mapped: list[Action], state: WorldState, game_data: GameData,
            declined: list[str] | None = None) -> list[Action] | None:
    """Front an optimal-loadout re-arm when the plan opens with a suboptimal
    Gather/Fight, then gate the whole plan on the first leg's applicability NOW.

    The directed fast-path emits a deterministic recycle/withdraw/gather/craft/
    buy/drop leg but does NOT model every inventory-room precondition. If the
    first leg is not applicable NOW (e.g. a stack-creating gather blocked by a
    full slot cap — the slot-exhaustion case, or a Fight that fails its
    suicide guard, or a Recycle that violates its bag/owned floor), defer to
    A*, which sequences the slot-freeing relief (DepositAll/Recycle/Sell)
    before the leg, or finds no plan honestly.

    `mapped` is always non-empty at both call sites (a LevelSkill leg, or a
    non-empty `craft_plan_full` plan)."""
    result = _with_rearm(mapped, state, game_data)
    if not result[0].is_applicable(state, game_data):
        return _decline(declined, f"first_leg_inapplicable:{result[0]!r}")
    return result


def _with_rearm(mapped: list[Action], state: WorldState,
                game_data: GameData) -> list[Action]:
    """Front the per-skill (Gather) or per-monster (Fight) loadout optimizer
    right before the FIRST Gather/Fight leg in `mapped`, when that leg's
    loadout is suboptimal. This generated path bypasses A* entirely
    (nodes=0), so the loadout-penalty cost terms never get a vote here —
    live trace 2026-07-05: every generated helmet plan opened bare-handed
    while the ferried copper_pickaxe rode in the bag.

    SCANS PAST any leading Recycle/Withdraw/Craft/Buy legs rather than only
    inspecting `mapped[0]` (whole-branch review, IMPORTANT 2, re-derived
    under the shared obtain model): recycle is now an ORDINARY leg in the
    SAME plan `craft_plan_full` returns, so a plan can be
    `[Recycle, Gather, Craft]` with the Recycle at index 0 — checking only
    `mapped[0]` would silently skip the re-arm and let the plan cache
    execute the Gather bare-handed, recreating the exact bug this helper
    exists to fix. Equipping a tool is unaffected by a prior recycle/
    withdraw/craft/buy leg, so `rearm.is_applicable` is still asked of the
    CURRENT `state` (the legs ahead of the Gather/Fight don't touch
    equipment) — only the INSERTION POINT moves, not the state it is judged
    against. A plan with no Gather/Fight leg at all (pure
    recycle/withdraw/craft/buy) is returned unchanged.

    Fight mirror (Task 5b Part 3): a mapped plan's Fight leg may be
    structurally fine but equipped suboptimally for the monster — the hard
    loadout gate would then reject it at execution (player.py runs plan[0]
    directly). Front `OptimizeLoadout(target_monster_code=...)` whenever it is
    `is_applicable`: `_swap_plan` is empty (and so `is_applicable` False) when
    the equipped loadout is already optimal for that monster, so this check is
    self-guarding — no separate `equipped_matches_loadout` predicate needed
    here."""
    for i, action in enumerate(mapped):
        if isinstance(action, FightAction):
            rearm = OptimizeLoadoutAction(
                target_monster_code=action.monster_code, game_data=game_data
            )
            if not rearm.is_applicable(state, game_data):
                return mapped  # loadout already optimal for this monster
            return [*mapped[:i], rearm, *mapped[i:]]
        if isinstance(action, GatherAction):
            skill_req = game_data.resource_skill_level(action.resource_code)
            if skill_req is None:
                return mapped
            rearm = OptimizeLoadoutAction(target_skill=skill_req[0], game_data=game_data)
            if not rearm.is_applicable(state, game_data):
                return mapped  # loadout already optimal for this skill
            return [*mapped[:i], rearm, *mapped[i:]]
    return mapped
