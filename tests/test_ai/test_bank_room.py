"""bank_has_room: the bank can physically accept a deposited item."""

from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(bank_accessible: bool = True) -> SelectionContext:
    return SelectionContext(
        bank_accessible=bank_accessible, bank_required_level=0,
        bank_unlock_monster=None, initial_xp=0, task_exchange_min_coins=1,
        combat_monster=None)


def _gd(capacity: int | None) -> GameData:
    gd = GameData()
    gd._bank_capacity = capacity
    return gd


def test_room_when_used_below_capacity():
    state = make_state(bank_items={"a": 1, "b": 1})
    assert bank_has_room(state, _gd(50), _ctx()) is True


def test_no_room_when_full():
    state = make_state(bank_items={f"i{n}": 1 for n in range(50)})
    assert bank_has_room(state, _gd(50), _ctx()) is False


def test_no_room_when_capacity_zero():
    state = make_state(bank_items={})
    assert bank_has_room(state, _gd(0), _ctx()) is False


def test_no_room_when_bank_inaccessible():
    state = make_state(bank_items={"a": 1})
    assert bank_has_room(state, _gd(50), _ctx(bank_accessible=False)) is False


def test_no_room_when_capacity_unknown():
    state = make_state(bank_items={"a": 1})
    assert bank_has_room(state, _gd(None), _ctx()) is False


def test_no_room_when_bank_unvisited():
    state = make_state(bank_items=None)
    assert bank_has_room(state, _gd(50), _ctx()) is False
