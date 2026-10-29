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
import artifactsmmo_cli.ai.craft_plan_gen as craft_plan_gen_mod
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
    frees_first,
    needs_slot,
    plan_codes,
    related_codes,
)
from artifactsmmo_cli.ai.bag_clear_core import (
    BAG_FULL_ALL_RELATED,
    ClearRoute,
    clear_route,
)
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.planner import GOAPPlanner, PlanStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
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


# --------------------------------------------------------------------------
# Fix round 2 (re-review task-13e-rereview-1.md; rulings T13e-d..g)
# --------------------------------------------------------------------------

def test_a_warm_pool_memo_never_answers_for_the_widened_clear(gd: GameData) -> None:
    """T13e-d: the pool's DepositAll memoises its deposits on the state object.
    The clear re-parameterises a copy with a wider keep; the copy must start
    cold, or it answers with the pool's deposits and models the related
    porkchop inputs as banked."""
    state = scenario_state(_r2d2(), gd)
    pool = _deposit(gd)
    assert pool.is_applicable(state, gd)  # warms the memo on THIS state object
    assert "raw_porkchop" not in pool.apply(state, gd).inventory  # the pool banks it
    related = related_codes([_craft(gd)], state, gd, _ctx())
    clear = clear_actions(state, gd, [pool], _ctx(), related)
    assert cleared_state(clear.actions, state, gd).inventory == {"raw_porkchop": 19}
    # The same rule covers DepositInventoryGoal's re-parameterised copy.
    assert replace(pool, ctx=_ctx())._last_deposits is None


def test_a_497_relief_plan_is_emitted_not_named(gd: GameData) -> None:
    """T13e-e: after a 497, a plan that frees a slot itself before it needs
    one IS the relief (the DEPOSIT_FULL guard's [DepositAll]): emitted as is,
    no clear, no `bag_full_all_related` verdict."""
    state = scenario_state(_r2d2(), gd)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    relief = [_deposit(gd)]
    assert frees_first(relief, state, gd)
    refused = replace(_ctx(), bag_refused=True)
    assert arbiter._clear_bag(RestoreHPGoal(), relief, state, gd, [_deposit(gd)], refused) == relief
    assert arbiter.last_bag_verdict is None
    assert arbiter.events.drain() == []


def test_frees_first_reads_the_first_slot_event(gd: GameData) -> None:
    """A plan that needs a slot before it frees one is not the relief."""
    state = scenario_state(_r2d2(), gd)
    assert not frees_first([_craft(gd), _deposit(gd)], state, gd)
    assert not frees_first([], state, gd)
    # A craft whose output is eaten returns only the slot it took.
    roomier = scenario_state(_r2d2(slots_max=30), gd)
    eat = UseConsumableAction(_item_stats=gd.all_item_stats)
    assert not frees_first([_craft(gd), eat], roomier, gd)


def test_the_quiet_ask_keeps_the_cycles_planner_stats(gd: GameData,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """T13e-f: the emptied-bag ask may run A*; the cycle's planner telemetry
    stays the goal's own attempt's, and the swap is restored even when the ask
    raises."""
    player, goal = _climb(gd)
    assert player.state is not None
    arbiter = player._arbiter
    before = PlanStats(nodes_explored=7)
    arbiter._planner.last_stats = before

    def search(*args: object, **kwargs: object) -> list[object]:
        arbiter._planner.last_stats = PlanStats(nodes_explored=99_999)
        arbiter.goals_tried.append({"goal": "hypothetical"})
        return []

    monkeypatch.setattr(arbiter, "_plans", search)
    arbiter._attempt_declined, arbiter._attempt_searched = [], True
    tried = arbiter.goals_tried
    assert arbiter._slot_blocked_plan(goal, player.state, gd, [], player._selection_context()) is None
    assert arbiter._planner.last_stats is before
    assert arbiter.goals_tried is tried and tried == []

    def boom(*args: object, **kwargs: object) -> list[object]:
        arbiter.goals_tried.append({"goal": "hypothetical"})
        raise RuntimeError("search failed")

    monkeypatch.setattr(arbiter, "_plans", boom)
    with pytest.raises(RuntimeError):
        arbiter._slot_blocked_plan(goal, player.state, gd, [], player._selection_context())
    assert arbiter.goals_tried is tried and tried == []
    assert arbiter._planner.last_stats is before


def test_a_heal_prep_never_clears_the_grinds_own_stack(gd: GameData,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """T13e-g: a grind whose legs smelt the held iron_ore and fight, fronted by
    a heal prep that cooks the held raw_porkchop, on R2D2's full bag. The prep
    alone overflows; clearing against ITS legs would bank the ore the grind
    smelts. The nested prep declines; the clear runs once, at the outermost
    grind, over the prep AND the grind's legs (ruling T14d-1), so the prep that
    fits after the clear runs this cycle, and neither the porkchop the prep
    cooks nor the ore the grind smelts is shed."""
    state = scenario_state(replace(_r2d2(), skills={"cooking": 30, "mining": 30}), gd)
    smelt = CraftAction(code="iron_bar", quantity=1, workshop_location=gd.workshop_location("mining"))
    fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}),
                        learned_drops=LearnedDrops.empty())
    rung = GatherMaterialsGoal("iron_bar", {"iron_bar": 1})
    prep = GatherMaterialsGoal("cooked_porkchop", {"cooked_porkchop": 1})
    walk = craft_plan_gen_mod._walk_plan

    def walk_plan(goal: GatherMaterialsGoal, *args: object, **kwargs: object) -> object:
        return [smelt, fight] if goal is rung else walk(goal, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(craft_plan_gen_mod, "grind_rung_goal", lambda *a, **k: rung)
    monkeypatch.setattr(craft_plan_gen_mod, "_walk_plan", walk_plan)
    monkeypatch.setattr(craft_plan_gen_mod, "heal_prep_goal", lambda *a, **k: prep)
    pool = [_deposit(gd), _craft(gd), smelt, fight]
    plan = decompose(ReachSkillGoal(skill_name="mining", target_level=31), state, gd, pool, _ctx())
    assert plan is not None and isinstance(plan[0], DepositAllAction), plan
    assert plan[2:] == [smelt, fight], plan
    assert isinstance(plan[1], CraftAction) and plan[1].code == "cooked_porkchop", plan
    after = cleared_state(plan[:1], state, gd)
    assert after.inventory == {"raw_porkchop": 19, "iron_ore": 12}
    # A nested grind (`outermost=False`) never clears, for its prep or itself.
    nested: list[str] = []
    assert decompose(ReachSkillGoal(skill_name="mining", target_level=31), state, gd, pool,
                     _ctx(), nested, outermost=False) is None
    assert nested and nested[-1].startswith("bag_overflow:"), nested
    # Nested, the prep alone declines rather than clearing for itself.
    declined: list[str] = []
    assert decompose(prep, state, gd, pool, _ctx(), declined, outermost=False) is None
    assert declined and declined[0].startswith("bag_overflow:")


def test_a_prep_that_does_not_fit_after_the_clear_never_blocks_the_grind(
        gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling T14d-1: when the clear does not make the prep and the grind's legs
    fit together, the prep is skipped and the grind runs as before: the
    outermost decompose clears for the legs alone."""
    state = scenario_state(replace(_r2d2(), skills={"cooking": 30, "mining": 30}), gd)
    smelt = CraftAction(code="iron_bar", quantity=1, workshop_location=gd.workshop_location("mining"))
    fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}),
                        learned_drops=LearnedDrops.empty())
    rung = GatherMaterialsGoal("iron_bar", {"iron_bar": 1})
    prep = GatherMaterialsGoal("cooked_porkchop", {"cooked_porkchop": 1})
    walk = craft_plan_gen_mod._walk_plan
    clear_first = craft_plan_gen_mod._clear_first
    asked: list[list[object]] = []

    def walk_plan(goal: GatherMaterialsGoal, *args: object, **kwargs: object) -> object:
        return [smelt, fight] if goal is rung else walk(goal, *args, **kwargs)  # type: ignore[arg-type]

    def no_room_with_the_prep(walked: list[object], *args: object) -> object:
        asked.append(list(walked))
        if walked != [smelt, fight]:
            return None
        return clear_first(walked, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(craft_plan_gen_mod, "grind_rung_goal", lambda *a, **k: rung)
    monkeypatch.setattr(craft_plan_gen_mod, "_walk_plan", walk_plan)
    monkeypatch.setattr(craft_plan_gen_mod, "heal_prep_goal", lambda *a, **k: prep)
    monkeypatch.setattr(craft_plan_gen_mod, "_clear_first", no_room_with_the_prep)
    pool = [_deposit(gd), _craft(gd), smelt, fight]
    plan = decompose(ReachSkillGoal(skill_name="mining", target_level=31), state, gd, pool, _ctx())
    assert plan is not None and isinstance(plan[0], DepositAllAction), plan
    assert plan[1:] == [smelt, fight], plan
    assert len(asked) == 2 and asked[0][-2:] == [smelt, fight] and len(asked[0]) > 2


# --------------------------------------------------------------------------
# Task 14a: the walk asks the bag the arbiter clears
# --------------------------------------------------------------------------

def test_the_walk_serves_a_climb_the_clear_unblocks(gd: GameData) -> None:
    """Live R2D2 2026-10-25 (777 cycles): the gearcrafting climb was declined
    by the WALK as `first_leg_inapplicable:Withdraw(steel_bar×4)` on 20 of 20
    slots, so it never headed the resolution and the arbiter's clear, which
    serves it (`test_a_withdraw_the_full_bag_refuses_is_cleared_then_runs`),
    was never asked. The walk now asks the bag the clear leaves."""
    player, _goal = _climb(gd)
    assert player.state is not None
    decline = player._step_decline(player.state, gd, player._selection_context(),
                                   player._build_actions())
    assert decline(ReachSkillLevel(skill="gearcrafting", level=24)) is None


def _helmet(gd: GameData) -> tuple[GamePlayer, ObtainItem]:
    """R2D2's full bag, a worn helmet, and the better one banked: the equip
    displaces the worn helmet into a bag with no slot for it."""
    sc = replace(_r2d2(bank={"steel_helm": 1}), hp=900,
                 equipment={"helmet_slot": "copper_helmet"})
    return _player(gd, sc), ObtainItem(code="steel_helm", quantity=1, slot="helmet_slot")


def test_the_walk_serves_an_equip_the_full_bag_refuses(gd: GameData) -> None:
    """Live R2D2 2026-10-27: 8 of 11 `L*` pieces declined
    `upgrade:equip_inapplicable` on 20 of 20 slots — the displaced piece has
    no slot to land in. A full bag is a slot decline the clear answers."""
    player, root = _helmet(gd)
    assert player.state is not None
    ctx = player._selection_context()
    actions = player._build_actions()
    assert player._step_decline(player.state, gd, ctx, actions)(root) is None
    goal = UpgradeEquipmentGoal(initial_equipment=player.state.equipment,
                                committed_target=("steel_helm", "helmet_slot"))
    declined: list[str] = []
    assert decompose(goal, player.state, gd, actions, ctx, declined) is None
    assert declined == ["upgrade:equip_inapplicable:Equip(steel_helm->helmet_slot)"]
    # ...and the arbiter serves it: the clear, then the withdraw and the equip.
    chosen, plan, _ = player._arbiter._arbitrate(
        [Candidate(goal=goal, repr_=repr(goal), band=BAND_STEP)], player.state, gd,
        actions, ctx)
    assert chosen is goal
    assert isinstance(plan[0], DepositAllAction), plan
    assert plan[-1] == EquipAction(code="steel_helm", slot="helmet_slot"), plan


def test_a_slot_decline_with_nothing_to_clear_stays_declined(gd: GameData) -> None:
    """Every stack is related (the climb's own materials), so the clear frees
    no slot: the arbiter would drop the plan (`bag_full_all_related`), and the
    walk keeps the decline."""
    sc = replace(_r2d2(inventory={"wolf_bone": 3, "skeleton_bone": 11, "pig_skin": 3},
                       slots_max=3, bank={"steel_bar": 40}),
                 hp=900, skills={"cooking": 30, "gearcrafting": 20, "mining": 30})
    player = _player(gd, sc)
    assert player.state is not None
    decline = player._step_decline(player.state, gd, player._selection_context(),
                                   player._build_actions())
    assert decline(ReachSkillLevel(skill="gearcrafting", level=24)) == (
        "first_leg_inapplicable:Withdraw(steel_bar×4)")
