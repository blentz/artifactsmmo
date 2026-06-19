"""bank_has_room: the bank can physically accept a deposited item."""

from artifactsmmo_cli.ai.bank_room import bank_has_room


def test_room_when_used_below_capacity():
    assert bank_has_room(True, {"a": 1, "b": 1}, 50) is True


def test_no_room_when_full():
    assert bank_has_room(True, {f"i{n}": 1 for n in range(50)}, 50) is False


def test_no_room_when_capacity_zero():
    assert bank_has_room(True, {}, 0) is False


def test_no_room_when_bank_inaccessible():
    assert bank_has_room(False, {"a": 1}, 50) is False


def test_no_room_when_capacity_unknown():
    assert bank_has_room(True, {"a": 1}, None) is False


def test_no_room_when_bank_unvisited():
    assert bank_has_room(True, None, 50) is False
