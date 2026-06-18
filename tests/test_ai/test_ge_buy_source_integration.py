"""Integration / liveness proof: the proven choose_buy_venue core (the DUAL of
choose_venue) is genuinely INVOKED on a live planning path.

GatherMaterials.relevant_actions injects an NpcBuy alternative for a needed item
when buying beats crafting. These tests demonstrate that when, on top of that, a
standing GE SELL order is priced BELOW the NPC buy price AND can supply the whole
needed quantity in one fill, the goal ALSO emits a real GeFillSellOrderAction
(choose_buy_venue == GE) — the cheaper, immediate buy source. When no order stands,
or it costs no less, or it cannot supply the whole quantity, only the NpcBuy path is
offered (BuyVenue.NPC). This is the live caller that makes
formal/Formal/BuySourceVenue.lean's proof non-inert.
"""

from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state

# Local gold-sizing baseline (the removed flat reserve value was 500); these
# liveness tests just need gold comfortably above any reserve floor.
_RESERVE_BASELINE = 500


def _gd(*, npc_price=5, ge_order=None, ge_loc=(7, 7)) -> GameData:
    """GameData where copper_bar is craftable (copper_ore x10) OR bought from 'shop'
    at npc_price (near), so acquisition_method returns BUY when affordable."""
    gd = GameData()
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._npc_stock = {"shop": {"copper_bar": npc_price}}
    gd._npc_locations = {"shop": (1, 0)}
    if ge_order is not None:
        gd._ge_sell_orders = {"copper_bar": ge_order}
    gd._grand_exchange_location = ge_loc
    return gd


def _state():
    return make_state(gold=_RESERVE_BASELINE + 1000, inventory={}, x=0, y=0,
                      skills={"mining": 5})


def test_cheaper_ge_sell_order_emits_ge_fill_action() -> None:
    """LIVENESS: a fillable GE sell order priced below the NPC buy price makes the
    gather goal emit a GeFillSellOrderAction for the choose_buy_venue==GE winner —
    the proven core is genuinely invoked on a live path."""
    # NPC sells at 5; standing GE sell order costs 2 and can supply all 1 → GE wins.
    gd = _gd(npc_price=5, ge_order=("ord-3", 2, 4))
    state = _state()
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})

    emitted = goal.relevant_actions([], state, gd)

    ge_buys = [a for a in emitted if isinstance(a, GeFillSellOrderAction)]
    assert len(ge_buys) == 1, f"expected one GeFillSellOrderAction, got {emitted}"
    buy = ge_buys[0]
    assert buy.order_id == "ord-3"
    assert buy.item_code == "copper_bar"
    assert buy.price == 2
    assert buy.quantity == 1
    assert buy.ge_location == (7, 7)
    # The applied state spends the standing order's gold (price * qty) and mints item.
    applied = buy.apply(state, gd)
    assert applied.gold == state.gold - 2 * 1
    assert applied.inventory.get("copper_bar", 0) == 1
    # The NpcBuy alternative is still offered so the least-cost planner chooses.
    assert any(isinstance(a, NpcBuyAction) for a in emitted)


def test_no_ge_sell_order_emits_only_npc_buy() -> None:
    """No standing GE sell order → buy_source_venue → NPC; no GeFillSell emitted."""
    gd = _gd(npc_price=5, ge_order=None)
    state = _state()
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillSellOrderAction) for a in emitted)
    assert any(isinstance(a, NpcBuyAction) for a in emitted)


def test_ge_sell_order_priced_above_npc_emits_only_npc_buy() -> None:
    """Standing order costs MORE than NPC buy price → choose_buy_venue → NPC."""
    gd = _gd(npc_price=5, ge_order=("ord-3", 9, 4))
    state = _state()
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillSellOrderAction) for a in emitted)
    assert any(isinstance(a, NpcBuyAction) for a in emitted)


def test_ge_sell_order_tie_emits_only_npc_buy() -> None:
    """Order priced EXACTLY at the NPC buy price → NPC (the strict-< guard)."""
    gd = _gd(npc_price=5, ge_order=("ord-3", 5, 4))
    state = _state()
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillSellOrderAction) for a in emitted)
    assert any(isinstance(a, NpcBuyAction) for a in emitted)


def test_ge_sell_order_too_small_emits_only_npc_buy() -> None:
    """Order is cheaper per unit but cannot supply the whole needed qty in one fill →
    buy_source_venue → NPC (the anti-surrogate quantity guard)."""
    gd = _gd(npc_price=5, ge_order=("ord-3", 2, 1))
    state = _state()
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 3})

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillSellOrderAction) for a in emitted)
    assert any(isinstance(a, NpcBuyAction) for a in emitted)


def test_no_npc_seller_emits_no_ge_buy() -> None:
    """When no NPC sells the item the buy branch is skipped entirely (acquisition is
    craft-only), so no GeFillSell is offered even if a cheap GE order stands — the GE
    buy source rides on the same BUY-preferred decision as the NpcBuy injection."""
    gd = GameData()
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 10}}
    gd._npc_stock = {}
    gd._npc_locations = {}
    gd._ge_sell_orders = {"iron_bar": ("ord-9", 1, 10)}
    gd._grand_exchange_location = (7, 7)
    state = _state()
    goal = GatherMaterialsGoal(target_item="iron_bar", needed={"iron_bar": 1})

    emitted = goal.relevant_actions([], state, gd)

    assert not any(isinstance(a, GeFillSellOrderAction) for a in emitted)
    assert not any(isinstance(a, NpcBuyAction) for a in emitted)
