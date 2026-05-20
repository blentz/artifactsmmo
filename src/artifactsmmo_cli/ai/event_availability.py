"""Decide whether an event-gated NPC can be traded with right now."""

from datetime import datetime

from artifactsmmo_cli.ai.game_data import GameData

EVENT_TRAVEL_SECONDS_PER_TILE = 5.0
"""Rough seconds per map tile of travel, used to check the event window won't
close before the character can walk to the merchant."""

EVENT_ARRIVAL_MARGIN_SECONDS = 10.0
"""Safety margin added to estimated travel time before committing to the trip."""


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
    """
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
    travel_seconds = distance * EVENT_TRAVEL_SECONDS_PER_TILE
    remaining = (expiration - now).total_seconds()
    return remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS
