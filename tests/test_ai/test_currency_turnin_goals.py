"""Tests for CurrencyTurnInGoal (buyer) and SurrenderCurrencyGoal (holder) —
the two goals CURRENCY_TURNIN maps to.

Both drive the REAL GOAPPlanner over a narrow, hand-built action pool.
`build_actions` never emits a Withdraw sized to a turn-in price or a Deposit
sized to a surrender quantity (neither is objective-step demand) — each goal
materializes its own bank leg instead, the same pattern `disposal_route.py`
uses for its DEPOSIT arm — and filters the rest (NpcBuy / Unequip) out of
whatever pool it is handed, since `build_actions` already emits those
unconditionally (one NpcBuyAction per (npc, item) pair, one UnequipAction per
equipment slot)."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_turnin import TURN_IN_PRIORITY, CurrencyTurnInGoal
from artifactsmmo_cli.ai.goals.surrender_currency import SURRENDER_PRIORITY, SurrenderCurrencyGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def _turn_in_actions(gd: GameData, state: WorldState) -> list[Action]:
    """A narrow hand-built pool standing in for `build_actions`'s
    unconditional NpcBuy/Unequip emissions, without pulling in the whole
    ~1800-action factory pool this module has no need of."""
    actions: list[Action] = []
    for npc_code, stock in gd.world.npc_stock.items():
        for item_code in stock:
            actions.append(NpcBuyAction(npc_code=npc_code, item_code=item_code,
                                        quantity=1, npc_location=(0, 0)))
    for slot in state.equipment:
        actions.append(UnequipAction(slot=slot))
    return actions


def test_buyer_plans_withdraw_then_purchase():
    """The last mile already works when the medals are in the bank — this goal
    exists to make the planner be HANDED that goal at all."""
    gd = medal_game_data()
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 10})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert [repr(a) for a in plan] == [
        "Withdraw(lich_race_medal×10)",
        "NpcBuy(lich_race_trophy×1@archaeologist)",
    ]


def test_buyer_funds_the_price_from_its_own_worn_and_carried_units():
    """CRITICAL (fix-round-2): the buyer must fund the purchase from what IT
    already holds, not from the bank alone.

    Live shape: the elected buyer wears 1 medal, carries 1, and the shared
    bank holds 8 — `fleet_total` is 10, so this character WINS the election,
    and a goal that always materializes `Withdraw(currency x price)` can then
    never plan (`WithdrawItemAction.is_applicable` needs `bank >= 10` and the
    bank has 8). That is a permanent livelock for exactly the character most
    likely to be elected: the upgrade gate favours a character the item is an
    upgrade for, and a medal-wearer is a natural winner.

    So the plan must unequip the buyer's own worn copies (each moves one unit
    into inventory, which is where `NpcBuyAction` pays from) and withdraw only
    the REMAINDER the bank has to supply."""
    gd = medal_game_data()
    state = make_state(level=27,
                       equipment={"artifact1_slot": "lich_race_medal"},
                       inventory={"lich_race_medal": 1},
                       bank_items={"lich_race_medal": 8})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")

    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    reprs = [repr(a) for a in plan]
    assert len(plan) == 3, reprs
    assert reprs.count("Unequip(artifact1_slot)") == 1, reprs
    assert "Withdraw(lich_race_medal×8)" in reprs, reprs
    assert "Withdraw(lich_race_medal×10)" not in reprs, reprs
    assert reprs[-1] == "NpcBuy(lich_race_trophy×1@archaeologist)", reprs

    # Replay it: `apply` asserts each action's own precondition, so a plan
    # ordered unequip-after-a-bag-filling-withdraw would crash here rather
    # than pass silently (UnequipAction needs `inventory_free >= 1`).
    end_state = state
    for action in plan:
        end_state = action.apply(end_state, gd)
    assert goal.is_satisfied(end_state) is True


def test_buyer_withdraws_nothing_when_it_already_holds_the_whole_price():
    """The degenerate end of the same sizing rule: a buyer already carrying
    the full price must NOT be handed a `Withdraw(...x0)` no-op leg — the
    remainder is zero, so there is no bank leg at all."""
    gd = medal_game_data()
    state = make_state(level=27, inventory={"lich_race_medal": 10}, bank_items={})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")

    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert [repr(a) for a in plan] == ["NpcBuy(lich_race_trophy×1@archaeologist)"]


def test_buyer_goal_is_satisfied_once_the_item_is_owned():
    state = make_state(inventory={"lich_race_trophy": 1})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    assert goal.is_satisfied(state) is True


def test_buyer_value_drops_to_zero_once_the_item_is_owned():
    """A satisfied buyer goal must stop reporting urgency — an arbiter that
    kept scoring it nonzero would re-plan a purchase already made."""
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    state = make_state(inventory={"lich_race_trophy": 1})
    assert goal.value(state, GameData()) == 0.0


def test_buyer_value_is_positive_before_the_item_is_owned():
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    state = make_state(inventory={})
    assert goal.value(state, GameData()) == TURN_IN_PRIORITY


def test_buyer_desired_state_targets_owning_one_copy():
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    assert goal.desired_state(make_state(), GameData()) == {
        "inventory": {"lich_race_trophy": 1}}


def test_buyer_repr_names_the_item():
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    assert repr(goal) == "CurrencyTurnIn(lich_race_trophy)"


def test_holder_plans_unequip_then_deposit():
    gd = medal_game_data()
    gd._bank_capacity = 50  # DepositItemAction.is_applicable needs room to land in
    state = make_state(equipment={"artifact1_slot": "lich_race_medal"},
                       inventory={}, bank_items={})
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert [repr(a) for a in plan][:2] == ["Unequip(artifact1_slot)",
                                           "DepositItem(lich_race_medal×1)"]


def test_holder_goal_is_satisfied_when_its_units_are_banked():
    state = make_state(inventory={}, equipment={},
                       bank_items={"lich_race_medal": 4})
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    assert goal.is_satisfied(state) is True


def test_holder_is_not_satisfied_when_the_bank_has_never_been_fetched():
    """`bank_items=None` is "the bank has not been read this cycle" — a
    genuinely reachable state (world_state.py), distinct from "bank read and
    empty" (`{}`). Neither must be mistaken for satisfied: a character that
    has not even looked at the bank cannot know its quota is banked."""
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    state = make_state(inventory={}, equipment={}, bank_items=None)
    assert goal.is_satisfied(state) is False


def test_holder_value_drops_to_zero_once_its_units_are_banked():
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    state = make_state(bank_items={"lich_race_medal": 1})
    assert goal.value(state, GameData()) == 0.0


def test_holder_value_is_positive_before_its_units_are_banked():
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=1)
    state = make_state(bank_items={})
    assert goal.value(state, GameData()) == SURRENDER_PRIORITY


def test_holder_desired_state_targets_the_full_holding_banked():
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=5)
    assert goal.desired_state(make_state(), GameData()) == {
        "banked": {"lich_race_medal": 5}}


def test_holder_repr_names_the_currency_and_the_full_quota():
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=5)
    assert repr(goal) == "SurrenderCurrency(lich_race_medalx5)"


def test_holder_surrenders_every_worn_copy_plus_what_it_already_carries():
    """The central case the controller ruling exists for: THREE worn copies
    (duplicate-artifact slots) plus TWO carried, units=5. A goal that only
    ever freed the first worn slot would strand 2 medals in equipment and
    never reach the full quota — this is the case that would catch it."""
    gd = medal_game_data()
    gd._bank_capacity = 50
    state = make_state(
        equipment={"artifact1_slot": "lich_race_medal",
                  "artifact2_slot": "lich_race_medal",
                  "artifact3_slot": "lich_race_medal"},
        inventory={"lich_race_medal": 2},
        bank_items={},
    )
    goal = SurrenderCurrencyGoal(currency="lich_race_medal", units=5)
    assert goal.is_satisfied(state) is False

    plan = GOAPPlanner().plan(state, goal, _turn_in_actions(gd, state), gd)

    assert len(plan) == 4
    unequips = sorted(repr(a) for a in plan if isinstance(a, UnequipAction))
    assert unequips == ["Unequip(artifact1_slot)", "Unequip(artifact2_slot)",
                        "Unequip(artifact3_slot)"]
    assert repr(plan[-1]) == "DepositItem(lich_race_medal×5)"

    end_state = state
    for action in plan:
        end_state = action.apply(end_state, gd)
    assert goal.is_satisfied(end_state) is True
