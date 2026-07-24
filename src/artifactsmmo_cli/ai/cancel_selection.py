"""Pure selection of open GE orders to cancel: on-need (free locked capital the bot
needs now) plus TTL (staleness backstop). Underwrites the liveness guarantee that no
posted order's capital is locked forever — every posted order either fills or ages
past `TTL_CYCLES` and is swept, so the cancel-target set a firing GE_CANCEL guard acts
on provably shrinks toward empty.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.open_order import OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


def cancel_targets(
    state: WorldState, game_data: GameData, need_gold: int, needed_items: frozenset[str]
) -> tuple[str, ...]:
    """Order ids to cancel, in deterministic (open-order) iteration order.

    Three cancel triggers, evaluated per open order:
      * TTL: any order older than `TTL_CYCLES` cycles (staleness backstop).
      * on-need gold: BUY orders while the character is still short of `need_gold`
        (cancelling a buy returns its escrowed `price*qty` gold), until the shortfall
        is covered.
      * on-need item: a SELL order whose `code` is in `needed_items` (the bot needs
        the item it had listed for sale back).

    `game_data` is accepted for signature parity with the other selection helpers and
    to leave room for future venue-aware pruning; the current triggers are decided
    purely from `state` + the passed demand.
    """
    targets: list[str] = []
    gold_short = max(0, need_gold - state.gold)
    for o in state.open_orders:
        if o.age > TTL_CYCLES:
            targets.append(o.id)
            continue
        if o.side is OrderSide.BUY and gold_short > 0:
            targets.append(o.id)
            gold_short -= o.price * o.qty
            continue
        if o.side is OrderSide.SELL and o.code in needed_items:
            targets.append(o.id)
    # Deterministic order; dedup preserved via dict.fromkeys insertion order.
    return tuple(dict.fromkeys(targets))
