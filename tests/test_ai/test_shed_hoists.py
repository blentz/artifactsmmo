"""Part 2 of the disposal-unification epic: the two starved shed rungs.

Defect A of the live diagnosis was that DRAIN_BANK_JUNK and SELL_IDLE fire and
are never selected (44/54 and 32/54 cycles fired, 0 selected) while the bank
grows to 2273 shedable copies. These cases pin all four halves of the fix:

  * the COLLECT-band hoist, CONDITIONAL on there being real work;
  * the snapshot that makes the drain plannable at all (without it the goal
    returns plan_len=0 for any pile deeper than the bag — the second, invisible
    half of the starvation);
  * the sell route's bank arm, which can shed a surplus held ENTIRELY in the
    bank;
  * the per-cycle bound, which stops a 2273-copy hoard being attempted at once.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.accumulation_sell import (
    bank_sellable_surplus,
    worst_bank_accumulation_steps,
)
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.arbiter_select import BAND_COLLECT, BAND_STEP
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.drain_bank_junk import DrainBankJunkGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.shed_urgency import bank_shed_hoist, bank_shed_hoist_pure
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

LIVE_BANK = {"sap": 703, "raw_wolf_meat": 509, "raw_chicken": 272,
             "raw_beef": 161, "gudgeon": 143, "wolf_hair": 124,
             "raw_porkchop": 104}
"""The seven deepest piles of R2D2's real bank (probe 2026-08-05), copy for
copy. 2016 copies against a 120-quantity bag — the shape that makes
all-or-nothing satisfaction unreachable."""

SELL_EVENT = "timber_merchant"
"""`sap`'s only buyer on the committed bundle is an EVENT merchant, so a sell
case must declare its window open or `NpcSellAction.is_applicable` refuses."""


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _ctx(**kw: object) -> SelectionContext:
    base: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=0, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)  # type: ignore[arg-type]


def _state(gd: GameData, *, bank: dict[str, int] | None = None,
           bag: dict[str, int] | None = None,
           events: tuple[str, ...] = (),
           inventory_max: int = 120) -> WorldState:
    return scenario_state(
        ScenarioCharacter(name="shed", level=11,
                          skills={s: 5 for s in SKILL_NAMES},
                          equipment={}, inventory=dict(bag or {}),
                          inventory_max=inventory_max, inventory_slots_max=20,
                          bank=dict(bank or {}), active_events=events),
        gd)


def _drive(gd: GameData, state: WorldState) -> tuple[Goal | None, list]:
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    arbiter.set_cycle(0)
    step = ReachCharLevel(level=12)
    decision = StrategyDecision(interrupt=None, chosen_root=step,
                                chosen_step=step)
    goal, plan, _tried = arbiter.select(decision, state, gd, actions, _ctx())
    return goal, plan


# ── defect A: the drain rung is selectable when there is real work ───────────

def test_drain_rung_is_selected_when_the_bank_holds_a_hoard(gd: GameData) -> None:
    """The whole of defect A, at the production seam. An objective step is in
    scope and plannable — that is exactly the condition under which the traced
    run selected the drain ZERO times in 44 firings."""
    state = _state(gd, bank=LIVE_BANK)
    assert sum(bank_drain_excess(state, gd, _ctx()).values()) > 0
    goal, plan = _drive(gd, state)
    assert repr(goal) == "DrainBankJunk", repr(goal)
    assert plan, "a selected rung that cannot plan is still starved"


def test_drain_rung_is_not_selected_when_nothing_is_licensed(gd: GameData) -> None:
    """The other half of the gate. An unconditional hoist would pass the case
    above and park progression forever, so the QUIET case is what makes the
    liveness case mean something."""
    state = _state(gd, bank={})
    assert bank_drain_excess(state, gd, _ctx()) == {}
    goal, plan = _drive(gd, state)
    assert repr(goal) != "DrainBankJunk"
    assert plan, "no plan at all is a stalled bot, not a quiet rung"


def test_drain_hoist_is_suppressed_under_inventory_pressure(gd: GameData) -> None:
    """The withdraw MINTS copies into the bag, so under space pressure the
    deposit/discard guards own it — the same gate the recycle hoist carries."""
    state = _state(gd, bank=LIVE_BANK, bag={"sap": 40}, inventory_max=45)
    cands = _candidates(gd, state)
    hoisted = [c for c in cands
               if isinstance(c.goal, DrainBankJunkGoal) and c.band == BAND_COLLECT]
    assert not hoisted


def _candidates(gd: GameData, state: WorldState, discretionary=()) -> list:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    return arbiter._build_candidates(
        guard_kinds=[], collect_kinds=[], discretionary_kinds=list(discretionary),
        step_goal=None, fallback_steps=[], fallback_roots=[],
        state=state, game_data=gd, ctx=_ctx())


def test_drain_hoist_lands_in_the_collect_band_above_the_step(gd: GameData) -> None:
    cands = _candidates(gd, _state(gd, bank=LIVE_BANK))
    drains = [c for c in cands if isinstance(c.goal, DrainBankJunkGoal)]
    assert len(drains) == 1
    assert drains[0].band == BAND_COLLECT < BAND_STEP


def test_hoisted_drain_is_deduped_from_the_discretionary_band(gd: GameData) -> None:
    """Two candidates with one repr would give the sticky-commitment machinery
    two goals under one key — and the discretionary twin is the one built
    WITHOUT the hoist's snapshot."""
    cands = _candidates(gd, _state(gd, bank=LIVE_BANK),
                        discretionary=[MeansKind.DRAIN_BANK_JUNK])
    drains = [c for c in cands if isinstance(c.goal, DrainBankJunkGoal)]
    assert len(drains) == 1 and drains[0].band == BAND_COLLECT


def test_sub_bag_load_bank_stock_keeps_the_discretionary_drain(gd: GameData) -> None:
    """Below the hoist threshold the rung stays where it always was, so the
    hoist is genuinely conditional rather than a relocation.

    30 banked `nettle_leaf` in a 120-quantity bag is ORDINARY BANK STOCK — it is
    the `l20_dual_utility` scenario's own bank, and hoisting on it preempted a
    winnable fight while the bag rule was in force."""
    state = _state(gd, bank={"nettle_leaf": 30})
    assert 0 < max(bank_drain_excess(state, gd, _ctx()).values()) < state.inventory_max
    cands = _candidates(gd, state, discretionary=[MeansKind.DRAIN_BANK_JUNK])
    drains = [c for c in cands if isinstance(c.goal, DrainBankJunkGoal)]
    assert len(drains) == 1 and drains[0].band != BAND_COLLECT


def test_bank_hoist_fires_at_exactly_one_bag_load(gd: GameData) -> None:
    """The threshold is the server's own quantity cap, so it moves with the bag
    rather than being a literal."""
    under = _state(gd, bank={"sap": 120})   # keep 1 -> licensed 119 < 120
    over = _state(gd, bank={"sap": 121})    # keep 1 -> licensed 120 == 120
    assert max(bank_drain_excess(under, gd, _ctx()).values()) == under.inventory_max - 1
    assert max(bank_drain_excess(over, gd, _ctx()).values()) == over.inventory_max
    assert not [c for c in _candidates(gd, under)
                if isinstance(c.goal, DrainBankJunkGoal)]
    assert [c for c in _candidates(gd, over)
            if isinstance(c.goal, DrainBankJunkGoal)]


def test_bank_hoist_rule_is_pure_and_refuses_a_zero_capacity_bag() -> None:
    assert not bank_shed_hoist_pure(1_000_000, 0)
    assert not bank_shed_hoist_pure(119, 120)
    assert bank_shed_hoist_pure(120, 120)
    assert not bank_shed_hoist({}, 120)
    assert bank_shed_hoist({"sap": 5, "gudgeon": 200}, 120)


# ── the snapshot: the drain was UNPLANNABLE, not merely outranked ────────────

def test_all_or_nothing_drain_cannot_plan_a_deep_pile(gd: GameData) -> None:
    """Regression pin for the second half of the starvation. `initial_total=None`
    is the pre-part-2 goal, and the planner refuses STRUCTURALLY — not on a
    timeout — because emptying the licence needs every copy in the bag at once."""
    state = _state(gd, bank=LIVE_BANK)
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    planner = GOAPPlanner()
    assert planner.plan(state, goal, actions, gd, budget_seconds=10.0) == []
    assert planner.last_stats is not None and not planner.last_stats.timed_out


def test_snapshot_makes_one_batch_a_complete_plan(gd: GameData) -> None:
    state = _state(gd, bank=LIVE_BANK)
    total = sum(bank_drain_excess(state, gd, _ctx()).values())
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             initial_total=total)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)
    assert len(plan) == 1 and isinstance(plan[0], WithdrawItemAction)


def test_snapshot_satisfies_on_any_reduction(gd: GameData) -> None:
    state = _state(gd, bank=LIVE_BANK)
    total = sum(bank_drain_excess(state, gd, _ctx()).values())
    goal = DrainBankJunkGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             initial_total=total)
    assert not goal.is_satisfied(state)
    smaller = _state(gd, bank={**LIVE_BANK, "sap": 500})
    assert goal.is_satisfied(smaller)
    assert goal.is_satisfied(_state(gd, bank={}))  # nothing licensed at all


# ── the per-cycle bound ──────────────────────────────────────────────────────

def test_drain_episode_does_not_attempt_the_whole_hoard(gd: GameData) -> None:
    """2016 licensed copies, a 120-quantity bag: the episode withdraws ONE
    bag-load and one action, not the pile."""
    state = _state(gd, bank=LIVE_BANK)
    licensed = sum(bank_drain_excess(state, gd, _ctx()).values())
    assert licensed > 1900
    _goal, plan = _drive(gd, state)
    withdrawn = sum(a.quantity for a in plan if isinstance(a, WithdrawItemAction))
    assert 0 < withdrawn <= state.inventory_free
    assert withdrawn < licensed


def test_sell_episode_does_not_attempt_the_whole_hoard(gd: GameData) -> None:
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    licensed = sum(bank_sellable_surplus(state, gd, _ctx()).values())
    assert licensed > 700
    _goal, plan = _drive(gd, state)
    withdrawn = sum(a.quantity for a in plan if isinstance(a, WithdrawItemAction))
    assert 0 < withdrawn <= state.inventory_free < licensed


# ── the sell route's bank arm ────────────────────────────────────────────────

def test_bank_sellable_surplus_sees_a_pile_held_only_in_the_bank(gd: GameData) -> None:
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    assert state.inventory == {}
    assert bank_sellable_surplus(state, gd, _ctx()) == {"sap": 702}


def test_bank_sellable_surplus_excludes_codes_no_one_buys(gd: GameData) -> None:
    """The bank arm is the DRAIN's licence FILTERED by sellability. Without the
    filter it would offer `ash_plank` — which no NPC buys on the committed
    catalog — and the sell rung would be the drain under another name."""
    assert gd.npcs_buying_item("ash_plank") == []
    state = _state(gd, bank={"sap": 703, "ash_plank": 400},
                   events=(SELL_EVENT,))
    assert set(bank_drain_excess(state, gd, _ctx())) == {"sap", "ash_plank"}
    assert set(bank_sellable_surplus(state, gd, _ctx())) == {"sap"}


def test_owned_progress_metric_is_unmoved_by_a_withdraw(gd: GameData) -> None:
    """The defining property of the bank arm's bound. A metric over the BANK
    alone would count a bare `Withdraw` as progress and satisfy the goal one
    action short of the sale it exists for; counting bag PLUS bank means only an
    actual alienation moves it."""
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             state=state)
    before = goal._owned_snapshot_total(state)
    assert before == 703
    landed = WithdrawItemAction(code="sap", quantity=120,
                                bank_location=gd.bank_location_or_none or (0, 0),
                                accessible=True).apply(state, gd)
    assert goal._owned_snapshot_total(landed) == before
    sold = NpcSellAction(npc_code="timber_merchant", item_code="sap",
                         quantity=120,
                         npc_location=gd.npc_location("timber_merchant")
                         ).apply(landed, gd)
    assert goal._owned_snapshot_total(sold) < before


def test_sell_plan_stages_withdraw_before_the_sale(gd: GameData) -> None:
    """The bag holds ZERO copies, so the sale is reachable only through the
    staged withdraw the bank arm adds."""
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    goal, plan = _drive(gd, state)
    assert repr(goal) == "SellInventory", repr(goal)
    kinds = [type(a) for a in plan]
    assert kinds.index(WithdrawItemAction) < kinds.index(NpcSellAction)


def test_bank_arm_declines_when_no_buyer_can_take_the_copies(gd: GameData) -> None:
    """`_is_sellable` only asks whether a buyer has a TILE; the merchant may
    still be dormant. A bare withdraw would be the DRAIN rung wearing a sell
    hat, so the arm offers nothing at all."""
    state = _state(gd, bank={"sap": 703})  # merchant window CLOSED
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             state=state)
    assert bank_sellable_surplus(state, gd, _ctx()) == {"sap": 702}
    assert goal.relevant_actions([], state, gd) == []
    assert goal.is_satisfied(state)


def test_bank_arm_is_inert_without_the_snapshot(gd: GameData) -> None:
    """Every pre-existing call site builds the goal without `state=` and must
    keep its bag-only behaviour — an unsnapshotted arm has no termination
    bound."""
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True)
    assert goal.relevant_actions([], state, gd) == []
    assert goal.is_satisfied(state)


def test_bank_arm_is_inert_when_the_bank_is_locked(gd: GameData) -> None:
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=False,
                             state=state)
    assert goal.relevant_actions([], state, gd) == []


def test_bank_arm_declines_when_the_bag_has_no_free_slot(gd: GameData) -> None:
    """SLOT room, not just quantity room. A bag with every stack occupied cannot
    receive a NEW code at any quantity (`inventory_room.has_room`), so the arm
    probes down to zero and offers nothing rather than a Withdraw that would
    HTTP 497."""
    state = scenario_state(
        ScenarioCharacter(name="shed", level=11,
                          skills={s: 5 for s in SKILL_NAMES}, equipment={},
                          inventory={"copper_ore": 1, "ash_wood": 1},
                          inventory_max=1000, inventory_slots_max=2,
                          bank={"sap": 703}, active_events=(SELL_EVENT,)),
        gd)
    assert state.inventory_slots_free == 0 and state.inventory_free > 0
    assert bank_sellable_surplus(state, gd, _ctx()) == {"sap": 702}
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             state=state)
    assert goal.relevant_actions([], state, gd) == []


def test_bank_arm_skips_a_higher_priced_buyer_with_no_tile(gd: GameData) -> None:
    """Buyers are walked in PRICE order, and the best price may belong to a
    merchant with no tile at all — `NpcSellAction.is_applicable` refuses it, so
    the arm must fall through to the next buyer rather than give up."""
    clone = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    clone.world.npc_sell_prices["ghost_merchant"] = {"sap": 9999}
    assert clone.npcs_buying_item("sap")[0][0] == "ghost_merchant"
    assert clone.npc_location("ghost_merchant") is None
    state = _state(clone, bank={"sap": 703}, events=(SELL_EVENT,))
    goal = SellInventoryGoal(game_data=clone, ctx=_ctx(), bank_accessible=True,
                             state=state)
    actions = goal.relevant_actions([], state, clone)
    sales = [a for a in actions if isinstance(a, NpcSellAction)]
    assert [a.npc_code for a in sales] == ["timber_merchant"]


def test_sell_value_sees_a_bank_only_hoard(gd: GameData) -> None:
    """Bag-only `value()` scored the live 703-sap pile 0.0 — a false story about
    the rung the bank arm exists to feed."""
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             state=state)
    assert worst_bank_accumulation_steps(state, gd, _ctx()) > 0
    assert goal.value(state, gd) > 0.0


def test_sell_value_is_zero_with_nothing_to_sell(gd: GameData) -> None:
    state = _state(gd, bank={})
    goal = SellInventoryGoal(game_data=gd, ctx=_ctx(), bank_accessible=True,
                             state=state)
    assert worst_bank_accumulation_steps(state, gd, _ctx()) == 0
    assert goal.value(state, gd) == 0.0


def test_sell_hoist_lands_in_the_collect_band(gd: GameData) -> None:
    state = _state(gd, bank={"sap": 703}, events=(SELL_EVENT,))
    cands = _candidates(gd, state, discretionary=[MeansKind.SELL_IDLE])
    sells = [c for c in cands if isinstance(c.goal, SellInventoryGoal)]
    assert len(sells) == 1 and sells[0].band == BAND_COLLECT


def test_sell_hoist_stands_down_with_no_licensed_surplus(gd: GameData) -> None:
    state = _state(gd, bank={}, events=(SELL_EVENT,))
    cands = _candidates(gd, state, discretionary=[MeansKind.SELL_IDLE])
    sells = [c for c in cands if isinstance(c.goal, SellInventoryGoal)]
    assert len(sells) == 1 and sells[0].band != BAND_COLLECT


# ── part 1's invariant still holds with the hoist live ───────────────────────

def test_no_code_is_both_drained_and_still_under_its_bank_cap(gd: GameData) -> None:
    """`drained > 0 ⇒ route != DEPOSIT`, end to end on the live pile, in the
    state the hoisted drain ACTUALLY produces (post-withdraw) as well as before
    it — the `withdrawn_is_never_redeposited` half."""
    from artifactsmmo_cli.ai.inventory_keep import destroyable
    from artifactsmmo_cli.ai.keep_valuation import (
        bank_quantity,
        bank_under_cap_pure,
        drain_licensed_pure,
        worth_keeping,
    )

    def _check(state: WorldState) -> int:
        seen = 0
        for code in state.bank_items or {}:
            keep = worth_keeping(code, state, gd, _ctx())
            bank_qty = bank_quantity(code, state)
            drained = drain_licensed_pure(
                destroyable(code, state, gd, _ctx()), keep, bank_qty)
            if drained <= 0:
                continue
            seen += 1
            assert not bank_under_cap_pure(keep, bank_qty), code
        return seen

    state = _state(gd, bank=LIVE_BANK)
    assert _check(state) == len(LIVE_BANK)
    _goal, plan = _drive(gd, state)
    for action in plan:
        state = action.apply(state, gd)
    assert _check(state) > 0
