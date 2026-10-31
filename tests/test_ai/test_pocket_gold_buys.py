"""Every gold buy pays from the POCKET (HTTP 492 hotfix, 2026-10-30).

Live, right after the fleet restart on 4eb1f76d: HAL held 6,516 gold in pocket
against a standing 6,550-gold `lich_crown` sell order and planned a bare
`GeBuy` five cycles in a row, each one answered HTTP 492 "The character does
not have enough gold", with tens of thousands of gold in the shared bank.
Robby did the same with `mithril_helm` from a 1,736 pocket.

`can_spend` asks the reserve of the ACCOUNT (pocket plus bank). The server
takes the price from the pocket alone. So:

- a buy is applicable only when the pocket covers it (and the reserve holds);
- a pocket-short, bank-rich plan withdraws the shortfall first, in both plan
  producers: A* through the goal's admitted `gold_ferry`, and the fast-path
  walk through `ObtainModel`'s gold WITHDRAW route;
- the pricer charges that withdraw, the one action and the bank hop.
"""

from dataclasses import replace
from fractions import Fraction
from math import ceil

import pytest

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions, acquisition_options, cheapest_route
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction, gold_ferry
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decisions.obtain_item import (
    DoesTheChainFitTheDepthBudget,
    DoesTheRecipeNeedAMonsterDrop,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.goal_serialization import goal_from_dict, goal_to_dict
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.post_buy_bid import PostBuyBidGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.gold_rate import gold_per_second, gold_spend_actions
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.obtain_item_routing import _equippable_goal, ge_fill_priced
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, PIECE_POLICY
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.progression_reserve import reserve_floor_multi, spendable_pocket
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state
from tests.test_ai.shared_world import attached, shared_world
from tests.test_ai.test_gold_funded_piece import (
    BUNDLE,
    CELL,
    PRICE,
    RUNE,
    SHARD,
    _crystal_ctx,
    _state,
    _world,
)

HAL_POCKET = 6516
HAL_PRICE = 6550
SHORT = HAL_PRICE - HAL_POCKET  # 34
BANK = (0, 0)
GE = (2, 2)


# --------------------------------------------------------------------------
# The buy actions gate on the pocket.
# --------------------------------------------------------------------------

def _crown_gd() -> GameData:
    """A level-5 helmet sold only on the GE at HAL's price; no recipe, so the
    standing order is the one route. The account reserve is the safety floor:
    nothing else is reserved."""
    gd = GameData()
    gd._item_stats = {"crown": ItemStats(code="crown", level=5, type_="helmet", hp_bonus=40)}
    gd._ge_sell_orders = {"crown": ("ord-crown", HAL_PRICE, 1)}
    gd._grand_exchange_location = GE
    gd._bank_location = BANK
    gd._taskmaster_location = (1, 1)
    return gd


def _hal(gd: GameData, *, gold: int = HAL_POCKET, bank_gold: int | None = 10_000) -> WorldState:
    state = scenario_state(ScenarioCharacter(name="hal", level=5), gd)
    return replace(state, gold=gold, bank_gold=bank_gold, bank_items={})


def _fill() -> GeFillSellOrderAction:
    return GeFillSellOrderAction(order_id="ord-crown", item_code="crown", price=HAL_PRICE,
                                 quantity=1, ge_location=GE)


def test_a_fill_the_account_affords_but_the_pocket_does_not_is_refused() -> None:
    """HAL's state: the account clears the reserve by thousands, the pocket is
    34 short, and the server refuses the buy, so the action must too."""
    gd = _crown_gd()
    hal = _hal(gd)
    assert reserve_floor_multi(hal, gd, frozenset({"crown"})) == 100
    assert _fill().is_applicable(hal, gd) is False
    assert _fill().is_applicable(replace(hal, gold=HAL_PRICE), gd) is True


def test_a_bid_the_pocket_cannot_escrow_is_refused() -> None:
    gd = _crown_gd()
    bid = GePostBuyOrderAction(item_code="crown", quantity=2, price=HAL_PRICE // 2,
                               ge_location=GE)
    hal = _hal(gd)
    assert bid.is_applicable(hal, gd) is False
    assert bid.is_applicable(replace(hal, gold=HAL_PRICE), gd) is True
    with pytest.raises(AssertionError, match="short of cost"):
        bid.apply(hal, gd)


# --------------------------------------------------------------------------
# The ferry.
# --------------------------------------------------------------------------

def _pool() -> list[Action]:
    return [WithdrawGoldAction(quantity=q, bank_location=BANK, accessible=True)
            for q in (50, 100, 500, 1000)]


def test_the_ferry_is_the_shortfall_from_the_pool_s_withdraw() -> None:
    gd = _crown_gd()
    hal = _hal(gd)
    locked: list[Action] = [WithdrawGoldAction(quantity=50, bank_location=BANK, accessible=False)]
    assert gold_ferry(_pool(), hal, SHORT) == WithdrawGoldAction(
        quantity=SHORT, bank_location=BANK, accessible=True)
    # The bank tile and its accessibility are the pool's.
    assert gold_ferry(locked, hal, SHORT) == WithdrawGoldAction(
        quantity=SHORT, bank_location=BANK, accessible=False)
    # Capped at what the bank holds.
    assert gold_ferry(_pool(), replace(hal, bank_gold=20), SHORT) == WithdrawGoldAction(
        quantity=20, bank_location=BANK, accessible=True)


@pytest.mark.parametrize(("deficit", "bank_gold", "pool"), [
    (0, 10_000, True),       # nothing short
    (-5, 10_000, True),      # the pocket covers it with change
    (SHORT, None, True),     # the bank was not read: unknown, not empty
    (SHORT, 0, True),        # an empty bank ferries nothing
    (SHORT, 10_000, False),  # no withdraw in the pool to size
])
def test_no_ferry(deficit: int, bank_gold: int | None, pool: bool) -> None:
    gd = _crown_gd()
    assert gold_ferry(_pool() if pool else [], _hal(gd, bank_gold=bank_gold), deficit) is None


# --------------------------------------------------------------------------
# A*: the goal admits the ferry beside the fill.
# --------------------------------------------------------------------------

def _upgrade() -> UpgradeEquipmentGoal:
    return UpgradeEquipmentGoal(committed_target=("crown", "helmet_slot"), ge_fill=True)


def test_a_star_withdraws_the_shortfall_then_buys() -> None:
    """HAL's case through the search: WithdrawGold(34), then the fill, then
    the equip. Never the bare GeBuy the server answers 492."""
    gd = _crown_gd()
    hal = _hal(gd)
    plan = GOAPPlanner().plan(hal, _upgrade(), list(_pool()), gd)
    assert plan == [WithdrawGoldAction(quantity=SHORT, bank_location=BANK, accessible=True),
                    _fill(), EquipAction(code="crown", slot="helmet_slot")]


def test_a_star_buys_from_a_pocket_that_covers_it_without_a_withdraw() -> None:
    gd = _crown_gd()
    hal = _hal(gd, gold=HAL_PRICE)
    rel = _upgrade().relevant_actions(list(_pool()), hal, gd)
    assert not [a for a in rel if isinstance(a, WithdrawGoldAction)]
    plan = GOAPPlanner().plan(hal, _upgrade(), list(_pool()), gd)
    assert plan == [_fill(), EquipAction(code="crown", slot="helmet_slot")]


def test_a_star_plans_no_buy_when_the_bank_cannot_cover_the_shortfall() -> None:
    gd = _crown_gd()
    hal = _hal(gd, bank_gold=SHORT - 1)
    plan = GOAPPlanner().plan(hal, _upgrade(), list(_pool()), gd)
    assert not [a for a in plan if isinstance(a, GeFillSellOrderAction)]


def test_a_bid_short_of_the_pocket_admits_the_ferry_for_the_joint_escrow() -> None:
    """`PostBuyBidGoal` is satisfied only once every bid is posted, so the
    ferry is sized to their joint escrow less the pocket."""
    gd = GameData()
    gd._crafting_recipes = {"steel": {"iron": 2}}
    gd._monster_drops = {"mob": [("iron", 50, 1, 1)]}
    gd._npc_stock = {"shop": {"steel": 5000}}
    gd._npc_locations = {"shop": (1, 0)}
    gd._ge_buy_orders = {"steel": ("b1", 40, 5)}
    gd._grand_exchange_location = (7, 7)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, step_profile={"steel": 1},
                  learned_drops=LearnedDrops.empty())
    goal = PostBuyBidGoal(game_data=gd, ctx=ctx)
    rich = make_state(gold=1000, inventory={})
    bids = goal.relevant_actions(list(_pool()), rich, gd)
    assert [type(a) for a in bids] == [GePostBuyOrderAction]
    bid = bids[0]
    assert isinstance(bid, GePostBuyOrderAction)
    # The bank holds the bid's gold, not the NPC's 5,000: still a bid.
    poor = make_state(gold=1, bank_gold=1000, bank_items={}, inventory={})
    assert goal.relevant_actions(list(_pool()), poor, gd) == [
        bid, WithdrawGoldAction(quantity=bid.price * bid.quantity - 1, bank_location=BANK,
                                accessible=True)]


# --------------------------------------------------------------------------
# The walk: banked gold is a WITHDRAW route.
# --------------------------------------------------------------------------

def test_the_walk_withdraws_banked_gold_above_the_reserve() -> None:
    """The gold route's capacity is the account's gold above the reserve floor,
    less the pocket the walk already counts, and one application moves it."""
    gd = _crown_gd()
    hal = _hal(gd)
    # The walk's buys of the crown keep the floor less the crown's own
    # reservation (the safety floor); a walk naming no buy keeps the whole
    # reserve, the crown's 6,550 included: conservative, never past it.
    spending = ObtainModel(hal, gd, TIMED_NO_PROFILE_CONTEXT, TIMED_NO_PROFILE_CONTEXT.now,
                           spend=frozenset({"crown"}))
    [route] = [r for r in spending.routes(GOLD_CODE) if r.kind is SourceKind.WITHDRAW]
    assert reserve_floor_multi(hal, gd, frozenset({"crown"})) == 100
    assert route.capacity == route.yield_per == 10_000 - 100
    assert route.gates[0].satisfied is True
    assert spending.feasible(GOLD_CODE, HAL_POCKET + 10_000 - 100, LEGACY)
    assert not spending.feasible(GOLD_CODE, HAL_POCKET + 10_000 - 99, LEGACY)
    model = ObtainModel(hal, gd, TIMED_NO_PROFILE_CONTEXT, TIMED_NO_PROFILE_CONTEXT.now)
    [whole] = [r for r in model.routes(GOLD_CODE) if r.kind is SourceKind.WITHDRAW]
    assert reserve_floor_multi(hal, gd, frozenset()) == HAL_PRICE
    assert whole.capacity == 10_000 - HAL_PRICE
    # An unread bank is unknown, not rich.
    unread = ObtainModel(replace(hal, bank_gold=None), gd, TIMED_NO_PROFILE_CONTEXT,
                         TIMED_NO_PROFILE_CONTEXT.now)
    assert not [r for r in unread.routes(GOLD_CODE) if r.kind is SourceKind.WITHDRAW]
    # A bank that holds only reserve has nothing to give.
    poor = ObtainModel(replace(hal, gold=50, bank_gold=40), gd, TIMED_NO_PROFILE_CONTEXT,
                       TIMED_NO_PROFILE_CONTEXT.now)
    assert not [r for r in poor.routes(GOLD_CODE) if r.kind is SourceKind.WITHDRAW]


def test_pocket_and_bank_gold_are_priced_alike() -> None:
    """The `L*` rune (20,000 gold at the rune vendor) from a 100-gold pocket
    and a rich bank: the buy and the withdraw, each with its hop, and EVERY
    gold piece spent at the actions it takes to earn it again (S-046), the
    pocket's 100 and the bank's 19,900 alike. From a pocket holding it all,
    the same price less only the withdraw and its hop."""
    world = _world()
    poor = _state(world)
    assert poor.gold == 100
    rich = replace(poor, bank_gold=50_000, bank_items={})
    ctx = attached(rich, world, TIMED_NO_PROFILE_CONTEXT, None)
    per_gold = gold_spend_actions(rich, world, ctx)
    assert 0 < per_gold < 1

    def price(state: WorldState) -> tuple[int, SourceKind | None]:
        return cheapest_route(RUNE.code, 1, state, world, ctx, None, policy=PIECE_POLICY,
                              pocket=spendable_pocket(state, world, frozenset({RUNE.code})))

    banked, route = price(rich)
    assert route is SourceKind.BUY
    assert banked == 3 + ceil(100 * per_gold) + ceil(1 + (PRICE - 100) * per_gold)
    pocketed, _ = price(replace(rich, gold=50_000, bank_gold=0))
    assert pocketed == 2 + ceil(PRICE * per_gold)
    assert banked - pocketed in (2, 3)  # the withdraw and its hop; one rounding


def test_the_player_withdraws_then_buys_the_rune() -> None:
    """Both producers, through the player: the rune's plan from a 100 pocket
    and a rich bank is WithdrawGold then the NpcBuy, not the gold fight it
    used to be (`test_gold_funded_piece`, whose bank is unread)."""
    world = _world()
    player = GamePlayer(character=CELL, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    state = scenario_state(SCENARIOS[CELL], world)
    player.seed_offline(replace(state, bank_gold=50_000, bank_items={}), world)
    report = player.plan_from_state()
    assert report.decision.chosen_root == RUNE
    assert [repr(a) for a in report.plan] == [
        f"WithdrawGold({PRICE - state.gold})", "NpcBuy(lifesteal_rune×1@rune_vendor)"]


def _piece_world() -> tuple[GameData, WorldState, list[Action]]:
    world = shared_world(BUNDLE, with_ge_orders=True)
    state = scenario_state(SCENARIOS[CELL], world)
    player = GamePlayer(character=state.character, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, world)
    return world, state, player._build_actions()


def _fighting_ctx(state: WorldState) -> SelectionContext:
    """`_crystal_ctx`'s hand-built objective with its fighter: the gold rate
    the pricer charges spent gold at is read on `L*(m*)` (ruling CB)."""
    ctx = _crystal_ctx()
    assert ctx.gear_objective is not None
    return replace(ctx, gear_objective=replace(ctx.gear_objective, fighter=state))


def test_the_fast_path_withdraws_the_shortfall_then_fills() -> None:
    """An `L*` piece's GE-filled material (the walk's GE route), pocket 34
    short of the fill, the bank rich: WithdrawGold(34) then the GeBuy, not a
    fight for gold and never a bare GeBuy."""
    world, state, actions = _piece_world()
    order = world.ge_best_sell_order(SHARD)
    assert order is not None
    cost = order[1] * 3
    goal = GatherMaterialsGoal(SHARD, {SHARD: 3}, fight_gold=True)
    short = replace(state, gold=cost - SHORT, bank_gold=50_000, bank_items={})
    assert spendable_pocket(short, world, frozenset({SHARD})) == cost - SHORT
    plan = decompose(goal, short, world, actions, _fighting_ctx(short))
    assert plan is not None
    fill = GeFillSellOrderAction(order_id=order[0], item_code=SHARD, price=order[1],
                                 quantity=3, ge_location=world.grand_exchange_location())
    withdraws = [a for a in plan if isinstance(a, WithdrawGoldAction)]
    assert withdraws == [WithdrawGoldAction(quantity=SHORT, bank_location=world.bank_location(),
                                            accessible=True)]
    assert plan.index(withdraws[0]) < plan.index(fill)
    # The plan as served: the withdraw makes the fill applicable.
    at = short
    for action in plan[:plan.index(fill)]:
        assert action.is_applicable(at, world)
        at = action.apply(at, world)
    assert fill.is_applicable(at, world)


def test_the_fast_path_buys_nothing_when_the_bank_cannot_cover_it() -> None:
    world, state, actions = _piece_world()
    order = world.ge_best_sell_order(SHARD)
    assert order is not None
    goal = GatherMaterialsGoal(SHARD, {SHARD: 3}, fight_gold=True)
    short = replace(state, gold=order[1] * 3 - SHORT, bank_gold=SHORT - 1, bank_items={})
    plan = decompose(goal, short, world, actions, _fighting_ctx(short))
    assert plan is not None
    assert not [a for a in plan if isinstance(a, GeFillSellOrderAction | WithdrawGoldAction)]


# --------------------------------------------------------------------------
# S-046: spent gold costs the time to earn it again.
# --------------------------------------------------------------------------

SWORD = "iron_sword"
"""Craftable in the l20 cell (iron ore -> bars -> the sword), so a GE fill of
it competes with a route that costs time, not gold."""


ROBBY = (1736, 150_000)
"""Robby's purse shape: a small pocket and a bank that can pay for the fill."""


def _sword_book(price: int, purse: tuple[int, int] = ROBBY
                ) -> tuple[GameData, WorldState, SelectionContext]:
    """The l20 world with a standing sell order for the sword at `price`, the
    character holding `purse` (pocket, bank)."""
    sc = SCENARIOS[CELL]
    world = load_bundle_game_data(BUNDLE, with_ge_orders=sc.ge_market,
                                  completed_achievements=frozenset(sc.unlocked_achievements))
    world._ge_sell_orders = {**world._ge_sell_orders, SWORD: ("ord-sword", price, 1)}
    state = replace(scenario_state(sc, world), gold=purse[0], bank_gold=purse[1], bank_items={})
    return world, state, attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)


def _sword(price: int, purse: tuple[int, int] = ROBBY) -> tuple[int, SourceKind | None]:
    world, state, ctx = _sword_book(price, purse)
    return cheapest_route(SWORD, 1, state, world, ctx, None, policy=PIECE_POLICY,
                          pocket=spendable_pocket(state, world, frozenset({SWORD})))


def test_a_huge_fill_loses_to_the_route_that_takes_time() -> None:
    """Robby's shape (live 2026-10-30: `WithdrawGold(90844)` ->
    `GeBuy(mithril_helm)`, about 92,500 gold on one helmet): a 92,500-gold
    order, the bank able to pay it, and a craft that costs a fraction of the
    time 92,500 gold takes to earn. The craft is the route."""
    world, state, ctx = _sword_book(92_500)
    price, route = _sword(92_500)
    assert route is SourceKind.CRAFT
    assert price < 92_500 * gold_spend_actions(state, world, ctx)
    # The same choice whichever purse holds the gold: the route CHOICE charges
    # the pocket's gold and the bank's alike, not only the price.
    assert _sword(92_500, (0, 150_000))[1] is SourceKind.CRAFT
    assert _sword(92_500, (150_000, 0))[1] is SourceKind.CRAFT


def test_a_fill_cheaper_in_time_than_its_alternatives_is_still_bought() -> None:
    """The same order at 50 gold: 50 gold earns back in a sliver of an action,
    far less than the craft's gathers, so the fill is the route."""
    price, route = _sword(50)
    assert route is SourceKind.GE_FILL
    assert price < _sword(92_500)[0]


def test_a_gold_piece_costs_its_earning_time_in_actions() -> None:
    """`gold_spend_actions` is the seconds to earn one gold piece
    (`1 / gold_per_second`) over the learned seconds of one action."""
    world, state, ctx = _sword_book(50)
    rate = gold_per_second(state, world, ctx)
    assert rate > 0
    assert gold_spend_actions(state, world, ctx) == 1 / (rate * ctx.action_seconds_of())


def test_no_grind_target_leaves_spent_gold_unpriceable() -> None:
    """No grind target and no `m*`: no gold rate, and the codebase's answer to
    that (`consumable_price_core.buy_seconds`) is that buying is unpriceable.
    The pricer follows it: a spent gold piece is walled, never priced at an
    invented rate, and a gold-only buy is priced as no route at all."""
    world = _world()
    state = replace(_state(world), gold=50_000)
    assert TIMED_NO_PROFILE_CONTEXT.combat_monster is None
    assert TIMED_NO_PROFILE_CONTEXT.gear_objective is None
    assert gold_spend_actions(state, world, TIMED_NO_PROFILE_CONTEXT) == UNOBTAINABLE_PER_UNIT
    assert acquisition_actions(RUNE.code, 1, state, world, TIMED_NO_PROFILE_CONTEXT,
                               equip=False) == UNOBTAINABLE_PER_UNIT


def test_a_closure_that_spends_no_gold_reads_no_gold_rate() -> None:
    """The rate walks a fight on the objective's fighter. A closure with no
    gold in it never asks: priced on an objective that carries no fighter
    (which the rate refuses), copper ore still prices."""
    world = _world()
    state = _state(world)
    ctx = _crystal_ctx()
    assert ctx.gear_objective is not None and ctx.gear_objective.fighter is None
    with pytest.raises(ValueError, match="no fighter"):
        gold_spend_actions(state, world, ctx)
    assert acquisition_actions("copper_ore", 1, replace(state, inventory={}), world, ctx,
                               equip=False) < UNOBTAINABLE_PER_UNIT


def test_the_grind_target_s_rate_prices_spent_gold() -> None:
    """`LEGACY` offers no gold fight, so the only way the price knows to earn a
    gold piece is the grind target's fight gold per second: the rune from a
    full pocket is the hop, the buy and 20,000 gold at that rate."""
    world = _world()
    state = replace(_state(world), gold=50_000)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, combat_monster="highwayman")
    per_gold = gold_spend_actions(state, world, ctx)
    assert acquisition_actions(RUNE.code, 1, state, world, ctx, equip=False) == \
        2 + ceil(PRICE * per_gold)


def test_a_gold_fight_the_closure_offers_prices_spent_gold() -> None:
    """No grind target, but `PIECE_POLICY` offers gold fights: earning a gold
    piece again takes the cheapest of them, so the held gold is priced at its
    rate rather than walled, and the rune from a full pocket is the hop, the
    buy and 20,000 gold of that fight."""
    world = _world()
    state = replace(_state(world), gold=50_000)
    ctx = TIMED_NO_PROFILE_CONTEXT
    gold = acquisition_options(RUNE.code, state, world, ctx, None, policy=PIECE_POLICY)["gold"]
    per_gold = min(Fraction(r.actions_per_application) / r.yield_per
                   for r in gold if r.kind == SourceKind.GOLD_DROP.value)
    price, route = cheapest_route(RUNE.code, 1, state, world, ctx, None, policy=PIECE_POLICY,
                                  pocket=state.gold)
    assert (price, route) == (2 + ceil(PRICE * per_gold), SourceKind.BUY)


def test_the_objective_prices_a_piece_at_its_own_m_star_s_rate() -> None:
    """While `L*` is being chosen no objective is on the context yet, so each
    candidate's pieces are priced with that candidate's provisional `m*`: the
    rune's piece price is its route's price at `m*`'s gold rate (the pig's,
    cheaper here than any gold fight), plus the equip. The gold is banked, so
    it is SPENT, not fought for: the rate is what prices it."""
    world = _world()
    state = replace(_state(world), bank_gold=50_000, bank_items={})
    ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
    objective = ctx.gear_objective
    assert objective is not None
    gold = acquisition_options(RUNE.code, state, world, ctx, None, policy=PIECE_POLICY)["gold"]
    fight = min(Fraction(r.actions_per_application) / r.yield_per
                for r in gold if r.kind == SourceKind.GOLD_DROP.value)
    assert gold_spend_actions(state, world, ctx) < fight
    piece = next(p for p in objective.missing if p.code == RUNE.code)
    price, _route = cheapest_route(RUNE.code, 1, state, world, ctx, None, policy=PIECE_POLICY,
                                   pocket=spendable_pocket(state, world, frozenset({RUNE.code})))
    assert piece.price == price + 1


# --------------------------------------------------------------------------
# Round 3: an upgrade goal admits a GE fill only when its PRICE took it.
# --------------------------------------------------------------------------

def test_a_robby_shaped_upgrade_does_not_buy_off_the_book() -> None:
    """Live Robby 2026-10-30, on S-046's own commit: root
    `ReachSkillLevel(gearcrafting, 27)`, but the fallback
    `UpgradeEquipment(mithril_helm)` planned `WithdrawGold(90843)` ->
    `GeBuy` -> `Equip`, because the goal admitted any standing order and the
    search prices an edge by its travel. The goal now admits the fill only
    when the item's price takes it (`ge_fill_priced`): with a ~92.5k order
    the craft is the priced route, so no fill and no ferry are admitted, from
    Robby's purse or from a bank that could pay it twice."""
    for purse in ((1736, 91_000), ROBBY):
        world, state, ctx = _sword_book(92_500, purse)
        assert not ge_fill_priced(SWORD, state, world, ctx)
        goal = UpgradeEquipmentGoal(committed_target=(SWORD, "weapon_slot"),
                                    ge_fill=ge_fill_priced(SWORD, state, world, ctx))
        rel = goal.relevant_actions(list(_pool()), state, world)
        assert not [a for a in rel if isinstance(a, GeFillSellOrderAction | WithdrawGoldAction)]
        plan = GOAPPlanner().plan(state, goal, list(_pool()), world, max_nodes=2_000)
        assert not [a for a in plan if isinstance(a, GeFillSellOrderAction | WithdrawGoldAction)]


def test_a_cheap_upgrade_that_pays_for_itself_is_still_bought() -> None:
    """The same order at 50 gold: the fill is the priced route, so the goal
    admits it and the search buys it, the equip after."""
    world, state, ctx = _sword_book(50)
    assert ge_fill_priced(SWORD, state, world, ctx)
    goal = UpgradeEquipmentGoal(committed_target=(SWORD, "weapon_slot"), ge_fill=True)
    plan = GOAPPlanner().plan(state, goal, list(_pool()), world)
    assert [type(a) for a in plan][-2:] == [GeFillSellOrderAction, EquipAction]


def test_a_piece_is_bought_only_by_the_route_that_priced_it() -> None:
    """An `L*` piece answers from its own priced route (plan B Task 3): a
    piece whose price took the fill is bought, one whose price took the craft
    is not, whatever the book offers; and a piece priced at the no-route
    sentinel buys nothing. No standing order, no fill."""
    world, state, ctx = _sword_book(50)

    def priced(route: SourceKind, price: int) -> bool:
        piece = GearPiece("weapon_slot", SWORD, 0, Fraction(1), Fraction(price), route)
        piece_ctx = replace(ctx, gear_objective=GearObjective(
            "pig", {"weapon_slot": SWORD}, Fraction(1), (piece,), fighter=state))
        return ge_fill_priced(SWORD, state, world, piece_ctx)

    assert priced(SourceKind.GE_FILL, 5)
    assert not priced(SourceKind.CRAFT, 5)
    assert not priced(SourceKind.GE_FILL, UNOBTAINABLE_PER_UNIT)
    world._ge_sell_orders = {k: v for k, v in world._ge_sell_orders.items() if k != SWORD}
    assert not priced(SourceKind.GE_FILL, 5)


def test_a_resumed_upgrade_keeps_its_priced_fill() -> None:
    """A committed plan resumed from the store keeps the flag it was priced
    with; a row written before the flag existed buys nothing."""
    for ge_fill in (True, False):
        goal = UpgradeEquipmentGoal(committed_target=("crown", "helmet_slot"), ge_fill=ge_fill)
        data = goal_to_dict(goal)
        assert data is not None
        back = goal_from_dict(data, None)
        assert isinstance(back, UpgradeEquipmentGoal) and back.ge_fill is ge_fill
    legacy = goal_to_dict(UpgradeEquipmentGoal(committed_target=("crown", "helmet_slot")))
    assert legacy is not None
    legacy.pop("ge_fill")
    back = goal_from_dict(legacy, None)
    assert isinstance(back, UpgradeEquipmentGoal) and back.ge_fill is False


def _crown_piece_ctx(hal: WorldState, route: SourceKind) -> SelectionContext:
    piece = GearPiece("helmet_slot", "crown", 0, Fraction(1), Fraction(10), route)
    return replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=GearObjective(
        "pig", {"helmet_slot": "crown"}, Fraction(1), (piece,), fighter=hal))


def test_both_upgrade_producers_ask_the_price_whether_to_buy() -> None:
    """The two places an `UpgradeEquipmentGoal` is built for a target (the
    equippable step's `_equippable_goal`, and the craft-chain root's
    `DoesTheRecipeNeedAMonsterDrop`) both set `ge_fill` from
    `ge_fill_priced`: on HAL's crown, the fill when the piece's price took
    it, none when it took another route, and none with no gold rate to price
    its 6,550 gold at all (the bare context, S-046's unpriceable case)."""
    gd = _crown_gd()
    hal = _hal(gd)
    root = ObtainItem("crown", 1, slot="helmet_slot")
    for ctx, buys in ((_crown_piece_ctx(hal, SourceKind.GE_FILL), True),
                      (_crown_piece_ctx(hal, SourceKind.CRAFT), False),
                      (TIMED_NO_PROFILE_CONTEXT, False)):
        goal = _equippable_goal("crown", "helmet_slot", hal, gd, ctx)
        assert isinstance(goal, UpgradeEquipmentGoal) and goal.ge_fill is buys
        chain = DoesTheRecipeNeedAMonsterDrop(ObtainItem("crown", 1), root,
                                              ["helmet_slot"]).resolve(hal, gd, ctx, None)
        assert isinstance(chain, DoesTheChainFitTheDepthBudget)
        assert chain.upgrade.ge_fill is buys
