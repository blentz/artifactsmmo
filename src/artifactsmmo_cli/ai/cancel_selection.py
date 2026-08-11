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
    state: WorldState, game_data: GameData, need_gold: int, needed_items: frozenset[str],
    sibling_claims: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Order ids to cancel, in deterministic (open-order) iteration order.

    Three cancel triggers, evaluated per open order:
      * TTL: any order older than `TTL_CYCLES` cycles (staleness backstop).
      * on-need gold: BUY orders while the character is still short of `need_gold`
        (cancelling a buy returns its escrowed `price*qty` gold), until the shortfall
        is covered.
      * on-need item: a SELL order whose `code` is in `needed_items` (the bot needs
        the item it had listed for sale back).

    `sibling_claims` is the set of order ids another character of the same account
    is already cancelling (`CoordinationStore.sibling_order_claims`), and they are
    skipped ENTIRELY — before any trigger is evaluated, so a claimed BUY is not
    credited against `gold_short` either. Its escrow is being freed by the sibling,
    not by us; counting it would make this character stop cancelling a second order
    whose gold it still needs.

    Grand Exchange orders are ACCOUNT-scoped, so all five `play --all` children read
    the same open-order list and age the same order past `TTL_CYCLES` together. The
    losers of that race spend an action-bucket request on HTTP 404 "Order not found"
    (6 of 20 ids contested on the 2026-08-10 run). Empty by default, which is every
    single-character run and every caller that does not coordinate — so the
    pre-coordination behaviour is exactly recovered.

    LIVENESS IS PRESERVED: a claim is TTL-bounded
    (`GE_ORDER_CLAIM_TTL_SECONDS`), so an id hidden by a crashed sibling becomes a
    target again within one TTL. The guarantee weakens from "a stale order is
    cancelled on the next cycle" to "within one claim TTL of it", and never to
    "never" — the cancel-target set still provably shrinks toward empty.

    `game_data` is accepted for signature parity with the other selection helpers and
    to leave room for future venue-aware pruning; the current triggers are decided
    purely from `state` + the passed demand.
    """
    targets: list[str] = []
    gold_short = max(0, need_gold - state.gold)
    for o in state.open_orders:
        if o.id in sibling_claims:
            continue
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
