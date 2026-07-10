"""Unit tests for the monster-drop loop pure core (proved in
formal/Formal/MonsterDropApply.lean)."""

from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    apply_monster_drops_pure,
    gather_is_applicable_pure,
)


def test_gather_blocked_when_new_drop_needs_slot_but_none_free() -> None:
    """Gathering a NOT-yet-held drop with 0 free slots is blocked even though
    quantity has room (the slot-exhaustion case)."""
    inv = GatherInv(used=20, cap=124, item_count={f"i{n}": 1 for n in range(20)},
                    slots_used=20, slots_max=20)
    # drop_item is a NEW code (not in item_count): needs a slot -> blocked
    assert gather_is_applicable_pure(inv, min_free=1, drop_item="copper_ore") is False


def test_gather_allowed_when_drop_grows_held_stack_with_no_free_slot() -> None:
    """Gathering MORE of a held drop needs no slot -> allowed at 0 free slots
    (quantity permitting)."""
    inv = GatherInv(used=20, cap=124,
                    item_count={"copper_ore": 5, **{f"i{n}": 1 for n in range(19)}},
                    slots_used=20, slots_max=20)
    assert gather_is_applicable_pure(inv, min_free=1, drop_item="copper_ore") is True


def test_gather_applicable_drop_none_ignores_slots() -> None:
    """`drop_item=None` preserves the old quantity-only behavior: with quantity
    room the check passes regardless of the slot budget."""
    inv = GatherInv(used=20, cap=124, item_count={f"i{n}": 1 for n in range(20)},
                    slots_used=20, slots_max=20)
    assert gather_is_applicable_pure(inv, min_free=3) is True


def test_gather_blocked_when_quantity_floor_unmet() -> None:
    """The quantity floor still gates first: below `min_free` free quantity the
    check refuses before the slot term is consulted."""
    inv = GatherInv(used=123, cap=124, item_count={"copper_ore": 5},
                    slots_used=1, slots_max=20)
    assert gather_is_applicable_pure(inv, min_free=3, drop_item="copper_ore") is False


def _inv(used=0, cap=20, **items):
    return GatherInv(used=used, cap=cap, item_count=dict(items))


def test_empty_drops_unchanged():
    inv = _inv(used=3, cap=20, junk=3)
    out = apply_monster_drops_pure(inv, ())
    assert out.item_count == {"junk": 3} and out.used == 3


def test_each_drop_increments_count():
    inv = _inv(used=0, cap=20)
    out = apply_monster_drops_pure(inv, ("feather", "raw_chicken"))
    assert out.item_count == {"feather": 1, "raw_chicken": 1}
    assert out.used == 2


def test_repeated_drop_accumulates():
    inv = _inv(used=0, cap=20, feather=2)
    out = apply_monster_drops_pure(inv, ("feather",))
    assert out.item_count["feather"] == 3
    assert out.used == 1


def test_break_at_capacity():
    """The loop BREAKS when full (does not mint past cap)."""
    inv = _inv(used=19, cap=20, junk=19)
    out = apply_monster_drops_pure(inv, ("feather", "raw_chicken", "egg"))
    assert out.used <= out.cap
    assert out.used == 20  # exactly one drop fit, then break


def test_other_items_preserved():
    inv = _inv(used=2, cap=20, sword=1, shield=1)
    out = apply_monster_drops_pure(inv, ("feather",))
    assert out.item_count["sword"] == 1 and out.item_count["shield"] == 1
    assert out.item_count["feather"] == 1
