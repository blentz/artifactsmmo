"""`DepositAllAction` is the BANK TRIP, not the item-deposit trip.

The liveness census has excused `DepositGoldAction` since it was written with
"gold is banked by DepositAll, not as a separate step". That was false —
`execute` called `deposit_item` and nothing else, and across 184,010 cycles no
character ever banked a coin. This makes the claim true.

Gold rides a trip items justify and never causes one: `is_applicable` stays
items-only, so `value`, `is_satisfied` and `desired_state` on
`DepositInventoryGoal` are untouched and both Lean theorems over them still bind.
"""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.progression_reserve import progression_reserve
from tests.test_ai.fixtures import make_state

BANK = (4, 0)


def _gd(bank_capacity: int = 200, next_expansion_cost: int = 3_500) -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._npc_stock = {"merchant": {"copper_ore": 5}}
    gd._monster_level = {"chicken": 1}
    gd._bank_capacity = bank_capacity
    gd._next_expansion_cost = next_expansion_cost
    return gd


def _action(gd: GameData | None) -> DepositAllAction:
    return DepositAllAction(bank_location=BANK, accessible=True, game_data=gd)


def _state(gold: int, bank_gold: int = 0, banked_codes: int = 0):
    bank = {f"slot{i}": 1 for i in range(banked_codes)}
    return make_state(x=BANK[0], y=BANK[1], gold=gold,
                      inventory={"copper_ore": 40}, inventory_max=200,
                      bank_items=bank, bank_gold=bank_gold)


def test_a_surplus_chunk_is_banked():
    gd = _gd()
    action = _action(gd)
    # reserve is the safety floor (100) for a state with no gear targets.
    assert action._gold_deposit(_state(gold=28_016)) == 20_000
    assert progression_reserve(_state(gold=28_016), gd) == 100


def test_no_chunk_means_no_gold_moves():
    gd = _gd()
    assert _action(gd)._gold_deposit(_state(gold=9_999)) == 0


def test_no_game_data_banks_no_gold():
    """No game data means no reserve can be computed. Use only API data or fail
    — never default the reserve to zero and bank a character dry."""
    assert _action(None)._gold_deposit(_state(gold=28_016)) == 0


def test_unread_bank_banks_no_gold():
    """`bank_items is None` means the bank was never read this cycle, not that
    it holds nothing. Guessing empty would feed `expansion_hold` a `bank_used`
    of 0 and bank away gold an imminent expansion needs — this pins the same
    rule `_deposits` already follows for `game_data is None`."""
    gd = _gd()
    action = _action(gd)
    state = make_state(x=BANK[0], y=BANK[1], gold=28_016,
                       inventory={"copper_ore": 40}, inventory_max=200,
                       bank_items=None, bank_gold=0)
    assert action._gold_deposit(state) == 0


def test_an_imminent_expansion_holds_its_price_back():
    """Bank at 70% of capacity: the expansion price stops being bankable."""
    gd = _gd(bank_capacity=100, next_expansion_cost=15_000)
    action = _action(gd)
    state = _state(gold=28_016, banked_codes=70)
    assert action._gold_deposit(state) == 10_000


def test_a_distant_expansion_holds_nothing_back():
    gd = _gd(bank_capacity=100, next_expansion_cost=15_000)
    action = _action(gd)
    state = _state(gold=28_016, banked_codes=69)
    assert action._gold_deposit(state) == 20_000


def test_apply_moves_gold_and_bank_gold_together():
    """`apply` and `execute` must tell the same story — this file's comments
    defend that invariant twice already for items."""
    gd = _gd()
    action = _action(gd)
    state = _state(gold=28_016, bank_gold=5_000)
    after = action.apply(state, gd)
    assert after.gold == 8_016
    assert after.bank_gold == 25_000


def test_apply_leaves_gold_alone_when_no_chunk_is_due():
    gd = _gd()
    action = _action(gd)
    state = _state(gold=9_999, bank_gold=5_000)
    after = action.apply(state, gd)
    assert after.gold == 9_999
    assert after.bank_gold == 5_000


def test_execute_issues_the_gold_request_after_the_items():
    """Ordering, not just occurrence. A shared `manager` records both patched
    calls (plus the cooldown wait) into ONE ordered call list, so this test
    goes red if the gold request moves ahead of the item batch — the exact
    defect class fixed in 8fff7d61 for the item batches themselves: a second
    request issued inside the first request's server cooldown returns HTTP 499
    and leaves a PARTIAL deposit."""
    gd = _gd()
    action = _action(gd)
    state = _state(gold=28_016)
    char = MagicMock()
    char.name = "testchar"
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char

    manager = MagicMock()
    with patch("artifactsmmo_cli.ai.actions.deposit_all.WorldState.from_character_schema",
               return_value=state), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=result) as items, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.action_deposit_gold",
               return_value=result) as gold, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown") as wait:
        manager.attach_mock(items, "deposit_item")
        manager.attach_mock(wait, "wait_out_cooldown")
        manager.attach_mock(gold, "action_deposit_gold")
        action.execute(state, MagicMock())

    assert items.called
    assert gold.call_count == 1
    assert gold.call_args.kwargs["body"].quantity == 20_000

    names = [call[0] for call in manager.mock_calls]
    items_index = names.index("deposit_item")
    wait_index = names.index("wait_out_cooldown")
    gold_index = names.index("action_deposit_gold")
    # The item batch must land before the wait, and the wait — which is what
    # makes the ordering SAFE, not the ordering alone — before the gold call.
    assert items_index < wait_index < gold_index


def test_execute_issues_no_gold_request_when_no_chunk_is_due():
    """The per-IP request budget is the fleet's binding constraint — a request
    that moves nothing is a request not worth making."""
    gd = _gd()
    action = _action(gd)
    state = _state(gold=9_999)
    char = MagicMock()
    char.name = "testchar"
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char

    with patch("artifactsmmo_cli.ai.actions.deposit_all.WorldState.from_character_schema",
               return_value=state), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=result), \
         patch("artifactsmmo_cli.ai.actions.deposit_all.action_deposit_gold") as gold, \
         patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown"):
        action.execute(state, MagicMock())

    gold.assert_not_called()


def test_is_applicable_still_ignores_gold():
    """Gold rides a trip items justify; it never causes one. If this flips, the
    goal's desired_state (inventory_used only) no longer describes the action."""
    gd = _gd()
    action = _action(gd)
    state = make_state(x=BANK[0], y=BANK[1], gold=999_999,
                       inventory={}, inventory_max=200,
                       bank_items={}, bank_gold=0)
    assert action.is_applicable(state, gd) is False
