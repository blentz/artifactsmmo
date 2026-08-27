"""Bid-vs-craft decision: only post a GE buy order for an item when acquiring it
ourselves would cost MORE PLANNER ACTIONS than we are willing to wait for a fill.
A posted bid fills asynchronously, so running a self-craft in parallel is wasted
work — this gate (and the open_orders suppression at the call site) keeps the two
mutually exclusive.

RE-DENOMINATED IN ACTIONS (wave 6, increment 5.4). This module used to carry its
own cost model: `estimate_craft_seconds` summed hand-set per-action constants
(`_FIGHT_SECONDS = 10.0`, `_GATHER_SECONDS = 6.0`, `_CRAFT_SECONDS = 5.0`) over a
recipe closure, and compared the total against a wall-clock horizon. That was a
SECOND cost model, drifting independently of the one every other route uses, and
it compared seconds against a horizon derived by multiplying cycles by an average
cycle length.

It now asks `decisions/route.route_price` — the same funnel the resolution graph
prices with — and compares against a horizon in CYCLES. Both sides of the
comparison are planner actions, so nothing converts and nothing can drift:
`route_price` already walks every route the executor can serve (withdraw,
recycle, craft, gather, buy, GE fill, drop), which is strictly more than the
closure walk this replaced could see.

THE UNIT MATTERS MORE THAN THE NUMBER HERE. Mixing seconds into an action count
is the confusion that has produced four separate bugs in this project
(`mats_missing` as cost, `DEFAULT_FIGHT_CYCLES` as cycles, `cycles_to_fifty` as
whole-loop cycles, `cheapest_path_to_level` in seconds), and it is why
`stat_projection_completeness` records `haste` as a PERMANENT exclusion.
"""

from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.world_state import WorldState


def should_bid(item: str, qty: int, bid_horizon_actions: int,
               state: WorldState, game_data: GameData,
               ctx: SelectionContext,
               history: LearningStore | None = None) -> bool:
    """Bid only when acquiring `qty` of `item` ourselves costs MORE planner
    actions than we are willing to wait for a fill.

    Both sides are actions: `route_price` returns them, `bid_horizon_actions` is
    a cycle count, and a cycle IS an action. A live buy-anchor's existence stays
    the caller's job (`buy_post_price`).

    An UNOBTAINABLE item prices at `UNOBTAINABLE_PER_UNIT`, which is far above
    any horizon, so it bids — and that is right: something we cannot route to at
    all is exactly what a standing order is for."""
    return route_price(ObtainItem(item, qty), state, game_data, ctx,
                       history) > bid_horizon_actions
