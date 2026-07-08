"""GatherMaterials.relevant_actions injects NpcBuyAction for a needed item that is
NPC-sold, affordable above the reserve, and cheaper to buy than craft; leaves
craft-only / unaffordable / pricier items alone.

Also covers the fail-open branches in acquisition_method and the relevant_actions
loop: no-seller skip, non-BUY skip.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.craft_vs_buy import Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves
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


def _satchel_gd() -> GameData:
    """GameData for satchel affordability tests (C4 Task 5).

    satchel is craftable (gearcrafting level 1, recipe: jasper_crystal x1).
    jasper_crystal: non-craftable, not gathered, not a monster drop.
    tasks_trader sells jasper_crystal for 8 tasks_coin (non-gold currency).
    Skill gate is OPEN (gearcrafting >= 1) so the existing skill-gate fast-fail
    passes; only the affordability gate is exercised.
    """
    gd = GameData()
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    gd._item_stats = {
        "satchel": ItemStats(
            code="satchel", level=1, type_="bag",
            crafting_skill="gearcrafting", crafting_level=1,
        ),
    }
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}  # C2 floor (min_task_coin_reward) for funding-cycle calc
    gd._npc_locations = {"tasks_trader": (4, 1)}
    return gd


def test_is_plannable_false_when_currency_buy_leaf_unaffordable() -> None:
    """C4 Task 5: affordability fast-fail.

    satchel requires jasper_crystal (tasks_coin buy, 8 per crystal).
    With 0 tasks_coin on hand the goal is unplannable — no plan can acquire
    jasper_crystal because NpcBuy is inapplicable and GatherMaterials has no
    action that earns tasks_coin. currency_afford_plannable_pure must drive
    this decision.
    """
    gd = _satchel_gd()
    goal = GatherMaterialsGoal(target_item="satchel", needed={"satchel": 1})
    state = make_state(skills={"gearcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is False


def test_is_plannable_true_when_currency_buy_leaf_affordable_inventory() -> None:
    """C4 Task 5: affordability fast-fail clears when tasks_coin in inventory >= price*qty."""
    gd = _satchel_gd()
    goal = GatherMaterialsGoal(target_item="satchel", needed={"satchel": 1})
    # 8 tasks_coin in inventory exactly covers price(8) * qty(1)
    state = make_state(skills={"gearcrafting": 5}, inventory={"tasks_coin": 8}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is True


def test_is_plannable_true_when_currency_buy_leaf_affordable_bank() -> None:
    """C4 Task 5: tasks_coin in bank also counts toward affordability."""
    gd = _satchel_gd()
    goal = GatherMaterialsGoal(target_item="satchel", needed={"satchel": 1})
    state = make_state(skills={"gearcrafting": 5}, inventory={}, bank_items={"tasks_coin": 8}, x=0, y=0)
    assert goal.is_plannable(state, gd) is True


def test_is_plannable_skill_gate_still_fires_independently() -> None:
    """C4 Task 5 regression: the existing skill-gate fast-fail is unaffected.

    feather_coat: gearcrafting level 5, player skill = 2 → skill gate prunes
    regardless of affordability (no currency-buy leaves in this closure).
    """
    gd = GameData()
    gd._crafting_recipes = {}
    gd._item_stats = {
        "feather_coat": ItemStats(
            code="feather_coat", level=5, type_="body_armor",
            crafting_skill="gearcrafting", crafting_level=5,
        ),
    }
    goal = GatherMaterialsGoal(target_item="feather_coat", needed={"feather_coat": 1})
    state = make_state(skills={"gearcrafting": 2}, inventory={}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is False


def test_is_plannable_not_pruned_when_leaf_is_craftable() -> None:
    """_currency_leaves_affordable: craftable leaf is skipped (not a currency-buy leaf)."""
    gd = GameData()
    # widget needs cog x1; cog is CRAFTABLE (iron_ore x2) → not a currency-buy leaf
    gd._crafting_recipes = {"widget": {"cog": 1}, "cog": {"iron_ore": 2}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    state = make_state(skills={"weaponcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    # No currency at all — but cog is craftable so no currency-buy pruning
    assert goal.is_plannable(state, gd) is True


def test_is_plannable_not_pruned_when_leaf_is_resource_drop() -> None:
    """_currency_leaves_affordable: resource-drop leaf is skipped."""
    gd = GameData()
    # widget needs copper_ore x1; copper_ore IS a resource drop (copper_rock drops it)
    gd._crafting_recipes = {"widget": {"copper_ore": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._resource_drops = {"copper_rock": "copper_ore"}
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    state = make_state(skills={"weaponcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is True


def test_is_plannable_not_pruned_when_leaf_is_monster_drop() -> None:
    """_currency_leaves_affordable: monster-drop leaf is skipped."""
    from tests.test_ai._monster_fixture import fill_monster_stat_defaults
    gd = GameData()
    # widget needs feather x1; feather is a monster drop (chicken drops it)
    gd._crafting_recipes = {"widget": {"feather": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 10}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {"chicken": [("feather", 50, 1, 1)]}
    gd._monster_locations = {"chicken": (1, 1)}
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    state = make_state(skills={"weaponcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is True


def test_is_plannable_not_pruned_when_leaf_has_no_npc_seller() -> None:
    """_currency_leaves_affordable: leaf with no NPC sellers is skipped (no purchases)."""
    gd = GameData()
    # widget needs mystery_item x1; mystery_item: no recipe, no drop, no sellers
    gd._crafting_recipes = {"widget": {"mystery_item": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._npc_stock = {}
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    state = make_state(skills={"weaponcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    # mystery_item has no sellers → no currency-buy leaf → no affordability pruning
    assert goal.is_plannable(state, gd) is True


def test_relevant_actions_emits_npcbuy_for_deep_closure_currency_buy_leaf() -> None:
    """C4 Task 1: a deep recipe-closure leaf that is currency-bought (not
    craftable, not a resource/monster drop) must surface an NpcBuyAction even
    though it is NOT in self._needed (i.e. it's a transitive ingredient).

    Scenario: satchel is the target (needed={satchel:1}). satchel's recipe
    requires jasper_crystal x1. jasper_crystal is non-craftable, not a
    resource drop, not a monster drop, and sold by tasks_trader for
    tasks_coin (a non-gold currency). The planner must be offered
    NpcBuyAction(item_code='jasper_crystal', npc_code='tasks_trader', ...) so
    it can chain currency-farming → buy.
    """
    gd = GameData()
    # satchel is craftable (recipe: jasper_crystal x1)
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    # jasper_crystal: non-craftable, not gathered, not dropped
    # tasks_trader sells it for 8 tasks_coin each (permanent vendor)
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}  # C2 floor (min_task_coin_reward) for funding-cycle calc
    gd._npc_locations = {"tasks_trader": (4, 1)}
    state = make_state(level=10, gold=0, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="satchel", needed={"satchel": 1})
    relevant = goal.relevant_actions([], state, gd)
    buy_actions = [a for a in relevant
                   if isinstance(a, NpcBuyAction) and a.item_code == "jasper_crystal"]
    assert buy_actions, (
        "NpcBuyAction for deep closure currency-buy leaf 'jasper_crystal' must be emitted "
        "even though it is not in self._needed (only satchel is)"
    )


def test_event_npc_vendor_blocked_but_not_funded() -> None:
    """C4 follow-up (Minor #3): a leaf sold ONLY by an EVENT vendor is BLOCKED
    (is_plannable prunes — relevant_actions emits no NpcBuy for an event vendor,
    so no plan can buy it) but is NOT a funding target (ReachCurrencyGoal mints
    only tasks_coin; it cannot earn the event currency, so routing to it would
    chase an unreachable goal).

    Scenario: mystical_crystal sold ONLY by EVENT NPC seasonal_trader for 50
    event_tokens. Even with 50 event_tokens on hand, the event vendor is not
    usable, so the leaf is blocked and there is no funding target.
    """
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {"widget": {"mystical_crystal": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._npc_stock = {"seasonal_trader": {"mystical_crystal": 50}}
    gd._npc_buy_currency = {"seasonal_trader": {"mystical_crystal": "event_tokens"}}
    gd._npc_locations = {"seasonal_trader": (0, 0)}
    gd.world.npc_event_codes["seasonal_trader"] = "seasonal_event"

    state = make_state(skills={"weaponcrafting": 5}, inventory={"event_tokens": 50},
                       bank_items={}, x=0, y=0)

    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is True, "event-only vendor leaf must block is_plannable"
    assert result.funding_target is None, (
        "must NOT route ReachCurrencyGoal toward an event/non-task currency: "
        f"got {result.funding_target}"
    )


def test_gold_leaf_blocked_but_not_funded() -> None:
    """C4 follow-up (Minor #1/#3): a leaf bought from a PERMANENT vendor for a
    NON-task currency (gold) that the character cannot afford is BLOCKED, but is
    NOT a funding target — ReachCurrencyGoal cannot earn gold (it mints
    tasks_coin), so the bot earns gold by its normal means instead."""
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {"widget": {"rare_gem": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._npc_stock = {"jeweler": {"rare_gem": 500}}
    gd._npc_buy_currency = {"jeweler": {"rare_gem": "gold"}}
    gd._npc_locations = {"jeweler": (0, 0)}
    gd._task_coin_rewards = {"chicken": 1}  # so min_task_coin_reward is defined

    state = make_state(skills={"weaponcrafting": 5}, inventory={"gold": 0},
                       bank_items={}, x=0, y=0)

    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is True, "unaffordable gold leaf must block is_plannable"
    assert result.funding_target is None, (
        "must NOT route ReachCurrencyGoal toward gold (unfundable by tasks): "
        f"got {result.funding_target}"
    )


# Task 3 (gold-reserve discipline, 2026-07-08): `widget` (weapon-type, level 1)
# is itself an in-horizon `crafting_unlock_targets` source — its recipe needs
# rare_gem (non-gatherable, non-craftable, gold-sold), so
# `progression_reserve.reserved_targets` always contains {"rare_gem": 500} for
# this fixture's state. `reserve_floor(state, gd, "rare_gem")` DEDUPS rare_gem's
# own reservation (buying it fulfills the reservation) down to 0, then floors at
# `_MIN_SAFETY_FLOOR` (100) — so every gold-priced buy in this fixture now needs
# 500 (price) + 100 (floor) = 600 gold on hand, not 500. Verified via direct
# `reserve_floor` computation (progression_reserve.py), not guessed.
_GOLD_VENDOR_RESERVE = 100


def _gold_vendor_gd() -> GameData:
    """widget (craftable) needs rare_gem x1; rare_gem is vendor-only at the
    PERMANENT jeweler for 500 GOLD — the GAP-3 shape (gold-priced buy leaf)."""
    gd = GameData()
    gd._crafting_recipes = {"widget": {"rare_gem": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._npc_stock = {"jeweler": {"rare_gem": 500}}
    gd._npc_buy_currency = {"jeweler": {"rare_gem": "gold"}}
    gd._npc_locations = {"jeweler": (3, 3)}
    gd._task_coin_rewards = {"chicken": 1}  # min_task_coin_reward defined
    return gd


def test_gold_leaf_affordable_from_pocket_gold() -> None:
    """GAP-3 root fix: gold is NOT an inventory item. A gold-priced leaf's
    affordability reads state.gold — 600 pocket gold (500 price +
    `_GOLD_VENDOR_RESERVE` 100, Task 3) covers the 500-gold rare_gem, so the
    leaf must NOT block (the old inventory["gold"] read scored this 0 and
    pruned every gold purchase at is_plannable)."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=500 + _GOLD_VENDOR_RESERVE,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is False, "pocket gold must fund a gold-priced leaf"
    assert result.gold_deficit == 0, result.gold_deficit


def test_gold_leaf_affordable_pocket_plus_bank_gold() -> None:
    """Pocket 200 + bank 400 (Task 3: 500 price + 100 reserve = 600 total
    needed, up from bank 300 pre-reserve) covers the 500-gold price → not
    blocked. gold_deficit stays 300 — the WithdrawGold ferry sizes off the raw
    pocket shortfall (`gold_demand - state.gold`), UNCHANGED by the reserve:
    the ferry only relocates gold pocket<->bank, it never spends it, so it
    cannot itself violate a reserve floor defined on the TOTAL (see
    currency_demand.py's module-docstring derivation)."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=200,
                       bank_gold=300 + _GOLD_VENDOR_RESERVE,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is False
    assert result.gold_deficit == 300, result.gold_deficit


def test_gold_leaf_unknown_bank_gold_not_credited() -> None:
    """bank_gold=None is UNKNOWN, not zero — it credits nothing (GAP-1's
    bank-stock rule): pocket 200 alone < 500 → blocked, honest deferral."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=200, bank_gold=None,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is True, "unknown bank gold must not fund the leaf"


def test_gold_leaf_owned_stock_needs_no_gold() -> None:
    """A leaf already owned (inventory/bank stock >= closure qty) demands no
    gold: gold_deficit stays 0 even with an empty pocket."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=0,
                       inventory={"rare_gem": 1}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is False
    assert result.gold_deficit == 0, result.gold_deficit


# --- Task 3 (gold-reserve discipline, 2026-07-08) ---------------------------

def test_gold_leaf_reserve_boundary_affordable() -> None:
    """Reserve-boundary case: pocket gold exactly equals price + reserve
    (500 + 100). `gold_on_hand >= price*qty + reserve` (P4a exact-int form,
    no signed subtraction) must read affordable AT the boundary, not past
    it — this is the currency_demand.py module-docstring invariant, pinned."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5},
                       gold=500 + _GOLD_VENDOR_RESERVE,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is False


def test_gold_leaf_reserve_boundary_minus_one_blocked() -> None:
    """One gold short of the reserve-adjusted price blocks — same honest
    deferral as plain unaffordable (no funding root; the bot earns gold by
    its normal means and retries later)."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5},
                       gold=500 + _GOLD_VENDOR_RESERVE - 1,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is True


def test_gold_leaf_reserve_none_bank_still_uncredited() -> None:
    """The reserve change must not disturb GAP-1's None-bank rule: an UNKNOWN
    bank (None) credits nothing toward EITHER the price or the reserve —
    pocket alone (500, short of the reserve-adjusted 600) still blocks."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=500, bank_gold=None,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is True, "unknown bank gold must not fund the reserve either"


def test_gold_leaf_deficit_sizing_respects_reserve_invariant() -> None:
    """WithdrawGold deficit-sizing derivation, pinned: pocket 100 + bank 500
    = 600 = price(500) + reserve(100), the exact boundary. `gold_deficit`
    tops the pocket up to the PRICE only (400 = 500 - 100) — NOT
    price+reserve — because WithdrawGold is gold-CONSERVING (a pocket<->bank
    transfer, never a spend) and so cannot itself violate a reserve floor
    defined on the TOTAL. The invariant instead falls out algebraically:
    post-buy total = pocket + bank - price = 600 - 500 = 100, exactly the
    reserve, independent of how the deficit is split between pocket and
    withdrawal."""
    gd = _gold_vendor_gd()
    pocket, bank = 100, 500
    state = make_state(skills={"weaponcrafting": 5}, gold=pocket, bank_gold=bank,
                       inventory={}, bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.blocked is False
    assert result.gold_deficit == 400, result.gold_deficit
    assert pocket + bank - 500 == _GOLD_VENDOR_RESERVE, (
        "post-buy total gold must land exactly at the reserve floor")


def test_is_plannable_true_when_gold_leaf_affordable_from_pocket() -> None:
    """The GAP-3 dead end, at the goal seam: with pocket gold covering the
    gold-priced leaf AND its reserve floor (Task 3: 500 + 100), GatherMaterials
    Goal.is_plannable must admit (the l30 tripwire's 0-node prune came exactly
    from this gate)."""
    gd = _gold_vendor_gd()
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    state = make_state(skills={"weaponcrafting": 5}, gold=500 + _GOLD_VENDOR_RESERVE,
                       inventory={}, bank_items={}, x=0, y=0)
    assert goal.is_plannable(state, gd) is True


def test_relevant_actions_ferries_gold_deficit_via_withdraw() -> None:
    """Admit/emit symmetry (GAP-3): pocket 200 short of the 500-gold leaf,
    bank holds 300 → relevant_actions must admit ONE WithdrawGold sized to
    the 300 deficit (resized from the factory-emitted template so bank
    location/accessibility survive), enabling WithdrawGold → NpcBuy."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=200, bank_gold=300,
                       inventory={}, bank_items={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    template = WithdrawGoldAction(quantity=100, bank_location=(1, 1))
    relevant = goal.relevant_actions([template], state, gd)
    withdraws = [a for a in relevant if isinstance(a, WithdrawGoldAction)]
    assert [w.quantity for w in withdraws] == [300], withdraws
    assert withdraws[0].bank_location == (1, 1)
    assert any(isinstance(a, NpcBuyAction) and a.item_code == "rare_gem"
               for a in relevant), "the gold-buy edge itself must be admitted"


def test_relevant_actions_no_gold_withdraw_when_pocket_covers() -> None:
    """Pocket gold alone covers the gold-buy leaves → no WithdrawGold edge
    (deficit 0; the buy pays straight from the pocket)."""
    gd = _gold_vendor_gd()
    state = make_state(skills={"weaponcrafting": 5}, gold=600, bank_gold=300,
                       inventory={}, bank_items={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    template = WithdrawGoldAction(quantity=100, bank_location=(1, 1))
    relevant = goal.relevant_actions([template], state, gd)
    assert not [a for a in relevant if isinstance(a, WithdrawGoldAction)]


def test_tasks_coin_leaf_blocked_and_funded() -> None:
    """A permanent tasks_coin vendor, unaffordable → blocked AND a funding target
    (tasks_coin, price*qty) the arbiter routes ReachCurrencyGoal to."""
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 2}}
    gd._item_stats = {
        "satchel": ItemStats(code="satchel", level=5, type_="bag",
                             crafting_skill="gearcrafting", crafting_level=5),
    }
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}  # C2 floor (min_task_coin_reward) for funding-cycle calc
    gd._npc_locations = {"tasks_trader": (1, 2)}
    gd._task_coin_rewards = {"chicken": 1}

    state = make_state(skills={"gearcrafting": 5}, inventory={"tasks_coin": 0},
                       bank_items={}, x=0, y=0)

    result = analyze_currency_leaves({"satchel": 1}, state, gd)
    assert result.blocked is True
    # jasper_crystal x2 (closure qty) @ 8 tasks_coin = 16
    assert result.funding_target == ("tasks_coin", 16), result.funding_target


def test_funding_vendor_picked_by_fewest_cycles_not_raw_price() -> None:
    """C4 follow-up (Minor #1): with two PERMANENT tasks_coin vendors at different
    prices, the funding target is the one needing the FEWEST funding cycles given
    current holdings — a semantic key, not raw cheapest price."""
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {"widget": {"shard": 1}}
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    # two permanent tasks_coin vendors for `shard`: cheap@10 and pricier@12.
    gd._npc_stock = {"trader_a": {"shard": 10}, "trader_b": {"shard": 12}}
    gd._npc_buy_currency = {
        "trader_a": {"shard": "tasks_coin"},
        "trader_b": {"shard": "tasks_coin"},
    }
    gd._npc_locations = {"trader_a": (0, 0), "trader_b": (1, 1)}
    gd._task_coin_rewards = {"chicken": 1}  # floor = 1

    # Same currency (tasks_coin), so fewest cycles == cheapest price here: 10.
    state = make_state(skills={"weaponcrafting": 5}, inventory={"tasks_coin": 0},
                       bank_items={}, x=0, y=0)
    result = analyze_currency_leaves({"widget": 1}, state, gd)
    assert result.funding_target == ("tasks_coin", 10), (
        "fewest-cycles vendor (cheapest in same currency) must win: "
        f"got {result.funding_target}"
    )

    # Cross-check: GatherMaterialsGoal.is_plannable should also return False
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    assert goal.is_plannable(state, gd) is False, (
        "Goal with only event-vendor currency-buy leaf must be unplannable"
    )


def test_relevant_actions_skips_event_vendor_for_closure_leaf() -> None:
    """C4 deep-leaf emission must NOT emit NpcBuy for a recipe-CLOSURE leaf whose
    only vendor is an EVENT/unlocated NPC (covers the event-vendor skip in
    relevant_actions, matching the currency_demand permanent-vendor filter)."""
    gd = GameData()
    # gizmo (weaponcrafting) requires flux x1; flux sold ONLY by an event vendor.
    gd._crafting_recipes = {"gizmo": {"flux": 1}}
    gd._item_stats = {
        "gizmo": ItemStats(code="gizmo", level=1, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._npc_stock = {"festival_trader": {"flux": 9}}
    gd._npc_buy_currency = {"festival_trader": {"flux": "festival_coin"}}
    gd._npc_locations = {"festival_trader": (3, 3)}
    gd.world.npc_event_codes["festival_trader"] = "festival_event"
    state = make_state(skills={"weaponcrafting": 5}, inventory={}, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="gizmo", needed={"gizmo": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert not any(isinstance(a, NpcBuyAction) and a.item_code == "flux" for a in relevant), (
        "event-vendor closure leaf must not get an NpcBuy emission"
    )


def test_directly_requested_currency_item_is_funded() -> None:
    """Stepwise decomposition hands the mapper the currency item ITSELF once
    every other input is in hand (satchel -> ... -> ObtainItem(jasper_crystal)).
    The old 'leaf in needed' exclusion silenced funding exactly at that final
    step: GatherMaterials(jasper_crystal) was built with 0 tasks_coin, NpcBuy
    inapplicable, goal unplannable — the live satchel stall (2026-07-06)."""
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {}
    gd._item_stats = {
        "gem": ItemStats(code="gem", level=1, type_="resource", subtype="task"),
    }
    gd._npc_stock = {"trader": {"gem": 8}}
    gd._npc_buy_currency = {"trader": {"gem": "tasks_coin"}}
    gd._npc_locations = {"trader": (0, 0)}
    gd._task_coin_rewards = {"chickens": 2}

    state = make_state(inventory={}, bank_items={})
    result = analyze_currency_leaves({"gem": 1}, state, gd)
    assert result.blocked is True, "unaffordable direct currency request must block"
    assert result.funding_target == ("tasks_coin", 8)


def test_directly_requested_currency_item_affordable_not_blocked() -> None:
    """With coins in hand the direct request is NOT blocked (GatherMaterials
    plans the NpcBuy) and needs no funding."""
    from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves

    gd = GameData()
    gd._crafting_recipes = {}
    gd._item_stats = {
        "gem": ItemStats(code="gem", level=1, type_="resource", subtype="task"),
    }
    gd._npc_stock = {"trader": {"gem": 8}}
    gd._npc_buy_currency = {"trader": {"gem": "tasks_coin"}}
    gd._npc_locations = {"trader": (0, 0)}
    gd._task_coin_rewards = {"chickens": 2}

    state = make_state(inventory={"tasks_coin": 8}, bank_items={})
    result = analyze_currency_leaves({"gem": 1}, state, gd)
    assert result.blocked is False
    assert result.funding_target is None
