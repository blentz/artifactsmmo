"""Decide whether an event-gated NPC can be traded with right now."""

from datetime import datetime

from artifactsmmo_cli.ai.game_data import GameData

EVENT_TRAVEL_SECONDS_PER_TILE = 5.0
"""Rough seconds per map tile of travel, used to check the event window won't
close before the character can walk to the merchant."""

EVENT_ARRIVAL_MARGIN_SECONDS = 10.0
"""Safety margin added to estimated travel time before committing to the trip."""

PLAN_SECONDS_PER_COST_UNIT = 10.0
"""The planner's cost unit in seconds. Established by `rest_cost_pure`: a full-HP
rest is 100 real seconds and costs 10.0, so one cost unit is 10s. That conversion
is what lets an event window be compared against a PLAN, not just against travel."""


def event_window_sufficient_pure(remaining_seconds: float, distance: int,
                                 plan_cost: float) -> bool:
    """True when the event stays up long enough to travel there AND finish the
    plan, with the arrival margin to spare.

    Travel alone was the original question (`event_npc_tradeable`), and it is
    only half: reaching the spawn tile is worthless if the window shuts partway
    through the ten actions planned for it. `plan_cost` is in planner cost units;
    a non-positive value degrades this to the pure travel question, which is the
    pre-P2 behaviour and the right answer for a caller that has no plan yet.
    """
    if remaining_seconds <= 0:
        return False
    needed = distance * EVENT_TRAVEL_SECONDS_PER_TILE + EVENT_ARRIVAL_MARGIN_SECONDS
    if plan_cost > 0:
        needed += plan_cost * PLAN_SECONDS_PER_COST_UNIT
    return remaining_seconds > needed


def event_npc_tradeable(
    npc_code: str,
    game_data: GameData,
    *,
    x: int,
    y: int,
    active_events: dict[str, datetime],
    now: datetime,
) -> bool:
    """True if this NPC is tradeable from (x, y) right now.

    Non-event NPCs are always tradeable (returns True) — the caller's other
    checks (location known, price, gold/inventory) still apply. Event NPCs are
    tradeable only when their event is active and won't expire before the
    character can reach the spawn tile.

    `now` must be timezone-aware (event expirations from the API are), otherwise
    the expiry subtraction raises an opaque TypeError deep in the planner.
    """
    if now.tzinfo is None:
        raise ValueError(f"event_npc_tradeable: 'now' must be timezone-aware, got {now!r}")
    event_code = game_data.npc_event_code(npc_code)
    if event_code is None:
        return True  # not an event NPC; nothing to gate on here
    expiration = active_events.get(event_code)
    if expiration is None:
        return False  # event not active
    spawn = game_data.npc_location(npc_code)
    if spawn is None:
        return False
    distance = abs(spawn[0] - x) + abs(spawn[1] - y)
    # Delegates to the shared window predicate so NPC and non-NPC event content
    # cannot drift apart. plan_cost=0 keeps the NPC question exactly as it was --
    # a trade is one action at the tile, so travel is the whole cost.
    return event_window_sufficient_pure(
        remaining_seconds=(expiration - now).total_seconds(),
        distance=distance, plan_cost=0.0)
