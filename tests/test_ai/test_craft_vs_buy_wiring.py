"""GatherMaterials.relevant_actions injects NpcBuyAction for a needed item that is
NPC-sold, affordable above the reserve, and cheaper to buy than craft; leaves
craft-only / unaffordable / pricier items alone.

Also covers the fail-open branches in acquisition_method and the relevant_actions
loop: no-seller skip, non-BUY skip.
"""

from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE, Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd_buyable() -> GameData:
    gd = GameData()
    # copper_bar: craftable (copper_ore x10) OR bought from shop_npc at 5g, near.
    # _npc_stock: what the NPC sells TO the player (player's buy price).
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._npc_stock = {"shop": {"copper_bar": 5}}
    gd._npc_locations = {"shop": (1, 0)}
    return gd


def test_acquisition_method_buys_cheap_affordable() -> None:
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0)
    # 1 copper_bar: craft ~10 ore gathers; buy ~2 cooldowns at 5g, affordable -> BUY
    assert acquisition_method("copper_bar", 1, state, gd, GOLD_RESERVE) == Method.BUY


def test_acquisition_method_crafts_when_unaffordable() -> None:
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE - 1, inventory={}, x=0, y=0)
    assert acquisition_method("copper_bar", 1, state, gd, GOLD_RESERVE) == Method.CRAFT


def test_acquisition_method_crafts_when_no_seller() -> None:
    """Fail-open: no NPC sells the item -> CRAFT."""
    gd = GameData()
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 10}}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0)
    assert acquisition_method("iron_bar", 1, state, gd, GOLD_RESERVE) == Method.CRAFT


def test_relevant_actions_injects_npcbuy_for_buy_item() -> None:
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0,
                       skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert any(isinstance(a, NpcBuyAction) and a.item_code == "copper_bar" for a in relevant)


def test_relevant_actions_no_npcbuy_when_unaffordable() -> None:
    """Non-BUY skip: unaffordable -> no NpcBuyAction injected."""
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE - 1, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert not any(isinstance(a, NpcBuyAction) for a in relevant)


def test_relevant_actions_no_npcbuy_when_no_seller() -> None:
    """No-seller skip: item has no NPC sellers -> no NpcBuyAction injected."""
    gd = GameData()
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 10}}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="iron_bar", needed={"iron_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert not any(isinstance(a, NpcBuyAction) for a in relevant)


def test_craft_cooldowns_uses_bank_items() -> None:
    """_craft_cooldowns counts bank holdings to reduce gather count."""
    from artifactsmmo_cli.ai.craft_vs_buy import _craft_cooldowns

    gd = GameData()
    # copper_bar needs copper_ore x10; we have 5 in bank -> need 5 more gathers
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    state = make_state(gold=1000, inventory={}, x=0, y=0, bank_items={"copper_ore": 5})
    result = _craft_cooldowns("copper_bar", 1, state, gd)
    # 5 gathers remaining + 1 craft action
    assert result == 6


def test_buy_cooldowns_unknown_location() -> None:
    """_buy_cooldowns with npc_location=None degrades to `needed`."""
    from artifactsmmo_cli.ai.craft_vs_buy import _buy_cooldowns

    state = make_state(gold=1000, inventory={}, x=0, y=0)
    # Unknown location: returns `needed` (1)
    assert _buy_cooldowns(None, state, 1) == 1
    assert _buy_cooldowns(None, state, 3) == 3
