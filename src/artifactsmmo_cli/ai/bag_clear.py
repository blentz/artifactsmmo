"""The full-bag clear (Task 13e, USER 2026-10-25, binding): "free up all in-use
inventory slots that aren't related to the current plan, then retry the plan
once the full inventory state is cleared."

Live R2D2 2026-10-22T19:02Z on: 20 of 20 SLOTS used (119/172 by quantity), the
HP_CRITICAL guard won the ladder, and RestoreHP's plan opened with
`Craft(cooked_porkchop×1)` — a NEW stack with no slot to land in. The server
answered HTTP 497 on 2,772 consecutive cycles. DEPOSIT_FULL fired on every one
of them and never ran: it sits BELOW the HP guard, and the HP guard always
planned, because a craft is deliberately not slot-gated (gating it made the bot
avoid the smelt and sit full of junk forever, 2026-07-11). A 497 is a STATE
failure (`failure_recovery_core`), answered by a refresh, so the same state drew
the same plan.

The answer lives at the arbiter's ONE planning seam, after either producer (the
fast path or A*) has answered: a plan that needs a slot it does not have — or
whose previous action the server refused with 497 — is prefixed with a clear of
every stack the plan does not use, and the goal is re-planned on the cleared bag.

Every authority here is an existing one:
  * slot room — `inventory_room.has_room`, over the plan's own modelled steps;
  * what is related — the plan's inputs and outputs, the chosen root's closure
    (`strategy_driver.chosen_root_closure`), the keep authority
    (`inventory_keep.keep_in_bag`), the equipped set;
  * the deposit — the pool's `DepositAllAction` (one request per batch,
    `DEPOSIT_SECONDS_PER_CODE` a code), its keep context widened to the related
    stacks so it banks exactly the unrelated ones;
  * a code the bank cannot take — the junk policy (`disposal_route`), only for
    a stack the keep authority licenses whole (`destroyable`);
  * the route per stack and the verdict — `bag_clear_core` (proved in
    formal/Formal/BagClear.lean).
"""

import dataclasses
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.bag_clear_core import ClearRoute, clear_route, slots_freed
from artifactsmmo_cli.ai.disposal_route import overstock_disposal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable, keep_in_bag
from artifactsmmo_cli.ai.inventory_room import has_room
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

BAG_FULL_OUTCOME = "error:HTTP_497"
"""The cycle outcome of a server refusal for want of bag room ("The
character's inventory is full"). The server's word overrides the model."""


SLOT_DECLINES = ("first_leg_inapplicable:", "bag_overflow:")
"""The fast path's declines a full bag can cause (`craft_plan_gen._finish`,
`craft_plan_gen.decompose`): a goal answered by one of them may be a goal the
clear unblocks (`StrategyArbiter._slot_blocked_plan` asks)."""


@dataclass(frozen=True)
class ClearPlan:
    """The clear: the actions that move the unrelated stacks out (one
    DepositAll, then one junk-policy action per bank-refused stack), and the
    slots they free (`slots_freed` over every held stack's route). Empty
    actions and `freed == 0` are the same fact: `bag_full_all_related`."""

    actions: tuple[Action, ...]
    freed: int


def roomy(state: WorldState) -> WorldState:
    """`state` with the room of an emptied bag: the quantity and slot caps
    raised by what the bag holds. The plan a goal takes here is the plan it
    would take once its bag were cleared, so its legs name what the goal uses
    (a goal the full bag stops from planning at all)."""
    return dataclasses.replace(
        state, inventory_max=state.inventory_max + state.inventory_used,
        inventory_slots_max=state.inventory_slots_max + state.inventory_slots_used)


NEEDS = "needs"
FREES = "frees"


def _room_events(plan: Sequence[Action], state: WorldState,
                 game_data: GameData) -> Iterator[str]:
    """The plan's slot events, step by step over its own modelled states:
    `NEEDS` where a step needs room the bag does not have, `FREES` where a
    step leaves the bag on fewer slots than it STARTED on (a craft whose
    output is eaten later frees nothing: it only returns the slot it took). One room authority
    (`inventory_room.has_room`) for both shapes of need:
      * a step that is not slot-gated (a craft) whose modelled result does not
        fit, net of what the step frees;
      * a slot-gated step (withdraw, equip, gather of a new code) that its own
        room check refuses here but admits with an emptied bag (`roomy`).

    The walk stops at the first fight: a fight's modelled loot is one of every
    drop (optimistic, `FightAction.apply`), so the states past it are not a slot
    fact, and the fight's own room is `fight_room_license.refused_fight`'s. It
    stops at a step refused for any other reason, too: the plan is not this
    bag's to judge past it."""
    current = state
    for action in plan:
        if isinstance(action, FightAction):
            return
        if not action.is_applicable(current, game_data):
            if action.is_applicable(roomy(current), game_data):
                yield NEEDS
            return
        nxt = action.apply(current, game_data)
        if not has_room(nxt.inventory_slots_used - current.inventory_slots_used,
                        nxt.inventory_used - current.inventory_used,
                        current.inventory_slots_free, current.inventory_free):
            yield NEEDS  # every reader stops at the first NEEDS
        elif nxt.inventory_slots_used < state.inventory_slots_used:
            yield FREES
        current = nxt


def needs_slot(plan: Sequence[Action], state: WorldState, game_data: GameData) -> bool:
    """Whether a step of `plan` needs room the bag does not have (`_room_events`)."""
    return NEEDS in _room_events(plan, state, game_data)


def frees_first(plan: Sequence[Action], state: WorldState, game_data: GameData) -> bool:
    """Whether `plan`'s own walk frees a slot before any step needs one: the
    plan IS the relief (a deposit, a shed, a recycle), so a server 497 calls
    for it, not for a clear in front of it (Task 13e re-review I2)."""
    return next(iter(_room_events(plan, state, game_data)), None) == FREES


def plan_codes(plan: Sequence[Action], state: WorldState, game_data: GameData) -> frozenset[str]:
    """Every code a step of `plan` consumes or produces: the codes whose held
    quantity a modelled step changes. Walked with an emptied bag's room
    (`roomy`), where every step of a plan the bag blocks still applies."""
    codes: set[str] = set()
    current = roomy(state)
    for action in plan:
        nxt = action.apply(current, game_data)
        codes |= {code for code in current.inventory.keys() | nxt.inventory.keys()
                  if current.inventory.get(code, 0) != nxt.inventory.get(code, 0)}
        current = nxt
    return frozenset(codes)


def related_codes(plan: Sequence[Action], state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> frozenset[str]:
    """The codes the clear must not touch: the plan's inputs and outputs, the
    chosen root's requirement closure (`ctx.root_closure`, bound by the
    arbiter), every held code the keep authority keeps a copy of in the bag,
    and the equipped codes."""
    kept = {code for code, qty in state.inventory.items()
            if qty > 0 and keep_in_bag(code, state, game_data, ctx) > 0}
    return (plan_codes(plan, state, game_data) | ctx.root_closure | frozenset(kept)
            | frozenset(code for code in state.equipment.values() if code is not None))


def _clear_deposit(state: WorldState, actions: Sequence[Action], ctx: SelectionContext,
                   related: frozenset[str]) -> DepositAllAction | None:
    """The pool's DepositAll with its keep context widened so every related
    held stack stays whole (`GOAL_MATERIALS` at the held quantity); None when
    the pool has none (no bank)."""
    deposit = next((a for a in actions if isinstance(a, DepositAllAction)), None)
    if deposit is None:
        return None
    profile = dict(ctx.step_profile)
    for code, qty in state.inventory.items():
        if code in related:
            profile[code] = max(profile.get(code, 0), qty)
    return dataclasses.replace(deposit, ctx=dataclasses.replace(ctx, step_profile=profile))


def _whole_disposal(code: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext) -> Action | None:
    """The junk policy's action for the WHOLE held stack of `code`, when the
    keep authority licenses destroying all of it and the action empties the
    stack; None otherwise (a partial disposal frees no slot)."""
    held = state.inventory.get(code, 0)
    if destroyable(code, state, game_data, ctx) < held:
        return None
    # Executable this cycle by `overstock_disposal`'s own contract; a RECYCLE
    # it sized below the stack (the minted materials did not fit) leaves copies.
    action = overstock_disposal(code, held, state, game_data, ctx.bank_accessible, ctx)
    if code in action.apply(state, game_data).inventory:
        return None
    return action


def clear_actions(state: WorldState, game_data: GameData, actions: Sequence[Action],
                  ctx: SelectionContext, related: frozenset[str]) -> ClearPlan:
    """The clear that moves every unrelated stack out of the bag at once: one
    DepositAll for the stacks the bank takes, then the junk policy for each
    stack it refuses. No actions and `freed == 0` when no stack can leave
    (`bag_full_all_related`)."""
    deposit = _clear_deposit(state, actions, ctx, related)
    banked = state
    if deposit is not None and deposit.is_applicable(state, game_data):
        banked = deposit.apply(state, game_data)
    held = [code for code, qty in state.inventory.items() if qty > 0]
    # A stack the deposit removes and the plan does not use. (A related stack it
    # removes is the deposit's last-resort arm, which runs only when nothing is
    # bankable — this clear then has nothing to bank, and the deposit is dropped.)
    taken = {code for code in held if code not in related and code not in banked.inventory}
    current = banked if taken else state
    routes: list[ClearRoute] = []
    disposals: list[Action] = []
    for code in held:
        disposal = (None if code in related or code in taken
                    else _whole_disposal(code, current, game_data, ctx))
        route = clear_route(code in related, code in taken, disposal is not None)
        routes.append(route)
        if route is ClearRoute.DISPOSE:
            assert disposal is not None  # clear_route: DISPOSE => disposable
            disposals.append(disposal)
            current = disposal.apply(current, game_data)
    head: list[Action] = []
    if taken:
        assert deposit is not None  # `taken` is read off the deposit's own state
        head = [deposit]
    return ClearPlan(actions=(*head, *disposals), freed=slots_freed(routes))


def cleared_state(clear: Sequence[Action], state: WorldState, game_data: GameData) -> WorldState:
    """The bag after `clear`, the state the goal is re-planned on."""
    current = state
    for action in clear:
        current = action.apply(current, game_data)
    return current
