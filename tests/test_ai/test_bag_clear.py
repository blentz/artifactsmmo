"""Task 13e: a full bag frees every slot the plan does not use, then retries
(USER 2026-10-25, binding: "free up all in-use inventory slots that aren't
related to the current plan, then retry the plan once the full inventory state
is cleared").

The live shape (R2D2 from 2026-10-22T19:02Z): 20 of 20 slots used, 119/172 by
quantity, HP_CRITICAL won the ladder and RestoreHP planned
`Craft(cooked_porkchop×1)` — a new stack with nowhere to land — and drew HTTP
497 on 2,772 consecutive cycles while DEPOSIT_FULL fired below it."""

from dataclasses import replace

import pytest

import artifactsmmo_cli.ai.bag_clear as bag_clear_mod
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bag_clear import (
    BAG_FULL_OUTCOME,
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
    slots_freed,
)
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
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


def test_slots_freed_counts_the_stacks_that_leave() -> None:
    routes = [ClearRoute.KEEP, ClearRoute.DEPOSIT, ClearRoute.DISPOSE, ClearRoute.KEEP]
    assert slots_freed(routes) == 2
    assert slots_freed([ClearRoute.KEEP]) == 0


# --------------------------------------------------------------------------
# The trigger
# --------------------------------------------------------------------------

def test_a_new_stack_into_a_full_bag_needs_a_slot(gd: GameData) -> None:
    state = scenario_state(_r2d2(), gd)
    assert state.inventory_slots_free == 0 and state.inventory_free > 0
    assert needs_slot([CraftAction(code="cooked_porkchop", quantity=1)], state, gd)


def test_a_new_stack_with_a_free_slot_fits(gd: GameData) -> None:
    state = scenario_state(_r2d2(slots_max=21), gd)
    assert not needs_slot([CraftAction(code="cooked_porkchop", quantity=1)], state, gd)


def test_the_walk_stops_at_a_fight(gd: GameData) -> None:
    """Past a fight the modelled loot is optimistic, so a craft behind it is
    not judged; the fight's own room is `refused_fight`'s."""
    state = scenario_state(_r2d2(), gd)
    fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}),
                        learned_drops=LearnedDrops.empty())
    assert not needs_slot([fight, CraftAction(code="cooked_porkchop", quantity=1)], state, gd)


def test_plan_codes_are_what_the_steps_consume_and_produce(gd: GameData) -> None:
    state = scenario_state(_r2d2(), gd)
    plan = [CraftAction(code="cooked_porkchop", quantity=1)]
    assert plan_codes(plan, state, gd) == {"raw_porkchop", "cooked_porkchop"}


# --------------------------------------------------------------------------
# The related set and the clear
# --------------------------------------------------------------------------

def test_related_items_are_never_shed(gd: GameData) -> None:
    """Plan inputs, root-closure materials and keep-authority items stay."""
    state = scenario_state(_r2d2(), gd)
    plan = [CraftAction(code="cooked_porkchop", quantity=1)]
    ctx = replace(_ctx(), step_profile={"owlbear_hair": 1})  # GOAL_MATERIALS keeps one
    closure = frozenset({"iron_ore", "coal"})                # a steel_bar root
    related = related_codes(plan, state, gd, ctx, closure)
    assert {"raw_porkchop", "iron_ore", "coal", "owlbear_hair"} <= related
    clear = clear_actions(state, gd, [_deposit(gd)], ctx, related)
    after = cleared_state(clear, state, gd)
    for code in ("raw_porkchop", "iron_ore", "coal", "owlbear_hair"):
        assert after.inventory[code] == state.inventory[code], code
    # Everything else left the bag, all of it at once, in one DepositAll.
    assert [type(a) for a in clear] == [DepositAllAction]
    assert set(after.inventory) == {"raw_porkchop", "iron_ore", "coal", "owlbear_hair"}


def test_the_equipped_codes_are_related(gd: GameData) -> None:
    state = replace(scenario_state(_r2d2(), gd),
                    equipment={**scenario_state(_r2d2(), gd).equipment, "weapon_slot": "iron_sword"})
    assert "iron_sword" in related_codes([], state, gd, _ctx(), frozenset())


def test_no_bank_in_the_pool_and_no_licence_frees_nothing(gd: GameData) -> None:
    """Without a deposit and with every unrelated stack still wanted
    (`destroyable` below the held stack), nothing can leave."""
    state = scenario_state(_r2d2(inventory={"raw_porkchop": 19, "event_ticket": 3}, slots_max=2), gd)
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [], _ctx(), related) == []


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
    assert clear == [DeleteItemAction(code="lich_tomb_key", quantity=1)]
    after = cleared_state(clear, state, gd)
    assert set(after.inventory) == {"raw_porkchop", "event_ticket"}


def test_a_disposal_that_leaves_copies_frees_no_slot(gd: GameData) -> None:
    """A recycle that cannot take the whole stack (its minted materials need
    the slots the bag lacks) is not a clear."""
    bank = {f"filler_{i}": 1 for i in range(gd.bank_capacity)}
    bag = {"raw_porkchop": 19, "copper_dagger": 5}
    state = scenario_state(_r2d2(inventory=bag, slots_max=2, bank=bank), gd)
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [_deposit(gd)], _ctx(), related) == []


def test_a_partial_disposal_frees_no_slot(gd: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """The junk policy sized below the stack (a RECYCLE whose minted materials
    did not fit) leaves copies, so it frees no slot and is no clear."""
    bank = {f"filler_{i}": 1 for i in range(gd.bank_capacity)}
    bag = {"raw_porkchop": 19, "lich_tomb_key": 2}
    state = scenario_state(_r2d2(inventory=bag, slots_max=2, bank=bank), gd)
    monkeypatch.setattr(bag_clear_mod, "overstock_disposal",
                        lambda code, qty, *_: DeleteItemAction(code=code, quantity=qty - 1))
    related = frozenset({"raw_porkchop", "cooked_porkchop"})
    assert clear_actions(state, gd, [_deposit(gd)], _ctx(), related) == []


def test_withdraw_and_equip_unblock_after_the_clear(gd: GameData) -> None:
    """The gearcrafting climb's `Withdraw(steel_bar×4)` was declined
    `first_leg_inapplicable` on the full bag; after the clear it applies."""
    sc = _r2d2(bank={"steel_bar": 40, "copper_helmet": 1})
    state = scenario_state(sc, gd)
    withdraw = WithdrawItemAction(code="steel_bar", quantity=4, bank_location=gd.bank_location())
    assert not withdraw.is_applicable(state, gd)
    related = related_codes([CraftAction(code="cooked_porkchop", quantity=1)], state, gd,
                            _ctx(), frozenset())
    after = cleared_state(clear_actions(state, gd, [_deposit(gd)], _ctx(), related), state, gd)
    assert after.inventory_slots_free > 0
    assert withdraw.is_applicable(after, gd)
    # And an equip that returns the worn piece to the bag.
    worn = replace(after, equipment={**after.equipment, "helmet_slot": "copper_helmet"},
                   inventory={**after.inventory, "iron_helm": 1})
    full = replace(worn, inventory_slots_max=worn.inventory_slots_used)
    equip = EquipAction(code="iron_helm", slot="helmet_slot")
    assert not equip.is_applicable(replace(full, inventory={**full.inventory, "iron_helm": 2}), gd)
    assert equip.is_applicable(replace(full, inventory_slots_max=full.inventory_slots_used + 1,
                                       inventory={**full.inventory, "iron_helm": 2}), gd)


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
    # Every unrelated code banked; the porkchop inputs stay.
    assert after.inventory["raw_porkchop"] == 19
    assert after.inventory_slots_free > 0
    banked = set(player.state.inventory) - set(after.inventory)
    assert banked == set(JUNK) - set(after.inventory)
    assert len(banked) >= len(JUNK) - 1
    # ...and then the plan the live bot was 497ing on: it crafts and eats.
    rest = report.plan[1:]
    assert any(isinstance(a, CraftAction) and a.code == "cooked_porkchop" for a in rest), rest
    assert any(isinstance(a, UseConsumableAction) for a in rest), rest
    assert not needs_slot(report.plan, player.state, gd)
    events = player._arbiter.events.drain()
    assert (Mechanism.BAG_CLEAR, "RestoreHP") in [(m, s) for m, s, _ in events]


def test_a_497_triggers_the_clear(gd: GameData) -> None:
    """The model believes there is room; the server's 497 overrides it."""
    player = _player(gd, _r2d2(slots_max=30))
    assert player.state is not None and player.state.inventory_slots_free > 0
    calm = player.plan_from_state()
    assert not isinstance(calm.plan[0], DepositAllAction), calm.plan
    player._last_outcome = BAG_FULL_OUTCOME
    report = player.plan_from_state()
    assert isinstance(report.plan[0], DepositAllAction), report.plan


def test_all_related_full_bag_is_named(gd: GameData) -> None:
    """Every stack is related, so nothing can free the slot the craft needs:
    the doomed plan is dropped (no silent retry), and the verdict is named in
    the events, on the arbiter and in the log."""
    bag = {"raw_porkchop": 19}
    state = scenario_state(_r2d2(inventory=bag, slots_max=1), gd)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    goal = RestoreHPGoal()
    craft = [CraftAction(code="cooked_porkchop", quantity=1)]
    assert arbiter._clear_bag(goal, craft, state, gd, [_deposit(gd)], _ctx(), None) == []
    assert arbiter.last_bag_verdict == BAG_FULL_ALL_RELATED
    assert arbiter.events.drain() == [
        (Mechanism.BAG_FULL_ALL_RELATED, "RestoreHP", "held=1 related=1")]
    # A plan the model believes fits keeps its turn under a bare 497.
    roomy = replace(state, inventory_slots_max=2)
    refused = replace(_ctx(), bag_refused=True)
    assert arbiter._clear_bag(goal, craft, roomy, gd, [_deposit(gd)], refused, None) == craft


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


def test_an_empty_plan_is_not_cleared(gd: GameData) -> None:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    state = scenario_state(_r2d2(), gd)
    refused = replace(_ctx(), bag_refused=True)
    assert arbiter._clear_bag(RestoreHPGoal(), [], state, gd, [_deposit(gd)], refused, None) == []
    assert arbiter.events.drain() == []


def test_the_player_reads_the_497_into_the_context(gd: GameData) -> None:
    player = _player(gd, _r2d2())
    assert player._selection_context().bag_refused is False
    player._last_outcome = BAG_FULL_OUTCOME
    assert player._selection_context().bag_refused is True
    player._last_outcome = "error:HTTP_499"
    assert player._selection_context().bag_refused is False


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
