"""Unit tests for the monster-drop loop pure core (proved in
formal/Formal/MonsterDropApply.lean)."""

from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    apply_monster_drops_pure,
)


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
