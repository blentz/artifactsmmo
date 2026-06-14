from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
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
