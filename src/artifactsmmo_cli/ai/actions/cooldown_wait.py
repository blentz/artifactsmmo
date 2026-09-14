"""`wait_out_cooldown`: block until the cooldown the server just set expires."""

import time
from datetime import datetime, timezone

from artifactsmmo_cli.ai.world_state import WorldState


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

    The extra 0.1s absorbs clock skew between this host and the server; without
    it a wait that lands exactly on the expiry still races the 499.
    """
    if state.cooldown_expires is None:
        return
    remaining = (state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds()
    if remaining > 0:
        time.sleep(remaining + 0.1)
