import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ITEM_FOCUS_SLOT,
    SKILL_FOCUS_SLOT,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    focus_key,
    focus_key_str,
)
from tests.test_ai.fixtures import make_state


def _ring_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    return gd


def test_slot_tagged_obtainitem_satisfied_only_when_that_slot_holds_code():
    gd = _ring_gd()
    root = ObtainItem("copper_ring", slot="ring2_slot")
    # ring1 holds it, ring2 empty -> the ring2 root is NOT satisfied.
    s1 = make_state(equipment={"ring1_slot": "copper_ring"})
    assert root.is_satisfied(s1, gd) is False
    # ring2 holds it -> satisfied.
    s2 = make_state(equipment={"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"})
    assert root.is_satisfied(s2, gd) is True


def test_slotless_equippable_unchanged_membership():
    gd = _ring_gd()
    root = ObtainItem("copper_ring")  # slot=None -> today's membership semantics
    assert root.is_satisfied(make_state(equipment={"ring1_slot": "copper_ring"}), gd) is True
    assert root.is_satisfied(make_state(equipment={}), gd) is False


def test_repr_omits_slot_when_none_and_shows_it_when_set():
    assert repr(ObtainItem("copper_boots")) == "ObtainItem(code='copper_boots', quantity=1)"
    assert repr(ObtainItem("copper_ring", slot="ring2_slot")) == (
        "ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot')")


def test_focus_key_covers_every_root_shape_the_walk_can_name():
    """The fix-round-2 defect, as a table. `_gear_root_key` used to duck-type
    `getattr(root, "slot"/"code")` and returned None unless BOTH were `str` —
    true for every root the deleted RANKING built, false for two of the three
    the resolution walk builds. Both keyed to None, `_charge_focus` returned
    early, and the anti-starvation ledger stayed permanently empty.

    All three shapes are asserted together because the defect was precisely
    that one of them was tested and the others were not."""
    assert focus_key(ObtainItem("copper_ring", 1, slot="ring1_slot")) == \
        ("ring1_slot", "copper_ring")
    # The MATERIAL-gated head: `IsThisTargetBlocked` emits `ObtainItem(blocker,
    # qty)` with no slot.
    assert focus_key(ObtainItem("wooden_stick", 1)) == \
        (ITEM_FOCUS_SLOT, "wooden_stick")
    # The SKILL-gated head: no slot, no code at all.
    assert focus_key(ReachSkillLevel(skill="gearcrafting", level=11)) == \
        (SKILL_FOCUS_SLOT, "gearcrafting")
    # …and the level is NOT in the key: the climb is one piece of work as it
    # advances, so `gearcrafting->11` and `->12` must share a ledger entry
    # rather than handing the root a fresh farm window every rung.
    assert focus_key(ReachSkillLevel(skill="gearcrafting", level=12)) == \
        focus_key(ReachSkillLevel(skill="gearcrafting", level=11))


def test_focus_key_declines_the_trunk_and_the_wall_explicitly():
    """Both None arms are DELIBERATE, not fall-throughs. The xp trunk is the
    last-resort alternative every board carries, so ageing it would decay the
    one root that must stay reachable; the wall committed nothing at all."""
    assert focus_key(ReachCharLevel(50)) is None
    assert focus_key(None) is None


def test_focus_key_fails_loudly_on_an_unregistered_kind():
    """A silent None is what produced the defect, so an unknown kind RAISES —
    same policy and same message as `prerequisite_graph.prerequisites`."""
    class _OtherMetaGoal:
        def is_satisfied(self, state, game_data) -> bool:
            return False

    with pytest.raises(AssertionError, match="unhandled MetaGoal kind"):
        focus_key(_OtherMetaGoal())  # type: ignore[arg-type]


def test_focus_key_str_joins_the_pair():
    """The scalar form both JSON snapshots and `dhondt_step` need. Keyed on the
    FULL pair, so two roots sharing a sentinel slot stay distinct."""
    a = focus_key_str((SKILL_FOCUS_SLOT, "gearcrafting"))
    b = focus_key_str((SKILL_FOCUS_SLOT, "jewelrycrafting"))
    assert a == "<skill>|gearcrafting"
    assert a != b
