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

import pytest

from artifactsmmo_cli.ai.acquisition_cost import cheapest_route
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction, gold_ferry
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.post_buy_bid import PostBuyBidGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, PIECE_POLICY
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.progression_reserve import reserve_floor_multi, spendable_pocket
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.source_kind import SourceKind
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
    return UpgradeEquipmentGoal(committed_target=("crown", "helmet_slot"))


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


def test_the_price_charges_the_withdraw_not_the_fights() -> None:
    """The `L*` rune (20,000 gold at the rune vendor) from a 100-gold pocket:
    with the gold banked, the price is the buy and the withdraw, each with its
    hop. One withdraw moves any amount, so the route CHOICE prices a unit of
    banked gold at a sliver of one action; rounded up to a whole action a gold
    piece it would lose to a fight and the price would fight for 19,900 gold."""
    world = _world()
    poor = _state(world)
    assert poor.gold == 100
    rich = replace(poor, bank_gold=50_000, bank_items={})
    ctx = attached(rich, world, TIMED_NO_PROFILE_CONTEXT, None)

    def price(state: WorldState) -> tuple[int, SourceKind | None]:
        return cheapest_route(RUNE.code, 1, state, world, ctx, None, policy=PIECE_POLICY,
                              pocket=spendable_pocket(state, world, frozenset({RUNE.code})))

    assert price(rich) == (4, SourceKind.BUY)
    fought, _route = price(replace(rich, bank_gold=None))
    assert fought > 1000


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
    plan = decompose(goal, short, world, actions, _crystal_ctx())
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
    plan = decompose(goal, short, world, actions, _crystal_ctx())
    assert plan is not None
    assert not [a for a in plan if isinstance(a, GeFillSellOrderAction | WithdrawGoldAction)]
