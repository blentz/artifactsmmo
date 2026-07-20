"""Reject a plan whose event-only content will expire before the plan finishes.

The P2 gap (docs/PLAN_events_raids_epic.md): `WorldState.active_events` has always
carried expirations, but nothing outside `event_availability` read them, so the
planner would commit a long chain to content with ninety seconds left on it.

Two judgements live here, each with a concrete witness in the committed bundle:

EVENT-GATED = has event tiles AND NO static tile. A monster that spawns both ways
(`solar_desert_scorpion`) is deliberately NOT gated -- its plan can be finished
after the window closes, so a short window must not suppress it. Using
`is_event_monster` alone would have wrongly gated it, since that predicate only
asks whether the content appears in the event registry.

ETA = summed action costs at 10 seconds per cost unit. This is an APPROXIMATION:
costs are evaluated against the STARTING state, and the history-dependent ones
(Fight, Gather, Move) reflect learned medians rather than this particular
execution. It is a guard against the obviously-impossible, not a scheduler --
which is the right ambition, because the alternative in place until now was no
check at all.
"""

from datetime import datetime

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.event_availability import event_window_sufficient_pure
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def _event_only_target(action: Action, game_data: GameData) -> str | None:
    """The content code this action depends on an OPEN event for, else None.

    None covers both "not event content at all" and "event content that also has
    a permanent spawn" -- neither is window-gated.
    """
    if isinstance(action, FightAction):
        code = action.monster_code
        if not game_data.world.event_monster_locations.get(code):
            return None
        return None if game_data.monsters.monster_locations(code) else code
    if isinstance(action, GatherAction):
        code = action.resource_code
        if not game_data.world.event_resource_locations.get(code):
            return None
        return None if game_data.recipes_catalog.resource_locations(code) else code
    return None


def plan_fits_event_window(plan: list[Action], state: WorldState,
                           game_data: GameData, now: datetime) -> bool:
    """True unless the plan needs event-only content whose window is too short.

    `now` must be timezone-aware (API expirations are), matching
    `event_npc_tradeable` -- a naive value would otherwise raise an opaque
    TypeError deep in the planner.
    """
    if now.tzinfo is None:
        raise ValueError(f"plan_fits_event_window: 'now' must be timezone-aware, got {now!r}")
    gated = {code for code in (_event_only_target(a, game_data) for a in plan)
             if code is not None}
    if not gated:
        return True
    plan_cost = sum(a.cost(state, game_data) for a in plan)
    for content_code in sorted(gated):          # sorted: deterministic verdict order
        event_code = game_data.world.event_code_of_content.get(content_code)
        expiration = state.active_events.get(event_code) if event_code else None
        if expiration is None:
            return False                        # event-only content, no open window
        tiles = game_data.monster_locations(content_code) or \
            game_data.resource_locations(content_code)
        if not tiles:
            return False
        distance = min(abs(tx - state.x) + abs(ty - state.y) for tx, ty in tiles)
        if not event_window_sufficient_pure(
                remaining_seconds=(expiration - now).total_seconds(),
                distance=distance, plan_cost=plan_cost):
            return False
    return True
