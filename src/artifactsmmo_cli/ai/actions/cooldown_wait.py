"""`wait_out_cooldown`: block until the cooldown the server just set expires."""

import re
import time
from datetime import datetime, timezone

from artifactsmmo_cli.ai.world_state import WorldState

SKEW_MARGIN_SECONDS = 0.1
"""Slept past every expiry to absorb clock skew between this host and the server."""

LAG_HOLD_SECONDS = 600.0
"""How long a learned server lag stands after the last 499 that taught it."""

MAX_SERVER_LAG_SECONDS = 2.0
"""The most lag a 499 can teach. A larger remainder is a call that skipped its
wait, not a server enforcing late, and must not stretch every wait."""

_REMAINING_RE = re.compile(r"(\d+(?:\.\d+)?) seconds? remaining")

_LAG: dict[str, float] = {"seconds": 0.0, "at": float("-inf")}
"""The server's enforcement lag this process has learned, and the monotonic
instant of the 499 that last raised it. Process state: one process plays one
character, and both wait sites (the loop's and the composite actions') read it."""


def _live_lag(now: float) -> float:
    if now - _LAG["at"] >= LAG_HOLD_SECONDS:
        return 0.0
    return _LAG["seconds"]


def cooldown_margin(now: float) -> float:
    """Seconds to sleep past a returned cooldown expiry: the skew margin plus
    any server lag a recent 499 taught."""
    return SKEW_MARGIN_SECONDS + _live_lag(now)


def note_server_cooldown(message: str, now: float) -> None:
    """Learn from a 499 how late the server is enforcing cooldowns.

    Live 2026-10-13 15:30-16:30Z: 336 of 733 cycles drew HTTP 499 with
    0.35-0.49 s "remaining", though the loop slept the returned expiry + 0.1 s
    (failed and successful requests went out at the same offset, and the
    server clock matched this host's). In episodes the server enforces each
    cooldown ~0.5 s past the expiry it returns. The wait that drew the 499
    already carried the live lag, so the remainder is added to it."""
    match = _REMAINING_RE.search(message)
    if match is None:
        return
    _LAG.update(seconds=min(_live_lag(now) + float(match.group(1)), MAX_SERVER_LAG_SECONDS),
                at=now)


def wait_out_cooldown(state: WorldState) -> None:
    """Block until the cooldown `state` carries has expired.

    THE COMPOSITE-ACTION IDIOM. The player loop sleeps out one cooldown per
    cycle, between actions — so any action that issues a SECOND API call of its
    own must sleep out the first call's cooldown itself, or the second gets
    HTTP 499 and strands the action half-done.

    Three actions live on this and each learned it from a live livelock:
      - `MoveAction`, for every composite that moves then acts (Gather, Fight,
        NpcBuy, TaskTrade).
      - `OptimizeLoadoutAction` 2026-07-05: the equip leg of a swap 499'd, the
        weapon slot sat empty, and the re-arm retried forever (~6 calls/min).
      - `DepositAllAction` 2026-09-13: a 2.07% cooldown-error rate over 1404
        executions, 18x `FightAction`'s, every failure a partial deposit.

    The extra `cooldown_margin` absorbs clock skew between this host and the
    server, and any lag a recent 499 taught; without it a wait that lands
    exactly on the expiry still races the 499.
    """
    if state.cooldown_expires is None:
        return
    remaining = (state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds()
    if remaining > 0:
        time.sleep(remaining + cooldown_margin(time.monotonic()))
