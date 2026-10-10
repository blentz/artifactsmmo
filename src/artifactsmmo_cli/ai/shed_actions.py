"""The venue for shedding one item's licensed copies: a GE fill, a GE sell post,
an NPC sale, else the proved `disposal_route` (recycle > deposit > delete).

One routing, two callers: `DiscardOverstockGoal` sheds bag overstock through it,
and `DrainBankJunkGoal` sheds the junk it withdraws through it in the same plan
(Phase 2d; before, the drained junk waited for bag pressure, and the deposit
guard banked it again first).
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.actions.ge_post_sell import GePostSellOrderAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.disposal_route import overstock_disposal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_order_config import GE_FILL_MAX_QUANTITY
from artifactsmmo_cli.ai.ge_post_pricing import sell_post_price
from artifactsmmo_cli.ai.liquidation_venue import Venue, choose_venue3, liquidation_venue
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def shed_actions(code: str, excess_qty: int, state: WorldState, game_data: GameData,
                 ctx: SelectionContext, bank_accessible: bool) -> list[Action]:
    """The batch actions that could shed `excess_qty` of `code` from the bag:
    Sell wins when any NPC buys (gold > zero; the highest-paying NPC), a GE
    fill or post when the book beats it, and with no executable sale the
    proved `disposal_route`: recycle > deposit > delete."""
    result: list[Action] = []
    buyers = game_data.npcs_buying_item(code)
    npc_loc: tuple[int, int] | None = None
    npc_code: str | None = None
    npc_pay = 0
    if buyers:
        # npcs_buying_item sorted highest-first
        npc_code, npc_pay = buyers[0]
        npc_loc = game_data.npc_location(npc_code)
    # Immediate-fill GE liquidation: when a standing GE buy order pays
    # strictly more than the best NPC sell-back AND can absorb the whole
    # excess in one fill, offer a GeFillBuyOrder. liquidation_venue → GE
    # (gated by choose_venue, proved in formal/Formal/LiquidationVenue.lean)
    # is the decision; the least-cost / higher-proceeds planner then picks
    # GE vs NPC. We only fill an EXISTING order — never post a new one.
    ge_loc = game_data.grand_exchange_location()
    order = game_data.ge_best_buy_order(code)
    ge_action_available = False
    if ge_loc is not None and order is not None and \
            liquidation_venue(code, excess_qty, state, game_data) is Venue.GE:
        order_id, price, _order_qty = order
        # One fill moves at most GE_FILL_MAX_QUANTITY units (server payload
        # bound). A holding above the cap is liquidated one capped fill per
        # cycle; emitting the whole excess instead emits a step the server
        # refuses identically every cycle, which is a livelock, not a slow
        # path (live R2D2 2026-09-09: 104 algae, HTTP 422, whole run).
        result.append(GeFillBuyOrderAction(
            order_id=order_id, item_code=code, price=price,
            quantity=min(excess_qty, GE_FILL_MAX_QUANTITY), ge_location=ge_loc,
        ))
        ge_action_available = True

    # Post our own SELL order when no standing buy order is worth filling but
    # the book gives an anchor and the post price beats the NPC floor.
    # choose_venue3 -> GE_POST (proved fail-closed in GePostPricing.lean).
    sell_anchor = game_data.ge_best_sell_order(code)
    best_sell = sell_anchor[1] if sell_anchor is not None else None
    fill_proceeds = order[1] if (order is not None and order[2] >= excess_qty) else None
    post_price = sell_post_price(best_sell, npc_sellback=npc_pay, margin=1)
    if ge_loc is not None and post_price is not None and \
            choose_venue3(npc_pay, fill_proceeds, post_price) is Venue.GE_POST:
        # Batch to the standing sell order's size, capped at the excess.
        batch = min(excess_qty, sell_anchor[2]) if sell_anchor is not None else excess_qty
        result.append(GePostSellOrderAction(
            item_code=code, quantity=batch, price=post_price, ge_location=ge_loc,
        ))

    sell_action: NpcSellAction | None = None
    if npc_code is not None and npc_loc is not None:
        sell_action = NpcSellAction(
            npc_code=npc_code, item_code=code, quantity=excess_qty,
            npc_location=npc_loc, travel_region=game_data.npc_region(npc_code),
        )
        result.append(sell_action)
    # Disposal fallback: whenever there is no fillable GE order AND no
    # EXECUTABLE sell — i.e. no sell action at all, OR the sell action
    # is not currently applicable (the dormant event-merchant case,
    # trace 2026-06-24: sap's only buyer is the `timber_merchant` event
    # NPC whose spawn window is closed) — route the item through the
    # proved disposal_route instead of a bare Delete (trace 2026-07-04:
    # copper_helmet x33 recyclable gear destroyed): an applicable
    # Recycle recovers materials; else a bankable item with future
    # value (recipe demand or equippable) deposits; else Delete frees
    # the slot for a worthless-NOW item. Every route is executable this
    # cycle, so overstock still always clears (no Withdraw↔Deposit
    # bag-full livelock regression).
    if not ge_action_available and (
        sell_action is None
        or not sell_action.is_applicable(state, game_data)
    ):
        result.append(overstock_disposal(
            code, excess_qty, state, game_data, bank_accessible,
            ctx))
    return result
