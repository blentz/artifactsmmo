"""Integration / liveness proof: the proven choose_venue core (via the
liquidation_venue adapter) is genuinely INVOKED on a live planning path.

DiscardOverstockGoal.relevant_actions is the surplus-liquidation goal. These tests
demonstrate that when a surplus item has a standing GE buy order priced ABOVE the
NPC sell-back AND able to absorb the whole excess, the goal emits a real
GeFillBuyOrderAction (choose_venue == GE). When no order stands, or it pays no more,
only the NpcSell path is offered (Venue.NPC) — the behavior is unchanged. This is
the live caller that makes formal/Formal/LiquidationVenue.lean's proof non-inert.
"""

from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state


def _gd(*, npc_buy=None, ge_order=None, ge_loc=(5, 5)) -> GameData:
    """GameData where 'iron_ore' has no recipe use (so any held qty is overstock)."""
    gd = GameData()
    gd._item_stats = {"iron_ore": ItemStats(code="iron_ore", level=1, type_="resource")}
    gd._crafting_recipes = {}
    if npc_buy is not None:
        npc_code, price = npc_buy
        gd._npc_sell_prices = {npc_code: {"iron_ore": price}}
        gd._npc_locations = {npc_code: (1, 1)}
    if ge_order is not None:
        gd._ge_buy_orders = {"iron_ore": ge_order}
    gd._grand_exchange_location = ge_loc
    return gd


def test_surplus_with_better_ge_buy_order_emits_ge_fill_action():
    """LIVENESS: a fillable GE buy order priced above NPC sell-back makes the
    surplus-liquidation goal emit a GeFillBuyOrderAction for the choose_venue==GE
    winner — the proven core is genuinely invoked on a live path."""
    # NPC pays 3; standing GE buy order pays 9 and can absorb all 10 → GE wins.
    gd = _gd(npc_buy=("merchant", 3), ge_order=("ord-7", 9, 10))
    # inventory_max=11 keeps the bag under genuine space pressure (10/11 >=
    # the 0.85 discard watermark) so the space-driven overstock fires and the
    # GE-liquidation path is exercised (spec 2026-06-07).
    state = make_state(inventory={"iron_ore": 10}, inventory_max=11)
    goal = DiscardOverstockGoal(gd, ctx=NO_PROFILE_CONTEXT)

    emitted = goal.relevant_actions([], state, gd)

    ge_fills = [a for a in emitted if isinstance(a, GeFillBuyOrderAction)]
    assert len(ge_fills) == 1, f"expected one GeFillBuyOrderAction, got {emitted}"
    fill = ge_fills[0]
    assert fill.order_id == "ord-7"
    assert fill.item_code == "iron_ore"
    assert fill.price == 9
    assert fill.quantity == 10
    assert fill.ge_location == (5, 5)
    # The applied state realizes the standing order's gold (price * qty).
    assert fill.apply(state, gd).gold == state.gold + 9 * 10
    # The NpcSell alternative is still offered so the least-cost planner chooses.
    assert any(isinstance(a, NpcSellAction) for a in emitted)


def test_surplus_without_ge_order_emits_only_npc_sell():
    """No standing GE buy order → liquidation_venue → NPC; no GeFill emitted."""
    gd = _gd(npc_buy=("merchant", 3), ge_order=None)
    # inventory_max=11 keeps the bag under genuine space pressure (10/11 >=
    # the 0.85 discard watermark) so the space-driven overstock fires and the
    # GE-liquidation path is exercised (spec 2026-06-07).
    state = make_state(inventory={"iron_ore": 10}, inventory_max=11)
    goal = DiscardOverstockGoal(gd, ctx=NO_PROFILE_CONTEXT)

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillBuyOrderAction) for a in emitted)
    assert any(isinstance(a, NpcSellAction) for a in emitted)


def test_surplus_with_ge_order_priced_below_npc_emits_only_npc_sell():
    """Standing order pays LESS than NPC sell-back → choose_venue → NPC; no GeFill."""
    gd = _gd(npc_buy=("merchant", 12), ge_order=("ord-7", 9, 10))
    # inventory_max=11 keeps the bag under genuine space pressure (10/11 >=
    # the 0.85 discard watermark) so the space-driven overstock fires and the
    # GE-liquidation path is exercised (spec 2026-06-07).
    state = make_state(inventory={"iron_ore": 10}, inventory_max=11)
    goal = DiscardOverstockGoal(gd, ctx=NO_PROFILE_CONTEXT)

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillBuyOrderAction) for a in emitted)
    assert any(isinstance(a, NpcSellAction) for a in emitted)


def test_surplus_with_ge_order_too_small_emits_only_npc_sell():
    """Order pays more per unit but cannot absorb the whole excess in one fill →
    liquidation_venue → NPC (the anti-surrogate quantity guard)."""
    gd = _gd(npc_buy=("merchant", 3), ge_order=("ord-7", 9, 4))
    # inventory_max=11 keeps the bag under genuine space pressure (10/11 >=
    # the 0.85 discard watermark) so the space-driven overstock fires and the
    # GE-liquidation path is exercised (spec 2026-06-07).
    state = make_state(inventory={"iron_ore": 10}, inventory_max=11)
    goal = DiscardOverstockGoal(gd, ctx=NO_PROFILE_CONTEXT)

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillBuyOrderAction) for a in emitted)
    assert any(isinstance(a, NpcSellAction) for a in emitted)


def test_surplus_no_npc_buyer_but_ge_order_emits_ge_fill_not_delete():
    """No NPC buys the item, but a standing GE order does → GeFill replaces the
    Delete fallback (the surplus is liquidated for gold, not destroyed)."""
    from artifactsmmo_cli.ai.actions.delete import DeleteItemAction

    gd = _gd(npc_buy=None, ge_order=("ord-7", 4, 10))
    # inventory_max=11 keeps the bag under genuine space pressure (10/11 >=
    # the 0.85 discard watermark) so the space-driven overstock fires and the
    # GE-liquidation path is exercised (spec 2026-06-07).
    state = make_state(inventory={"iron_ore": 10}, inventory_max=11)
    goal = DiscardOverstockGoal(gd, ctx=NO_PROFILE_CONTEXT)

    emitted = goal.relevant_actions([], state, gd)

    assert any(isinstance(a, GeFillBuyOrderAction) for a in emitted)
    assert not any(isinstance(a, DeleteItemAction) for a in emitted)
