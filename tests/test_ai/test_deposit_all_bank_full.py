"""`DepositAllAction` must not offer a deposit a full bank cannot accept.

Live Robby 2026-09-12: the bank held 50 codes in 50 slots and Robby held six
codes, none of them already banked. `select_bank_deposits` licensed 152 of his
157 items as bag-surplus, so `is_applicable` said yes, the skill-grind sub-plan
put `DepositAll` at its head, and every cycle 462'd against the full bank.

The `DEPOSIT_FULL` guard already asked `bank_has_room` and correctly declined.
The ACTION did not, so the objective path kept emitting what the guard refused.
Its sibling `DepositItemAction.is_applicable` has carried the gate all along.

Room is asked PER CODE, not once for the bank: depositing into a stack the bank
already holds needs no new slot, so a full bank still accepts those. The filter
lives in `_deposits`, which is the single list `is_applicable`, `apply` and
`execute` all read — gating only `is_applicable` would leave `apply` projecting
a deposit `execute` cannot make.
"""

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(bank_capacity: int) -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._npc_stock = {"merchant": {"copper_ore": 5, "iron_ore": 6}}
    gd._monster_level = {"chicken": 1}
    gd._bank_capacity = bank_capacity
    return gd


def _action(gd: GameData) -> DepositAllAction:
    return DepositAllAction(bank_location=(1, 1), accessible=True, game_data=gd)


def _full_bank(size: int) -> dict[str, int]:
    return {f"slot{i}": 1 for i in range(size)}


def test_not_applicable_when_a_full_bank_holds_none_of_the_held_codes():
    gd = _gd(bank_capacity=50)
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50,
                       bank_items=_full_bank(50))
    assert action.is_applicable(state, gd) is False


def test_still_applicable_for_a_code_the_full_bank_already_holds():
    """A full bank accepts more of a stack it already carries — no new slot."""
    gd = _gd(bank_capacity=50)
    action = _action(gd)
    bank = _full_bank(49)
    bank["copper_ore"] = 1
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50, bank_items=bank)
    assert action.is_applicable(state, gd) is True
    assert [code for code, _ in action._deposits(state)] == ["copper_ore"]


def test_a_full_bank_drops_only_the_unbankable_codes():
    gd = _gd(bank_capacity=50)
    action = _action(gd)
    bank = _full_bank(49)
    bank["iron_ore"] = 1
    state = make_state(inventory={"copper_ore": 40, "iron_ore": 30}, inventory_max=80,
                       bank_items=bank)
    assert [code for code, _ in action._deposits(state)] == ["iron_ore"]


def test_room_in_the_bank_leaves_every_licensed_deposit_alone():
    gd = _gd(bank_capacity=50)
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40, "iron_ore": 30}, inventory_max=80,
                       bank_items=_full_bank(10))
    assert {code for code, _ in action._deposits(state)} == {"copper_ore", "iron_ore"}


def test_an_unread_bank_is_unknown_not_full():
    """`bank_items is None` means the bank has not been read this cycle. Treating
    that as full would refuse every deposit before the first bank visit."""
    gd = _gd(bank_capacity=50)
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50, bank_items=None)
    assert action.is_applicable(state, gd) is True


def test_an_unknown_capacity_is_unknown_not_full():
    """`bank_capacity == 0` is the sentinel for capacity not yet read (the same
    divide-guard BANK_EXPAND uses), not a zero-slot bank."""
    gd = _gd(bank_capacity=0)
    action = _action(gd)
    state = make_state(inventory={"copper_ore": 40}, inventory_max=50,
                       bank_items=_full_bank(50))
    assert action.is_applicable(state, gd) is True
