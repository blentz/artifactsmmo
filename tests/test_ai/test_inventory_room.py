from artifactsmmo_cli.ai.inventory_room import has_room


def test_new_stack_blocked_when_no_free_slot_even_with_qty_room() -> None:
    """A stack-CREATING action needs a free slot even if quantity has headroom
    — the slot-exhaustion bug. slots_free 0, qty_free 50 -> blocked."""
    assert has_room(new_stacks=1, added_qty=1, slots_free=0, qty_free=50) is False


def test_grow_stack_allowed_when_no_free_slot() -> None:
    """Growing a HELD stack needs no new slot — only quantity headroom."""
    assert has_room(new_stacks=0, added_qty=1, slots_free=0, qty_free=50) is True


def test_blocked_when_qty_full_even_with_free_slot() -> None:
    """The quantity cap still binds: no quantity headroom -> blocked."""
    assert has_room(new_stacks=1, added_qty=1, slots_free=5, qty_free=0) is False


def test_allowed_when_both_caps_have_room() -> None:
    assert has_room(new_stacks=1, added_qty=3, slots_free=2, qty_free=10) is True


def test_multi_new_stacks_need_enough_free_slots() -> None:
    """new_stacks may exceed 1 (a swap displacing two distinct items)."""
    assert has_room(new_stacks=2, added_qty=2, slots_free=1, qty_free=10) is False
    assert has_room(new_stacks=2, added_qty=2, slots_free=2, qty_free=10) is True
