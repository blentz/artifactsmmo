"""GatherMaterials.relevant_actions injects NpcBuyAction for a needed item that is
NPC-sold, affordable above the reserve, and cheaper to buy than craft; leaves
craft-only / unaffordable / pricier items alone.

Also covers the fail-open branches in acquisition_method and the relevant_actions
loop: no-seller skip, non-BUY skip.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.craft_vs_buy import Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

# A representative reserve value passed to acquisition_method's `reserve` param
# (the proof is parametric in `reserve`).
_RESERVE = 500


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
    state = make_state(gold=_RESERVE + 1000, inventory={}, x=0, y=0)
    # 1 copper_bar: craft ~10 ore gathers; buy ~2 cooldowns at 5g, affordable -> BUY
    assert acquisition_method("copper_bar", 1, state, gd, _RESERVE) == Method.BUY


def test_acquisition_method_crafts_when_unaffordable() -> None:
    gd = _gd_buyable()
    state = make_state(gold=_RESERVE - 1, inventory={}, x=0, y=0)
    assert acquisition_method("copper_bar", 1, state, gd, _RESERVE) == Method.CRAFT


def test_acquisition_method_crafts_when_no_seller() -> None:
    """Fail-open: no NPC sells the item -> CRAFT."""
    gd = GameData()
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 10}}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    state = make_state(gold=_RESERVE + 1000, inventory={}, x=0, y=0)
    assert acquisition_method("iron_bar", 1, state, gd, _RESERVE) == Method.CRAFT


def test_relevant_actions_injects_npcbuy_for_buy_item() -> None:
    gd = _gd_buyable()
    state = make_state(gold=_RESERVE + 1000, inventory={}, x=0, y=0,
                       skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert any(isinstance(a, NpcBuyAction) and a.item_code == "copper_bar" for a in relevant)


def test_relevant_actions_no_npcbuy_when_unaffordable() -> None:
    """Non-BUY skip: buy would breach the progression reserve -> no NpcBuyAction.

    copper_bar costs 5g.  iron_armor (body_armor, no recipe) is an unmet
    near-term gear upgrade sold for 490g → reserve_floor = 490.  With
    gold=494, buying copper_bar leaves 489 < 490 → blocked (Method.CRAFT).
    """
    gd = _gd_buyable()
    # Add a progression-reserve item so the reserve floor is non-zero.
    gd._item_stats = {
        "iron_armor": ItemStats(
            code="iron_armor", level=5, type_="body_armor", hp_bonus=10),
    }
    gd._npc_stock["armorer"] = {"iron_armor": 490}
    gd._npc_locations["armorer"] = (10, 10)
    # gold=494: reserve_floor("copper_bar")=490; 494-5=489 < 490 → blocked.
    state = make_state(gold=494, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert not any(isinstance(a, NpcBuyAction) for a in relevant)


def test_relevant_actions_must_buy_noncraftable_npc_only_item() -> None:
    """Task #12 phase 6 reachability fix: a NON-craftable NPC-sold item (rune /
    bag / artifact — no recipe, not gathered) can ONLY be bought, so NpcBuy is
    offered unconditionally even though acquisition_method returns CRAFT for it
    (a non-craftable item misleadingly looks 'cheap to gather'). Pre-fix this
    slot was unreachable."""
    gd = GameData()
    gd._item_stats = {
        "lifesteal_rune": ItemStats(code="lifesteal_rune", level=20, type_="rune", lifesteal=10),
    }
    gd._npc_stock = {"rune_vendor": {"lifesteal_rune": 20000}}
    gd._npc_buy_currency = {"rune_vendor": {"lifesteal_rune": "gold"}}
    gd._npc_locations = {"rune_vendor": (8, 13)}
    # CRAFT is what the craft-vs-buy gate returns for this non-craftable item —
    # proving the must-buy path is NOT going through that gate.
    assert acquisition_method("lifesteal_rune", 1, state := make_state(
        level=20, gold=100000, x=0, y=0), gd, _RESERVE) == Method.CRAFT
    goal = GatherMaterialsGoal(target_item="lifesteal_rune", needed={"lifesteal_rune": 1})
    relevant = goal.relevant_actions([], state, gd)
    buys = [a for a in relevant if isinstance(a, NpcBuyAction) and a.item_code == "lifesteal_rune"]
    assert buys, "non-craftable NPC-only item must offer NpcBuy"
    assert buys[0].is_applicable(state, gd) is True


def test_relevant_actions_must_buy_offers_every_vendor_for_affordable_currency() -> None:
    """For a non-craftable item sold by multiple vendors in different currencies,
    EVERY vendor is offered so the planner can pick one the character can afford
    (is_applicable gates each). The gold vendor is affordable; the coin vendor is
    not (no coins on hand) — both offered, only the gold one applicable."""
    gd = GameData()
    gd._item_stats = {"omni_rune": ItemStats(code="omni_rune", level=20, type_="rune", lifesteal=5)}
    gd._npc_stock = {"gold_vendor": {"omni_rune": 5000}, "coin_vendor": {"omni_rune": 50}}
    gd._npc_buy_currency = {"gold_vendor": {"omni_rune": "gold"},
                            "coin_vendor": {"omni_rune": "rare_coin"}}
    gd._npc_locations = {"gold_vendor": (1, 1), "coin_vendor": (2, 2)}
    state = make_state(level=20, gold=100000, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="omni_rune", needed={"omni_rune": 1})
    relevant = goal.relevant_actions([], state, gd)
    buys = {a.npc_code for a in relevant if isinstance(a, NpcBuyAction) and a.item_code == "omni_rune"}
    assert buys == {"gold_vendor", "coin_vendor"}, "every vendor offered"
    applicable = {a.npc_code for a in relevant
                  if isinstance(a, NpcBuyAction) and a.item_code == "omni_rune"
                  and a.is_applicable(state, gd)}
    assert applicable == {"gold_vendor"}, "only the affordable-currency vendor is applicable"


def test_relevant_actions_farms_nongold_currency_for_must_buy(_=None) -> None:
    """Task #13: a non-craftable item paid in a NON-GOLD currency surfaces BOTH
    the NpcBuy AND a Fight for the monster that drops the currency, so the
    planner chains Fight×N → NpcBuy. greater_lifesteal_rune costs sandwhisper_coin
    (a sea_marauder drop) — the coin's demand is injected into the closure and
    the proven monster-drop emission farms it."""
    gd = GameData()
    gd._item_stats = {"greater_lifesteal_rune": ItemStats(
        code="greater_lifesteal_rune", level=40, type_="rune", lifesteal=20)}
    gd._npc_stock = {"sandwhisper_trader": {"greater_lifesteal_rune": 100}}
    gd._npc_buy_currency = {"sandwhisper_trader": {"greater_lifesteal_rune": "sandwhisper_coin"}}
    gd._npc_locations = {"sandwhisper_trader": (-2, 18)}
    gd._monster_level = {"sea_marauder": 5}
    gd._monster_hp = {"sea_marauder": 20}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {"sea_marauder": [("sandwhisper_coin", 50, 1, 1)]}
    gd._monster_locations = {"sea_marauder": (10, 10)}
    actions = [
        FightAction(monster_code="sea_marauder", locations=[(10, 10)]),
        NpcBuyAction(npc_code="sandwhisper_trader", item_code="greater_lifesteal_rune",
                     npc_location=(-2, 18), quantity=1),
    ]
    goal = GatherMaterialsGoal(target_item="greater_lifesteal_rune",
                              needed={"greater_lifesteal_rune": 1})
    state = make_state(level=40, attack={"air": 50}, gold=0, x=0, y=0)
    relevant = goal.relevant_actions(actions, state, gd)
    assert any(isinstance(a, FightAction) and a.monster_code == "sea_marauder" for a in relevant), \
        "currency-dropper Fight must be farmed"
    assert any(isinstance(a, NpcBuyAction) for a in relevant), "rune NpcBuy must be offered"


def test_relevant_actions_no_currency_farm_when_gold_vendor_exists() -> None:
    """If a permanent GOLD vendor also sells the item, no currency-farming is
    injected (gold needs no farming): the coin-dropper Fight is NOT surfaced."""
    gd = GameData()
    gd._item_stats = {"omni_rune": ItemStats(code="omni_rune", level=40, type_="rune", lifesteal=5)}
    gd._npc_stock = {"gold_vendor": {"omni_rune": 5000}, "coin_vendor": {"omni_rune": 100}}
    gd._npc_buy_currency = {"gold_vendor": {"omni_rune": "gold"},
                            "coin_vendor": {"omni_rune": "sandwhisper_coin"}}
    gd._npc_locations = {"gold_vendor": (1, 1), "coin_vendor": (2, 2)}
    gd._monster_level = {"sea_marauder": 5}
    gd._monster_hp = {"sea_marauder": 20}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {"sea_marauder": [("sandwhisper_coin", 50, 1, 1)]}
    gd._monster_locations = {"sea_marauder": (10, 10)}
    actions = [FightAction(monster_code="sea_marauder", locations=[(10, 10)])]
    goal = GatherMaterialsGoal(target_item="omni_rune", needed={"omni_rune": 1})
    state = make_state(level=40, attack={"air": 50}, gold=100000, x=0, y=0)
    relevant = goal.relevant_actions(actions, state, gd)
    assert not any(isinstance(a, FightAction) for a in relevant), \
        "gold vendor available → no coin-farming"


def test_relevant_actions_no_npcbuy_when_no_seller() -> None:
    """No-seller skip: item has no NPC sellers -> no NpcBuyAction injected."""
    gd = GameData()
    gd._crafting_recipes = {"iron_bar": {"iron_ore": 10}}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    state = make_state(gold=_RESERVE + 1000, inventory={}, x=0, y=0)
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
