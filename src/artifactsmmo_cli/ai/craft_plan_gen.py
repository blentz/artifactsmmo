"""The route-driven next-action producer: `decompose(goal, ...)`, used by the
arbiter.

Phase 2c-2 of docs/PLAN_decision_architecture_redesign.md. A plan is built from
THE ONE WALK (`ObtainModel.walk` over `decompose_core`, proved in
`formal/Formal/Decompose.lean`): feasibility and the next step are one
computation, so decomposition never declines a goal the model judges feasible
(the walk's COMPLETE theorem). The plan is the walk's whole witness, each leg
a concrete action (Phase 2d-L1c): executed from the bag it delivers the goal
(`formal/Formal/DecomposeWitness.lean`), and the plan cache follows it leg by
leg, repeating a leg that comes up short.

This replaces the old descent (`next_craft_core` + `craft_plan_driver_core` over
a separate recipe map and a `Source` projection of the model), which disagreed
with the model about craft yield, secondary-drop gathers and banked copies of
the target, and was patched where each bit (skill-gate emission, a no-source
pre-check, a WITHDRAW filter, a held-leaf exemption, bank-count fudges).

`None` (the caller may search) for a goal shape it does not serve, and for a
decline, which `declined` names: `infeasible:<item>:no_route:<leaves>`,
`unmapped_step:<step>` (a route no concrete action serves yet),
`first_leg_inapplicable:<action>`, `bag_overflow:qty=<peak>/<max>:slots=<peak>/<max>`,
`satisfied`, and for potions `no_batch`,
`equip_inapplicable`, `off_ladder_leg`.

SAFETY NET, NOT ADMIT-TIME FILTERING. A route says nothing about a fight's
suicide guard, the bag's free slots or a recycle's floors: the executor
re-validates `is_applicable` on the plan head every cycle before running it, and
`_finish` checks the first leg this cycle.
"""

import dataclasses
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.acquisition_cost import door_route, fight_gold_monster
from artifactsmmo_cli.ai.actions.base import Action, serves_region
from artifactsmmo_cli.ai.actions.combat import FightAction, win_gold
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bag_clear import clear_actions, related_codes
from artifactsmmo_cli.ai.bag_peak import plan_bag_peak
from artifactsmmo_cli.ai.best_loadout import loadout_for
from artifactsmmo_cli.ai.currency_buy_batch import currency_buy_batch_pure
from artifactsmmo_cli.ai.decompose_core import Act, OpenGate, Step
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.fight_room_license import refused_monster
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.grey_farm import grey_farm_allowed, serves_a_demand
from artifactsmmo_cli.ai.grind_heal_prep import HEAL_PREP_POLICY, heal_prep_goal
from artifactsmmo_cli.ai.grind_rung import grind_rung_goal
from artifactsmmo_cli.ai.obtain_model.gate import Door, Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, PIECE_POLICY, Policy
from artifactsmmo_cli.ai.obtain_model.walk_graph import WalkAnswer, WalkGraph
from artifactsmmo_cli.ai.obtain_sources import SourceKind
from artifactsmmo_cli.ai.potion_supply import POTION_POLICY
from artifactsmmo_cli.ai.progression_reserve import spendable_pocket
from artifactsmmo_cli.ai.region_edges import REGION_EDGE_TAG, admit_region_edges, crossings
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState


def _decline(declined: list[str] | None, reason: str) -> list[Action] | None:
    """Record why decomposition declines (Phase 2c-2.0), then decline. Declines
    were invisible: the caller silently searched instead. `declined` is the
    caller's sink, None when nobody is listening."""
    if declined is not None:
        declined.append(reason)
    return None


SEARCH_HANDOFFS = ("upgrade:uncommitted", "upgrade:ge_venue:")
"""Declines that hand a goal to the A* search ON PURPOSE (Phase 2e): the
search picks among uncommitted upgrades, and buying an upgrade off the GE
book against making it is a price question the walk does not answer (D-E).
Every other decline of a goal this producer serves is final."""


def hands_off_to_search(declined: list[str]) -> bool:
    """Whether a `decompose` that returned None leaves the goal to the search:
    yes when it named no decline (a goal shape it does not serve) or a
    `SEARCH_HANDOFFS` one; no for any other decline, which is the goal's
    answer (Phase 2e: the fallback fired 0 useful times in 15 h live and on 0 of
    599 craft-census cells)."""
    return not declined or any(reason.startswith(SEARCH_HANDOFFS) for reason in declined)


def decompose(goal: Goal, state: WorldState, game_data: GameData,
              actions: list[Action], ctx: SelectionContext,
              declined: list[str] | None = None, *,
              subtasks: bool = True,
              policy: Policy = DECOMPOSE_POLICY,
              outermost: bool = True) -> list[Action] | None:
    """The route-driven next-action producer: a plan for `goal` built by
    decomposing its recipe closure over the obtain model's routes, or None when
    decomposition cannot serve it (the caller may then search).

    The ONE entry point every caller uses, so every candidate the arbiter
    plans asks the same producer with the same source map (Phase 2 of docs/PLAN_decision_architecture_redesign.md). The
    map is built once per call, over the goal's recipe closure, and only for a
    `GatherMaterialsGoal`: every other goal shape short-circuits
    `generate_next_craft_action` immediately. A `CraftPotionsGoal` is served
    as the obtain goal it is (`_decompose_potions`).

    A `ReachSkillGoal` is served by its grind (`_decompose_grind`, Phase 2d-a):
    the arbiter plans the grind's real legs instead of an opaque `LevelSkill`
    macro that a second planner expanded at execution. A committed
    `UpgradeEquipmentGoal` is the walk's plan for its item, then the equip
    (`_decompose_upgrade`, Phase 2d-b).

    `declined`, when given, receives a named reason for every decline of a goal
    this producer serves (not for a goal shape it does not serve at all).
    `subtasks=False` forbids opening a skill gate as a sub-task (a potion batch
    or a heal stock must not turn into a grind). `policy` is the walk's
    readiness for a `GatherMaterialsGoal`: a batch chosen under a narrower
    policy (the potion ladder's, the heal prep's) is decomposed under that
    same policy, so the walk serves exactly what selection judged feasible
    (Phase 2d-F).

    A plan whose bag would overflow at some leg (`bag_peak.plan_bag_peak`,
    total quantity or occupied slots) first tries the ONE make-room mechanism,
    the full-bag clear (`bag_clear.clear_actions`, Task 13e ruling T13e-b): every
    stack the plan does not use leaves (banked, or the junk policy for a stack
    the bank refuses), and the plan is kept with the clear in front when that
    makes it fit. Otherwise it declines as
    `bag_overflow:...`: the walk counts quantities, not the bag, and the plan is
    committed, so a leg that cannot fit would stall it mid-cycle.

    The clear runs only at the OUTERMOST call (`outermost`). A nested decompose
    (a grind's heal prep, a potion batch's obtain) that overflows declines
    instead: its plan is a prefix of the outer one, and cleared against its own
    legs alone it would bank or junk a stack the outer plan consumes (Task 13e
    re-review m2; USER: never shed a related item). The outer call judges and
    clears the WHOLE plan, so the related set holds every leg. The outermost
    grind retries an overflowing prep with the clear in front of the prep AND
    its legs (`_prep_after_clear`, ruling T14d-1), so a prep that fits once the
    bag is cleared runs this cycle; one that does not fit even then is skipped,
    as before, and never blocks the grind.

    The deposit is the plan's, not the deposit guard's: that guard fires on
    pressure (`DEPOSIT_FULL_FRACTION`), and a bag far below it can still be too
    full for the plan ahead. Live HAL 2026-10-11 21:35Z: 61/164 items in 17/20
    slots, `GatherMaterials(cooked_shrimp, 120, carry)` declined
    `bag_overflow:qty=181/164`, no guard fired, and the bot waited 12 cycles."""
    walked = _dispatch(goal, state, game_data, actions, ctx, declined, subtasks, policy, outermost)
    if walked is None:
        return None
    plan = _bridge_regions(walked, state, game_data, actions, declined)
    if plan is None:
        return None
    peak_qty, peak_slots = plan_bag_peak(plan, state, game_data)
    if peak_qty > state.inventory_max or peak_slots > state.inventory_slots_max:
        cleared = (_clear_first(walked, state, game_data, actions, ctx)
                   if outermost else None)
        if cleared is not None:
            return cleared
        return _decline(declined, f"bag_overflow:qty={peak_qty}/{state.inventory_max}"
                                  f":slots={peak_slots}/{state.inventory_slots_max}")
    return plan


def _clear_first(walked: list[Action], state: WorldState, game_data: GameData,
                 actions: list[Action], ctx: SelectionContext) -> list[Action] | None:
    """`walked` with the full-bag clear in front (`bag_clear.clear_actions`:
    every stack the walk does not use leaves), region-bridged, when the clear
    frees something and the plan then fits the bag; None otherwise."""
    clear = clear_actions(state, game_data, actions, ctx,
                          related_codes(walked, state, game_data, ctx))
    if not clear.actions:
        return None
    plan = _bridge_regions([*clear.actions, *walked], state, game_data, actions, None)
    if plan is None:
        return None
    peak_qty, peak_slots = plan_bag_peak(plan, state, game_data)
    if peak_qty > state.inventory_max or peak_slots > state.inventory_slots_max:
        return None
    return plan


def _bridge_regions(plan: list[Action], state: WorldState, game_data: GameData,
                    actions: list[Action], declined: list[str] | None) -> list[Action] | None:
    """`plan` with a region crossing before every leg that acts in another
    region than the one the plan has reached, or None (a named decline) when no
    single crossing from the pool gets there.

    The walk names WHAT to do, not WHERE it is reachable from: its legs carry
    their `travel_region`, which the search filters on and the walk did not.
    Live 2026-10-08, `SupplyBank(cooked_rat_meatx10)`: rat lives on the interior
    layer of the Abandoned House (`interior:-3,12` / `-2,12`), its plan was
    [Fight(rat), Craft(...)] from the overworld, and 51 fights came back HTTP 598
    "Monster not found on this map" on the identically-numbered overworld tile.
    The crossing is a `MapTransitionAction` (`region_edges.REGION_EDGE_TAG`, the
    edge the search admits for the same reason), chosen applicable where the
    plan stands and landing in the leg's region; the way back out is the same
    question asked of the next leg."""
    edges = [edge for edge in actions if REGION_EDGE_TAG in edge.tags]
    bridged: list[Action] = []
    at = state
    for leg in plan:
        here = game_data.state_region(at)
        if not serves_region(leg, here):
            route = crossings(at, leg.travel_region, edges, game_data)
            if route is None:
                return _decline(declined, f"region:{here}->{leg.travel_region}:{leg!r}")
            for crossing in route:
                bridged.append(crossing)
                at = crossing.apply(at, game_data)
        bridged.append(leg)
        if leg.is_applicable(at, game_data):
            at = leg.apply(at, game_data)
    return bridged


def _dispatch(goal: Goal, state: WorldState, game_data: GameData, actions: list[Action],
              ctx: SelectionContext, declined: list[str] | None, subtasks: bool,
              policy: Policy, outermost: bool) -> list[Action] | None:
    """`decompose` by goal shape, before the bag check. `outermost` is
    `decompose`'s: only the outermost grind may clear the bag for its prep."""
    if isinstance(goal, CraftPotionsGoal):
        return _decompose_potions(goal, state, game_data, actions, ctx, declined)
    if isinstance(goal, ReachSkillGoal):
        return _decompose_grind(goal.skill, goal.target_level, state, game_data, actions, ctx,
                                declined, frozenset(), outermost)
    if isinstance(goal, UpgradeEquipmentGoal):
        return _decompose_upgrade(goal, state, game_data, actions, ctx, declined, subtasks)
    if isinstance(goal, SupplyBankGoal):
        return _decompose_supply(goal, state, game_data, actions, ctx, declined, policy)
    if not isinstance(goal, GatherMaterialsGoal):
        return None
    if goal.fight_gold:
        # An `L*` piece priced through fight gold (plan B Task 15, ruling
        # T3a): only its goal's walk may fight for gold, and a grey monster
        # may pay it, as `PIECE_POLICY` priced it. It also fills a standing GE
        # sell order (ruling T14a-C: the piece is served by the route that
        # priced it, and `PIECE_POLICY` prices GE fills), so D-E is lifted for
        # a piece's goal only: the price, not the walk, weighed the fill.
        return _walk_plan(goal, state, game_data, actions, ctx, declined, subtasks, frozenset(),
                          replace(policy, fight_gold=True, ge_routes=True), frozenset({GOLD_CODE}))
    return _walk_plan(goal, state, game_data, actions, ctx, declined, subtasks, frozenset(), policy)


def _decompose_supply(goal: SupplyBankGoal, state: WorldState, game_data: GameData,
                      actions: list[Action], ctx: SelectionContext,
                      declined: list[str] | None, policy: Policy) -> list[Action] | None:
    """A supply request as an obtain plan: the walk's plan for the units still
    to produce, then the deposit that banks them.

    It used to go to A* alone. Live 2026-10-07, the first fleet consumable
    floor request (`SupplyBank(cooked_rat_meatx10)`, rat drops then cooking):
    200k-1M nodes per attempt, timed out, plan_len 0, on every attempt by
    three characters — the batch-aware walk is the planner for "obtain N of X".
    No skill gate opens as a sub-task: the producer was chosen because its role
    already serves the item (`serves_item`). The walk is asked against the bank
    minus the target's own copies (`SupplyBankGoal.production`), so it never
    withdraws what it is banking."""
    if goal.is_satisfied(state):
        return _decline(declined, "satisfied")
    bank_location = game_data.bank_location_or_none
    if bank_location is None:
        return _decline(declined, "supply:no_bank")
    production_state, obtain, deficit = goal.production(state)
    legs = _walk_plan(obtain, production_state, game_data, actions, ctx, declined, False,
                      frozenset(), policy)
    if legs is None:
        return None
    deposit = DepositItemAction(code=goal.item_code, quantity=deficit, bank_location=bank_location,
                                accessible=ctx.bank_accessible)
    landed = state
    for leg in legs:
        if leg.is_applicable(landed, game_data):
            landed = leg.apply(landed, game_data)
    return [*legs, deposit] if deposit.is_applicable(landed, game_data) else legs


def _decompose_upgrade(goal: UpgradeEquipmentGoal, state: WorldState, game_data: GameData,
                       actions: list[Action], ctx: SelectionContext,
                       declined: list[str] | None, subtasks: bool) -> list[Action] | None:
    """A committed upgrade as an obtain plan (Phase 2d-b): the walk's committed
    plan for one copy of the item (a banked copy is withdrawn; a skill gate
    opens as a sub-grind), then the equip that lands it in the slot.

    Its only A* route to a skill-gated item used to be the `LevelSkill` macro,
    which is leaving the action pool. The equip joins only when the legs land
    the item (a plan that ends in a sub-grind does not), and the next cycle
    decomposes the rest, as the potion batch does."""
    if goal.committed_target is None:
        return _decline(declined, "upgrade:uncommitted")
    if goal.is_satisfied(state):
        return _decline(declined, "satisfied")
    item, slot = goal.committed_target
    equip = EquipAction(code=item, slot=slot)
    held = replace(state, inventory={**state.inventory, item: state.inventory.get(item, 0) + 1})
    if not equip.is_applicable(state if state.inventory.get(item, 0) >= 1 else held, game_data):
        # Decline before obtaining a copy the equip could not use: a withdraw
        # the next cycle cannot follow up is banked again by the deposit guard.
        return _decline(declined, f"upgrade:equip_inapplicable:{equip!r}")
    if state.inventory.get(item, 0) >= 1:
        return [equip]
    if game_data.ge_best_sell_order(item) is not None:
        # The book sells it: buying off the GE against making it is a price
        # question the walk does not answer (no GE routes, D-E); the search,
        # which prices both, keeps that choice.
        return _decline(declined, f"upgrade:ge_venue:{item}")
    legs = _walk_plan(GatherMaterialsGoal(item, {item: 1}), state, game_data, actions, ctx,
                      declined, subtasks, frozenset(), grey_exempt=frozenset({item}))
    if legs is None:
        return None
    landed = state
    for leg in legs:
        if leg.is_applicable(landed, game_data):
            landed = leg.apply(landed, game_data)
    return [*legs, equip] if equip.is_applicable(landed, game_data) else legs


def _decompose_grind(skill: str, target_level: int, state: WorldState, game_data: GameData,
                     actions: list[Action], ctx: SelectionContext, declined: list[str] | None,
                     grinding: frozenset[str], outermost: bool) -> list[Action] | None:
    """The legs of one grind cycle toward `target_level` in `skill` (Phase 2d-a):
    rung `grind_rung_goal` names (another rung, whose committed plan ends in the
    leg that earns), served by the one walk, whose own skill
    gates open as sub-tasks in turn. `grinding` holds the skills already being
    ground further up; the walk never opens their gates again, so a cyclic
    dependency is infeasible rather than a loop.

    When the grind's plan holds a fight (anywhere: the plan is committed, so a
    fight after a gather still runs this cycle) and the food the chosen loadout
    eats against its monster is short of its carry, the legs that stock it come
    first (`grind_heal_prep`): the leaf task builds what it needs. The prep never opens a grind of its own and is
    skipped when it cannot be served, since it saves requests and must never
    block the grind (live C3P0 2026-09-28: `Craft(cheese×1)` + eat before every
    fight)."""
    if state.skills.get(skill, 1) >= target_level:
        return _decline(declined, "satisfied")
    rung = grind_rung_goal(skill, state, game_data, ctx)
    if rung is None:
        return _decline(declined, f"no_grind_rung:{skill}")
    legs = _walk_plan(rung, state, game_data, actions, ctx, declined, True, grinding | {skill})
    if legs is None:
        return None
    fight = next((a for a in legs if isinstance(a, FightAction)), None)
    if fight is not None:
        # The fight is priced at `loadout_for`'s pick, read once (ruling
        # T14d-R m4) for its bag-room verdict and its heal prep: a pick whose
        # loop has no room for the drops refuses the fight here, as the
        # cycle's own refuses it in the pool (ruling T14d-2).
        loadout = loadout_for(state, game_data, ctx, fight.monster_code)
        if refused_monster(loadout) is not None:
            return _decline(declined, f"fight_no_room:{fight.monster_code}")
        prep = heal_prep_goal(state, game_data, ctx, loadout)
        if prep is not None:
            prep_declined: list[str] = []
            prep_legs = decompose(prep, state, game_data, actions, ctx, prep_declined,
                                  subtasks=False, policy=HEAL_PREP_POLICY, outermost=False)
            if declined is not None:
                declined.extend(f"heal_prep:{reason}" for reason in prep_declined)
            if prep_legs:
                return [*prep_legs, *legs]
            if outermost and prep_declined and prep_declined[-1].startswith("bag_overflow:"):
                cleared = _prep_after_clear(prep, legs, state, game_data, actions, ctx)
                if cleared is not None:
                    return cleared
    return legs


def _prep_after_clear(prep: GatherMaterialsGoal, legs: list[Action], state: WorldState,
                      game_data: GameData, actions: list[Action],
                      ctx: SelectionContext) -> list[Action] | None:
    """The prep and the grind's legs behind the full-bag clear, when the clear
    makes the WHOLE plan fit (ruling T14d-1): the prep's own walk (unjudged,
    under `HEAL_PREP_POLICY`) then `legs`, cleared against both, so no stack
    either uses leaves (T13e-g). None when the clear does not make it fit; the
    grind then runs without the prep.

    The prep's walk cannot fail here: `bag_overflow` is declined only after
    the same walk, over the same inputs, returned its legs."""
    walked = _dispatch(prep, state, game_data, actions, ctx, None, False, HEAL_PREP_POLICY, False)
    assert walked is not None, f"the prep {prep!r} walked once and not again"
    return _clear_first([*walked, *legs], state, game_data, actions, ctx)


def _walk_plan(goal: GatherMaterialsGoal, state: WorldState, game_data: GameData,
               actions: list[Action], ctx: SelectionContext,
               declined: list[str] | None, subtasks: bool,
               grinding: frozenset[str],
               policy: Policy = DECOMPOSE_POLICY,
               grey_exempt: frozenset[str] = frozenset()) -> list[Action] | None:
    """The goal's plan from THE ONE WALK (Phase 2c-2b of
    docs/PLAN_decision_architecture_redesign.md): the legs `ObtainModel.walk`
    extracts under `DECOMPOSE_POLICY`, each as a concrete action.

    COMMITTED (Phase 2d-L1c): the plan is the whole witness of the walk's yes,
    proved to deliver the goal when executed from the bag
    (`DecomposeWitness.feasible_witness`), not a forecast re-walked after each
    leg. Re-walking does not converge: a leg that shrinks a deficit can make an
    earlier route usable that spends a scarce unit a later leg needed, and the
    re-walk declines a goal the plan would have reached. A leg that comes up
    short (a gather or a drop below its average) is repeated by the plan cache
    until it delivers. The plan stops at a skill gate: the grind that opens it
    (`_decompose_grind`) is the plan's tail, and the next cycle continues from
    there. It also stops at one bag-load of an item-currency buy of the goal's
    own item (`_one_trip`): the walk is asked for the smaller target, and the
    next cycle walks the rest.

    The walk is proved complete: a feasible goal the bag does not hold always
    has a step, so a decline here names either an infeasible goal (with the
    item the walk could not supply) or a step no concrete action serves.

    The goal's rung (`exclude_recycle`, a skill grind's) is PRODUCED: its
    banked or recyclable copies do not count toward it, since the XP is in the
    craft. No goal target is ever destroyed to source its own parts. A skill
    gate is a sub-task (when `subtasks` allows it) when the skill can be ground
    from here and is not already being ground further up (`grinding`)."""
    verdicts: dict[tuple[str, int | None], bool] = {}

    def openable(gate: Gate) -> bool:
        """A skill gate the character can grind open, asked only for the gates
        the walk meets (a grind's openness walks its own rung)."""
        if (not subtasks or gate.kind not in (GateKind.GATHER_SKILL, GateKind.CRAFT_SKILL)
                or gate.level is None or gate.subject in grinding):
            return False
        key = (gate.subject, gate.level)
        if key not in verdicts:
            verdicts[key] = skill_is_grindable(gate.subject, gate.level, state, game_data)
        return verdicts[key]

    grey_verdicts: dict[str, bool] = {}

    def grey_ok(item: str) -> bool:
        """Whether a zero-xp dropper may serve `item` (the 2026-07-06 grey-farm
        directive, as the search's admission applied it): a skill grind farms
        greys by design (`GRIND_ALLOWS_GREY`), an upgrade's own target is its
        own consumer (`grey_exempt`), and anything else only when the
        directive licenses the drop (`grey_farm_allowed`)."""
        if goal.skill_grind or item in grey_exempt:
            return True
        if goal.piece_material and serves_a_demand(item, game_data):
            # An `L*` piece's material walk (ruling T14a-D): the demand gate
            # alone, as `ai/grey_farm.py` states.
            return True
        if item not in grey_verdicts:
            grey_verdicts[item] = grey_farm_allowed(item, state, game_data)
        return grey_verdicts[item]

    relevant = admit_region_edges(goal.relevant_actions(actions, state, game_data),
                                  actions, state, game_data)
    # A walk that may fight for gold counts only the pocket its buy may spend
    # (`spendable_pocket`, the reserve `NpcBuy` keeps through `can_spend`), so
    # the buy is planned only once it will pass, and the gold the reserve
    # keeps is fought for. Its gold leg fights the monster the piece's price
    # fought (`fight_gold_monster` under `PIECE_POLICY`).
    walked = (replace(state, gold=spendable_pocket(state, game_data, frozenset(goal.needed)))
              if policy.fight_gold else state)
    gold_monster = (fight_gold_monster(state, game_data, ctx, policy=PIECE_POLICY)
                    if policy.fight_gold else None)
    preferred: dict[str, tuple[SourceKind, str] | None] = {}

    def prefer(code: str) -> tuple[SourceKind, str] | None:
        """The route past a door the pricer took for `code`, asked only of an
        item the walk can reach past a door (ruling T14e-1): the walk serves
        the route the price took."""
        if code not in preferred:
            preferred[code] = door_route(code, walked, game_data, ctx, policy=policy,
                                         pocket=walked.gold)
        return preferred[code]

    for item, needed in goal.needed.items():
        qty = _bag_target(item, needed, goal.exclude_recycle, state)
        model = ObtainModel(walked, game_data, ctx, datetime.now(UTC))
        answer = model.walk(item, qty, policy, goal.exclude_recycle, openable,
                            frozenset(goal.needed), grey_ok, prefer)
        trip = _one_trip(item, qty, answer, state, game_data)
        if trip < qty:
            answer = model.walk(item, trip, policy, goal.exclude_recycle, openable,
                                frozenset(goal.needed), grey_ok, prefer)
        if not answer.feasible:
            graph = answer.graph
            dead = sorted(code for code, routes in graph.routes.items()
                          if not routes and not graph.on_hand.get(code, 0))
            return _decline(declined, f"infeasible:{item}:no_route:{','.join(dead)}")
        legs: list[Action] = []
        sim = state
        for leg in answer.plan:
            if isinstance(leg, OpenGate):
                gate = leg.gate
                assert isinstance(gate, Gate)
                if gate.kind is GateKind.SPAWN_KNOWN:
                    sub = _open_door(gate.doors[0], sim, game_data, actions, ctx, declined,
                                     subtasks, grinding, policy)
                else:
                    assert gate.level is not None
                    sub = _decompose_grind(gate.subject, gate.level, sim, game_data, actions,
                                           ctx, declined, grinding, False)
                if sub is None:
                    if legs:
                        break
                    return None
                legs.extend(sub)
                break
            action = _action_for(leg, answer.graph, relevant, actions, state, game_data,
                                 ctx.bank_accessible, grey_ok, gold_monster)
            if action is None:
                if legs:
                    break
                return _decline(declined, f"unmapped_step:{leg!r}")
            legs.append(action)
            if isinstance(action, FightAction) and action.gold_target is not None:
                # One fight for gold, then the next cycle re-decides (ruling
                # T15b): a 20000-gold buy is thousands of wins, and a plan
                # committed to all of them would not see the objective move.
                break
            if action.is_applicable(sim, game_data):
                sim = action.apply(sim, game_data)
        if legs:
            return _finish(legs, state, game_data, declined)
    return _decline(declined, "satisfied")


def _open_door(door: Door, state: WorldState, game_data: GameData, actions: list[Action],
               ctx: SelectionContext, declined: list[str] | None, subtasks: bool,
               grinding: frozenset[str], policy: Policy) -> list[Action] | None:
    """The legs that open a key door the walk routed through (Task 14e,
    `ObtainModel.walk_graph`): the walk's own plan for the door's first
    shortfall (a key, or the fee's gold), held on top of the bag.
    The plan stops there, as at a skill gate: the next cycle walks again from
    the bag it left, and once the shortfall is held the content is reached
    and the region bridge crosses the door (`_bridge_regions`)."""
    code, units = door[0]
    bag = state.gold if code == GOLD_CODE else state.inventory.get(code, 0)
    return _walk_plan(GatherMaterialsGoal(code, {code: bag + units}, fight_gold=policy.fight_gold),
                      state, game_data, actions, ctx, declined, subtasks, grinding, policy)


def _one_trip(item: str, qty: int, answer: WalkAnswer, state: WorldState,
              game_data: GameData) -> int:
    """`qty`, less what the walk's buys of `item` from a vendor paid in an ITEM
    carry beyond one bag-load (`currency_buy_batch_pure`).

    The walk sizes a buy to the whole deficit, and its pay stack has to be in
    the bag at the counter, so a deficit past one bag-load is a plan no
    deposit can make fit. Live 2026-10-12: `GatherMaterials(lich_race_medal,
    x5)` walked `Withdraw(event_ticket x400)` -> `NpcBuy(lich_race_medal x4)`,
    peak 493 in a 166 bag, and every character declined the trophy
    `bag_overflow` ~1,000 times in 12 h. Walking the smaller target is the
    proved walk on a smaller goal: one trip, and the next cycle walks the rest
    from the bag it left. A buy not even one unit of which fits is left whole,
    for the `bag_overflow` decline to name."""
    excess = 0
    for leg in answer.plan:
        if not isinstance(leg, Act) or leg.item != item:
            continue
        route = answer.graph.sources[item][leg.route]
        if route.kind is not SourceKind.BUY:
            continue
        price, currency = next((p, c) for npc, p, c in game_data.npc_purchases(item)
                               if npc == route.via)
        if currency == GOLD_CODE:
            continue
        batch = currency_buy_batch_pure(leg.amount, price, state.inventory_max)
        if 0 < batch < leg.amount:
            excess += leg.amount - batch
    return qty - excess


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
                state: WorldState, game_data: GameData, bank_accessible: bool,
                grey_ok: Callable[[str], bool], gold_monster: str | None = None) -> Action | None:
    """The concrete action a walk step names, sized to it: the goal's own
    sized actions first, then the whole pool, and a withdraw built at the bank
    tile when neither has one. None for a route no action serves yet (GE fill,
    sale, task reward: 2c-2d constructs them).

    A fight-gold step is ONE win against `gold_monster`, the monster the
    piece's price fought (plan B Task 15), whichever monster the walk's own
    route names: the walk only proved fights can pay the gold. Its plan-cache
    target is that win's mean gold in the pocket (`gold_target`)."""
    candidates = (*relevant, *pool)
    assert isinstance(step, Act), "an open gate is expanded by `_walk_plan`"
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
        # One resource can grow in several regions, one action each. The one in
        # the character's own region needs no crossing; another region's is the
        # fallback (`_bridge_regions` crosses to it). Census 2026-10-08:
        # palm_tree grows on the mainland AND in `overworld:-4,17`, the first
        # match was the latter, and no modelled edge leads back to the workshop.
        here = game_data.state_region(state)
        gathers = [a for a in candidates if isinstance(a, GatherAction)
                   and a.resource_code == route.via and a.drop_item(game_data) == step.item]
        gather = next((a for a in gathers if a.travel_region == here), next(iter(gathers), None))
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
    if route.kind is SourceKind.GE_FILL:
        # A standing sell order filled (ruling T14a-C, only under a piece's
        # policy): the order the route names, at its own price, while it still
        # stands as the book's best.
        order = game_data.ge_best_sell_order(step.item)
        location = game_data.grand_exchange_location()
        if order is None or order[0] != route.via or location is None:
            return None
        return GeFillSellOrderAction(order_id=route.via, item_code=step.item, price=order[1],
                                     quantity=step.amount, ge_location=location)
    if route.kind is SourceKind.GOLD_DROP:
        # The goal's own actions come last so their fight wins for the monster,
        # as in the DROP arm below.
        fights = {a.monster_code: a for a in (*pool, *relevant)
                  if isinstance(a, FightAction) and not a.participants}
        fight = fights.get(gold_monster) if gold_monster is not None else None
        if fight is None:
            return None
        # A grey monster may pay the gold (`PIECE_POLICY` priced it); the
        # plain fight fails the zero-xp gate, so it is the drop_farm variant,
        # as `select_drop_fight` hunts a grey dropper.
        grey = game_data.xp_per_kill(fight.monster_code, state.level) <= 0
        return dataclasses.replace(fight, drop_farm=fight.drop_farm or grey,
                                   gold_target=win_gold(fight.monster_code, game_data))
    if route.kind is SourceKind.DROP:
        # Which dropper to fight is the proved selection's (expected kills,
        # then distance; the grey drop_farm variant): the route only proved a
        # fight can serve the item.
        # The goal's own actions come last so their fight (possibly the
        # synthesized drop_farm variant the static pool lacks) wins per monster.
        fight = select_drop_fight(step.item, [*pool, *relevant], state, game_data,
                                  allow_grey=grey_ok(step.item))
        return None if fight is None else dataclasses.replace(fight, drop_target=(step.item, step.amount))
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

    The plan may stop short of the equip, when a later leg has no concrete
    action yet; the next cycle decomposes the rest.

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
    legs = decompose(obtain, state, game_data, actions, ctx, declined, subtasks=False,
                     policy=POTION_POLICY, outermost=False)
    if legs is None:
        return None
    # The legs can be a PREFIX of the batch (a later leg with no action): the
    # equip joins the plan only when they land the whole batch.
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

    `mapped` is always non-empty at every call site (a non-empty walk or
    `craft_plan_full` plan)."""
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
