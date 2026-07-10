"""Differential test: the real Python pure core
`artifactsmmo_cli.ai.inventory_room.has_room` must agree with the proved Lean
core `InventoryRoom.hasRoom` on EVERY row.

The game enforces BOTH a per-slot cap and a total-quantity cap: a NEW distinct
stack needs a free slot AND quantity headroom; GROWING a held stack
(`new_stacks == 0`) needs only quantity headroom. The independence structure is
pinned by explicit boundary rows below and fuzzed over random integers.

Rows required by the spec (Task 3):
* new-stack-no-slot            -> blocked  (slot conjunct alone forces False)
* grow-stack-no-slot           -> allowed  (new_stacks=0 ignores the slot cap)
* qty-full-with-free-slot      -> blocked  (qty conjunct alone forces False)
* both-room                    -> allowed
* multi-new-stack boundary     -> new_stacks=2 vs slots_free {1 blocked, 2 ok}
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.inventory_room import has_room
from formal.diff.oracle_client import run_oracle

# (new_stacks, added_qty, slots_free, qty_free, expected)
TABLE = [
    # new-stack-no-slot: a distinct new stack with zero free slots is blocked
    # even though the quantity would fit.
    ((1, 5, 0, 10), False),
    # grow-stack-no-slot: new_stacks=0 grows a held stack; ignores the slot cap
    # entirely, admitted on quantity headroom alone.
    ((0, 5, 0, 10), True),
    # qty-full-with-free-slot: a free slot exists but the quantity overflows the
    # total-quantity cap -> blocked.
    ((1, 11, 5, 10), False),
    # both-room: a free slot and quantity headroom -> admitted.
    ((1, 5, 2, 10), True),
    # multi-new-stack boundary: two new stacks need two free slots.
    ((2, 5, 1, 10), False),  # one slot short -> blocked
    ((2, 5, 2, 10), True),   # exactly enough slots -> admitted
    # boundary equalities: new_stacks == slots_free and added_qty == qty_free
    # both pass (the `<=` is inclusive).
    ((2, 10, 2, 10), True),
    # quantity-neutral swap (added_qty=0) trivially passes the qty term.
    ((1, 0, 1, 0), True),
]


def _lean(rows: list[tuple[int, int, int, int]]) -> list[bool]:
    out = run_oracle("inventory_room", [list(r) for r in rows])
    return [o["has_room"] for o in out]


def test_table_python_matches_lean_every_row():
    inputs = [row for row, _ in TABLE]
    lean = _lean(inputs)
    for (new_stacks, added_qty, slots_free, qty_free), expected, lean_room in zip(
            inputs, [e for _, e in TABLE], lean, strict=True):
        py = has_room(new_stacks, added_qty, slots_free, qty_free)
        assert py == expected, (new_stacks, added_qty, slots_free, qty_free, py, expected)
        assert py == lean_room, (new_stacks, added_qty, slots_free, qty_free, py, lean_room)


@settings(max_examples=300)
@given(
    new_stacks=st.integers(min_value=0, max_value=20),
    added_qty=st.integers(min_value=0, max_value=200),
    slots_free=st.integers(min_value=0, max_value=20),
    qty_free=st.integers(min_value=0, max_value=200),
)
def test_has_room_matches_lean(new_stacks, added_qty, slots_free, qty_free):
    py = has_room(new_stacks, added_qty, slots_free, qty_free)
    lean = _lean([(new_stacks, added_qty, slots_free, qty_free)])[0]
    assert py == lean, (new_stacks, added_qty, slots_free, qty_free, py, lean)


def test_grow_ignores_slots_independence():
    """new_stacks=0 admits regardless of how tight the slot budget is, as long
    as the quantity fits -- the grow-stack independence theorem."""
    for slots_free in range(0, 5):
        row = (0, 7, slots_free, 10)
        assert has_room(*row) is True
        assert _lean([row])[0] is True


def test_no_slot_blocks_regardless_of_qty():
    """new_stacks > slots_free blocks regardless of quantity room."""
    for qty_free in (0, 10, 999):
        row = (3, 1, 2, qty_free)  # 3 new stacks, only 2 free slots
        assert has_room(*row) is False
        assert _lean([row])[0] is False


def test_no_qty_blocks_regardless_of_slots():
    """added_qty > qty_free blocks regardless of slot room."""
    for slots_free in (0, 5, 999):
        row = (1, 11, slots_free, 10)
        assert has_room(*row) is False
        assert _lean([row])[0] is False
