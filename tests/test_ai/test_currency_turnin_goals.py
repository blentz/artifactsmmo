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
from artifactsmmo_cli.ai.goals.currency_turnin import CurrencyTurnInGoal
from artifactsmmo_cli.ai.goals.surrender_currency import SurrenderCurrencyGoal
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


def test_buyer_goal_is_satisfied_once_the_item_is_owned():
    state = make_state(inventory={"lich_race_trophy": 1})
    goal = CurrencyTurnInGoal(item_code="lich_race_trophy", npc_code="archaeologist",
                              price=10, currency="lich_race_medal")
    assert goal.is_satisfied(state) is True


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
