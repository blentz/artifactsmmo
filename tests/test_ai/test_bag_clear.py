"""Task 13e: a full bag frees every slot the plan does not use, then retries
(USER 2026-10-25, binding: "free up all in-use inventory slots that aren't
related to the current plan, then retry the plan once the full inventory state
is cleared").

The live shape (R2D2 from 2026-10-22T19:02Z): 20 of 20 slots used, 119/172 by
quantity, HP_CRITICAL won the ladder and RestoreHP planned
`Craft(cooked_porkchop×1)` — a new stack with nowhere to land — and drew HTTP
497 on 2,772 consecutive cycles while DEPOSIT_FULL fired below it."""

import time
from dataclasses import replace

import pytest

import artifactsmmo_cli.ai.bag_clear as bag_clear_mod
import artifactsmmo_cli.ai.strategy_driver as strategy_driver_mod
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.arbiter_select import BAND_STEP, Candidate
from artifactsmmo_cli.ai.bag_clear import (
    BAG_FULL_OUTCOME,
    ClearPlan,
    clear_actions,
    cleared_state,
    needs_slot,
    plan_codes,
    related_codes,
)
from artifactsmmo_cli.ai.bag_clear_core import (
    BAG_FULL_ALL_RELATED,
    ClearRoute,
    clear_route,
)
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.scenarios.test_slot_coverage import BUNDLE

# R2D2's live bag on 2026-10-26, less the 20th slot (`raw_porkchop`, below).
JUNK = {
    "skull_amulet": 3, "skeleton_helmet": 1, "hardwood_plank": 7, "wolf_bone": 3,
    "skeleton_bone": 11, "sapphire_stone": 2, "topaz_stone": 1, "event_ticket": 3,
    "owlbear_hair": 18, "owlbear_claw": 16, "birch_wood": 10, "wolf_hair": 2,
    "lich_tomb_key": 1, "king_slimeball": 2, "skeleton_skull": 3, "pig_skin": 3,
    "iron_ore": 12, "ruby_stone": 1, "coal": 1,
}


@pytest.fixture(scope="module")
def gd() -> GameData:
    return load_bundle_game_data(BUNDLE)


def _r2d2(inventory: dict[str, int] | None = None, slots_max: int = 20,
          bank: dict[str, int] | None = None) -> ScenarioCharacter:
    bag = inventory if inventory is not None else {"raw_porkchop": 19, **JUNK}
    return ScenarioCharacter(
        name="r2d2", level=37, hp=100, max_hp=900, skills={"cooking": 30},
        inventory=bag, inventory_max=172, inventory_slots_max=slots_max,
        bank={} if bank is None else bank, derive_combat_stats=True,
        description="R2D2 2026-10-22: every slot used, quantity room, HP low.")


def _player(gd: GameData, sc: ScenarioCharacter) -> GamePlayer:
    player = GamePlayer(character=sc.name, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(scenario_state(sc, gd), gd)
    return player


def _no_rest(player: GamePlayer, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pool without Rest, so RestoreHP's only heal is the porkchop craft —
    the live plan (`Craft(cooked_porkchop×1)`), whatever the clear's walk to
    the bank does to Rest's relative cost."""
    build = player._build_actions
    monkeypatch.setattr(player, "_build_actions",
                        lambda: [a for a in build() if not isinstance(a, RestAction)])


def _deposit(gd: GameData) -> DepositAllAction:
    return DepositAllAction(bank_location=gd.bank_location(), accessible=True, game_data=gd)


def _craft(gd: GameData) -> CraftAction:
    return CraftAction(code="cooked_porkchop", quantity=1,
                       workshop_location=gd.workshop_location("cooking"))


def _ctx() -> SelectionContext:
    return TIMED_NO_PROFILE_CONTEXT


# --------------------------------------------------------------------------
# The pure core (mirrored in formal/Formal/BagClear.lean)
# --------------------------------------------------------------------------

def test_a_related_stack_is_kept_whatever_the_bank_says() -> None:
    assert clear_route(True, True, True) is ClearRoute.KEEP


def test_the_bank_comes_before_any_disposal() -> None:
    assert clear_route(False, True, True) is ClearRoute.DEPOSIT


def test_a_bank_refusal_disposes_of_a_licensed_stack() -> None:
    assert clear_route(False, False, True) is ClearRoute.DISPOSE


def test_an_unmovable_unrelated_stack_stays() -> None:
    assert clear_route(False, False, False) is ClearRoute.KEEP


# --------------------------------------------------------------------------
# The trigger
# --------------------------------------------------------------------------

def test_a_new_stack_into_a_full_bag_needs_a_slot(gd: GameData) -> None:
    state = scenario_state(_r2d2(), gd)
    assert state.inventory_slots_free == 0 and state.inventory_free > 0
    assert needs_slot([_craft(gd)], state, gd)


def test_a_new_stack_with_a_free_slot_fits(gd: GameData) -> None:
    state = scenario_state(_r2d2(slots_max=21), gd)
    assert not needs_slot([_craft(gd)], state, gd)


def test_the_walk_stops_at_a_fight(gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fight's modelled loot (one of every drop: four new stacks for a
    chicken) is optimistic, so the walk stops there instead of judging it, or
    the craft behind it; the fight's own room is `refused_fight`'s."""
    state = scenario_state(_r2d2(slots_max=21), gd)
    monkeypatch.setattr(FightAction, "is_applicable", lambda self, s, g: True)
    fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}),
                        learned_drops=LearnedDrops.empty())
    assert len(fight.apply(state, gd).inventory) > state.inventory_slots_max  # the optimism
    assert not needs_slot([fight, _craft(gd)], state, gd)


def test_plan_codes_are_what_the_steps_consume_and_produce(gd: GameData) -> None:
    state = scenario_state(_r2d2(), gd)
    plan = [_craft(gd)]
    assert plan_codes(plan, state, gd) == {"raw_porkchop", "cooked_porkchop"}


# --------------------------------------------------------------------------
# The related set and the clear
# --------------------------------------------------------------------------

def test_related_items_are_never_shed(gd: GameData) -> None:
    """Plan inputs, root-closure materials and keep-authority items stay."""
    state = scenario_state(_r2d2(), gd)
    plan = [_craft(gd)]
    ctx = replace(_ctx(), step_profile={"owlbear_hair": 1},       # GOAL_MATERIALS keeps one
                  root_closure=frozenset({"iron_ore", "coal"}))   # a steel_bar root
    related = related_codes(plan, state, gd, ctx)
    assert {"raw_porkchop", "iron_ore", "coal", "owlbear_hair"} <= related
    clear = clear_actions(state, gd, [_deposit(gd)], ctx, related)
    after = cleared_state(clear.actions, state, gd)
    for code in ("raw_porkchop", "iron_ore", "coal", "owlbear_hair"):
        assert after.inventory[code] == state.inventory[code], code
    # Everything else left the bag, all of it at once, in one DepositAll.
    assert [type(a) for a in clear.actions] == [DepositAllAction]
    assert set(after.inventory) == {"raw_porkchop", "iron_ore", "coal", "owlbear_hair"}
    assert clear.freed == 16


def test_the_equipped_codes_are_related(gd: GameData) -> None:
    state = replace(scenario_state(_r2d2(), gd),
                    equipment={**scenario_state(_r2d2(), gd).equipment, "weapon_slot": "iron_sword"})
    assert "iron_sword" in related_codes([], state, gd, _ctx())


def test_no_bank_in_the_pool_and_no_licence_frees_nothing(gd: GameData) -> None:
    """Without a deposit and with every unrelated stack still wanted
    (`destroyable` below the held stack), nothing can leave."""
    state = scenario_state(_r2d2(inventory={"raw_porkchop": 19, "event_ticket": 3}, slots_max=2), gd)
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [], _ctx(), related) == ClearPlan(actions=(), freed=0)


def test_a_full_bank_routes_the_licensed_junk_through_the_junk_policy(gd: GameData) -> None:
    """Bank full (50 of 50 codes, none of the bag's): the deposit takes
    nothing, so each unrelated stack the keep authority licenses WHOLE goes
    through `disposal_route`; a stack it still wants (`event_ticket`, kept
    owned) stays."""
    bank = {f"filler_{i}": 1 for i in range(gd.bank_capacity)}
    bag = {"raw_porkchop": 19, "lich_tomb_key": 1, "event_ticket": 3}
    state = scenario_state(_r2d2(inventory=bag, slots_max=3, bank=bank), gd)
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    clear = clear_actions(state, gd, [_deposit(gd)], _ctx(), related)
    assert clear == ClearPlan(actions=(DeleteItemAction(code="lich_tomb_key", quantity=1),), freed=1)
    after = cleared_state(clear.actions, state, gd)
    assert set(after.inventory) == {"raw_porkchop", "event_ticket"}


def test_a_disposal_that_leaves_copies_frees_no_slot(gd: GameData) -> None:
    """A stack the keep authority still wants owned (`destroyable` below the
    held stack) is not disposed of, so it frees no slot."""
    bank = {f"filler_{i}": 1 for i in range(gd.bank_capacity)}
    bag = {"raw_porkchop": 19, "copper_dagger": 5}
    state = scenario_state(_r2d2(inventory=bag, slots_max=2, bank=bank), gd)
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [_deposit(gd)], _ctx(), related).freed == 0


def test_a_partial_disposal_frees_no_slot(gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """The junk policy sized below the stack (a RECYCLE whose minted materials
    did not fit) leaves copies, so it frees no slot and is no clear."""
    bank = {f"filler_{i}": 1 for i in range(gd.bank_capacity)}
    bag = {"raw_porkchop": 19, "lich_tomb_key": 2}
    state = scenario_state(_r2d2(inventory=bag, slots_max=2, bank=bank), gd)
    monkeypatch.setattr(bag_clear_mod, "overstock_disposal",
                        lambda code, qty, *_: DeleteItemAction(code=code, quantity=qty - 1))
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [_deposit(gd)], _ctx(), related) == ClearPlan(actions=(), freed=0)


def test_a_slot_gated_step_needs_the_slot_it_is_refused(gd: GameData) -> None:
    """A withdraw of a code not held is refused by its own room check on the
    full bag and admitted with an emptied one: that is a slot need."""
    state = scenario_state(_r2d2(bank={"steel_bar": 40}), gd)
    withdraw = WithdrawItemAction(code="steel_bar", quantity=4, bank_location=gd.bank_location())
    assert not withdraw.is_applicable(state, gd)
    assert needs_slot([withdraw], state, gd)
    # A step refused for another reason (nothing banked) is no slot need.
    absent = WithdrawItemAction(code="gold_bar", quantity=4, bank_location=gd.bank_location())
    assert not needs_slot([absent], state, gd)


def test_an_equip_unblocks_through_the_clear(gd: GameData) -> None:
    """Equipping a held helmet over a worn one returns the worn piece to the
    bag: a new stack the full bag has no slot for. The clear keeps both
    helmets and makes the room."""
    base = scenario_state(_r2d2(), gd)
    bag = {**{k: v for k, v in base.inventory.items() if k != "raw_porkchop"}, "iron_helm": 2}
    state = replace(base, inventory=bag, inventory_slots_max=len(bag),
                    equipment={**base.equipment, "helmet_slot": "copper_helmet"})
    equip = EquipAction(code="iron_helm", slot="helmet_slot")
    assert not equip.is_applicable(state, gd)
    assert needs_slot([equip], state, gd)
    related = related_codes([equip], state, gd, _ctx())
    assert {"iron_helm", "copper_helmet"} <= related
    after = cleared_state(clear_actions(state, gd, [_deposit(gd)], _ctx(), related).actions,
                          state, gd)
    assert after.inventory["iron_helm"] == 2
    assert equip.is_applicable(after, gd)


# --------------------------------------------------------------------------
# The arbiter: clear, then retry the same goal
# --------------------------------------------------------------------------

def test_a_full_bag_clears_every_unrelated_slot_then_retries(
        gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    player = _player(gd, _r2d2())
    _no_rest(player, monkeypatch)
    report = player.plan_from_state()
    assert isinstance(report.selected_goal, RestoreHPGoal)
    assert isinstance(report.plan[0], DepositAllAction), report.plan
    assert player.state is not None
    after = cleared_state(report.plan[:1], player.state, gd)
    # Every unrelated code banked; exactly the porkchop inputs stay.
    assert after.inventory == {"raw_porkchop": 19}
    # ...and then the plan the live bot was 497ing on: it crafts and eats.
    rest = report.plan[1:]
    assert any(isinstance(a, CraftAction) and a.code == "cooked_porkchop" for a in rest), rest
    assert any(isinstance(a, UseConsumableAction) for a in rest), rest
    assert not needs_slot(report.plan, player.state, gd)
    events = player._arbiter.events.drain()
    assert (Mechanism.BAG_CLEAR, "RestoreHP") in [(m, s) for m, s, _ in events]
    # The goal that ran is recorded with the plan it emitted.
    tried = {g["goal"]: g for g in report.goals_tried}
    assert tried["RestoreHP"]["plan_len"] == len(report.plan)


def test_a_497_triggers_the_clear(gd: GameData) -> None:
    """The model believes there is room; the server's 497 overrides it. The
    goal is unchanged and its retry follows the clear."""
    player = _player(gd, _r2d2(slots_max=30))
    assert player.state is not None and player.state.inventory_slots_free > 0
    calm = player.plan_from_state()
    assert not isinstance(calm.plan[0], DepositAllAction), calm.plan
    player._last_outcome = BAG_FULL_OUTCOME
    report = player.plan_from_state()
    assert repr(report.selected_goal) == repr(calm.selected_goal) == "RestoreHP"
    assert isinstance(report.plan[0], DepositAllAction), report.plan
    assert len(report.plan) > 1, report.plan
    assert not any(isinstance(a, DepositAllAction) for a in report.plan[1:]), report.plan


def test_all_related_full_bag_is_named(gd: GameData) -> None:
    """Every stack is related, so nothing can free the slot the craft needs:
    the plan is dropped (no silent retry), and the verdict is named in the
    events and on the arbiter."""
    bag = {"raw_porkchop": 19}
    state = scenario_state(_r2d2(inventory=bag, slots_max=1), gd)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    goal = RestoreHPGoal()
    craft = [_craft(gd)]
    assert arbiter._clear_bag(goal, craft, state, gd, [_deposit(gd)], _ctx()) == []
    assert arbiter.last_bag_verdict == BAG_FULL_ALL_RELATED
    assert arbiter.events.drain() == [
        (Mechanism.BAG_FULL_ALL_RELATED, "RestoreHP", "held=1 related=1")]


def test_a_497_with_nothing_freeable_is_dropped(gd: GameData) -> None:
    """The model believes the craft fits, the server said 497, and every
    stack is related: the plan is DROPPED like the predictive case, so another
    goal runs instead of a repeated 497 (ruling T13e-c)."""
    state = scenario_state(_r2d2(inventory={"raw_porkchop": 19}, slots_max=2), gd)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    craft = [_craft(gd)]
    assert not needs_slot(craft, state, gd)
    refused = replace(_ctx(), bag_refused=True)
    assert arbiter._clear_bag(RestoreHPGoal(), craft, state, gd, [_deposit(gd)], refused) == []
    assert arbiter.last_bag_verdict == BAG_FULL_ALL_RELATED


def _climb(gd: GameData) -> tuple[GamePlayer, ReachSkillGoal]:
    """The live gearcrafting climb whose first leg is `Withdraw(steel_bar×4)`."""
    sc = replace(_r2d2(bank={"steel_bar": 40}), hp=900,
                 skills={"cooking": 30, "gearcrafting": 20, "mining": 30})
    return _player(gd, sc), ReachSkillGoal(skill_name="gearcrafting", target_level=24)


def test_a_withdraw_the_full_bag_refuses_is_cleared_then_runs(gd: GameData) -> None:
    """Ruling T13e-a: the gear climb's fast path declines
    `first_leg_inapplicable:Withdraw(steel_bar×4)` on the full bag, so the goal
    has NO plan. Through the arbiter's walk the clear fires anyway (the plan
    the climb takes with an emptied bag needs the slot), and the climb is
    re-planned behind it: the clear, then the withdraw."""
    player, goal = _climb(gd)
    assert player.state is not None
    arbiter = player._arbiter
    actions = player._build_actions()
    ctx = player._selection_context()
    chosen, plan, _ = arbiter._arbitrate(
        [Candidate(goal=goal, repr_=repr(goal), band=BAND_STEP)],
        player.state, gd, actions, ctx)
    assert chosen is goal
    assert isinstance(plan[0], DepositAllAction), plan
    assert plan[1] == WithdrawItemAction(code="steel_bar", quantity=4,
                                         bank_location=gd.bank_location()), plan
    events = arbiter.events.drain()
    assert (Mechanism.DECOMPOSE_DECLINE, repr(goal),
            "first_leg_inapplicable:Withdraw(steel_bar×4)") in events
    assert [e for e in events if e[0] is Mechanism.BAG_CLEAR]
    after = cleared_state(plan[:1], player.state, gd)
    # The climb's own materials stay (its skeleton_armor craft), the rest left.
    assert set(after.inventory) == {"wolf_bone", "skeleton_bone", "pig_skin"}
    assert arbiter.goals_tried[-1]["plan_len"] == len(plan)


def test_an_empty_plan_not_stopped_by_the_bag_is_not_cleared(gd: GameData) -> None:
    """A goal with no plan for any other reason (no slot decline, no search
    on a full bag) is left alone."""
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    state = scenario_state(_r2d2(), gd)
    refused = replace(_ctx(), bag_refused=True)
    assert arbiter._clear_bag(RestoreHPGoal(), [], state, gd, [_deposit(gd)], refused) == []
    assert arbiter.events.drain() == []


def test_a_slot_decline_the_emptied_bag_cannot_serve_is_not_cleared(gd: GameData) -> None:
    """A slot-shaped decline whose goal does not plan with an emptied bag
    either is the goal's answer, not a slot block."""
    player, goal = _climb(gd)
    assert player.state is not None
    arbiter = player._arbiter
    arbiter._attempt_declined = ["first_leg_inapplicable:Fight(x)"]
    no_bank = [a for a in player._build_actions() if not isinstance(a, WithdrawItemAction)]
    nothing = replace(player.state, bank_items={})
    assert arbiter._slot_blocked_plan(goal, nothing, gd, no_bank,
                                      player._selection_context()) is None


def test_a_search_on_a_full_bag_is_asked_with_room(gd: GameData,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """A* found nothing on a bag with no free slot: the roomy plan is asked."""
    player, goal = _climb(gd)
    assert player.state is not None
    arbiter = player._arbiter
    arbiter._attempt_declined = []
    arbiter._attempt_searched = True
    intended = arbiter._slot_blocked_plan(goal, player.state, gd, player._build_actions(),
                                          player._selection_context())
    assert intended is not None and isinstance(intended[0], WithdrawItemAction)
    # ...and asked quietly: no attempt record, no event.
    assert arbiter.goals_tried == [] and arbiter.events.drain() == []
    # A search on a bag WITH a free slot is not a slot block. (Each ask re-arms
    # the attempt's facts: the quiet roomy ask is itself an attempt of `_plans`.)
    roomier = replace(player.state, inventory_slots_max=21)
    arbiter._attempt_declined, arbiter._attempt_searched = [], True
    assert arbiter._slot_blocked_plan(goal, roomier, gd, player._build_actions(),
                                      player._selection_context()) is None
    # ...even when the emptied-bag plan would need more slots than the one
    # free: an empty search re-asks only a bag with NO free slot (the extra
    # search is bounded to the bag the clear exists for).
    two = [WithdrawItemAction(code="steel_bar", quantity=1, bank_location=gd.bank_location()),
           WithdrawItemAction(code="iron_bar", quantity=1, bank_location=gd.bank_location())]
    stocked = replace(roomier, bank_items={"steel_bar": 1, "iron_bar": 1})
    assert needs_slot(two, stocked, gd)
    monkeypatch.setattr(arbiter, "_plans", lambda *a, **k: two)
    arbiter._attempt_declined, arbiter._attempt_searched = [], True
    assert arbiter._slot_blocked_plan(goal, stocked, gd, player._build_actions(),
                                      player._selection_context()) is None
    monkeypatch.undo()
    # A slot decline whose emptied-bag plan fits the real bag is no slot block.
    arbiter._attempt_searched = False
    arbiter._attempt_declined = ["bag_overflow:qty=1/1:slots=1/1"]
    assert arbiter._slot_blocked_plan(goal, roomier, gd, player._build_actions(),
                                      player._selection_context()) is None


def test_a_retry_that_still_needs_a_slot_is_not_emitted(
        gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry is re-checked with `needs_slot`: a retry the clear did not
    make room for is dropped, and the clear runs alone."""
    state = scenario_state(_r2d2(), gd)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    craft = [_craft(gd)]
    doomed = [_craft(gd) for _ in range(30)]
    budgets: list[float | None] = []

    def plans(goal: object, state: object, gd: object, actions: object, ctx: object,
              budget: float | None = None) -> list[CraftAction]:
        budgets.append(budget)
        arbiter.goals_tried.append({"goal": "RestoreHP", "plan_len": len(doomed)})
        return doomed

    monkeypatch.setattr(arbiter, "_plans", plans)
    arbiter.set_planning_deadline(time.monotonic() - 5.0)  # the window is spent
    monkeypatch.setattr(strategy_driver_mod, "needs_slot",
                        lambda plan, *_: plan is doomed or plan is craft)
    plan = arbiter._clear_bag(RestoreHPGoal(), craft, state, gd, [_deposit(gd)], _ctx())
    assert [type(a) for a in plan] == [DepositAllAction]
    assert arbiter.goals_tried[-1]["plan_len"] == 1
    # The retry searched what was LEFT of the window, not a second floor.
    assert budgets == [0.0]


def test_the_retry_searches_only_the_remaining_window(gd: GameData) -> None:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    assert arbiter._remaining_budget_seconds() is None
    arbiter.set_planning_deadline(time.monotonic() - 5.0)
    assert arbiter._remaining_budget_seconds() == 0.0
    arbiter.set_planning_deadline(time.monotonic() + 30.0)
    left = arbiter._remaining_budget_seconds()
    assert left is not None and 29.0 < left <= 30.0


def test_the_verdict_reaches_the_log(gd: GameData, monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    player = _player(gd, _r2d2(inventory={"raw_porkchop": 19}, slots_max=1))
    assert player.state is not None and player.game_data is not None
    arbiter = player._arbiter

    def select(*args: object, **kwargs: object) -> tuple[None, list[object], list[object]]:
        arbiter.last_bag_verdict = BAG_FULL_ALL_RELATED
        return None, [], []

    monkeypatch.setattr(arbiter, "select", select)
    player._decide_band(player.state, player.game_data, player._build_actions())
    assert f"[bag] {BAG_FULL_ALL_RELATED}" in capsys.readouterr().out


def test_the_player_reads_the_497_into_the_context(gd: GameData) -> None:
    player = _player(gd, _r2d2())
    assert player._selection_context().bag_refused is False
    player._last_outcome = BAG_FULL_OUTCOME
    assert player._selection_context().bag_refused is True
    player._last_outcome = "error:HTTP_499"
    assert player._selection_context().bag_refused is False


def test_the_arbiter_binds_the_root_closure(gd: GameData) -> None:
    """The chosen root's closure rides the ctx into the clear's related set."""
    player = _player(gd, _r2d2())
    report = player.plan_from_state()
    assert report.plan
    root = ObtainItem(code="steel_bar", quantity=1)
    arbiter = player._arbiter
    seen: list[frozenset[str]] = []
    real = arbiter._arbitrate

    def spy(candidates: object, state: object, game_data: object, actions: object,
            ctx: SelectionContext) -> object:
        seen.append(ctx.root_closure)
        return real(candidates, state, game_data, actions, ctx)  # type: ignore[arg-type]

    arbiter._arbitrate = spy  # type: ignore[method-assign]
    assert player.state is not None
    decision = StrategyDecision(interrupt=None, chosen_root=root, chosen_step=root)
    arbiter.select(decision, player.state, gd, player._build_actions(), player._selection_context())
    assert seen == [frozenset({"steel_bar", "iron_ore", "coal"})]


def _plan(player: GamePlayer) -> PlanReport:
    return player.plan_from_state()


def test_two_cycles_clear_then_the_original_goal(
        gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cycle 1 clears; cycle 2, on the cleared bag, runs the original goal's
    plan with room for it — never two 497-doomed actions in a row."""
    player = _player(gd, _r2d2())
    _no_rest(player, monkeypatch)
    first = _plan(player)
    assert isinstance(first.plan[0], DepositAllAction)
    assert player.state is not None
    executed: WorldState = first.plan[0].apply(player.state, gd)
    player.seed_offline(executed, gd)
    _no_rest(player, monkeypatch)
    second = _plan(player)
    assert isinstance(second.selected_goal, RestoreHPGoal)
    assert second.plan and not isinstance(second.plan[0], DepositAllAction), second.plan
    assert not needs_slot(second.plan, executed, gd)
    assert any(isinstance(a, CraftAction) and a.code == "cooked_porkchop" for a in second.plan)
